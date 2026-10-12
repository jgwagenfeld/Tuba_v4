"""Coupled candidate evaluation through Tuba's existing retained search history."""

from __future__ import annotations

from dataclasses import asdict
import os

from tuba.project.freshness import expected_identity
from tuba.search.artifacts import atomic_json
from tuba.search.contracts import CheckResult, CheckSpec, EvaluationContext, decide
from tuba.search.evaluate import evaluate_candidate
from tuba.search.run import digest, objective_values

from .structural import apply_fluid_loads


def hydraulic_check_specs(bound):
    """Declare delivery and pressure limits as well as each local velocity limit."""
    requirements = bound.requirements
    limits = [(f"flow.velocity.{index}", requirements.max_velocity_m_s, "m/s",
               (f"element:{segment.element_id}",) if segment.element_id else ())
              for index, segment in enumerate(bound.segments)]
    limits.extend([
        ("flow.delivery", requirements.min_delivered_mass_flow_kg_s, "kg/s", ()),
        ("flow.source_pressure", requirements.max_source_pressure_pa, "Pa", ()),
        ("flow.sink_pressure", requirements.min_sink_pressure_pa, "Pa", ()),
    ])
    return tuple(CheckSpec(name, "design_requirement", True, (), refs, limit, unit, {})
                 for name, limit, unit, refs in limits)


def hydraulic_checks(bound, results):
    """Only unchanged, verified real OpenModelica measurements establish verdicts."""
    results.verify_for(bound)
    segments = {segment.segment_id: segment for segment in results.segments}
    measured = [(segments[segment.segment_id].velocity_m_s, "max") for segment in bound.segments]
    measured.extend([(results.mass_flow_kg_s, "min"), (results.source_pressure_pa, "max"),
                     (results.sink_pressure_pa, "min")])
    checks = []
    for spec, (value, comparator) in zip(hydraulic_check_specs(bound), measured, strict=True):
        passed = value <= spec.limit if comparator == "max" else value >= spec.limit
        checks.append(CheckResult(
            spec.id, "pass" if passed else "fail", True, "openmodelica",
            "hydraulic_limit_satisfied" if passed else spec.id.rsplit(".", 1)[0] + "_limit_exceeded"
            if comparator == "max" else "hydraulic_delivery_or_pressure_insufficient",
            f"{spec.id}: {value:.6g} {spec.unit}; {comparator} {spec.limit:.6g} {spec.unit}",
            entity_refs=spec.target_refs,
            evidence_refs=(results.manifest_path, results.artifacts["csv"]["path"]),
            details={"scenario_id": bound.scenario.id, "bound_fingerprint": bound.fingerprint,
                     "solver": "OpenModelica", "pressure_reference": "absolute"},
            measured_value=value, limit=spec.limit, unit=spec.unit, comparator=comparator,
        ))
    return tuple(checks)


def evaluate_process_candidate(candidate, model, bound, *, backend, archive, history,
                               settings, structural_checks, wall_temperature_model,
                               user_evaluator=None, process_import=None):
    """Evaluate one registered candidate and retain flow, mapping and FEA evidence.

    This is a single steady operating case. The caller owns the History run,
    source snapshot and proposal policy. A hydraulic rejection retains a fluid
    preview and no structural results. The native acceptance decision uses every
    declared check; satisfying them does not establish piping-code compliance.
    """
    if len(settings.operations) != 1:
        raise ValueError("Process coupling currently requires one steady mechanical operation")
    operation = settings.operations[0]
    if archive.path(f"candidates/{candidate.id}/model.json").exists():
        raise ValueError("This candidate already has retained geometry; give every revision a new Candidate ID")
    bound.verify_for(model)
    if process_import is not None:
        process_import.verify_for(bound.network)
    specs = (*hydraulic_check_specs(bound), *structural_checks)
    if len({spec.id for spec in specs}) != len(specs):
        raise ValueError("Coupled check identifiers must be unique")
    required = {spec.id: spec for spec in structural_checks if spec.required}
    if ("cold.model" not in required or required["cold.model"].kind != "cold_model"
            or f"evidence.{operation}" not in required
            or required[f"evidence.{operation}"].kind != "evidence_verified"
            or required[f"evidence.{operation}"].operations != (operation,)):
        raise ValueError("Coupled evaluation requires cold.model and matching evidence gates")

    def prepare(attempt_id):
        folder = archive.path(f"attempts/{attempt_id}")
        mapping = None
        try:
            source_refs = None
            if process_import is not None:
                process_import.verify_for(bound.network)
                source = process_import.to_dict()
                source_refs = {"xml": f"attempts/{attempt_id}/process_input.xml",
                               "import": f"attempts/{attempt_id}/process_import.json"}
                with archive.path(source_refs["xml"]).open("xb") as stream:
                    stream.write(process_import.source_xml)
                    stream.flush()
                    os.fsync(stream.fileno())
                atomic_json(archive.path(source_refs["import"]), {
                    "schema": "tuba.process.import.v1", "source": source, "bound": bound.to_dict(),
                })
                history.append("process.imported", {"attempt_id": attempt_id, "source_refs": source_refs,
                               "source_sha256": source["source_sha256"],
                               "bound_fingerprint": bound.fingerprint}, candidate.id)
            hydraulic = backend.solve(bound, folder / "hydraulics")
            # Even a rejected hydraulic preview must describe the geometry
            # currently being archived, including edits made during execution.
            bound.verify_for(model)
            checks = hydraulic_checks(bound, hydraulic)
            projection = {
                "schema": "tuba.process.review.v1", "basis": "openmodelica",
                "operation": operation, "scenario_id": bound.scenario.id,
                "bound_fingerprint": bound.fingerprint,
                "geometry_fingerprint": bound.geometry_fingerprint,
                "segments": [asdict(segment) for segment in hydraulic.segments],
                "pressure_reference": "absolute", "limitations": list(hydraulic.limitations),
                "provenance": hydraulic.provenance,
            }
            if source_refs is not None:
                projection["source_refs"] = source_refs
            atomic_json(folder / "process_review.json", projection)
            history.append("process.evaluated", {"attempt_id": attempt_id,
                           "bound_fingerprint": bound.fingerprint,
                           "hydraulic_checks_passed": all(check.verdict == "pass" for check in checks)}, candidate.id)
            if all(check.verdict == "pass" for check in checks):
                mapping = apply_fluid_loads(model, bound, hydraulic, operation_name=operation,
                                           wall_temperature_model=wall_temperature_model)
                atomic_json(folder / "fluid_load_mapping.json", mapping.evidence)
            return checks
        finally:
            identities = ({operation: expected_identity(model, operation,
                           solver_options=settings.solver_options,
                           volume_export=settings.volume_export).to_dict()} if mapping else {})
            history.append("candidate.built", {
                "model_ref": archive.save_model(candidate.id, model),
                "design_digest": digest(model.to_dict()),
                "check_digest": digest([spec.to_dict() for spec in specs]),
                "solver_identities": identities,
                "objectives": objective_values(model, ("pipe_length_m", "bend_count", "support_count")),
                "geometry_recovered": False,
            }, candidate.id)

    evaluation = evaluate_candidate(candidate, model,
        EvaluationContext({}, settings, specs, user_evaluator), archive=archive,
        history=history, prepare_attempt=prepare)
    decision = decide(evaluation, specs, settings.operations)
    history.append("candidate.decision", decision.to_dict(), candidate.id)
    return evaluation, decision
