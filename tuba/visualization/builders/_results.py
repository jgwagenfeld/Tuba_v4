"""Solver-result and result-state scene/overlay builders."""

from __future__ import annotations
from typing import Any
import numpy as np
from tuba.analysis.mesh import AnalysisMesh
from tuba.model import Element
from tuba.model import TubaModel
from tuba.analysis.results import ResultState
from tuba.refs import EntityRef
from tuba.solver.base import FEAResults
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._helpers import _as_float, _as_int, _bounds_for_points, _coerce_point, _dedupe, _deformed_element_points, _element_points, _node_coords, _numeric_triplet, _object_id, _object_ids_for_node, _safe_id, _vector_endpoint


def _build_solver_result_scene(
    model: TubaModel,
    results: FEAResults,
    deformation_scale: float,
) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []
    load_case = results.load_case or "default"

    deformed_object_ids: list[str] = []
    for elem in model.elements:
        if elem.id not in results.element_results:
            continue
        deformed = _deformed_element_points(model, results, elem, deformation_scale)
        if deformed is None:
            continue
        base_points = _element_points(model, elem)
        object_id = f"object:solver_result:deformed:{load_case}:{elem.id}"
        asset_id = f"geometry:solver_result:deformed:{load_case}:{elem.id}"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_bounds_for_points(deformed, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.solver_results",
                    "result_type": "deformed_shape",
                    "load_case": load_case,
                    "element_id": elem.id,
                    "deformation_scale": float(deformation_scale),
                    "base_points": base_points,
                    "points": deformed,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="deformed_result",
                name=f"{elem.id} deformed {load_case}",
                geometry_asset_id=asset_id,
                metadata={
                    "result_type": "deformed_shape",
                    "load_case": load_case,
                    "element_id": elem.id,
                    "deformation_scale": float(deformation_scale),
                },
            )
        )
        deformed_object_ids.append(object_id)

    if deformed_object_ids:
        overlays.append(
            Overlay(
                id=f"overlay:solver_result:deformed:{load_case}",
                kind="solver_result",
                object_ids=deformed_object_ids,
                name=f"Deformed shape {load_case}",
                data={"result_type": "deformed_shape", "load_case": load_case, "deformation_scale": float(deformation_scale)},
            )
        )

    stress_overlay = _solver_stress_overlay(results, load_case)
    if stress_overlay is not None:
        overlays.append(stress_overlay)

    reaction_objects, reaction_assets, reaction_overlay = _solver_reaction_vectors(model, results, load_case)
    objects.extend(reaction_objects)
    assets.extend(reaction_assets)
    if reaction_overlay is not None:
        overlays.append(reaction_overlay)

    temperature_overlay = _solver_temperature_overlay(model, results, load_case)
    if temperature_overlay is not None:
        overlays.append(temperature_overlay)

    return objects, assets, overlays
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

    stress_overlay = _result_state_stress_overlay(model, result_state, diagnostics)
    if stress_overlay is not None:
        overlays.append(stress_overlay)

    displacement_overlay = _result_state_displacement_overlay(model, result_state, analysis_mesh, diagnostics)
    if displacement_overlay is not None:
        displacement_objects, displacement_assets = _result_state_vector_scene(result_state, displacement_overlay)
        objects.extend(displacement_objects)
        assets.extend(displacement_assets)
        overlays.append(displacement_overlay)

    reaction_overlay = _result_state_reaction_overlay(model, result_state)
    if reaction_overlay is not None:
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
def _result_state_vector_scene(
    result_state: ResultState,
    overlay: Overlay,
) -> tuple[list[SceneObject], list[GeometryAsset]]:
    result_type = str(overlay.data.get("result_type", ""))
    if result_type not in {"displacement", "reaction"}:
        return [], []
    kind = f"{result_type}_vector"
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
            "color": "#dc2626" if result_type == "reaction" else "#7c3aed",
        }
        if result_type == "reaction":
            generation_config["reaction_force_n"] = list(vector.get("reaction_force_n", []))
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
                name=f"{node_id} {result_type} {result_state.load_case}",
                geometry_asset_id=asset_id,
                layer_ids=[f"result:{result_type}"],
                metadata={
                    "result_type": result_type,
                    "result_state_id": result_state.id,
                    "load_case": result_state.load_case,
                    "node_id": node_id,
                    "magnitude": vector.get(f"magnitude_{'n' if result_type == 'reaction' else 'm'}"),
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
    utilization_values: dict[str, float] = {}
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
        values[object_id] = value
        object_ids.append(object_id)
        entity_refs.append(EntityRef("element", elem.id))
        element_metadata[object_id] = _result_state_element_result_metadata(data)
        allowable = _allowable_stress_for_element(model, elem, result_state.load_case)
        if allowable is not None and allowable > 0.0:
            utilization_values[object_id] = value / allowable

    if not values:
        return None
    numeric_values = list(values.values())
    hotspots = _stress_hotspots(values, utilization_values)
    return Overlay(
        id=f"overlay:solver_result:stress:{result_state.id}",
        kind="solver_result",
        object_ids=object_ids,
        entity_refs=entity_refs,
        name=f"Stress {result_state.load_case}",
        data={
            "result_type": "stress",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "field": "max_von_mises",
            "values": values,
            "utilization_values": utilization_values,
            "range": {"min": min(numeric_values), "max": max(numeric_values)},
            "unit": "Pa",
            "legend": {
                "field": "max_von_mises",
                "unit": "Pa",
                "range": {"min": min(numeric_values), "max": max(numeric_values)},
                "color_map": "turbo",
                "thresholds": {"warning": 0.8, "critical": 1.0},
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
    values: dict[str, float] = {}
    object_ids: list[str] = []
    for node_id, displacement in result_state.node_displacements.items():
        vector = [float(value) for value in displacement[:3]]
        magnitude = float(np.linalg.norm(vector))
        values[node_id] = magnitude
        node_object_ids = _object_ids_for_node(model, node_id)
        object_ids.extend(node_object_ids)
        entry: dict[str, Any] = {
            "node_id": node_id,
            "displacement_m": vector,
            "rotation_rad": [float(value) for value in displacement[3:6]],
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
    numeric_values = list(values.values())
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
def _result_state_reaction_overlay(model: TubaModel, result_state: ResultState) -> Overlay | None:
    vectors: list[dict[str, Any]] = []
    values: dict[str, float] = {}
    object_ids: list[str] = []
    for node_id, reaction in result_state.node_reactions.items():
        vector = [float(value) for value in reaction[:3]]
        magnitude = float(np.linalg.norm(vector))
        if magnitude <= 0.0:
            continue
        values[node_id] = magnitude
        node_object_ids = _object_ids_for_node(model, node_id)
        object_ids.extend(node_object_ids)
        entry: dict[str, Any] = {
            "node_id": node_id,
            "reaction_force_n": vector,
            "reaction_moment_nm": [float(value) for value in reaction[3:6]],
            "magnitude_n": magnitude,
            "object_ids": node_object_ids,
        }
        if node_id in model.nodes:
            entry["start"] = _node_coords(model, node_id)
            entry["end"] = _vector_endpoint(entry["start"], vector)
        vectors.append(entry)

    if not vectors:
        return None
    numeric_values = list(values.values())
    return Overlay(
        id=f"overlay:solver_result:reaction:{result_state.id}",
        kind="solver_result",
        object_ids=_dedupe(object_ids),
        name=f"Reactions {result_state.load_case}",
        data={
            "result_type": "reaction",
            "result_state_id": result_state.id,
            "study_id": result_state.study_id,
            "mesh_id": result_state.mesh_id,
            "load_case": result_state.load_case,
            "vectors": vectors,
            "values": values,
            "legend": {
                "field": "reaction_force_magnitude",
                "unit": "N",
                "range": {"min": min(numeric_values), "max": max(numeric_values)},
                "color_map": "magma",
                "thresholds": {},
            },
        },
    )
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
        subpoint_indices.append(_as_int(row.get("subpoint_index")))
        position_sources.add(str(row.get("position_source", "centerline_from_sieq_elno")))

    if not starts:
        return [], [], None, diagnostics

    value_range = {"min": min(values), "max": max(values)}
    position_source = position_sources.pop() if len(position_sources) == 1 else "mixed"
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
            "hotspots": _tuyau_subpoint_hotspots(object_id, row_indices, values, element_ids, subpoint_indices),
            "legend": {
                "field": tuyau_legend_field,
                "unit": "Pa",
                "range": value_range,
                "color_map": "turbo",
                "thresholds": {},
            },
        },
    )
    return objects, assets, overlay, diagnostics
def _tuyau_subpoint_hotspots(
    object_id: str,
    row_indices: list[int],
    values: list[float],
    element_ids: list[str],
    subpoint_indices: list[int | None],
) -> list[dict[str, Any]]:
    ranked = sorted(range(len(values)), key=lambda index: values[index], reverse=True)[:20]
    return [
        {
            "object_id": object_id,
            "row_index": row_indices[index],
            "element_id": element_ids[index],
            "subpoint_index": subpoint_indices[index],
            "value": values[index],
            "unit": "Pa",
        }
        for index in ranked
    ]
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
            metadata[key] = float(data[key])
    metadata["force_unit"] = "N"
    metadata["moment_unit"] = "N*m"
    metadata["stress_unit"] = "Pa"
    return metadata
def _allowable_stress_for_element(model: TubaModel, elem: Element, load_case: str) -> float | None:
    material = model.materials.get(elem.material)
    if material is None:
        return None
    try:
        _, load_case_data = model.resolve_load_case(load_case)
    except ValueError:
        return None
    temperature = float(load_case_data.temperature)
    try:
        return float(material.get_allowable(temperature))
    except ValueError:
        return None
def _stress_hotspots(values: dict[str, float], utilization_values: dict[str, float]) -> list[dict[str, Any]]:
    hotspots: list[dict[str, Any]] = []
    for object_id, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
        hotspot = {"object_id": object_id, "value": float(value), "unit": "Pa"}
        if object_id in utilization_values:
            hotspot["utilization"] = float(utilization_values[object_id])
        hotspots.append(hotspot)
    return hotspots[:10]
def _solver_stress_overlay(results: FEAResults, load_case: str) -> Overlay | None:
    values: dict[str, float] = {}
    object_ids: list[str] = []
    for element_id, result in results.element_results.items():
        object_id = _object_id(EntityRef("element", element_id))
        object_ids.append(object_id)
        values[object_id] = float(result.max_von_mises)
    if not values:
        return None
    numeric_values = list(values.values())
    return Overlay(
        id=f"overlay:solver_result:stress:{load_case}",
        kind="solver_result",
        object_ids=object_ids,
        entity_refs=[EntityRef("element", element_id) for element_id in results.element_results],
        name=f"Stress {load_case}",
        data={
            "result_type": "stress",
            "load_case": load_case,
            "field": "max_von_mises",
            "values": values,
            "range": {"min": min(numeric_values), "max": max(numeric_values)},
            "unit": "Pa",
        },
    )
def _solver_reaction_vectors(
    model: TubaModel,
    results: FEAResults,
    load_case: str,
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay | None]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    object_ids: list[str] = []
    values: dict[str, list[float]] = {}
    for node_id, result in results.node_results.items():
        if result.reaction_force is None:
            continue
        reaction = [float(value) for value in result.reaction_force[:3].tolist()]
        if max((abs(value) for value in reaction), default=0.0) <= 0.0:
            continue
        start = _node_coords(model, node_id)
        end = _vector_endpoint(start, reaction)
        object_id = f"object:solver_result:reaction:{load_case}:{node_id}"
        asset_id = f"geometry:solver_result:reaction:{load_case}:{node_id}"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="vector",
                bounds=_bounds_for_points([start, end], 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.solver_results",
                    "result_type": "reaction",
                    "load_case": load_case,
                    "node_id": node_id,
                    "start": start,
                    "end": end,
                    "reaction_force_n": reaction,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="reaction_vector",
                name=f"{node_id} reaction {load_case}",
                geometry_asset_id=asset_id,
                layer_ids=["result:reaction"],
                metadata={"result_type": "reaction", "load_case": load_case, "node_id": node_id, "reaction_force_n": reaction},
            )
        )
        object_ids.append(object_id)
        values[node_id] = reaction
    if not object_ids:
        return objects, assets, None
    return (
        objects,
        assets,
        Overlay(
            id=f"overlay:solver_result:reaction:{load_case}",
            kind="solver_result",
            object_ids=object_ids,
            name=f"Reactions {load_case}",
            data={"result_type": "reaction", "load_case": load_case, "values": values, "unit": "N"},
        ),
    )
def _solver_temperature_overlay(model: TubaModel, results: FEAResults, load_case: str) -> Overlay | None:
    try:
        _, load_case_data = model.resolve_load_case(load_case)
    except ValueError:
        return None
    object_ids = [_object_id(EntityRef("element", elem.id)) for elem in model.elements]
    return Overlay(
        id=f"overlay:solver_result:temperature:{load_case}",
        kind="solver_result",
        object_ids=object_ids,
        entity_refs=[EntityRef("element", elem.id) for elem in model.elements],
        name=f"Temperature {load_case}",
        data={
            "result_type": "temperature",
            "load_case": load_case,
            "temperature_c": float(load_case_data.temperature),
            "values": {object_id: float(load_case_data.temperature) for object_id in object_ids},
            "unit": "C",
        },
    )
