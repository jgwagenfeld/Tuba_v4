"""Deformed/geometry-state and analysis-mesh scene builders."""

from __future__ import annotations
from typing import Any
from typing import Iterable
from dataclasses import dataclass
import numpy as np
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.projection import project_deformed_centerline
from tuba.model import TubaModel
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.geometry.deformed import build_deformed_envelopes
from tuba.geometry.profiles import profile_for_section
from tuba.geometry.section_mesh import deformed_section_sweep_surface_mesh
from tuba.refs import EntityRef
from tuba.solver.aster_mesh import _nodal_force_node_ids
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._contract import SceneContribution
from tuba.visualization.builders._helpers import _bounds_for_points, _dedupe, _node_coords, _safe_bounds_for_points
from tuba.visualization.builders._results import SCALAR_COLOR_MAP


def _analysis_line_element_ids(mesh: AnalysisMesh) -> set[str]:
    """A TRI3 shell is a surface even though SEG3 also has three nodes."""
    other_families = {
        element_id for group, family in mesh.modelisations.items()
        if family in {"3D", "DKT", "COQUE_3D", "DIS_TR"}
        for element_id in mesh.groups.get(group, ())
    }
    return {
        element_id for element_id, nodes in mesh.elements.items()
        if len(nodes) in {2, 3} and (
            (element_id not in mesh.element_sources and element_id not in other_families
             and not element_id.startswith(("VM", "VS", "SM", "RC")))
            or (element_id in mesh.element_sources and mesh.element_sources[element_id].role
                in {"native_element", "spring_connector", "contact_connector"})
        )
    }


def _shell_surface_mesh(mesh: AnalysisMesh) -> dict[str, Any] | None:
    cells = [
        mesh.elements[element_id] for element_id, source in mesh.element_sources.items()
        if source.role == "shell_cell"
    ]
    if not cells:
        return None
    node_ids = tuple(dict.fromkeys(node_id for cell in cells for node_id in cell))
    indices = {node_id: index for index, node_id in enumerate(node_ids)}
    return {
        "node_ids": node_ids, "vertices": [mesh.nodes[node_id] for node_id in node_ids],
        "faces": [[indices[node_id] for node_id in cell] for cell in cells],
    }


def _build_shell_scene(
    mesh: AnalysisMesh,
    result_state: ResultState | None = None,
    geometry_state: GeometryState | None = None,
) -> SceneContribution:
    """Shell geometry and real scalar results in the existing web scene path."""
    surface = _shell_surface_mesh(mesh)
    if surface is None:
        return SceneContribution()
    base = np.asarray(surface["vertices"], dtype=float)
    fields = [("surface", base.tolist(), None, None)]
    suffix = mesh.id
    metadata: dict[str, Any] = {"mesh_id": mesh.id, "role": "shell_surface", "modelisation": "DKT"}
    if result_state is not None:
        try:
            displacement = np.asarray([
                result_state.node_displacements[node_id][:3] for node_id in surface["node_ids"]
            ], dtype=float)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Shell review requires native displacement at every shell node.") from exc
        if not np.isfinite(displacement).all():
            raise ValueError("Shell review contains non-finite native displacement.")
        metadata.update(result_state_id=result_state.id, load_case=result_state.load_case)
        suffix += ":" + result_state.id
        if geometry_state is not None:
            factor = geometry_state.displacement_scale * geometry_state.safety_factor
            fields = [("deformed_surface", (base + displacement * factor).tolist(), None, None)]
            suffix += ":" + geometry_state.id
            metadata.update(_deformed_metadata(geometry_state, result_state))
        else:
            values_by_node = result_state.metadata.get("shell_von_mises", {})
            try:
                values = [float(values_by_node[node_id]) for node_id in surface["node_ids"]]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Shell review requires native through-thickness VMIS at every shell node.") from exc
            if not np.isfinite(values).all():
                raise ValueError("Shell review contains non-finite native VMIS.")
            fields = [
                ("stress", base.tolist(), values, "Pa"),
                ("displacement", (base + displacement).tolist(), np.linalg.norm(displacement, axis=1).tolist(), "m"),
            ]
    objects, assets, overlays = [], [], []
    for field, vertices, values, unit in fields:
        object_id = f"object:shell:{field}:{suffix}"
        asset_id = f"geometry:shell:{field}:{suffix}"
        name = {"surface": "DKT shell mesh", "deformed_surface": "Deformed DKT shell",
                "stress": "Shell FE VMIS (not code stress)", "displacement": "Shell displacement"}[field]
        config = {"source": f"tuba.analysis_shell.{field}", "mesh_id": mesh.id,
                  "vertices": vertices, "faces": surface["faces"], "base_vertices": base.tolist()}
        layer = "analysis_mesh:shell_surface" if result_state is None else f"solver_result:shell_{field}"
        if values is not None:
            field_name = "Shell FE VMIS (not code stress)" if field == "stress" else "Shell displacement magnitude"
            legend = {"field": field_name, "unit": unit, "range": {"min": min(values), "max": max(values)},
                      "color_map": SCALAR_COLOR_MAP, "thresholds": {}}
            config.update(vertex_values=values, legend=legend, result_state_id=result_state.id)
            overlays.append(Overlay(
                id=f"overlay:shell:{field}:{suffix}", kind="solver_result", object_ids=[object_id], name=name,
                data={"result_type": "stress" if field == "stress" else "displacement",
                      "field": field_name, "unit": unit, "result_state_id": result_state.id,
                      "study_id": result_state.study_id, "mesh_id": mesh.id, "load_case": result_state.load_case,
                      "values": {object_id: max(values)}, "range": legend["range"], "legend": legend,
                      "components": ["magnitude"], "support": "node",
                      "stress_basis": result_state.metadata.get("shell_stress_basis")},
            ))
        assets.append(GeometryAsset(id=asset_id, format="mesh", bounds=_bounds_for_points(vertices, 0.0),
                                    object_ids=[object_id], generation_config=config))
        objects.append(SceneObject(id=object_id, kind=f"shell_{field}_field" if values is not None else "analysis_mesh_surface",
                                   name=name, geometry_asset_id=asset_id, layer_ids=[layer], metadata=dict(metadata)))
    return SceneContribution(objects=tuple(objects), assets=tuple(assets), overlays=tuple(overlays))


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

    return SceneContribution(objects=tuple(objects), assets=tuple(assets), diagnostics=tuple(diagnostics))
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
        insulation = model.get_insulation(envelope.entity)
        if insulation is None or insulation.thickness_m <= 0:
            continue
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
    shell = _build_shell_scene(analysis_mesh, result_state, geometry_state)
    objects.extend(shell.objects)
    assets.extend(shell.assets)
    line_element_ids = _analysis_line_element_ids(analysis_mesh)
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
    line_elements = {}
    for element_id, node_ids in analysis_mesh.elements.items():
        if analysis_mesh.surface_mesh is not None and element_id not in line_element_ids:
            continue
        source = analysis_mesh.element_sources.get(element_id)
        if source is not None and source.role in {"contact_connector", "spring_connector", "shell_cell", "reference_carrier"}:
            continue
        line_elements[element_id] = node_ids
    for display in _deformed_line_displays(model, analysis_mesh, line_elements):
        element_id, node_ids, stations, source = display.element_id, display.node_ids, display.stations, display.source
        points = [
            _deformed_mesh_point(analysis_mesh, result_state, node_id, factor)
            for node_id in stations
        ]
        base_points = _base_points_for_node_ids(None, analysis_mesh, stations)
        object_id = f"object:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:{display.id}"
        asset_id = f"geometry:deformed_mesh:{geometry_state.id}:{analysis_mesh.id}:{display.id}"
        groups = sorted({group for segment in display.segment_ids for group in groups_by_member.get(segment, [])})
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
        if display.span_index is not None:
            metadata.update(span_index=display.span_index, element_ids=list(display.segment_ids))
        elif source is not None and source.segment_index is not None:
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
        if model_element is not None and (len(stations) == 2 or display.span_index is not None):
            profile = profile_for_section(model.sections[model_element.section])
            generation_config["profile_kind"] = profile.kind
            generation_config["source"] = "tuba.deformed_analysis_mesh.profile"
            if profile.kind in {"ibeam", "rectangular"}:
                deformations = [
                    list(result_state.node_displacements[node_id]) for node_id in stations
                ]
                base_surface, deformed_surface = deformed_section_sweep_surface_mesh(
                    model.sections[model_element.section],
                    base_points,
                    deformations,
                    scale=factor,
                    twist_angle_deg=float(getattr(model_element, "twist_angle", 0.0)),
                )
                generation_config.update(
                    section_origins=base_points,
                    section_deformations=deformations,
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
                name=f"{display.id} {geometry_state.id} warped mesh",
                geometry_asset_id=asset_id,
                group_ids=groups,
                layer_ids=["deformed:mesh", *(f"deformed:group:{group}" for group in groups)],
                metadata=metadata,
            )
        )
    return objects, assets


# A member split into at most _PER_SEGMENT_LIMIT straight FE segments draws one
# warped body per segment, as line models always have: eight per straight, 16
# or 32 per bend. A finer chain - a gmsh mesh sized for a solid puts hundreds of
# nodes on one frame member - is drawn as _MAX_MEMBER_SPANS spans instead:
# still eight colour bands along the member, not hundreds of capped skins that
# no browser should have to load. A member of quadratic (SEG3) segments is
# always drawn as spans: one segment's nodes are not stored in order along it.
_PER_SEGMENT_LIMIT = 64
_MAX_MEMBER_SPANS = 8
# Rings per span. The solved shape between FE nodes is smooth, so three
# sub-segments per span (25 stations per member) bend as the solver did.
_SPAN_STATIONS = 4


@dataclass(frozen=True)
class _LineDisplay:
    id: str
    element_id: str
    node_ids: tuple[str, ...]
    stations: tuple[str, ...]
    segment_ids: tuple[str, ...]
    source: Any
    span_index: int | None = None


def _deformed_line_displays(
    model: TubaModel,
    analysis_mesh: AnalysisMesh,
    line_elements: dict[str, Any],
) -> list[_LineDisplay]:
    """The warped line bodies to draw: FE segments, or spans of long members."""
    by_member: dict[str, list[str]] = {}
    for element_id, node_ids in line_elements.items():
        source = analysis_mesh.element_sources.get(element_id)
        if source is not None and source.source_ref.kind == "element" and len(node_ids) in {2, 3}:
            by_member.setdefault(source.source_ref.id, []).append(element_id)
    spans: dict[str, list[_LineDisplay]] = {}
    for member_id, segment_ids in by_member.items():
        member = model.get_element(member_id)
        quadratic = any(len(analysis_mesh.elements[segment]) == 3 for segment in segment_ids)
        if member is None or (len(segment_ids) <= _PER_SEGMENT_LIMIT and not quadratic):
            continue
        chain = _member_node_chain(analysis_mesh, segment_ids, model.nodes[member.n1].coords)
        if chain is not None:
            source = analysis_mesh.element_sources[segment_ids[0]]
            spans[member_id] = _member_spans(member_id, chain, analysis_mesh, segment_ids, source)
    displays: list[_LineDisplay] = []
    drawn: set[str] = set()
    for element_id, node_ids in line_elements.items():
        source = analysis_mesh.element_sources.get(element_id)
        member_id = source.source_ref.id if source is not None and source.source_ref.kind == "element" else None
        if member_id in spans and element_id in by_member[member_id]:
            if member_id not in drawn:
                displays.extend(spans[member_id])
                drawn.add(member_id)
            continue
        nodes = tuple(node_ids)
        displays.append(_LineDisplay(element_id, element_id, nodes, nodes, (element_id,), source))
    return displays


def _member_spans(
    member_id: str,
    chain: list[str],
    analysis_mesh: AnalysisMesh,
    segment_ids: list[str],
    source: Any,
) -> list[_LineDisplay]:
    position = {node: index for index, node in enumerate(chain)}
    # Spans end on segment ends, never on a quadratic segment's middle node.
    ends = sorted(min(position[node] for node in analysis_mesh.elements[segment]) for segment in segment_ids)
    ends.append(len(chain) - 1)
    count = min(_MAX_MEMBER_SPANS, len(segment_ids))
    bounds = [ends[pick] for pick in np.linspace(0, len(segment_ids), count + 1).round().astype(int).tolist()]
    spans = []
    for index, (first, last) in enumerate(zip(bounds[:-1], bounds[1:])):
        nodes = tuple(chain[first : last + 1])
        picks = np.linspace(0, len(nodes) - 1, min(len(nodes), _SPAN_STATIONS)).round().astype(int)
        spans.append(_LineDisplay(
            id=f"{member_id}:span{index}",
            element_id=member_id,
            node_ids=nodes,
            stations=tuple(nodes[pick] for pick in dict.fromkeys(picks.tolist())),
            segment_ids=tuple(
                segment for segment in segment_ids
                if first <= min(position[node] for node in analysis_mesh.elements[segment]) < last
            ),
            source=source,
            span_index=index,
        ))
    return spans


def _member_node_chain(analysis_mesh: AnalysisMesh, segment_ids: list[str], start) -> list[str] | None:
    """A member's FE nodes in order from its n1 end, or None if they do not form one chain."""
    neighbours: dict[str, list[str]] = {}
    middles: dict[frozenset[str], str] = {}
    for segment in segment_ids:
        a, b, middle = _segment_ends(analysis_mesh, analysis_mesh.elements[segment])
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
        if middle is not None:
            middles[frozenset((a, b))] = middle
    ends = [node for node, adjacent in neighbours.items() if len(adjacent) == 1]
    if len(ends) != 2 or any(len(adjacent) > 2 for adjacent in neighbours.values()):
        return None
    chain = [min(ends, key=lambda node: float(np.linalg.norm(np.asarray(analysis_mesh.nodes[node]) - start)))]
    previous = None
    while len(chain) <= 2 * len(segment_ids):
        following = [node for node in neighbours[chain[-1]] if node != previous]
        if not following:
            break
        previous = chain[-1]
        middle = middles.get(frozenset((previous, following[0])))
        chain.extend((following[0],) if middle is None else (middle, following[0]))
    return chain if len(chain) == len(segment_ids) + 1 + len(middles) else None


def _segment_ends(analysis_mesh: AnalysisMesh, node_ids) -> tuple[str, str, str | None]:
    """A segment's two end nodes and its middle node, whatever order they are stored in."""
    if len(node_ids) == 2:
        return node_ids[0], node_ids[1], None
    coords = [np.asarray(analysis_mesh.nodes[node], dtype=float) for node in node_ids]
    pairs = ((0, 1, 2), (0, 2, 1), (1, 2, 0))
    a, b, middle = max(pairs, key=lambda pair: float(np.linalg.norm(coords[pair[0]] - coords[pair[1]])))
    return node_ids[a], node_ids[b], node_ids[middle]


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
def _mesh_node_radius(model: TubaModel | None) -> float:
    """Radius for the node balls, small enough to read as markers on the pipe.

    The viewer's fallback for a radius-less point is 35 mm, which is wider than
    a DN50 run: the balls swallowed the pipe they annotate. Size them off the
    thinnest section in the model instead.
    """
    radii = [
        profile_for_section(section).collision_radius_m
        for section in (model.sections.values() if model is not None else ())
    ]
    smallest = min((radius for radius in radii if radius > 0.0), default=0.0)
    # ponytail: one radius for the whole mesh; go per-node if mixed DNs ever read wrong.
    return smallest * 0.25 if smallest > 0.0 else 0.01
def _build_analysis_mesh_scene(
    analysis_mesh: AnalysisMesh,
    model: TubaModel | None = None,
    *,
    required_node_ids: Iterable[str] = (),
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    required_node_ids = set(required_node_ids)
    node_radius = _mesh_node_radius(model)
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []
    groups_by_member = _analysis_mesh_groups_by_member(analysis_mesh)
    # Node temperatures give every solver node they write a GN_ group; only support and nodal-force groups are layers.
    layered_node_groups = None if model is None else {
        f"GN_{node_id}" for node_id in {support.node for support in model.supports} | _nodal_force_node_ids(model)
    }
    line_element_ids = _analysis_line_element_ids(analysis_mesh)
    shell = _build_shell_scene(analysis_mesh)
    objects.extend(shell.objects)
    assets.extend(shell.assets)
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
        for element_id, element_nodes in analysis_mesh.elements.items():
            source = analysis_mesh.element_sources.get(element_id)
            if source is not None and source.role != "volume_cell":
                continue
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
                    **({"geometry_ref": analysis_mesh.geometry_ref} if analysis_mesh.geometry_ref else {}),
                },
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "surface_mesh"}},
            )
        )
    for node_id, coords in analysis_mesh.nodes.items():
        if analysis_mesh.surface_mesh is not None and node_id not in line_node_ids and node_id not in required_node_ids:
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
                bounds=_bounds_for_points([point], node_radius),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.analysis_mesh.node",
                    "mesh_id": analysis_mesh.id,
                    "node_id": node_id,
                    "point": point,
                    "radius_m": node_radius,
                    "role": role,
                    "groups": groups,
                    "source_ref": str(source.source_ref) if source is not None else None,
                },
            )
        )
        layer_groups = [
            group for group in groups
            if layered_node_groups is None or not group.startswith("GN_") or group in layered_node_groups
        ]
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=source.source_ref if source is not None else None,
                kind="analysis_mesh_node",
                name=f"{node_id} ({role})",
                geometry_asset_id=asset_id,
                group_ids=groups,
                layer_ids=_analysis_mesh_node_layers(role, layer_groups),
                metadata=metadata,
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "node", "member_id": node_id}},
            )
        )

    for element_id, node_ids in analysis_mesh.elements.items():
        if analysis_mesh.surface_mesh is not None and element_id not in line_element_ids:
            continue
        source = analysis_mesh.element_sources.get(element_id)
        if source is not None and source.role in {"shell_cell", "reference_carrier"}:
            continue
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
                layer_ids=_analysis_mesh_element_layers(role, groups),
                metadata=metadata,
                source={"analysis_mesh": {"id": analysis_mesh.id, "member_type": "element", "member_id": element_id}},
            )
        )

    return SceneContribution(objects=tuple(objects), assets=tuple(assets), diagnostics=tuple(diagnostics))
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
    if role in {"contact_ground", "spring_helper"}:
        return ["analysis_mesh:helpers"]
    layers = ["analysis_mesh:nodes"]
    if role == "generated_bend_node":
        layers.append("analysis_mesh:generated_bend_nodes")
    if groups:
        layers.append("analysis_mesh:groups")
        layers.extend(f"analysis_mesh:group:{group}" for group in groups)
    return _dedupe(layers)
def _analysis_mesh_element_layers(role: str, groups: list[str]) -> list[str]:
    if role in {"contact_connector", "spring_connector"}:
        return ["analysis_mesh:helpers"]
    layers = ["analysis_mesh:elements"]
    if groups:
        layers.append("analysis_mesh:groups")
        layers.extend(f"analysis_mesh:group:{group}" for group in groups)
    return _dedupe(layers)
