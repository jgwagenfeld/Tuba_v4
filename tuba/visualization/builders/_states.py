"""Deformed/geometry-state and analysis-mesh scene builders."""

from __future__ import annotations
from typing import Any
from typing import Iterable
import numpy as np
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.projection import project_deformed_centerline
from tuba.model import TubaModel
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.geometry.deformed import build_deformed_envelopes
from tuba.geometry.profiles import profile_for_section
from tuba.geometry.section_mesh import deformed_straight_section_surface_mesh
from tuba.refs import EntityRef
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._helpers import _bounds_for_points, _dedupe, _node_coords, _safe_bounds_for_points
from tuba.visualization.builders._imported import _mesh_group_layer_ids


def _build_geometry_state_record(geometry_state: GeometryState) -> tuple[SceneObject, Overlay]:
    object_id = f"object:geometry_state:{geometry_state.id}"
    payload = geometry_state.to_dict()
    scene_object = SceneObject(
        id=object_id,
        kind="geometry_state",
        name=f"Geometry state {geometry_state.id}",
        metadata={
            "geometry_state_id": geometry_state.id,
            "state_type": geometry_state.state_type,
            "load_case": geometry_state.load_case,
            "result_state_id": geometry_state.result_state_id,
            "displacement_scale": geometry_state.displacement_scale,
            "safety_factor": geometry_state.safety_factor,
            "purpose": geometry_state.purpose,
        },
        source={"tuba_geometry_state": payload},
    )
    overlay = Overlay(
        id=f"overlay:geometry_state:{geometry_state.id}",
        kind="geometry_state",
        object_ids=[object_id],
        name=f"Geometry state {geometry_state.id}",
        data=payload,
    )
    return scene_object, overlay
def _build_deformed_state_scene(
    model: TubaModel,
    result_states: list[ResultState],
    geometry_states: list[GeometryState],
    analysis_meshes: list[AnalysisMesh],
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    results_by_id = {result_state.id: result_state for result_state in result_states}
    meshes_by_id = {analysis_mesh.id: analysis_mesh for analysis_mesh in analysis_meshes}

    for geometry_state in geometry_states:
        if geometry_state.state_type not in {"operating", "deformed"}:
            continue
        if geometry_state.result_state_id is None:
            continue
        result_state = results_by_id.get(geometry_state.result_state_id)
        if result_state is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="deformed_state.missing_result_state",
                    message=f"GeometryState {geometry_state.id!r} references missing ResultState {geometry_state.result_state_id!r}.",
                    target=geometry_state.id,
                    source=geometry_state.result_state_id,
                )
            )
            continue
        analysis_mesh = meshes_by_id.get(result_state.mesh_id or "")
        centerline_objects, centerline_assets, centerline_diagnostics = _build_deformed_centerline_scene(
            model,
            result_state,
            geometry_state,
            analysis_mesh,
        )
        envelope_objects, envelope_assets, envelope_diagnostics = _build_deformed_envelope_scene(
            model,
            result_state,
            geometry_state,
            analysis_mesh,
        )
        mesh_objects, mesh_assets = _build_deformed_mesh_scene(model, result_state, geometry_state, analysis_mesh)
        objects.extend(centerline_objects)
        assets.extend(centerline_assets)
        diagnostics.extend(centerline_diagnostics)
        objects.extend(envelope_objects)
        assets.extend(envelope_assets)
        diagnostics.extend(envelope_diagnostics)
        objects.extend(mesh_objects)
        assets.extend(mesh_assets)

    return objects, assets, diagnostics
def _build_deformed_centerline_scene(
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    layer_id = _deformed_layer(geometry_state, "centerline")
    for elem in model.elements:
        projected = project_deformed_centerline(
            model=model,
            element=elem,
            result_state=result_state,
            geometry_state=geometry_state,
            analysis_mesh=analysis_mesh,
        )
        points = [[float(value) for value in point] for point in projected.points]
        base_points = _base_points_for_node_ids(model, analysis_mesh, projected.source_mesh_nodes)
        entity_ref = EntityRef("element", elem.id)
        object_id = f"object:deformed_centerline:{geometry_state.id}:{elem.id}"
        asset_id = f"geometry:deformed_centerline:{geometry_state.id}:{elem.id}"
        metadata = _deformed_metadata(geometry_state, result_state)
        metadata.update(
            {
                "entity_ref": str(entity_ref),
                "source_mesh_nodes": list(projected.source_mesh_nodes),
                "diagnostics": list(projected.diagnostics),
            }
        )
        for diagnostic in projected.diagnostics:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code=f"deformed_centerline.{diagnostic}",
                    message=f"Deformed centerline for {elem.id!r}: {diagnostic}.",
                    target=str(entity_ref),
                    source=geometry_state.id,
                )
            )
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_safe_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_centerline",
                    "entity_ref": str(entity_ref),
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "visual_scale": geometry_state.displacement_scale,
                    "base_points": base_points,
                    "points": points,
                    "source_mesh_nodes": list(projected.source_mesh_nodes),
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=entity_ref,
                kind="deformed_centerline",
                name=f"{elem.id} {geometry_state.id} centerline",
                geometry_asset_id=asset_id,
                layer_ids=[layer_id],
                metadata=metadata,
            )
        )
    return objects, assets, diagnostics
def _build_deformed_envelope_scene(
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    layer_id = _deformed_layer(geometry_state, "envelope")
    for envelope in build_deformed_envelopes(
        model=model,
        result_state=result_state,
        geometry_state=geometry_state,
        envelope_type="insulation",
        analysis_mesh=analysis_mesh,
    ):
        points = [[float(value) for value in point] for point in envelope.polyline]
        base_points = _base_points_for_node_ids(model, analysis_mesh, envelope.source_mesh_nodes)
        object_id = f"object:deformed_envelope:{geometry_state.id}:{envelope.entity}:{envelope.envelope_type}"
        asset_id = f"geometry:deformed_envelope:{geometry_state.id}:{envelope.entity}:{envelope.envelope_type}"
        metadata = _deformed_metadata(geometry_state, result_state)
        metadata.update(
            {
                "entity_ref": str(envelope.entity),
                "envelope_type": envelope.envelope_type,
                "radius_m": float(envelope.radius_m),
                "source_mesh_nodes": list(envelope.source_mesh_nodes),
                "diagnostics": list(envelope.diagnostics),
            }
        )
        for diagnostic in envelope.diagnostics:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code=f"deformed_envelope.{diagnostic}",
                    message=f"Deformed envelope for {envelope.entity}: {diagnostic}.",
                    target=str(envelope.entity),
                    source=geometry_state.id,
                )
            )
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="tube",
                bounds=list(envelope.bounds),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_envelope",
                    "entity_ref": str(envelope.entity),
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "visual_scale": geometry_state.displacement_scale,
                    "envelope_type": envelope.envelope_type,
                    "radius_m": float(envelope.radius_m),
                    "base_points": base_points,
                    "points": points,
                    "source_mesh_nodes": list(envelope.source_mesh_nodes),
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=envelope.entity,
                kind="deformed_envelope",
                name=f"{envelope.entity} {geometry_state.id} {envelope.envelope_type}",
                geometry_asset_id=asset_id,
                layer_ids=[layer_id],
                metadata=metadata,
            )
        )
    return objects, assets, diagnostics
def _build_deformed_mesh_scene(
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset]]:
    if analysis_mesh is None:
        return [], []
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    groups_by_member = _analysis_mesh_groups_by_member(analysis_mesh)
    factor = geometry_state.displacement_scale * geometry_state.safety_factor
    if analysis_mesh.surface_mesh is not None:
        surface = analysis_mesh.surface_mesh
        base_vertices = [[float(value) for value in vertex] for vertex in surface["vertices"]]
        vertices = []
        for vertex, node_id in zip(base_vertices, surface["node_ids"]):
            displacement = np.asarray(
                result_state.node_displacements.get(node_id, (0.0, 0.0, 0.0))[:3],
                dtype=float,
            )
            vertices.append((np.asarray(vertex) + displacement * factor).tolist())
        object_id = f"object:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:volume_skin"
        asset_id = f"geometry:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:volume_skin"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="mesh",
                bounds=_bounds_for_points(vertices, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_analysis_mesh.volume_surface",
                    "mesh_id": analysis_mesh.id,
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "visual_scale": geometry_state.displacement_scale,
                    "base_vertices": base_vertices,
                    "vertices": vertices,
                    "faces": surface["faces"],
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="deformed_analysis_mesh_surface",
                name=f"{analysis_mesh.id} {geometry_state.id} deformed volume skin",
                geometry_asset_id=asset_id,
                layer_ids=["deformed:mesh"],
                metadata={
                    **_deformed_metadata(geometry_state, result_state),
                    "mesh_id": analysis_mesh.id,
                    "role": "volume_surface",
                },
            )
        )
    for element_id, node_ids in analysis_mesh.elements.items():
        if analysis_mesh.surface_mesh is not None and len(node_ids) not in {2, 3}:
            continue
        source = analysis_mesh.element_sources.get(element_id)
        points = [
            _deformed_mesh_point(analysis_mesh, result_state, node_id, factor)
            for node_id in node_ids
        ]
        base_points = _base_points_for_node_ids(None, analysis_mesh, node_ids)
        object_id = f"object:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:{element_id}"
        asset_id = f"geometry:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:{element_id}"
        groups = groups_by_member.get(element_id, [])
        metadata = _deformed_metadata(geometry_state, result_state)
        metadata.update(
            {
                "mesh_id": analysis_mesh.id,
                "element_id": element_id,
                "node_ids": list(node_ids),
                "groups": groups,
                "source_ref": str(source.source_ref) if source is not None else None,
                "role": source.role if source is not None else "unmapped_element",
            }
        )
        if source is not None and source.segment_index is not None:
            metadata["segment_index"] = source.segment_index
        asset_format = "polyline"
        asset_bounds = _safe_bounds_for_points(points, 0.0)
        generation_config: dict[str, Any] = {
            "source": "tuba.deformed_analysis_mesh.element",
            "mesh_id": analysis_mesh.id,
            "element_id": element_id,
            "node_ids": list(node_ids),
            "geometry_state_id": geometry_state.id,
            "result_state_id": result_state.id,
            "load_case": geometry_state.load_case,
            "visual_scale": geometry_state.displacement_scale,
            "base_points": base_points,
            "points": points,
        }
        model_element = (
            model.get_element(source.source_ref.id)
            if source is not None and source.source_ref.kind == "element"
            else None
        )
        if model_element is not None and len(node_ids) == 2:
            profile = profile_for_section(model.sections[model_element.section])
            generation_config["profile_kind"] = profile.kind
            generation_config["source"] = "tuba.deformed_analysis_mesh.profile"
            if profile.kind in {"ibeam", "rectangular"}:
                base_surface, deformed_surface = deformed_straight_section_surface_mesh(
                    model.sections[model_element.section],
                    base_points[0],
                    base_points[1],
                    result_state.node_displacements.get(node_ids[0], (0.0,) * 6),
                    result_state.node_displacements.get(node_ids[1], (0.0,) * 6),
                    scale=factor,
                    twist_angle_deg=float(getattr(model_element, "twist_angle", 0.0)),
                )
                generation_config.update(
                    base_vertices=[list(vertex) for vertex in base_surface.vertices],
                    vertices=[list(vertex) for vertex in deformed_surface.vertices],
                    faces=[list(face) for face in deformed_surface.faces],
                )
                asset_format = "mesh"
                asset_bounds = _bounds_for_points(generation_config["vertices"], 0.0)
            else:
                radius = float(profile.collision_radius_m)
                generation_config["radius_m"] = radius
                if profile.kind == "pipe":
                    generation_config["inner_radius_m"] = float(profile.dimensions["ID"]) / 2.0
                asset_format = "tube"
                asset_bounds = _bounds_for_points(points, radius)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format=asset_format,
                bounds=asset_bounds,
                object_ids=[object_id],
                generation_config=generation_config,
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=source.source_ref if source is not None else None,
                kind="deformed_analysis_mesh_element",
                name=f"{element_id} {geometry_state.id} warped mesh",
                geometry_asset_id=asset_id,
                group_ids=groups,
                layer_ids=["deformed:mesh", *_mesh_group_layer_ids(groups)],
                metadata=metadata,
            )
        )
    return objects, assets
def _deformed_mesh_point(
    analysis_mesh: AnalysisMesh,
    result_state: ResultState,
    node_id: str,
    factor: float,
) -> list[float]:
    base = np.asarray(analysis_mesh.nodes[node_id], dtype=float)
    displacement = np.asarray(result_state.node_displacements.get(node_id, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float)
    return [float(value) for value in (base + displacement[:3] * factor).tolist()]
def _base_points_for_node_ids(
    model: TubaModel | None,
    analysis_mesh: AnalysisMesh | None,
    node_ids: Iterable[str],
) -> list[list[float]]:
    points: list[list[float]] = []
    for node_id in node_ids:
        if model is not None and node_id in model.nodes:
            points.append(_node_coords(model, node_id))
        elif analysis_mesh is not None and node_id in analysis_mesh.nodes:
            points.append([float(value) for value in analysis_mesh.nodes[node_id]])
    return points
def _deformed_layer(geometry_state: GeometryState, asset_type: str) -> str:
    prefix = "visual" if geometry_state.purpose == "visualization" else "physical"
    return f"deformed:{prefix}_{asset_type}"
def _deformed_metadata(geometry_state: GeometryState, result_state: ResultState) -> dict[str, Any]:
    return {
        "geometry_state_id": geometry_state.id,
        "result_state_id": result_state.id,
        "load_case": geometry_state.load_case,
        "state_type": geometry_state.state_type,
        "purpose": geometry_state.purpose,
        "displacement_scale": geometry_state.displacement_scale,
        "safety_factor": geometry_state.safety_factor,
        "visual_scale": geometry_state.displacement_scale,
    }
def _build_analysis_mesh_scene(
    analysis_mesh: AnalysisMesh,
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    groups_by_member = _analysis_mesh_groups_by_member(analysis_mesh)
    line_element_ids = {
        element_id
        for element_id, node_ids in analysis_mesh.elements.items()
        if len(node_ids) in {2, 3}
    }
    line_node_ids = {
        node_id
        for element_id in line_element_ids
        for node_id in analysis_mesh.elements[element_id]
    }

    if analysis_mesh.surface_mesh is not None:
        vertices = analysis_mesh.surface_mesh["vertices"]
        faces = analysis_mesh.surface_mesh["faces"]
        surface_edges = {
            tuple(sorted((face[index], face[(index + 1) % len(face)])))
            for face in faces
            for index in range(len(face))
        }
        volume_edges: set[tuple[str, str]] = set()
        for element_nodes in analysis_mesh.elements.values():
            if len(element_nodes) in {4, 10}:
                corners = element_nodes[:4]
                edge_pairs = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
            elif len(element_nodes) in {8, 20, 27}:
                corners = element_nodes[:8]
                edge_pairs = (
                    (0, 1), (1, 2), (2, 3), (3, 0),
                    (4, 5), (5, 6), (6, 7), (7, 4),
                    (0, 4), (1, 5), (2, 6), (3, 7),
                )
            else:
                continue
            volume_edges.update(
                tuple(sorted((corners[left], corners[right])))
                for left, right in edge_pairs
            )
        volume_corner_node_ids = {node_id for edge in volume_edges for node_id in edge}
        volume_node_ids = [node_id for node_id in analysis_mesh.nodes if node_id in volume_corner_node_ids]
        volume_node_indices = {node_id: index for index, node_id in enumerate(volume_node_ids)}
        object_id = f"object:analysis_mesh:{analysis_mesh.id}:volume_skin"
        asset_id = f"geometry:analysis_mesh:{analysis_mesh.id}:volume_skin"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="mesh",
                bounds=_safe_bounds_for_points(vertices, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.analysis_mesh.volume_skin",
                    "mesh_id": analysis_mesh.id,
                    "vertices": vertices,
                    "faces": faces,
                    "show_edges": True,
                    "surface_edge_indices": [list(edge) for edge in sorted(surface_edges)],
                    "volume_vertices": [list(analysis_mesh.nodes[node_id]) for node_id in volume_node_ids],
                    "volume_edge_indices": [
                        [volume_node_indices[left], volume_node_indices[right]]
                        for left, right in sorted(volume_edges)
                    ],
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=None,
                kind="analysis_mesh_surface",
                name=f"{analysis_mesh.id} volume skin",
                geometry_asset_id=asset_id,
                layer_ids=["analysis_mesh:volume_skin"],
                metadata={
                    "mesh_id": analysis_mesh.id,
                    "solver_name": analysis_mesh.solver_name,
                    "model_revision": analysis_mesh.model_revision,
                    "role": "analysis_input",
                },
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "surface_mesh"}},
            )
        )
    for node_id, coords in analysis_mesh.nodes.items():
        if analysis_mesh.surface_mesh is not None and node_id not in line_node_ids:
            continue
        source = analysis_mesh.node_sources.get(node_id)
        groups = groups_by_member.get(node_id, [])
        if source is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="analysis_mesh.missing_node_source",
                    message=f"Analysis mesh node {node_id!r} has no provenance source.",
                    target=f"{analysis_mesh.id}:node:{node_id}",
                    source=analysis_mesh.id,
                )
            )
        role = source.role if source is not None else "unmapped_node"
        point = [float(value) for value in coords]
        object_id = f"object:analysis_mesh:{analysis_mesh.id}:node:{node_id}"
        asset_id = f"geometry:analysis_mesh:{analysis_mesh.id}:node:{node_id}"
        metadata = _analysis_mesh_source_metadata(
            mesh_id=analysis_mesh.id,
            solver_name=analysis_mesh.solver_name,
            model_revision=analysis_mesh.model_revision,
            member_id=node_id,
            role=role,
            groups=groups,
            source=source,
        )
        metadata["coordinates"] = point
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="point",
                bounds=_bounds_for_points([point], 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.analysis_mesh.node",
                    "mesh_id": analysis_mesh.id,
                    "node_id": node_id,
                    "point": point,
                    "role": role,
                    "groups": groups,
                    "source_ref": str(source.source_ref) if source is not None else None,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=source.source_ref if source is not None else None,
                kind="analysis_mesh_node",
                name=f"{node_id} ({role})",
                geometry_asset_id=asset_id,
                group_ids=groups,
                layer_ids=_analysis_mesh_node_layers(role, groups),
                metadata=metadata,
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "node", "member_id": node_id}},
            )
        )

    for element_id, node_ids in analysis_mesh.elements.items():
        if analysis_mesh.surface_mesh is not None and element_id not in line_element_ids:
            continue
        source = analysis_mesh.element_sources.get(element_id)
        groups = groups_by_member.get(element_id, [])
        if source is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="analysis_mesh.missing_element_source",
                    message=f"Analysis mesh element {element_id!r} has no provenance source.",
                    target=f"{analysis_mesh.id}:element:{element_id}",
                    source=analysis_mesh.id,
                )
            )
        role = source.role if source is not None else "unmapped_element"
        points = [[float(value) for value in analysis_mesh.nodes[node_id]] for node_id in node_ids]
        object_id = f"object:analysis_mesh:{analysis_mesh.id}:element:{element_id}"
        asset_id = f"geometry:analysis_mesh:{analysis_mesh.id}:element:{element_id}"
        metadata = _analysis_mesh_source_metadata(
            mesh_id=analysis_mesh.id,
            solver_name=analysis_mesh.solver_name,
            model_revision=analysis_mesh.model_revision,
            member_id=element_id,
            role=role,
            groups=groups,
            source=source,
        )
        metadata["node_ids"] = list(node_ids)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_safe_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.analysis_mesh.element",
                    "mesh_id": analysis_mesh.id,
                    "element_id": element_id,
                    "node_ids": list(node_ids),
                    "points": points,
                    "role": role,
                    "groups": groups,
                    "source_ref": str(source.source_ref) if source is not None else None,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=source.source_ref if source is not None else None,
                kind="analysis_mesh_element",
                name=f"{element_id} ({role})",
                geometry_asset_id=asset_id,
                group_ids=groups,
                layer_ids=_analysis_mesh_element_layers(groups),
                metadata=metadata,
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "element", "member_id": element_id}},
            )
        )

    return objects, assets, diagnostics
def _analysis_mesh_source_metadata(
    *,
    mesh_id: str,
    solver_name: str,
    model_revision: int,
    member_id: str,
    role: str,
    groups: list[str],
    source: Any,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "mesh_id": mesh_id,
        "solver_name": solver_name,
        "model_revision": model_revision,
        "member_id": member_id,
        "role": role,
        "groups": groups,
    }
    if source is None:
        return metadata
    metadata["source_ref"] = str(source.source_ref)
    if source.segment_index is not None:
        metadata["segment_index"] = source.segment_index
    if getattr(source, "parametric_t", None) is not None:
        metadata["parametric_t"] = source.parametric_t
    if source.metadata:
        metadata["source_metadata"] = dict(source.metadata)
    return metadata
def _analysis_mesh_groups_by_member(analysis_mesh: AnalysisMesh) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for group_id, member_ids in analysis_mesh.groups.items():
        for member_id in member_ids:
            groups.setdefault(member_id, []).append(group_id)
    return {member_id: sorted(group_ids) for member_id, group_ids in groups.items()}
def _analysis_mesh_node_layers(role: str, groups: list[str]) -> list[str]:
    layers = ["analysis_mesh:nodes"]
    if role == "generated_bend_node":
        layers.append("analysis_mesh:generated_bend_nodes")
    if groups:
        layers.append("analysis_mesh:groups")
        layers.extend(f"analysis_mesh:group:{group}" for group in groups)
    return _dedupe(layers)
def _analysis_mesh_element_layers(groups: list[str]) -> list[str]:
    layers = ["analysis_mesh:elements"]
    if groups:
        layers.append("analysis_mesh:groups")
        layers.extend(f"analysis_mesh:group:{group}" for group in groups)
    return _dedupe(layers)
