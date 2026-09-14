"""Interactive PyVista visualization helpers for routed pipe scenes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from tuba.model import TubaModel, sample_bend_geometry
from tuba.routing.adapter import candidate_render_points as _candidate_render_points
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
            "Install it with: pip install 'tuba[viz]' "
            "(or 'tuba[notebook-viz]' for interactive notebook rendering)."
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
        if request is None:
            request = result.request
        route_candidates = result.candidates
        selected_index = result.selected_index

    palette = ["#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#1f78b4"]
    for idx, candidate in enumerate(route_candidates):
        selected = idx == selected_index
        color = "#1b9e77" if selected else palette[idx % len(palette)]
        radius = _route_radius(model, request)
        opacity = 1.0 if selected else 0.35
        _add_candidate_bend_geometry(
            plotter,
            model,
            request,
            candidate,
            color=color,
            radius=radius,
            opacity=opacity,
            label=f"candidate {idx}",
        )
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
        points = _element_render_points(model, elem)
        radius = _section_radius(model, elem.section)
        color = "#1f78b4" if elem.type == "pipe_straight" else "#6a3d9a"
        _add_tube_path(plotter, points, radius=radius, color=color, opacity=0.85, label=elem.id)


def _element_render_points(model: TubaModel, elem) -> list[Point3D]:
    p1 = model.nodes[elem.n1].coords
    p2 = model.nodes[elem.n2].coords
    if elem.type != "pipe_bend":
        return [_as_point(p1), _as_point(p2)]
    if elem.bend_geometry is None:
        raise ValueError(f"Cannot visualize pipe bend {elem.id!r} without explicit bend_geometry.")
    return [_as_point(point) for point in sample_bend_geometry(p1, elem.bend_geometry, n_segments=24)]


def _add_candidate_bend_geometry(
    plotter: "pv.Plotter",
    model: TubaModel,
    request: PipeRouteRequest | None,
    candidate: PipeRouteCandidate,
    *,
    color: str,
    radius: float,
    opacity: float,
    label: str,
) -> None:
    points = _candidate_render_points(model, request, candidate)
    _add_tube_path(plotter, points, radius=radius, color=color, opacity=opacity, label=label)


def _add_tube_path(
    plotter: "pv.Plotter",
    points: list[Point3D],
    *,
    radius: float,
    color: str,
    opacity: float,
    label: str,
) -> None:
    clean = [point for point in points if len(point) == 3]
    if len(clean) < 2:
        return
    coords = np.asarray(clean, dtype=float)
    if np.any(np.linalg.norm(np.diff(coords, axis=0), axis=1) <= 1e-12):
        keep = np.concatenate([[True], np.linalg.norm(np.diff(coords, axis=0), axis=1) > 1e-12])
        coords = coords[keep]
    if len(coords) < 2:
        return
    line = pv.PolyData(coords)
    line.lines = np.concatenate([[len(coords)], np.arange(len(coords))])
    plotter.add_mesh(line.tube(radius=radius, n_sides=24, capping=True), color=color, opacity=opacity, label=label)


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


def _as_point(point) -> Point3D:
    return (float(point[0]), float(point[1]), float(point[2]))


def _section_radius(model: TubaModel, section_name: str) -> float:
    if section_name not in model.sections:
        raise ValueError(f"Cannot visualize route geometry: section {section_name!r} is not defined.")
    from tuba.plotting.pipeline import get_section_radius

    return get_section_radius(model.sections[section_name])


def _route_radius(model: TubaModel, request: PipeRouteRequest | None) -> float:
    if request is None:
        raise ValueError("Cannot visualize route candidates without a PipeRouteRequest section.")
    return _section_radius(model, request.section)
