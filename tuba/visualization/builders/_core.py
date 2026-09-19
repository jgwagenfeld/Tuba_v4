"""Scene orchestrator: build_visualization_scene."""

from __future__ import annotations
from datetime import datetime
from datetime import timezone
from typing import Any
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.provenance import (
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)
from tuba.solver.compiler_contract import compiler_id_for
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Issue
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import RouteReview
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.scene import ViewState
from tuba.visualization.scene import VisualizationScene
from tuba.visualization.builders._contract import SceneBuildOptions, SceneRequest, SceneContribution
from tuba.visualization.builders._helpers import _default_scene_id, _normalize_ifc_guid_map
from tuba.visualization.builders._objects import _build_element_object, _build_obstacle_object, _build_support_link_object, _build_support_object
from tuba.visualization.builders._imported import _build_imported_component_scene
from tuba.visualization.builders._layers import build_layer_registry, build_result_fields
from tuba.visualization.builders._loads import build_load_scene
from tuba.visualization.builders._states import _build_analysis_mesh_scene, _build_deformed_state_scene, _build_geometry_state_record
from tuba.visualization.builders._results import _build_result_state_record, _build_result_state_result_scene
from tuba.visualization.builders._review import _build_clash_issue_scene, _build_cost_quantity_overlays, _build_field_context_scene, _build_load_path_scene, _build_route_result_scene, _build_rule_issue_scene


def build_visualization_scene(request: SceneRequest) -> VisualizationScene:
    """Build a semantic scene manifest from one :class:`SceneRequest`."""
    model = request.model
    options = request.options
    route_results = request.route_results
    clash_results = request.clash_results
    operating_clash_results = request.operating_clash_results
    rule_results = request.rule_results
    load_path_report = request.load_path_report
    analysis_runs = request.analysis_runs
    result_states = request.result_states
    geometry_states = request.geometry_states
    analysis_meshes = request.analysis_meshes
    include_analysis_mesh = request.include_analysis_mesh
    ifc_guid_map = request.ifc_guid_map
    ifc_context = request.ifc_context
    field_notes = request.field_notes
    review_focus = request.review_focus
    scene_id = request.scene_id
    model_id = request.model_id
    created_at = request.created_at
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
        for run in analysis_run_records:
            run.validate_for_publication(model)
        result_state_records = [state for run in analysis_run_records for state in (run.result_states or (run.result_state,))]
        analysis_mesh_records = [
            run.analysis_mesh for run in analysis_run_records if run.analysis_mesh is not None
        ]
    elif not analysis_mesh_records and model.elements:
        should_include_mesh = include_analysis_mesh if include_analysis_mesh is not None else opts.include_analysis_mesh
        if should_include_mesh:
            from tuba.solver.aster_mesh import generate_analysis_mesh

            try:
                analysis_mesh_records = [generate_analysis_mesh(model)]
            except Exception:
                pass
    analysis_meshes_by_id = {analysis_mesh.id: analysis_mesh for analysis_mesh in analysis_mesh_records}
    volume_element_refs: set[str] = set()
    unscoped_volume_skin = False
    for analysis_mesh in analysis_mesh_records:
        if analysis_mesh.surface_mesh is None:
            continue
        mesh_element_refs = {
            str(source.source_ref)
            for source in analysis_mesh.element_sources.values()
            if source.source_ref.kind == "element" and source.role == "volume_cell"
        }
        for source in analysis_mesh.element_sources.values():
            if source.role == "volume_cell":
                mesh_element_refs.update(source.metadata.get("source_element_refs", ()))
        volume_element_refs.update(mesh_element_refs)
        unscoped_volume_skin = unscoped_volume_skin or not mesh_element_refs
    for analysis_run in analysis_run_records:
        if analysis_run.analysis_mesh is None or analysis_run.analysis_mesh.surface_mesh is None:
            continue
        volume_element_refs.update(
            f"element:{element_id}"
            for element_id in analysis_run.study.metadata.get("compiler_inputs", {}).get("element_ids", ())
        )
    for result_state in result_state_records:
        analysis_mesh = analysis_meshes_by_id.get(result_state.mesh_id or "")
        if analysis_mesh is None or analysis_mesh.surface_mesh is None:
            continue
        volume_element_refs.update(
            f"element:{element_id}"
            for element_id in result_state.metadata.get("compiler_inputs", {}).get("element_ids", ())
        )
    owned_mesh_ids = {state.mesh_id for state in result_state_records if state.mesh_id}
    for analysis_mesh in analysis_mesh_records:
        if analysis_mesh.solver_input_identity is not None and analysis_mesh.id not in owned_mesh_ids:
            raise ValueError(
                f"Provenance-bearing analysis mesh {analysis_mesh.id!r} requires a supplied "
                "owning result state."
            )
    for result_state in result_state_records:
        compiler_id = compiler_id_for(result_state.metadata)
        compiler_inputs = result_state.metadata.get("compiler_inputs")
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
    views: list[ViewState] = []

    def merge(contribution: SceneContribution) -> None:
        objects.extend(contribution.objects)
        assets.extend(contribution.assets)
        overlays.extend(contribution.overlays)
        issues.extend(contribution.issues)
        route_reviews.extend(contribution.route_reviews)
        views.extend(contribution.views)
        diagnostics.extend(contribution.diagnostics)

    if opts.include_elements:
        for elem in model.elements:
            volume_skin = elem.type.startswith("pipe") and (
                unscoped_volume_skin or f"element:{elem.id}" in volume_element_refs
            )
            merge(_build_element_object(model, elem, opts, resolved_ifc_guid_map, volume_skin=volume_skin))

    if opts.include_supports:
        for support in model.supports:
            scene_object, asset = _build_support_object(model, support)
            objects.append(scene_object)
            assets.append(asset)
            link = _build_support_link_object(model, support)
            if link is not None:
                link_object, link_asset = link
                objects.append(link_object)
                assets.append(link_asset)

    if opts.include_obstacles:
        for obstacle in model.obstacles:
            scene_object, asset = _build_obstacle_object(obstacle)
            objects.append(scene_object)
            assets.append(asset)

    if opts.include_loads:
        merge(build_load_scene(model))

    if opts.include_imported_components:
        merge(_build_imported_component_scene(model))

    for route_result in route_results or []:
        merge(_build_route_result_scene(route_result))

    for clash in clash_results or []:
        merge(_build_clash_issue_scene(model, clash))

    for clash in operating_clash_results or []:
        merge(_build_clash_issue_scene(model, clash))

    for result_state in result_state_records:
        state_object, state_overlay = _build_result_state_record(result_state)
        objects.append(state_object)
        overlays.append(state_overlay)
        merge(
            _build_result_state_result_scene(
                model,
                result_state,
                analysis_meshes_by_id.get(result_state.mesh_id or ""),
            )
        )

    for geometry_state in geometry_state_records:
        state_object, state_overlay = _build_geometry_state_record(geometry_state)
        objects.append(state_object)
        overlays.append(state_overlay)

    for analysis_mesh in analysis_mesh_records:
        merge(_build_analysis_mesh_scene(analysis_mesh, model))

    merge(
        _build_deformed_state_scene(
            model,
            result_state_records,
            geometry_state_records,
            analysis_mesh_records,
        )
    )

    for result in rule_results or []:
        merge(_build_rule_issue_scene(model, result))

    if load_path_report is not None:
        merge(_build_load_path_scene(model, load_path_report))

    if opts.include_cost_overlays:
        overlays.extend(_build_cost_quantity_overlays(model, opts.cost_metric))

    if field_notes:
        merge(_build_field_context_scene(field_notes))

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
        views=views,
        diagnostics=diagnostics,
        extra={
            **_scene_provenance_extra(result_state_records, analysis_mesh_records, ifc_context),
            **({"review_focus": review_focus} if review_focus else {}),
        },
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
