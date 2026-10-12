"""Read-only history projections and reviews through Tuba's existing web scene."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.clash.types import ClashResult
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.reporting import ReportColumn, ReportTable, build_engineering_review
from tuba.visualization import Issue, SceneBuildOptions, SceneRequest, build_visualization_scene, write_engineering_review_with_scene

from .artifacts import ArtifactStore, atomic_json, digest_file, no_links
from .checks import render_reason
from .contracts import CheckResult, Evaluation, safe_id
from .history import History, encode


def _archive(run_dir):
    root = Path(run_dir).absolute()
    no_links(root)
    if not (root / "history.sqlite3").is_file():
        raise FileNotFoundError("Run history does not exist")
    archive = ArtifactStore(root)
    archive.path("history.sqlite3")
    return archive


def inspect_history(run_dir: Path, candidate_id: str | None = None) -> dict:
    archive = _archive(run_dir)
    with History.open(archive.path("history.sqlite3"), readonly=True) as h:
        manifest, events, candidates = h.manifest(), h.events(), h.candidates()
    if candidate_id is not None and candidate_id not in {c.id for c in candidates}:
        raise ValueError(f"Unknown candidate: {candidate_id}")
    rows = []
    for candidate in candidates:
        if candidate_id is not None and candidate.id != candidate_id:
            continue
        own = [e for e in events if e["candidate_id"] == candidate.id]
        decisions = [e["payload"] | {"sequence": e["sequence"]} for e in own if e["kind"] == "candidate.decision"]
        evaluations = [e["payload"] for e in own if e["kind"] in {"evaluation.completed", "evaluation.failed", "evaluation.interrupted"}]
        recovered = [e["payload"] | {"sequence": e["sequence"]} for e in own if e["kind"] == "attempt.recovered"]
        built = [e["payload"] for e in own if e["kind"] == "candidate.built"]
        completed = evaluations[-1]["completed_operations"] if evaluations else []
        rows.append(candidate.to_dict() | {"outcome": decisions[-1]["outcome"] if decisions else "incomplete",
                    "reason_codes": decisions[-1]["reason_codes"] if decisions else ["decision_not_recorded"],
                    "decisions": decisions, "evaluations": evaluations, "recovered_attempts": recovered, "build": built[-1] if built else None,
                    "unevaluated_operations": [op for op in manifest["settings"]["operations"] if op not in completed]})
    return {"run": manifest, "candidates": rows, "events": events}


def _availability(archive, entry):
    path = archive.path(entry["path"])
    available = "missing" if not path.is_file() else "available" if path.stat().st_size == entry["size_bytes"] and digest_file(path) == entry["sha256"] else "damaged"
    return entry | {"availability": available}


def _new_output(output_dir):
    path = Path(output_dir).absolute()
    no_links(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def _model_artifact(archive, build):
    path = archive.path(build["model_ref"])
    if not path.is_file():
        return {"path": build["model_ref"], "availability": "missing"}
    entry = archive._entry(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        current = hashlib.sha256(encode(data).encode()).hexdigest()
    except (ValueError, UnicodeError):
        current = None
    return entry | {"availability": "available" if current == build["design_digest"] else "damaged",
                    "expected_design_digest": build["design_digest"]}


def export_history(run_dir: Path, output_dir: Path) -> Path:
    archive = _archive(run_dir)
    snapshot = inspect_history(run_dir)
    # A manifest intentionally references the retained archive; it is not a full copy.
    relative_archive = os.path.relpath(archive.root, Path(output_dir).absolute()).replace("\\", "/")
    output = _new_output(output_dir)
    references = {snapshot["run"]["source_manifest_ref"]}
    if snapshot['run'].get('evaluator_manifest_ref'):
        references.add(snapshot['run']['evaluator_manifest_ref'])
    references.update(row['parameters']['source_manifest_ref'] for row in snapshot['candidates']
                      if 'source_manifest_ref' in row['parameters'])
    for event in snapshot["events"]:
        ref = event["payload"].get("evidence_manifest_ref")
        if ref:
            references.add(ref)
    inventories, diagnostics, files, visited = [], [], {}, set()
    inventory_hashes = {evaluation['evidence_manifest_ref']: evaluation.get('evidence_manifest_sha256')
                       for row in snapshot['candidates'] for evaluation in row['evaluations']}
    while references:
        ref = references.pop()
        if ref in visited:
            continue
        visited.add(ref)
        path = archive.path(ref)
        if not path.is_file():
            diagnostics.append({"path": ref, "availability": "missing", "message": "Inventory is unavailable"})
            continue
        try:
            if inventory_hashes.get(ref) and digest_file(path) != inventory_hashes[ref]:
                raise ValueError('Archive integrity failure: sealed inventory changed')
            native = archive.read_inventory(ref)
            entries = [_availability(archive, entry) for entry in native["files"]]
        except (ValueError, UnicodeError) as exc:
            diagnostics.append({"path": ref, "availability": "damaged", "message": str(exc)})
            continue
        inventories.append(native | {"manifest": archive._entry(path), "files": entries})
        files.update((entry["path"], entry) for entry in entries)
        diagnostics.extend({"path": entry["path"], "availability": entry["availability"]} for entry in entries if entry["availability"] != "available")
        references.update(ref for ref in native.get("evidence_links", ()) if ref not in visited)
    for row in snapshot["candidates"]:
        for name, reference in (("model", row["build"]["model_ref"] if row["build"] else None),
                                ("parameters", f"candidates/{row['id']}/parameters.json")):
            if reference:
                path = archive.path(reference)
                entry = _model_artifact(archive, row["build"]) if name == "model" else (
                    archive._entry(path) | {"availability": "available"} if path.is_file() else {"path": reference, "availability": "missing"})
                row[f"{name}_artifact"] = entry
                if entry["availability"] != "available":
                    diagnostics.append({"path": reference, "availability": entry["availability"]})
        for evaluation in row["evaluations"]:
            evaluation["scoped_checks"] = []
            for check in evaluation["checks"]:
                evidence = [files.get(ref, {"path": ref, "availability": "not_in_inventory"}) for ref in check["evidence_refs"]]
                evaluation["scoped_checks"].append({"check": check,
                    "scope": {"candidate_id": row["id"], "attempt_id": evaluation["attempt_id"],
                              "operation": check["operation"], "result_state_id": check["result_state_id"]}, "evidence": evidence})
    payload = {"schema": "tuba.search.replay.v1", "self_contained": False, "archive_relative_path": relative_archive,
               "handoff": "Keep the referenced retained archive. A native candidate review bundle is a separate complete handoff.",
               **snapshot, "inventories": inventories, "availability_diagnostics": diagnostics}
    events_path = output / "events.jsonl"
    with events_path.open("x", encoding="utf-8", newline="\n") as stream:
        for event in snapshot["events"]:
            stream.write(encode(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    payload["events_artifact"] = {"path": "events.jsonl", "sha256": digest_file(events_path), "size_bytes": events_path.stat().st_size}
    atomic_json(output / "search_history.json", payload)
    return output / "search_history.json"


def _clashes(checks, *, operating):
    findings = []
    seen = set()
    for check in checks:
        if (check.operation is not None) != operating:
            continue
        for data in check.details.get("clashes", ()):
            identity = encode(data)
            if identity in seen:
                continue
            seen.add(identity)
            findings.append(ClashResult(EntityRef.from_dict(data["left"]), EntityRef.from_dict(data["right"]),
                         data["severity"], data["distance_m"], data["penetration_m"],
                         tuple(data["location"]) if "location" in data else None,
                         data.get("diagnostics", []), data.get("metadata", {})))
    return findings


def write_candidate_review(run_dir: Path, candidate_id: str, output_dir: Path, *, attempt_id: str | None = None,
                           evaluation_id: str | None = None, include_decisions: bool = True) -> Path:
    safe_id(candidate_id)
    archive = _archive(run_dir)
    snapshot = inspect_history(run_dir, candidate_id)
    row = snapshot["candidates"][0]
    if not row["build"]:
        raise ValueError("Candidate has no archived geometry to review")
    if _model_artifact(archive, row["build"])["availability"] != "available":
        raise ValueError("Candidate geometry integrity check failed")
    model = TubaModel.from_dict(json.loads(archive.path(row["build"]["model_ref"]).read_text(encoding="utf-8")))
    records = row["evaluations"]
    if evaluation_id is not None:
        safe_id(evaluation_id)
        records = [e for e in records if e["id"] == evaluation_id]
        if not records:
            raise ValueError("Unknown candidate evaluation")
    if attempt_id is not None:
        safe_id(attempt_id)
        records = [e for e in records if e["attempt_id"] == attempt_id]
        if not records:
            raise ValueError("Unknown candidate attempt")
    evaluation = Evaluation.from_dict(records[-1]) if records else None
    attempt_decisions = [d for d in row["decisions"] if evaluation is None or d["evaluation_id"] == evaluation.id]
    outcome = attempt_decisions[-1]["outcome"] if attempt_decisions else "incomplete"
    runs, checks = {}, ()
    if evaluation:
        archive.verify_inventory(evaluation.evidence_manifest_ref, expected_sha256=evaluation.evidence_manifest_sha256)
        checks = evaluation.checks
        for event in snapshot["events"]:
            if event["kind"] == "operation.completed" and event["candidate_id"] == candidate_id and event["payload"]["attempt_id"] == evaluation.attempt_id:
                operation = event["payload"]["operation"]
                from tuba.analysis.provenance import SolverInputIdentity
                expected = row['build']['solver_identities'][operation]
                run = import_code_aster_artifacts(model=model, work_dir=archive.path(event["payload"]["artifact_dir"]),
                                                 expected_identity=SolverInputIdentity.from_dict(expected))
                run.validate_for_publication(model)
                runs[operation] = run
    output = _new_output(output_dir)
    staged = stage_runs(runs, output)
    process_payload = None
    import_payload, import_bound, import_refs = None, None, None
    if evaluation:
        process_ref = f"attempts/{evaluation.attempt_id}/process_review.json"
        inventory = archive.read_inventory(evaluation.evidence_manifest_ref)
        retained_paths = {entry["path"] for entry in inventory["files"]}
        source_refs = {"xml": f"attempts/{evaluation.attempt_id}/process_input.xml",
                       "import": f"attempts/{evaluation.attempt_id}/process_import.json"}
        if any(ref in retained_paths or archive.path(ref).exists() for ref in source_refs.values()):
            if not set(source_refs.values()) <= retained_paths:
                raise ValueError("Process import requires a sealed XML and association pair")
            from tuba.process.network import BoundProcessNetwork
            import_payload = json.loads(archive.path(source_refs["import"]).read_text(encoding="utf-8"))
            if (type(import_payload) is not dict or set(import_payload) != {"schema", "source", "bound"}
                    or import_payload["schema"] != "tuba.process.import.v1"):
                raise ValueError("Unsupported retained process import")
            import_bound = BoundProcessNetwork.from_dict(import_payload["bound"])
            import_bound.verify_for(model)
            source = import_payload["source"]
            if (type(source) is not dict or source.get("source_sha256") != digest_file(archive.path(source_refs["xml"]))
                    or source.get("network") != import_bound.network.to_dict()):
                raise ValueError("Process import source or graph does not match its retained association")
            process_output = output / "artifacts" / "process"
            process_output.mkdir(parents=True)
            import_refs = {}
            for name, ref in source_refs.items():
                target = process_output / Path(ref).name
                shutil.copyfile(archive.path(ref), target)
                expected_hash = next(entry["sha256"] for entry in inventory["files"] if entry["path"] == ref)
                if digest_file(target) != expected_hash:
                    raise ValueError("Process import changed during review staging")
                import_refs[name] = target.relative_to(output).as_posix()
        if process_ref in retained_paths:
            process_payload = json.loads(archive.path(process_ref).read_text(encoding="utf-8"))
            from tuba.process.network import BoundProcessNetwork
            network_ref = f"attempts/{evaluation.attempt_id}/hydraulics/network.json"
            if network_ref not in retained_paths:
                raise ValueError("Process review has no sealed route association")
            bound = BoundProcessNetwork.from_dict(json.loads(archive.path(network_ref).read_text(encoding="utf-8")))
            bound.verify_for(model)
            if (process_payload.get("bound_fingerprint") != bound.fingerprint
                    or process_payload.get("geometry_fingerprint") != bound.geometry_fingerprint):
                raise ValueError("Process review does not match its evaluated network")
            if import_bound is not None and (import_bound.fingerprint != bound.fingerprint
                    or process_payload.get("source_refs") != source_refs):
                raise ValueError("Process review does not match its retained import")
            if process_payload.get("source_refs") is not None:
                if import_refs is None:
                    raise ValueError("Process review has no sealed import association")
                process_payload["source_refs"] = import_refs
            fluid_prefix = f"attempts/{evaluation.attempt_id}/hydraulics/"
            fluid_output = output / "artifacts" / "hydraulics"
            fluid_output.mkdir(parents=True)
            for entry in inventory["files"]:
                if entry["path"].startswith(fluid_prefix):
                    relative = Path(entry["path"].removeprefix(fluid_prefix))
                    target = fluid_output / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(archive.path(entry["path"]), target)
            mapping_ref = f"attempts/{evaluation.attempt_id}/fluid_load_mapping.json"
            if any(entry["path"] == mapping_ref for entry in inventory["files"]):
                shutil.copyfile(archive.path(mapping_ref), fluid_output / "fluid_load_mapping.json")
    local_checks = tuple(replace(check, evidence_refs=tuple(f"artifacts/{check.operation}/{Path(ref).name}"
                         for ref in check.evidence_refs)) if check.operation in staged else
                         replace(check, evidence_refs=tuple(f"artifacts/hydraulics/{Path(ref).name}"
                         for ref in check.evidence_refs)) if process_payload and check.basis in ("openmodelica", "pandapipes") else check
                         for check in checks)
    scene = build_visualization_scene(SceneRequest(model, options=SceneBuildOptions(include_physical_envelopes=True),
                   analysis_runs=tuple(staged.values()), clash_results=_clashes(checks, operating=False),
                   operating_clash_results=_clashes(checks, operating=True),
                   volume_export=snapshot["run"]["settings"]["volume_export"], scene_id=f"scene:search:{candidate_id}"))
    if process_payload is not None:
        # Only an entry in the already verified sealed inventory may add fluid
        # fields. An untracked JSON file beside an old attempt is not evidence.
        from tuba.process.review import attach_process_review
        attach_process_review(scene, process_payload)
    if import_payload is not None:
        scene.extra["process_import"] = {"source": import_payload["source"], "source_refs": import_refs,
                                         "bound_fingerprint": import_bound.fingerprint,
                                         "geometry_fingerprint": import_bound.geometry_fingerprint}
    metadata = {"run_id": snapshot["run"]["run_id"], "candidate_id": candidate_id,
                "evaluation_id": evaluation.id if evaluation else None,
                "attempt_id": evaluation.attempt_id if evaluation else None, "outcome": outcome,
                "current_candidate_outcome": row["outcome"], "attempt_decisions": attempt_decisions,
                "evaluation_status": evaluation.status if evaluation else "not_started", "solved_operations": list(staged),
                "result_status": "code_aster_results" if staged else f"{scene.extra['process']['basis']}_results" if scene.extra.get("process") else "unsolved_preview", "scope": snapshot["run"]["scope"],
                "checks": [check.to_dict() for check in local_checks], "decisions": row["decisions"]}
    if import_refs is not None:
        metadata["process_source_refs"] = import_refs
    if not include_decisions:
        for key in ("outcome", "current_candidate_outcome", "attempt_decisions", "decisions"):
            metadata.pop(key)
        metadata["decision_scope"] = "Replay timeline; this static evidence view contains no candidate decisions"
    scene.extra["search"] = metadata
    for index, check in enumerate(local_checks):
        if check.verdict in {"fail", "unknown"}:
            scene.issues.append(Issue(id=f"issue:search:{index}", type="search_constraint", title=render_reason(check),
                          severity="error" if check.required and check.verdict == "fail" else "warning", status="open",
                          entity_refs=[EntityRef.parse(ref) for ref in check.entity_refs], extra={"search_check": check.to_dict()}))
    for obj in scene.objects:
        matching = [check.constraint_id for check in local_checks if obj.entity_ref and str(obj.entity_ref) in check.entity_refs]
        if matching:
            obj.metadata["search_constraints"] = matching
    review = build_engineering_review(model, analysis_runs=tuple(staged.values()), package_id=f"review:search:{candidate_id}")
    table = ReportTable("search_constraints", "Recorded search constraints", tuple(ReportColumn(key, label) for key, label in
                 (("constraint_id", "Constraint"), ("verdict", "Verdict"), ("operation", "Operation"),
                  ("result_state_id", "State / increment"), ("entity_refs", "Targets"), ("measured_value", "Measurement"),
                  ("limit", "Limit"), ("unit", "Unit"), ("reason_code", "Reason"), ("evidence_refs", "Evidence"))),
                 tuple(check.to_dict() for check in local_checks), "tuba.search recorded checks")
    review = replace(review, tables=(*review.tables, table))
    if import_payload is not None:
        source = import_payload["source"]
        rows = [{"item": label, "value": source.get(key)} for key, label in
                (("dexpi_version", "DEXPI version"), ("profile", "Supported import profile"),
                 ("source_sha256", "Raw source SHA-256"), ("selected_segment", "Selected segment"),
                 ("source_associations", "Original source and native associations"),
                 ("source_data", "Retained source tags"),
                 ("validation", "Import validation scope"))]
        if "source_attribution" in source:
            rows.append({"item": "Source attribution", "value": source["source_attribution"]})
        omitted = source.get("omitted_objects", {})
        rows.append({"item": "Objects outside selected subset", "value": {
            "count": omitted.get("count"), "anonymous_count": omitted.get("anonymous_count"),
            "full_record": import_refs["import"],
        }})
        rows.extend({"item": f"Study assumption: {name}", "value": value}
                    for name, value in source.get("study_assumptions", {}).items())
        rows.extend(({"item": "Operating scenario (SI, absolute pressure)", "value": import_bound.scenario.to_dict()},
                     {"item": "Hydraulic requirements (SI, absolute pressure)", "value": import_bound.requirements.to_dict()},
                     {"item": "Retained source files", "value": import_refs}))
        table = ReportTable("process_import", "DEXPI source and declared study assumptions",
                            (ReportColumn("item", "Input"), ReportColumn("value", "Declared value")),
                            tuple(rows), "Retained input provenance; not solver evidence")
        review = replace(review, tables=(*review.tables, table))
    source_inventory = archive.verify_inventory(row['parameters'].get('source_manifest_ref')
                                               or snapshot["run"]["source_manifest_ref"])
    source_entry = next((f for f in source_inventory["files"] if f.get("logical_name") == "model.py"), None)
    if source_entry is None:
        raise ValueError("Archived authored model is unavailable in the source inventory")
    source = archive.path(source_entry["path"])
    title = f"Search candidate {candidate_id}: {outcome}" if include_decisions else f"Search candidate {candidate_id}: recorded evaluation"
    write_engineering_review_with_scene(review, output, scene=scene, title=title, source=source)
    atomic_json(output / "search_review.json", metadata)
    return output / "scene.json"
