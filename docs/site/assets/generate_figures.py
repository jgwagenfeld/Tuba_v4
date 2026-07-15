"""Render the documentation figures from the real Tuba pipeline.

Run:  .\\.venv\\Scripts\\python.exe docs/site/assets/generate_figures.py
Outputs committed PNGs under docs/site/assets/figures/. No solver required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pyvista as pv
from PIL import Image

from tuba import Model
from tuba.plotting.scenes import build_model_scene
from tuba.plotting.plots import add_local_axes_to_plotter, _add_supports_to_plotter
from tuba.plotting.export import export_screenshot

FIG_DIR = Path(__file__).resolve().parent / "figures"
RES = (1600, 1000)


def _autocrop(path: Path, *, pad_frac: float = 0.05, min_pad: int = 24) -> None:
    """Crop the solid-colour background margin so the subject fills the frame.

    Background colour is read from the top-left corner, so this works on both the
    dark model renders (#111827) and the light route schematics (#f7f8fa) without
    knowing which is which. Padding is a fraction of the subject's larger side, so
    every figure keeps the same visual breathing room regardless of subject size.
    """
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im, dtype=int)
    h, w, _ = arr.shape
    bg = arr[0, 0]
    mask = np.abs(arr - bg).sum(axis=2) > 24
    if not mask.any():
        return
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    pad = max(min_pad, round(pad_frac * max(y1 - y0, x1 - x0)))
    box = (max(0, x0 - pad), max(0, y0 - pad),
           min(w, x1 + 1 + pad), min(h, y1 + 1 + pad))
    im.crop(box).save(path)


def _steel(model: Model) -> None:
    model.add_material(
        "steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6,
        allowable_stress={20.0: 140e6, 180.0: 120e6},
    )


def _render(model, path: Path, *, results=None, deform_scale=None,
            local_axes=False, local_axes_scale=0.45,
            supports=False, supports_scale=0.085, body_opacity=None,
            res=RES, zoom=1.5, post: Optional[Callable[["pv.Plotter"], None]] = None) -> Path:
    plotter = build_model_scene(model, results, off_screen=True, title="",
                                deform_scale=deform_scale)
    if body_opacity is not None:
        # Only the pipe body exists at this point (axes/supports are added below),
        # so make it translucent to reveal the local X axis that runs down the bore.
        for actor in list(plotter.renderer.actors.values()):
            try:
                actor.prop.opacity = body_opacity
            except AttributeError:
                pass
    if local_axes:
        add_local_axes_to_plotter(plotter, model, scale=local_axes_scale)
    if supports:
        _add_supports_to_plotter(plotter, model, scale=supports_scale)
    if post is not None:
        post(plotter)
    plotter.reset_camera()
    plotter.camera.zoom(zoom)
    export_screenshot(plotter, str(path), resolution=res)
    plotter.close()
    _autocrop(path)
    return path


from tuba import PlacementFrame
from tuba.coordinates import CoordinateSystem


def _triad(plotter, origin, cs, scale, labels) -> None:
    origin = np.asarray(origin, dtype=float)
    axes = ((cs.x_axis, "#ff3b30", labels[0]),
            (cs.y_axis, "#7ed321", labels[1]),
            (cs.z_axis, "#2f80ff", labels[2]))
    tips, texts = [], []
    for vec, col, lbl in axes:
        v = np.asarray(vec, dtype=float)
        plotter.add_mesh(pv.Arrow(start=origin, direction=v, scale=scale,
                                  tip_radius=0.07, shaft_radius=0.028),
                         color=col, lighting=False)
        tips.append(origin + v * scale * 1.08)
        texts.append(lbl)
    plotter.add_mesh(pv.Sphere(radius=scale * 0.05, center=origin), color="#e5e7eb")
    plotter.add_point_labels(np.array(tips), texts, font_size=16, text_color="white",
                             shape=None, show_points=False, always_visible=True)


def fig_element_triad(out_dir: Path) -> Path:
    """One straight pipe element with its local X/Y/Z triad (X runs down the bore)."""
    from tuba.plotting.plots import _get_element_local_frame

    m = Model(project_name="ElementTriad")
    _steel(m)
    m.add_pipe_section("DN150", OD=0.1683, WT=0.0071)
    with m.pipe(section="DN150", material="steel", route="P") as p:
        p.start([0.0, 0.0, 0.0])
        p.run(2.5)

    elem = m.elements[0]
    mid = (m.nodes[elem.n1].coords + m.nodes[elem.n2].coords) / 2.0
    frame = _get_element_local_frame(m, elem)
    scale = 0.7

    def label_axes(plotter):
        tips = [mid + np.asarray(v, float) * scale * 1.1 for v in frame]
        plotter.add_point_labels(
            np.array(tips),
            ["local X — along the pipe", "local Y", "local Z"],
            font_size=17, text_color="white", shape=None, show_points=False,
            always_visible=True)

    return _render(m, out_dir / "element_triad.png", local_axes=True,
                   local_axes_scale=scale, body_opacity=0.4, zoom=1.4, post=label_axes)


def fig_placement_frame(out_dir: Path) -> Path:
    """World triad + a rotated local placement frame with a pipe authored in local coords."""
    m = Model(project_name="Placement")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    frame = PlacementFrame(id="rack", origin=(2.4, 1.4, 0.4),
                           axis=(0.0, 0.35, 1.0), ref_direction=(1.0, 0.6, 0.0))
    cs = frame.to_coordinate_system()
    start_g = cs.to_global_point(np.array([0.0, 0.0, 0.0]))
    end_g = cs.to_global_point(np.array([1.8, 0.0, 0.0]))
    n1 = m.add_node(start_g.tolist())
    n2 = m.add_node(end_g.tolist())
    m.add_element(id="local_pipe", type="pipe_straight", n1=n1, n2=n2,
                  section="DN100", material="steel")
    plotter = build_model_scene(m, off_screen=True, title="")
    _triad(plotter, (0.0, 0.0, 0.0), CoordinateSystem.identity(), 1.1,
           ["world X", "world Y", "world Z"])
    _triad(plotter, cs.origin, cs, 1.0, ["local X", "local Y", "local Z"])
    plotter.hide_axes()  # redundant with the drawn world triad; its corner widget only skews the crop
    plotter.reset_camera()
    plotter.camera.zoom(1.2)
    export_screenshot(plotter, str(out_dir / "placement_frame.png"), resolution=RES)
    plotter.close()
    _autocrop(out_dir / "placement_frame.png")
    return out_dir / "placement_frame.png"


def fig_builder_route(out_dir: Path) -> Path:
    """Local triad following a pipe through an in-plane and an out-of-plane bend."""
    m = Model(project_name="BuilderRoute")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="P-100") as p:
        p.start([0.0, 0.0, 0.0], support="anchor")
        p.run(2.0)
        p.bend(radius=0.3, angle=90.0, plane="XY")
        p.run(1.5)
        p.bend(radius=0.3, angle=90.0, plane="XZ")
        p.run(1.2)
        p.end(support="anchor")
    return _render(m, out_dir / "builder_route.png", local_axes=True,
                   local_axes_scale=0.45, supports=True, supports_scale=0.085, zoom=1.5)


def fig_supports(out_dir: Path) -> Path:
    """Anchor / guide / rest / spring support glyphs on a routed pipe."""
    m = Model(project_name="Supports")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="S") as p:
        p.start([0.0, 0.0, 0.0], support="anchor")
        p.run(1.5)
        p.add_support(type="guide")
        p.run(1.5)
        p.add_support(type="rest")
        p.run(1.5)
        p.add_support(type="spring")
        p.run(1.5)
        p.end(support="anchor")
    return _render(m, out_dir / "supports.png", supports=True, supports_scale=0.1, zoom=1.4)


def fig_bend_chord_arc(out_dir: Path) -> Path:
    """The FE node chord (tangent-intersection) vs the true stored circular arc."""
    from tuba.model import sample_bend_geometry

    m = Model(project_name="BendChordArc")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="B") as p:
        p.start([0.0, 0.0, 0.0])
        p.run(1.5)
        p.bend(radius=0.6, angle=90.0, plane="XY")
        p.run(1.5)

    plotter = build_model_scene(m, off_screen=True, title="")
    # Straight FE chord: polyline through the actual stored node coordinates.
    order = [e.n1 for e in m.elements] + [m.elements[-1].n2]
    chord = np.array([m.nodes[n].coords for n in order], dtype=float)
    plotter.add_mesh(pv.lines_from_points(chord), color="#f5a623", line_width=6,
                     label="FE node chord")
    plotter.add_mesh(pv.PolyData(chord), color="#f5a623", point_size=14,
                     render_points_as_spheres=True)
    # True arc for the bend element (sampler needs the bend start node as origin).
    bend = next(e for e in m.elements if e.type == "pipe_bend")
    start = m.nodes[bend.n1].coords
    arc = np.asarray(sample_bend_geometry(start, bend.bend_geometry, n_segments=48), dtype=float)
    plotter.add_mesh(pv.lines_from_points(arc), color="#2f80ff", line_width=6,
                     label="true arc")
    plotter.add_point_labels(
        np.array([chord[1], arc[len(arc) // 2]]),
        ["FE node (tangent point)", "true arc"],
        font_size=15, text_color="white", shape=None, show_points=False, always_visible=True)
    plotter.reset_camera()
    plotter.camera.zoom(1.6)
    export_screenshot(plotter, str(out_dir / "bend_chord_arc.png"), resolution=RES)
    plotter.close()
    _autocrop(out_dir / "bend_chord_arc.png")
    return out_dir / "bend_chord_arc.png"


REPO_ROOT = Path(__file__).resolve().parents[3]  # docs/site/assets -> repo root


def _viz_gallery_model() -> Model:
    """The review model that matches the committed viz_gallery_operating study (from notebook 10)."""
    m = Model("VizGalleryDemo", standard="ASME_B31.3")
    m.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5,
                   allowable_stress={20.0: 137e6, 150.0: 127e6})
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)
    m.define_load_case("Operating", gravity=True, pressure=1.5e6,
                       temperature=150.0, ref_temperature=20.0)
    with m.pipe(section="DN100", material="Steel") as b:
        b.start([0, 0, 0], support="anchor")
        b.run(3.0)
        b.add_support(type="guide")
        b.bend(radius=0.3, angle=90, plane="XY")
        b.run(2.0)
        b.add_support(type="rest")
        b.bend(radius=0.3, angle=90, plane="XZ")
        b.run(2.0)
        b.end(support="anchor")
    m.validate()
    return m


def fig_tutorial_model(out_dir: Path) -> Path:
    """The review model as pure geometry — 'just data until it is solved'."""
    return _render(_viz_gallery_model(), out_dir / "tutorial_model.png",
                   supports=True, supports_scale=0.09, zoom=1.4)


def _vmis_legend(plotter) -> None:
    """Replace the default VMIS scalar bar with a titled one that fits the frame.

    The stock bar renders its title and top exponent tick hard against the window
    edge, so both clip. This re-draws the same mapper as an explicit horizontal
    bar, centred and inset, with a readable title and non-clipping ticks (Pa in
    scientific notation — the array is Pa, so no misleading unit conversion)."""
    mappers = plotter.scalar_bars._scalar_bar_mappers.get("VMIS")
    mapper = mappers[0] if mappers else None
    try:
        plotter.remove_scalar_bar("VMIS")
    except (StopIteration, KeyError, IndexError):
        pass
    plotter.add_scalar_bar(
        title="Von Mises stress (Pa)",
        mapper=mapper,
        color="#e5e7eb",
        title_font_size=26,
        label_font_size=20,
        position_x=0.22,
        position_y=0.09,
        width=0.56,
        height=0.045,
        n_labels=5,
        fmt="%.1e",
    )


def fig_money_shot(out_dir: Path) -> Path:
    """Deformed shape + Von Mises stress from the committed viz_gallery_operating study (no solver)."""
    from tuba.analysis.code_aster_notebook import load_or_run_code_aster_results

    model = _viz_gallery_model()
    work_dir = REPO_ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating"
    run = load_or_run_code_aster_results(model, "Operating", work_dir, run_solver=False)
    return _render(model, out_dir / "money_shot.png", results=run.results,
                   deform_scale=35.0, zoom=1.35, res=(1280, 1000), post=_vmis_legend)


def _route_model_and_request():
    """The autorouting demo scene from notebook 05 (two obstacles, A->B request)."""
    from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingConstraints

    m = Model("RouteDemo")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    m.add_obstacle(id="equipment_box", type="cuboid",
                   min_point=[1.5, -0.4, -0.4], max_point=[2.5, 0.4, 0.4])
    m.add_obstacle(id="maintenance_keepout", type="cuboid",
                   min_point=[2.8, 0.8, -0.4], max_point=[3.4, 1.4, 0.8])
    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
        goal=RouteEndpoint("B", (4.0, 0.0, 0.0)),
        section="DN100", material="steel",
        constraints=RoutingConstraints(clearance=0.10, min_bend_radius=0.20),
    )
    return m, request


def fig_route_preroute(out_dir: Path) -> Path:
    """Obstacles + start/goal endpoints before any route exists."""
    from tuba.routing.visualization import build_route_plotter

    m, request = _route_model_and_request()
    plotter = build_route_plotter(m, request=request, off_screen=True)
    plotter.reset_camera()
    plotter.camera.zoom(1.3)
    export_screenshot(plotter, str(out_dir / "route_preroute.png"), resolution=RES)
    plotter.close()
    _autocrop(out_dir / "route_preroute.png")
    return out_dir / "route_preroute.png"


def fig_route_candidates(out_dir: Path) -> Path:
    """Ranked route candidates (selected highlighted) with reserved envelopes around obstacles."""
    from tuba.routing import GridRouter
    from tuba.routing.types import RoutingGridSpec
    from tuba.routing.visualization import build_route_plotter

    m, request = _route_model_and_request()
    # GridRouter.route returns a PipeRouteResult directly (no study files written to disk).
    result = GridRouter(RoutingGridSpec(cell_size=0.25, margin=1.0), candidate_count=3).route(m, request)
    plotter = build_route_plotter(m, request=request, result=result, off_screen=True)
    plotter.reset_camera()
    plotter.camera.zoom(1.3)
    export_screenshot(plotter, str(out_dir / "route_candidates.png"), resolution=RES)
    plotter.close()
    _autocrop(out_dir / "route_candidates.png")
    return out_dir / "route_candidates.png"


FIGURES: dict[str, Callable[[Path], Path]] = {
    "element_triad": fig_element_triad,
    "placement_frame": fig_placement_frame,
    "builder_route": fig_builder_route,
    "supports": fig_supports,
    "bend_chord_arc": fig_bend_chord_arc,
    "tutorial_model": fig_tutorial_model,
    "money_shot": fig_money_shot,
    "route_preroute": fig_route_preroute,
    "route_candidates": fig_route_candidates,
}


def main(out_dir: Path = FIG_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        path = fn(out_dir)
        print(f"OK  {path.relative_to(out_dir.parent)}")


if __name__ == "__main__":
    main()
