"""Structured clash detection API."""

from tuba.clash.engine import ClashEngine
from tuba.clash.types import ClashResult, ClashSeverity

__all__ = [
    "ClashResult",
    "ClashSeverity",
    "ClashEngine",
]
