"""Model-object builders: elements, supports, obstacles, envelopes."""

from __future__ import annotations
from dataclasses import asdict
from typing import Any
from tuba.model import Element
from tuba.model import TubaModel
from tuba.geometry.profiles import profile_for_section
from tuba.physical import element_quantities
from tuba.physical import physical_properties_for_element
from tuba.refs import EntityRef
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import Overlay
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._helpers import SceneBuildOptions, _asset_id, _bounds_for_points, _element_kind, _element_points, _groups_for_element, _ifc_source_for_ref, _node_coords, _object_id, _obstacle_bounds


_PROFILE_DIMENSION_KEYS = {
    "OD": "outer_diameter_m",
    "WT": "wall_thickness_m",
    "ID": "inner_diameter_m",
    "H": "height_m",
    "B": "width_m",
    "Tw": "web_thickness_m",
    "Tf": "flange_thickness_m",
    "radius": "radius_m",
    "pretension": "pretension_n",
    "height_y": "height_y_m",
    "height_z": "height_z_m",
    "thickness_y": "thickness_y_m",
    "thickness_z": "thickness_z_m",
}
def _profile_metadata(model: TubaModel, elem: Element) -> dict[str, Any]:
    profile = profile_for_section(model.sections[elem.section])
    data: dict[str, Any] = {
        "section": elem.section,
        "kind": profile.kind,
        "area_m2": profile.area_m2,
        "collision_radius_m": profile.collision_radius_m,
    }
    for key, value in profile.dimensions.items():
        data[_PROFILE_DIMENSION_KEYS.get(key, key)] = value
    return data
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
    metadata["profile"] = _profile_metadata(model, elem)
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
