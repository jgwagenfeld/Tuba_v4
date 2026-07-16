"""Shared leaf helpers and options for scene builders."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
from typing import Iterable
import numpy as np
from tuba.model import Element
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.clash.types import ClashResult
from tuba.load_path import LoadPathReport
from tuba.load_path import SupportRackAssociation
from tuba.patches import ModelPatch
from tuba.routing.types import PipeRouteCandidate
from tuba.routing.types import RouteSegment
from tuba.rules import RuleResult
from tuba.solver.base import FEAResults


@dataclass(frozen=True)
class SceneBuildOptions:
    include_elements: bool = True
    include_supports: bool = True
    include_obstacles: bool = True
    include_imported_components: bool = True
    include_physical: bool = True
    include_quantities: bool = True
    include_attributes: bool = True
    include_physical_envelopes: bool = False
    clearance_m: float = 0.0
    include_cost_overlays: bool = False
    cost_metric: str = "insulation_cost"
def _normalised_vector(values: Any) -> list[float] | None:
    vector = _numeric_triplet(values)
    if vector is None:
        return None
    arr = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        return None
    return [float(value) for value in (arr / norm).tolist()]
def _points_to_lists(points: Iterable[Iterable[float]]) -> list[list[float]]:
    return [[float(value) for value in point] for point in points]
def _coerce_point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return [float(part) for part in value]
    except (TypeError, ValueError):
        return None
def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
def _object_ids_for_node(model: TubaModel, node_id: str) -> list[str]:
    return [
        _object_id(EntityRef("element", elem.id))
        for elem in model.elements
        if elem.n1 == node_id or elem.n2 == node_id
    ]
def _element_kind(elem: Element) -> str:
    if elem.type.startswith("pipe"):
        return "pipe"
    if "beam" in elem.type or "rack" in elem.type:
        return "rack_member"
    return "element"
def _default_scene_id(model: TubaModel) -> str:
    project = getattr(model, "project_name", "tuba_model")
    return f"scene:{project}"
def _object_id(ref: EntityRef) -> str:
    return f"object:{ref}"
def _asset_id(ref: EntityRef) -> str:
    return f"geometry:{ref}"
def _route_candidate_ref(request_id: str, index: int) -> EntityRef:
    return EntityRef("route", f"{request_id}:candidate:{index}")
def _route_candidate_entity_id(request_id: str, index: int | None) -> str | None:
    if index is None:
        return None
    return str(_route_candidate_ref(request_id, index))
def _clash_issue_id(clash: ClashResult) -> str:
    return f"issue:clash:{clash.left.kind}:{clash.left.id}:{clash.right.kind}:{clash.right.id}"
def _rule_issue_id(result: RuleResult) -> str:
    refs = ":".join(f"{ref.kind}:{ref.id}" for ref in result.refs) or "model"
    return f"issue:rule:{result.rule_id}:{refs}"
def _proposal_patch(value: ModelPatch | dict[str, Any]) -> tuple[ModelPatch, dict[str, Any]]:
    if isinstance(value, ModelPatch):
        return value, value.to_dict()
    patch = ModelPatch.from_dict(dict(value))
    return patch, patch.to_dict()
def _normalize_ifc_guid_map(values: dict[str | EntityRef, str] | None) -> dict[str, str]:
    if not values:
        return {}
    return {str(key): guid for key, guid in values.items()}
def _ifc_source_for_ref(model: TubaModel, ref: EntityRef, ifc_guid_map: dict[str, str]) -> dict[str, Any]:
    attributes = model.get_attributes(ref)
    guid = ifc_guid_map.get(str(ref)) or attributes.get("ifc.guid")
    if not guid:
        return {}
    ifc_type = attributes.get("ifc.type") or _default_ifc_type_for_ref(model, ref)
    source = {
        "ifc": {
            "guid": guid,
            "property_sets": {
                "Pset_TubaIdentity": {
                    "EntityRef": str(ref),
                    "TubaKind": ref.kind,
                }
            },
        }
    }
    if ifc_type:
        source["ifc"]["type"] = ifc_type
        source["ifc"]["property_sets"]["Pset_TubaIdentity"]["IfcType"] = ifc_type
    tuba_attributes = {
        key: value
        for key, value in attributes.items()
        if not key.startswith("ifc.") and key != "insulation"
    }
    if tuba_attributes:
        source["ifc"]["property_sets"]["Pset_TubaAttributes"] = tuba_attributes
    if ref.kind == "element":
        insulation = model.get_insulation(ref)
        if insulation is not None:
            source["ifc"]["property_sets"]["Pset_TubaInsulation"] = {
                "InsulationSpec": insulation.id,
                "Material": insulation.material,
                "ThicknessM": float(insulation.thickness_m),
            }
    return source
def _default_ifc_type_for_ref(model: TubaModel, ref: EntityRef) -> str | None:
    if ref.kind == "element":
        try:
            elem = _find_element(model, ref.id)
        except KeyError:
            return None
        if elem.type == "beam":
            return "IfcBeam"
        if elem.type == "pipe_bend":
            return "IfcPipeFitting"
        if elem.type.startswith("pipe"):
            return "IfcPipeSegment"
    if ref.kind == "support":
        return "IfcMechanicalFastener"
    if ref.kind == "obstacle":
        return "IfcBuildingElementProxy"
    return None
def _find_element(model: TubaModel, element_id: str) -> Element:
    get_element = getattr(model, "get_element", None)
    if get_element is not None:
        element = get_element(element_id)
        if element is not None:
            return element
    for elem in model.elements:
        if elem.id == element_id:
            return elem
    raise KeyError(f"Unknown element {element_id!r}.")
def _groups_for_element(model: TubaModel, element_id: str) -> list[str]:
    groups: list[str] = []
    for group_id, group in model.groups.items():
        if element_id in group.get("elements", []):
            groups.append(group_id)
    return groups
def _element_points(model: TubaModel, elem: Element) -> list[list[float]]:
    return [_node_coords(model, elem.n1), _node_coords(model, elem.n2)]
def _node_coords(model: TubaModel, node_id: str) -> list[float]:
    return [float(value) for value in model.nodes[node_id].coords.tolist()]
def _numeric_triplet(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    triplet = [float(item) for item in value[:3]]
    if not all(np.isfinite(triplet)):
        return None
    return triplet
def _bounds_for_points(points: Iterable[Iterable[float]], padding: float) -> list[float]:
    arr = np.array(list(points), dtype=float)
    mins = arr.min(axis=0) - padding
    maxs = arr.max(axis=0) + padding
    return [float(value) for value in (*mins.tolist(), *maxs.tolist())]
def _safe_bounds_for_points(points: Iterable[Iterable[float]], padding: float) -> list[float]:
    values = list(points)
    if not values:
        return []
    return _bounds_for_points(values, padding)
def _route_points(candidate: PipeRouteCandidate) -> list[list[float]]:
    return [[float(value) for value in point] for point in candidate.points]
def _clash_location(clash: ClashResult) -> list[float]:
    if clash.location is None:
        return [0.0, 0.0, 0.0]
    return [float(value) for value in clash.location]
def _point_for_refs(model: TubaModel, refs: list[EntityRef]) -> list[float]:
    for ref in refs:
        if ref.kind == "element":
            for elem in model.elements:
                if elem.id == ref.id:
                    points = np.array(_element_points(model, elem), dtype=float)
                    center = points.mean(axis=0)
                    return [float(value) for value in center.tolist()]
        if ref.kind == "obstacle":
            for obstacle in model.obstacles:
                if obstacle.get("id") == ref.id:
                    bounds = _obstacle_bounds(obstacle)
                    if len(bounds) == 6:
                        return [
                            (bounds[0] + bounds[3]) / 2.0,
                            (bounds[1] + bounds[4]) / 2.0,
                            (bounds[2] + bounds[5]) / 2.0,
                        ]
        if ref.kind == "support":
            for support in model.supports:
                if support.id == ref.id:
                    return _node_coords(model, support.node)
    return [0.0, 0.0, 0.0]
def _deformed_element_points(
    model: TubaModel,
    results: FEAResults,
    elem: Element,
    deformation_scale: float,
) -> list[list[float]] | None:
    points: list[list[float]] = []
    for node_id in (elem.n1, elem.n2):
        node_result = results.node_results.get(node_id)
        if node_result is None:
            return None
        base = np.array(_node_coords(model, node_id), dtype=float)
        displacement = np.array(node_result.displacement[:3], dtype=float)
        point = base + displacement * float(deformation_scale)
        points.append([float(value) for value in point.tolist()])
    return points
def _support_point(model: TubaModel, support_id: str) -> list[float]:
    for support in model.supports:
        if support.id == support_id:
            return _node_coords(model, support.node)
    return [0.0, 0.0, 0.0]
def _reaction_for_association(report: LoadPathReport, association: SupportRackAssociation) -> list[float]:
    rack_load = report.rack_loads.get(association.rack.id, {})
    if rack_load.get("support_count") != 1:
        return [0.0, 0.0, 0.0]
    return [
        float(rack_load.get("force_x_n", 0.0)),
        float(rack_load.get("force_y_n", 0.0)),
        float(rack_load.get("force_z_n", 0.0)),
    ]
def _vector_endpoint(start: list[float], vector: list[float]) -> list[float]:
    max_component = max((abs(value) for value in vector), default=0.0)
    if max_component <= 0.0:
        return list(start)
    scale = 1.0 / max_component
    return [float(start[index] + vector[index] * scale) for index in range(3)]
def _clash_envelope_source(model: TubaModel, clash: ClashResult) -> dict[str, Any]:
    for ref in (clash.left, clash.right):
        if ref.kind != "element":
            continue
        insulation = model.get_insulation(ref)
        if insulation is not None:
            return {
                "type": "insulation",
                "entity_ref": str(ref),
                "insulation_id": insulation.id,
                "material": insulation.material,
                "thickness_m": float(insulation.thickness_m),
            }
    return {"type": "bare_geometry"}
def _issue_severity_for_clash(clash: ClashResult) -> str:
    if clash.severity == "hard" or str(clash.severity).endswith("_hard"):
        return "error"
    return "warning"
def _route_segment_to_dict(segment: RouteSegment) -> dict[str, Any]:
    data = asdict(segment)
    data["start"] = [float(value) for value in segment.start]
    data["end"] = [float(value) for value in segment.end]
    return data
def _route_candidate_summary(
    candidate: PipeRouteCandidate,
    index: int,
    candidate_id: str,
    selected: bool,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "index": index,
        "selected": selected,
        "is_valid": candidate.is_valid,
        "cost": float(candidate.cost),
        "cost_breakdown": dict(candidate.cost_breakdown),
        "diagnostics": list(candidate.diagnostics),
        "point_count": len(candidate.points),
        "segment_count": len(candidate.segments),
        "length_m": _candidate_length(candidate),
        "metadata": dict(candidate.metadata),
    }
def _route_cost_terms(candidate: PipeRouteCandidate | None) -> list[dict[str, Any]]:
    if candidate is None:
        return []
    return [
        {
            "name": name,
            "total": float(total),
            "unit": "cost",
        }
        for name, total in candidate.cost_breakdown.items()
    ]
def _candidate_length(candidate: PipeRouteCandidate) -> float:
    if "length" in candidate.cost_breakdown:
        return float(candidate.cost_breakdown["length"])
    total = 0.0
    for start, end in zip(candidate.points, candidate.points[1:]):
        start_arr = np.array(start, dtype=float)
        end_arr = np.array(end, dtype=float)
        total += float(np.linalg.norm(end_arr - start_arr))
    return total
def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
def _transform_bounds(bounds: list[float], transform: dict[str, Any]) -> list[float]:
    if len(bounds) != 6:
        return []
    translation = transform.get("translation", [0.0, 0.0, 0.0])
    if len(translation) != 3:
        translation = [0.0, 0.0, 0.0]
    return [
        float(bounds[0] + translation[0]),
        float(bounds[1] + translation[1]),
        float(bounds[2] + translation[2]),
        float(bounds[3] + translation[0]),
        float(bounds[4] + translation[1]),
        float(bounds[5] + translation[2]),
    ]
def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_.-" else "_" for char in value)
def _obstacle_bounds(obstacle: dict[str, Any]) -> list[float]:
    if "min_point" in obstacle and "max_point" in obstacle:
        return [float(value) for value in (*obstacle["min_point"], *obstacle["max_point"])]
    if "center" in obstacle and "radius" in obstacle:
        center = np.array(obstacle["center"], dtype=float)
        radius = float(obstacle["radius"])
        mins = center - radius
        maxs = center + radius
        return [float(value) for value in (*mins.tolist(), *maxs.tolist())]
    return []
