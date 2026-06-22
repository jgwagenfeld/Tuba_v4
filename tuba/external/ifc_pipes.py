"""IFC export helpers for Tuba pipe systems."""

from __future__ import annotations

from typing import Any

import ifcopenshell.guid
import numpy as np

from tuba.external.ifc_mapping import IfcGuidRegistry, add_property_set, ifc_property


def export_pipe_products(ifc_file: Any, model: Any, storey: Any, project_context: Any, registry: IfcGuidRegistry) -> dict[str, Any]:
    created: dict[str, Any] = {}
    pipe_elements = [elem for elem in model.elements if elem.type in ("pipe_straight", "pipe_bend")]
    if not pipe_elements:
        return created

    products = []
    for elem in pipe_elements:
        product = _create_pipe_product(ifc_file, model, elem, project_context, registry)
        created[elem.id] = product
        products.append(product)

    ifc_file.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=products,
    )
    system = ifc_file.create_entity(
        "IfcDistributionSystem",
        GlobalId=registry.guid_for(f"pipe-system:{model.project_name}"),
        Name=model.project_name,
        PredefinedType="NOTDEFINED",
    )
    ifc_file.create_entity(
        "IfcRelAssignsToGroup",
        GlobalId=ifcopenshell.guid.new(),
        Name=f"{model.project_name} pipe run",
        RelatedObjects=products,
        RelatingGroup=system,
    )
    ifc_file.create_entity(
        "IfcRelServicesBuildings",
        GlobalId=ifcopenshell.guid.new(),
        Name=f"{model.project_name} services",
        RelatingSystem=system,
        RelatedBuildings=[storey],
    )
    return created


def _create_pipe_product(ifc_file: Any, model: Any, elem: Any, context: Any, registry: IfcGuidRegistry) -> Any:
    cls_name = "IfcPipeFitting" if elem.type == "pipe_bend" else "IfcPipeSegment"
    kwargs = {}
    if elem.type == "pipe_bend":
        kwargs["PredefinedType"] = "BEND"
    product = ifc_file.create_entity(
        cls_name,
        GlobalId=registry.guid_for(f"element:{elem.id}"),
        Name=elem.id,
        Description=f"Material: {elem.material}, Section: {elem.section}",
        **kwargs,
    )
    section = model.sections[elem.section]
    add_property_set(
        ifc_file,
        product,
        "Pset_TubaPipe",
        [
            ifc_property(ifc_file, "SectionName", elem.section),
            ifc_property(ifc_file, "MaterialName", elem.material),
            ifc_property(ifc_file, "OuterDiameterM", float(section.OD)),
            ifc_property(ifc_file, "WallThicknessM", float(section.WT)),
        ],
    )
    axis_points = _pipe_axis_points(model, elem)
    body = _swept_disk_body(ifc_file, model, elem, axis_points)
    axis = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Axis",
        RepresentationType="Curve3D",
        Items=[_polyline(ifc_file, axis_points)],
    )
    body_rep = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[body],
    )
    product.Representation = ifc_file.create_entity("IfcProductDefinitionShape", Representations=[axis, body_rep])
    if elem.type == "pipe_bend":
        add_property_set(
            ifc_file,
            product,
            "Pset_TubaPipeBend",
            [
                ifc_property(ifc_file, "BendRadiusM", float(elem.bend_radius or 0.0)),
                ifc_property(ifc_file, "BendAngleDeg", float(elem.bend_angle or 0.0)),
            ],
        )
    return product


def _pipe_axis_points(model: Any, elem: Any) -> list[np.ndarray]:
    if elem.type != "pipe_bend" or elem.bend_radius is None or elem.bend_angle is None:
        return [
            np.asarray(model.nodes[elem.n1].coords, dtype=float),
            np.asarray(model.nodes[elem.n2].coords, dtype=float),
        ]

    from tuba.solver.aster import CodeAsterSolver

    center, axis, r1, theta = CodeAsterSolver._get_bend_geometry(model, elem)
    steps = 8
    points = []
    for index in range(steps + 1):
        t = index / steps
        angle = theta * t
        rotated = _rotate_about_axis(r1, axis, angle)
        points.append(center + rotated)
    return points


def _rotate_about_axis(vector: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    vector = np.asarray(vector, dtype=float)
    return (
        vector * np.cos(angle)
        + np.cross(axis, vector) * np.sin(angle)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle))
    )

def _swept_disk_body(ifc_file: Any, model: Any, elem: Any, axis_points: list[np.ndarray]) -> Any:
    section = model.sections[elem.section]
    radius = float(section.OD / 2.0)
    inner_radius = float(max(section.OD - 2.0 * section.WT, 0.0) / 2.0)
    return ifc_file.create_entity(
        "IfcSweptDiskSolid",
        Directrix=_polyline(ifc_file, axis_points),
        Radius=radius,
        InnerRadius=inner_radius,
    )


def _polyline(ifc_file: Any, points: list[np.ndarray]) -> Any:
    ifc_points = [
        ifc_file.create_entity("IfcCartesianPoint", Coordinates=[float(p[0]), float(p[1]), float(p[2])])
        for p in points
    ]
    return ifc_file.create_entity("IfcPolyline", Points=ifc_points)
