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
    plotter.set_background("#111827")

    mesh = build_3d_mesh_from_model(model, results)
    if deform_scale is not None and "DEPL" in mesh.point_data:
        plotter.add_mesh(
            mesh,
            color="#9ca3af",
            opacity=0.25,
            label="Undeformed",
            show_edges=True,
            edge_color="#e5e7eb",
        )
        mesh = mesh.warp_by_vector("DEPL", factor=deform_scale)

    tubes = mesh
    if tubes.n_points:
        scalar_key = "VMIS" if results is not None and "VMIS" in tubes.point_data else None
        if scalar_key:
            plotter.add_mesh(
                tubes,
                scalars=scalar_key,
                cmap="turbo",
                show_edges=True,
                edge_color="#0f172a",
            )
        else:
            plotter.add_mesh(
                tubes,
                color="#cbd5e1",
                show_edges=True,
                edge_color="#334155",
                smooth_shading=True,
            )
    plotter.add_axes()
    plotter.add_title(title, color="white")
    plotter.view_isometric()
    plotter.reset_camera()
    return plotter
