"""One cold-model verification gate: structural validation, the join-aware clash
check, and the rule engine, composed into a single report a solver surface must pass.

Advisory findings never block; blocking errors do, so a surface that solves cannot
quietly run only the checks that were convenient to call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from tuba.clash import ClashEngine
from tuba.clash.types import ClashResult
from tuba.model import TubaModel
from tuba.rules import ModelRule, RuleEngine, RuleReport
from tuba.validation import ModelValidationError, validate_model

#: Severities that make a clash blocking. ``check_all`` is a cold check, so today this
#: is ``"hard"``; the operating variants are listed so operating results can reuse the gate.
_BLOCKING_CLASH_SEVERITIES: frozenset[str] = frozenset(
    {"hard", "cold_hard", "operating_hard", "operating_only_hard"}
)


@dataclass(frozen=True)
class VerifyReport:
    """The three checks' native records."""

    validation_errors: list[str] = field(default_factory=list)
    clashes: list[ClashResult] = field(default_factory=list)
    rules: RuleReport = field(default_factory=RuleReport)

    @property
    def errors(self) -> list[str]:
        """Blocking findings: validation errors, hard clashes, error-severity rules."""
        found = list(self.validation_errors)
        found += [
            f"{clash.left} clashes with {clash.right}: penetration {clash.penetration_m:.6g} m."
            for clash in self.blocking_clashes
        ]
        found += [result.message for result in self.rules.results if not result.passed and result.severity == "error"]
        return found

    @property
    def blocking_clashes(self) -> list[ClashResult]:
        return [clash for clash in self.clashes if clash.severity in _BLOCKING_CLASH_SEVERITIES]

    @property
    def warnings(self) -> list[str]:
        """Advisory findings: clearance clashes and warning rules."""
        found = [
            f"{clash.left} is within clearance of {clash.right}: {clash.distance_m:.6g} m."
            for clash in self.clashes
            if clash.severity not in _BLOCKING_CLASH_SEVERITIES
        ]
        found += [result.message for result in self.rules.results if not result.passed and result.severity != "error"]
        return found

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "validation_errors": list(self.validation_errors),
            "clashes": [clash.to_dict() for clash in self.clashes],
            "rules": self.rules.to_dict(),
        }


def verify_model(
    model: TubaModel,
    *,
    clearance_m: float = 0.0,
    duplicate_tol_m: float | None = None,
    rules: Iterable[ModelRule] = (),
) -> VerifyReport:
    """Run every cold-model check in one pass and report what blocks a solve.

    Structural validation runs first. When it fails, the geometry stages are skipped
    (the clash engine and the geometric rules need a model whose nodes and references
    exist), so the report carries the validation errors alone.

    *rules* is supplementary engineering rules (for example
    ``SupportSpacingRule(max_span_m=...)``); the clash check is always run here and
    must not be repeated in *rules*.
    """
    validation_errors: list[str] = []
    try:
        validate_model(model)
    except ModelValidationError as exc:
        validation_errors = [line for line in str(exc).splitlines() if line]

    if validation_errors:
        return VerifyReport(validation_errors=validation_errors)

    clashes = ClashEngine().check_all(
        model, clearance_m=clearance_m, duplicate_tol_m=duplicate_tol_m
    )
    report = RuleEngine(list(rules)).evaluate(model)

    return VerifyReport(
        validation_errors=validation_errors,
        clashes=clashes,
        rules=report,
    )
