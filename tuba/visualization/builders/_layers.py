"""Layer taxonomy and result-field catalogue.

Two things the viewer used to guess at, now stated by the builders.

The four categories are rules, not buckets:

``design``
    What the engineer authored: pipes, supports, applied loads, envelopes, and
    imported/reference context.
``analysis_mesh``
    What was handed to the solver: nodes, elements, ``GROUP_MA``/``GROUP_NO``.
``results``
    What the solver returned: deformed shapes, fields, vectors.
``annotations``
    What comments on the model: clashes, rule violations, routes, proposals.

Adding a new object or overlay kind means adding it to the table below. An
unclassified kind is filed under ``annotations`` *and* reported as a scene
diagnostic — silently landing in a generic bin is the failure mode this module
exists to remove.
"""

from __future__ import annotations

from tuba.analysis.mesh import AnalysisMesh, modelisation_info
from tuba.analysis.mesh_quality import discretisation_summary
from tuba.visualization.scene import (
    Overlay,
    ResultField,
    SceneDiagnostic,
    SceneLayer,
    SceneObject,
)

OBJECT_KIND_CATEGORY: dict[str, str] = {
    # design — what was authored
    "pipe": "design",
    "rack_member": "design",
    "element": "design",
    "support": "design",
    "applied_load": "design",
    "obstacle": "design",
    "physical_envelope": "design",
    "imported_component": "design",
    "imported_port": "design",
    "mixed_coupling": "design",
    "local_coordinate_axis": "design",
    "external_context": "design",
    "point_cloud": "design",
    # analysis_mesh — what was solved
    "analysis_mesh_node": "analysis_mesh",
    "analysis_mesh_element": "analysis_mesh",
    # results — what came back
    "result_state": "results",
    "geometry_state": "results",
    "deformed_result": "results",
    "deformed_centerline": "results",
    "deformed_envelope": "results",
    "deformed_analysis_mesh_element": "results",
    "tuyau_subpoint_field": "results",
    "displacement_vector": "results",
    "reaction_vector": "results",
    # annotations — what comments on it
    "clash_marker": "annotations",
    "rule_marker": "annotations",
    "route_candidate": "annotations",
    "load_path_vector": "annotations",
    "field_note": "annotations",
}

OVERLAY_KIND_CATEGORY: dict[str, str] = {
    # design
    "physical_envelope": "design",
    "load_case": "design",
    "external_source": "design",
    "field_context": "design",
    "rack_assembly": "design",
    # results
    "solver_result": "results",
    "result_state": "results",
    "geometry_state": "results",
    "runtime_state": "results",
    # annotations
    "agent_proposal": "annotations",
    "clash": "annotations",
    "rule_violation": "annotations",
    "route_alternatives": "annotations",
    "load_path": "annotations",
    "cost_heatmap": "annotations",
    "quantity_summary": "annotations",
}

#: Namespaced layer-id prefixes that override the per-kind tables. Objects that
#: set explicit ``layer_ids`` route through this first.
LAYER_ID_PREFIX_CATEGORY: tuple[tuple[str, str], ...] = (
    ("design:", "design"),
    ("physical_envelope:", "design"),
    ("imported_components", "design"),
    ("mixed_", "design"),
    ("local_coordinate_axes", "design"),
    ("analysis_mesh:", "analysis_mesh"),
    ("result:", "results"),
    ("solver_result:", "results"),
    ("deformed:", "results"),
)

#: Fields whose overlay stores per-node vectors rather than per-object scalars.
VECTOR_RESULT_TYPES = frozenset({"displacement", "reaction_force", "reaction_moment"})
VECTOR_COMPONENTS = ("DX", "DY", "DZ", "magnitude")
SCALAR_COMPONENTS = ("magnitude",)


def category_for_layer_id(layer_id: str, *, object_kind: str = "", overlay_kind: str = "") -> str | None:
    """Best-known category for a layer, or ``None`` when unclassified."""
    for prefix, category in LAYER_ID_PREFIX_CATEGORY:
        if layer_id.startswith(prefix):
            return category
    if overlay_kind:
        return OVERLAY_KIND_CATEGORY.get(overlay_kind)
    if object_kind:
        return OBJECT_KIND_CATEGORY.get(object_kind)
    return OBJECT_KIND_CATEGORY.get(layer_id)


def build_layer_registry(
    objects: list[SceneObject],
    overlays: list[Overlay],
    analysis_meshes: list[AnalysisMesh],
) -> tuple[list[SceneLayer], list[SceneDiagnostic]]:
    """Return the scene's layers plus diagnostics for unclassified content."""
    layers: dict[str, SceneLayer] = {}
    diagnostics: list[SceneDiagnostic] = []
    has_volume_skin = any(mesh.surface_mesh is not None for mesh in analysis_meshes)

    def add(layer_id: str, category: str | None, label: str, source: str, source_kind: str) -> None:
        if layer_id in layers:
            return
        if category is None:
            category = "annotations"
            diagnostics.append(
                SceneDiagnostic(
                    code="visualization.layer.unclassified",
                    severity="warning",
                    message=(
                        f"{source} kind {source_kind!r} has no layer category; filed under 'annotations'. "
                        "Add it to tuba/visualization/builders/_layers.py."
                    ),
                )
            )
        layers[layer_id] = SceneLayer(
            id=layer_id,
            category=category,
            label=_label_for(layer_id),
            default_visible=not (layer_id == "pipe" and has_volume_skin),
        )

    for obj in objects:
        layer_ids = list(obj.layer_ids) if obj.layer_ids else [obj.kind or "object"]
        for layer_id in layer_ids:
            add(layer_id, category_for_layer_id(layer_id, object_kind=obj.kind), layer_id, "Object", obj.kind)

    for overlay in overlays:
        layer_id = f"overlay:{overlay.kind or 'overlay'}"
        add(layer_id, category_for_layer_id(layer_id, overlay_kind=overlay.kind), layer_id, "Overlay", overlay.kind)

    for layer in _mesh_identity_layers(analysis_meshes):
        layers.setdefault(layer.id, layer)

    return list(layers.values()), diagnostics


def mesh_identity(analysis_mesh: AnalysisMesh) -> dict[str, object]:
    """Describe what kind of mesh this actually is, for the viewer badge.

    Modelisations are ordered by descending element count so a mixed model leads
    with its dominant one. The discretisation entry is the bend-chord check; it
    is omitted entirely when the mesh has no bends, so the viewer shows nothing
    rather than a check that passed vacuously.
    """
    counts: dict[str, int] = {}
    for group_name, modelisation in analysis_mesh.modelisations.items():
        counts[modelisation] = counts.get(modelisation, 0) + len(analysis_mesh.groups.get(group_name, ()))
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    entries = [
        {
            "modelisation": modelisation,
            "element_count": count,
            "topological_dim": modelisation_info(modelisation)[0],
            "result_support": modelisation_info(modelisation)[1],
        }
        for modelisation, count in ordered
    ]
    dims = [entry["topological_dim"] for entry in entries if entry["topological_dim"] >= 0]
    identity: dict[str, object] = {
        "mesh_id": analysis_mesh.id,
        "solver": analysis_mesh.solver_name,
        "modelisations": entries,
        "topological_dim": max(dims) if dims else -1,
        "node_count": len(analysis_mesh.nodes),
        "element_count": len(analysis_mesh.elements),
        "element_families": _element_families(analysis_mesh),
    }
    discretisation = discretisation_summary(analysis_mesh)
    if discretisation is not None:
        identity["discretisation"] = discretisation
    return identity


#: Node count -> Code_Aster element family, for the 1D meshes Tuba emits.
_SEG_FAMILIES: dict[int, str] = {1: "POI1", 2: "SEG2", 3: "SEG3", 4: "SEG4"}


def _element_families(analysis_mesh: AnalysisMesh) -> list[dict[str, object]]:
    """Element topology by node count, e.g. SEG2 / SEG3, descending by count.

    The viewer names the mesh in the reviewer's vocabulary ("11 SEG3"), which it
    cannot do from ``MODELISATION`` alone: Tuba emits TUYAU_3M on SEG3, but the
    family is a property of the connectivity rather than of the modelisation.
    """
    counts: dict[int, int] = {}
    for node_ids in analysis_mesh.elements.values():
        counts[len(node_ids)] = counts.get(len(node_ids), 0) + 1
    return [
        {"family": _SEG_FAMILIES.get(node_count, f"NODE{node_count}"), "element_count": count}
        for node_count, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_result_fields(overlays: list[Overlay]) -> list[ResultField]:
    """Catalogue the selectable colouring fields carried by solver overlays.

    A field advertises exactly what its overlay holds: nothing is synthesised.
    Overlays with per-object scalars offer only ``magnitude``; the two vector
    result types offer per-axis components as well.
    """
    fields: list[ResultField] = []
    for overlay in overlays:
        if overlay.kind not in {"solver_result", "tuyau_subpoint_field"}:
            continue
        data = overlay.data or {}
        values = data.get("values") or {}
        if not values:
            continue
        result_type = str(data.get("result_type") or overlay.kind)
        is_vector = result_type in VECTOR_RESULT_TYPES
        fields.append(
            ResultField(
                id=overlay.id.replace("overlay:", "field:", 1),
                label=str(data.get("legend", {}).get("field") or overlay.name or result_type),
                load_case=str(data.get("load_case") or ""),
                result_state_id=str(data.get("result_state_id") or ""),
                overlay_id=overlay.id,
                support=str(data.get("support") or _support_for(result_type)),
                components=VECTOR_COMPONENTS if is_vector else SCALAR_COMPONENTS,
                unit=str(data.get("unit") or data.get("legend", {}).get("unit") or ""),
                range=_range_for(data, values),
                compliance_role=data.get("compliance_role"),
            )
        )
    return fields


def _support_for(result_type: str) -> str:
    if result_type == "tuyau_subpoints":
        return "subpoint"
    if result_type in VECTOR_RESULT_TYPES:
        return "node"
    return "cell"


def _range_for(data: dict, values: dict) -> tuple[float, float] | None:
    declared = data.get("legend", {}).get("range") or data.get("range")
    if isinstance(declared, dict) and "min" in declared and "max" in declared:
        return (float(declared["min"]), float(declared["max"]))
    numeric = [magnitude for value in values.values() if (magnitude := _field_magnitude(value)) is not None]
    return (min(numeric), max(numeric)) if numeric else None


def _field_magnitude(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, (list, tuple)) or not value:
        return None
    if not all(isinstance(component, (int, float)) for component in value):
        return None
    return float(sum(float(component) ** 2 for component in value) ** 0.5)


def _mesh_identity_layers(analysis_meshes: list[AnalysisMesh]) -> list[SceneLayer]:
    return [
        SceneLayer(
            id=f"analysis_mesh:identity:{analysis_mesh.id}",
            category="analysis_mesh",
            label=_mesh_badge(analysis_mesh),
            default_visible=False,
            extra={"mesh_identity": mesh_identity(analysis_mesh)},
        )
        for analysis_mesh in analysis_meshes
    ]


def _mesh_badge(analysis_mesh: AnalysisMesh) -> str:
    identity = mesh_identity(analysis_mesh)
    entries = identity["modelisations"]
    if not entries:
        return "Mesh (modelisation unknown)"
    lead = entries[0]
    parts = [f"{lead['topological_dim']}D", str(lead["modelisation"]), f"{lead['result_support']} recovery"]
    if len(entries) > 1:
        parts.append(f"+{len(entries) - 1} more")
    return " · ".join(parts)


def _label_for(layer_id: str) -> str:
    tail = layer_id.split(":")[-1]
    return tail.replace("_", " ").replace("-", " ").strip().capitalize() or layer_id
