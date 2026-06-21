"""Tuba v4 — Auto-generated Blender import script.

Run inside Blender: File → Run Script, or:
    blender --python blender_import_tuba.py
"""

import bpy
import bmesh
import math
from mathutils import Vector

# ---- Pipe Data ----
coords = [[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [4.1524, 0.15239999999999998, 0.0], [4.1524, 2.1524, 0.0], [4.0, 2.3048, 0.0], [0.0, 2.304800000000002, 0.0]]
edges = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]]
vmis = [35000000.0, 60000000.0, 60000000.0, 60000000.0, 60000000.0, 35000000.0]
pipe_radius = 0.05715

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
# Set radius for all vertices
for v in mesh.skin_vertices[0].data:
    v.radius = (pipe_radius, pipe_radius)

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
