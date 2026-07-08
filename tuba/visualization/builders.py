"""Builders that project Tuba model state into semantic visualization scenes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

import numpy as np

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.projection import project_deformed_centerline
from tuba.model import Element, TubaModel
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.geometry.deformed import build_deformed_envelopes
from tuba.physical import element_quantities, physical_properties_for_element
from tuba.quantities import quantity_takeoff
from tuba.refs import EntityRef
from tuba.clash.types import ClashResult
from tuba.load_path import LoadPathReport, SupportRackAssociation
from tuba.patches import ModelPatch, ModelTransaction
from tuba.routing.types import PipeRouteCandidate, PipeRouteResult, RouteSegment
from tuba.rules import RuleResult
from tuba.solver.base import FEAResults
from tuba.visualization.scene import (
    AgentProposal,
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneDiff,
    SceneObject,
    ViewState,
    VisualizationScene,
)

@dataclass(frozen=True)
class SceneBuildOptions:
    include_elements: bool = True
    include_supports: bool = True
    include_obstacles: bool = True
    include_physical: bool = True
    include_quantities: bool = True
    include_attributes: bool = True
    include_physical_envelopes: bool = False
    clearance_m: float = 0.0
    include_cost_overlays: bool = False
    cost_metric: str = "insulation_cost"


def build_visualization_scene(
    model: TubaModel,
    *,
    options: SceneBuildOptions | None = None,
    route_results: Iterable[PipeRouteResult] | None = None,
    clash_results: Iterable[ClashResult] | None = None,
    operating_clash_results: Iterable[ClashResult] | None = None,
    rule_results: Iterable[RuleResult] | None = None,
    load_path_report: LoadPathReport | None = None,
    solver_results: FEAResults | None = None,
    result_states: Iterable[ResultState] | None = None,
    geometry_states: Iterable[GeometryState] | None = None,
    analysis_meshes: Iterable[AnalysisMesh] | None = None,
    result_deformation_scale: float = 50.0,
    agent_proposals: Iterable[AgentProposal | dict[str, Any]] | None = None,
    ifc_guid_map: dict[str | EntityRef, str] | None = None,
    ifc_context: dict[str, Any] | None = None,
    external_sources: Iterable[dict[str, Any]] | None = None,
    point_clouds: Iterable[dict[str, Any]] | None = None,
    field_notes: Iterable[dict[str, Any]] | None = None,
    runtime_states: Iterable[dict[str, Any]] | None = None,
    scene_id: str | None = None,
    model_id: str | None = None,
    created_at: str | None = None,
) -> VisualizationScene:
    """Build a semantic scene manifest from a Tuba model."""
    opts = options or SceneBuildOptions()
    resolved_scene_id = scene_id or _default_scene_id(model)
    resolved_ifc_guid_map = _normalize_ifc_guid_map(ifc_guid_map)
    result_state_records = list(result_states or [])
    geometry_state_records = list(geometry_states or [])
    analysis_mesh_records = list(analysis_meshes or [])
    diagnostics: list[SceneDiagnostic] = []
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []
    issues: list[Issue] = []
    route_reviews: list[RouteReview] = []
    proposal_records: list[AgentProposal] = []
    scene_diffs: list[SceneDiff] = []
    views: list[ViewState] = []

    if opts.include_elements:
        for elem in model.elements:
            scene_object, asset, object_diagnostics, envelope_objects, envelope_assets, envelope_overlays = (
                _build_element_object(model, elem, opts, resolved_ifc_guid_map)
            )
            objects.append(scene_object)
            assets.append(asset)
            diagnostics.extend(object_diagnostics)
            objects.extend(envelope_objects)
            assets.extend(envelope_assets)
            overlays.extend(envelope_overlays)

    if opts.include_supports:
        for support in model.supports:
            scene_object, asset = _build_support_object(model, support)
            objects.append(scene_object)
            assets.append(asset)

    if opts.include_obstacles:
        for obstacle in model.obstacles:
            scene_object, asset = _build_obstacle_object(obstacle)
            objects.append(scene_object)
            assets.append(asset)

    for route_result in route_results or []:
        route_objects, route_assets, overlay, review = _build_route_result_scene(route_result)
        objects.extend(route_objects)
        assets.extend(route_assets)
        overlays.append(overlay)
        route_reviews.append(review)

    for clash in clash_results or []:
        marker_object, marker_asset, overlay, issue, view = _build_clash_issue_scene(model, clash)
        objects.append(marker_object)
        assets.append(marker_asset)
        overlays.append(overlay)
        issues.append(issue)
        views.append(view)

    for clash in operating_clash_results or []:
        marker_object, marker_asset, overlay, issue, view = _build_clash_issue_scene(model, clash)
        objects.append(marker_object)
        assets.append(marker_asset)
        overlays.append(overlay)
        issues.append(issue)
        views.append(view)

    for result_state in result_state_records:
        state_object, state_overlay = _build_result_state_record(result_state)
        objects.append(state_object)
        overlays.append(state_overlay)
        result_objects, result_assets, result_overlays, result_diagnostics = _build_result_state_result_scene(
            model,
            result_state,
        )
        objects.extend(result_objects)
        assets.extend(result_assets)
        overlays.extend(result_overlays)
        diagnostics.extend(result_diagnostics)

    for geometry_state in geometry_state_records:
        state_object, state_overlay = _build_geometry_state_record(geometry_state)
        objects.append(state_object)
        overlays.append(state_overlay)

    for analysis_mesh in analysis_mesh_records:
        mesh_objects, mesh_assets, mesh_diagnostics = _build_analysis_mesh_scene(analysis_mesh)
        objects.extend(mesh_objects)
        assets.extend(mesh_assets)
        diagnostics.extend(mesh_diagnostics)

    deformed_objects, deformed_assets, deformed_diagnostics = _build_deformed_state_scene(
        model,
        result_state_records,
        geometry_state_records,
        analysis_mesh_records,
    )
    objects.extend(deformed_objects)
    assets.extend(deformed_assets)
    diagnostics.extend(deformed_diagnostics)

    for result in rule_results or []:
        marker_object, marker_asset, overlay, issue, view = _build_rule_issue_scene(model, result)
        objects.append(marker_object)
        assets.append(marker_asset)
        overlays.append(overlay)
        issues.append(issue)
        views.append(view)

    if load_path_report is not None:
        rack_overlays, load_objects, load_assets, load_overlays, load_issues = _build_load_path_scene(
            model,
            load_path_report,
        )
        overlays.extend(rack_overlays)
        objects.extend(load_objects)
        assets.extend(load_assets)
        overlays.extend(load_overlays)
        issues.extend(load_issues)

    if solver_results is not None:
        result_objects, result_assets, result_overlays = _build_solver_result_scene(
            model,
            solver_results,
            result_deformation_scale,
        )
        objects.extend(result_objects)
        assets.extend(result_assets)
        overlays.extend(result_overlays)

    if opts.include_cost_overlays:
        overlays.extend(_build_cost_quantity_overlays(model, opts.cost_metric))

    for proposal_payload in agent_proposals or []:
        proposal, diff, proposal_objects, proposal_assets, proposal_overlay = _build_agent_proposal_preview(
            model,
            proposal_payload,
            opts,
            resolved_scene_id,
        )
        proposal_records.append(proposal)
        scene_diffs.append(diff)
        objects.extend(proposal_objects)
        assets.extend(proposal_assets)
        overlays.append(proposal_overlay)

    for external_source in external_sources or []:
        external_objects, external_assets, external_overlay = _build_external_source_scene(external_source)
        objects.extend(external_objects)
        assets.extend(external_assets)
        overlays.append(external_overlay)

    if point_clouds or field_notes:
        field_objects, field_assets, field_overlay = _build_field_context_scene(point_clouds or [], field_notes or [])
        objects.extend(field_objects)
        assets.extend(field_assets)
        overlays.append(field_overlay)

    if runtime_states:
        overlays.append(_build_runtime_state_overlay(runtime_states))

    scene = VisualizationScene(
        scene_id=resolved_scene_id,
        model_id=model_id or getattr(model, "project_name", "tuba_model"),
        created_at=created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        units={"length": "m", "mass": "kg"},
        coordinate_system={"up_axis": "Z"},
        objects=objects,
        geometry_assets=assets,
        overlays=overlays,
        issues=issues,
        route_reviews=route_reviews,
        agent_proposals=proposal_records,
        views=views,
        scene_diffs=scene_diffs,
        diagnostics=diagnostics,
        extra={"ifc_context": dict(ifc_context)} if ifc_context else {},
    )
    scene.validate()
    return scene


def _build_element_object(
    model: TubaModel,
    elem: Element,
    options: SceneBuildOptions,
    ifc_guid_map: dict[str, str] | None = None,
) -> tuple[SceneObject, GeometryAsset, list[SceneDiagnostic], list[SceneObject], list[GeometryAsset], list[Overlay]]:
    diagnostics: list[SceneDiagnostic] = []
    entity_ref = EntityRef("element", elem.id)
    asset_id = _asset_id(entity_ref)
    metadata: dict[str, Any] = {
        "element_type": elem.type,
        "section": elem.section,
        "material": elem.material,
        "nodes": [elem.n1, elem.n2],
        "groups": _groups_for_element(model, elem.id),
    }
    if elem.bend_geometry is not None:
        metadata["bend_geometry"] = elem.bend_geometry.to_dict()

    if options.include_attributes:
        attributes = model.get_attributes(entity_ref)
        if attributes:
            metadata["attributes"] = attributes
        insulation = model.get_insulation(entity_ref)
        if insulation is not None:
            metadata["insulation"] = {"id": insulation.id, **insulation.to_dict()}

    physical: dict[str, Any] = {}
    if options.include_physical:
        try:
            physical = asdict(physical_properties_for_element(model, elem))
        except Exception as exc:  # pragma: no cover - diagnostic path
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    message=f"Could not compute physical properties for element {elem.id!r}: {exc}",
                    target=str(entity_ref),
                )
            )

    quantities: dict[str, Any] = {}
    if options.include_quantities:
        try:
            quantities = asdict(element_quantities(model, elem))
        except Exception as exc:  # pragma: no cover - diagnostic path
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    message=f"Could not compute quantities for element {elem.id!r}: {exc}",
                    target=str(entity_ref),
                )
            )

    points = _element_points(model, elem)
    radius = float(physical.get("effective_radius_m") or physical.get("bare_radius_m") or 0.0)
    asset = GeometryAsset(
        id=asset_id,
        format="tube" if elem.type.startswith("pipe") else "line",
        bounds=_bounds_for_points(points, radius),
        object_ids=[_object_id(entity_ref)],
        generation_config={
            "source": "tuba.element",
            "entity_ref": str(entity_ref),
            "points": points,
            "radius_m": radius,
        },
    )
    scene_object = SceneObject(
        id=_object_id(entity_ref),
        entity_ref=entity_ref,
        kind=_element_kind(elem),
        name=elem.id,
        geometry_asset_id=asset_id,
        group_ids=metadata["groups"],
        metadata=metadata,
        quantities=quantities,
        physical=physical,
        source=_ifc_source_for_ref(model, entity_ref, ifc_guid_map or {}),
    )
    envelope_objects: list[SceneObject] = []
    envelope_assets: list[GeometryAsset] = []
    envelope_overlays: list[Overlay] = []
    if options.include_physical_envelopes and elem.type.startswith("pipe"):
        envelope_objects, envelope_assets, envelope_overlays = _build_physical_envelopes(
            elem=elem,
            entity_ref=entity_ref,
            points=points,
            physical=physical,
            clearance_m=options.clearance_m,
        )
    return scene_object, asset, diagnostics, envelope_objects, envelope_assets, envelope_overlays


def _build_physical_envelopes(
    *,
    elem: Element,
    entity_ref: EntityRef,
    points: list[list[float]],
    physical: dict[str, Any],
    clearance_m: float,
) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay]]:
    envelope_specs = _physical_envelope_specs(elem, physical, clearance_m)
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []
    for spec in envelope_specs:
        envelope_type = spec["envelope_type"]
        object_id = f"object:physical_envelope:{entity_ref}:{envelope_type}"
        asset_id = f"geometry:physical_envelope:{entity_ref}:{envelope_type}"
        overlay_id = f"overlay:physical_envelope:{entity_ref}:{envelope_type}"
        radius = float(spec["radius_m"])
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="tube_envelope",
                bounds=_bounds_for_points(points, radius),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.physical_envelope",
                    "entity_ref": str(entity_ref),
                    "envelope_type": envelope_type,
                    "points": points,
                    "radius_m": radius,
                    "source_data": spec["source"],
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="physical_envelope",
                name=f"{elem.id} {envelope_type} envelope",
                geometry_asset_id=asset_id,
                layer_ids=[f"physical_envelope:{envelope_type}"],
                metadata={
                    "entity_ref": str(entity_ref),
                    "envelope_type": envelope_type,
                    "radius_m": radius,
                    "diameter_m": radius * 2.0,
                    "source": spec["source"],
                },
            )
        )
        overlays.append(
            Overlay(
                id=overlay_id,
                kind="physical_envelope",
                object_ids=[object_id],
                entity_refs=[entity_ref],
                name=f"{elem.id} {envelope_type}",
                data={
                    "entity_ref": str(entity_ref),
                    "envelope_type": envelope_type,
                    "radius_m": radius,
                    "source": spec["source"],
                },
            )
        )
    return objects, assets, overlays


def _build_support_object(model: TubaModel, support) -> tuple[SceneObject, GeometryAsset]:
    entity_ref = EntityRef("support", support.id)
    coords = _node_coords(model, support.node)
    asset = GeometryAsset(
        id=_asset_id(entity_ref),
        format="point",
        bounds=_bounds_for_points([coords], 0.0),
        object_ids=[_object_id(entity_ref)],
        generation_config={"source": "tuba.support", "entity_ref": str(entity_ref), "point": coords},
    )
    scene_object = SceneObject(
        id=_object_id(entity_ref),
        entity_ref=entity_ref,
        kind="support",
        name=support.id,
        geometry_asset_id=asset.id,
        metadata={"support_type": support.type, "node": support.node},
    )
    return scene_object, asset


def _build_obstacle_object(obstacle: dict[str, Any]) -> tuple[SceneObject, GeometryAsset]:
    entity_ref = EntityRef("obstacle", obstacle["id"])
    bounds = _obstacle_bounds(obstacle)
    asset = GeometryAsset(
        id=_asset_id(entity_ref),
        format=obstacle.get("type", "obstacle"),
        bounds=bounds,
        object_ids=[_object_id(entity_ref)],
        generation_config={"source": "tuba.obstacle", "entity_ref": str(entity_ref), "obstacle": dict(obstacle)},
    )
    scene_object = SceneObject(
        id=_object_id(entity_ref),
        entity_ref=entity_ref,
        kind="obstacle",
        name=obstacle["id"],
        geometry_asset_id=asset.id,
        metadata=dict(obstacle),
    )
    return scene_object, asset


def _mesh_group_layer_ids(groups: list[str]) -> list[str]:
    if not groups:
        return []
    return ["analysis_mesh:groups", *(f"analysis_mesh:group:{group}" for group in groups)]


def _build_deformed_element_scene(
    *,
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None,
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    state_key = _safe_id(geometry_state.id)
    mode = _deformed_state_mode(geometry_state)
    centerline_layer = f"deformed:{mode}_centerline"
    envelope_layer = f"deformed:{mode}_envelope"

    for element in model.elements:
        try:
            projected = project_deformed_centerline(
                model=model,
                element=element,
                result_state=result_state,
                geometry_state=geometry_state,
                analysis_mesh=analysis_mesh,
            )
        except KeyError as exc:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="deformed_state.projection_failed",
                    message=str(exc),
                    target=str(EntityRef("element", element.id)),
                    source=geometry_state.id,
                )
            )
            continue

        points = _points_to_lists(projected.points)
        entity_ref = EntityRef("element", element.id)
        object_id = f"object:deformed_centerline:{state_key}:{element.id}"
        asset_id = f"geometry:deformed_centerline:{state_key}:{element.id}"
        metadata = _deformed_state_metadata(geometry_state, result_state)
        metadata.update(
            {
                "element_id": element.id,
                "source_mesh_nodes": list(projected.source_mesh_nodes),
                "diagnostics": list(projected.diagnostics),
            }
        )
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_centerline",
                    "entity_ref": str(entity_ref),
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "visual_scale": geometry_state.displacement_scale,
                    "points": points,
                    "source_mesh_nodes": list(projected.source_mesh_nodes),
                    "diagnostics": list(projected.diagnostics),
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=entity_ref,
                kind="deformed_centerline",
                name=f"{element.id} {mode} deformed centerline",
                geometry_asset_id=asset_id,
                layer_ids=[centerline_layer],
                metadata=metadata,
                source={"tuba_deformed_centerline": {"geometry_state_id": geometry_state.id, "result_state_id": result_state.id}},
            )
        )

    try:
        envelopes = build_deformed_envelopes(
            model=model,
            result_state=result_state,
            geometry_state=geometry_state,
            envelope_type="insulation",
            analysis_mesh=analysis_mesh,
        )
    except ValueError as exc:
        diagnostics.append(
            SceneDiagnostic(
                severity="warning",
                code="deformed_state.envelope_failed",
                message=str(exc),
                target=geometry_state.id,
                source=geometry_state.id,
            )
        )
        envelopes = ()

    for envelope in envelopes:
        entity_ref = envelope.entity
        object_id = f"object:deformed_envelope:{state_key}:{entity_ref.id}"
        asset_id = f"geometry:deformed_envelope:{state_key}:{entity_ref.id}"
        points = _points_to_lists(envelope.polyline)
        metadata = _deformed_state_metadata(geometry_state, result_state)
        metadata.update(
            {
                "element_id": entity_ref.id,
                "envelope_type": envelope.envelope_type,
                "radius_m": envelope.radius_m,
                "source_mesh_nodes": list(envelope.source_mesh_nodes),
                "diagnostics": list(envelope.diagnostics),
            }
        )
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="tube_envelope",
                bounds=list(envelope.bounds),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_envelope",
                    "entity_ref": str(entity_ref),
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "envelope_type": envelope.envelope_type,
                    "visual_scale": geometry_state.displacement_scale,
                    "points": points,
                    "radius_m": envelope.radius_m,
                    "source_mesh_nodes": list(envelope.source_mesh_nodes),
                    "diagnostics": list(envelope.diagnostics),
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=entity_ref,
                kind="deformed_envelope",
                name=f"{entity_ref.id} {mode} deformed envelope",
                geometry_asset_id=asset_id,
                layer_ids=[envelope_layer],
                metadata=metadata,
                source={"tuba_deformed_envelope": {"geometry_state_id": geometry_state.id, "result_state_id": result_state.id}},
            )
        )

    return objects, assets, diagnostics


def _build_deformed_analysis_mesh_scene(
    *,
    analysis_mesh: AnalysisMesh,
    result_state: ResultState,
    geometry_state: GeometryState,
) -> tuple[list[SceneObject], list[GeometryAsset]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    state_key = _safe_id(geometry_state.id)
    mesh_key = _safe_id(analysis_mesh.id)
    groups_by_member = _mesh_groups_by_member(analysis_mesh.groups)
    factor = geometry_state.displacement_scale * geometry_state.safety_factor

    for element_id, node_ids in analysis_mesh.elements.items():
        source = analysis_mesh.element_sources.get(element_id)
        source_ref = source.source_ref if source is not None else None
        groups = groups_by_member.get(element_id, [])
        points = [
            _deformed_mesh_node_point(analysis_mesh, result_state, node_id, factor)
            for node_id in node_ids
        ]
        object_id = f"object:deformed_analysis_mesh:{state_key}:{mesh_key}:element:{element_id}"
        asset_id = f"geometry:deformed_analysis_mesh:{state_key}:{mesh_key}:element:{element_id}"
        metadata = _deformed_state_metadata(geometry_state, result_state)
        metadata.update(
            {
                "mesh_id": analysis_mesh.id,
                "element_id": element_id,
                "node_ids": list(node_ids),
                "role": source.role if source is not None else "unmapped_element",
                "groups": groups,
            }
        )
        if source_ref is not None:
            metadata["source_ref"] = str(source_ref)
        if source is not None and source.segment_index is not None:
            metadata["segment_index"] = int(source.segment_index)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.deformed_analysis_mesh.element",
                    "mesh_id": analysis_mesh.id,
                    "element_id": element_id,
                    "geometry_state_id": geometry_state.id,
                    "result_state_id": result_state.id,
                    "load_case": geometry_state.load_case,
                    "visual_scale": geometry_state.displacement_scale,
                    "points": points,
                    "node_ids": list(node_ids),
                    "source_ref": str(source_ref) if source_ref is not None else None,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=source_ref,
                kind="deformed_analysis_mesh_element",
                name=f"{analysis_mesh.id} {element_id} deformed",
                geometry_asset_id=asset_id,
                layer_ids=["deformed:mesh", *_mesh_group_layer_ids(groups)],
                metadata=metadata,
                source={"tuba_deformed_analysis_mesh": {"mesh_id": analysis_mesh.id, "geometry_state_id": geometry_state.id}},
            )
        )

    return objects, assets


def _deformed_mesh_node_point(
    analysis_mesh: AnalysisMesh,
    result_state: ResultState,
    node_id: str,
    factor: float,
) -> list[float]:
    base = np.asarray(analysis_mesh.nodes[node_id], dtype=float)
    displacement = np.asarray(result_state.node_displacements.get(node_id, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float)
    return [float(value) for value in (base + displacement[:3] * factor).tolist()]


def _deformed_state_mode(geometry_state: GeometryState) -> str:
    if geometry_state.purpose == "visualization" or geometry_state.state_type == "deformed":
        return "visual"
    return "physical"


def _deformed_state_metadata(geometry_state: GeometryState, result_state: ResultState) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "geometry_state_id": geometry_state.id,
        "result_state_id": result_state.id,
        "load_case": geometry_state.load_case,
        "state_type": geometry_state.state_type,
        "purpose": geometry_state.purpose,
        "displacement_scale": geometry_state.displacement_scale,
        "safety_factor": geometry_state.safety_factor,
        "visual_scale": geometry_state.displacement_scale,
    }
    return metadata


def _points_to_lists(points: Iterable[Iterable[float]]) -> list[list[float]]:
    return [[float(value) for value in point] for point in points]


def _physical_envelope_specs(elem: Element, physical: dict[str, Any], clearance_m: float) -> list[dict[str, Any]]:
    bare_radius = float(physical.get("bare_radius_m") or 0.0)
    effective_radius = float(physical.get("effective_radius_m") or bare_radius)
    wind_radius = float(physical.get("wind_diameter_m") or effective_radius * 2.0) / 2.0
    specs: list[dict[str, Any]] = [
        {
            "envelope_type": "bare_pipe",
            "radius_m": bare_radius,
            "source": {
                "type": "section",
                "section": elem.section,
                "field": "bare_radius_m",
            },
        }
    ]
    if physical.get("insulation_spec_id"):
        specs.append(
            {
                "envelope_type": "insulation",
                "radius_m": effective_radius,
                "source": {
                    "type": "insulation",
                    "insulation_id": physical["insulation_spec_id"],
                    "thickness_m": float(physical.get("insulation_thickness_m") or 0.0),
                    "field": "effective_radius_m",
                },
            }
        )
    if clearance_m > 0.0:
        specs.append(
            {
                "envelope_type": "clearance",
                "radius_m": effective_radius + float(clearance_m),
                "source": {
                    "type": "clearance",
                    "base_radius_m": effective_radius,
                    "clearance_m": float(clearance_m),
                },
            }
        )
    specs.append(
        {
            "envelope_type": "wind",
            "radius_m": wind_radius,
            "source": {
                "type": "wind",
                "field": "wind_diameter_m",
                "wind_diameter_m": float(physical.get("wind_diameter_m") or wind_radius * 2.0),
            },
        }
    )
    return specs


def _build_route_result_scene(
    result: PipeRouteResult,
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay, RouteReview]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    candidate_summaries: list[dict[str, Any]] = []
    request_ref = EntityRef("route", result.request.id)
    selected_candidate_id = _route_candidate_entity_id(result.request.id, result.selected_index)

    for index, candidate in enumerate(result.candidates):
        entity_ref = _route_candidate_ref(result.request.id, index)
        object_id = _object_id(entity_ref)
        asset_id = _asset_id(entity_ref)
        candidate_id = str(entity_ref)
        selected = candidate_id == selected_candidate_id
        points = _route_points(candidate)

        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_safe_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.route_candidate",
                    "entity_ref": candidate_id,
                    "request_id": result.request.id,
                    "candidate_index": index,
                    "points": points,
                    "segments": [_route_segment_to_dict(segment) for segment in candidate.segments],
                    "selected": selected,
                    "is_valid": candidate.is_valid,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=entity_ref,
                kind="route_candidate",
                name=f"{result.request.id} candidate {index}",
                geometry_asset_id=asset_id,
                metadata={
                    "request_id": result.request.id,
                    "candidate_index": index,
                    "selected": selected,
                    "is_valid": candidate.is_valid,
                    "cost": float(candidate.cost),
                    "cost_breakdown": dict(candidate.cost_breakdown),
                    "diagnostics": list(candidate.diagnostics),
                    "section": result.request.section,
                    "material": result.request.material,
                    "route_metadata": dict(candidate.metadata),
                },
                quantities={
                    "point_count": len(candidate.points),
                    "segment_count": len(candidate.segments),
                    "length_m": _candidate_length(candidate),
                },
            )
        )
        candidate_summaries.append(_route_candidate_summary(candidate, index, candidate_id, selected))

    overlay = Overlay(
        id=f"overlay:route:{result.request.id}:alternatives",
        kind="route_alternatives",
        object_ids=[obj.id for obj in objects],
        entity_refs=[request_ref],
        name=f"{result.request.id} alternatives",
        data={
            "request_id": result.request.id,
            "selected_candidate_id": selected_candidate_id,
            "diagnostics": list(result.diagnostics),
            "candidate_count": len(result.candidates),
        },
    )
    review = RouteReview(
        request_id=result.request.id,
        selected_candidate_id=selected_candidate_id,
        candidates=candidate_summaries,
        cost_terms=_route_cost_terms(result.selected),
        diagnostics=[
            SceneDiagnostic(severity="warning", message=message, target=str(request_ref))
            for message in result.diagnostics
        ],
    )
    return objects, assets, overlay, review


def _build_clash_issue_scene(
    model: TubaModel,
    clash: ClashResult,
) -> tuple[SceneObject, GeometryAsset, Overlay, Issue, ViewState]:
    issue_id = _clash_issue_id(clash)
    marker_id = f"object:{issue_id}"
    marker_asset_id = f"geometry:{issue_id}"
    involved_object_ids = [_object_id(clash.left), _object_id(clash.right)]
    point = _clash_location(clash)
    envelope_source = _clash_envelope_source(model, clash)
    review = _clash_review_payload(clash, involved_object_ids)
    overlay_id = f"overlay:clash:{issue_id}"
    view_id = f"view:{issue_id}"

    marker_asset = GeometryAsset(
        id=marker_asset_id,
        format="point",
        bounds=_bounds_for_points([point], 0.0),
        object_ids=[marker_id],
        generation_config={
            "source": "tuba.clash",
            "issue_id": issue_id,
            "point": point,
            "clash": clash.to_dict(),
        },
    )
    marker_object = SceneObject(
        id=marker_id,
        kind="clash_marker",
        name=f"Clash {clash.left} vs {clash.right}",
        geometry_asset_id=marker_asset_id,
        metadata={
            "issue_id": issue_id,
            "left": str(clash.left),
            "right": str(clash.right),
            "severity": clash.severity,
            "distance_m": float(clash.distance_m),
            "penetration_m": float(clash.penetration_m),
            "diagnostics": list(clash.diagnostics),
            "envelope_source": envelope_source,
            "clash_metadata": dict(clash.metadata),
            "review": review,
        },
    )
    overlay = Overlay(
        id=overlay_id,
        kind="clash",
        object_ids=[*involved_object_ids, marker_id],
        entity_refs=[clash.left, clash.right],
        name=f"Clash {clash.left} vs {clash.right}",
        data={
            "issue_ids": [issue_id],
            "severity": clash.severity,
            "distance_m": float(clash.distance_m),
            "penetration_m": float(clash.penetration_m),
            "metadata": dict(clash.metadata),
            **review,
        },
    )
    issue = Issue(
        id=issue_id,
        type="clash",
        title=f"{clash.left} clashes with {clash.right}",
        description=(
            f"{clash.severity} clash with penetration {clash.penetration_m:.6g} m "
            f"and distance {clash.distance_m:.6g} m."
        ),
        severity=_issue_severity_for_clash(clash),
        status="open",
        entity_refs=[clash.left, clash.right],
        view_id=view_id,
        source_report_id="clash",
        external_refs={
            "bcf": {
                "topic_type": "Clash",
                "topic_status": "Open",
                "related_entity_refs": [str(clash.left), str(clash.right)],
                "labels": ["tuba", "clash", clash.severity],
            },
            "clash": clash.to_dict(),
            "clash_review": {
                "focus_object_ids": [*involved_object_ids, marker_id],
                "grouping": dict(review["grouping"]),
                "object_pair": list(review["object_pair"]),
            },
        },
    )
    view = ViewState(
        id=view_id,
        name=issue.title,
        camera={"mode": "orbit", "target": point, "distance": 2.0},
        selected_object_ids=[*involved_object_ids, marker_id],
        active_overlay_ids=[overlay_id],
        issue_id=issue_id,
    )
    return marker_object, marker_asset, overlay, issue, view


def _clash_review_payload(clash: ClashResult, involved_object_ids: list[str]) -> dict[str, Any]:
    metadata = dict(clash.metadata)
    object_pair = [str(clash.left), str(clash.right)]
    load_case = metadata.get("load_case")
    geometry_state = metadata.get("geometry_state")
    result_state_id = metadata.get("result_state_id")
    envelope_type = metadata.get("envelope_type")
    grouping = {
        "severity": clash.severity,
        "load_case": load_case,
        "geometry_state": geometry_state,
        "result_state_id": result_state_id,
        "envelope_type": envelope_type,
        "object_pair": object_pair,
    }
    return {
        "object_pair": object_pair,
        "involved_object_ids": list(involved_object_ids),
        "cold_distance_m": metadata.get("cold_distance_m"),
        "operating_distance_m": metadata.get("operating_distance_m"),
        "penetration_m": float(clash.penetration_m),
        "load_case": load_case,
        "geometry_state": geometry_state,
        "result_state_id": result_state_id,
        "envelope_type": envelope_type,
        "introduced_by_deformation": bool(metadata.get("introduced_by_deformation", False)),
        "grouping": grouping,
    }


def _build_rule_issue_scene(
    model: TubaModel,
    result: RuleResult,
) -> tuple[SceneObject, GeometryAsset, Overlay, Issue, ViewState]:
    issue_id = _rule_issue_id(result)
    marker_id = f"object:{issue_id}"
    marker_asset_id = f"geometry:{issue_id}"
    involved_object_ids = [_object_id(ref) for ref in result.refs]
    point = _point_for_refs(model, result.refs)
    overlay_id = f"overlay:rule:{issue_id}"
    view_id = f"view:{issue_id}"

    marker_asset = GeometryAsset(
        id=marker_asset_id,
        format="point",
        bounds=_bounds_for_points([point], 0.0),
        object_ids=[marker_id],
        generation_config={
            "source": "tuba.rule",
            "issue_id": issue_id,
            "point": point,
            "rule_result": result.to_dict(),
        },
    )
    marker_object = SceneObject(
        id=marker_id,
        kind="rule_marker",
        name=f"Rule {result.rule_id}",
        geometry_asset_id=marker_asset_id,
        metadata={
            "issue_id": issue_id,
            "rule_id": result.rule_id,
            "passed": result.passed,
            "severity": result.severity,
            "message": result.message,
            "rule_data": dict(result.data),
        },
    )
    overlay = Overlay(
        id=overlay_id,
        kind="rule_violation",
        object_ids=[*involved_object_ids, marker_id],
        entity_refs=list(result.refs),
        name=f"Rule {result.rule_id}",
        data={
            "issue_ids": [issue_id],
            "rule_id": result.rule_id,
            "passed": result.passed,
            "severity": result.severity,
            "rule_data": dict(result.data),
        },
    )
    issue = Issue(
        id=issue_id,
        type="rule",
        title=f"{result.rule_id}: {result.message}",
        description=result.message,
        severity=result.severity,
        status="open" if not result.passed else "closed",
        entity_refs=list(result.refs),
        view_id=view_id,
        source_report_id="rules",
        external_refs={"rule": result.to_dict()},
    )
    view = ViewState(
        id=view_id,
        name=issue.title,
        camera={"mode": "orbit", "target": point, "distance": 2.0},
        selected_object_ids=[*involved_object_ids, marker_id],
        active_overlay_ids=[overlay_id],
        issue_id=issue_id,
    )
    return marker_object, marker_asset, overlay, issue, view


def _build_cost_quantity_overlays(model: TubaModel, metric: str) -> list[Overlay]:
    takeoff = quantity_takeoff(model)
    values: dict[str, float] = {}
    object_ids: list[str] = []
    entity_refs: list[EntityRef] = []
    for record in takeoff.records:
        record_data = record.to_dict()
        raw_value = record_data.get(metric, 0.0)
        object_id = _object_id(record.element)
        object_ids.append(object_id)
        entity_refs.append(record.element)
        values[object_id] = float(raw_value)
    numeric_values = list(values.values())
    value_range = {
        "min": min(numeric_values) if numeric_values else 0.0,
        "max": max(numeric_values) if numeric_values else 0.0,
    }
    return [
        Overlay(
            id=f"overlay:cost_heatmap:{metric}",
            kind="cost_heatmap",
            object_ids=object_ids,
            entity_refs=entity_refs,
            name=f"{metric} heatmap",
            data={
                "metric": metric,
                "values": values,
                "range": value_range,
                "record_count": len(takeoff.records),
            },
        ),
        Overlay(
            id="overlay:quantity_summary",
            kind="quantity_summary",
            object_ids=object_ids,
            entity_refs=entity_refs,
            name="Quantity summary",
            data={
                "totals": dict(takeoff.totals),
                "groups": {name: dict(values) for name, values in takeoff.groups.items()},
                "record_count": len(takeoff.records),
            },
        ),
    ]


def _build_load_path_scene(
    model: TubaModel,
    report: LoadPathReport,
) -> tuple[list[Overlay], list[SceneObject], list[GeometryAsset], list[Overlay], list[Issue]]:
    rack_overlays = _build_rack_assembly_overlays(model)
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    load_object_ids: list[str] = []
    association_payloads: list[dict[str, Any]] = []

    for association in report.associations:
        vector_object, vector_asset = _build_load_path_vector(model, report, association)
        objects.append(vector_object)
        assets.append(vector_asset)
        load_object_ids.extend([_object_id(association.support), vector_object.id])
        association_payloads.append(association.to_dict())

    load_overlays: list[Overlay] = []
    if report.associations or report.rack_loads:
        load_overlays.append(
            Overlay(
                id="overlay:load_path",
                kind="load_path",
                object_ids=_dedupe(load_object_ids),
                entity_refs=[association.support for association in report.associations],
                name="Load paths",
                data={
                    "associations": association_payloads,
                    "rack_loads": {rack: dict(loads) for rack, loads in report.rack_loads.items()},
                    "diagnostics": list(report.diagnostics),
                },
            )
        )

    issues = [
        Issue(
            id=f"issue:load_path:diagnostic:{index}",
            type="load_path",
            title="Load path diagnostic",
            description=diagnostic,
            severity="warning",
            status="open",
            source_report_id="load_path",
            external_refs={"load_path": {"diagnostic": diagnostic}},
        )
        for index, diagnostic in enumerate(report.diagnostics)
    ]
    return rack_overlays, objects, assets, load_overlays, issues


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
    payload = result_state.to_dict()
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


def _build_result_state_result_scene(
    model: TubaModel,
    result_state: ResultState,
) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []
    diagnostics: list[SceneDiagnostic] = []

    stress_overlay = _result_state_stress_overlay(model, result_state, diagnostics)
    if stress_overlay is not None:
        overlays.append(stress_overlay)

    displacement_overlay = _result_state_displacement_overlay(model, result_state, diagnostics)
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
                "legend": {
                    "field": "VMIS",
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
            name=f"TUYAU sub-points {result_state.load_case}",
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
        name=f"TUYAU sub-points {result_state.load_case}",
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
            "total_count": len(rows),
            "rendered_count": len(starts),
            "values": {object_id: max(values)},
            "range": value_range,
            "hotspots": _tuyau_subpoint_hotspots(object_id, row_indices, values, element_ids, subpoint_indices),
            "legend": {
                "field": "VMIS",
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


def _result_state_element_result_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("forces_n1", "forces_n2"):
        if key in data:
            metadata[key] = [float(value) for value in data[key]]
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
    load_case_data = model.load_cases.get(load_case)
    temperature = float(getattr(load_case_data, "temperature", 20.0)) if load_case_data is not None else 20.0
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


def _object_ids_for_node(model: TubaModel, node_id: str) -> list[str]:
    return [
        _object_id(EntityRef("element", elem.id))
        for elem in model.elements
        if elem.n1 == node_id or elem.n2 == node_id
    ]


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
        mesh_objects, mesh_assets = _build_deformed_mesh_scene(result_state, geometry_state, analysis_mesh)
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
    for element_id, node_ids in analysis_mesh.elements.items():
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
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="polyline",
                bounds=_safe_bounds_for_points(points, 0.0),
                object_ids=[object_id],
                generation_config={
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
                },
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

    for node_id, coords in analysis_mesh.nodes.items():
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


def _build_agent_proposal_preview(
    model: TubaModel,
    payload: AgentProposal | dict[str, Any],
    options: SceneBuildOptions,
    base_scene_id: str,
) -> tuple[AgentProposal, SceneDiff, list[SceneObject], list[GeometryAsset], Overlay]:
    proposal_data = payload.to_dict() if isinstance(payload, AgentProposal) else dict(payload)
    patch_obj, patch_dict = _proposal_patch(proposal_data["model_patch"])
    preview_model = TubaModel.from_dict(model.to_dict())
    result = ModelTransaction(preview_model).apply(patch_obj)
    created_refs = [EntityRef("element", element_id) for element_id in result.element_ids.values()]

    added_objects: list[SceneObject] = []
    added_assets: list[GeometryAsset] = []
    for element_id in result.element_ids.values():
        elem = _find_element(preview_model, element_id)
        scene_object, asset, _diagnostics, _envelope_objects, _envelope_assets, _envelope_overlays = _build_element_object(
            preview_model,
            elem,
            options,
            {},
        )
        scene_object.metadata = {"proposal_state": "added", "base_kind": scene_object.kind, **scene_object.metadata}
        scene_object.kind = "proposal_added"
        added_objects.append(scene_object)
        added_assets.append(asset)

    proposal = AgentProposal(
        proposal_id=proposal_data["proposal_id"],
        agent_id=proposal_data["agent_id"],
        goal=proposal_data["goal"],
        rationale=proposal_data["rationale"],
        model_patch=patch_dict,
        before_metrics=dict(proposal_data.get("before_metrics", {})),
        after_metrics={
            "created_element_count": len(result.element_ids),
            "created_node_count": len(result.node_ids),
            **dict(proposal_data.get("after_metrics", {})),
        },
        changed_entity_refs=list(proposal_data.get("changed_entity_refs", [])),
        created_entity_refs=created_refs,
        removed_entity_refs=list(proposal_data.get("removed_entity_refs", [])),
        risks=list(proposal_data.get("risks", [])),
        approval_state=proposal_data.get("approval_state", "pending"),
        review_comments=list(proposal_data.get("review_comments", [])),
    )
    diff = SceneDiff(
        diff_id=f"diff:proposal:{proposal.proposal_id}",
        base_scene_id=base_scene_id,
        added_objects=added_objects,
        added_geometry_assets=added_assets,
    )
    overlay = Overlay(
        id=f"overlay:agent_proposal:{proposal.proposal_id}",
        kind="agent_proposal",
        object_ids=[obj.id for obj in added_objects],
        entity_refs=created_refs,
        name=f"Proposal {proposal.proposal_id}",
        data={
            "proposal_id": proposal.proposal_id,
            "agent_id": proposal.agent_id,
            "approval_state": proposal.approval_state,
            "created_entity_refs": [str(ref) for ref in created_refs],
        },
    )
    return proposal, diff, added_objects, added_assets, overlay


def _build_external_source_scene(source: dict[str, Any]) -> tuple[list[SceneObject], list[GeometryAsset], Overlay]:
    source_id = str(source["source_id"])
    transform = dict(source.get("transform", {}))
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    for item in source.get("objects", []):
        item_id = str(item["id"])
        object_id = f"object:external:{_safe_id(source_id)}:{_safe_id(item_id)}"
        asset_id = f"geometry:external:{_safe_id(source_id)}:{_safe_id(item_id)}"
        bounds = _transform_bounds(item.get("bounds", []), transform)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format=item.get("format", "external_bounds"),
                bounds=bounds,
                object_ids=[object_id],
                generation_config={
                    "source": "external",
                    "source_id": source_id,
                    "source_type": source.get("source_type", "external"),
                    "external_object_id": item_id,
                    "transform": transform,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="external_context",
                name=item.get("name", item_id),
                geometry_asset_id=asset_id,
                metadata={
                    "external_object_id": item_id,
                    "external_kind": item.get("kind", "object"),
                    **dict(item.get("metadata", {})),
                },
                source={
                    "external": {
                        "source_id": source_id,
                        "source_type": source.get("source_type", "external"),
                        "object_id": item_id,
                        "transform": transform,
                    }
                },
            )
        )
    overlay = Overlay(
        id=f"overlay:external_source:{_safe_id(source_id)}",
        kind="external_source",
        object_ids=[obj.id for obj in objects],
        name=source.get("name", source_id),
        data={
            "source_id": source_id,
            "source_type": source.get("source_type", "external"),
            "transform": transform,
            "object_count": len(objects),
        },
    )
    return objects, assets, overlay


def _build_field_context_scene(
    point_clouds: Iterable[dict[str, Any]],
    field_notes: Iterable[dict[str, Any]],
) -> tuple[list[SceneObject], list[GeometryAsset], Overlay]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    for cloud in point_clouds:
        cloud_id = str(cloud["id"])
        object_id = f"object:point_cloud:{_safe_id(cloud_id)}"
        asset_id = f"geometry:point_cloud:{_safe_id(cloud_id)}"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="point_cloud",
                uri=cloud.get("uri", ""),
                bounds=[float(value) for value in cloud.get("bounds", [])],
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.field_context",
                    "point_cloud_id": cloud_id,
                    "point_count": int(cloud.get("point_count", 0)),
                    "metadata": dict(cloud.get("source", {})),
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="point_cloud",
                name=cloud.get("name", cloud_id),
                geometry_asset_id=asset_id,
                metadata={
                    "point_cloud_id": cloud_id,
                    "point_count": int(cloud.get("point_count", 0)),
                    "source": dict(cloud.get("source", {})),
                },
            )
        )
    for note in field_notes:
        note_id = str(note["id"])
        point = [float(value) for value in note.get("position", [0.0, 0.0, 0.0])]
        object_id = f"object:field_note:{_safe_id(note_id)}"
        asset_id = f"geometry:field_note:{_safe_id(note_id)}"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="point",
                bounds=_bounds_for_points([point], 0.0),
                object_ids=[object_id],
                generation_config={"source": "tuba.field_note", "field_note_id": note_id, "point": point},
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                kind="field_note",
                name=note.get("title", note_id),
                geometry_asset_id=asset_id,
                metadata={
                    "field_note_id": note_id,
                    "text": note.get("text", ""),
                    "position": point,
                    "entity_refs": list(note.get("entity_refs", [])),
                },
            )
        )
    overlay = Overlay(
        id="overlay:field_context",
        kind="field_context",
        object_ids=[obj.id for obj in objects],
        name="Field context",
        data={"point_cloud_count": len([obj for obj in objects if obj.kind == "point_cloud"]), "field_note_count": len([obj for obj in objects if obj.kind == "field_note"])},
    )
    return objects, assets, overlay


def _build_runtime_state_overlay(runtime_states: Iterable[dict[str, Any]]) -> Overlay:
    timestamps: list[str] = []
    states_by_time: dict[str, dict[str, Any]] = {}
    object_ids: list[str] = []
    for state in runtime_states:
        timestamp = str(state["timestamp"])
        timestamps.append(timestamp)
        object_states: dict[str, Any] = {}
        for ref_text, values in state.get("states", {}).items():
            try:
                object_id = _object_id(EntityRef.parse(ref_text))
            except ValueError:
                object_id = f"object:{ref_text}"
            object_states[object_id] = dict(values)
            object_ids.append(object_id)
        states_by_time[timestamp] = object_states
    return Overlay(
        id="overlay:runtime_state",
        kind="runtime_state",
        object_ids=_dedupe(object_ids),
        name="Runtime state",
        data={
            "timestamps": timestamps,
            "states": states_by_time,
        },
    )


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
    load_case_data = model.load_cases.get(load_case)
    if load_case_data is None:
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


def _build_rack_assembly_overlays(model: TubaModel) -> list[Overlay]:
    overlays: list[Overlay] = []
    for group_name, group in model.groups.items():
        metadata = group.get("metadata", {})
        if metadata.get("assembly_type") != "rack_bay":
            continue
        object_ids = [_object_id(EntityRef("element", element_id)) for element_id in group.get("elements", [])]
        data = {
            "rack_id": group_name,
            "assembly_type": metadata.get("assembly_type"),
            "levels": list(metadata.get("levels", [])),
            "attachment_points": dict(metadata.get("attachment_points", {})),
        }
        if metadata.get("zone") is not None:
            data["zone"] = metadata["zone"]
        overlays.append(
            Overlay(
                id=f"overlay:rack_assembly:{group_name}",
                kind="rack_assembly",
                object_ids=object_ids,
                entity_refs=[EntityRef("group", group_name)],
                name=f"Rack {group_name}",
                data=data,
            )
        )
    return overlays


def _build_load_path_vector(
    model: TubaModel,
    report: LoadPathReport,
    association: SupportRackAssociation,
) -> tuple[SceneObject, GeometryAsset]:
    reaction = _reaction_for_association(report, association)
    start = _support_point(model, association.support.id)
    end = _vector_endpoint(start, reaction)
    object_id = f"object:load_path:{association.support.id}:{association.rack.id}"
    asset_id = f"geometry:load_path:{association.support.id}:{association.rack.id}"
    asset = GeometryAsset(
        id=asset_id,
        format="vector",
        bounds=_bounds_for_points([start, end], 0.0),
        object_ids=[object_id],
        generation_config={
            "source": "tuba.load_path",
            "start": start,
            "end": end,
            "reaction_vector_n": reaction,
            "association": association.to_dict(),
        },
    )
    obj = SceneObject(
        id=object_id,
        kind="load_path_vector",
        name=f"{association.support.id} to {association.rack.id}",
        geometry_asset_id=asset_id,
        metadata={
            "support_id": association.support.id,
            "rack_id": association.rack.id,
            "node_id": association.node.id,
            "attachment_point": association.attachment_point,
            "reaction_n": reaction,
        },
    )
    return obj, asset


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
