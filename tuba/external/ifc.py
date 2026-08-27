"""tuba.external.ifc — IFC (Industry Foundation Classes) Importer & Exporter.

Leverages IfcOpenShell to exchange piping geometry, structural support frames,
and enrich elements with FEA stress analysis Property Sets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Any

import numpy as np

from tuba.external.ifc_placements import (
    create_local_placement,
    frame_from_local_placement,
    placement_for_target,
)
from tuba.placements import PlacementAssignment

if TYPE_CHECKING:
    from tuba.model import TubaModel
    from tuba.solver.base import FEAResults
    from tuba.analysis.results import ResultState
    from tuba.clash.types import ClashResult

try:
    import ifcopenshell
    import ifcopenshell.guid
    import ifcopenshell.util.representation
except ImportError:
    _HAS_IFCOPENSHELL = False
else:
    from tuba.external.ifc_mapping import IfcGuidRegistry, ifc_property
    from tuba.external.ifc_pipes import export_pipe_products

    _HAS_IFCOPENSHELL = True


def _require_ifcopenshell():
    if not _HAS_IFCOPENSHELL:
        raise ImportError(
            "ifcopenshell is required for IFC integration. "
            "Install it via: pip install 'tuba[ifc]'"
        )


class IfcExporter:
    """Exports Tuba piping networks, structural frames, and supports to IFC4."""

    OPERATING_STATE_PSET = "Pset_TubaOperatingState"

    def __init__(self) -> None:
        _require_ifcopenshell()

    def export_model(
        self,
        model: TubaModel,
        file_path: str | Path,
        results: Optional[FEAResults] = None,
        result_state: Optional["ResultState"] = None,
        operating_clash_results: Optional[List["ClashResult"]] = None,
    ) -> None:
        """Create a new IFC4 file containing the piping model, supports, structural frames, and stress results."""
        ifc_file = ifcopenshell.file(schema="IFC4")

        # 1. Setup Project, Site, Building structure
        project = ifc_file.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name=model.project_name)
        site = ifc_file.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Tuba Site")
        building = ifc_file.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name="Tuba Plant Section")
        storey = ifc_file.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="Ground Floor Level")

        # Spatial Containment Relations
        ifc_file.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=project, RelatedObjects=[site])
        ifc_file.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=site, RelatedObjects=[building])
        ifc_file.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=building, RelatedObjects=[storey])

        # Store product objects created
        created_elements: Dict[str, ifcopenshell.entity_instance] = {}
        registry = IfcGuidRegistry()
        created_elements.update(export_pipe_products(ifc_file, model, storey, project, registry))

        # Default 2D position for profiles
        origin_2d = ifc_file.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0])
        position_2d = ifc_file.create_entity("IfcAxis2Placement2D", Location=origin_2d)

        # 2. Export elements (pipes, bends, beams, etc.)
        for elem in model.elements:
            if elem.type in ("pipe_straight", "pipe_bend"):
                continue

            p1 = model.nodes[elem.n1].coords
            p2 = model.nodes[elem.n2].coords

            # Determine IFC entity class
            if elem.type == "beam":
                # Classify based on verticality (Y is vertical in Tuba)
                v = p2 - p1
                L = np.linalg.norm(v)
                is_vertical = L > 1e-6 and abs(v[1]) / L > 0.8
                elem_type = "IfcColumn" if is_vertical else "IfcBeam"
            else:
                elem_type = "IfcPipeSegment"

            # Create the IFC object
            ifc_elem = ifc_file.create_entity(
                elem_type,
                GlobalId=ifcopenshell.guid.new(),
                Name=elem.id,
                Description=f"Material: {elem.material}, Section: {elem.section}"
            )
            frame = placement_for_target(model, f"element:{elem.id}")
            if frame is not None:
                ifc_elem.ObjectPlacement = create_local_placement(ifc_file, frame)
            created_elements[elem.id] = ifc_elem

            # Spatial containment relation (contained in storey)
            ifc_file.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=storey,
                RelatedElements=[ifc_elem]
            )

            # 3. Create representation geometry
            try:
                sec = model.sections.get(elem.section)
                if sec is None:
                    raise ValueError(f"Element {elem.id!r} references undefined section {elem.section!r}.")
                solid = None
                rep_type = "SweptSolid"

                # For beams, bars, cables, use IfcExtrudedAreaSolid
                if elem.type in ("beam", "bar", "cable") and sec:
                    v = p2 - p1
                    L = np.linalg.norm(v)
                    if L < 1e-6:
                        z_dir = np.array([0.0, 0.0, 1.0])
                    else:
                        z_dir = v / L

                    if abs(z_dir[1]) < 0.9:
                        ref_x = np.cross(np.array([0.0, 1.0, 0.0]), z_dir)
                    else:
                        ref_x = np.cross(np.array([0.0, 0.0, 1.0]), z_dir)
                    ref_x = ref_x / np.linalg.norm(ref_x)

                    loc = ifc_file.create_entity("IfcCartesianPoint", Coordinates=p1.tolist())
                    axis = ifc_file.create_entity("IfcDirection", DirectionRatios=z_dir.tolist())
                    ref_direction = ifc_file.create_entity("IfcDirection", DirectionRatios=ref_x.tolist())

                    placement = ifc_file.create_entity(
                        "IfcAxis2Placement3D",
                        Location=loc,
                        Axis=axis,
                        RefDirection=ref_direction
                    )
                    extruded_dir = ifc_file.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0])

                    profile = None
                    # Dynamic profile definition matching Tuba section type
                    from tuba.model import IBeamSection, RectangularSection, BarSection, CableSection
                    if isinstance(sec, IBeamSection):
                        from tuba.plotting.pipeline import get_ibeam_dimensions

                        h, b, tw, tf = get_ibeam_dimensions(sec)
                        r = sec.properties.get("R", 0.0)
                        profile = ifc_file.create_entity(
                            "IfcIShapeProfileDef",
                            ProfileType="AREA",
                            ProfileName=sec.name,
                            Position=position_2d,
                            OverallWidth=float(b),
                            OverallDepth=float(h),
                            WebThickness=float(tw),
                            FlangeThickness=float(tf),
                            FilletRadius=float(r)
                        )
                    elif isinstance(sec, RectangularSection):
                        xdim = sec.height_z
                        ydim = sec.height_y
                        thickness = max(sec.thickness_y, sec.thickness_z)
                        if thickness > 0.0:
                            profile = ifc_file.create_entity(
                                "IfcRectangleHollowProfileDef",
                                ProfileType="AREA",
                                ProfileName=sec.name,
                                Position=position_2d,
                                XDim=float(xdim),
                                YDim=float(ydim),
                                WallThickness=float(thickness)
                            )
                        else:
                            profile = ifc_file.create_entity(
                                "IfcRectangleProfileDef",
                                ProfileType="AREA",
                                ProfileName=sec.name,
                                Position=position_2d,
                                XDim=float(xdim),
                                YDim=float(ydim)
                            )
                    elif isinstance(sec, BarSection):
                        od = sec.OD
                        wt = sec.WT
                        if wt > 0.0:
                            profile = ifc_file.create_entity(
                                "IfcCircleHollowProfileDef",
                                ProfileType="AREA",
                                ProfileName=sec.name,
                                Position=position_2d,
                                Radius=float(od / 2.0),
                                WallThickness=float(wt)
                            )
                        else:
                            profile = ifc_file.create_entity(
                                "IfcCircleProfileDef",
                                ProfileType="AREA",
                                ProfileName=sec.name,
                                Position=position_2d,
                                Radius=float(od / 2.0)
                            )
                    elif isinstance(sec, CableSection):
                        profile = ifc_file.create_entity(
                            "IfcCircleProfileDef",
                            ProfileType="AREA",
                            ProfileName=sec.name,
                            Position=position_2d,
                            Radius=float(sec.radius)
                        )

                    if profile is not None:
                        solid = ifc_file.create_entity(
                            "IfcExtrudedAreaSolid",
                            SweptArea=profile,
                            Position=placement,
                            ExtrudedDirection=extruded_dir,
                            Depth=float(L)
                        )
                        rep_type = "SweptSolid"

                # For pipe-like sections, create an IfcSweptDiskSolid from explicit section data.
                if solid is None and sec:
                    if not hasattr(sec, "OD"):
                        raise ValueError(
                            f"Element {elem.id!r} section {elem.section!r} cannot be exported as a swept disk."
                        )
                    radius = sec.OD / 2.0
                    inner_radius = (sec.OD - 2.0 * sec.WT) / 2.0 if hasattr(sec, "WT") else 0.0

                    pt1 = ifc_file.create_entity("IfcCartesianPoint", Coordinates=p1.tolist())
                    pt2 = ifc_file.create_entity("IfcCartesianPoint", Coordinates=p2.tolist())
                    line = ifc_file.create_entity("IfcPolyline", Points=[pt1, pt2])

                    solid = ifc_file.create_entity(
                        "IfcSweptDiskSolid",
                        Directrix=line,
                        Radius=radius,
                        InnerRadius=inner_radius
                    )
                    rep_type = "SweptSolid"

                if solid is not None:
                    # Shape representation
                    rep = ifc_file.create_entity(
                        "IfcShapeRepresentation",
                        ContextOfItems=project,
                        RepresentationIdentifier="Body",
                        RepresentationType=rep_type,
                        Items=[solid]
                    )
                    product_rep = ifc_file.create_entity("IfcProductDefinitionShape", Representations=[rep])
                    ifc_elem.Representation = product_rep
            except Exception as exc:
                raise RuntimeError(f"Failed to create IFC representation for element {elem.id!r}.") from exc

        # 4. Export supports as mechanical fasteners
        for i, sup in enumerate(model.supports):
            if sup.node not in model.nodes:
                continue
            coords = model.nodes[sup.node].coords

            ifc_sup = ifc_file.create_entity(
                "IfcMechanicalFastener",
                GlobalId=ifcopenshell.guid.new(),
                Name=f"Support_{sup.node}_{i}",
                Description=f"Type: {sup.type}"
            )
            support_ref = f"support:{sup.id}" if sup.id is not None else None
            frame = placement_for_target(model, support_ref) if support_ref is not None else None
            if frame is not None:
                ifc_sup.ObjectPlacement = create_local_placement(ifc_file, frame)

            # Contained in storey
            ifc_file.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=storey,
                RelatedElements=[ifc_sup]
            )

            # Simple box geometry representation
            try:
                pt = ifc_file.create_entity("IfcCartesianPoint", Coordinates=coords.tolist())
                box = ifc_file.create_entity("IfcBoundingBox", Corner=pt, XDim=0.2, YDim=0.2, ZDim=0.2)
                rep = ifc_file.create_entity(
                    "IfcShapeRepresentation",
                    ContextOfItems=project,
                    RepresentationIdentifier="Box",
                    RepresentationType="BoundingBox",
                    Items=[box]
                )
                product_rep = ifc_file.create_entity("IfcProductDefinitionShape", Representations=[rep])
                ifc_sup.Representation = product_rep
            except Exception:
                pass

            # Enrich support with FEA property set
            r_forc = np.zeros(3)
            r_moment = np.zeros(3)
            if results:
                node_res = results.node_results.get(sup.node)
                if node_res is not None and node_res.reaction_force is not None:
                    r_forc = node_res.reaction_force[:3]
                    r_moment = node_res.reaction_force[3:]

            friction_coeff = getattr(sup, "friction_coefficient", 0.0)

            props = [
                ifc_file.create_entity("IfcPropertySingleValue", Name="VerticalReaction_N", NominalValue=ifc_file.create_entity("IfcReal", float(r_forc[1]))),
                ifc_file.create_entity("IfcPropertySingleValue", Name="LateralReaction_N", NominalValue=ifc_file.create_entity("IfcReal", float(r_forc[2]))),
                ifc_file.create_entity("IfcPropertySingleValue", Name="AxialReaction_N", NominalValue=ifc_file.create_entity("IfcReal", float(r_forc[0]))),
                ifc_file.create_entity("IfcPropertySingleValue", Name="TorsionalMoment_Nm", NominalValue=ifc_file.create_entity("IfcReal", float(r_moment[0]))),
                ifc_file.create_entity("IfcPropertySingleValue", Name="SupportType", NominalValue=ifc_file.create_entity("IfcLabel", sup.type)),
                ifc_file.create_entity("IfcPropertySingleValue", Name="FrictionCoefficient", NominalValue=ifc_file.create_entity("IfcReal", float(friction_coeff))),
            ]
            pset = ifc_file.create_entity(
                "IfcPropertySet",
                GlobalId=ifcopenshell.guid.new(),
                Name="Pset_TubaSupportForces",
                HasProperties=props
            )
            ifc_file.create_entity(
                "IfcRelDefinesByProperties",
                GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[ifc_sup],
                RelatingPropertyDefinition=pset
            )

        # 5. Export obstacles as building element proxies
        for obs in model.obstacles:
            obs_id = obs.get("id", "Unnamed")
            obs_type = obs.get("type", "cuboid")
            ifc_obs = ifc_file.create_entity(
                "IfcBuildingElementProxy",
                GlobalId=ifcopenshell.guid.new(),
                Name=obs_id,
                Description=f"Obstacle type: {obs_type}"
            )
            frame = placement_for_target(model, f"obstacle:{obs_id}")
            if frame is not None:
                ifc_obs.ObjectPlacement = create_local_placement(ifc_file, frame)

            # Contained in storey
            ifc_file.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=storey,
                RelatedElements=[ifc_obs]
            )

            # Build box geometry for cuboids
            if obs_type == "cuboid" and "min_point" in obs and "max_point" in obs:
                try:
                    pmin = np.array(obs["min_point"])
                    pmax = np.array(obs["max_point"])
                    dims = pmax - pmin
                    pt = ifc_file.create_entity("IfcCartesianPoint", Coordinates=pmin.tolist())
                    box = ifc_file.create_entity("IfcBoundingBox", Corner=pt, XDim=float(dims[0]), YDim=float(dims[1]), ZDim=float(dims[2]))
                    rep = ifc_file.create_entity(
                        "IfcShapeRepresentation",
                        ContextOfItems=project,
                        RepresentationIdentifier="Box",
                        RepresentationType="BoundingBox",
                        Items=[box]
                    )
                    product_rep = ifc_file.create_entity("IfcProductDefinitionShape", Representations=[rep])
                    ifc_obs.Representation = product_rep
                except Exception:
                    pass

        # 6. Enrich elements with FEA stress property sets
        if results:
            from tuba.compliance.asme_b313 import ASMEB313Evaluator
            evaluator = ASMEB313Evaluator()
            report = evaluator.evaluate(model, results)

            for res in report.results:
                ifc_elem = created_elements.get(res.element_id)
                if not ifc_elem:
                    continue

                props = [
                    ifc_file.create_entity("IfcPropertySingleValue", Name="SustainedStressRatio", NominalValue=ifc_file.create_entity("IfcReal", float(res.sustained_ratio))),
                    ifc_file.create_entity("IfcPropertySingleValue", Name="ExpansionStressRatio", NominalValue=ifc_file.create_entity("IfcReal", float(res.expansion_ratio))),
                    ifc_file.create_entity("IfcPropertySingleValue", Name="ComplianceVerdict", NominalValue=ifc_file.create_entity("IfcLabel", "PASS" if (res.sustained_pass and res.expansion_pass) else "FAIL")),
                    ifc_file.create_entity("IfcPropertySingleValue", Name="MaxStress_Pa", NominalValue=ifc_file.create_entity("IfcReal", float(max(res.sustained_stress, res.expansion_stress)))),
                ]

                pset = ifc_file.create_entity(
                    "IfcPropertySet",
                    GlobalId=ifcopenshell.guid.new(),
                    Name="Pset_TubaStressAnalysis",
                    HasProperties=props
                )
                ifc_file.create_entity(
                    "IfcRelDefinesByProperties",
                    GlobalId=ifcopenshell.guid.new(),
                    RelatedObjects=[ifc_elem],
                    RelatingPropertyDefinition=pset
                )

        if result_state is not None or operating_clash_results:
            self._add_operating_state_property_sets(
                ifc_file=ifc_file,
                model=model,
                created_elements=created_elements,
                result_state=result_state,
                operating_clash_results=list(operating_clash_results or []),
            )

        # Write file
        ifc_file.write(str(file_path))

    def _add_operating_state_property_sets(
        self,
        *,
        ifc_file: Any,
        model: TubaModel,
        created_elements: Dict[str, Any],
        result_state: Optional["ResultState"],
        operating_clash_results: List["ClashResult"],
    ) -> None:
        clashes_by_element: Dict[str, list[Any]] = {}
        for clash in operating_clash_results:
            for ref in (clash.left, clash.right):
                if ref.kind == "element":
                    clashes_by_element.setdefault(ref.id, []).append(clash)

        for elem in model.elements:
            ifc_elem = created_elements.get(elem.id)
            if ifc_elem is None:
                continue
            clashes = clashes_by_element.get(elem.id, [])
            if result_state is None and not clashes:
                continue
            load_case = result_state.load_case if result_state is not None else _first_clash_metadata(clashes, "load_case", "")
            result_state_id = result_state.id if result_state is not None else _first_clash_metadata(clashes, "result_state_id", "")
            props = [
                _ifc_property(ifc_file, "LoadCase", load_case),
                _ifc_property(ifc_file, "ResultStateId", result_state_id),
                _ifc_property(ifc_file, "OperatingClashCount", len(clashes)),
                _ifc_property(ifc_file, "MaxOperatingPenetrationM", max((clash.penetration_m for clash in clashes), default=0.0)),
            ]
            if result_state is not None:
                props.extend(
                    [
                        _ifc_property(ifc_file, "SolverName", result_state.solver_name),
                        _ifc_property(ifc_file, "StudyId", result_state.study_id),
                        _ifc_property(ifc_file, "MeshId", result_state.mesh_id),
                    ]
                )
                props.append(_ifc_property(ifc_file, "MaxNodeDisplacementM", _max_element_displacement(model, elem, result_state)))
            if clashes:
                props.append(_ifc_property(ifc_file, "GeometryState", _first_clash_metadata(clashes, "geometry_state", "")))
                props.append(_ifc_property(ifc_file, "MinColdDistanceM", min(clash.metadata.get("cold_distance_m", 0.0) for clash in clashes)))
                props.append(
                    _ifc_property(
                        ifc_file,
                        "MinOperatingDistanceM",
                        min(clash.metadata.get("operating_distance_m", 0.0) for clash in clashes),
                    )
                )

            pset = ifc_file.create_entity(
                "IfcPropertySet",
                GlobalId=ifcopenshell.guid.new(),
                Name=self.OPERATING_STATE_PSET,
                HasProperties=props,
            )
            ifc_file.create_entity(
                "IfcRelDefinesByProperties",
                GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[ifc_elem],
                RelatingPropertyDefinition=pset,
            )


def _ifc_property(ifc_file: Any, name: str, value: Any) -> Any:
    return ifc_property(ifc_file, name, value)


def _first_clash_metadata(clashes: list[Any], key: str, default: Any) -> Any:
    for clash in clashes:
        if key in clash.metadata:
            return clash.metadata[key]
    return default


def _max_element_displacement(model: Any, elem: Any, result_state: Any) -> float:
    max_displacement = 0.0
    for node_id in (elem.n1, elem.n2):
        values = result_state.node_displacements.get(node_id)
        if values is None:
            continue
        max_displacement = max(max_displacement, float(np.linalg.norm(np.asarray(values[:3], dtype=float))))
    return max_displacement


class IfcImporter:
    """Imports piping layout, support structures, supports, and obstacles from IFC files."""

    def __init__(self) -> None:
        _require_ifcopenshell()

    def import_model(self, file_path: str | Path) -> TubaModel:
        """Parse an IFC file and extract piping, beams, columns, supports, and obstacles into a TubaModel."""
        from tuba.model import TubaModel, IBeamSection, RectangularSection, BarSection, CableSection

        ifc_file = ifcopenshell.open(str(file_path))
        model = TubaModel(project_name=Path(file_path).stem)

        # Add default material and section specs
        model.add_material("S235JR", E=2.1e11, nu=0.3, rho=7850.0, allowable_stress={20.0: 137e6})
        model.add_pipe_section("StandardPipe", OD=0.1143, WT=0.00602)

        node_map: Dict[Tuple[float, float, float], str] = {}

        def get_or_create_node(coords: np.ndarray | Tuple[float, float, float] | List[float]) -> str:
            # Round coords to 1mm to collapse overlapping endpoints
            c = np.asarray(coords, dtype=float)
            key = (round(c[0], 3), round(c[1], 3), round(c[2], 3))
            if key not in node_map:
                nid = model.add_node(c)
                node_map[key] = nid
            return node_map[key]

        def get_element_material(elem_inst) -> str:
            try:
                for assoc in getattr(elem_inst, "HasAssociations", []):
                    if assoc.is_a("IfcRelAssociatesMaterial"):
                        rel_mat = assoc.RelatingMaterial
                        if rel_mat.is_a("IfcMaterial"):
                            mat_name = rel_mat.Name
                            if mat_name not in model.materials:
                                model.add_material(mat_name, E=2.1e11, nu=0.3, rho=7850.0, allowable_stress={20.0: 137e6})
                            return mat_name
            except Exception:
                pass
            return "S235JR"

        def get_or_create_section(swept_area) -> str:
            if not swept_area:
                return "StandardPipe"
            sec_name = swept_area.ProfileName if swept_area.ProfileName else f"Profile_{swept_area.id()}"
            if sec_name in model.sections:
                return sec_name

            try:
                if swept_area.is_a("IfcIShapeProfileDef"):
                    h = float(swept_area.OverallDepth)
                    b = float(swept_area.OverallWidth)
                    tw = float(swept_area.WebThickness)
                    tf = float(swept_area.FlangeThickness)
                    r = float(swept_area.FilletRadius) if swept_area.FilletRadius else 0.0
                    props = {"H": h, "B": b, "Tw": tw, "Tf": tf, "R": r}
                    try:
                        model.add_ibeam_section(sec_name, sec_name)
                    except ValueError:
                        model.sections[sec_name] = IBeamSection(name=sec_name, profile_name=sec_name, properties=props)
                    return sec_name

                elif swept_area.is_a("IfcRectangleProfileDef") or swept_area.is_a("IfcRectangleHollowProfileDef"):
                    xdim = float(swept_area.XDim)
                    ydim = float(swept_area.YDim)
                    thickness = float(swept_area.WallThickness) if swept_area.is_a("IfcRectangleHollowProfileDef") else 0.0
                    model.sections[sec_name] = RectangularSection(
                        name=sec_name, height_y=ydim, height_z=xdim, thickness_y=thickness, thickness_z=thickness
                    )
                    return sec_name

                elif swept_area.is_a("IfcCircleProfileDef") or swept_area.is_a("IfcCircleHollowProfileDef"):
                    r = float(swept_area.Radius)
                    wt = float(swept_area.WallThickness) if swept_area.is_a("IfcCircleHollowProfileDef") else 0.0
                    model.sections[sec_name] = BarSection(name=sec_name, OD=r * 2.0, WT=wt)
                    return sec_name
            except Exception:
                pass
            return "StandardPipe"

        def get_pset_values(product, pset_name: str) -> dict[str, object]:
            values = {}
            for definition in getattr(product, "IsDefinedBy", []):
                if not definition.is_a("IfcRelDefinesByProperties"):
                    continue
                pset = definition.RelatingPropertyDefinition
                if not pset.is_a("IfcPropertySet") or pset.Name != pset_name:
                    continue
                for prop in pset.HasProperties:
                    if prop.is_a("IfcPropertySingleValue") and prop.NominalValue is not None:
                        values[prop.Name] = prop.NominalValue.wrappedValue
            return values

        def get_or_create_pipe_section(pipe_props: dict[str, object]) -> str:
            sec_name = str(pipe_props.get("SectionName", "StandardPipe"))
            if sec_name not in model.sections and "OuterDiameterM" in pipe_props and "WallThicknessM" in pipe_props:
                model.add_pipe_section(
                    sec_name,
                    OD=float(pipe_props["OuterDiameterM"]),
                    WT=float(pipe_props["WallThicknessM"]),
                )
            return sec_name

        def extract_points_from_representation(product) -> Optional[List[np.ndarray]]:
            reprs = product.Representation
            if not reprs:
                return None

            for representation in reprs.Representations:
                if representation.RepresentationIdentifier == "Axis":
                    for item in representation.Items:
                        if item.is_a("IfcPolyline"):
                            pts = [[float(x) for x in p.Coordinates] for p in item.Points]
                            return [np.array(p) for p in pts]

            for representation in reprs.Representations:
                if representation.RepresentationIdentifier in ("Body", "Box"):
                    for item in representation.Items:
                        if item.is_a("IfcSweptDiskSolid"):
                            directrix = item.Directrix
                            if directrix.is_a("IfcPolyline"):
                                pts = [[float(x) for x in p.Coordinates] for p in directrix.Points]
                                return [np.array(p) for p in pts]
                        elif item.is_a("IfcExtrudedAreaSolid"):
                            position = item.Position
                            depth = float(item.Depth)

                            loc = [0.0, 0.0, 0.0]
                            if position.Location:
                                loc = [float(x) for x in position.Location.Coordinates]

                            z_axis = [0.0, 0.0, 1.0]
                            if position.Axis:
                                z_axis = [float(x) for x in position.Axis.DirectionRatios]

                            p1 = np.array(loc)
                            p2 = p1 + np.array(z_axis) * depth
                            return [p1, p2]
                        elif item.is_a("IfcBoundingBox"):
                            loc = [float(x) for x in item.Corner.Coordinates]
                            return [np.array(loc)]
            return None

        def get_absolute_placement_coords(product) -> Optional[np.ndarray]:
            placement = product.ObjectPlacement
            if not placement:
                return None
            coords = np.zeros(3)
            curr = placement
            while curr:
                if curr.is_a("IfcLocalPlacement"):
                    rel = curr.RelativePlacement
                    if rel and rel.is_a("IfcAxis2Placement3D"):
                        loc = rel.Location
                        if loc:
                            coords += np.array([float(x) for x in loc.Coordinates])
                    curr = curr.PlacementRelTo
                else:
                    break
            return coords

        def preserve_product_placement(product, target: str) -> None:
            placement = getattr(product, "ObjectPlacement", None)
            if placement is None or not placement.is_a("IfcLocalPlacement"):
                return
            frame_id = f"ifc_product_{product.id()}_placement"
            if frame_id not in model.placement_frames:
                model.placement_frames[frame_id] = frame_from_local_placement(frame_id, placement)
            model.placement_assignments.append(
                PlacementAssignment(
                    target=target,
                    frame=f"placement_frame:{frame_id}",
                    role="object_placement",
                    source="ifc",
                    metadata={"ifc_product_id": int(product.id())},
                )
            )

        # 1. Import Pipe segments and fittings
        elem_counter = 0
        for pipe in ifc_file.by_type("IfcPipeSegment"):
            pts = extract_points_from_representation(pipe)
            if pts and len(pts) >= 2:
                pipe_props = get_pset_values(pipe, "Pset_TubaPipe")
                mat = str(pipe_props.get("MaterialName", get_element_material(pipe)))
                sec_name = get_or_create_pipe_section(pipe_props)

                for idx in range(len(pts) - 1):
                    n1 = get_or_create_node(pts[idx])
                    n2 = get_or_create_node(pts[idx + 1])
                    element_id = f"pipe_str_{elem_counter}"
                    model.add_element(
                        id=element_id,
                        type="pipe_straight",
                        n1=n1,
                        n2=n2,
                        section=sec_name,
                        material=mat
                    )
                    preserve_product_placement(pipe, f"element:{element_id}")
                    elem_counter += 1

        for fitting in ifc_file.by_type("IfcPipeFitting"):
            pts = extract_points_from_representation(fitting)
            if pts and len(pts) >= 2:
                pipe_props = get_pset_values(fitting, "Pset_TubaPipe")
                bend_props = get_pset_values(fitting, "Pset_TubaPipeBend")
                mat = str(pipe_props.get("MaterialName", get_element_material(fitting)))
                sec_name = get_or_create_pipe_section(pipe_props)
                bend_radius = float(bend_props.get("BendRadiusM", 0.15))
                bend_angle = float(bend_props.get("BendAngleDeg", 90.0))
                n1 = get_or_create_node(pts[0])
                n2 = get_or_create_node(pts[-1])
                element_id = f"pipe_bend_{elem_counter}"
                model.add_element(
                    id=element_id,
                    type="pipe_bend",
                    n1=n1,
                    n2=n2,
                    section=sec_name,
                    material=mat,
                    bend_radius=bend_radius,
                    bend_angle=bend_angle,
                )
                preserve_product_placement(fitting, f"element:{element_id}")
                elem_counter += 1

        # 2. Import Beams and Columns
        for beam in list(ifc_file.by_type("IfcBeam")) + list(ifc_file.by_type("IfcColumn")):
            pts = extract_points_from_representation(beam)
            if pts and len(pts) >= 2:
                mat = get_element_material(beam)
                sec_name = "StandardPipe"
                try:
                    reprs = beam.Representation
                    if reprs:
                        for representation in reprs.Representations:
                            for item in representation.Items:
                                if item.is_a("IfcExtrudedAreaSolid"):
                                    sec_name = get_or_create_section(item.SweptArea)
                except Exception:
                    pass

                for idx in range(len(pts) - 1):
                    n1 = get_or_create_node(pts[idx])
                    n2 = get_or_create_node(pts[idx + 1])
                    element_id = f"beam_{elem_counter}"
                    model.add_element(
                        id=element_id,
                        type="beam",
                        n1=n1,
                        n2=n2,
                        section=sec_name,
                        material=mat
                    )
                    preserve_product_placement(beam, f"element:{element_id}")
                    elem_counter += 1

        # 3. Import Supports (IfcMechanicalFastener)
        for i, fastener in enumerate(ifc_file.by_type("IfcMechanicalFastener")):
            pos = get_absolute_placement_coords(fastener)
            if pos is None:
                pts = extract_points_from_representation(fastener)
                if pts:
                    pos = pts[0]
            if pos is not None:
                closest_node = None
                min_dist = float("inf")
                for nid, n in model.nodes.items():
                    d = np.linalg.norm(n.coords - pos)
                    if d < min_dist:
                        min_dist = d
                        closest_node = nid

                if closest_node and min_dist < 0.2:
                    sup_type = "rest"
                    friction_coeff = 0.0
                    for definition in fastener.IsDefinedBy:
                        if definition.is_a("IfcRelDefinesByProperties"):
                            prop_def = definition.RelatingPropertyDefinition
                            if prop_def.is_a("IfcPropertySet") and prop_def.Name == "Pset_TubaSupportForces":
                                for prop in prop_def.HasProperties:
                                    if prop.is_a("IfcPropertySingleValue"):
                                        if prop.Name == "SupportType":
                                            sup_type = str(prop.NominalValue.wrappedValue)
                                        elif prop.Name == "FrictionCoefficient":
                                            friction_coeff = float(prop.NominalValue.wrappedValue)

                    if not any(t in sup_type for t in ["anchor", "guide", "rest", "spring", "hanger"]):
                        desc = (fastener.Description or "").lower()
                        name = (fastener.Name or "").lower()
                        for t in ["anchor", "guide", "rest", "spring", "hanger"]:
                            if t in desc or t in name:
                                sup_type = t
                                break

                    model.add_support(node=closest_node, type=sup_type, friction_coefficient=friction_coeff)

        # 4. Import Obstacles (IfcBuildingElementProxy)
        for proxy in ifc_file.by_type("IfcBuildingElementProxy"):
            min_pt, max_pt = None, None
            reprs = proxy.Representation
            if reprs:
                for representation in reprs.Representations:
                    for item in representation.Items:
                        if item.is_a("IfcBoundingBox"):
                            pmin = np.array([float(x) for x in item.Corner.Coordinates])
                            dims = np.array([float(item.XDim), float(item.YDim), float(item.ZDim)])
                            min_pt = pmin.tolist()
                            max_pt = (pmin + dims).tolist()

            if min_pt is None or max_pt is None:
                pos = get_absolute_placement_coords(proxy)
                if pos is not None:
                    min_pt = (pos - np.array([0.5, 0.5, 0.5])).tolist()
                    max_pt = (pos + np.array([0.5, 0.5, 0.5])).tolist()

            if min_pt is not None and max_pt is not None:
                model.add_obstacle(
                    id=proxy.Name if proxy.Name else f"Obstacle_{proxy.id()}",
                    type="cuboid",
                    min_point=min_pt,
                    max_point=max_pt
                )

        return model
