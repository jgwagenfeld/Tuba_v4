"""Native operation evaluation into permanent, never-promoted attempts."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from types import SimpleNamespace
from time import monotonic
import uuid

from tuba.project.evidence import evidence_verdict
from tuba.project.freshness import export_study

from .contracts import Candidate, CheckResult, Evaluation, LoadedSearch


def verification_checks(report, check_specs):
    checks = []
    for spec in check_specs:
        if spec.kind not in {"cold_model", "cold_clearance"}:
            continue
        unknown = bool(report.validation_errors) and spec.kind == "cold_clearance"
        failed = not report.passed if spec.kind == "cold_model" else bool(report.clashes)
        checks.append(CheckResult(spec.id, "unknown" if unknown else "fail" if failed else "pass",
                                  spec.required, "cold_geometry", "invalid_model" if report.validation_errors else
                                  "cold_collision" if failed else "cold_verified", "Cold verification",
                                  details=report.to_dict()))
    return tuple(checks)


def execution_checks(model, runs, specs, *, user_evaluator=None, candidate_id=None):
    """Execution gates; Task 5 extends the native constraint adapters."""
    checks = []
    for spec in specs:
        if spec.kind != "evidence_verified":
            continue
        for operation in spec.operations:
            run = runs.get(operation)
            verified = bool(run and evidence_verdict(run.study.work_dir, run.study.solver_input_identity).reusable)
            checks.append(CheckResult(spec.id, "pass" if verified else "unknown", spec.required,
                                      "code_aster", "evidence_verified" if verified else "evidence_unavailable",
                                      "Native evidence verification", operation=operation,
                                      result_state_id=run.result_state.id if run else None,
                                      evidence_refs=(str(Path(run.study.work_dir) / "study_execution.json"),) if run else ()))
    if user_evaluator is not None:
        results = user_evaluator(SimpleNamespace(model=model, runs=runs, check_specs=specs, candidate_id=candidate_id))
        if not isinstance(results, tuple) or any(not isinstance(c, CheckResult) for c in results):
            raise ValueError("evaluate_search must return a tuple of CheckResult records")
        checks.extend(results)
    return tuple(checks)


def unknown_checks(specs, checks, reason):
    completed = {(c.constraint_id, c.operation) for c in checks}
    return tuple(CheckResult(spec.id, "unknown", spec.required, "unavailable", reason,
                             "Required check has not been evaluated", operation=operation,
                             unit=spec.unit, limit=spec.limit)
                 for spec in specs for operation in (spec.operations or (None,))
                 if (spec.id, operation) not in completed)


def evaluate_candidate(candidate: Candidate, model, loaded: LoadedSearch, *, archive, history, solver=None) -> Evaluation:
    attempt_id = archive.begin_attempt(candidate.id)
    evaluation_id = "E" + uuid.uuid4().hex
    operations = loaded.settings.operations
    runs, checks = {}, []
    history.append("evaluation.started", {"evaluation_id": evaluation_id, "attempt_id": attempt_id,
                                         "operations": operations}, candidate.id)
    status, error_kind, diagnostic = "complete", None, None
    cancelled = False
    try:
        clearance = max((float(s.options.get("clearance_m", 0.0)) for s in loaded.check_specs
                         if s.kind == "cold_clearance"), default=0.0)
        report = model.verify(clearance_m=clearance, script=loaded.namespace.get("__search_model_script__"))
        checks.extend(verification_checks(report, loaded.check_specs))
        history.append("candidate.verified", {"attempt_id": attempt_id, "report": report.to_dict()}, candidate.id)
        cold_failed = not report.passed or any(c.required and c.verdict == "fail" for c in checks)
        if cold_failed:
            status = "not_started"
        else:
            for operation in operations:
                folder = archive.operation_dir(attempt_id, operation)
                exporter = loaded.settings.solver(folder)
                start = monotonic()
                history.append("operation.started", {"attempt_id": attempt_id, "operation": operation}, candidate.id)
                # Recorder calls stay outside the execution exception handler.
                try:
                    study = export_study(exporter, model, operation, folder, loaded.settings.volume_export)
                    port = solver if solver is not None else exporter
                    run = port.solve_exported_study(model, study)
                except KeyboardInterrupt:
                    cancelled, status = True, "interrupted"
                    break
                except (OSError, sqlite3.Error):
                    raise
                except Exception as exc:
                    status, error_kind = "failed", f"solver:{type(exc).__name__}"
                    diagnostic = {"exception_class": type(exc).__name__, "message": str(exc)[:4000]}
                    if isinstance(exc, RuntimeError) and any(word in str(exc).lower() for word in
                            ("runtime", "no code_aster", "not available", "no executable")):
                        error_kind = "runtime"
                    history.append("operation.failed", {"attempt_id": attempt_id, "operation": operation,
                                   "elapsed_s": monotonic() - start, **diagnostic}, candidate.id)
                    break
                try:
                    run.validate_for_publication(model)
                    if not evidence_verdict(run.study.work_dir, run.study.solver_input_identity).reusable:
                        raise ValueError("Native evidence verdict is not reusable")
                except ValueError as exc:
                    status = "blocked"
                    diagnostic = {"exception_class": type(exc).__name__, "message": str(exc)[:4000]}
                    history.append("operation.untrusted", {"attempt_id": attempt_id, "operation": operation,
                                   "elapsed_s": monotonic() - start, **diagnostic}, candidate.id)
                    break
                runs[operation] = run
                history.append("operation.completed", {"attempt_id": attempt_id, "operation": operation,
                    "elapsed_s": monotonic() - start,
                    "result_state_ids": [state.id for state in (run.result_states or (run.result_state,))],
                    "artifact_dir": Path(run.study.work_dir).relative_to(archive.root).as_posix()}, candidate.id)
        # Seal execution before acceptance code can fail or reject the design.
        inventory_ref = archive.seal_attempt(attempt_id, status)
        if not cold_failed and status == "complete":
            try:
                checks.extend(execution_checks(model, runs, loaded.check_specs,
                              user_evaluator=loaded.user_evaluator, candidate_id=candidate.id))
            except (OSError, sqlite3.Error):
                raise
            except Exception as exc:
                status, error_kind = "failed", f"checker:{type(exc).__name__}"
                diagnostic = {"exception_class": type(exc).__name__, "message": str(exc)[:4000]}
    except KeyboardInterrupt:
        cancelled, status = True, "interrupted"
        inventory_ref = archive.seal_attempt(attempt_id, status)
    except (OSError, sqlite3.Error):
        # Preserve every available byte and stop scheduling. Recovery owns missing events.
        archive.seal_attempt(attempt_id, "interrupted")
        raise
    checks.extend(unknown_checks(loaded.check_specs, checks, "evaluation_interrupted" if cancelled else "check_unavailable"))
    evaluation = Evaluation(evaluation_id, candidate.id, attempt_id, status, operations, tuple(runs), tuple(checks), inventory_ref, error_kind)
    if diagnostic:
        history.append("evaluation.diagnostic", {"attempt_id": attempt_id, **diagnostic,
                       "evidence_manifest_ref": inventory_ref}, candidate.id)
    for check in checks:
        history.append("constraint.checked", {"evaluation_id": evaluation_id, "attempt_id": attempt_id,
                       **check.to_dict()}, candidate.id)
    kind = "evaluation.interrupted" if cancelled else "evaluation.failed" if status == "failed" else "evaluation.completed"
    history.append(kind, evaluation.to_dict(), candidate.id)
    if cancelled:
        raise KeyboardInterrupt
    return evaluation
