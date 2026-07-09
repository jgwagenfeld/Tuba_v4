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


FIGURES: dict[str, Callable[[Path], Path]] = {
    "sections": fig_sections,
}


def main(out_dir: Path = FIG_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        path = fn(out_dir)
        print(f"OK  {path.relative_to(out_dir.parent)}")


if __name__ == "__main__":
    main()
