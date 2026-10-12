"""Strict records and conservative acceptance for piping search."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import re
from typing import Any, Callable, TypeAlias

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
CHECK_KINDS = {"cold_model", "cold_clearance", "design_requirement", "evidence_verified", "operating_clearance",
               "reaction_force", "displacement", "user_evaluator"}
OUTCOMES = {"rejected_constraint", "evaluation_failed", "incomplete", "feasible_retained",
            "feasible_not_selected", "duplicate", "deferred", "pruned", "selected"}


def json_copy(value: Any) -> Any:
    """Validate literal JSON, preserving precision and rejecting coerced dictionary keys."""
    def validate(item: Any) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) in (list, tuple):
            for child in item:
                validate(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                validate(child)
            return
        raise ValueError("Expected finite JSON literals and string dictionary keys")
    validate(value)
    return json.loads(json.dumps(value, allow_nan=False))


def safe_id(value: str) -> str:
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(10))}
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value)
            or value.endswith(".") or value.split(".")[0].upper() in reserved):
        raise ValueError("Expected a nonempty path-safe identifier")
    return value


def finite(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, not Boolean")
    return float(value)


class Record:
    def to_dict(self) -> dict:
        return json_copy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**json_copy(data))


@dataclass(frozen=True)
class Candidate(Record):
    id: str
    parent_ids: tuple[str, ...]
    parameters: dict[str, JsonValue]
    intent: str

    def __post_init__(self):
        safe_id(self.id)
        object.__setattr__(self, "parent_ids", tuple(safe_id(p) for p in self.parent_ids))
        if self.id in self.parent_ids or len(set(self.parent_ids)) != len(self.parent_ids):
            raise ValueError("Parents must be distinct and cannot include the candidate")
        if type(self.parameters) is not dict:
            raise ValueError("parameters must be a dictionary")
        object.__setattr__(self, "parameters", json_copy(self.parameters))
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ValueError("A proposal intent is required")


@dataclass(frozen=True)
class CheckSpec(Record):
    id: str
    kind: str
    required: bool
    operations: tuple[str, ...]
    target_refs: tuple[str, ...]
    limit: float | None
    unit: str | None
    options: dict[str, JsonValue]

    def __post_init__(self):
        safe_id(self.id)
        if self.kind not in CHECK_KINDS or type(self.required) is not bool:
            raise ValueError("Expected a supported check kind and Boolean required flag")
        object.__setattr__(self, "operations", tuple(safe_id(op) for op in self.operations))
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        if len(set(self.operations)) != len(self.operations):
            raise ValueError("Check operations must be unique")
        if any(not isinstance(ref, str) or not ref for ref in self.target_refs):
            raise ValueError("Target references must be nonempty strings")
        object.__setattr__(self, "options", json_copy(self.options))
        if self.limit is not None:
            finite(self.limit, "limit")
        if self.kind in {"reaction_force", "displacement"}:
            expected = "N" if self.kind == "reaction_force" else "m"
            if self.unit != expected or self.limit is None or self.limit < 0 or not self.target_refs or not self.operations:
                raise ValueError(f"{self.kind} requires targets, operations, nonnegative limit in {expected}")


@dataclass(frozen=True)
class CheckResult(Record):
    constraint_id: str
    verdict: str
    required: bool
    basis: str
    reason_code: str
    message: str
    entity_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, JsonValue] = field(default_factory=dict)
    operation: str | None = None
    result_state_id: str | None = None
    measured_value: float | None = None
    limit: float | None = None
    unit: str | None = None
    comparator: str | None = None

    def __post_init__(self):
        safe_id(self.constraint_id)
        if self.verdict not in {"pass", "fail", "unknown", "not_applicable"} or type(self.required) is not bool:
            raise ValueError("Expected an explicit verdict and Boolean required flag")
        if not self.basis or not self.reason_code or not self.message:
            raise ValueError("Every verdict needs basis, reason and message")
        object.__setattr__(self, "entity_refs", tuple(self.entity_refs))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "details", json_copy(self.details))
        if self.verdict == "not_applicable" and not self.details.get("applicability_condition"):
            raise ValueError("Non-applicability requires an authored condition")
        if self.required and self.verdict == "pass" and self.basis == "prediction":
            raise ValueError("Prediction cannot establish a required pass")
        for name in ("measured_value", "limit"):
            if getattr(self, name) is not None:
                finite(getattr(self, name), name)
        if self.comparator not in {None, "max", "min"}:
            raise ValueError("Unsupported comparator")
        if self.comparator:
            if self.unit not in {"N", "N m", "m", "1", "Pa", "m/s", "kg/s"} or self.limit is None:
                raise ValueError("Numeric checks require a limit and supported canonical unit")
            if self.verdict in {"pass", "fail"}:
                if self.measured_value is None:
                    raise ValueError("A numeric verdict requires a measurement")
                passes = self.measured_value <= self.limit if self.comparator == "max" else self.measured_value >= self.limit
                if passes != (self.verdict == "pass"):
                    raise ValueError("Numeric verdict disagrees with its limit")
                if self.basis == "code_aster" and not (self.operation and self.result_state_id and self.evidence_refs):
                    raise ValueError("Solver measurements require operation, state and evidence")


@dataclass(frozen=True)
class Evaluation(Record):
    id: str
    candidate_id: str
    attempt_id: str
    status: str
    operations: tuple[str, ...]
    completed_operations: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    evidence_manifest_ref: str | None = None
    error_kind: str | None = None
    evidence_manifest_sha256: str | None = None

    def __post_init__(self):
        for value in (self.id, self.candidate_id, self.attempt_id):
            safe_id(value)
        if self.status not in {"complete", "failed", "interrupted", "not_started", "blocked"}:
            raise ValueError("Unsupported evaluation status")
        if self.evidence_manifest_sha256 is not None and not re.fullmatch('[a-f0-9]{64}', self.evidence_manifest_sha256):
            raise ValueError('Expected a SHA-256 sealed-inventory fingerprint')
        object.__setattr__(self, "operations", tuple(self.operations))
        object.__setattr__(self, "completed_operations", tuple(self.completed_operations))
        object.__setattr__(self, "checks", tuple(CheckResult.from_dict(c) if isinstance(c, dict) else c for c in self.checks))
        if not set(self.completed_operations) <= set(self.operations):
            raise ValueError("Completed operations must belong to the evaluation")


@dataclass(frozen=True)
class Decision(Record):
    candidate_id: str
    evaluation_id: str
    outcome: str
    reason_codes: tuple[str, ...]
    primary_constraint_id: str | None = None
    comparison_ids: tuple[str, ...] = ()
    details: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self):
        safe_id(self.candidate_id)
        safe_id(self.evaluation_id)
        if self.outcome not in OUTCOMES:
            raise ValueError("Unsupported decision outcome")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "comparison_ids", tuple(self.comparison_ids))
        object.__setattr__(self, "details", json_copy(self.details))


@dataclass(frozen=True)
class SearchDefinition(Record):
    parameter_grid: dict[str, tuple[JsonValue, ...]]
    objective_fields: tuple[str, ...]
    candidate_limit: int
    max_solver_calls: int
    max_artifact_bytes: int | None = None

    def __post_init__(self):
        if type(self.parameter_grid) is not dict or not self.parameter_grid:
            raise ValueError("A nonempty parameter grid is required")
        grid = json_copy(self.parameter_grid)
        if any(not key or not values or not isinstance(values, list) for key, values in grid.items()):
            raise ValueError("Grid axes must be named and nonempty")
        object.__setattr__(self, "parameter_grid", {k: tuple(v) for k, v in grid.items()})
        object.__setattr__(self, "objective_fields", tuple(self.objective_fields))
        if not self.objective_fields or any(f not in {"pipe_length_m", "bend_count", "support_count"} for f in self.objective_fields):
            raise ValueError("Declare supported objective fields")
        for name in ("candidate_limit", "max_solver_calls", "max_artifact_bytes"):
            value = getattr(self, name)
            if value is None and name == "max_artifact_bytes":
                continue
            if type(value) is not int or value < (1 if name == "candidate_limit" else 0):
                raise ValueError(f"{name} must be an explicit nonnegative integer budget")


@dataclass(frozen=True)
class EvaluationContext:
    """Inputs shared by grid searches and source-authored candidate evaluation."""
    namespace: dict
    settings: Any
    check_specs: tuple[CheckSpec, ...]
    user_evaluator: Callable | None


@dataclass(frozen=True)
class LoadedSearch:
    project: Any
    namespace: dict
    settings: Any
    definition: SearchDefinition
    check_specs: tuple[CheckSpec, ...]
    build_candidate: Callable
    user_evaluator: Callable | None


def decide(evaluation: Evaluation, check_specs: tuple[CheckSpec, ...], required_operations: tuple[str, ...]) -> Decision:
    """Acceptance is independent of cross-candidate objective ranking."""
    def result(outcome, reasons, primary=None):
        return Decision(evaluation.candidate_id, evaluation.id, outcome, tuple(reasons), primary)
    if evaluation.error_kind or evaluation.status == "failed":
        return result("evaluation_failed", (evaluation.error_kind or "execution_failed",))
    required_ids = {spec.id for spec in check_specs if spec.required}
    failures = [c for c in evaluation.checks if c.verdict == "fail" and (c.required or c.constraint_id in required_ids)]
    if failures:
        return result("rejected_constraint", [c.reason_code for c in failures], failures[0].constraint_id)
    missing = []
    if evaluation.status != "complete":
        missing.append(evaluation.status)
    if not set(required_operations) <= set(evaluation.completed_operations):
        missing.append("operations_incomplete")
    if not evaluation.evidence_manifest_ref:
        missing.append("evidence_missing")
    for spec in check_specs:
        if not spec.required:
            continue
        scopes = spec.operations or (None,)
        for operation in scopes:
            checks = [c for c in evaluation.checks if c.constraint_id == spec.id and c.operation == operation]
            if not checks or any(c.verdict == "unknown" for c in checks):
                missing.append(f"check_incomplete:{spec.id}")
            for state_id in {c.result_state_id for c in checks} or {None}:
                covered = {ref for c in checks if c.result_state_id == state_id for ref in c.entity_refs}
                if spec.target_refs and not set(spec.target_refs) <= covered:
                    missing.append(f"target_coverage_incomplete:{spec.id}")
            for check in checks:
                if not check.required or (spec.unit and check.unit != spec.unit) or (spec.limit is not None and check.limit != spec.limit):
                    missing.append(f"check_scope_mismatch:{spec.id}")
                if check.verdict == "not_applicable" and check.details.get("applicability_condition") != spec.options.get("applicability_condition"):
                    missing.append(f"applicability_unproven:{spec.id}")
    return result("incomplete", dict.fromkeys(missing)) if missing else result("feasible_retained", ("declared_checks_satisfied",))
