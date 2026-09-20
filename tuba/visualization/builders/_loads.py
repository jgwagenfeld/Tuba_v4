"""Applied loads and load-case definitions as scene content.

Load cases used to reach the viewer only as a string on a result overlay, so the
*inputs* of an analysis were invisible while its outputs were not. This builder
puts the design intent on screen: one arrow per applied nodal force, and one
inspectable record per load case.
"""

from __future__ import annotations

import math
import numpy as np

from tuba.model import LoadCase, NodalForce, OperationField, TubaModel, sample_bend_geometry
from tuba.refs import EntityRef
from tuba.solver.aster_loads import resolve_operation_field_groups
from tuba.visualization.builders._contract import SceneContribution
from tuba.visualization.builders._helpers import (
    _bounds_for_points,
    _node_coords,
    _script_line_fields,
    _vector_endpoint,
    model_span,
)
from tuba.visualization.scene import GeometryAsset, Overlay, SceneObject

FORCE_LAYER = "design:loads:forces"
MOMENT_LAYER = "design:loads:moments"
LINE_LOAD_LAYER = "design:loads:line_loads"


def _format_force_badge(vector_kind: str, magnitude: float) -> str:
    prefix = "F" if vector_kind == "force" else "M"
    base_unit = "N" if vector_kind == "force" else "N·m"
    k_unit = "kN" if vector_kind == "force" else "kN·m"
    if magnitude >= 1000.0:
        val = magnitude / 1000.0
        s = f"{val:.2f}".rstrip("0").rstrip(".") if val < 10 else f"{val:.1f}".rstrip("0").rstrip(".")
        return f"{prefix} = {s} {k_unit}"
    s = f"{magnitude:.2f}".rstrip("0").rstrip(".") if abs(magnitude - round(magnitude)) > 1e-3 else f"{int(round(magnitude))}"
    return f"{prefix} = {s} {base_unit}"


def _format_line_load_badge(value: float) -> str:
    mag = abs(value)
    if mag >= 1000.0:
        val = mag / 1000.0
        s = f"{val:.2f}".rstrip("0").rstrip(".") if val < 10 else f"{val:.1f}".rstrip("0").rstrip(".")
        return f"q = {s} kN/m"
    s = f"{mag:.2f}".rstrip("0").rstrip(".") if abs(mag - round(mag)) > 1e-3 else f"{int(round(mag))}"
    return f"q = {s} N/m"


def _select_badge_element_ids(model: TubaModel, elements: list) -> set[str]:
    """Select representative element(s) for line load badges, avoiding repetition."""
    if not elements:
        return set()
    if len(elements) == 1:
        return {elements[0].id}
    straight_elements = [e for e in elements if getattr(e, "type", "") != "pipe_bend"]
    if not straight_elements:
        return {elements[len(elements) // 2].id}

    groups: dict[tuple[int, int, int], list[tuple[float, str]]] = {}
    for e in straight_elements:
        p1 = np.asarray(_node_coords(model, e.n1), dtype=float)
        p2 = np.asarray(_node_coords(model, e.n2), dtype=float)
        vec = p2 - p1
        length = float(np.linalg.norm(vec))
        if length <= 1e-6:
            continue
        u = vec / length
        k = (int(round(u[0] * 10)), int(round(u[1] * 10)), int(round(u[2] * 10)))
        inv_k = (-k[0], -k[1], -k[2])
        canonical = k if k >= inv_k else inv_k
        groups.setdefault(canonical, []).append((length, e.id))

    badge_ids: set[str] = set()
    for items in groups.values():
        items.sort(key=lambda x: x[0], reverse=True)
        badge_ids.add(items[0][1])
    return badge_ids if badge_ids else {straight_elements[0].id}


def build_load_scene(model: TubaModel) -> tuple[list[SceneObject], list[GeometryAsset], list[Overlay]]:
    """Return (objects, assets, overlays) for every load case in the model."""
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    overlays: list[Overlay] = []

    seen_cases: set[str] = set()
    for requested_name in [*model.load_cases, *model.operations]:
        case_name, load_case = model.resolve_load_case(requested_name)
        if case_name in seen_cases:
            continue
        seen_cases.add(case_name)
        case_object_ids: list[str] = []
        for index, nodal_force in enumerate(load_case.nodal_forces):
            for glyph in _force_glyphs(model, case_name, index, nodal_force):
                glyph_objects, glyph_assets = glyph
                objects.append(glyph_objects)
                assets.append(glyph_assets)
                case_object_ids.append(glyph_objects.id)
        for index, field_record in enumerate(getattr(load_case, "fields", [])):
            if field_record.quantity == "line_load":
                for glyph in _line_load_glyphs(model, case_name, index, field_record):
                    glyph_objects, glyph_assets = glyph
                    objects.append(glyph_objects)
                    assets.append(glyph_assets)
                    case_object_ids.append(glyph_objects.id)
        overlays.append(_load_case_overlay(model, case_name, load_case, case_object_ids))

    return SceneContribution(objects=tuple(objects), assets=tuple(assets), overlays=tuple(overlays))


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
    # Script links go on the object only: the asset's generation_config describes the arrow.
    case = model.load_cases.get(case_name) or model.operations.get(case_name)
    links = dict(_script_line_fields(nodal_force))
    if case is not None and case.source_line is not None:
        links["property_lines"] = {"load_case": case.source_line}
    for vector_kind, components, unit, layer_id in parts:
        vector = [float(value) for value in components]
        if max((abs(value) for value in vector), default=0.0) <= 0.0:
            continue
        # An authored load has no family to compare against, so the glyph is
        # drawn at the family maximum: it states direction and kind, and the
        # component values live on the object.
        norm = float(np.linalg.norm(vector))
        end = _vector_endpoint(
            start, vector, reference=norm, span=model_span(model)
        )
        key = f"{case_name}:{nodal_force.node}:{index}:{vector_kind}"
        object_id = f"object:applied_load:{key}"
        asset_id = f"geometry:applied_load:{key}"
        badge_text = _format_force_badge(vector_kind, norm)
        metadata = {
            "load_case": case_name,
            "node_id": nodal_force.node,
            "vector_kind": vector_kind,
            "components": vector,
            "magnitude": norm,
            "badge_text": badge_text,
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
                    metadata={**metadata, **links},
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


def _line_load_glyphs(
    model: TubaModel,
    case_name: str,
    field_index: int,
    field_record: OperationField,
) -> list[tuple[SceneObject, GeometryAsset]]:
    """Generate vector comb and crest rail glyphs for a distributed line load."""
    if not field_record.direction or max(abs(v) for v in field_record.direction) <= 0.0 or abs(field_record.value) <= 0.0:
        return []
    try:
        elements = model.resolve_operation_field_elements(field_record)
    except Exception:
        return []
    if not elements:
        return []

    dir_arr = np.asarray(field_record.direction, dtype=float)
    dir_norm = float(np.linalg.norm(dir_arr))
    if dir_norm <= 1e-12:
        return []
    unit_dir = dir_arr / dir_norm

    span = model_span(model)
    arrow_len = span * 0.06

    case = model.load_cases.get(case_name) or model.operations.get(case_name)
    links = dict(_script_line_fields(field_record))
    if case is not None and case.source_line is not None:
        links["property_lines"] = {"load_case": case.source_line}

    badge_elem_ids = _select_badge_element_ids(model, elements)
    line_load_badge_text = _format_line_load_badge(float(field_record.value))

    glyphs: list[tuple[SceneObject, GeometryAsset]] = []
    for elem in elements:
        if elem.type == "pipe_bend" and elem.bend_geometry is not None:
            geom = elem.bend_geometry
            radius = float(geom.radius) if geom.radius else 1.0
            angle_rad = math.radians(abs(float(geom.angle))) if geom.angle else math.pi / 2.0
            arc_len = radius * angle_rad
            steps = max(2, min(16, int(round(arc_len / 0.5))))
            centerline_points = sample_bend_geometry(_node_coords(model, elem.n1), geom, n_segments=steps).tolist()
        else:
            p1 = np.asarray(_node_coords(model, elem.n1), dtype=float)
            p2 = np.asarray(_node_coords(model, elem.n2), dtype=float)
            length = float(np.linalg.norm(p2 - p1))
            if length <= 1e-6:
                centerline_points = [p1.tolist()]
            else:
                steps = max(1, min(20, int(round(length / 0.6))))
                centerline_points = [(p1 + (p2 - p1) * (i / steps)).tolist() for i in range(steps + 1)]

        arrow_ends = [[float(v) for v in pt] for pt in centerline_points]
        arrow_starts = [[float(v - unit_dir[i] * arrow_len) for i, v in enumerate(pt)] for pt in centerline_points]
        crest_points = list(arrow_starts)

        key = f"{case_name}:{elem.id}:{field_index}:line_load"
        object_id = f"object:applied_load:{key}"
        asset_id = f"geometry:applied_load:{key}"
        show_badge = elem.id in badge_elem_ids
        metadata = {
            "load_case": case_name,
            "element_id": elem.id,
            "vector_kind": "line_load",
            "quantity": "line_load",
            "value_npm": float(field_record.value),
            "direction": [float(v) for v in field_record.direction],
            "unit": "N/m",
            "show_badge": show_badge,
        }
        if show_badge:
            metadata["badge_text"] = line_load_badge_text
        if field_record.route_id:
            metadata["route_id"] = field_record.route_id
        if field_record.station_start is not None:
            metadata["station_start"] = float(field_record.station_start)
        if field_record.station_end is not None:
            metadata["station_end"] = float(field_record.station_end)

        color = "#0284c7"
        glyphs.append(
            (
                SceneObject(
                    id=object_id,
                    kind="applied_load",
                    name=f"{elem.id} applied line load ({field_record.value:.1f} N/m, {case_name})",
                    geometry_asset_id=asset_id,
                    layer_ids=[LINE_LOAD_LAYER],
                    entity_ref=EntityRef("element", elem.id),
                    metadata={**metadata, **links},
                ),
                GeometryAsset(
                    id=asset_id,
                    format="line_load_comb",
                    bounds=_bounds_for_points([*arrow_starts, *arrow_ends], 0.0),
                    object_ids=[object_id],
                    generation_config={
                        "source": "tuba.applied_loads",
                        "color": color,
                        "arrow_starts": arrow_starts,
                        "arrow_ends": arrow_ends,
                        "crest_points": crest_points,
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
    line_load_fields = [f for f in getattr(load_case, "fields", []) if f.quantity == "line_load"]
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
            "line_load_count": len(line_load_fields),
            "field_count": len(load_case.fields),
            "pressure_fields": [
                {"element_ids": list(element_ids), "pressure_pa": value}
                for element_ids, value in pressure_fields
            ],
            "pressure_source": "authored_input",
        },
    )

