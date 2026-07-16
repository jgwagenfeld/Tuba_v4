"""Review scene builders: routes, clashes, rules, costs, proposals."""

from __future__ import annotations
from typing import Any
from typing import Iterable
from tuba.model import TubaModel
from tuba.quantities import quantity_takeoff
from tuba.refs import EntityRef
from tuba.clash.types import ClashResult
from tuba.load_path import LoadPathReport
from tuba.load_path import SupportRackAssociation
from tuba.patches import ModelTransaction
from tuba.routing.types import PipeRouteResult
from tuba.rules import RuleResult
from tuba.visualization.scene import AgentProposal
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Issue
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import RouteReview
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneDiff
from tuba.visualization.scene import SceneObject
from tuba.visualization.scene import ViewState
from tuba.visualization.builders._helpers import SceneBuildOptions, _asset_id, _bounds_for_points, _candidate_length, _clash_envelope_source, _clash_issue_id, _clash_location, _dedupe, _find_element, _issue_severity_for_clash, _object_id, _point_for_refs, _proposal_patch, _reaction_for_association, _route_candidate_entity_id, _route_candidate_ref, _route_candidate_summary, _route_cost_terms, _route_points, _route_segment_to_dict, _rule_issue_id, _safe_bounds_for_points, _safe_id, _support_point, _transform_bounds, _vector_endpoint
from tuba.visualization.builders._objects import _build_element_object


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
