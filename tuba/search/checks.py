"""Evidence-backed checks over native geometry and imported Code_Aster states."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from types import SimpleNamespace

from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import ClashEngine
from tuba.physical import physical_properties_for_element
from tuba.project.evidence import evidence_verdict
from tuba.refs import EntityRef

from .contracts import CheckResult, finite


def compare_scalar(*, constraint_id, value, limit, unit, comparator, required, basis,
                   operation, result_state_id, entity_refs, evidence_refs) -> CheckResult:
    finite(limit, "limit")
    available = type(value) in (int, float) and math.isfinite(value)
    verdict = ("pass" if (value <= limit if comparator == "max" else value >= limit) else "fail") if available else "unknown"
    reason = "within_limit" if verdict == "pass" else "limit_exceeded" if verdict == "fail" else "measurement_unavailable"
    return CheckResult(constraint_id, verdict, required, basis, reason,
                       f"Measurement {value if available else 'unavailable'}; {comparator} {limit} {unit}",
                       entity_refs=entity_refs, evidence_refs=evidence_refs, operation=operation,
                       result_state_id=result_state_id, measured_value=float(value) if available else None,
                       limit=limit, unit=unit, comparator=comparator)


def _unsupported_obstacles(model):
    return tuple(o.get("id", "unknown") for o in model.obstacles
                 if o.get("type") not in {"cuboid", "cylinder"}
                 or o.get("min_point") is None or o.get("max_point") is None)


def verification_checks(report, check_specs, *, model=None):
    checks = []
    unsupported = _unsupported_obstacles(model) if model is not None else ()
    coverage_unavailable = model is None or bool(unsupported)
    for spec in check_specs:
        if spec.kind not in {"cold_model", "cold_clearance"}:
            continue
        failed = not report.passed if spec.kind == "cold_model" else bool(report.clashes)
        unknown = (bool(report.validation_errors) and spec.kind == "cold_clearance") or (coverage_unavailable and not failed)
        refs = tuple(dict.fromkeys([str(ref) for clash in report.clashes for ref in (clash.left, clash.right)]
                                  + [f"obstacle:{name}" for name in unsupported]))
        details = report.to_dict() | {"coverage": {"available": not coverage_unavailable,
                                                   "unsupported_obstacle_ids": list(unsupported)}}
        checks.append(CheckResult(spec.id, "unknown" if unknown else "fail" if failed else "pass",
                                  spec.required, "cold_geometry", "coverage_unavailable" if unknown and coverage_unavailable else "invalid_model" if report.validation_errors else
                                  "cold_collision" if failed else "cold_verified", "Cold verification",
                                  entity_refs=refs, details=details))
    return tuple(checks)


def unknown(spec, operation=None, state=None, *, reason="evidence_unavailable", message="Evidence is unavailable", refs=()):
    return CheckResult(spec.id, "unknown", spec.required, "unavailable", reason, message,
                       operation=operation, result_state_id=state.id if state else None,
                       entity_refs=refs, limit=spec.limit, unit=spec.unit)


def _trusted(model, run):
    if run is None:
        return False
    try:
        run.validate_for_publication(model)
    except ValueError:
        return False
    return evidence_verdict(run.study.work_dir, run.study.solver_input_identity).reusable


def _states(run, spec):
    scope = spec.options.get("increments", "all")
    if scope == "all":
        return run.result_states or (run.result_state,)
    if scope == "final":
        return (run.result_state,)
    raise ValueError("increments must be 'all' or 'final'")


def _numeric(model, run, state, operation, spec):
    field = state.node_reactions if spec.kind == "reaction_force" else state.node_displacements
    name = "study_reac.csv" if spec.kind == "reaction_force" else "study_depl.csv"
    evidence = (str(Path(run.study.work_dir) / name),)
    results = []
    for target in spec.target_refs:
        ref = EntityRef.parse(target)
        vector = field.get(ref.id) if ref.kind == "node" and ref.id in model.nodes else None
        available = vector is not None and all(type(v) in (float, int) and math.isfinite(v) for v in vector[:3]) and len(vector) >= 3
        value = math.hypot(*vector[:3]) if available else None
        check = compare_scalar(constraint_id=spec.id, value=value, limit=spec.limit, unit=spec.unit,
                    comparator="max", required=spec.required, basis="code_aster", operation=operation,
                    result_state_id=state.id, entity_refs=(target,), evidence_refs=evidence)
        results.append(replace(check, details={"components": list(vector[:3]) if available else None,
                               "quantity": spec.kind, "components_used": "translation", "increment_scope": spec.options.get("increments", "all")}))
    return results


def _operating(model, run, state, operation, spec):
    envelope = spec.options.get("envelope_type", "insulation")
    clearance = finite(spec.options.get("clearance_m", 0.0), "clearance_m")
    if clearance < 0 or envelope not in {"bare", "insulation", "clearance", "maintenance"}:
        raise ValueError("Declare a supported envelope and nonnegative clearance")
    try:
        if spec.target_refs:
            raise ValueError("M1 operating clearance covers the full model; target subsets are unsupported")
        if _unsupported_obstacles(model):
            raise ValueError("Unsupported obstacle coverage")
        if envelope != "bare" and any(physical_properties_for_element(model, e).insulation_spec_id is None
                                      for e in model.elements if e.type in {"pipe_straight", "pipe_bend"}):
            raise ValueError("Declare insulation for every pipe, or explicitly choose the bare envelope")
        cold = create_cold_geometry_state(model)
        operating = create_operating_geometry_state(model=model, result_state=state, safety_factor=1.0)
        findings = ClashEngine().check_operating_state(model, cold_state=cold, operating_state=operating,
                         result_state=state, envelope_type=envelope, clearance_m=clearance, analysis_mesh=run.analysis_mesh)
    except ValueError as exc:
        return unknown(spec, operation, state, reason="coverage_unavailable", message=str(exc))
    active = [clash for clash in findings if clash.severity != "resolved_in_operating"]
    refs = tuple(dict.fromkeys(str(ref) for clash in active for ref in (clash.left, clash.right)))
    reason = "operating_overlap" if active and envelope != "clearance" else "operating_clearance" if active else "operating_clear"
    return CheckResult(spec.id, "fail" if active else "pass", spec.required, "code_aster", reason,
                       "Operating geometry checked at physical displacement scale",
                       entity_refs=refs, evidence_refs=(str(Path(run.study.work_dir) / "study_depl.csv"),),
                       operation=operation, result_state_id=state.id,
                       details={"clashes": [clash.to_dict() for clash in findings], "envelope_type": envelope,
                                "clearance_m": clearance, "displacement_scale": 1.0,
                                "coverage": {"elements": [e.id for e in model.elements],
                                             "obstacles": [o["id"] for o in model.obstacles],
                                             "obstacle_representation": "native bounding volumes and imported reference surfaces"}})


def _user_checks(model, runs, specs, evaluator, candidate_id):
    requested = {s.id: s for s in specs if s.kind == "user_evaluator"}
    if evaluator is None:
        output = ()
    else:
        output = evaluator(SimpleNamespace(model=model, runs=runs, check_specs=specs, candidate_id=candidate_id))
        if not isinstance(output, tuple) or any(not isinstance(c, CheckResult) for c in output):
            raise ValueError("evaluate_search must return a tuple of CheckResult records")
    for check in output:
        spec = requested.get(check.constraint_id)
        if spec is None:
            raise ValueError("Evaluator returned a check not declared in requested user_evaluator specs")
        if check.required != spec.required or check.operation not in (spec.operations or (None,)) or check.unit != spec.unit or check.limit != spec.limit:
            raise ValueError("Evaluator output differs from declared scope, unit or limit")
        if spec.target_refs and not set(check.entity_refs) <= set(spec.target_refs):
            raise ValueError("Evaluator returned undeclared targets")
        if check.verdict == "not_applicable" and check.details.get("applicability_condition") != spec.options.get("applicability_condition"):
            raise ValueError("Evaluator non-applicability differs from authored condition")
        if check.verdict in {"pass", "fail"}:
            run = runs.get(check.operation)
            if not _trusted(model, run) or check.basis != "code_aster" or not check.evidence_refs:
                raise ValueError("Evaluator verdict requires trusted native evidence")
            states = _states(run, spec)
            if check.result_state_id not in {state.id for state in states}:
                raise ValueError("Evaluator result-state scope is not declared")
            folder = Path(run.study.work_dir).resolve()
            allowed = set(run.result_state.metadata["solve_attestation"]["artifacts"]) | {"study_execution.json"}
            for ref in check.evidence_refs:
                path = Path(ref).resolve()
                if path.parent != folder or path.name not in allowed or not path.is_file():
                    raise ValueError("Evaluator references evidence outside its attested operation")
    checks = list(output)
    for spec in requested.values():
        for operation in spec.operations or (None,):
            run = runs.get(operation)
            states = _states(run, spec) if run else (None,)
            for state in states:
                found = [c for c in output if c.constraint_id == spec.id and c.operation == operation
                         and (c.result_state_id == state.id if state else c.result_state_id is None)]
                covered = {ref for check in found for ref in check.entity_refs}
                missing = tuple(ref for ref in spec.target_refs if ref not in covered)
                if not found or missing:
                    checks.append(unknown(spec, operation, state, reason="evaluator_target_missing" if missing else "evaluator_output_missing",
                                          message="Evaluator coverage is incomplete for this operation/state", refs=missing))
    return checks


def evaluate_checks(model, runs, check_specs, *, user_evaluator=None, candidate_id=None) -> tuple[CheckResult, ...]:
    checks = []
    for spec in check_specs:
        if spec.kind in {"cold_model", "cold_clearance", "user_evaluator"}:
            continue
        for operation in spec.operations:
            run = runs.get(operation)
            if not _trusted(model, run):
                checks.append(unknown(spec, operation))
                continue
            if spec.kind == "evidence_verified":
                checks.append(CheckResult(spec.id, "pass", spec.required, "code_aster", "evidence_verified",
                                          "Native evidence is intact and verified", operation=operation,
                                          result_state_id=run.result_state.id,
                                          evidence_refs=(str(Path(run.study.work_dir) / "study_execution.json"),)))
                continue
            for state in _states(run, spec):
                if spec.kind in {"reaction_force", "displacement"}:
                    checks.extend(_numeric(model, run, state, operation, spec))
                elif spec.kind == "operating_clearance":
                    checks.append(_operating(model, run, state, operation, spec))
    checks.extend(_user_checks(model, runs, check_specs, user_evaluator, candidate_id))
    return tuple(checks)


def render_reason(result: CheckResult) -> str:
    scope = "/".join(part for part in (result.operation, result.result_state_id) if part) or "cold"
    numeric = f"; {result.measured_value} {result.unit} {result.comparator} {result.limit} {result.unit}" if result.comparator else ""
    targets = ", ".join(result.entity_refs) or "declared model scope"
    evidence = ", ".join(result.evidence_refs) or "no solver evidence"
    return f"{result.constraint_id} [{scope}] {result.verdict}: {result.reason_code}; {targets}{numeric}; {result.message}; evidence: {evidence}"
