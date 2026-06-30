"""IFC placement helpers for Tuba placement frames."""

from __future__ import annotations

from typing import Any

from tuba.placements import PlacementFrame


def create_axis2placement3d(ifc_file: Any, frame: PlacementFrame) -> Any:
    point = ifc_file.create_entity("IfcCartesianPoint", Coordinates=[float(v) for v in frame.origin])
    axis = ifc_file.create_entity("IfcDirection", DirectionRatios=[float(v) for v in frame.axis])
    ref_direction = ifc_file.create_entity("IfcDirection", DirectionRatios=[float(v) for v in frame.ref_direction])
    return ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=point,
        Axis=axis,
        RefDirection=ref_direction,
    )


def create_local_placement(ifc_file: Any, frame: PlacementFrame, parent_placement: Any | None = None) -> Any:
    return ifc_file.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=parent_placement,
        RelativePlacement=create_axis2placement3d(ifc_file, frame),
    )


def frame_from_local_placement(frame_id: str, local_placement: Any) -> PlacementFrame:
    relative = local_placement.RelativePlacement
    loc = tuple(float(v) for v in relative.Location.Coordinates)
    axis = (0.0, 0.0, 1.0)
    ref_direction = (1.0, 0.0, 0.0)
    if relative.Axis is not None:
        axis = tuple(float(v) for v in relative.Axis.DirectionRatios)
    if relative.RefDirection is not None:
        ref_direction = tuple(float(v) for v in relative.RefDirection.DirectionRatios)
    metadata: dict[str, Any] = {"ifc_local_placement_id": int(local_placement.id())}
    if local_placement.PlacementRelTo is not None:
        metadata["parent_ifc_local_placement_id"] = int(local_placement.PlacementRelTo.id())
    return PlacementFrame(
        id=frame_id,
        origin=loc,
        axis=axis,
        ref_direction=ref_direction,
        frame_type="product",
        source="ifc",
        metadata=metadata,
    )


def placement_for_target(model: Any, target: str) -> PlacementFrame | None:
    for assignment in getattr(model, "placement_assignments", []):
        if assignment.target == target and assignment.role == "object_placement":
            frame_id = assignment.frame.split(":", 1)[1] if ":" in assignment.frame else assignment.frame
            return getattr(model, "placement_frames", {}).get(frame_id)
    return None
