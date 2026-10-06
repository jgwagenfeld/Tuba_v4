"""Selected boundary footprints and their reference points, before and after meshing."""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable

import numpy as np

from tuba.analysis.mesh import AnalysisMesh
from tuba.refs import EntityRef
from tuba.visualization.scene import GeometryAsset, SceneDiagnostic, SceneObject
from tuba.visualization.builders._contract import SceneContribution
from tuba.visualization.builders._helpers import _bounds_for_points, _node_coords
from tuba.visualization.builders._imported import _reference_attachments, _transform_asset_points, _valid_mesh_payload


def build_interface_mapping_scene(model, *, analysis_meshes: Iterable[AnalysisMesh] = (), volume_export=None) -> SceneContribution:
    """Display authored incidence; mesh group membership supplies resolved cells and nodes."""
    objects, assets, diagnostics = [], [], []
    meshes = list(analysis_meshes)

    def emit(id, ref, metadata, target_parts, target_points):
        source = _node_coords(model, metadata["source_node_ref"].split(":", 1)[1])
        object_id = f"object:interface_mapping:{id}"
        bounds = _bounds_for_points(target_points or [source], 0.0)
        span = max(bounds[i + 3] - bounds[i] for i in range(3))
        radius = max(span * .025, .003)
        metadata.update(source_point_m=source, target_bounds_m=bounds,
                        target_geometry_available=bool(target_parts))
        created = []

        def asset(part, format, config, points):
            asset_id = f"geometry:interface_mapping:{id}:{part}:{len(created)}"
            created.append(GeometryAsset(id=asset_id, format=format,
                bounds=_bounds_for_points(points, radius if format == "marker" else 0.0), object_ids=[object_id],
                generation_config={"source": "tuba.interface_mapping", "part": part,
                    "color": "#06b6d4" if part == "target" else "#f59e0b", **config}))

        for format, config, points in target_parts:
            asset("target", format, {"opacity": .7, "transparent": True, **config}, points)
        asset("source", "marker", {"point": source, "radius_m": radius}, [source])
        if target_points:
            # Spokes show incidence, not the solver's individual constraint equations.
            samples = target_points[::max(1, math.ceil(len(target_points) / 12))]
            points = [source]
            for point in samples:
                points.extend([point, source])
            asset("spokes", "polyline", {"points": points}, points)
        label = [source[0], source[1], source[2] + max(span * .2, .03)]
        text = f"{metadata['source_node_ref'].split(':', 1)[1]} · 0D ↔ {metadata['target_dimension']}D"
        asset("label", "label", {"text": text, "position": label,
              "height": max(span * .07, .006)}, [label])
        if not target_parts:
            diagnostics.append(SceneDiagnostic(code="interface_mapping.unavailable_target", severity="warning",
                message=f"Mapping {id!r} has no exact displayable target selection; reimport its source or generate its analysis mesh.", target=object_id))
        objects.append(SceneObject(id=object_id, entity_ref=ref, kind="interface_mapping", name=id,
            geometry_asset_id=created[0].id, layer_ids=["interface_mappings"], metadata=metadata))
        assets.extend(created)

    for coupling in model.couplings.values():
        if coupling.source_node.id not in model.nodes:
            continue
        source_node_ref = str(coupling.source_node)
        attachments = _reference_attachments(model, coupling.source_node.id)
        owners = [f"coupling:{coupling.id}", str(coupling.source), source_node_ref, str(coupling.target)]
        for attachment in attachments:
            owners.extend([f"support:{attachment['id']}", f"node:{attachment['attached_to']}"])
        metadata = {"source_ref": str(coupling.source), "source_node_ref": source_node_ref,
            "target_ref": str(coupling.target), "coupling_ref": f"coupling:{coupling.id}",
            "method": f"{coupling.code_aster_keyword} / {coupling.code_aster_option}",
            "status": "authored", "attachments": attachments, "owner_refs": owners}
        parts, points = [], []
        if coupling.kind == "pipe_to_solid_port":
            port = model.ports.get(coupling.target.id)
            if port is None:
                continue
            component = model.imported_components.get(port.owner.id)
            metadata.update(model_mapping="1D frame ↔ 3D solid" if coupling.code_aster_option == "3D_POU" else "1D pipe ↔ 3D solid",
                interface_mapping="0D endpoint ↔ 2D cut face", target_dimension=2,
                face_group=port.face_group, node_group=f"G_NODE_{coupling.source_node.id}")
            metadata["owner_refs"].append(str(port.owner))
            selected = _mesh_selection(meshes, face_group=port.face_group)
            if selected:
                parts, points, resolved = selected
                metadata.update(status="meshed", **resolved)
            elif component:
                parts, points = _component_faces(model, component, [port.metadata.get("face_selector")])
        elif coupling.kind == "rigid_patch":
            data = coupling.metadata
            selection = data.get("selection")
            metadata["node_group"] = data.get("mesh_node_group")
            if selection == "component_faces":
                metadata.update(model_mapping="0D reference ↔ 3D solid", interface_mapping="0D reference ↔ 2D face", target_dimension=2)
                if data.get("node_filter"):
                    metadata.update(interface_mapping="0D reference ↔ selected nodes on a 2D face", node_filter=data["node_filter"])
                selected = _mesh_selection(meshes, node_group=data.get("mesh_node_group"), owner=coupling.target,
                                           source_group=f"G_NODE_{coupling.source_node.id}")
                if selected:
                    parts, points, resolved = selected
                    metadata.update(status="meshed", **resolved)
                elif component := model.imported_components.get(coupling.target.id):
                    parts, points = _component_faces(model, component, data.get("face_selectors", []), node_filter=data.get("node_filter"))
            elif selection in {"shell_edges", "shell_vertices"}:
                region = next((r for r in model.analysis_regions.values() if r.role == "shell_2d" and r.owner == coupling.target), None)
                if region is None:
                    continue
                polygon = region.metadata["polygon_m"]
                is_edge = selection == "shell_edges"
                metadata.update(model_mapping="0D reference ↔ 2D shell",
                    interface_mapping="0D reference ↔ 1D edges" if is_edge else "0D reference ↔ 0D vertices", target_dimension=1 if is_edge else 0)
                for index in data.get("edges" if is_edge else "vertices", []):
                    selected_points = [polygon[index], polygon[(index + 1) % len(polygon)]] if is_edge else [polygon[index]]
                    points.extend(selected_points)
                    parts.append(("line", {"points": selected_points}, selected_points) if is_edge else
                                 ("marker", {"point": selected_points[0], "radius_m": .006}, selected_points))
                resolved = _resolved_nodes(metadata, meshes, data.get("mesh_node_group"), f"G_NODE_{coupling.source_node.id}")
                if resolved:
                    mesh, node_ids = resolved
                    points = [list(mesh.nodes[id]) for id in node_ids]
                    parts = [("marker", {"point": p, "radius_m": .006}, [p]) for p in points]
                    if is_edge:
                        selected = set(node_ids)
                        boundary = Counter(tuple(sorted((nodes[i], nodes[(i + 1) % len(nodes)])))
                            for id, source in mesh.element_sources.items()
                            if source.role == "shell_cell" and source.source_ref == region.owner
                            for nodes in [mesh.elements[id]] for i in range(len(nodes)))
                        edges = [edge for edge, count in boundary.items() if count == 1 and set(edge).issubset(selected)]
                        for edge in edges:
                            segment = [list(mesh.nodes[id]) for id in edge]
                            parts.append(("line", {"points": segment}, segment))
                        metadata["target_edge_count"] = len(edges)
            elif selection == "nodes":
                points = [_node_coords(model, node) for node in data.get("nodes", []) if node in model.nodes]
                parts = [("marker", {"point": p, "radius_m": .006}, [p]) for p in points]
                metadata.update(model_mapping="0D reference ↔ 0D nodes", interface_mapping="0D reference ↔ 0D nodes", target_dimension=0)
                metadata["owner_refs"].extend(f"node:{n}" for n in data.get("nodes", []))
                if resolved := _resolved_nodes(metadata, meshes, data.get("mesh_node_group"), f"G_NODE_{coupling.source_node.id}"):
                    mesh, node_ids = resolved
                    points = [list(mesh.nodes[id]) for id in node_ids]
                    parts = [("marker", {"point": p, "radius_m": .006}, [p]) for p in points]
            else:
                continue
        else:
            continue
        metadata["owner_refs"] = list(dict.fromkeys(metadata["owner_refs"]))
        metadata.setdefault("target_face_count", sum(len(config.get("faces", [])) for _, config, _ in parts))
        emit(coupling.id, EntityRef("coupling", coupling.id), metadata, parts, points)

    if volume_export:
        from tuba.geometry.volume import build_volume_geometry
        from tuba.solver.aster_volume import _coupling_groups
        ids = tuple(volume_export.get("element_ids", ()))
        try:
            geometry = build_volume_geometry(model, ids)
            terminals = {t.node_id: t for t in geometry.terminals}
            groups = {f"G_END_{node}": () for node in terminals}
            for face_group, node_group, axis in _coupling_groups(model, groups, ids):
                node = node_group.removeprefix("G_NODE_")
                terminal = terminals[node]
                continuation = next(e for e in model.elements if e.id not in ids and node in (e.n1, e.n2))
                metadata = {"source_ref": f"element:{continuation.id}", "source_node_ref": f"node:{node}",
                    "target_ref": f"element:{terminal.element_id}", "owner_refs": [
                        f"element:{continuation.id}", f"node:{node}", *(f"element:{id}" for id in ids)],
                    "model_mapping": "1D pipe ↔ 3D solid", "interface_mapping": "0D endpoint ↔ 2D cut face",
                    "method": "LIAISON_ELEM / 3D_TUYAU", "status": "authored", "target_dimension": 2,
                    "face_group": face_group, "node_group": node_group, "geometry_ref": geometry.id}
                selected = _mesh_selection(meshes, face_group=face_group)
                if selected:
                    parts, points, resolved = selected
                    metadata.update(status="meshed", **resolved)
                else:
                    section = model.sections[model.get_element(terminal.element_id).section]
                    vertices, faces = _annular_face(terminal.point, axis, section.OD / 2, section.ID / 2)
                    parts, points = [("mesh", {"vertices": vertices, "faces": faces}, vertices)], vertices
                    metadata["target_face_count"] = len(faces)
                emit(f"volume:{node}", EntityRef("element", continuation.id), metadata, parts, points)
        except (ValueError, KeyError) as exc:
            diagnostics.append(SceneDiagnostic(code="interface_mapping.invalid_volume_selection", severity="warning",
                message=f"Volume interface mapping unavailable: {exc}"))
    return SceneContribution(objects=tuple(objects), assets=tuple(assets), diagnostics=tuple(diagnostics))


def _clip_face_triangle(points, node_filter):
    """Clip display triangles in source coordinates to the authored half-space."""
    from tuba.mixed import patch_node_filter_contains
    axis = ("x", "y", "z").index(node_filter["axis"])
    threshold = node_filter["threshold"]
    clipped = []
    for start, end in zip(points, points[1:] + points[:1]):
        start_in = patch_node_filter_contains(start, node_filter)
        end_in = patch_node_filter_contains(end, node_filter)
        if start_in:
            clipped.append(start)
        if start_in != end_in:
            fraction = (threshold - start[axis]) / (end[axis] - start[axis])
            clipped.append([a + fraction*(b-a) for a,b in zip(start,end)])
    return clipped


def _component_faces(model, component, selectors, *, node_filter=None):
    from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError
    asset = model.cad_assets[component.asset.id]
    try:
        source_vertices, source_faces = asset.metadata.get("mesh_vertices_local"), asset.metadata.get("mesh_faces")
        if not selectors or not _valid_mesh_payload(source_vertices, source_faces):
            return [], []
        descriptors = [{**p["selector"], "face_indices": p["face_indices"]}
                       for p in asset.metadata.get("display_face_partitions", [])]
        if not descriptors:
            return [], []
        indices = sorted({index for selector in selectors
                          for index in StepAnalysisImporter._select_face(descriptors, selector)["face_indices"]})
        if not indices or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(source_faces) for i in indices):
            return [], []
        faces = [source_faces[index] for index in indices]
        if node_filter:
            vertices, clipped_faces = [], []
            for face in faces:
                polygon = _clip_face_triangle([source_vertices[i] for i in face], node_filter)
                offset = len(vertices)
                vertices.extend(polygon)
                for i in range(1, len(polygon)-1):
                    if np.linalg.norm(np.cross(np.subtract(polygon[i],polygon[0]),np.subtract(polygon[i+1],polygon[0]))) > 1e-12:
                        clipped_faces.append([offset,offset+i,offset+i+1])
            if not clipped_faces:
                return [], []
            vertices = _transform_asset_points(vertices, asset)
            return [("mesh", {"vertices": vertices, "faces": clipped_faces}, vertices)], vertices
        used = list(dict.fromkeys(index for face in faces for index in face))
        vertices = _transform_asset_points([asset.metadata["mesh_vertices_local"][i] for i in used], asset)
        remap = {index: i for i, index in enumerate(used)}
        return [("mesh", {"vertices": vertices, "faces": [[remap[i] for i in face] for face in faces]}, vertices)], vertices
    except (StepImportError, KeyError, TypeError, IndexError, ValueError):
        return [], []


def _mesh_selection(meshes, *, face_group=None, node_group=None, owner=None, source_group=None):
    for mesh in meshes:
        excluded = set(mesh.groups.get(source_group, ())) if source_group else set()
        node_ids = set(mesh.groups.get(node_group, ())) - excluded if node_group else set()
        ids = list(mesh.groups.get(face_group, ())) if face_group else [id for id, source in mesh.element_sources.items()
            if source.role == "volume_skin" and source.source_ref == owner and
            set(mesh.elements[id]).issubset(node_ids)]
        ids = [id for id in ids if id in mesh.elements and
               mesh.element_sources.get(id) and mesh.element_sources[id].role == "volume_skin"]
        if not ids and not node_ids:
            continue
        node_ids = sorted(node_ids if node_group else {n for id in ids for n in mesh.elements[id]})
        if any(n not in mesh.nodes for n in node_ids):
            continue
        corners = [list(mesh.elements[id][:3] if len(mesh.elements[id]) in {3, 6} else mesh.elements[id][:4]) for id in ids]
        used = list(dict.fromkeys(n for face in corners for n in face))
        vertices = [list(mesh.nodes[n]) for n in used]
        remap = {n: i for i, n in enumerate(used)}
        config = {"vertices": vertices, "faces": [[remap[n] for n in face] for face in corners], "show_edges": True}
        parts = [("mesh", config, vertices)] if ids else []
        represented = {n for id in ids for n in mesh.elements[id]}
        for node in node_ids if node_group else ():
            if node not in represented:
                point = list(mesh.nodes[node])
                parts.append(("marker", {"point": point, "radius_m": .003}, [point]))
        points = [list(mesh.nodes[n]) for n in node_ids] if node_group else vertices
        return parts, points, {"mesh_id": mesh.id, "node_ids": node_ids,
            "element_ids": ids, "target_node_count": len(node_ids), "target_face_count": len(ids)}
    return None


def _resolved_nodes(metadata, meshes, node_group, source_group):
    for mesh in meshes:
        ids = sorted(set(mesh.groups.get(node_group, ())) - set(mesh.groups.get(source_group, ())))
        if ids and all(id in mesh.nodes for id in ids):
            metadata.update(status="meshed", mesh_id=mesh.id, node_ids=ids, target_node_count=len(ids))
            return mesh, ids
    return None


def _annular_face(center, axis, outer, inner):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    seed = np.eye(3)[int(np.argmin(np.abs(axis)))]
    u = np.cross(axis, seed)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    center = np.asarray(center, dtype=float)
    vertices = [(center + radius * (math.cos(i * math.tau / 32) * u + math.sin(i * math.tau / 32) * v)).tolist()
                for radius in (outer, inner) for i in range(32)]
    faces = [face for i in range(32) for face in ([i, (i + 1) % 32, 32 + i],
             [(i + 1) % 32, 32 + (i + 1) % 32, 32 + i])]
    return vertices, faces
