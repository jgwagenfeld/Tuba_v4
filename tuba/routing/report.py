"""Engineer-readable route reports."""

from __future__ import annotations

import json
import math
from pathlib import Path

from tuba.model import TubaModel
from tuba.routing.types import NetworkRouteResult, PipeRouteResult, route_result_to_dict


def write_route_report(
    result: PipeRouteResult | NetworkRouteResult,
    output_dir: str | Path,
    *,
    model: TubaModel | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = route_result_to_dict(result)
    (out / "route_result.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    report_path = out / "route_report.md"
    if isinstance(result, PipeRouteResult):
        report_text = _single_route_markdown(result)
    else:
        report_text = _network_route_markdown(result)
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def _single_route_markdown(result: PipeRouteResult) -> str:
    request = result.request
    selected = result.selected
    lines = [
        f"# Route Report: {request.id}",
        "",
        "## Inputs",
        "",
        f"- Start: `{request.start.id}` {request.start.point}",
        f"- Goal: `{request.goal.id}` {request.goal.point}",
        f"- Section: `{request.section}`",
        f"- Material: `{request.material}`",
        f"- Clearance: `{request.constraints.clearance}`",
        f"- Insulation thickness: `{request.constraints.insulation_thickness}`",
        f"- Minimum bend radius: `{request.constraints.min_bend_radius}`",
        "",
        "## Candidate Comparison",
        "",
        "| Candidate | Valid | Cost | Length | Bends | Diagnostics |",
        "|---:|:---:|---:|---:|---:|---|",
    ]
    for idx, candidate in enumerate(result.candidates):
        lines.append(
            "| {idx} | {valid} | {cost:.3f} | {length:.3f} | {bends:.0f} | {diag} |".format(
                idx=idx,
                valid="yes" if candidate.is_valid else "no",
                cost=candidate.cost,
                length=candidate.cost_breakdown.get("length", 0.0),
                bends=candidate.cost_breakdown.get("bends", 0.0),
                diag="; ".join(candidate.diagnostics),
            )
        )
    lines.extend(["", "## Selected Route", ""])
    if selected is None:
        lines.append("No route selected.")
    else:
        low_z, high_z = _low_high_elevation(selected.points)
        lines.append(f"- Points: `{selected.points}`")
        lines.append(f"- Cost: `{selected.cost:.3f}`")
        lines.append(f"- Length: `{selected.cost_breakdown.get('length', _path_length(selected.points)):.3f}`")
        lines.append(f"- Bends: `{selected.cost_breakdown.get('bends', 0.0):.0f}`")
        lines.append(f"- Low / high elevation: `{low_z:.3f}` / `{high_z:.3f}`")
        clash_status = "requires review"
        if selected.is_valid and not selected.diagnostics:
            clash_status = "no candidate diagnostics"
        elif selected.diagnostics:
            clash_status = "; ".join(selected.diagnostics)
        lines.append(f"- Clash status: `{clash_status}`")

        lines.extend(["", "## Support Spans", ""])
        spans = _support_spans(selected.points)
        if spans:
            lines.append(f"- Maximum straight span: `{max(spans):.3f}`")
            lines.append(f"- Span count: `{len(spans)}`")
        else:
            lines.append("- No straight spans found.")

        lines.extend(["", "## Solver / Compliance", ""])
        solver = selected.metadata.get("solver", {})
        compliance = selected.metadata.get("compliance", {})
        if solver:
            lines.append(f"- Solver ran: `{solver.get('solver_ran', False)}`")
            if solver.get("solver_name"):
                lines.append(f"- Solver: `{solver['solver_name']}`")
            if solver.get("study_dir"):
                lines.append(f"- Study directory: `{solver['study_dir']}`")
        else:
            lines.append("- Solver ran: `False`")
        if compliance:
            lines.append(f"- ASME overall pass: `{compliance.get('overall_pass')}`")
            lines.append(f"- Worst sustained ratio: `{compliance.get('worst_sustained_ratio')}`")
            lines.append(f"- Worst expansion ratio: `{compliance.get('worst_expansion_ratio')}`")
        else:
            lines.append("- ASME compliance: `not run`")

        lines.extend(["", "## Known Limitations", ""])
        lines.append("- Centerline routing; engineer review required before construction or stress signoff.")
    if result.diagnostics:
        lines.extend(["", "## Diagnostics", ""])
        lines.extend(f"- {diag}" for diag in result.diagnostics)
    return "\n".join(lines) + "\n"


def _network_route_markdown(result: NetworkRouteResult) -> str:
    lines = [
        f"# Network Route Report: {result.request.id}",
        "",
        "## Candidate Comparison",
        "",
        "| Pipe | Accepted | Cost | Points |",
        "|---|:---:|---:|---:|",
    ]
    for pipe_id, route in result.pipe_results.items():
        selected = route.selected
        lines.append(
            f"| {pipe_id} | {'yes' if selected else 'no'} | {selected.cost if selected else 0.0:.3f} | {len(selected.points) if selected else 0} |"
        )
    if result.unresolved_conflicts:
        lines.extend(["", "## Unresolved Conflicts", ""])
        lines.append("| Pipes | Segments | Distance | Required clearance |")
        lines.append("|---|---|---:|---:|")
        for conflict in result.unresolved_conflicts:
            lines.append(
                "| {pipes} | {segments} | {distance:.6g} | {required:.6g} |".format(
                    pipes=" / ".join(conflict.get("pipes", ("?", "?"))),
                    segments=conflict.get("segments", ("?", "?")),
                    distance=conflict.get("distance", 0.0),
                    required=conflict.get("required_clearance", 0.0),
                )
            )
    if result.diagnostics:
        lines.extend(["", "## Diagnostics", ""])
        lines.extend(f"- {diag}" for diag in result.diagnostics)
    return "\n".join(lines) + "\n"


def _path_length(points: list[tuple[float, float, float]]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))


def _support_spans(points: list[tuple[float, float, float]]) -> list[float]:
    return [_distance(a, b) for a, b in zip(points, points[1:]) if _distance(a, b) > 1e-9]


def _low_high_elevation(points: list[tuple[float, float, float]]) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    zs = [point[2] for point in points]
    return min(zs), max(zs)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3)))
