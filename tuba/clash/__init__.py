"""Structured clash detection API."""

from tuba.clash.engine import ClashEngine, TrimeshClashEngine
from tuba.clash.report import clash_report_to_dict, clash_report_to_markdown
from tuba.clash.types import ClashResult, ClashSeverity

__all__ = [
    "ClashResult",
    "ClashSeverity",
    "ClashEngine",
    "TrimeshClashEngine",
    "clash_report_to_dict",
    "clash_report_to_markdown",
]
