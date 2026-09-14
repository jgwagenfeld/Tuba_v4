"""Clash report serialization helpers."""

from __future__ import annotations

from tuba.clash.types import ClashResult


def clash_report_to_dict(clashes: list[ClashResult]) -> dict:
    return {
        "clash_count": len(clashes),
        "clashes": [clash.to_dict() for clash in clashes],
    }


def clash_report_to_markdown(clashes: list[ClashResult]) -> str:
    if not clashes:
        return "# Clash Report\n\nNo clashes found.\n"
    lines = ["# Clash Report", "", f"Clashes: {len(clashes)}", ""]
    for clash in clashes:
        lines.append(
            f"- `{clash.left}` vs `{clash.right}`: {clash.severity}, "
            f"penetration `{clash.penetration_m:.6g} m`"
        )
    return "\n".join(lines) + "\n"
