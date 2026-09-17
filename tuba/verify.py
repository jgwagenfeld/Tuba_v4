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
    """The three checks' native records, plus model-script findings."""

    validation_errors: list[str] = field(default_factory=list)
    clashes: list[ClashResult] = field(default_factory=list)
    rules: RuleReport = field(default_factory=RuleReport)
    script_findings: list[str] = field(default_factory=list)

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
        """Advisory findings: clearance clashes, warning rules, model-script findings."""
        found = [
            f"{clash.left} is within clearance of {clash.right}: {clash.distance_m:.6g} m."
            for clash in self.clashes
            if clash.severity not in _BLOCKING_CLASH_SEVERITIES
        ]
        found += [result.message for result in self.rules.results if not result.passed and result.severity != "error"]
        found += list(self.script_findings)
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
            "script_findings": list(self.script_findings),
        }


def verify_model(
    model: TubaModel,
    *,
    clearance_m: float = 0.0,
    duplicate_tol_m: float | None = None,
    rules: Iterable[ModelRule] = (),
    script: str | None = None,
) -> VerifyReport:
    """Run every cold-model check in one pass and report what blocks a solve.

    Structural validation runs first. When it fails, the geometry stages are skipped
    (the clash engine and the geometric rules need a model whose nodes and references
    exist), so the report carries the validation errors and any model-script findings.

    *rules* is supplementary engineering rules (for example
    ``SupportSpacingRule(max_span_m=...)``); the clash check is always run here and
    must not be repeated in *rules*. *script* is the model-script text, linted as
    advisories when given; generated scripts are exempt inside the lint.
    """
    validation_errors: list[str] = []
    try:
        validate_model(model)
    except ModelValidationError as exc:
        validation_errors = [line for line in str(exc).splitlines() if line]

    script_findings: list[str] = []
    if script is not None:
        from tuba.project.script import check_model_script

        script_findings = check_model_script(script)

    if validation_errors:
        return VerifyReport(validation_errors=validation_errors, script_findings=script_findings)

    clashes = ClashEngine().check_all(
        model, clearance_m=clearance_m, duplicate_tol_m=duplicate_tol_m
    )
    report = RuleEngine(list(rules)).evaluate(model)

    return VerifyReport(
        validation_errors=validation_errors,
        clashes=clashes,
        rules=report,
        script_findings=script_findings,
    )
