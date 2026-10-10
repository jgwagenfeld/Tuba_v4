"""Bounded sequential search, qualified evidence reuse and explicit selection."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import shutil
import uuid

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.model import TubaModel
from tuba.physical import element_length
from tuba.project import Project, load_project
from tuba.project.execution import execute_project_script, project_namespace
from tuba.project.freshness import expected_identity
from tuba.project.evidence import evidence_verdict
from tuba.project.script import is_generated
from tuba.project.study import study_settings

from .artifacts import ArtifactStore, atomic_json, digest_file, no_links
from .contracts import Candidate, CheckSpec, Decision, Evaluation, LoadedSearch, SearchDefinition, decide, finite, json_copy
from .evaluate import evaluate_candidate
from .history import History, encode


class SearchBlocked(RuntimeError):
    """A runtime, durable-storage or coordinator blocker stops scheduling."""


def digest(value) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


def grid_parameters(definition: SearchDefinition) -> list[dict]:
    keys = sorted(definition.parameter_grid)
    if math.prod(len(definition.parameter_grid[key]) for key in keys) > definition.candidate_limit:
        raise ValueError("Grid exceeds candidate_limit before enumeration")
    return [json_copy(dict(zip(keys, values))) for values in product(*(definition.parameter_grid[key] for key in keys))]


def load_search(project: Project) -> LoadedSearch:
    no_links(project.root)
    study = project.load_study()
    settings = study_settings(study)
    if not settings.operations:
        raise ValueError("Search requires declared Code_Aster study operations")
    namespace = project.run_model()
    source = project.model_path.read_text(encoding="utf-8-sig")
    if is_generated(source) or not callable(namespace.get("build_model")):
        raise ValueError("Search requires authored build_model(parameters) and a bound default model")
    config = execute_project_script(project.root / "search.py", run_name="tuba_search.config")
    definition = config.get("SEARCH")
    if not isinstance(definition, SearchDefinition):
        raise ValueError("search.py must declare SEARCH: SearchDefinition")
    grid_parameters(definition)
    authored = tuple(getattr(study, "SEARCH_CHECKS", ()))
    if any(not isinstance(s, CheckSpec) for s in authored):
        raise ValueError("SEARCH_CHECKS must contain CheckSpec records")
    if len({s.id for s in authored}) != len(authored):
        raise ValueError("Check identifiers must be unique")
    if any(s.kind in {"cold_model", "evidence_verified"} or s.id == "cold.model" or s.id.startswith("evidence.") for s in authored):
        raise ValueError("Mandatory cold/evidence gates cannot be replaced by authored checks")
    if sum(s.kind == "cold_clearance" for s in authored) > 1:
        raise ValueError("M1 supports one explicit cold-clearance policy")
    for spec in authored:
        if not set(spec.operations) <= set(settings.operations):
            raise ValueError(f"Check {spec.id} names an undeclared study operation")
        if spec.kind not in {"cold_clearance", "user_evaluator"} and not spec.operations:
            raise ValueError(f"Check {spec.id} requires operation scope")
        if spec.kind == "cold_clearance" and spec.operations:
            raise ValueError("Cold clearance cannot declare solver operations")
        if spec.kind in {"cold_clearance", "operating_clearance"}:
            if finite(spec.options.get("clearance_m", 0), "clearance_m") < 0:
                raise ValueError("clearance_m must be nonnegative")
    specs = (CheckSpec("cold.model", "cold_model", True, (), (), None, None, {}), *authored,
             *(CheckSpec(f"evidence.{op}", "evidence_verified", True, (op,), (), None, None, {}) for op in settings.operations))
    evaluator = getattr(study, "evaluate_search", None)
    if evaluator is not None and not callable(evaluator):
        raise ValueError("evaluate_search must be callable")
    dependencies = set(namespace["__tuba_project_dependencies__"])
    dependencies.update(config["__tuba_project_dependencies__"])
    dependencies.update(getattr(study, "__tuba_project_dependencies__", ()))
    for key in ("SEARCH_DEPENDENCIES", "SEARCH_ASSETS"):
        for ref in config.get(key, ()):
            if not isinstance(ref, str):
                raise ValueError(f"{key} must contain project-relative path strings")
            path = project.root / ref
            no_links(path.absolute())
            if not path.resolve().is_relative_to(project.root):
                raise ValueError("Explicit dependencies must stay inside the project")
            dependencies.add(path.resolve())
    fingerprints = {str(path): digest_file(path) for path in sorted(dependencies)}
    namespace.update(__search_model_script__=source, __search_dependencies__=tuple(sorted(dependencies)),
                     __search_fingerprints__=fingerprints)
    payload = project.model_path.read_bytes()

    def build_candidate(parameters):
        for path, fingerprint in fingerprints.items():
            if digest_file(Path(path)) != fingerprint:
                raise ValueError("Frozen project source changed during search")
        # Keep local construction-unit imports inside the native isolated context.
        with project_namespace(project.model_path) as fresh:
            exec(compile(payload, str(project.model_path), "exec", dont_inherit=True), fresh)
            model = fresh["build_model"](json_copy(parameters))
        if not isinstance(model, TubaModel) or model is fresh.get("model"):
            raise ValueError("build_model(parameters) must return a fresh TubaModel")
        if any(path not in dependencies for path in fresh["__tuba_project_dependencies__"]):
            raise ValueError("Builder loaded a dependency absent from the frozen inventory; declare SEARCH_DEPENDENCIES")
        return model

    return LoadedSearch(project, namespace, settings, definition, tuple(specs), build_candidate, evaluator)


def storage_report(archive: ArtifactStore) -> dict:
    retained = 0
    for path in archive._files(archive.root):
        try:
            retained += path.stat().st_size
        except FileNotFoundError:  # A committed SQLite journal may disappear between enumeration and stat.
            continue
    return {"retained_bytes": retained, "free_bytes": shutil.disk_usage(archive.root).free}


@contextmanager
def coordinator(archive):
    """OS releases the lock on process death; recovery needs no stale-lock guessing."""
    with archive.path("coordinator.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SearchBlocked("Another coordinator owns this run") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if __import__("os").name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class EvidenceCache:
    def __init__(self, archive, history):
        self.archive, self.history = archive, history
        self.entries = []
        self.collected = set()

    def collect(self, archive, history):
        events = history.events()
        builds = {e["candidate_id"]: e["payload"] for e in events if e["kind"] == "candidate.built"}
        qualified = {e["payload"]["attempt_id"] for e in events if e["kind"] == "evaluation.completed"
                     and e["payload"]["status"] == "complete" and not e["payload"]["error_kind"]
                     and all(c["verdict"] != "unknown" for c in e["payload"]["checks"] if c["required"])}
        for event in events:
            if event["kind"] != "operation.completed" or event["payload"]["attempt_id"] not in qualified:
                continue
            payload = event["payload"]
            key = (str(archive.root), event["sequence"])
            if key in self.collected:
                continue
            ref = f"attempts/{payload['attempt_id']}/inventory.json"
            folder = archive.path(payload["artifact_dir"])
            self.entries.append({"archive": archive, "inventory_ref": ref, "folder": folder,
                                 "run_id": history.manifest()["run_id"], "candidate_id": event["candidate_id"],
                                 "attempt_id": payload["attempt_id"], "operation": payload["operation"],
                                 "identity": builds[event["candidate_id"]]["solver_identities"][payload["operation"]]})
            self.collected.add(key)

    def find(self, identity):
        for entry in self.entries:
            if entry["identity"] != identity.to_dict():
                continue
            # A damaged/unknown attempt is not a cache hit; keep the original history intact.
            try:
                entry["archive"].verify_inventory(entry["inventory_ref"])
            except (OSError, ValueError):
                continue
            if evidence_verdict(entry["folder"], identity).reusable:
                return entry
        return None

    def local_folder(self, entry, identity):
        if entry["archive"].root == self.archive.root:
            return entry["folder"]
        # Across separately owned runs, capture attested bytes once per identity;
        # within a run all candidates refer to the same evidence without copying it.
        reference = f"assets/{identity.fingerprint}/{identity.load_case}/inventory.json"
        inventory_path = self.archive.path(reference)
        if inventory_path.exists():
            self.archive.verify_inventory(reference)
            return inventory_path.parent
        verdict = evidence_verdict(entry["folder"], identity)
        if not verdict.reusable:
            raise ValueError("Parent-run evidence no longer qualifies for reuse")
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        for name in (*verdict.state.attestation["artifacts"], "study_execution.json"):
            source, target = entry["folder"] / name, inventory_path.parent / name
            no_links(source)
            no_links(target)
            if target.exists() and digest_file(target) != digest_file(source):
                raise ValueError("Interrupted parent evidence copy has different bytes")
            if not target.exists():
                shutil.copyfile(source, target)
        files = [self.archive._entry(p) for p in self.archive._files(inventory_path.parent)]
        atomic_json(inventory_path, {"schema": "tuba.search.inventory.v1", "kind": "shared_solver_evidence",
                                    "origin": {k: entry[k] for k in ("run_id", "candidate_id", "attempt_id", "operation")}, "files": files})
        return inventory_path.parent


class SearchSolverPort:
    def __init__(self, archive, history, candidate_id, cache, delegate, settings, budget):
        self.archive, self.history, self.candidate_id = archive, history, candidate_id
        self.cache, self.delegate, self.settings, self.budget = cache, delegate, settings, budget

    def solve_exported_study(self, model, study):
        entry = self.cache.find(study.solver_input_identity)
        if entry:
            folder = self.cache.local_folder(entry, study.solver_input_identity)
            self.history.append("operation.reused", {"attempt_id": Path(study.work_dir).parent.name,
                                "operation": study.load_case, "origin_run_id": entry["run_id"],
                                "origin_candidate_id": entry["candidate_id"], "origin_attempt_id": entry["attempt_id"],
                                "artifact_dir": folder.relative_to(self.archive.root).as_posix(),
                                "entity_mapping": "exact native identity and entity names"}, self.candidate_id)
            return import_code_aster_artifacts(model=model, work_dir=folder, expected_identity=study.solver_input_identity)
        calls = sum(e["kind"] == "solver.invoked" for e in self.history.events())
        if calls >= self.budget:
            raise SearchBlocked("Solver call budget exhausted")
        self.history.append("solver.invoked", {"attempt_id": Path(study.work_dir).parent.name, "operation": study.load_case}, self.candidate_id)
        port = self.delegate if self.delegate is not None else self.settings.solver(study.work_dir)
        return port.solve_exported_study(model, study)


def objective_values(model, fields) -> dict:
    values = {"pipe_length_m": sum(element_length(model, e) for e in model.elements if e.type in {"pipe_straight", "pipe_bend"}),
              "bend_count": sum(e.type == "pipe_bend" for e in model.elements), "support_count": len(model.supports)}
    return {field: finite(values[field], field) for field in fields}


def _manifest(loaded, archive, parent_run_id, *, capture=True):
    if capture:
        ref = archive.capture_source(loaded.project, loaded.namespace["__search_dependencies__"])
        source = archive.verify_inventory(ref)
    else:
        paths = set(loaded.namespace["__search_dependencies__"]) | {loaded.project.root / name for name in ("model.py", "study.py", "search.py")}
        records = [{"logical_name": path.relative_to(loaded.project.root).as_posix(), "sha256": digest_file(path),
                    "size_bytes": path.stat().st_size} for path in sorted(paths)]
        ref, source = None, {"digest": digest(records)}
    definition = loaded.definition.to_dict()
    checks = [s.to_dict() for s in loaded.check_specs]
    settings = {"operations": loaded.settings.operations, "solver_options": loaded.settings.solver_options,
                "volume_export": loaded.settings.volume_export}
    return {"schema": "tuba.search.history.v1", "run_id": "R" + uuid.uuid4().hex,
            "parent_run_id": parent_run_id, "source_manifest_ref": ref, "source_digest": source["digest"],
            "check_digest": digest({"source": source["digest"], "checks": checks}),
            "configuration_digest": digest({"source": source["digest"], "definition": definition, "checks": checks, "settings": settings}),
            "definition": definition, "check_specs": checks, "settings": json_copy(settings),
            "scope": "Feasible only against the declared operations, checks and model assumptions; no implicit piping-standard compliance."}


def run_search(project_root: Path, run_dir: Path, *, resume: bool = False, parent_run_dir: Path | None = None, solver=None) -> dict:
    project = load_project(project_root)
    no_links(Path(run_dir).absolute())
    root = Path(run_dir).absolute()
    if root.resolve().is_relative_to(project.root) or project.root.is_relative_to(root.resolve()):
        raise ValueError("Run archive must be outside the authored source project")
    if parent_run_dir is not None and (resume or Path(parent_run_dir).resolve() == root.resolve()):
        raise ValueError("Parent run is for a distinct new run")
    loaded = load_search(project)
    if not resume and root.exists() and any(root.iterdir()):
        raise FileExistsError("New run directory must be empty")
    if resume and not (root / "history.sqlite3").is_file():
        raise FileNotFoundError("Resume requires an existing run history")
    archive = ArtifactStore(root)
    if resume:
        with History.open(archive.path("history.sqlite3"), readonly=True) as existing:
            if existing.manifest()["configuration_digest"] != _manifest(loaded, archive, None, capture=False)["configuration_digest"]:
                raise ValueError("Resume source/configuration differs; create a new run with --parent-run")
    parent_archive = ArtifactStore(parent_run_dir) if parent_run_dir is not None else None
    parent_id = None
    if parent_archive:
        with History.open(parent_archive.path("history.sqlite3"), readonly=True) as parent:
            parent_id = parent.manifest()["run_id"]
    with coordinator(archive):
        manifest = _manifest(loaded, archive, parent_id)
        h = History.open(archive.path("history.sqlite3")) if resume else History.create(archive.path("history.sqlite3"), manifest)
        with h:
            if resume and h.manifest()["configuration_digest"] != manifest["configuration_digest"]:
                raise ValueError("Resume source/configuration differs; create a new run with --parent-run")
            archive.recover(h)
            previous = [e for e in h.events() if e["kind"] == "run.completed"]
            if resume and previous:
                for event in h.events():
                    if event["kind"] in {"evaluation.completed", "evaluation.failed", "evaluation.interrupted"}:
                        archive.verify_inventory(event["payload"]["evidence_manifest_ref"])
                return previous[-1]["payload"] | storage_report(archive)
            for index, parameters in enumerate(grid_parameters(loaded.definition), 1):
                candidate = Candidate(f"C{index:04d}", (), parameters, "Deterministic authored parameter-grid proposal")
                existing = {c.id for c in h.candidates()}
                if candidate.id not in existing:
                    h.record_candidate(candidate)
                    atomic_json(archive.path(f"candidates/{candidate.id}/parameters.json"), parameters)
            cache = EvidenceCache(archive, h)
            cache.collect(archive, h)
            if parent_archive:
                with History.open(parent_archive.path("history.sqlite3"), readonly=True) as parent:
                    cache.collect(parent_archive, parent)
            evaluations, built, decisions = {}, {}, {}
            for event in h.events():
                if event["kind"] == "candidate.built":
                    built[event["candidate_id"]] = event["payload"]
                elif event["kind"] in {"evaluation.completed", "evaluation.failed"}:
                    evaluations[event["candidate_id"]] = Evaluation.from_dict(event["payload"])
                elif event["kind"] == "candidate.decision":
                    decisions[event["candidate_id"]] = Decision.from_dict(event["payload"])
            if resume:
                # A repaired runtime gets a fresh attempt; its old failure stays in history.
                evaluations = {cid: evaluation for cid, evaluation in evaluations.items()
                               if evaluation.error_kind != "runtime"}
            seen_designs = {data["design_digest"]: cid for cid, data in built.items() if cid in evaluations}
            blocked, stop_reason = False, None
            for candidate in h.candidates():
                if candidate.id in evaluations or (candidate.id in decisions and decisions[candidate.id].outcome == "duplicate"):
                    continue
                storage = storage_report(archive)
                if loaded.definition.max_artifact_bytes is not None and storage["retained_bytes"] >= loaded.definition.max_artifact_bytes:
                    blocked, stop_reason = True, "artifact_byte_budget"
                if stop_reason:
                    decision = Decision(candidate.id, "unexecuted", "deferred", (stop_reason,), details=storage)
                    h.append("candidate.decision", decision.to_dict(), candidate.id)
                    continue
                try:
                    model = loaded.build_candidate(candidate.parameters)
                    identities = {op: expected_identity(model, op, solver_options=loaded.settings.solver_options,
                                   volume_export=loaded.settings.volume_export) for op in loaded.settings.operations}
                    objectives = objective_values(model, loaded.definition.objective_fields)
                except (OSError, ValueError, TypeError) as exc:
                    # A source/model/configuration error is visible and is never a constraint violation.
                    decision = Decision(candidate.id, "unexecuted", "evaluation_failed", (f"builder:{type(exc).__name__}",), details={"message": str(exc)[:4000]})
                    h.append("candidate.decision", decision.to_dict(), candidate.id)
                    if isinstance(exc, OSError):
                        raise
                    continue
                data = {"design_digest": digest(model.to_dict()), "check_digest": h.manifest()["check_digest"],
                        "solver_identities": {op: identity.to_dict() for op, identity in identities.items()}, "objectives": objectives}
                if candidate.id not in built:
                    data["model_ref"] = archive.save_model(candidate.id, model)
                    h.append("candidate.built", data, candidate.id)
                    built[candidate.id] = data
                previous_id = seen_designs.get(data["design_digest"])
                if previous_id is not None and previous_id != candidate.id:
                    h.append("candidate.decision", Decision(candidate.id, "unexecuted", "duplicate", ("identical_design",),
                             comparison_ids=(previous_id,)).to_dict(), candidate.id)
                    continue
                calls = sum(e["kind"] == "solver.invoked" for e in h.events())
                fresh = sum(cache.find(identity) is None for identity in identities.values())
                if calls + fresh > loaded.definition.max_solver_calls:
                    h.append("candidate.decision", Decision(candidate.id, "unexecuted", "deferred", ("solver_call_budget",)).to_dict(), candidate.id)
                    continue
                port = SearchSolverPort(archive, h, candidate.id, cache, solver, loaded.settings, loaded.definition.max_solver_calls)
                evaluation = evaluate_candidate(candidate, model, loaded, archive=archive, history=h, solver=port)
                evaluations[candidate.id] = evaluation
                seen_designs[data["design_digest"]] = candidate.id
                decision = decide(evaluation, loaded.check_specs, loaded.settings.operations)
                h.append("candidate.decision", decision.to_dict(), candidate.id)
                decisions[candidate.id] = decision
                cache.collect(archive, h)
                if evaluation.error_kind == "runtime":
                    blocked, stop_reason = True, "runtime_unavailable"
            feasible = []
            for sequence, candidate in enumerate(h.candidates()):
                evaluation = evaluations.get(candidate.id)
                if evaluation and decide(evaluation, loaded.check_specs, loaded.settings.operations).outcome == "feasible_retained":
                    values = built[candidate.id]["objectives"]
                    feasible.append((tuple(finite(values[f], f) for f in loaded.definition.objective_fields) + (sequence,), candidate.id))
            feasible.sort()
            selected = feasible[0][1] if feasible else None
            for _, candidate_id in feasible:
                outcome = "selected" if candidate_id == selected else "feasible_not_selected"
                comparison = tuple(cid for _, cid in feasible if cid != candidate_id)
                selection = Decision(candidate_id, evaluations[candidate_id].id, outcome,
                                     ("lexicographic_objectives_and_proposal_order",), comparison_ids=comparison,
                                     details={"objective_fields": loaded.definition.objective_fields,
                                              "objectives": built[candidate_id]["objectives"], "selected_candidate_id": selected})
                h.append("candidate.decision", selection.to_dict(), candidate_id)
            storage = storage_report(archive)
            if loaded.definition.max_artifact_bytes is not None and storage["retained_bytes"] > loaded.definition.max_artifact_bytes:
                blocked, stop_reason = True, "artifact_byte_budget"
            summary = {"run_id": h.manifest()["run_id"], "candidate_count": len(h.candidates()),
                       "selected_candidate_id": selected, "feasible_count": len(feasible),
                       "solver_calls": sum(e["kind"] == "solver.invoked" for e in h.events()),
                       "blocked": blocked, "stop_reason": stop_reason, **storage}
            h.append("run.blocked" if blocked else "run.completed", summary)
            return summary
