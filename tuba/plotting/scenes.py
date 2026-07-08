"""Scene-first visualization builders."""

from __future__ import annotations

from typing import Optional

from tuba.model import TubaModel
from tuba.solver.base import FEAResults


def build_model_scene(
    model: TubaModel,
    results: Optional[FEAResults] = None,
    *,
    off_screen: bool = False,
    title: str = "Tuba v4",
    deform_scale: float | None = None,
):
    """Return a PyVista plotter without showing it."""
    import pyvista as pv

    from tuba.plotting.pipeline import build_3d_mesh_from_model

    plotter = pv.Plotter(off_screen=off_screen)
    plotter.set_background("#1a1a2e")

    mesh = build_3d_mesh_from_model(model, results)
    if deform_scale is not None and "DEPL" in mesh.point_data:
        plotter.add_mesh(mesh, color="#9ca3af", opacity=0.25, label="Undeformed")
        mesh = mesh.warp_by_vector("DEPL", factor=deform_scale)

    tubes = mesh
    if tubes.n_points:
        plotter.add_mesh(
            tubes,
            scalars="VMIS" if "VMIS" in tubes.point_data else None,
            cmap="turbo",
        )
    plotter.add_axes()
    plotter.add_title(title, color="white")
    return plotter
