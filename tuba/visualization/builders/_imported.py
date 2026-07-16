"""Imported-component scene builders."""

from __future__ import annotations
from typing import Any
from typing import Iterable
import numpy as np
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.visualization.scene import GeometryAsset
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.scene import SceneObject
from tuba.visualization.builders._helpers import _asset_id, _bounds_for_points, _node_coords, _normalised_vector, _numeric_triplet, _object_id


_BOX_FACES = [
    [0, 1, 2],
    [0, 2, 3],
    [4, 6, 5],
    [4, 7, 6],
    [0, 4, 5],
    [0, 5, 1],
    [1, 5, 6],
    [1, 6, 2],
    [2, 6, 7],
    [2, 7, 3],
    [3, 7, 4],
    [3, 4, 0],
]
def _build_imported_component_scene(
    model: TubaModel,
) -> tuple[list[SceneObject], list[GeometryAsset], list[SceneDiagnostic]]:
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    diagnostics: list[SceneDiagnostic] = []

    for component in model.imported_components.values():
        if component.asset.kind != "cad_asset" or component.asset.id not in model.cad_assets:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="imported_component.missing_asset",
                    message=f"Imported component {component.id!r} references missing asset {component.asset!s}.",
                    target=f"component:{component.id}",
                )
            )
            continue

        asset_record = model.cad_assets[component.asset.id]
        component_ref = EntityRef("component", component.id)
        component_object, component_asset = _build_imported_component_object(component_ref, component, asset_record)
        objects.append(component_object)
        assets.append(component_asset)

        axis_objects, axis_assets = _build_imported_component_axes(component_ref, asset_record)
        objects.extend(axis_objects)
        assets.extend(axis_assets)

    for port in model.ports.values():
        point = _numeric_triplet(port.position)
        if point is None:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code="imported_port.invalid_position",
                    message=f"Imported port {port.id!r} has an invalid position.",
                    target=f"port:{port.id}",
                )
            )
            continue
        port_ref = EntityRef("port", port.id)
        object_id = _object_id(port_ref)
        asset_id = _asset_id(port_ref)
        radius = max(float(port.radius) * 0.18, 0.025)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="marker",
                bounds=_bounds_for_points([point], radius),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.imported_port",
                    "entity_ref": str(port_ref),
                    "point": point,
                    "radius_m": radius,
                    "color": "#f97316",
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=port_ref,
                kind="imported_port",
                name=port.id,
                geometry_asset_id=asset_id,
                layer_ids=["imported_components", "mixed_ports"],
                metadata=port.to_dict(),
            )
        )

    for coupling in model.couplings.values():
        if coupling.kind != "pipe_to_solid_port" or coupling.source_node.id not in model.nodes:
            continue
        port = model.ports.get(coupling.target.id)
        if port is None:
            continue
        start = _node_coords(model, coupling.source_node.id)
        end = _numeric_triplet(port.position)
        if end is None:
            continue
        axis = _normalised_vector(port.axis) or [1.0, 0.0, 0.0]
        if float(np.linalg.norm(np.asarray(end) - np.asarray(start))) <= 1e-9:
            # ponytail: coincident endpoint/port; draw the coupling intent along the port axis.
            end = [float(end[i] + axis[i] * max(port.radius * 2.5, 0.18)) for i in range(3)]

        coupling_ref = EntityRef("coupling", coupling.id)
        object_id = _object_id(coupling_ref)
        asset_id = _asset_id(coupling_ref)
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="line",
                bounds=_bounds_for_points([start, end], 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.mixed_coupling",
                    "entity_ref": str(coupling_ref),
                    "points": [start, end],
                    "color": "#ea580c",
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=coupling_ref,
                kind="mixed_coupling",
                name=coupling.id,
                geometry_asset_id=asset_id,
                layer_ids=["imported_components", "mixed_couplings"],
                metadata=coupling.to_dict(),
            )
        )

    return objects, assets, diagnostics
def _build_imported_component_object(component_ref: EntityRef, component: Any, asset_record: Any) -> tuple[SceneObject, GeometryAsset]:
    vertices, faces = _imported_component_mesh(asset_record)
    object_id = _object_id(component_ref)
    asset_id = _asset_id(component_ref)
    asset = GeometryAsset(
        id=asset_id,
        format="mesh",
        bounds=_bounds_for_points(vertices, 0.0),
        object_ids=[object_id],
        generation_config={
            "source": "tuba.imported_component",
            "entity_ref": str(component_ref),
            "vertices": vertices,
            "faces": faces,
            "color": "#64748b",
            "opacity": 0.34,
            "transparent": True,
        },
    )
    obj = SceneObject(
        id=object_id,
        entity_ref=component_ref,
        kind="imported_component",
        name=component.name,
        geometry_asset_id=asset_id,
        layer_ids=["imported_components"],
        metadata={
            **component.to_dict(),
            "cad_asset": asset_record.to_dict(),
        },
    )
    return obj, asset
def _build_imported_component_axes(component_ref: EntityRef, asset_record: Any) -> tuple[list[SceneObject], list[GeometryAsset]]:
    origin, rotation = _asset_placement_transform(asset_record.placement)
    length = _axis_length(asset_record)
    axis_defs = (
        ("x", [1.0, 0.0, 0.0], "#dc2626"),
        ("y", [0.0, 1.0, 0.0], "#16a34a"),
        ("z", [0.0, 0.0, 1.0], "#2563eb"),
    )
    objects: list[SceneObject] = []
    assets: list[GeometryAsset] = []
    start = [float(value) for value in origin.tolist()]
    for axis_name, local_axis, color in axis_defs:
        end_arr = origin + rotation @ (np.asarray(local_axis, dtype=float) * length)
        end = [float(value) for value in end_arr.tolist()]
        object_id = f"{_object_id(component_ref)}:local_axis:{axis_name}"
        asset_id = f"{_asset_id(component_ref)}:local_axis:{axis_name}"
        assets.append(
            GeometryAsset(
                id=asset_id,
                format="vector",
                bounds=_bounds_for_points([start, end], 0.0),
                object_ids=[object_id],
                generation_config={
                    "source": "tuba.imported_component.local_axis",
                    "axis": axis_name,
                    "start": start,
                    "end": end,
                    "color": color,
                },
            )
        )
        objects.append(
            SceneObject(
                id=object_id,
                entity_ref=component_ref,
                kind="local_coordinate_axis",
                name=f"{component_ref.id} local {axis_name.upper()}",
                geometry_asset_id=asset_id,
                layer_ids=["imported_components", "local_coordinate_axes"],
                metadata={"axis": axis_name, "asset": asset_record.id},
            )
        )
    return objects, assets
def _imported_component_mesh(asset_record: Any) -> tuple[list[list[float]], list[list[int]]]:
    vertices = asset_record.metadata.get("mesh_vertices_local")
    faces = asset_record.metadata.get("mesh_faces")
    if _valid_mesh_payload(vertices, faces):
        return _transform_asset_points(vertices, asset_record), [[int(index) for index in face] for face in faces]
    return _transform_asset_points(_box_vertices(_asset_local_bounds(asset_record)), asset_record), list(_BOX_FACES)
def _valid_mesh_payload(vertices: Any, faces: Any) -> bool:
    return (
        isinstance(vertices, list)
        and isinstance(faces, list)
        and len(vertices) >= 3
        and all(isinstance(point, (list, tuple)) and len(point) >= 3 for point in vertices)
        and all(isinstance(face, (list, tuple)) and len(face) >= 3 for face in faces)
    )
def _asset_local_bounds(asset_record: Any) -> list[float]:
    bounds = asset_record.metadata.get("local_bounds")
    if isinstance(bounds, (list, tuple)) and len(bounds) == 6:
        values = [float(value) for value in bounds]
        if all(np.isfinite(values)):
            return values
    return [-0.1, -0.1, -0.1, 0.1, 0.1, 0.1]
def _axis_length(asset_record: Any) -> float:
    bounds = _asset_local_bounds(asset_record)
    spans = [abs(bounds[3] - bounds[0]), abs(bounds[4] - bounds[1]), abs(bounds[5] - bounds[2])]
    return max(max(spans) * float(getattr(asset_record, "unit_scale_to_m", 1.0)) * 0.65, 0.15)
def _box_vertices(bounds: list[float]) -> list[list[float]]:
    x0, y0, z0, x1, y1, z1 = bounds
    return [
        [x0, y0, z0],
        [x1, y0, z0],
        [x1, y1, z0],
        [x0, y1, z0],
        [x0, y0, z1],
        [x1, y0, z1],
        [x1, y1, z1],
        [x0, y1, z1],
    ]
def _transform_asset_points(points: Iterable[Iterable[float]], asset_record: Any) -> list[list[float]]:
    origin, rotation = _asset_placement_transform(asset_record.placement)
    scale = float(getattr(asset_record, "unit_scale_to_m", 1.0))
    transformed = []
    for point in points:
        arr = np.asarray(list(point)[:3], dtype=float) * scale
        global_point = origin + rotation @ arr
        transformed.append([float(value) for value in global_point.tolist()])
    return transformed
def _asset_placement_transform(placement: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    origin = np.asarray(placement.get("origin", [0.0, 0.0, 0.0]), dtype=float)
    qw, qx, qy, qz = [float(value) for value in placement.get("rotation", [1.0, 0.0, 0.0, 0.0])]
    norm = float(np.linalg.norm([qw, qx, qy, qz]))
    if norm <= 1e-12:
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
    else:
        qw, qx, qy, qz = [value / norm for value in (qw, qx, qy, qz)]
    rotation = np.array(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=float,
    )
    return origin, rotation
def _mesh_group_layer_ids(groups: list[str]) -> list[str]:
    if not groups:
        return []
    return ["analysis_mesh:groups", *(f"analysis_mesh:group:{group}" for group in groups)]
