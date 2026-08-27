"""Solver-result and result-state scene/overlay builders."""

from __future__ import annotations
from typing import Any
import numpy as np
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.tuyau import (
    CODE_ASTER_TUYAU_NCOU,
    CODE_ASTER_TUYAU_NSEC,
    section_profile,
    subpoint_station,
)
from tuba.model import TubaModel
from tuba.analysis.results import ResultState
from tuba.refs import EntityRef
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._helpers import _as_float, _as_int, _bounds_for_points, _coerce_point, _dedupe, _node_coords, _numeric_triplet, _object_id, _object_ids_for_node, _safe_id, _vector_endpoint
def _build_result_state_record(result_state: ResultState) -> tuple[SceneObject, Overlay]:
    object_id = f"object:result_state:{result_state.id}"
    payload = _compact_result_state_payload(result_state)
    scene_object = SceneObject(
        id=object_id,
        kind="result_state",
        name=f"Result state {result_state.load_case}",
        metadata={
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "model_revision": result_state.model_revision,
            "solver_name": result_state.solver_name,
            "load_case": result_state.load_case,
            "mesh_id": result_state.mesh_id,
            "node_count": len(result_state.node_displacements),
            "element_result_count": len(result_state.element_results),
        },
        source={"tuba_result_state": payload},
    )
    overlay = Overlay(
        id=f"overlay:result_state:{result_state.id}",
        kind="result_state",
        object_ids=[object_id],
        name=f"Result state {result_state.load_case}",
        data=payload,
    )
    return scene_object, overlay
def _compact_result_state_payload(result_state: ResultState) -> dict[str, Any]:
    payload = result_state.to_dict()
    metadata = dict(payload.get("metadata", {}))
    subpoints = metadata.pop("tuyau_subpoints", None)
    if isinstance(subpoints, list):
        metadata["tuyau_subpoint_count"] = len(subpoints)
        source_file = result_state.files.get("tuyau_subpoints") or result_state.files.get("sieq")
        if source_file:
            metadata["tuyau_subpoints_file"] = source_file
    volume_values = metadata.pop("volume_von_mises", None)
    if isinstance(volume_values, dict):
        metadata["volume_von_mises_count"] = len(volume_values)
        source_file = result_state.files.get("sieq")
        if source_file:
            metadata["volume_von_mises_file"] = source_file
    if metadata.get("volume_analysis"):
        metadata["volume_displacement_count"] = len(payload.get("node_displacements", {}))
        metadata["volume_reaction_node_count"] = len(payload.get("node_reactions", {}))
        payload["node_displacements"] = {}
        payload["node_reactions"] = {}
    payload["metadata"] = metadata
    return payload
def _build_result_state_result_scene(
    model: TubaModel,
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []
    diagnostics: list[SceneDiagnostic] = []

    volume_objects, volume_assets, volume_overlay = _result_state_volume_stress_scene(
        result_state,
        analysis_mesh,
    )
    if volume_overlay is not None:
        objects.extend(volume_objects)
        assets.extend(volume_assets)
        overlays.append(volume_overlay)
    else:
        stress_overlay = _result_state_stress_overlay(model, result_state, diagnostics)
        if stress_overlay is not None:
            overlays.append(stress_overlay)

    if volume_overlay is not None:
        displacement_objects, displacement_assets, displacement_overlay = (
            _result_state_volume_displacement_scene(result_state, analysis_mesh)
        )
        reaction_overlays = _result_state_volume_reaction_overlays(model, result_state, analysis_mesh)
    else:
        displacement_overlay = _result_state_displacement_overlay(model, result_state, analysis_mesh, diagnostics)
        displacement_objects, displacement_assets = (
            _result_state_vector_scene(result_state, displacement_overlay)
            if displacement_overlay is not None
            else ([], [])
        )
        reaction_overlays = _result_state_reaction_overlays(model, result_state, analysis_mesh)
    if displacement_overlay is not None:
        objects.extend(displacement_objects)
        assets.extend(displacement_assets)
        overlays.append(displacement_overlay)

    for reaction_overlay in reaction_overlays:
        reaction_objects, reaction_assets = _result_state_vector_scene(result_state, reaction_overlay)
        objects.extend(reaction_objects)
        assets.extend(reaction_assets)
        overlays.append(reaction_overlay)

    parser_overlay = _result_state_parser_diagnostics_overlay(result_state)
    if parser_overlay is not None:
        overlays.append(parser_overlay)

    subpoint_objects, subpoint_assets, subpoint_overlay, subpoint_diagnostics = _result_state_tuyau_subpoint_scene(
        model,
        result_state,
    )
    if subpoint_overlay is not None:
        overlays.append(subpoint_overlay)
    diagnostics.extend(subpoint_diagnostics)

    objects.extend(subpoint_objects)
    assets.extend(subpoint_assets)
    return objects, assets, overlays, diagnostics


def _result_state_volume_stress_scene(
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay | None]:
    values_by_node = result_state.metadata.get("volume_von_mises")
    surface_mesh = None if analysis_mesh is None else analysis_mesh.surface_mesh
    if not isinstance(values_by_node, dict) or not surface_mesh or not surface_mesh.get("node_ids"):
        return [], [], None
    node_ids = surface_mesh["node_ids"]
    try:
        values = [float(values_by_node[node_id]) for node_id in node_ids]
    except (KeyError, TypeError, ValueError):
        return [], [], None
    if not values or not np.isfinite(values).all():
        return [], [], None

    object_id = f"object:solver_result:volume_stress:{_safe_id(result_state.id)}"
    asset_id = f"geometry:solver_result:volume_stress:{_safe_id(result_state.id)}"
    value_range = {"min": min(values), "max": max(values)}
    legend = {
        "field": "FE VMIS (not code stress)",
        "unit": "Pa",
        "range": value_range,
        "color_map": "turbo",
        "thresholds": {},
    }
    asset = GeometryAsset(
        id=asset_id,
        format="mesh",
        bounds=_bounds_for_points(surface_mesh["vertices"], 0.0),
        object_ids=[object_id],
        generation_config={
            "source": "tuba.result_state.volume_stress",
            "result_state_id": result_state.id,
            "mesh_id": analysis_mesh.id,
            "vertices": surface_mesh["vertices"],
            "faces": surface_mesh["faces"],
            "vertex_values": values,
            "legend": legend,
            "compliance_role": "visualization_only_not_asme_code_stress",
        },
    )
    obj = SceneObject(
        id=object_id,
        kind="volume_stress_field",
        name=f"3D FE VMIS (not code stress) {result_state.load_case}",
        geometry_asset_id=asset_id,
        layer_ids=["solver_result:volume_stress"],
        metadata={
            "result_state_id": result_state.id,
            "mesh_id": analysis_mesh.id,
            "field": "VMIS",
            "unit": "Pa",
            "compliance_role": "visualization_only_not_asme_code_stress",
        },
    )
    overlay = Overlay(
        id=f"overlay:solver_result:volume_stress:{result_state.id}",
        kind="solver_result",
        object_ids=[object_id],
        name=f"3D FE VMIS (not code stress) {result_state.load_case}",
        data={
            "result_type": "stress",
            "field": "FE VMIS (not code stress)",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": analysis_mesh.id,
            "load_case": result_state.load_case,
            "values": {object_id: max(values)},
            "range": value_range,
            "unit": "Pa",
            "legend": legend,
            "compliance_role": "visualization_only_not_asme_code_stress",
            "averaging": "arithmetic mean of SIEQ_ELNO element-node rows at each surface node",
        },
    )
    return [obj], [asset], overlay


def _result_state_volume_displacement_scene(
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay | None]:
    surface_mesh = None if analysis_mesh is None else analysis_mesh.surface_mesh
    if not surface_mesh or not surface_mesh.get("node_ids"):
        return [], [], None
    node_ids = surface_mesh["node_ids"]
    try:
        vectors = [
            [float(value) for value in result_state.node_displacements[node_id][:3]]
            for node_id in node_ids
        ]
    except (KeyError, TypeError, ValueError):
        return [], [], None
    vector_array = np.asarray(vectors, dtype=float)
    if not np.isfinite(vector_array).all():
        return [], [], None
    base = np.asarray(surface_mesh["vertices"], dtype=float)
    displaced = base + vector_array
    values = np.linalg.norm(vector_array, axis=1).tolist()
    value_range = {"min": min(values), "max": max(values)}
    legend = {
        "field": "displacement_magnitude",
        "unit": "m",
        "range": value_range,
        "color_map": "viridis",
        "thresholds": {},
    }
    object_id = f"object:solver_result:volume_displacement:{_safe_id(result_state.id)}"
    asset_id = f"geometry:solver_result:volume_displacement:{_safe_id(result_state.id)}"
    asset = GeometryAsset(
        id=asset_id,
        format="mesh",
        bounds=_bounds_for_points(displaced.tolist(), 0.0),
        object_ids=[object_id],
        generation_config={
            "source": "tuba.result_state.volume_displacement",
            "result_state_id": result_state.id,
            "mesh_id": analysis_mesh.id,
            "vertices": displaced.tolist(),
            "base_vertices": surface_mesh["vertices"],
            "faces": surface_mesh["faces"],
            "vertex_values": values,
            "legend": legend,
            "deformation_scale": 1.0,
        },
    )
    obj = SceneObject(
        id=object_id,
        kind="volume_displacement_field",
        name=f"3D displacement {result_state.load_case}",
        geometry_asset_id=asset_id,
        layer_ids=["solver_result:volume_displacement"],
        metadata={"result_state_id": result_state.id, "mesh_id": analysis_mesh.id, "unit": "m"},
    )
    overlay = Overlay(
        id=f"overlay:solver_result:volume_displacement:{result_state.id}",
        kind="solver_result",
        object_ids=[object_id],
        name=f"3D displacement {result_state.load_case}",
        data={
            "result_type": "displacement",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": analysis_mesh.id,
            "load_case": result_state.load_case,
            "values": {object_id: max(values)},
            "range": value_range,
            "legend": legend,
            "deformation_scale": 1.0,
        },
    )
    return [obj], [asset], overlay
def _result_state_vector_scene(
    result_state: ResultState,
    overlay: Overlay,
) -> tuple[list[SceneObject], list[GeometryAsset]]:
    result_type = str(overlay.data.get("result_type", ""))
    if result_type not in {"displacement", "reaction_force", "reaction_moment"}:
        return [], []
    kind = "displacement_vector" if result_type == "displacement" else "reaction_vector"
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    vector_object_ids: list[str] = []
    for vector in overlay.data.get("vectors", []):
        # Analysis-mesh nodes already have authoritative selectable scene
        # objects. Keep their displacement provenance on the overlay without
        # multiplying the public bundle with duplicate vector geometry.
        if vector.get("analysis_mesh_node_object_id"):
            continue
        start = _numeric_triplet(vector.get("start"))
        end = _numeric_triplet(vector.get("end"))
        if start is None or end is None:
            continue
        if float(np.linalg.norm(np.array(end, dtype=float) - np.array(start, dtype=float))) <= 1e-12:
            continue
        node_id = str(vector.get("node_id", "node"))
        object_id = f"object:solver_result:{result_type}:{_safe_id(result_state.id)}:{_safe_id(node_id)}"
        asset_id = f"geometry:solver_result:{result_type}:{_safe_id(result_state.id)}:{_safe_id(node_id)}"
        generation_config = {
            "source": "tuba.result_state",
            "result_type": result_type,
            "result_state_id": result_state.id,
            "load_case": result_state.load_case,
            "node_id": node_id,
            "start": start,
            "end": end,
            "color": {
                "displacement": "#7c3aed",
                "reaction_force": "#dc2626",
                "reaction_moment": "#f97316",
            }[result_type],
        }
        if result_type == "reaction_force":
            generation_config["reaction_force_n"] = list(vector.get("reaction_force_n", []))
        elif result_type == "reaction_moment":
            generation_config["reaction_moment_nm"] = list(vector.get("reaction_moment_nm", []))
        else:
            generation_config["displacement_m"] = list(vector.get("displacement_m", []))
            generation_config["rotation_rad"] = list(vector.get("rotation_rad", []))
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="vector",
                bounds=_bounds_for_points([start, end], 0.0),
                object_ids=[object_id],
                generation_config=generation_config,
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind=kind,
                name=f"{node_id} {result_type.replace('_', ' ')} {result_state.load_case}",
                geometry_asset_id=asset_id,
                layer_ids=[f"result:{result_type}"],
                metadata={
                    "result_type": result_type,
                    "result_state_id": result_state.id,
                    "load_case": result_state.load_case,
                    "node_id": node_id,
                    "magnitude": vector.get(
                        {
                            "displacement": "magnitude_m",
                            "reaction_force": "magnitude_n",
                            "reaction_moment": "magnitude_nm",
                        }[result_type]
                    ),
                },
            )
        )
        vector_object_ids.append(object_id)
    if vector_object_ids:
        overlay.object_ids = _dedupe([*overlay.object_ids, *vector_object_ids])
    return objects, assets
def _result_state_stress_overlay(
    model: TubaModel,
    result_state: ResultState,
    diagnostics: list[SceneDiagnostic],
) -> Overlay | None:
    values: dict[str, float] = {}
    object_ids: list[str] = []
    entity_refs: list[EntityRef] = []
    element_metadata: dict[str, dict[str, Any]] = {}
    for elem in model.elements:
        object_id = _object_id(EntityRef("element", elem.id))
        data = result_state.element_results.get(elem.id)
        if data is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.missing_element_result",
                    message=f"ResultState {result_state.id!r} has no element result for {elem.id!r}.",
                    target=str(EntityRef("element", elem.id)),
                    source=result_state.id,
                )
            )
            continue
        if "max_von_mises" not in data:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.missing_stress",
                    message=f"ResultState {result_state.id!r} has no max_von_mises value for {elem.id!r}.",
                    target=str(EntityRef("element", elem.id)),
                    source=result_state.id,
                )
            )
            continue
        value = float(data["max_von_mises"])
        if not np.isfinite(value):
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.invalid_stress",
                    message=f"ResultState {result_state.id!r} has non-finite max_von_mises for {elem.id!r}.",
                    target=str(EntityRef("element", elem.id)),
                    source=result_state.id,
                )
            )
            continue
        values[object_id] = value
        object_ids.append(object_id)
        entity_refs.append(EntityRef("element", elem.id))
        element_metadata[object_id] = _result_state_element_result_metadata(data)

    if not values:
        return None
    numeric_values = list(values.values())
    hotspots = _stress_hotspots(values)
    return Overlay(
        id=f"overlay:solver_result:stress:{result_state.id}",
        kind="solver_result",
        object_ids=object_ids,
        entity_refs=entity_refs,
        name=f"FE VMIS (not code stress) {result_state.load_case}",
        data={
            "result_type": "stress",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "field": "max_von_mises",
            "values": values,
            "compliance_role": "visualization_only_not_asme_code_stress",
            "range": {"min": min(numeric_values), "max": max(numeric_values)},
            "unit": "Pa",
            "legend": {
                "field": "FE VMIS (not code stress)",
                "unit": "Pa",
                "range": {"min": min(numeric_values), "max": max(numeric_values)},
                "color_map": "turbo",
                "thresholds": {},
            },
            "hotspots": hotspots,
            "element_results": element_metadata,
        },
    )
def _result_state_displacement_overlay(
    model: TubaModel,
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
    diagnostics: list[SceneDiagnostic],
) -> Overlay | None:
    vectors: list[dict[str, Any]] = []
    values: dict[str, list[float]] = {}
    object_ids: list[str] = []
    for node_id, displacement in result_state.node_displacements.items():
        if any(value is None or not np.isfinite(float(value)) for value in displacement[:3]):
            continue
        vector = [float(value) for value in displacement[:3]]
        magnitude = float(np.linalg.norm(vector))
        values[node_id] = vector
        node_object_ids = _object_ids_for_node(model, node_id)
        object_ids.extend(node_object_ids)
        entry: dict[str, Any] = {
            "node_id": node_id,
            "displacement_m": vector,
            "rotation_rad": [None if value is None else float(value) for value in displacement[3:6]],
            "magnitude_m": magnitude,
            "object_ids": node_object_ids,
        }
        if node_id in model.nodes:
            entry["start"] = _node_coords(model, node_id)
            entry["end"] = [entry["start"][index] + vector[index] for index in range(3)]
        elif analysis_mesh is not None and node_id in analysis_mesh.nodes:
            analysis_mesh_node_object_id = f"object:analysis_mesh:{analysis_mesh.id}:node:{node_id}"
            entry["object_ids"] = [analysis_mesh_node_object_id]
            entry["analysis_mesh_id"] = analysis_mesh.id
            entry["analysis_mesh_node_object_id"] = analysis_mesh_node_object_id
            entry["coordinate_source"] = "analysis_mesh"
            entry["start"] = [float(value) for value in analysis_mesh.nodes[node_id]]
            entry["end"] = [entry["start"][index] + vector[index] for index in range(3)]
            object_ids.append(analysis_mesh_node_object_id)
        else:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.missing_node_geometry",
                    message=f"ResultState {result_state.id!r} has displacement for non-native node {node_id!r}.",
                    target=node_id,
                    source=result_state.id,
                )
            )
        vectors.append(entry)

    if not vectors:
        return None
    numeric_values = [float(np.linalg.norm(vector)) for vector in values.values()]
    return Overlay(
        id=f"overlay:solver_result:displacement:{result_state.id}",
        kind="solver_result",
        object_ids=_dedupe(object_ids),
        name=f"Displacement {result_state.load_case}",
        data={
            "result_type": "displacement",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "vectors": vectors,
            "values": values,
            "legend": {
                "field": "displacement_magnitude",
                "unit": "m",
                "range": {"min": min(numeric_values), "max": max(numeric_values)},
                "color_map": "viridis",
                "thresholds": {},
            },
        },
    )
def _result_state_reaction_overlays(
    model: TubaModel,
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
) -> list[Overlay]:
    overlays: list[Overlay] = []
    for result_type, component_slice, value_key, magnitude_key, unit, label in (
        ("reaction_force", slice(0, 3), "reaction_force_n", "magnitude_n", "N", "Reaction forces"),
        ("reaction_moment", slice(3, 6), "reaction_moment_nm", "magnitude_nm", "N*m", "Reaction moments"),
    ):
        vectors: list[dict[str, Any]] = []
        values: dict[str, list[float]] = {}
        object_ids: list[str] = []
        for node_id, reaction in result_state.node_reactions.items():
            components = reaction[component_slice]
            if any(value is None or not np.isfinite(float(value)) for value in components):
                continue
            vector = [float(value) for value in components]
            magnitude = float(np.linalg.norm(vector))
            if magnitude <= 0.0:
                continue
            values[node_id] = vector
            node_object_ids = _object_ids_for_node(model, node_id)
            object_ids.extend(node_object_ids)
            entry: dict[str, Any] = {
                "node_id": node_id,
                value_key: vector,
                magnitude_key: magnitude,
                "object_ids": node_object_ids,
            }
            if node_id in model.nodes:
                entry["start"] = _node_coords(model, node_id)
                entry["end"] = _vector_endpoint(entry["start"], vector)
            elif analysis_mesh is not None and node_id in analysis_mesh.nodes:
                mesh_object_id = f"object:analysis_mesh:{analysis_mesh.id}:node:{node_id}"
                entry["object_ids"] = [mesh_object_id]
                entry["analysis_mesh_id"] = analysis_mesh.id
                entry["analysis_mesh_node_object_id"] = mesh_object_id
                entry["coordinate_source"] = "analysis_mesh"
                entry["start"] = [float(value) for value in analysis_mesh.nodes[node_id]]
                entry["end"] = _vector_endpoint(entry["start"], vector)
                object_ids.append(mesh_object_id)
            vectors.append(entry)
        if not vectors:
            continue
        numeric_values = [float(np.linalg.norm(vector)) for vector in values.values()]
        overlays.append(
            Overlay(
                id=f"overlay:solver_result:{result_type}:{result_state.id}",
                kind="solver_result",
                object_ids=_dedupe(object_ids),
                name=f"{label} {result_state.load_case}",
                data={
                    "result_type": result_type,
                    "result_state_id": result_state.id,
                    "study_id": result_state.study_id,
                    "mesh_id": result_state.mesh_id,
                    "load_case": result_state.load_case,
                    "vectors": vectors,
                    "values": values,
                    "legend": {
                        "field": f"{result_type}_magnitude",
                        "unit": unit,
                        "range": {"min": min(numeric_values), "max": max(numeric_values)},
                        "color_map": "magma",
                        "thresholds": {},
                    },
                },
            )
        )
    return overlays


def _result_state_volume_reaction_overlays(
    model: TubaModel,
    result_state: ResultState,
    analysis_mesh: AnalysisMesh | None,
) -> list[Overlay]:
    if analysis_mesh is None or not result_state.node_reactions:
        return []
    selected = set(result_state.metadata.get("compiler_inputs", {}).get("element_ids", ()))
    planes: dict[str, tuple[np.ndarray, np.ndarray, float]] = {}
    for support in model.supports:
        if support.type != "anchor" or support.node in planes:
            continue
        for element_id in selected:
            element = model.get_element(element_id)
            if element is None:
                continue
            other_id = element.n2 if element.n1 == support.node else element.n1 if element.n2 == support.node else None
            if other_id is None:
                continue
            origin = np.asarray(model.nodes[support.node].coords, dtype=float)
            inward = np.asarray(model.nodes[other_id].coords, dtype=float) - origin
            length = float(np.linalg.norm(inward))
            planes[support.node] = (origin, inward / length, max(length * 1.0e-7, 1.0e-9))
            break

    resultants: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for support_node, (origin, normal, tolerance) in planes.items():
        force = np.zeros(3)
        moment = np.zeros(3)
        for node_id, reaction in result_state.node_reactions.items():
            if node_id not in analysis_mesh.nodes or any(value is None for value in reaction[:3]):
                continue
            point = np.asarray(analysis_mesh.nodes[node_id], dtype=float)
            if abs(float(np.dot(point - origin, normal))) > tolerance:
                continue
            nodal_force = np.asarray(reaction[:3], dtype=float)
            if not np.isfinite(nodal_force).all():
                continue
            force += nodal_force
            moment += np.cross(point - origin, nodal_force)
        resultants[support_node] = (force, moment)

    overlays: list[Overlay] = []
    for result_type, index, value_key, magnitude_key, unit, label in (
        ("reaction_force", 0, "reaction_force_n", "magnitude_n", "N", "Reaction forces"),
        ("reaction_moment", 1, "reaction_moment_nm", "magnitude_nm", "N*m", "Reaction moments"),
    ):
        vectors: list[dict[str, Any]] = []
        values: dict[str, list[float]] = {}
        object_ids: list[str] = []
        for node_id, pair in resultants.items():
            vector = pair[index].tolist()
            magnitude = float(np.linalg.norm(pair[index]))
            if magnitude <= 0.0:
                continue
            node_object_ids = _object_ids_for_node(model, node_id)
            object_ids.extend(node_object_ids)
            start = _node_coords(model, node_id)
            values[node_id] = vector
            vectors.append(
                {
                    "node_id": node_id,
                    value_key: vector,
                    magnitude_key: magnitude,
                    "object_ids": node_object_ids,
                    "start": start,
                    "end": _vector_endpoint(start, vector),
                    "derivation": "sum of Code_Aster FORC_NODA over the anchored terminal",
                }
            )
        if not vectors:
            continue
        magnitudes = [float(np.linalg.norm(value)) for value in values.values()]
        overlays.append(
            Overlay(
                id=f"overlay:solver_result:{result_type}:{result_state.id}",
                kind="solver_result",
                object_ids=_dedupe(object_ids),
                name=f"{label} {result_state.load_case}",
                data={
                    "result_type": result_type,
                    "result_state_id": result_state.id,
                    "study_id": result_state.study_id,
                    "mesh_id": result_state.mesh_id,
                    "load_case": result_state.load_case,
                    "vectors": vectors,
                    "values": values,
                    "legend": {
                        "field": f"{result_type}_magnitude",
                        "unit": unit,
                        "range": {"min": min(magnitudes), "max": max(magnitudes)},
                        "color_map": "magma",
                        "thresholds": {},
                    },
                    "derivation": "terminal resultant from Code_Aster nodal reactions",
                },
            )
        )
    return overlays
def _result_state_parser_diagnostics_overlay(result_state: ResultState) -> Overlay | None:
    diagnostics = list(result_state.metadata.get("parser_diagnostics", []))
    if not diagnostics:
        return None
    return Overlay(
        id=f"overlay:solver_result:parser_diagnostics:{result_state.id}",
        kind="solver_result",
        name=f"Parser diagnostics {result_state.load_case}",
        data={
            "result_type": "parser_diagnostics",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "diagnostics": diagnostics,
        },
    )
def _result_state_tuyau_subpoint_scene(
    model: TubaModel,
    result_state: ResultState,
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay | None, list[SceneDiagnostic]]:
    tuyau_label = f"TUYAU FE VMIS (not code stress) {result_state.load_case}"
    tuyau_legend_field = "FE VMIS (not code stress)"
    tuyau_role = "visualization_only_not_asme_code_stress"
    rows = [dict(row) for row in result_state.metadata.get("tuyau_subpoints", []) if isinstance(row, dict)]
    if not rows:
        return [], [], None, []

    diagnostics: list[SceneDiagnostic] = []
    candidates: list[tuple[int, dict[str, Any], float, list[float]]] = []
    for row_index, row in enumerate(rows):
        value = _as_float(row.get("value"))
        point = _tuyau_subpoint_point(model, row)
        if value is None or point is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.tuyau_subpoint_missing_position",
                    message="Skipped TUYAU sub-point row without a numeric value or centerline position.",
                    target=str(row.get("element_id") or row.get("solver_element_label") or row_index),
                    source=result_state.id,
                )
            )
            continue
        candidates.append((row_index, row, value, point))

    if not candidates:
        return [], [], None, diagnostics

    state_key = _safe_id(result_state.id)
    object_id = f"object:tuyau_subpoints:{state_key}"
    asset_id = f"geometry:tuyau_subpoints:{state_key}"
    starts: list[list[float]] = []
    ends: list[list[float]] = []
    display_positions: list[list[float]] = []
    values: list[float] = []
    row_indices: list[int] = []
    element_ids: list[str] = []
    subpoint_indices: list[int | None] = []
    sector_indices: list[int | None] = []
    layer_indices: list[int | None] = []
    section_shapes: set[tuple[int, int]] = set()
    position_sources: set[str] = set()
    for row_index, row, value, point in candidates:
        glyph_points = _tuyau_subpoint_glyph_points(row, point)
        if glyph_points is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="result_state.tuyau_subpoint_missing_radial_position",
                    message="Skipped TUYAU sub-point row without a radial shell display position.",
                    target=str(row.get("element_id") or row.get("solver_element_label") or row_index),
                    source=result_state.id,
                )
            )
            continue
        element_id = str(row.get("element_id") or "")
        starts.append(glyph_points[0])
        ends.append(glyph_points[1])
        display_positions.append(point)
        values.append(value)
        row_indices.append(row_index)
        element_ids.append(element_id)
        subpoint_index = _as_int(row.get("subpoint_index"))
        nsec = _as_int(row.get("tuyau_nsec")) or CODE_ASTER_TUYAU_NSEC
        ncou = _as_int(row.get("tuyau_ncou")) or CODE_ASTER_TUYAU_NCOU
        section_shapes.add((nsec, ncou))
        station = None if subpoint_index is None else subpoint_station(subpoint_index, nsec=nsec, ncou=ncou)
        subpoint_indices.append(subpoint_index)
        sector_indices.append(None if station is None else station.sector_index)
        layer_indices.append(None if station is None else station.layer_index)
        position_sources.add(str(row.get("position_source", "centerline_from_sieq_elno")))

    if not starts:
        return [], [], None, diagnostics

    value_range = {"min": min(values), "max": max(values)}
    position_source = position_sources.pop() if len(position_sources) == 1 else "mixed"
    # Describe the sub-point grid only when every row agrees on it. A run that
    # mixed two TUYAU discretisations has no single rosette to draw, so the
    # viewer must omit the panel rather than pick one shape and imply it covers
    # the rest.
    profile = section_profile(*section_shapes.pop()) if len(section_shapes) == 1 else None
    peak = _tuyau_subpoint_peak(values, element_ids, subpoint_indices, sector_indices, layer_indices, profile)
    asset_bounds = _bounds_for_points([*starts, *ends], 0.006)
    object_metadata = {
        "result_state_id": result_state.id,
        "load_case": result_state.load_case,
        "field": "SIEQ_ELNO",
        "component": "VMIS",
        "unit": "Pa",
        "count": len(starts),
        "position_source": position_source,
        "source_file": result_state.files.get("tuyau_subpoints") or result_state.files.get("sieq"),
        "stress_basis": "Code_Aster SIEQ_ELNO VMIS TUYAU sub-point",
        "compliance_role": tuyau_role,
    }
    assets = [
        GeometryAsset(
            id=asset_id,
            format="tuyau_subpoint_glyphs",
            bounds=asset_bounds,
            object_ids=[object_id],
            generation_config={
                "source": "tuba.tuyau_subpoint_field",
                "radius_m": 0.006,
                "radial_segments": 8,
                "starts": starts,
                "ends": ends,
                "display_positions": display_positions,
                "values": values,
                "row_indices": row_indices,
                "element_ids": element_ids,
                "subpoint_indices": subpoint_indices,
                "sector_indices": sector_indices,
                "layer_indices": layer_indices,
                "result_state_id": result_state.id,
                "position_source": position_source,
                "range": value_range,
                "stress_basis": "Code_Aster SIEQ_ELNO VMIS TUYAU sub-point",
                "compliance_role": tuyau_role,
                "legend": {
                    "field": tuyau_legend_field,
                    "unit": "Pa",
                    "range": value_range,
                    "color_map": "turbo",
                    "thresholds": {},
                },
            },
        )
    ]
    objects = [
        SceneObject(
            id=object_id,
            kind="tuyau_subpoint_field",
            name=tuyau_label,
            geometry_asset_id=asset_id,
            layer_ids=["solver_result:tuyau_subpoints"],
            metadata=object_metadata,
            source={"code_aster_tuyau_subpoints": {"count": len(starts)}},
        )
    ]

    overlay = Overlay(
        id=f"overlay:solver_result:tuyau_subpoints:{result_state.id}",
        kind="solver_result",
        object_ids=[object_id],
        name=tuyau_label,
        data={
            "result_type": "tuyau_subpoints",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "field": "SIEQ_ELNO",
            "component": "VMIS",
            "unit": "Pa",
            "source_file": result_state.files.get("tuyau_subpoints") or result_state.files.get("sieq"),
            "position_source": position_source,
            "stress_basis": "Code_Aster SIEQ_ELNO VMIS TUYAU sub-point",
            "compliance_role": tuyau_role,
            "total_count": len(rows),
            "rendered_count": len(starts),
            "values": {object_id: max(values)},
            "range": value_range,
            "hotspots": _tuyau_subpoint_hotspots(
                object_id, row_indices, values, element_ids, subpoint_indices, sector_indices, layer_indices
            ),
            "legend": {
                "field": tuyau_legend_field,
                "unit": "Pa",
                "range": value_range,
                "color_map": "turbo",
                "thresholds": {},
            },
        },
    )
    if profile is not None:
        assets[0].generation_config["section_profile"] = profile
        overlay.data["section_profile"] = profile
    if peak is not None:
        overlay.data["peak"] = peak
    return objects, assets, overlay, diagnostics
def _tuyau_subpoint_hotspots(
    object_id: str,
    row_indices: list[int],
    values: list[float],
    element_ids: list[str],
    subpoint_indices: list[int | None],
    sector_indices: list[int | None],
    layer_indices: list[int | None],
) -> list[dict[str, Any]]:
    ranked = sorted(range(len(values)), key=lambda index: values[index], reverse=True)[:20]
    return [
        {
            "object_id": object_id,
            "row_index": row_indices[index],
            "element_id": element_ids[index],
            "subpoint_index": subpoint_indices[index],
            "sector_index": sector_indices[index],
            "layer_index": layer_indices[index],
            "value": values[index],
            "unit": "Pa",
        }
        for index in ranked
    ]
def _tuyau_subpoint_peak(
    values: list[float],
    element_ids: list[str],
    subpoint_indices: list[int | None],
    sector_indices: list[int | None],
    layer_indices: list[int | None],
    profile: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Where the largest sub-point value sits, decoded into a wall position.

    Only the two radial extremes get a name: the bore and the outer surface are
    identifiable without knowing how the pipe is bent, whereas calling a sector
    "intrados" would require an orientation the scene does not carry.
    """
    if not values:
        return None
    index = max(range(len(values)), key=lambda candidate: values[candidate])
    sector_index = sector_indices[index]
    layer_index = layer_indices[index]
    peak: dict[str, Any] = {
        "value": values[index],
        "unit": "Pa",
        "element_id": element_ids[index],
        "subpoint_index": subpoint_indices[index],
        "sector_index": sector_index,
        "layer_index": layer_index,
    }
    if profile is None:
        return peak
    if sector_index is not None:
        peak["angle_deg"] = 360.0 * sector_index / (2.0 * int(profile["nsec"]))
    if layer_index is not None:
        peak["wall_position"] = _tuyau_wall_position(layer_index, int(profile["layers"]))
    return peak
def _tuyau_wall_position(layer_index: int, layers: int) -> str:
    if layer_index <= 0:
        return "bore"
    if layer_index >= layers - 1:
        return "outer"
    return "mid_wall"
def _tuyau_subpoint_point(model: TubaModel, row: dict[str, Any]) -> list[float] | None:
    point = _coerce_point(row.get("display_position"))
    if point is not None:
        return point
    point = _coerce_point(row.get("centerline_position"))
    if point is not None:
        return point
    node_id = row.get("node_id")
    if isinstance(node_id, str) and node_id in model.nodes:
        return _node_coords(model, node_id)
    return None
def _tuyau_subpoint_glyph_points(row: dict[str, Any], point: list[float]) -> list[list[float]] | None:
    center = _coerce_point(row.get("centerline_position"))
    if center is None:
        return None
    center_arr = np.asarray(center, dtype=float)
    point_arr = np.asarray(point, dtype=float)
    radial = point_arr - center_arr
    norm = float(np.linalg.norm(radial))
    if norm <= 1.0e-12:
        return None
    start = center_arr + radial * 0.85
    end = center_arr + radial * 1.25
    return [[float(value) for value in start], [float(value) for value in end]]
def _result_state_element_result_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("forces_n1", "forces_n2"):
        if key in data:
            values = [_as_float(value) for value in data[key]]
            metadata[key] = [value if value is not None and np.isfinite(value) else None for value in values]
    for key in ("von_mises_n1", "von_mises_n2", "max_von_mises"):
        if key in data:
            value = float(data[key])
            if np.isfinite(value):
                metadata[key] = value
    metadata["force_unit"] = "N"
    metadata["moment_unit"] = "N*m"
    metadata["stress_unit"] = "Pa"
    return metadata
def _stress_hotspots(values: dict[str, float]) -> list[dict[str, Any]]:
    hotspots: list[dict[str, Any]] = []
    for object_id, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
        hotspot = {"object_id": object_id, "value": float(value), "unit": "Pa"}
        hotspots.append(hotspot)
    return hotspots[:10]
