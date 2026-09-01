"""Applied loads and load-case definitions as scene content.

Load cases used to reach the viewer only as a string on a result overlay, so the
*inputs* of an analysis were invisible while its outputs were not. This builder
puts the design intent on screen: one arrow per applied nodal force, and one
inspectable record per load case.
"""

from __future__ import annotations

from tuba.model import LoadCase, NodalForce, TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_loads import resolve_operation_field_groups
from tuba.visualization.builders._helpers import (
    _bounds_for_points,
    _node_coords,
    _vector_endpoint,
)
from tuba.visualization.scene import GeometryAsset, Overlay, SceneObject

FORCE_LAYER = "design:loads"
MOMENT_LAYER = "design:loads:moments"


def build_load_scene(model: TubaModel) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay]]:
    """Return (objects, assets, overlays) for every load case in the model."""
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []

    for requested_name in [*model.load_cases, *model.operations]:
        case_name, load_case = model.resolve_load_case(requested_name)
        case_object_ids: list[str] = []
        for index, nodal_force in enumerate(load_case.nodal_forces):
            for glyph in _force_glyphs(model, case_name, index, nodal_force):
                glyph_objects, glyph_assets = glyph
                objects.append(glyph_objects)
                assets.append(glyph_assets)
                case_object_ids.append(glyph_objects.id)
        overlays.append(_load_case_overlay(model, case_name, load_case, case_object_ids))

    return objects, assets, overlays


def _force_glyphs(
    model: TubaModel,
    case_name: str,
    index: int,
    nodal_force: NodalForce,
) -> list[tuple[SceneObject, GeometryAsset]]:
    """One glyph for the force part, one for the moment part.

    Moments are drawn separately and tagged ``vector_kind="moment"`` so the
    viewer can render their signed axis and right-hand-rule rotation: a moment
    glyph that looks like a force arrow is a misread waiting to happen.
    """
    start = _node_coords(model, nodal_force.node)
    glyphs: list[tuple[SceneObject, GeometryAsset]] = []
    parts = (
        ("force", nodal_force.components[:3], "N", FORCE_LAYER),
        ("moment", nodal_force.components[3:], "N*m", MOMENT_LAYER),
    )
    for vector_kind, components, unit, layer_id in parts:
        vector = [float(value) for value in components]
        if max((abs(value) for value in vector), default=0.0) <= 0.0:
            continue
        end = _vector_endpoint(start, vector)
        key = f"{case_name}:{nodal_force.node}:{index}:{vector_kind}"
        object_id = f"object:applied_load:{key}"
        asset_id = f"geometry:applied_load:{key}"
        metadata = {
            "load_case": case_name,
            "node_id": nodal_force.node,
            "vector_kind": vector_kind,
            "components": vector,
            "unit": unit,
        }
        color = "#2563eb" if vector_kind == "force" else "#0f766e"
        glyphs.append(
            (
                SceneObject(
                    id=object_id,
                    kind="applied_load",
                    name=f"{nodal_force.node} applied {vector_kind} ({case_name})",
                    geometry_asset_id=asset_id,
                    layer_ids=[layer_id],
                    entity_ref=EntityRef("node", nodal_force.node),
                    metadata=metadata,
                ),
                GeometryAsset(
                    id=asset_id,
                    format="vector",
                    bounds=_bounds_for_points([start, end], 0.0),
                    object_ids=[object_id],
                    generation_config={
                        "source": "tuba.applied_loads",
                        "color": color,
                        "start": start,
                        "end": end,
                        **metadata,
                    },
                ),
            )
        )
    return glyphs


def _load_case_overlay(
    model: TubaModel,
    case_name: str,
    load_case: LoadCase,
    object_ids: list[str],
) -> Overlay:
    pressure_fields = resolve_operation_field_groups(model, load_case, "pressure")
    return Overlay(
        id=f"overlay:load_case:{case_name}",
        kind="load_case",
        object_ids=object_ids,
        name=f"Load case {case_name}",
        data={
            "load_case": case_name,
            "gravity": bool(load_case.gravity),
            "internal_pressure_pa": float(load_case.internal_pressure),
            "temperature_c": float(load_case.temperature),
            "ref_temperature_c": float(load_case.ref_temperature),
            "nodal_force_count": len(load_case.nodal_forces),
            "field_count": len(load_case.fields),
            "pressure_fields": [
                {"element_ids": list(element_ids), "pressure_pa": value}
                for element_ids, value in pressure_fields
            ],
            "pressure_source": "authored_input",
        },
    )
