"""
tuba.visualizer.pipeline — Core visualization pipeline.

Converts Tuba model data and FEA results into PyVista meshes
for rendering. Handles:
  - Loading .rmed files via meshio
  - Building line meshes directly from TubaModel geometry
  - Inflating 1D lines into 3D tubes
  - Mapping scalar fields to tube surfaces
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

try:
    import meshio

    _HAS_MESHIO = True
except ImportError:
    _HAS_MESHIO = False


def _require_pyvista():
    if not _HAS_PYVISTA:
        raise ImportError(
            "PyVista is required for visualization. "
            "Install it with: pip install pyvista"
        )


def get_section_radius(sec) -> float:
    """Calculate an equivalent radius for a section profile [m]."""
    from tuba.geometry.profiles import collision_radius_for_section

    try:
        return collision_radius_for_section(sec)
    except ValueError:
        return 0.05


# ---------------------------------------------------------------------------
# Loading .rmed results
# ---------------------------------------------------------------------------


def load_rmed(path: str) -> "pv.UnstructuredGrid":
    """Read a Code_Aster ``.rmed`` result file and return a PyVista mesh.

    Uses *meshio* to parse the MED format, then converts to a PyVista
    :class:`~pyvista.UnstructuredGrid`.  All point and cell data arrays
    present in the file are preserved.
    """
    _require_pyvista()
    if not _HAS_MESHIO:
        raise ImportError("meshio is required to read .rmed files: pip install meshio")

    mesh_io = meshio.read(str(path))

    points = mesh_io.points
    if points.shape[1] == 2:
        points = np.column_stack([points, np.zeros(len(points))])

    cells, cell_types = [], []
    for cell_block in mesh_io.cells:
        ct = cell_block.type
        data = cell_block.data
        if ct == "line":
            vtk_type = 3  # VTK_LINE
        elif ct == "triangle":
            vtk_type = 5
        elif ct == "quad":
            vtk_type = 9
        else:
            continue  # skip unsupported
        for conn in data:
            cells.append(np.concatenate([[len(conn)], conn]))
            cell_types.append(vtk_type)

    if not cells:
        # Fallback: create a point cloud
        return pv.PolyData(points)

    cells_arr = np.concatenate(cells)
    grid = pv.UnstructuredGrid(cells_arr, np.array(cell_types), points)

    # Transfer point data
    for name, arr in mesh_io.point_data.items():
        grid.point_data[name] = arr

    # Transfer cell data
    for name, blocks in mesh_io.cell_data.items():
        combined = np.concatenate(blocks) if isinstance(blocks, list) else blocks
        if len(combined) == grid.n_cells:
            grid.cell_data[name] = combined

    return grid


# ---------------------------------------------------------------------------
# Build mesh from TubaModel + FEAResults
# ---------------------------------------------------------------------------


def _get_bend_points(model: "TubaModel", elem: "Element", n_segments: int = 16) -> np.ndarray:
    """Calculate intermediate coordinates along the 3D circular bend arc."""
    p1 = model.nodes[elem.n1].coords
    p2 = model.nodes[elem.n2].coords
    radius = elem.bend_radius or 0.15
    angle_deg = elem.bend_angle or 90.0

    d_in = None
    for e in model.elements:
        if e.id == elem.id:
            continue
        if e.n2 == elem.n1:
            v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
            if np.linalg.norm(v) > 1e-9:
                d_in = v / np.linalg.norm(v)
                break
        elif e.n1 == elem.n1:
            v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
            if np.linalg.norm(v) > 1e-9:
                d_in = v / np.linalg.norm(v)
                break

    d_out = None
    for e in model.elements:
        if e.id == elem.id:
            continue
        if e.n1 == elem.n2:
            v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
            if np.linalg.norm(v) > 1e-9:
                d_out = v / np.linalg.norm(v)
                break
        elif e.n2 == elem.n2:
            v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
            if np.linalg.norm(v) > 1e-9:
                d_out = v / np.linalg.norm(v)
                break

    if d_in is None and d_out is not None:
        d_in = d_out.copy()
    elif d_out is None and d_in is not None:
        d_out = d_in.copy()
    elif d_in is None and d_out is None:
        v = p2 - p1
        d_in = v / np.linalg.norm(v)
        d_out = d_in.copy()

    theta = np.radians(angle_deg)
    T = radius * np.tan(theta / 2.0)
    V = p1 + d_in * T

    v_bisect = d_out - d_in
    norm_bisect = np.linalg.norm(v_bisect)
    if norm_bisect > 1e-9:
        v_bisect_u = v_bisect / norm_bisect
    else:
        v_bisect_u = np.array([-d_in[1], d_in[0], 0.0])
        if np.linalg.norm(v_bisect_u) < 1e-9:
            v_bisect_u = np.array([0.0, -d_in[2], d_in[1]])
        v_bisect_u /= np.linalg.norm(v_bisect_u)

    L = radius / np.cos(theta / 2.0)
    C = V + v_bisect_u * L

    r1 = p1 - C
    r2 = p2 - C

    axis = np.cross(r1, r2)
    norm_axis = np.linalg.norm(axis)
    if norm_axis > 1e-9:
        axis /= norm_axis
    else:
        axis = np.array([0.0, 0.0, 1.0])

    cross_u = np.cross(axis, r1)
    arc_points = []
    for i in range(n_segments + 1):
        phi = theta * (i / n_segments)
        pt = C + r1 * np.cos(phi) + cross_u * np.sin(phi)
        arc_points.append(pt)
    return np.array(arc_points)


def build_mesh_from_model(
    model: "TubaModel",
    results: Optional["FEAResults"] = None,
) -> "pv.PolyData":
    """Construct a PyVista line mesh from a :class:`TubaModel` with curved bends."""
    _require_pyvista()

    # Pre-populate points list with basic nodes
    node_ids = list(model.nodes.keys())
    points_list = [model.nodes[nid].coords for nid in node_ids]
    
    # Store indices for basic nodes
    node_idx = {nid: i for i, nid in enumerate(node_ids)}
    
    # Results data lists
    disp_list = []
    vmis_list = []
    forc_list = []
    
    if results is not None:
        for nid in node_ids:
            nr = results.node_results.get(nid)
            disp_list.append(nr.displacement[:3] if nr is not None else np.zeros(3))
            
            # Average Von Mises for this node
            v_val = 0.0
            v_cnt = 0
            for elem in model.elements:
                er = results.element_results.get(elem.id)
                if er is not None:
                    if elem.n1 == nid:
                        v_val += er.von_mises_n1
                        v_cnt += 1
                    elif elem.n2 == nid:
                        v_val += er.von_mises_n2
                        v_cnt += 1
            vmis_list.append(v_val / max(v_cnt, 1))
            
            forc_list.append(nr.reaction_force[:3] if (nr is not None and nr.reaction_force is not None) else np.zeros(3))

    all_edges = []
    
    for elem in model.elements:
        if elem.type == "pipe_bend" and elem.bend_radius:
            # Generate curved points
            n_segs = 16
            arc_pts = _get_bend_points(model, elem, n_segments=n_segs)
            
            pts_idxs = [node_idx[elem.n1]]
            for i in range(1, n_segs):
                pts_idxs.append(len(points_list))
                points_list.append(arc_pts[i])
                
                # Interpolate results for intermediate points
                if results is not None:
                    t = i / n_segs
                    nr1 = results.node_results.get(elem.n1)
                    nr2 = results.node_results.get(elem.n2)
                    d1 = nr1.displacement[:3] if nr1 is not None else np.zeros(3)
                    d2 = nr2.displacement[:3] if nr2 is not None else np.zeros(3)
                    disp_list.append(d1 + t * (d2 - d1))
                    
                    er = results.element_results.get(elem.id)
                    if er is not None:
                        vmis_list.append(er.von_mises_n1 + t * (er.von_mises_n2 - er.von_mises_n1))
                    else:
                        vmis_list.append(0.0)
                        
                    forc_list.append(np.zeros(3))
                    
            pts_idxs.append(node_idx[elem.n2])
            
            for idx in range(n_segs):
                all_edges.append((pts_idxs[idx], pts_idxs[idx+1]))
        else:
            # Straight elements
            i1 = node_idx[elem.n1]
            i2 = node_idx[elem.n2]
            all_edges.append((i1, i2))

    # Group edges into continuous polylines
    n_pts = len(points_list)
    adj = {i: set() for i in range(n_pts)}
    for u, v in all_edges:
        adj[u].add(v)
        adj[v].add(u)

    degrees = {i: len(neighbors) for i, neighbors in adj.items()}
    visited_edges = set()
    polylines = []

    # 1. Start from endpoints or junctions (degree != 2)
    start_nodes = [i for i, deg in degrees.items() if deg != 2 and deg > 0]
    for u in start_nodes:
        for v in list(adj[u]):
            edge = tuple(sorted((u, v)))
            if edge not in visited_edges:
                poly = [u, v]
                visited_edges.add(edge)
                curr = v
                prev = u
                while degrees[curr] == 2:
                    neighbors = list(adj[curr] - {prev})
                    if not neighbors:
                        break
                    next_node = neighbors[0]
                    next_edge = tuple(sorted((curr, next_node)))
                    if next_edge in visited_edges:
                        break
                    poly.append(next_node)
                    visited_edges.add(next_edge)
                    prev = curr
                    curr = next_node
                polylines.append(poly)

    # 2. Start from any remaining unvisited edges (closed loops)
    for u in range(n_pts):
        for v in list(adj[u]):
            edge = tuple(sorted((u, v)))
            if edge not in visited_edges:
                poly = [u, v]
                visited_edges.add(edge)
                curr = v
                prev = u
                while True:
                    neighbors = list(adj[curr] - {prev})
                    if not neighbors:
                        break
                    next_node = neighbors[0]
                    next_edge = tuple(sorted((curr, next_node)))
                    if next_edge in visited_edges:
                        break
                    poly.append(next_node)
                    visited_edges.add(next_edge)
                    prev = curr
                    curr = next_node
                polylines.append(poly)

    # Build the PyVista lines cell array
    lines = []
    for poly in polylines:
        lines.append(len(poly))
        lines.extend(poly)

    points_arr = np.array(points_list)
    mesh = pv.PolyData(points_arr, lines=np.array(lines))

    if results is not None:
        mesh.point_data["DEPL"] = np.array(disp_list)
        mesh.point_data["DEPL_magnitude"] = np.linalg.norm(mesh.point_data["DEPL"], axis=1)
        mesh.point_data["VMIS"] = np.array(vmis_list)
        mesh.point_data["FORC_NODA"] = np.array(forc_list)
        mesh.point_data["FORC_magnitude"] = np.linalg.norm(mesh.point_data["FORC_NODA"], axis=1)

    return mesh


# ---------------------------------------------------------------------------
# Tube inflation
# ---------------------------------------------------------------------------


def inflate_tubes(
    mesh: "pv.PolyData",
    radius: float = 0.05,
    n_sides: int = 16,
) -> "pv.PolyData":
    """Convert a 1-D line mesh into 3-D tubes.

    Parameters
    ----------
    mesh : pv.PolyData
        Line mesh (e.g. from :func:`build_mesh_from_model`).
    radius : float
        Outer radius of the pipe [m].
    n_sides : int
        Number of facets around the circumference.

    Returns
    -------
    pv.PolyData
        3-D tube surface with all point-data arrays interpolated.
    """
    _require_pyvista()
    if mesh.n_faces > 0:
        return mesh
    return mesh.tube(radius=radius, n_sides=n_sides)


# ---------------------------------------------------------------------------
# Scalar mapping helper
# ---------------------------------------------------------------------------


def map_stress_to_tubes(
    line_mesh: "pv.PolyData",
    tube_mesh: "pv.PolyData",
    field_name: str = "VMIS",
) -> "pv.PolyData":
    """Interpolate a scalar field from the line mesh onto the tube surface.

    Uses nearest-point interpolation so that each tube-surface vertex
    picks up the value from its closest centreline node.
    """
    _require_pyvista()
    if field_name in line_mesh.point_data:
        tube_mesh = tube_mesh.sample(line_mesh)
    return tube_mesh


# ---------------------------------------------------------------------------
# True 3D Cross-Sectional Geometry Extrusion
# ---------------------------------------------------------------------------


def get_ibeam_dimensions(sec) -> tuple[float, float, float, float]:
    """Retrieve H, B, Tw, Tf (in meters) for an IBeamSection."""
    h = sec.properties.get("H")
    b = sec.properties.get("B")
    tw = sec.properties.get("Tw")
    tf = sec.properties.get("Tf")
    if all(x is not None for x in (h, b, tw, tf)):
        return float(h), float(b), float(tw), float(tf)
    
    profile_name = getattr(sec, "profile_name", "")
    if profile_name:
        from tuba.sections import SectionCatalog

        try:
            profile = SectionCatalog.default().get_ibeam_profile(profile_name)
            return (
                profile.dimensions["H"],
                profile.dimensions["B"],
                profile.dimensions["Tw"],
                profile.dimensions["Tf"],
            )
        except ValueError:
            pass
    # If all else fails, estimate from EY and EZ
    ey = sec.properties.get("EY", 0.04)
    ez = sec.properties.get("EZ", 0.02)
    h = ey * 2.0
    b = ez * 2.0
    tw = h * 0.05
    tf = h * 0.1
    return h, b, tw, tf


def _get_profile_2d_polygon(sec, n_sides: int = 16) -> np.ndarray:
    """Return a 2D closed polygon (y, z) representing the section profile in meters."""
    from tuba.model import PipeSection, BarSection, CableSection, RectangularSection, IBeamSection
    
    if isinstance(sec, (PipeSection, BarSection)):
        r = float(sec.OD / 2.0)
        angles = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
        y = r * np.cos(angles)
        z = r * np.sin(angles)
        return np.column_stack([y, z])
        
    elif isinstance(sec, CableSection):
        r = float(sec.radius)
        angles = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
        y = r * np.cos(angles)
        z = r * np.sin(angles)
        return np.column_stack([y, z])
        
    elif isinstance(sec, RectangularSection):
        hy = float(sec.height_y)
        hz = float(sec.height_z)
        return np.array([
            [-hy/2.0, -hz/2.0],
            [ hy/2.0, -hz/2.0],
            [ hy/2.0,  hz/2.0],
            [-hy/2.0,  hz/2.0],
        ])
        
    elif isinstance(sec, IBeamSection) or (hasattr(sec, "properties") and "EY" in sec.properties):
        h, b, tw, tf = get_ibeam_dimensions(sec)
        return np.array([
            [-h/2.0, -b/2.0],
            [-h/2.0,  b/2.0],
            [-h/2.0 + tf,  b/2.0],
            [-h/2.0 + tf,  tw/2.0],
            [ h/2.0 - tf,  tw/2.0],
            [ h/2.0 - tf,  b/2.0],
            [ h/2.0,  b/2.0],
            [ h/2.0, -b/2.0],
            [ h/2.0 - tf, -b/2.0],
            [ h/2.0 - tf, -tw/2.0],
            [-h/2.0 + tf, -tw/2.0],
            [-h/2.0 + tf, -b/2.0],
        ])
    else:
        # Default fallback
        r = 0.05
        angles = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
        y = r * np.cos(angles)
        z = r * np.sin(angles)
        return np.column_stack([y, z])


def _get_element_3d_mesh(
    model: "TubaModel",
    elem: "Element",
    results: Optional["FEAResults"] = None,
) -> "pv.PolyData":
    """Construct a 3-D extruded solid mesh for a single element with result mapping."""
    _require_pyvista()
    
    # 1. Determine centerline path points
    if elem.type == "pipe_bend" and elem.bend_radius:
        path = _get_bend_points(model, elem, n_segments=16)
    else:
        p1 = model.nodes[elem.n1].coords
        p2 = model.nodes[elem.n2].coords
        path = np.array([p1, p2])
        
    N = len(path)
    if N < 2:
        return pv.PolyData()
        
    # 2. Get 2D profile polygon
    sec = model.sections[elem.section]
    poly2d = _get_profile_2d_polygon(sec)
    M = len(poly2d)
    
    # 3. Generate parallel transport frames (lx, ly, lz) along the path
    # Tangent at start
    t0 = path[1] - path[0]
    t0_norm = np.linalg.norm(t0)
    if t0_norm > 1e-9:
        t0 = t0 / t0_norm
    else:
        t0 = np.array([1.0, 0.0, 0.0])
        
    lx = t0
    # Base local coordinate frame calculation matching Code_Aster
    if elem.type in ("pipe_straight", "pipe_bend"):
        V = np.array([0.0, 0.0, 1.0])
        cross = np.cross(V, lx)
        norm_cross = np.linalg.norm(cross)
        if norm_cross > 1e-9:
            ly = cross / norm_cross
        else:
            V_fallback = np.array([0.0, 1.0, 0.0])
            cross = np.cross(V_fallback, lx)
            ly = cross / np.linalg.norm(cross)
        lz = np.cross(lx, ly)
    else:
        Z = np.array([0.0, 0.0, 1.0])
        if np.abs(np.abs(lx[2]) - 1.0) < 1e-6:
            ly = np.array([0.0, 1.0, 0.0])
        else:
            cross = np.cross(Z, lx)
            ly = cross / np.linalg.norm(cross)
        lz = np.cross(lx, ly)
        
    # Apply twist angle
    twist_deg = getattr(elem, "twist_angle", 0.0)
    if twist_deg != 0.0:
        theta = np.radians(twist_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        ly_new = ly * cos_t + lz * sin_t
        lz_new = lz * cos_t - ly * sin_t
        ly, lz = ly_new, lz_new
        
    frames = [(lx, ly, lz)]
    
    # Propagate frames using parallel transport
    for i in range(1, N):
        if i < N - 1:
            ti = path[i+1] - path[i-1]
        else:
            ti = path[i] - path[i-1]
        norm_ti = np.linalg.norm(ti)
        if norm_ti > 1e-9:
            ti /= norm_ti
        else:
            ti = frames[-1][0]
            
        lx_prev, ly_prev, lz_prev = frames[-1]
        rot_axis = np.cross(lx_prev, ti)
        rot_norm = np.linalg.norm(rot_axis)
        if rot_norm > 1e-9:
            rot_axis /= rot_norm
            dot = np.clip(np.dot(lx_prev, ti), -1.0, 1.0)
            theta = np.arccos(dot)
            cos_t = np.cos(theta)
            sin_t = np.sin(theta)
            
            # Rodrigues' rotation
            ly_curr = ly_prev * cos_t + np.cross(rot_axis, ly_prev) * sin_t + rot_axis * np.dot(rot_axis, ly_prev) * (1.0 - cos_t)
            ly_curr /= np.linalg.norm(ly_curr)
            lz_curr = np.cross(ti, ly_curr)
            lz_curr /= np.linalg.norm(lz_curr)
        else:
            ly_curr = ly_prev
            lz_curr = lz_prev
            
        frames.append((ti, ly_curr, lz_curr))
        
    # 4. Generate 3D points
    points_3d = []
    for j in range(N):
        pj = path[j]
        _, ly, lz = frames[j]
        for i in range(M):
            y_i, z_i = poly2d[i]
            pt_3d = pj + y_i * ly + z_i * lz
            points_3d.append(pt_3d)
    points_3d = np.array(points_3d)
    
    # 5. Build quad cells and end caps
    cells = []
    # Quads
    for j in range(N - 1):
        for i in range(M):
            i_next = (i + 1) % M
            v0 = j * M + i
            v1 = j * M + i_next
            v2 = (j + 1) * M + i_next
            v3 = (j + 1) * M + i
            cells.append([4, v0, v1, v2, v3])
            
    # Start Cap
    start_cap = [M] + [i for i in reversed(range(M))]
    cells.append(start_cap)
    
    # End Cap
    end_cap = [M] + [(N - 1) * M + i for i in range(M)]
    cells.append(end_cap)
    
    cells_arr = []
    for c in cells:
        cells_arr.extend(c)
    cells_arr = np.array(cells_arr, dtype=np.int32)
    
    mesh = pv.PolyData(points_3d, faces=cells_arr)
    
    # 6. Map results
    disp1 = np.zeros(3)
    disp2 = np.zeros(3)
    vmis1 = 0.0
    vmis2 = 0.0
    forc1 = np.zeros(3)
    forc2 = np.zeros(3)
    
    if results is not None:
        nr1 = results.node_results.get(elem.n1)
        nr2 = results.node_results.get(elem.n2)
        if nr1 is not None:
            disp1 = nr1.displacement[:3]
            if nr1.reaction_force is not None:
                forc1 = nr1.reaction_force[:3]
        if nr2 is not None:
            disp2 = nr2.displacement[:3]
            if nr2.reaction_force is not None:
                forc2 = nr2.reaction_force[:3]
                
        er = results.element_results.get(elem.id)
        if er is not None:
            vmis1 = er.von_mises_n1
            vmis2 = er.von_mises_n2
            
    disp_3d = []
    vmis_3d = []
    forc_3d = []
    for j in range(N):
        t = j / (N - 1) if N > 1 else 0.0
        d_val = disp1 + t * (disp2 - disp1)
        v_val = vmis1 + t * (vmis2 - vmis1)
        f_val = forc1 + t * (forc2 - forc1)
        for _ in range(M):
            disp_3d.append(d_val)
            vmis_3d.append(v_val)
            forc_3d.append(f_val)
            
    mesh.point_data["DEPL"] = np.array(disp_3d)
    mesh.point_data["DEPL_magnitude"] = np.linalg.norm(mesh.point_data["DEPL"], axis=1)
    mesh.point_data["VMIS"] = np.array(vmis_3d)
    mesh.point_data["FORC_NODA"] = np.array(forc_3d)
    mesh.point_data["FORC_magnitude"] = np.linalg.norm(mesh.point_data["FORC_NODA"], axis=1)
    
    # Map Temperature if load case exists
    temp_val = 20.0
    if results is not None and results.load_case in model.load_cases:
        temp_val = model.load_cases[results.load_case].temperature
    elif model.load_cases:
        temp_val = next(iter(model.load_cases.values())).temperature
    mesh.point_data["TEMP"] = np.full(len(points_3d), temp_val)
    
    return mesh


def build_3d_mesh_from_model(
    model: "TubaModel",
    results: Optional["FEAResults"] = None,
) -> "pv.PolyData":
    """Construct a full 3-D cross-sectional geometry mesh from a TubaModel."""
    _require_pyvista()
    meshes = []
    for elem in model.elements:
        m = _get_element_3d_mesh(model, elem, results)
        if m.n_points > 0:
            meshes.append(m)
            
    if not meshes:
        return pv.PolyData()
        
    merged = meshes[0]
    if len(meshes) > 1:
        merged = merged.merge(meshes[1:])
        
    return merged
