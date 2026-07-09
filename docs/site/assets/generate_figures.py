"""Render the documentation figures from the real Tuba pipeline.

Run:  .\\.venv\\Scripts\\python.exe docs/site/assets/generate_figures.py
Outputs committed PNGs under docs/site/assets/figures/. No solver required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pyvista as pv

from tuba import Model
from tuba.plotting.scenes import build_model_scene
from tuba.plotting.plots import add_local_axes_to_plotter, _add_supports_to_plotter
from tuba.plotting.export import export_screenshot

FIG_DIR = Path(__file__).resolve().parent / "figures"
RES = (1600, 1000)


def _steel(model: Model) -> None:
    model.add_material(
        "steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6,
        allowable_stress={20.0: 140e6, 180.0: 120e6},
    )


def _render(model, path: Path, *, results=None, deform_scale=None,
            local_axes=False, local_axes_scale=0.45,
            supports=False, supports_scale=0.085,
            res=RES, zoom=1.5) -> Path:
    plotter = build_model_scene(model, results, off_screen=True, title="",
                                deform_scale=deform_scale)
    if local_axes:
        add_local_axes_to_plotter(plotter, model, scale=local_axes_scale)
    if supports:
        _add_supports_to_plotter(plotter, model, scale=supports_scale)
    plotter.reset_camera()
    plotter.camera.zoom(zoom)
    export_screenshot(plotter, str(path), resolution=res)
    plotter.close()
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


def fig_sections(out_dir: Path) -> Path:
    m = Model(project_name="Sections")
    _steel(m)
    m.add_pipe_section("Pipe", OD=0.25, WT=0.02)
    m.add_bar_section("Bar", OD=0.18, WT=0.0)
    m.add_cable_section("Cable", radius=0.04, pretension=500.0)
    m.add_rectangular_section("Box", height_y=0.24, height_z=0.14,
                              thickness_y=0.012, thickness_z=0.012)
    m.add_ibeam_section("IBeam", "HE200B")
    members = [("Pipe", "pipe_straight"), ("Bar", "bar"), ("Cable", "cable"),
               ("Box", "beam"), ("IBeam", "beam")]
    for i, (sec, etype) in enumerate(members):
        y = i * 0.7
        n1 = m.add_node([0.0, y, 0.0])
        n2 = m.add_node([1.4, y, 0.0])
        m.add_element(id=f"e_{sec}", type=etype, n1=n1, n2=n2, section=sec, material="steel")
    return _render(m, out_dir / "sections.png", zoom=1.5)


def fig_element_triad(out_dir: Path) -> Path:
    """One straight pipe element with its local X/Y/Z triad."""
    m = Model(project_name="ElementTriad")
    _steel(m)
    m.add_pipe_section("DN150", OD=0.1683, WT=0.0071)
    with m.pipe(section="DN150", material="steel", route="P") as p:
        p.start([0.0, 0.0, 0.0])
        p.run(2.5)
    return _render(m, out_dir / "element_triad.png", local_axes=True,
                   local_axes_scale=0.7, zoom=1.4)


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
    plotter.reset_camera()
    plotter.camera.zoom(1.2)
    export_screenshot(plotter, str(out_dir / "placement_frame.png"), resolution=RES)
    plotter.close()
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


FIGURES: dict[str, Callable[[Path], Path]] = {
    "sections": fig_sections,
    "element_triad": fig_element_triad,
    "placement_frame": fig_placement_frame,
    "builder_route": fig_builder_route,
}


def main(out_dir: Path = FIG_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        path = fn(out_dir)
        print(f"OK  {path.relative_to(out_dir.parent)}")


if __name__ == "__main__":
    main()
