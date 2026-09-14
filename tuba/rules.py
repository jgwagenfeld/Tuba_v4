"""Composable model rule checks for proxy engineering diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from tuba.clash import ClashEngine
from tuba.model import TubaModel
from tuba.physical import element_length
from tuba.refs import EntityRef


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    passed: bool
    severity: str
    message: str
    refs: list[EntityRef] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "refs": [ref.to_dict() for ref in self.refs],
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class RuleReport:
    results: list[RuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
        }


class ModelRule(Protocol):
    rule_id: str

    def evaluate(self, model: TubaModel) -> list[RuleResult]:
        ...


class RuleEngine:
    def __init__(self, rules: list[ModelRule]):
        self.rules = rules

    def evaluate(self, model: TubaModel) -> RuleReport:
        results: list[RuleResult] = []
        for rule in self.rules:
            results.extend(rule.evaluate(model))
        return RuleReport(results=results)


@dataclass(frozen=True)
class SupportSpacingRule:
    max_span_m: float
    rule_id: str = "support_spacing"

    def evaluate(self, model: TubaModel) -> list[RuleResult]:
        results: list[RuleResult] = []
        for elem in model.elements:
            if elem.type not in ("pipe_straight", "pipe_bend"):
                continue
            length = element_length(model, elem)
            if length <= self.max_span_m:
                continue
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    passed=False,
                    severity="warning",
                    message=f"Element {elem.id!r} span {length:.6g} m exceeds max {self.max_span_m:.6g} m.",
                    refs=[EntityRef("element", elem.id)],
                    data={"span_m": length, "max_span_m": self.max_span_m},
                )
            )
        return results


@dataclass(frozen=True)
class ClashFreeRule:
    clearance_m: float = 0.0
    rule_id: str = "clash_free"

    def evaluate(self, model: TubaModel) -> list[RuleResult]:
        results: list[RuleResult] = []
        for clash in ClashEngine().check_model(model, clearance_m=self.clearance_m):
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    passed=False,
                    severity="error" if clash.severity == "hard" else "warning",
                    message=(
                        f"{clash.left} clashes with {clash.right}: "
                        f"penetration {clash.penetration_m:.6g} m."
                    ),
                    refs=[clash.left, clash.right],
                    data=clash.to_dict(),
                )
            )
        return results


def rule_report_to_markdown(report: RuleReport) -> str:
    lines = ["# Rule Report", "", f"Passed: {'yes' if report.passed else 'no'}", ""]
    if not report.results:
        lines.append("No rule diagnostics.")
        return "\n".join(lines) + "\n"
    for result in report.results:
        refs = ", ".join(str(ref) for ref in result.refs)
        lines.append(f"- `{result.rule_id}` [{result.severity}]: {result.message} ({refs})")
    return "\n".join(lines) + "\n"
