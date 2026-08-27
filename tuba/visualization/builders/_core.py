"""Scene orchestrator: build_visualization_scene."""

from __future__ import annotations
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Iterable
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.run import AnalysisRun
from tuba.model import TubaModel
from tuba.analysis.results import ResultState
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)
from tuba.analysis.states import GeometryState
from tuba.refs import EntityRef
from tuba.clash.types import ClashResult
from tuba.load_path import LoadPathReport
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
from tuba.visualization.scene import VisualizationScene
from tuba.visualization.builders._helpers import SceneBuildOptions, _default_scene_id, _normalize_ifc_guid_map
from tuba.visualization.builders._objects import _build_element_object, _build_obstacle_object, _build_support_object
from tuba.visualization.builders._imported import _build_imported_component_scene
from tuba.visualization.builders._layers import build_layer_registry, build_result_fields
from tuba.visualization.builders._loads import build_load_scene
from tuba.visualization.builders._states import _build_analysis_mesh_scene, _build_deformed_state_scene, _build_geometry_state_record
from tuba.visualization.builders._results import _build_result_state_record, _build_result_state_result_scene
from tuba.visualization.builders._review import _build_agent_proposal_preview, _build_clash_issue_scene, _build_cost_quantity_overlays, _build_external_source_scene, _build_field_context_scene, _build_load_path_scene, _build_route_result_scene, _build_rule_issue_scene, _build_runtime_state_overlay


def build_visualization_scene(
    model: TubaModel,
    *,
    options: SceneBuildOptions | None = None,
    route_results: Iterable[PipeRouteResult] | None = None,
    clash_results: Iterable[ClashResult] | None = None,
    operating_clash_results: Iterable[ClashResult] | None = None,
    rule_results: Iterable[RuleResult] | None = None,
    load_path_report: LoadPathReport | None = None,
    analysis_runs: Iterable[AnalysisRun] = (),
    result_states: Iterable[ResultState] | None = None,
    geometry_states: Iterable[GeometryState] | None = None,
    analysis_meshes: Iterable[AnalysisMesh] | None = None,
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
    analysis_run_records = tuple(analysis_runs)
    result_state_records = list(result_states or [])
    geometry_state_records = list(geometry_states or [])
    analysis_mesh_records = list(analysis_meshes or [])
    if analysis_run_records:
        if result_state_records or analysis_mesh_records:
            raise ValueError(
                "analysis_runs cannot be mixed with lower-level result_states or analysis_meshes."
            )
        result_state_records = [run.result_state for run in analysis_run_records]
        analysis_mesh_records = [
            run.analysis_mesh for run in analysis_run_records if run.analysis_mesh is not None
        ]
    analysis_meshes_by_id = {analysis_mesh.id: analysis_mesh for analysis_mesh in analysis_mesh_records}
    owned_mesh_ids = {state.mesh_id for state in result_state_records if state.mesh_id}
    for analysis_mesh in analysis_mesh_records:
        if analysis_mesh.solver_input_identity is not None and analysis_mesh.id not in owned_mesh_ids:
            raise ValueError(
                f"Provenance-bearing analysis mesh {analysis_mesh.id!r} requires a supplied "
                "owning result state."
            )
    for result_state in result_state_records:
        is_volume = bool(result_state.metadata.get("volume_analysis"))
        compiler_id = VOLUME_CODE_ASTER_COMPILER_ID if is_volume else CODE_ASTER_COMPILER_ID
        compiler_inputs = result_state.metadata.get("compiler_inputs") if is_volume else None
        validate_solver_input_identity(
            model,
            result_state.solver_input_identity,
            context=f"ResultState {result_state.id!r}",
            expected_load_case=result_state.load_case,
            expected_compiler_id=compiler_id,
            compiler_inputs=compiler_inputs,
        )
        analysis_mesh = analysis_meshes_by_id.get(result_state.mesh_id or "")
        if analysis_mesh is not None:
            require_matching_solver_input_identities(
                result_state.solver_input_identity,
                analysis_mesh.solver_input_identity,
                context=f"ResultState {result_state.id!r} and analysis mesh {analysis_mesh.id!r}",
            )
            validate_solver_input_identity(
                model,
                analysis_mesh.solver_input_identity,
                context=f"Analysis mesh {analysis_mesh.id!r}",
                expected_load_case=result_state.load_case,
                expected_compiler_id=compiler_id,
                compiler_inputs=compiler_inputs,
            )
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

    if opts.include_loads:
        load_objects, load_assets, load_case_overlays = build_load_scene(model)
        objects.extend(load_objects)
        assets.extend(load_assets)
        overlays.extend(load_case_overlays)

    if opts.include_imported_components:
        mixed_objects, mixed_assets, mixed_diagnostics = _build_imported_component_scene(model)
        objects.extend(mixed_objects)
        assets.extend(mixed_assets)
        diagnostics.extend(mixed_diagnostics)

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
            analysis_meshes_by_id.get(result_state.mesh_id or ""),
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

    layers, layer_diagnostics = build_layer_registry(objects, overlays, analysis_mesh_records)
    diagnostics.extend(layer_diagnostics)

    scene = VisualizationScene(
        scene_id=resolved_scene_id,
        model_id=model_id or getattr(model, "project_name", "tuba_model"),
        created_at=created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        units={"length": "m", "mass": "kg"},
        coordinate_system={"up_axis": "Z"},
        objects=objects,
        geometry_assets=assets,
        overlays=overlays,
        layers=layers,
        result_fields=build_result_fields(overlays),
        issues=issues,
        route_reviews=route_reviews,
        agent_proposals=proposal_records,
        views=views,
        scene_diffs=scene_diffs,
        diagnostics=diagnostics,
        extra=_scene_provenance_extra(result_state_records, analysis_mesh_records, ifc_context),
    )
    scene.validate()
    return scene


def _scene_provenance_extra(
    result_states: list[ResultState],
    analysis_meshes: list[AnalysisMesh],
    ifc_context: dict[str, Any] | None,
) -> dict[str, Any]:
    extra = {"ifc_context": dict(ifc_context)} if ifc_context else {}
    identities = {
        identity.fingerprint: identity.to_dict()
        for identity in [
            *(state.solver_input_identity for state in result_states),
            *(mesh.solver_input_identity for mesh in analysis_meshes),
        ]
        if identity is not None
    }
    if identities:
        extra["solver_input_identities"] = [identities[key] for key in sorted(identities)]
    return extra
