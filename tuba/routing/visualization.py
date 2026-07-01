"""Interactive PyVista visualization helpers for routed pipe scenes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from tuba.model import TubaModel
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, PipeRouteResult, Point3D

try:
    import pyvista as pv

    _HAS_PYVISTA = True
except ImportError:
    _HAS_PYVISTA = False


def _require_pyvista() -> None:
    if not _HAS_PYVISTA:
        raise ImportError(
            "PyVista is required for route visualization. "
            "Install notebook support with: pip install 'jupyterlab>=3' ipywidgets 'pyvista[all,trame]'"
        )


def build_route_plotter(
    model: TubaModel,
    *,
    request: PipeRouteRequest | None = None,
    result: PipeRouteResult | None = None,
    candidates: Iterable[PipeRouteCandidate] | None = None,
    show_existing_model: bool = True,
    show_obstacles: bool = True,
    show_endpoints: bool = True,
    show_reserved_envelopes: bool = True,
    off_screen: bool = False,
) -> "pv.Plotter":
    """Build a PyVista plotter for interactive route review."""
    _require_pyvista()
    plotter = pv.Plotter(notebook=True, off_screen=off_screen)
    plotter.set_background("#f7f8fa")

    if show_obstacles:
        _add_obstacles(plotter, model)
    if show_existing_model:
        _add_model_pipes(plotter, model)
    if show_endpoints and request is not None:
        _add_endpoint(plotter, request.start.point, "#1b9e77", f"start: {request.start.id}")
        _add_endpoint(plotter, request.goal.point, "#d95f02", f"goal: {request.goal.id}")

    route_candidates = list(candidates or [])
    selected_index = None
    if result is not None:
        route_candidates = result.candidates
        selected_index = result.selected_index

    palette = ["#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#1f78b4"]
    for idx, candidate in enumerate(route_candidates):
        selected = idx == selected_index
        color = "#1b9e77" if selected else palette[idx % len(palette)]
        radius = _route_radius(model, request, selected)
        opacity = 1.0 if selected else 0.35
        _add_candidate(plotter, candidate, color=color, radius=radius, opacity=opacity, label=f"candidate {idx}")
        if show_reserved_envelopes:
            _add_reserved_envelope(
                plotter,
                candidate,
                color="#1b9e77" if selected else color,
                opacity=0.16 if selected else 0.07,
                label=f"candidate {idx} reserved envelope" if selected else None,
            )

    plotter.add_axes()
    plotter.show_grid(color="#d0d5dd")
    plotter.camera_position = "iso"
    return plotter


def show_route_scene(
    model: TubaModel,
    *,
    request: PipeRouteRequest | None = None,
    result: PipeRouteResult | None = None,
    candidates: Iterable[PipeRouteCandidate] | None = None,
    jupyter_backend: str = "html",
):
    """Display an interactive PyVista route scene in Jupyter."""
    plotter = build_route_plotter(
        model,
        request=request,
        result=result,
        candidates=candidates,
        off_screen=False,
    )
    return plotter.show(jupyter_backend=jupyter_backend)


def export_route_scene_html(
    model: TubaModel,
    path: str | Path,
    *,
    request: PipeRouteRequest | None = None,
    result: PipeRouteResult | None = None,
    candidates: Iterable[PipeRouteCandidate] | None = None,
) -> Path:
    """Export the interactive route scene to a standalone HTML file."""
    plotter = build_route_plotter(
        model,
        request=request,
        result=result,
        candidates=candidates,
        off_screen=True,
    )
    try:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        plotter.export_html(str(out))
        return out
    finally:
        plotter.close()


def _add_obstacles(plotter: "pv.Plotter", model: TubaModel) -> None:
    for obs in model.obstacles:
        if obs.get("type") not in ("cuboid", "cylinder"):
            continue
        min_pt = np.asarray(obs["min_point"], dtype=float)
        max_pt = np.asarray(obs["max_point"], dtype=float)
        center = (min_pt + max_pt) / 2.0
        lengths = max_pt - min_pt
        box = pv.Cube(center=center, x_length=lengths[0], y_length=lengths[1], z_length=lengths[2])
        plotter.add_mesh(
            box,
            color="#d95f02",
            opacity=0.25,
            show_edges=True,
            edge_color="#8c2d04",
            label=obs.get("id", "obstacle"),
        )


def _add_model_pipes(plotter: "pv.Plotter", model: TubaModel) -> None:
    if not model.elements:
        return
    for elem in model.elements:
        p1 = tuple(float(v) for v in model.nodes[elem.n1].coords)
        p2 = tuple(float(v) for v in model.nodes[elem.n2].coords)
        radius = model.sections[elem.section].OD / 2.0 if elem.section in model.sections else 0.05
        tube = pv.Tube(pointa=p1, pointb=p2, radius=radius, n_sides=24, capping=True)
        color = "#1f78b4" if elem.type == "pipe_straight" else "#6a3d9a"
        plotter.add_mesh(tube, color=color, opacity=0.85, label=elem.id)


def _add_candidate(
    plotter: "pv.Plotter",
    candidate: PipeRouteCandidate,
    *,
    color: str,
    radius: float,
    opacity: float,
    label: str,
) -> None:
    for seg_idx, (start, end) in enumerate(zip(candidate.points, candidate.points[1:])):
        if np.linalg.norm(np.asarray(end) - np.asarray(start)) <= 1e-12:
            continue
        tube = pv.Tube(pointa=start, pointb=end, radius=radius, n_sides=24, capping=True)
        plotter.add_mesh(tube, color=color, opacity=opacity, label=label if seg_idx == 0 else None)
    for point in candidate.points:
        plotter.add_mesh(pv.Sphere(radius=radius * 1.35, center=point), color=color, opacity=min(1.0, opacity + 0.2))


def _add_endpoint(plotter: "pv.Plotter", point: Point3D, color: str, label: str) -> None:
    clean_point = (float(point[0]), float(point[1]), float(point[2]))
    plotter.add_mesh(pv.Sphere(radius=0.09, center=clean_point), color=color, label=label)
    plotter.add_point_labels(
        [clean_point],
        [label],
        font_size=12,
        text_color="#111827",
        point_color=color,
        shape_opacity=0.35,
    )


def _add_reserved_envelope(
    plotter: "pv.Plotter",
    candidate: PipeRouteCandidate,
    *,
    color: str,
    opacity: float,
    label: str | None,
) -> None:
    bounds = _reserved_envelope_bounds(candidate)
    if bounds is None:
        return
    min_point, max_point = bounds
    center = (min_point + max_point) / 2.0
    lengths = max_point - min_point
    box = pv.Cube(center=center, x_length=lengths[0], y_length=lengths[1], z_length=lengths[2])
    plotter.add_mesh(
        box,
        color=color,
        opacity=opacity,
        show_edges=True,
        edge_color=color,
        label=label,
    )


def _reserved_envelope_bounds(candidate: PipeRouteCandidate) -> tuple[np.ndarray, np.ndarray] | None:
    envelope = candidate.metadata.get("reserved_envelope")
    if not isinstance(envelope, dict):
        return None
    try:
        min_point = np.asarray(envelope["min_point"], dtype=float)
        max_point = np.asarray(envelope["max_point"], dtype=float)
    except (KeyError, TypeError, ValueError):
        return None
    if min_point.shape != (3,) or max_point.shape != (3,):
        return None
    if not np.all(np.isfinite(min_point)) or not np.all(np.isfinite(max_point)):
        return None
    lo = np.minimum(min_point, max_point)
    hi = np.maximum(min_point, max_point)
    if np.any(hi <= lo):
        return None
    return lo, hi


def _route_radius(model: TubaModel, request: PipeRouteRequest | None, selected: bool) -> float:
    if request is not None and request.section in model.sections:
        return model.sections[request.section].OD / 2.0 if selected else model.sections[request.section].OD / 3.5
    return 0.06 if selected else 0.035
