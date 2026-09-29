"""Reference figures: a committed, diffable picture of what a study returned.

A solved study folder holds numbers, and numbers in a table are hard to review. This
module renders them as an SVG next to the evidence they came from, with an optional
analytical series beside the solved one, so a reviewer sees the comparison instead of
taking it on trust.

Two constraints shaped it. The figure is written as plain SVG by hand, because Tuba's
core dependencies are numpy, jsonschema and gmsh — a review artifact must not require
a plotting stack. And it is deterministic: the same evidence and the same reference
series produce byte-identical SVG, because a committed figure that changes on every
run is a figure nobody diffs.

Nothing here produces a verdict. A figure shows solved values and, when the example
supplies one, an analytical reference; agreement between them is the example's claim
about its own model, not a code check. Tuba evaluates no standard.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

_STYLES = {
    "solved": {"stroke": "#1d4ed8", "fill": "#1d4ed8", "width": 1.6, "dash": None, "marker": 3.0},
    "reference": {"stroke": "#b45309", "fill": "#b45309", "width": 1.4, "dash": "6 4", "marker": 3.0},
    "envelope": {"stroke": "#6b7280", "fill": "#6b7280", "width": 1.2, "dash": "2 4", "marker": 2.4},
}

_MARGIN_LEFT = 78
_MARGIN_RIGHT = 24
_MARGIN_TOP = 62
_MARGIN_BOTTOM = 92
_PLOT_WIDTH = 640
_PLOT_HEIGHT = 360
#: Above this many points a series is drawn as a line only; per-point markers would
#: overlap into a solid band and hide the line they are meant to mark.
_MARKER_LIMIT = 40
_CANVAS_WIDTH = _MARGIN_LEFT + _PLOT_WIDTH + _MARGIN_RIGHT
_CANVAS_HEIGHT = _MARGIN_TOP + _PLOT_HEIGHT + _MARGIN_BOTTOM

_FONT = "ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"


class ReferenceFigureError(ValueError):
    """A figure was asked for with data it cannot honestly draw."""


@dataclass(frozen=True)
class FigureSeries:
    """One line in the figure: an ordered list of ``(x, y)`` points and how to draw it.

    ``style`` is ``solved`` for Code_Aster output, ``reference`` for an analytical
    solution the example supplies, and ``envelope`` for a band rather than a line.
    """

    label: str
    points: tuple[tuple[float, float], ...]
    style: str = "solved"

    def __post_init__(self) -> None:
        if self.style not in _STYLES:
            raise ReferenceFigureError(
                f"Unknown figure style {self.style!r}; expected one of {sorted(_STYLES)}."
            )
        if not self.points:
            raise ReferenceFigureError(f"Series {self.label!r} holds no points to draw.")
        for x, y in self.points:
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ReferenceFigureError(
                    f"Series {self.label!r} holds a non-finite point ({x}, {y}); "
                    "a figure cannot show a value the solver did not produce."
                )


def compare_series(
    solved: FigureSeries,
    reference: FigureSeries,
    *,
    rtol: float = 0.02,
) -> dict[str, float | int | bool]:
    """Compare a solved series with a reference series, node position by node position.

    The two must share their x coordinates: a reference that was sampled elsewhere
    cannot be differenced against the solved field, and pairing them up anyway would
    invent a number. Returns the point count, the worst absolute and relative
    difference, and whether the worst relative difference is inside *rtol*.
    """
    solved_x = [x for x, _ in solved.points]
    reference_x = [x for x, _ in reference.points]
    if solved_x != reference_x:
        raise ReferenceFigureError(
            f"Series {solved.label!r} and {reference.label!r} were sampled at different "
            "x positions; they cannot be differenced against each other."
        )
    deltas = [abs(y_solved - y_reference) for (_, y_solved), (_, y_reference) in zip(solved.points, reference.points)]
    worst_absolute = max(deltas)
    worst_relative = max(
        (abs(y_solved - y_reference) / abs(y_reference) if y_reference else 0.0)
        for (_, y_solved), (_, y_reference) in zip(solved.points, reference.points)
    )
    return {
        "points": len(deltas),
        "worst_absolute": worst_absolute,
        "worst_relative": worst_relative,
        "within_tolerance": worst_relative <= rtol,
        "rtol": rtol,
    }


def _nice_step(span: float, target_ticks: int = 8) -> float:
    """A round tick step covering *span* in about *target_ticks* intervals."""
    if span <= 0:
        return 1.0
    raw = span / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = multiple * magnitude
        if step >= raw:
            return step
    return 10.0 * magnitude


def _ticks(low: float, high: float, target_ticks: int = 8) -> tuple[float, ...]:
    """Axis ticks on round numbers spanning *low* to *high* inclusive."""
    if high <= low:
        return (low,)
    step = _nice_step(high - low, target_ticks)
    first = math.ceil(low / step) * step
    values: list[float] = []
    value = first
    while value <= high + step * 1e-9:
        values.append(round(value, 12))
        value += step
    return tuple(values) or (low, high)


def _format_tick(value: float) -> str:
    if value == 0:
        return "0"
    magnitude = abs(value)
    if 1e-4 <= magnitude < 1e5:
        return f"{value:.6g}"
    return f"{value:.2e}"


def _limits(series: Sequence[FigureSeries], key: int) -> tuple[float, float]:
    values = [point[key] for item in series for point in item.points]
    low, high = min(values), max(values)
    if low == high:
        span = abs(low) * 0.1 or 1.0
        return low - span, high + span
    pad = (high - low) * 0.08
    return low - pad, high + pad


def _project(item: FigureSeries, x_low: float, x_high: float, y_low: float, y_high: float) -> list[tuple[float, float]]:
    """Map a series' data coordinates into canvas coordinates."""
    x0 = _MARGIN_LEFT
    y0 = _MARGIN_TOP
    return [
        (
            x0 + _PLOT_WIDTH * ((x - x_low) / (x_high - x_low)),
            y0 + _PLOT_HEIGHT - _PLOT_HEIGHT * ((y - y_low) / (y_high - y_low)),
        )
        for x, y in item.points
    ]


def _draw_series(item: FigureSeries, projected: list[tuple[float, float]]) -> list[str]:
    style = _STYLES[item.style]
    dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
    parts = [
        '<polyline points="{}" fill="none" stroke="{}" stroke-width="{}"{} '
        'stroke-linejoin="round" />'.format(
            " ".join(f"{px:.2f},{py:.2f}" for px, py in projected),
            style["stroke"],
            style["width"],
            dash,
        )
    ]
    # A dense field reads as a band; markers on every node would hide the line.
    if len(projected) <= _MARKER_LIMIT:
        radius = style["marker"]
        parts.append(
            f'<g fill="{style["fill"]}">'
            + "".join(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{radius}" />' for px, py in projected)
            + "</g>"
        )
    return parts



def render_reference_figure(
    series: Sequence[FigureSeries],
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    subtitle: str = "",
    note: str = "",
) -> str:
    """Render *series* as a standalone SVG document string.

    The output carries no timestamp, no run id and no host detail, so the same inputs
    render byte-identical and a committed figure only changes when the study or the
    reference changes.
    """
    if not series:
        raise ReferenceFigureError("A figure needs at least one series.")
    x_low, x_high = _limits(series, 0)
    y_low, y_high = _limits(series, 1)
    x_ticks = _ticks(x_low, x_high)
    y_ticks = _ticks(y_low, y_high)
    x_span = x_high - x_low
    y_span = y_high - y_low
    x0 = _MARGIN_LEFT
    y0 = _MARGIN_TOP

    def to_x(value: float) -> float:
        return x0 + _PLOT_WIDTH * ((value - x_low) / x_span)

    def to_y(value: float) -> float:
        return y0 + _PLOT_HEIGHT - _PLOT_HEIGHT * ((value - y_low) / y_span)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_CANVAS_WIDTH}" '
        f'height="{_CANVAS_HEIGHT}" viewBox="0 0 {_CANVAS_WIDTH} {_CANVAS_HEIGHT}" '
        f'font-family=\'{_FONT}\'>',
        f'<rect width="{_CANVAS_WIDTH}" height="{_CANVAS_HEIGHT}" fill="#ffffff" />',
        f'<text x="{x0}" y="28" font-size="16" font-weight="600" fill="#111827">{escape(title)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{x0}" y="46" font-size="11.5" fill="#4b5563">{escape(subtitle)}</text>'
        )

    # Horizontal grid and y tick labels.
    for tick in y_ticks:
        y = to_y(tick)
        parts.append(
            f'<line x1="{x0}" y1="{y:.2f}" x2="{x0 + _PLOT_WIDTH}" y2="{y:.2f}" '
            'stroke="#e5e7eb" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{x0 - 10}" y="{y + 4:.2f}" font-size="11" fill="#6b7280" '
            f'text-anchor="end">{escape(_format_tick(tick))}</text>'
        )
    for tick in x_ticks:
        x = to_x(tick)
        parts.append(
            f'<text x="{x:.2f}" y="{y0 + _PLOT_HEIGHT + 20}" font-size="11" fill="#6b7280" '
            f'text-anchor="middle">{escape(_format_tick(tick))}</text>'
        )

    parts.append(
        f'<line x1="{x0}" y1="{y0 + _PLOT_HEIGHT}" x2="{x0 + _PLOT_WIDTH}" '
        f'y2="{y0 + _PLOT_HEIGHT}" stroke="#9ca3af" stroke-width="1" />'
    )
    parts.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + _PLOT_HEIGHT}" '
        'stroke="#9ca3af" stroke-width="1" />'
    )

    # References draw under the solved curve. Where the two agree — which is the point
    # of a reference — the solid solved line stays visible and the dashed one hides
    # under it; where they disagree, the dashed line shows at once.
    draw_order = sorted(series, key=lambda item: item.style == "solved")
    for item in draw_order:
        parts.extend(_draw_series(item, _project(item, x_low, x_high, y_low, y_high)))

    parts.append(
        f'<text x="{x0 + _PLOT_WIDTH / 2:.0f}" y="{y0 + _PLOT_HEIGHT + 44}" font-size="12" '
        f'fill="#374151" text-anchor="middle">{escape(xlabel)}</text>'
    )
    parts.append(
        f'<text x="18" y="{y0 + _PLOT_HEIGHT / 2:.0f}" font-size="12" fill="#374151" '
        f'text-anchor="middle" transform="rotate(-90 18 {y0 + _PLOT_HEIGHT / 2:.0f})">'
        f'{escape(ylabel)}</text>'
    )

    # Legend, one row per series under the axis.
    legend_y = y0 + _PLOT_HEIGHT + 62
    for index, item in enumerate(series):
        style = _STYLES[item.style]
        row_y = legend_y + index * 16
        dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
        parts.append(
            f'<line x1="{x0}" y1="{row_y - 4}" x2="{x0 + 24}" y2="{row_y - 4}" '
            f'stroke="{style["stroke"]}" stroke-width="{style["width"]}"{dash} />'
        )
        parts.append(
            f'<text x="{x0 + 32}" y="{row_y}" font-size="11.5" fill="#374151">'
            f'{escape(item.label)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_reference_figure(path: str | Path, series: Sequence[FigureSeries], **labels: str) -> Path:
    """Write the rendered figure to *path*, creating parent directories as needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_reference_figure(series, **labels), encoding="utf-8", newline="\n")
    return target
