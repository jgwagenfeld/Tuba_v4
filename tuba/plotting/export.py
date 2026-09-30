"""
tuba.plotting.export — Export utilities for Tuba v4 results.

Supports:
  - Standalone HTML (vtk.js) for browser viewing
  - PLY with vertex colors for Blender import
  - glTF for universal 3-D viewing
  - Blender Python script generation
"""

from __future__ import annotations

from pathlib import Path
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


def _require_pyvista():
    if not _HAS_PYVISTA:
        raise ImportError("PyVista is required for export: pip install 'tuba[viz]'")


# ---------------------------------------------------------------------------
# HTML export (vtk.js)
# ---------------------------------------------------------------------------


def export_html(results_or_plotter, path: str, **kwargs):
    """Export an interactive 3-D scene to a standalone HTML file.

    Accepts either a :class:`pyvista.Plotter` (exports the current scene)
    or :class:`~tuba.solver.base.FEAResults` (builds the default
    deformed-stress view and exports it).
    """
    _require_pyvista()

    if isinstance(results_or_plotter, pv.Plotter):
        results_or_plotter.export_html(path)
        return

    # Assume FEAResults — build the default view offscreen
    from tuba.plotting.pipeline import build_3d_mesh_from_model, _require_result_field

    model = kwargs.get("model") or getattr(results_or_plotter, "_model", None)
    results = results_or_plotter

    if model is None:
        raise ValueError("Pass model= kwarg or attach _model to results")

    mesh = build_3d_mesh_from_model(model, results)

    _require_result_field(mesh, "VMIS", complete=True)
    _require_result_field(mesh, "DEPL", complete=True)
    warped = mesh.warp_by_vector("DEPL", factor=50.0)

    tubes = warped

    p = pv.Plotter(off_screen=True)
    p.set_background("#1a1a2e")
    p.add_mesh(
        tubes,
        scalars="VMIS" if "VMIS" in tubes.point_data else None,
        cmap="turbo",
    )
    p.export_html(path)
    p.close()


# ---------------------------------------------------------------------------
# PLY export (vertex colors for Blender)
# ---------------------------------------------------------------------------


def export_ply(
    results: "FEAResults",
    path: str,
    model: Optional["TubaModel"] = None,
    cmap: str = "turbo",
):
    """Export inflated tubes with vertex-color stress to PLY for Blender.

    The PLY file contains per-vertex RGB colours derived from the
    Von Mises stress (``VMIS``), making it directly importable into Blender
    with colours visible via the Vertex Color attribute.
    """
    _require_pyvista()
    from tuba.plotting.pipeline import build_3d_mesh_from_model, _require_result_field

    mdl = model or getattr(results, "_model", None)
    if mdl is None:
        raise ValueError("Model required for PLY export — pass model= kwarg")

    mesh = build_3d_mesh_from_model(mdl, results)
    tubes = mesh

    values = _require_result_field(tubes, "VMIS", complete=True)
    import matplotlib
    import matplotlib.colors as mcolors

    if values.max() > values.min():
        norm = mcolors.Normalize(vmin=values.min(), vmax=values.max())
    else:
        norm = mcolors.Normalize(vmin=0, vmax=1)
    colormap = matplotlib.colormaps.get_cmap(cmap)
    colors = (colormap(norm(values))[:, :3] * 255).astype(np.uint8)
    tubes.point_data["RGB"] = colors

    tubes.save(str(path), texture="RGB")


# ---------------------------------------------------------------------------
# glTF export
# ---------------------------------------------------------------------------


def export_gltf(
    results: "FEAResults",
    path: str,
    model: Optional["TubaModel"] = None,
):
    """Export tubes to glTF format for universal 3-D viewing."""
    _require_pyvista()
    from tuba.plotting.pipeline import build_3d_mesh_from_model, _require_result_field

    mdl = model or getattr(results, "_model", None)
    if mdl is None:
        raise ValueError("Model required for glTF export — pass model= kwarg")

    mesh = build_3d_mesh_from_model(mdl, results)
    tubes = mesh

    _require_result_field(tubes, "VMIS", complete=True)
    p = pv.Plotter(off_screen=True)
    p.add_mesh(
        tubes,
        scalars="VMIS" if "VMIS" in tubes.point_data else None,
        cmap="turbo",
    )
    p.export_gltf(str(path))
    p.close()


# ---------------------------------------------------------------------------
# Blender Python script export
# ---------------------------------------------------------------------------


def export_blender_script(
    results: "FEAResults",
    path: str,
    model: Optional["TubaModel"] = None,
    stress_cmap: str = "turbo",
):
    """Generate a Blender Python script that recreates the pipe geometry
    with Von Mises stress mapped as vertex colours.

    The generated script can be executed inside Blender via
    ``File → Run Script`` or ``blender --python script.py``.
    """
    mdl = model or getattr(results, "_model", None)
    if mdl is None:
        raise ValueError("Model required for Blender script export")

    # Collect node coords and element connectivity
    node_ids = list(mdl.nodes.keys())
    node_idx = {nid: i for i, nid in enumerate(node_ids)}
    coords = [mdl.nodes[nid].coords.tolist() for nid in node_ids]

    edges = []
    for elem in mdl.elements:
        edges.append([node_idx[elem.n1], node_idx[elem.n2]])

    from tuba.plotting.pipeline import _nodal_von_mises

    stress_by_node = _nodal_von_mises(mdl, results)
    unavailable = [node_id for node_id in node_ids if not np.isfinite(stress_by_node[node_id])]
    if unavailable or not node_ids:
        raise ValueError(
            "Cannot export Blender stress: missing or non-finite endpoint stress at model nodes: "
            + ", ".join(unavailable)
        )
    vmis = [stress_by_node[node_id] for node_id in node_ids]

    # Per-node outer radius, straight from each element's own section — a node
    # shared by two sections takes the larger radius (no artificial pinch).
    from tuba.geometry.profiles import collision_radius_for_section

    radii = [None] * len(node_ids)
    for elem in mdl.elements:
        sec = mdl.sections.get(elem.section)
        if sec is None:
            raise ValueError(f"Cannot export Blender pipe radius: section {elem.section!r} is not defined.")
        r = collision_radius_for_section(sec)
        for nid in (elem.n1, elem.n2):
            i = node_idx[nid]
            radii[i] = r if radii[i] is None else max(radii[i], r)
    missing_radius_nodes = [node_id for node_id, radius in zip(node_ids, radii) if radius is None]
    if missing_radius_nodes:
        raise ValueError(
            "Cannot export Blender pipe radius for nodes not connected to elements: "
            + ", ".join(missing_radius_nodes)
        )

    script = f'''\
"""Tuba v4 — Auto-generated Blender import script.

Run inside Blender: File → Run Script, or:
    blender --python {Path(path).name}
"""

import bpy
import bmesh
import math
from mathutils import Vector

# ---- Pipe Data ----
coords = {coords}
edges = {edges}
vmis = {vmis}
pipe_radii = {radii}

# ---- Normalise stress for colour mapping ----
vmis_min = min(vmis) if vmis else 0
vmis_max = max(vmis) if vmis else 1
vmis_range = vmis_max - vmis_min if vmis_max > vmis_min else 1.0

def stress_to_rgb(value):
    """Turbo-like colour ramp: blue → cyan → green → yellow → red."""
    t = (value - vmis_min) / vmis_range
    t = max(0.0, min(1.0, t))
    # Simplified turbo approximation
    r = max(0.0, min(1.0, 1.5 - abs(t - 0.75) * 4.0))
    g = max(0.0, min(1.0, 1.5 - abs(t - 0.5) * 4.0))
    b = max(0.0, min(1.0, 1.5 - abs(t - 0.25) * 4.0))
    return (r, g, b, 1.0)

# ---- Create centreline mesh ----
mesh = bpy.data.meshes.new("TubaPipeCentreline")
obj = bpy.data.objects.new("TubaPipe", mesh)
bpy.context.collection.objects.link(obj)

bm = bmesh.new()
bm_verts = [bm.verts.new(Vector(c)) for c in coords]
bm.verts.ensure_lookup_table()
for e in edges:
    bm.edges.new((bm_verts[e[0]], bm_verts[e[1]]))
bm.to_mesh(mesh)
bm.free()

# ---- Add vertex colour layer ----
if not mesh.vertex_colors:
    mesh.vertex_colors.new(name="StressColors")

color_layer = mesh.vertex_colors["StressColors"]
for poly in mesh.polygons:
    for loop_idx in poly.loop_indices:
        vi = mesh.loops[loop_idx].vertex_index
        color_layer.data[loop_idx].color = stress_to_rgb(vmis[vi])

# ---- Apply Skin modifier to inflate to tubes ----
skin = obj.modifiers.new(name="PipeSkin", type='SKIN')
# Set each vertex's radius from its node's section (per-node, not uniform)
skin_data = mesh.skin_vertices[0].data
for i in range(len(skin_data)):
    skin_data[i].radius = (pipe_radii[i], pipe_radii[i])

# Subdivision for smoothness
sub = obj.modifiers.new(name="Subdivision", type='SUBSURF')
sub.levels = 2

# ---- Create material with vertex colour ----
mat = bpy.data.materials.new("StressMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Clear defaults
for n in nodes:
    nodes.remove(n)

# Build node tree: Vertex Color → Principled BSDF → Output
output = nodes.new("ShaderNodeOutputMaterial")
output.location = (400, 0)
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (0, 0)
vcol = nodes.new("ShaderNodeVertexColor")
vcol.location = (-300, 0)
vcol.layer_name = "StressColors"

links.new(vcol.outputs["Color"], bsdf.inputs["Base Color"])
links.new(vcol.outputs["Color"], bsdf.inputs["Emission Color"])
bsdf.inputs["Emission Strength"].default_value = 0.3
links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

obj.data.materials.append(mat)

print("Tuba v4: Pipe geometry imported with stress colours.")
'''

    Path(path).write_text(script, encoding="utf-8")
