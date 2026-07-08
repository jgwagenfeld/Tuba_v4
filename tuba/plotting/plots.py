"""
tuba.plotting.plots — High-level plot functions.

Each function is called from the :class:`~tuba.solver.base.FEAResults`
convenience methods (e.g. ``results.plot_deformed()``).

All plots use a dark theme with scalar bars, title text, and optional
HTML export.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from tuba.model import TubaModel
    from tuba.solver.base import FEAResults

try:
    import pyvista as pv

    _HAS_PYVISTA = True
except ImportError:
    _HAS_PYVISTA = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BG_COLOR = "#1a1a2e"
_TEXT_COLOR = "white"


def _require_pyvista():
    if not _HAS_PYVISTA:
        raise ImportError(
            "PyVista is required for visualization. "
            "Install it with: pip install pyvista"
        )


def _get_pipe_radius(results: "FEAResults", model: Optional["TubaModel"] = None) -> float:
    """Determine the pipe outer radius from the model."""
    from tuba.plotting.pipeline import get_section_radius
    mdl = model or getattr(results, "_model", None)
    if mdl and mdl.sections:
        sec = next(iter(mdl.sections.values()))
        return get_section_radius(sec)
    raise ValueError("Pipe visualization requires a model with at least one defined section.")


def _get_mesh(
    results: "FEAResults",
    model: Optional["TubaModel"] = None,
) -> "pv.PolyData":
    """Build (or retrieve) the 3D mesh from results."""
    from tuba.plotting.pipeline import build_3d_mesh_from_model

    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        return build_3d_mesh_from_model(mdl, results)

    # If no model reference, attempt to load from result file
    if results.result_file is not None:
        from tuba.plotting.pipeline import load_rmed
        return load_rmed(str(results.result_file))

    raise RuntimeError(
        "Cannot build visualization mesh: no model reference or result file available. "
        "Pass model= kwarg explicitly."
    )


def _make_plotter(title: str = "Tuba v4") -> "pv.Plotter":
    """Create a consistently styled plotter."""
    p = pv.Plotter()
    p.set_background(_BG_COLOR)
    p.add_text(title, position="upper_left", font_size=12, color=_TEXT_COLOR)
    p.add_axes(color=_TEXT_COLOR)
    return p


def _get_element_local_frame(model: "TubaModel", elem: "Element") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the local coordinate frame (lx, ly, lz) matching Code_Aster logic."""
    p1 = model.nodes[elem.n1].coords
    p2 = model.nodes[elem.n2].coords
    v = p2 - p1
    L = np.linalg.norm(v)
    if L < 1e-9:
        lx = np.array([1.0, 0.0, 0.0])
    else:
        lx = v / L
        
    # Determine local frame depending on element type
    if elem.type in ("pipe_straight", "pipe_bend"):
        # Code_Aster uses GENE_TUYAU = (0, 0, 1) by default in our solver
        V = np.array([0.0, 0.0, 1.0])
        cross = np.cross(V, lx)
        norm_cross = np.linalg.norm(cross)
        if norm_cross > 1e-9:
            ly = cross / norm_cross
        else:
            # Fallback if tangent is along Z
            V_fallback = np.array([0.0, 1.0, 0.0])
            cross = np.cross(V_fallback, lx)
            ly = cross / np.linalg.norm(cross)
        lz = np.cross(lx, ly)
    else:
        # Default beam frame calculation (ANGL_VRIL = 0.0)
        Z = np.array([0.0, 0.0, 1.0])
        if np.abs(np.abs(lx[2]) - 1.0) < 1e-6:
            # Vertical beam
            ly = np.array([0.0, 1.0, 0.0])
        else:
            cross = np.cross(Z, lx)
            ly = cross / np.linalg.norm(cross)
        lz = np.cross(lx, ly)

    # Rotate by twist_angle if non-zero
    twist_deg = getattr(elem, "twist_angle", 0.0)
    if twist_deg != 0.0:
        theta = np.radians(twist_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        ly_new = ly * cos_t + lz * sin_t
        lz_new = lz * cos_t - ly * sin_t
        ly = ly_new
        lz = lz_new
        
    return lx, ly, lz


def add_local_axes_to_plotter(plotter: "pv.Plotter", model: "TubaModel", scale: float = 0.15):
    """Draw local coordinate system triads (X=red, Y=green, Z=blue) at the midpoint of each element."""
    for elem in model.elements:
        p1 = model.nodes[elem.n1].coords
        p2 = model.nodes[elem.n2].coords
        midpoint = (p1 + p2) / 2.0
        
        lx, ly, lz = _get_element_local_frame(model, elem)
        
        # Add small arrows representing the local axes
        arrow_x = pv.Arrow(start=midpoint, direction=lx, scale=scale, tip_radius=0.1, shaft_radius=0.04)
        arrow_y = pv.Arrow(start=midpoint, direction=ly, scale=scale, tip_radius=0.1, shaft_radius=0.04)
        arrow_z = pv.Arrow(start=midpoint, direction=lz, scale=scale, tip_radius=0.1, shaft_radius=0.04)
        
        plotter.add_mesh(arrow_x, color="red")
        plotter.add_mesh(arrow_y, color="green")
        plotter.add_mesh(arrow_z, color="blue")


def _get_node_frame(model: "TubaModel", node_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find the local coordinate frame (lx, ly, lz) at a node based on connected elements."""
    for elem in model.elements:
        if elem.n1 == node_id or elem.n2 == node_id:
            return _get_element_local_frame(model, elem)
    return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])


def _add_supports_to_plotter(plotter: "pv.Plotter", model: "TubaModel", scale: float = 0.15):
    """Draw realistic 3D support shapes at support nodes aligned with local axes."""

    def _transform_mesh(mesh: "pv.PolyData", R: np.ndarray, coords: np.ndarray) -> "pv.PolyData":
        transformed = mesh.copy(deep=True)
        transformed.points = (transformed.points @ R.T) + coords
        return transformed

    def _make_torus(ring_radius: float, cross_section_radius: float) -> "pv.PolyData":
        try:
            return pv.ParametricTorus(ringradius=ring_radius, crosssectionradius=cross_section_radius)
        except TypeError:
            return pv.ParametricTorus(ring_radius=ring_radius, cross_section_radius=cross_section_radius)

    for sup in model.supports:
        if sup.node not in model.nodes:
            continue
        coords = model.nodes[sup.node].coords
        existing_labels = plotter.legend_labels if hasattr(plotter, "legend_labels") else []
        
        # Determine equivalent pipe radius from scale
        r = scale / 1.5
        
        # Get local coordinate frame for alignment
        lx, ly, lz = _get_node_frame(model, sup.node)
        R = np.column_stack([lx, ly, lz])
        
        if sup.type == "anchor":
            # Square anchor flange block
            block = pv.Cube(center=(0.0, 0.0, 0.0), x_length=scale*0.6, y_length=scale*2.4, z_length=scale*2.4)
            block = _transform_mesh(block, R, coords)
            label = "Anchor" if "Anchor" not in existing_labels else None
            plotter.add_mesh(block, color="red", label=label, metallic=0.6, roughness=0.3)
            
        elif sup.type == "guide":
            # Pipe collar cylinder
            collar = pv.Cylinder(center=(0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0), radius=r*1.12, height=scale*0.6)
            
            # Left/Right guide bumper blocks
            t_bump = scale * 0.15
            h_bump = scale * 1.2
            w_bump = scale * 0.6
            
            left_bump = pv.Cube(center=(0.0, 0.0, r + t_bump/2.0), x_length=w_bump, y_length=h_bump, z_length=t_bump)
            right_bump = pv.Cube(center=(0.0, 0.0, -(r + t_bump/2.0)), x_length=w_bump, y_length=h_bump, z_length=t_bump)
            
            # Combine guide elements
            guide_mesh = collar.merge([left_bump, right_bump])
            guide_mesh = _transform_mesh(guide_mesh, R, coords)
            
            label = "Guide" if "Guide" not in existing_labels else None
            plotter.add_mesh(guide_mesh, color="green", label=label, metallic=0.7, roughness=0.4)
            
        elif sup.type == "rest":
            # Vertical support rib plate
            h_rib = scale * 0.8
            rib = pv.Cube(center=(0.0, -(r + h_rib/2.0), 0.0), x_length=scale*1.6, y_length=h_rib, z_length=scale*0.08)
            
            # Horizontal base sliding plate
            t_plate = scale * 0.06
            plate = pv.Cube(center=(0.0, -(r + h_rib + t_plate/2.0), 0.0), x_length=scale*1.6, y_length=t_plate, z_length=scale*1.4)
            
            rest_mesh = rib.merge(plate)
            rest_mesh = _transform_mesh(rest_mesh, R, coords)
            
            label = "Rest" if "Rest" not in existing_labels else None
            plotter.add_mesh(rest_mesh, color="blue", label=label, metallic=0.8, roughness=0.3)
            
        elif sup.type == "spring":
            # Spring hanger assembly
            h_rod = scale * 1.5
            h_can = scale * 1.0
            
            # Canister cylinder
            canister = pv.Cylinder(center=(0.0, r + h_rod + h_can/2.0, 0.0), direction=(0.0, 1.0, 0.0), radius=scale*0.35, height=h_can)
            # Connecting rod
            rod = pv.Cylinder(center=(0.0, r + h_rod/2.0, 0.0), direction=(0.0, 1.0, 0.0), radius=scale*0.06, height=h_rod)
            # Pipe clamp torus
            clamp = _make_torus(ring_radius=r*1.05, cross_section_radius=scale*0.05)
            # Rotate clamp to face axial direction lx (default torus normal is along Z)
            clamp.rotate_y(90, inplace=True)
            
            spring_mesh = canister.merge([rod, clamp])
            spring_mesh = _transform_mesh(spring_mesh, R, coords)
            
            label = "Spring" if "Spring" not in existing_labels else None
            plotter.add_mesh(spring_mesh, color="yellow", label=label, metallic=0.5, roughness=0.5)
            
        else:
            # Custom support fallback
            sphere = pv.Sphere(center=coords, radius=scale*0.3)
            label = "Custom Support" if "Custom Support" not in existing_labels else None
            plotter.add_mesh(sphere, color="magenta", label=label)

        # 2. Discrete Mass shape (Sphere of size 2 * outerRadius)
        if hasattr(sup, "mass") and sup.mass > 0.0:
            mass_shape = pv.Sphere(center=coords, radius=scale*0.8)
            label = "Discrete Mass" if "Discrete Mass" not in existing_labels else None
            plotter.add_mesh(mass_shape, color="orange", label=label)


# ---------------------------------------------------------------------------
# Public plot functions
# ---------------------------------------------------------------------------


def plot_deformed(
    results: "FEAResults",
    scale: float = 50.0,
    show_undeformed: bool = True,
    model: Optional["TubaModel"] = None,
    **kwargs,
):
    """Render the deformed pipe shape (replaces ParaVis Warp-By-Vector)."""
    _require_pyvista()

    mesh = _get_mesh(results, model)
    radius = _get_pipe_radius(results, model)

    p = _make_plotter("Deformed Shape")

    # Draw supports
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        _add_supports_to_plotter(p, mdl, radius * 1.5)

    # Undeformed (ghosted wireframe)
    if show_undeformed:
        tubes_orig = mesh
        p.add_mesh(
            tubes_orig,
            color="#444466",
            style="wireframe",
            line_width=1,
            opacity=0.3,
            label="Undeformed",
        )

    # Deformed
    if "DEPL" in mesh.point_data:
        warped = mesh.warp_by_vector("DEPL", factor=scale)
    else:
        warped = mesh

    tubes_def = warped
    p.add_mesh(
        tubes_def,
        scalars="DEPL_magnitude" if "DEPL_magnitude" in tubes_def.point_data else None,
        cmap="plasma",
        scalar_bar_args={"title": "Displacement [m]", "color": _TEXT_COLOR},
        label="Deformed",
    )

    p.add_legend(bcolor=_BG_COLOR)
    return p.show(**kwargs)


def plot_stress(
    results: "FEAResults",
    cmap: str = "jet",
    model: Optional["TubaModel"] = None,
    **kwargs,
):
    """Color-map Von Mises stress on the pipe surface (replaces ParaVis SIEQ_ELNO)."""
    _require_pyvista()

    mesh = _get_mesh(results, model)
    radius = _get_pipe_radius(results, model)

    scalar_key = "VMIS"  # the only stress field the mesh builder maps
    tubes = mesh

    p = _make_plotter("Stress Distribution")

    # Draw supports
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        _add_supports_to_plotter(p, mdl, radius * 1.5)

    p.add_mesh(
        tubes,
        scalars=scalar_key if scalar_key in tubes.point_data else None,
        cmap=cmap,
        scalar_bar_args={"title": "Von Mises Stress [Pa]", "color": _TEXT_COLOR},
    )
    return p.show(**kwargs)


def plot_displacement_vectors(
    results: "FEAResults",
    scale: float = 50.0,
    model: Optional["TubaModel"] = None,
    **kwargs,
):
    """Arrow glyphs showing displacement at each node."""
    _require_pyvista()

    mesh = _get_mesh(results, model)
    radius = _get_pipe_radius(results, model)

    p = _make_plotter("Displacement Vectors")

    # Draw supports
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        _add_supports_to_plotter(p, mdl, radius * 1.5)

    tubes = mesh
    p.add_mesh(tubes, color="#334455", opacity=0.5)

    if "DEPL" in mesh.point_data:
        arrows = mesh.glyph(
            orient="DEPL",
            scale="DEPL_magnitude",
            factor=scale,
        )
        p.add_mesh(arrows, color="cyan", label="Displacement")

    p.add_legend(bcolor=_BG_COLOR)
    return p.show(**kwargs)


def _reaction_vector_points(results: "FEAResults", model: Optional["TubaModel"]):
    if model is None:
        return np.empty((0, 3)), np.empty((0, 3)), np.empty((0,))

    points = []
    vectors = []
    magnitudes = []
    for node_id, result in results.node_results.items():
        if result.reaction_force is None or node_id not in model.nodes:
            continue
        vector = np.asarray(result.reaction_force[:3], dtype=float)
        magnitude = float(np.linalg.norm(vector))
        if magnitude <= 1e-6:
            continue
        points.append(model.nodes[node_id].coords)
        vectors.append(vector)
        magnitudes.append(magnitude)
    return np.asarray(points), np.asarray(vectors), np.asarray(magnitudes)


def _reaction_glyph_factor(scale, bounds, magnitudes: np.ndarray) -> float:
    if scale != "auto":
        return float(scale)
    max_magnitude = float(np.max(magnitudes)) if len(magnitudes) else 0.0
    if max_magnitude <= 0.0:
        return 0.0
    bounds_arr = np.asarray(bounds, dtype=float)
    diagonal = float(np.linalg.norm(bounds_arr[3:6] - bounds_arr[0:3])) if bounds_arr.shape == (6,) else 1.0
    target_length = (diagonal if diagonal > 1e-12 else 1.0) * 0.12
    return target_length / max_magnitude


def plot_reactions(
    results: "FEAResults",
    scale: float | str = "auto",
    model: Optional["TubaModel"] = None,
    show_geometry: bool = True,
    show_supports: bool = True,
    geometry_opacity: float = 0.25,
    **kwargs,
):
    """Arrow glyphs at supports showing reaction forces."""
    _require_pyvista()

    mesh = _get_mesh(results, model)
    radius = _get_pipe_radius(results, model)

    p = _make_plotter("Reaction Forces")

    mdl = model or getattr(results, "_model", None)
    if show_supports and mdl is not None:
        _add_supports_to_plotter(p, mdl, radius * 1.5)

    tubes = mesh
    if show_geometry:
        p.add_mesh(tubes, color="#334455", opacity=geometry_opacity)

    points, vectors, magnitudes = _reaction_vector_points(results, mdl)
    if len(points):
        reaction_points = pv.PolyData(points)
        reaction_points.point_data["FORC_NODA"] = vectors
        reaction_points.point_data["FORC_magnitude"] = magnitudes
        arrows = reaction_points.glyph(
            orient="FORC_NODA",
            scale="FORC_magnitude",
            factor=_reaction_glyph_factor(scale, mesh.bounds, magnitudes),
        )
        p.add_mesh(arrows, color="red", label="Reactions")
    elif "FORC_NODA" in mesh.point_data:
        magnitudes = mesh.point_data["FORC_magnitude"]
        mask = magnitudes > 1e-6
        if mask.any():
            support_pts = mesh.extract_points(mask)
            arrows = support_pts.glyph(
                orient="FORC_NODA",
                scale="FORC_magnitude",
                factor=_reaction_glyph_factor(scale, mesh.bounds, magnitudes[mask]),
            )
            p.add_mesh(arrows, color="red", label="Reactions")

    p.add_legend(bcolor=_BG_COLOR)
    return p.show(**kwargs)


def plot_temperature(
    results: "FEAResults",
    cmap: str = "coolwarm",
    model: Optional["TubaModel"] = None,
    **kwargs,
):
    """Temperature scalar color map."""
    _require_pyvista()

    mesh = _get_mesh(results, model)
    radius = _get_pipe_radius(results, model)

    tubes = mesh

    p = _make_plotter("Temperature Distribution")

    # Draw supports
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        _add_supports_to_plotter(p, mdl, radius * 1.5)

    scalar_key = "TEMP" if "TEMP" in tubes.point_data else None
    p.add_mesh(
        tubes,
        scalars=scalar_key,
        cmap=cmap,
        scalar_bar_args={"title": "Temperature [°C]", "color": _TEXT_COLOR},
    )
    return p.show(**kwargs)


def plot_deformed_stress(
    results: "FEAResults",
    deform_scale: float = 50.0,
    cmap: str = "turbo",
    export_html: Optional[str] = None,
    model: Optional["TubaModel"] = None,
    **kwargs,
):
    """Combined deformed shape colored by stress — the primary view.

    This is the "money shot" visualization that replaces the combined
    ParaVis warp + SIEQ_ELNO coloring from Tuba v2.
    """
    _require_pyvista()
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        from tuba.plotting.scenes import build_model_scene

        p = build_model_scene(
            mdl,
            results,
            off_screen=bool(export_html),
            title="Deformed Stress",
            deform_scale=deform_scale,
        )
        if export_html:
            p.export_html(export_html)
            p.close()
            return
        return p.show(**kwargs)


    mesh = _get_mesh(results, model)

    # Warp by displacement
    if "DEPL" in mesh.point_data:
        warped = mesh.warp_by_vector("DEPL", factor=deform_scale)
    else:
        warped = mesh

    tubes = warped

    scalar_key = "VMIS" if "VMIS" in tubes.point_data else None

    p = _make_plotter("Deformed Shape — Stress Distribution")

    p.add_mesh(
        tubes,
        scalars=scalar_key,
        cmap=cmap,
        scalar_bar_args={"title": "Von Mises [Pa]", "color": _TEXT_COLOR},
    )

    # Optionally show undeformed ghost
    if "DEPL" in mesh.point_data:
        tubes_ghost = mesh
        p.add_mesh(tubes_ghost, color="#333344", style="wireframe", opacity=0.15)

    if export_html:
        p.export_html(export_html)

    return p.show(**kwargs)
