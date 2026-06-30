"""
tuba.model — Core data model for Tuba v4.

Defines the canonical, serializable representation of a piping system:
materials, cross-sections, nodes, elements, supports, and load cases.
All data is stored in plain Python dataclasses and can be round-tripped
to/from the Tuba JSON schema.
"""

from __future__ import annotations

import json
import math
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tuba.attributes import AttributeAssignment, InsulationSpec, coerce_entity_ref
from tuba.coordinates import CoordinateSystem
from tuba.placements import PlacementAssignment, PlacementFrame, resolve_placement_frame
from tuba.mixed import (
    AnalysisRegion,
    CadAsset,
    CouplingSpec,
    ImportedComponent,
    MeshGroup,
    Port,
)
from tuba.refs import EntityRef, resolve_entity_ref


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Material:
    """Engineering material with temperature-dependent allowable stress."""

    name: str
    E: float  # Young's modulus [Pa]
    nu: float  # Poisson's ratio [-]
    rho: float = 7850.0  # Density [kg/m³]
    alpha: float = 0.0  # Mean thermal expansion coeff [1/K]
    allowable_stress: Dict[float, float] = field(default_factory=dict)
    """Mapping of temperature [°C] → allowable stress [Pa]."""

    @property
    def G(self) -> float:
        """Shear modulus derived from E and nu."""
        return self.E / (2.0 * (1.0 + self.nu))

    def get_allowable(self, temperature: float) -> float:
        """Linearly interpolate allowable stress for *temperature* [°C].

        Returns the nearest boundary value if *temperature* is outside the
        defined range.
        """
        if not self.allowable_stress:
            raise ValueError(f"No allowable stress data for material '{self.name}'")
        temps = sorted(self.allowable_stress.keys())
        if temperature <= temps[0]:
            return self.allowable_stress[temps[0]]
        if temperature >= temps[-1]:
            return self.allowable_stress[temps[-1]]
        # Linear interpolation
        for i in range(len(temps) - 1):
            t0, t1 = temps[i], temps[i + 1]
            if t0 <= temperature <= t1:
                s0 = self.allowable_stress[t0]
                s1 = self.allowable_stress[t1]
                frac = (temperature - t0) / (t1 - t0)
                return s0 + frac * (s1 - s0)
        # Fallback (should not reach here)
        return self.allowable_stress[temps[-1]]


@dataclass
class PipeSection:
    """Circular pipe cross-section."""

    name: str
    OD: float  # Outer diameter [m]
    WT: float  # Wall thickness [m]
    corrosion_allowance: float = 0.0  # [m]

    @property
    def ID(self) -> float:  # noqa: N802 – intentional capital
        """Inner diameter [m]."""
        return self.OD - 2.0 * self.WT

    @property
    def corroded_WT(self) -> float:
        """Wall thickness after corrosion allowance [m]."""
        return self.WT - self.corrosion_allowance

    @property
    def mean_radius(self) -> float:
        """Mean radius [m]."""
        return (self.OD - self.WT) / 2.0

    @property
    def area(self) -> float:
        """Cross-sectional area [m²]."""
        r_o = self.OD / 2.0
        r_i = self.ID / 2.0
        return math.pi * (r_o**2 - r_i**2)

    @property
    def I(self) -> float:  # noqa: E741, N802
        """Second moment of area [m⁴]."""
        r_o = self.OD / 2.0
        r_i = self.ID / 2.0
        return math.pi / 4.0 * (r_o**4 - r_i**4)

    @property
    def J(self) -> float:
        """Polar moment of area [m⁴]."""
        return 2.0 * self.I

    @property
    def Z(self) -> float:
        """Elastic section modulus [m³]."""
        return self.I / (self.OD / 2.0)

    @property
    def corroded_Z(self) -> float:
        """Section modulus with corroded wall [m³]."""
        t = self.corroded_WT
        OD_c = self.OD  # OD unchanged by internal corrosion
        ID_c = OD_c - 2.0 * t
        r_o = OD_c / 2.0
        r_i = ID_c / 2.0
        I_c = math.pi / 4.0 * (r_o**4 - r_i**4)
        return I_c / r_o


@dataclass
class BarSection:
    """Solid circular bar or pipe-like bar section."""

    name: str
    OD: float  # Outer diameter [m]
    WT: float  # Wall thickness [m] (0.0 if solid)

    @property
    def area(self) -> float:
        if self.WT == 0.0 or self.WT >= self.OD / 2.0:
            return math.pi * (self.OD / 2.0)**2
        r_o = self.OD / 2.0
        r_i = r_o - self.WT
        return math.pi * (r_o**2 - r_i**2)


@dataclass
class CableSection:
    """Tension-only cable section."""

    name: str
    radius: float  # [m]
    pretension: float = 0.0  # [N]

    @property
    def area(self) -> float:
        return math.pi * self.radius**2


@dataclass
class RectangularSection:
    """Rectangular or hollow box section."""

    name: str
    height_y: float  # [m]
    height_z: float  # [m]
    thickness_y: float = 0.0  # [m], 0.0 if solid
    thickness_z: float = 0.0  # [m], 0.0 if solid

    @property
    def area(self) -> float:
        h_y = self.height_y
        h_z = self.height_z
        if self.thickness_y == 0.0 and self.thickness_z == 0.0:
            return h_y * h_z
        t_y = self.thickness_y
        t_z = self.thickness_z
        i_y = h_y - 2.0 * t_y
        i_z = h_z - 2.0 * t_z
        return (h_y * h_z) - max(0.0, i_y * i_z)


@dataclass
class IBeamSection:
    """Standard or general I-beam profile."""

    name: str
    profile_name: str
    properties: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def load_from_db(cls, name: str, profile_name: str) -> IBeamSection:
        from tuba.sections import SectionCatalog

        profile = SectionCatalog.default().get_ibeam_profile(profile_name)
        return cls(name=name, profile_name=profile_name, properties=dict(profile.properties))



@dataclass
class Node:
    """A point in 3-D space."""

    id: str
    coords: np.ndarray  # shape (3,)

    def __post_init__(self):
        self.coords = np.asarray(self.coords, dtype=float)


@dataclass
class Element:
    """A 1-D structural element connecting two nodes."""

    id: str
    type: str  # "pipe_straight" | "pipe_bend" | "beam" | "bar" | "cable"
    n1: str  # start node id
    n2: str  # end node id
    section: str  # PipeSection name
    material: str  # Material name
    bend_radius: Optional[float] = None  # [m], only for bends
    bend_angle: Optional[float] = None  # [deg], only for bends
    twist_angle: float = 0.0  # [deg], local cross-section twist angle


@dataclass
class Support:
    """A boundary condition applied at a node."""

    node: str
    type: str  # "anchor" | "guide" | "rest" | "spring" | "hanger" | "custom"
    direction: Optional[List[float]] = None  # constrained direction [x, y, z]
    stiffness: Optional[float] = None  # spring stiffness [N/m]
    imposed_displacement: Optional[List[float]] = None  # [m]
    stiffness_matrix: Optional[List[float]] = None  # discrete spring stiffnesses [K_x, K_y, K_z, K_rx, K_ry, K_rz]
    blocked_dof: Optional[List[Any]] = None  # discrete blockings [x, y, z, rx, ry, rz]
    mass: float = 0.0  # discrete mass [kg]
    friction_coefficient: float = 0.0
    id: Optional[str] = None



@dataclass
class LoadCase:
    """Operating load case definition."""

    name: str
    gravity: bool = True
    internal_pressure: float = 0.0  # [Pa]
    temperature: float = 20.0  # [°C]
    ref_temperature: float = 20.0  # [°C]


# ---------------------------------------------------------------------------
# Central model
# ---------------------------------------------------------------------------

class TubaModel:
    """Root container for a complete piping analysis model.

    This is the single source of truth: geometry, materials, sections,
    supports, and load cases.  It serialises to the canonical Tuba JSON
    schema and drives every downstream operation (solver, compliance,
    visualisation).
    """

    def __init__(self, project_name: str = "Untitled", standard: str = "ASME_B31.3"):
        self.project_name = project_name
        self.standard = standard

        self.materials: Dict[str, Material] = {}
        self.sections: Dict[str, PipeSection] = {}
        self.nodes: Dict[str, Node] = {}
        self.elements: List[Element] = []
        self.supports: List[Support] = []
        self.load_cases: Dict[str, LoadCase] = {}
        self.tees: Dict[str, Dict[str, Any]] = {}
        self.obstacles: List[Dict[str, Any]] = []
        self.groups: Dict[str, Dict[str, Any]] = {}
        self.placement_frames: Dict[str, PlacementFrame] = {}
        self.placement_assignments: List[PlacementAssignment] = []
        self.specs: Dict[str, Dict[str, Any]] = {}
        self.attributes: List[AttributeAssignment] = []
        self.cad_assets: Dict[str, CadAsset] = {}
        self.imported_components: Dict[str, ImportedComponent] = {}
        self.analysis_regions: Dict[str, AnalysisRegion] = {}
        self.ports: Dict[str, Port] = {}
        self.mesh_groups: Dict[str, MeshGroup] = {}
        self.couplings: Dict[str, CouplingSpec] = {}

        self._node_counter: int = 0
        self._element_counters: Dict[str, int] = {}
        self._support_counter: int = 0
        self._node_point_index: Dict[Tuple[int, int, int], str] = {}
        self._element_ids: set[str] = set()
        self._element_by_id: Dict[str, Element] = {}

    # -- Materials -----------------------------------------------------------

    def add_material(
        self,
        name: str,
        E: float,
        nu: float,
        rho: float = 7850.0,
        alpha: float = 0.0,
        allowable_stress: Optional[Dict[float, float]] = None,
    ) -> Material:
        mat = Material(
            name=name,
            E=E,
            nu=nu,
            rho=rho,
            alpha=alpha,
            allowable_stress=allowable_stress or {},
        )
        self.materials[name] = mat
        return mat

    # -- Sections ------------------------------------------------------------

    def add_pipe_section(
        self,
        name: str,
        OD: float,
        WT: float,
        corrosion_allowance: float = 0.0,
    ) -> PipeSection:
        sec = PipeSection(name=name, OD=OD, WT=WT, corrosion_allowance=corrosion_allowance)
        self.sections[name] = sec
        return sec

    def add_bar_section(self, name: str, OD: float, WT: float) -> BarSection:
        sec = BarSection(name=name, OD=OD, WT=WT)
        self.sections[name] = sec
        return sec

    def add_cable_section(self, name: str, radius: float, pretension: float = 0.0) -> CableSection:
        sec = CableSection(name=name, radius=radius, pretension=pretension)
        self.sections[name] = sec
        return sec

    def add_rectangular_section(
        self,
        name: str,
        height_y: float,
        height_z: float,
        thickness_y: float = 0.0,
        thickness_z: float = 0.0,
    ) -> RectangularSection:
        sec = RectangularSection(
            name=name,
            height_y=height_y,
            height_z=height_z,
            thickness_y=thickness_y,
            thickness_z=thickness_z,
        )
        self.sections[name] = sec
        return sec

    def add_ibeam_section(self, name: str, profile_name: str) -> IBeamSection:
        sec = IBeamSection.load_from_db(name=name, profile_name=profile_name)
        self.sections[name] = sec
        return sec

    # -- Mixed-analysis records ----------------------------------------------

    def add_cad_asset(self, **kwargs) -> CadAsset:
        asset = CadAsset(**kwargs)
        self.cad_assets[asset.id] = asset
        return asset

    def add_imported_component(self, **kwargs) -> ImportedComponent:
        component = ImportedComponent(**kwargs)
        self.imported_components[component.id] = component
        return component

    def add_analysis_region(self, **kwargs) -> AnalysisRegion:
        region = AnalysisRegion(**kwargs)
        self.analysis_regions[region.id] = region
        return region

    def add_port(self, **kwargs) -> Port:
        port = Port(**kwargs)
        self.ports[port.id] = port
        return port

    def add_mesh_group(self, **kwargs) -> MeshGroup:
        mesh_group = MeshGroup(**kwargs)
        self.mesh_groups[mesh_group.id] = mesh_group
        return mesh_group

    def add_coupling(self, **kwargs) -> CouplingSpec:
        coupling = CouplingSpec(**kwargs)
        self.couplings[coupling.id] = coupling
        return coupling

    def connect_pipe_to_port(
        self,
        *,
        pipe: str | EntityRef,
        node: str | EntityRef,
        port: str | EntityRef,
        method: str = "3D_TUYAU",
        id: str | None = None,
    ) -> CouplingSpec:
        """Create a pipe-to-port coupling with basic structural checks."""
        pipe_ref = coerce_entity_ref(pipe)
        node_ref = coerce_entity_ref(node)
        port_ref = coerce_entity_ref(port)

        if pipe_ref.kind != "element":
            raise ValueError(f"pipe reference must target an element, got {pipe_ref.kind!r}.")
        if node_ref.kind != "node":
            raise ValueError(f"node reference must target a node, got {node_ref.kind!r}.")
        if port_ref.kind != "port":
            raise ValueError(f"port reference must target a port, got {port_ref.kind!r}.")

        if method not in {"3D_TUYAU", "3D_POU", "COQ_TUYAU", "COQ_POU"}:
            raise ValueError(f"Unsupported coupling method {method!r}.")

        try:
            element = resolve_entity_ref(self, pipe_ref)
        except KeyError as exc:
            raise ValueError(f"Unknown pipe element {pipe_ref!r}.") from exc
        if element.type not in {"pipe_straight", "pipe_bend"}:
            raise ValueError(
                f"Element {element.id!r} type {element.type!r} is not valid for pipe-port coupling."
            )

        if node_ref.id not in {element.n1, element.n2}:
            raise ValueError(
                f"Node {node_ref.id!r} is not an endpoint of element {element.id!r}."
            )

        try:
            port_entity = resolve_entity_ref(self, port_ref)
        except KeyError as exc:
            raise ValueError(f"Unknown port {port_ref!r}.") from exc

        if not port_entity.face_group:
            raise ValueError(f"Port {port_ref.id!r} must define a face_group.")

        try:
            section = self.sections[element.section]
        except KeyError as exc:
            raise ValueError(
                f"Element {element.id!r} references missing section {element.section!r}."
            ) from exc

        if not hasattr(section, "OD"):
            raise ValueError(
                f"Section {element.section!r} does not define an OD for diameter comparison."
            )

        pipe_radius = float(section.OD) / 2.0
        tolerance = max(0.001, pipe_radius * 0.02)
        if abs(pipe_radius - port_entity.radius) > tolerance:
            raise ValueError(
                "Port diameter mismatch: pipe section OD and port radius differ beyond tolerance."
            )

        coupling_id = id or f"coupling_{len(self.couplings)}"
        return self.add_coupling(
            id=coupling_id,
            kind="pipe_to_solid_port",
            source=pipe_ref,
            source_node=node_ref,
            target=port_ref,
            code_aster_keyword="LIAISON_ELEM",
            code_aster_option=method,
        )

    # -- Nodes ---------------------------------------------------------------

    def add_node(self, coords: np.ndarray) -> str:
        """Create a node and return its id."""
        node_id = f"N{self._node_counter}"
        self._node_counter += 1
        self.nodes[node_id] = Node(id=node_id, coords=np.asarray(coords, dtype=float))
        self._index_node(node_id)
        return node_id

    def find_node_by_point(self, coords, *, tol: float = 1e-6) -> Optional[str]:
        """Return an existing node id at coords, if one exists within tolerance."""
        target = np.asarray(coords, dtype=float)
        indexed = self._node_point_index.get(_point_index_key(target, tol))
        if indexed is not None:
            node = self.nodes.get(indexed)
            if node is not None and np.allclose(node.coords, target, atol=tol):
                return indexed
        for nid, node in self.nodes.items():
            if np.allclose(node.coords, target, atol=tol):
                return nid
        return None

    # -- Elements ------------------------------------------------------------

    def add_element(self, **kwargs) -> Element:
        elem = Element(**kwargs)
        self.elements.append(elem)
        self._element_ids.add(elem.id)
        self._element_by_id[elem.id] = elem
        self._sync_element_counter(elem.id)
        return elem

    def get_element(self, element_id: str) -> Optional[Element]:
        """Return an element by id using the maintained model index."""

        return self._element_by_id.get(element_id)

    def next_element_id(self, prefix: str) -> str:
        """Return the next globally unique element id for *prefix*.

        Element IDs are consumed by solver result mapping, so they must be
        unique across independent builder contexts and autorouted pipe runs.
        """
        idx = self._element_counters.get(prefix, 0)
        while f"{prefix}_{idx}" in self._element_ids:
            idx += 1
        self._element_counters[prefix] = idx + 1
        return f"{prefix}_{idx}"

    def _sync_element_counter(self, elem_id: str) -> None:
        """Advance the matching prefix counter beyond an existing element id."""
        if "_" not in elem_id:
            return
        prefix, suffix = elem_id.rsplit("_", 1)
        if not suffix.isdigit():
            return
        self._element_counters[prefix] = max(
            self._element_counters.get(prefix, 0),
            int(suffix) + 1,
        )

    def _index_node(self, node_id: str) -> None:
        node = self.nodes[node_id]
        self._node_point_index[_point_index_key(node.coords)] = node_id

    # -- Supports ------------------------------------------------------------

    def add_support(
        self,
        node: str,
        type: str,
        direction: Optional[List[float]] = None,
        stiffness: Optional[float] = None,
        imposed_displacement: Optional[List[float]] = None,
        stiffness_matrix: Optional[List[float]] = None,
        blocked_dof: Optional[List[Any]] = None,
        mass: float = 0.0,
        friction_coefficient: float = 0.0,
        id: Optional[str] = None,
    ) -> Support:
        support_id = id or self.next_support_id()
        sup = Support(
            node=node,
            type=type,
            direction=direction,
            stiffness=stiffness,
            imposed_displacement=imposed_displacement,
            stiffness_matrix=stiffness_matrix,
            blocked_dof=blocked_dof,
            mass=mass,
            friction_coefficient=friction_coefficient,
            id=support_id,
        )
        self.supports.append(sup)
        self._sync_support_counter(support_id)
        return sup

    def next_support_id(self) -> str:
        """Return the next globally unique support id."""
        existing = {support.id for support in self.supports}
        idx = self._support_counter
        while f"support_{idx}" in existing:
            idx += 1
        self._support_counter = idx + 1
        return f"support_{idx}"

    def _sync_support_counter(self, support_id: Optional[str]) -> None:
        if not support_id or "_" not in support_id:
            return
        prefix, suffix = support_id.rsplit("_", 1)
        if prefix != "support" or not suffix.isdigit():
            return
        self._support_counter = max(self._support_counter, int(suffix) + 1)

    # -- Semantic attributes -------------------------------------------------

    def add_insulation_spec(
        self,
        id: str,
        material: str,
        thickness_m: float,
        density_kg_m3: float = 0.0,
        cost_per_m: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InsulationSpec:
        spec = InsulationSpec(
            id=id,
            material=material,
            thickness_m=thickness_m,
            density_kg_m3=density_kg_m3,
            cost_per_m=cost_per_m,
            metadata=dict(metadata or {}),
        )
        self.specs.setdefault("insulation", {})[spec.id] = spec
        return spec

    def assign_attribute(
        self,
        target,
        key: str,
        value: Any,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AttributeAssignment:
        assignment = AttributeAssignment(
            target=coerce_entity_ref(target),
            key=key,
            value=value,
            source=source,
            metadata=dict(metadata or {}),
        )
        self.attributes.append(assignment)
        return assignment

    def assign_insulation(
        self,
        target,
        insulation_spec_id: str,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AttributeAssignment:
        if insulation_spec_id not in self.specs.get("insulation", {}):
            raise ValueError(f"Unknown insulation spec {insulation_spec_id!r}.")
        return self.assign_attribute(
            target,
            "insulation",
            insulation_spec_id,
            source=source,
            metadata=metadata,
        )

    def get_attributes(self, target) -> Dict[str, Any]:
        ref = coerce_entity_ref(target)
        values: Dict[str, Any] = {}

        if ref.kind in _GROUP_MEMBER_KEYS:
            containing_groups = self._groups_containing_ref(ref)
            for assignment in self.attributes:
                if assignment.target.kind == "group" and assignment.target.id in containing_groups:
                    values[assignment.key] = assignment.value

        for assignment in self.attributes:
            if assignment.target == ref:
                values[assignment.key] = assignment.value

        return values

    def get_insulation(self, target) -> Optional[InsulationSpec]:
        spec_id = self.get_attributes(target).get("insulation")
        if spec_id is None:
            return None
        spec = self.specs.get("insulation", {}).get(spec_id)
        if spec is None:
            raise ValueError(f"Unknown insulation spec {spec_id!r}.")
        if isinstance(spec, InsulationSpec):
            return spec
        return InsulationSpec.from_dict(spec_id, spec)

    def _groups_containing_ref(self, ref) -> set[str]:
        member_key = _GROUP_MEMBER_KEYS.get(ref.kind)
        if member_key is None:
            return set()
        return {
            group_name
            for group_name, group in self.groups.items()
            if ref.id in group.get(member_key, [])
        }

    # -- Load cases ----------------------------------------------------------

    def define_load_case(
        self,
        name: str,
        gravity: bool = True,
        pressure: float = 0.0,
        temperature: float = 20.0,
        ref_temperature: float = 20.0,
    ) -> LoadCase:
        lc = LoadCase(
            name=name,
            gravity=gravity,
            internal_pressure=pressure,
            temperature=temperature,
            ref_temperature=ref_temperature,
        )
        self.load_cases[name] = lc
        return lc

    # -- Tees and Obstacles --------------------------------------------------

    def define_tee(self, node: str, type: str = "unreinforced_tee", pad_thickness: float = 0.0) -> None:
        """Explicitly define the Tee type and reinforcement for a node."""
        if node not in self.nodes:
            raise ValueError(f"Node '{node}' does not exist in the model.")
        if type not in ("welding_tee", "reinforced_tee", "unreinforced_tee"):
            raise ValueError(f"Unknown Tee type: {type}")
        self.tees[node] = {
            "type": type,
            "pad_thickness": pad_thickness
        }

    def add_obstacle(
        self,
        id: str,
        type: str,
        min_point: Optional[List[float]] = None,
        max_point: Optional[List[float]] = None,
        file_path: Optional[str] = None,
        position: Optional[List[float]] = None,
        orientation: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Add an obstacle (cuboid, cylinder, or mesh) to the model."""
        obs = {
            "id": id,
            "type": type,
        }
        if type in ("cuboid", "cylinder"):
            obs["min_point"] = min_point
            obs["max_point"] = max_point
        elif type == "mesh":
            obs["file_path"] = file_path
            obs["position"] = position or [0.0, 0.0, 0.0]
            obs["orientation"] = orientation or [1.0, 0.0, 0.0, 0.0] # [qw, qx, qy, qz]
        else:
            raise ValueError(f"Unknown obstacle type: {type}")
        self.obstacles.append(obs)
        return obs

    # -- Builder context manager ---------------------------------------------

    @contextmanager
    def pipe(self, section: str, material: str):
        """Context manager that yields a :class:`PipingBuilder`."""
        from tuba.builder import PipingBuilder

        builder = PipingBuilder(model=self, section_name=section, material_name=material)
        yield builder

    def place_fragment(self, fragment, coordinate_system, *, name: str):
        """Place a local-coordinate fragment into this model."""
        from tuba.fragments import place_fragment

        return place_fragment(self, fragment, coordinate_system, name=name)

    # -- Placement frames ----------------------------------------------------

    def add_placement_frame(self, frame: PlacementFrame) -> PlacementFrame:
        """Register a named local placement frame."""
        if frame.id in self.placement_frames:
            raise ValueError(f"Placement frame {frame.id!r} already exists.")
        self.placement_frames[frame.id] = frame
        return frame

    def assign_placement(self, assignment: PlacementAssignment) -> PlacementAssignment:
        """Assign an entity to a placement frame."""
        self.placement_assignments.append(assignment)
        return assignment

    def resolve_placement_frame(self, frame: str) -> CoordinateSystem:
        """Resolve a placement frame ref into a model-global coordinate system."""
        frame_id = frame.split(":", 1)[1] if frame.startswith("placement_frame:") else frame
        return resolve_placement_frame(frame_id, self.placement_frames)

    def to_global_point(self, point, frame: str | None = None) -> np.ndarray:
        """Transform a point from a named frame to model-global coordinates."""
        if frame is None:
            return np.asarray(point, dtype=float)
        return self.resolve_placement_frame(frame).to_global_point(point)

    def to_global_vector(self, vector, frame: str | None = None) -> np.ndarray:
        """Transform a vector from a named frame to model-global coordinates."""
        if frame is None:
            return np.asarray(vector, dtype=float)
        return self.resolve_placement_frame(frame).to_global_vector(vector)

    def to_local_point(self, point, frame: str) -> np.ndarray:
        """Transform a model-global point into a named local frame."""
        return self.resolve_placement_frame(frame).to_local_point(point)

    # -- Solver dispatch -----------------------------------------------------

    def solve(self, solver: str = "code_aster", load_case: Optional[str] = None, **kwargs):
        """Run FEA using the specified solver backend.

        Parameters
        ----------
        solver : str
            ``"code_aster"`` (default and currently only supported backend).
        load_case : str, optional
            Name of the load case to solve.  If *None*, the first defined
            load case is used.

        Returns
        -------
        FEAResults
        """
        if solver == "code_aster":
            from tuba.solver.aster import CodeAsterSolver

            s = CodeAsterSolver(**kwargs)
        else:
            raise ValueError(f"Unknown solver backend: {solver!r}")

        lc_name = load_case or (next(iter(self.load_cases)) if self.load_cases else None)
        return s.solve(self, lc_name)

    def validate(self) -> None:
        """Validate model references and structural invariants."""
        from tuba.validation import validate_model

        validate_model(self)

    # -- Serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict matching the Tuba JSON schema."""
        return {
            "meta": {
                "project_name": self.project_name,
                "standard": self.standard,
                "version": "4.0.0",
            },
            "materials": {
                name: {
                    "E": m.E,
                    "nu": m.nu,
                    "rho": m.rho,
                    "alpha": m.alpha,
                    "allowable_stress": {str(k): v for k, v in m.allowable_stress.items()},
                }
                for name, m in self.materials.items()
            },
            "sections": {
                name: (
                    {
                        "type": "pipe",
                        "OD": s.OD,
                        "WT": s.WT,
                        "corrosion_allowance": s.corrosion_allowance,
                    }
                    if isinstance(s, PipeSection)
                    else {
                        "type": "bar",
                        "OD": s.OD,
                        "WT": s.WT,
                    }
                    if isinstance(s, BarSection)
                    else {
                        "type": "cable",
                        "radius": s.radius,
                        "pretension": s.pretension,
                    }
                    if isinstance(s, CableSection)
                    else {
                        "type": "rectangular",
                        "height_y": s.height_y,
                        "height_z": s.height_z,
                        "thickness_y": s.thickness_y,
                        "thickness_z": s.thickness_z,
                    }
                    if isinstance(s, RectangularSection)
                    else {
                        "type": "ibeam",
                        "profile_name": s.profile_name,
                        "properties": s.properties,
                    }
                    if isinstance(s, IBeamSection)
                    else {}
                )
                for name, s in self.sections.items()
            },
            "nodes": {nid: n.coords.tolist() for nid, n in self.nodes.items()},
            "elements": [
                {
                    "id": e.id,
                    "type": e.type,
                    "n1": e.n1,
                    "n2": e.n2,
                    "section": e.section,
                    "material": e.material,
                    **({"bend_radius": e.bend_radius} if e.bend_radius is not None else {}),
                    **({"bend_angle": e.bend_angle} if e.bend_angle is not None else {}),
                    **({"twist_angle": e.twist_angle} if getattr(e, "twist_angle", 0.0) != 0.0 else {}),
                }
                for e in self.elements
            ],
            "supports": [
                {
                    "node": s.node,
                    "type": s.type,
                    **({"id": s.id} if s.id is not None else {}),
                    **({"direction": s.direction} if s.direction else {}),
                    **({"stiffness": s.stiffness} if s.stiffness is not None else {}),
                    **({"stiffness_matrix": s.stiffness_matrix} if s.stiffness_matrix is not None else {}),
                    **({"blocked_dof": s.blocked_dof} if s.blocked_dof is not None else {}),
                    **({"mass": s.mass} if s.mass != 0.0 else {}),
                    **({"friction_coefficient": s.friction_coefficient} if s.friction_coefficient != 0.0 else {}),
                }
                for s in self.supports
            ],
            "load_cases": {
                name: {
                    "gravity": lc.gravity,
                    "internal_pressure": lc.internal_pressure,
                    "temperature": lc.temperature,
                    "ref_temperature": lc.ref_temperature,
                }
                for name, lc in self.load_cases.items()
            },
            "obstacles": self.obstacles,
            "tees": self.tees,
            "groups": self.groups,
            "placement_frames": {
                frame_id: frame.to_dict()
                for frame_id, frame in self.placement_frames.items()
            },
            "placement_assignments": [
                assignment.to_dict()
                for assignment in self.placement_assignments
            ],
            "specs": _serialize_specs(self.specs),
            "attributes": [assignment.to_dict() for assignment in self.attributes],
            "cad_assets": {
                asset_id: asset.to_dict()
                for asset_id, asset in self.cad_assets.items()
            },
            "imported_components": {
                component_id: component.to_dict()
                for component_id, component in self.imported_components.items()
            },
            "analysis_regions": {
                region_id: region.to_dict()
                for region_id, region in self.analysis_regions.items()
            },
            "ports": {
                port_id: port.to_dict()
                for port_id, port in self.ports.items()
            },
            "mesh_groups": {
                group_id: mesh_group.to_dict()
                for group_id, mesh_group in self.mesh_groups.items()
            },
            "couplings": {
                coupling_id: coupling.to_dict()
                for coupling_id, coupling in self.couplings.items()
            },
        }

    def to_json(self, path: Optional[str] = None, indent: int = 2) -> str:
        """Serialise to JSON string.  Optionally write to *path*."""
        text = json.dumps(self.to_dict(), indent=indent)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TubaModel":
        """Reconstruct a TubaModel from a dict (inverse of :meth:`to_dict`)."""
        from tuba.schema import validate_model_dict

        validate_model_dict(data)
        meta = data.get("meta", {})
        model = cls(
            project_name=meta.get("project_name", "Untitled"),
            standard=meta.get("standard", "ASME_B31.3"),
        )

        for name, m in data.get("materials", {}).items():
            model.add_material(
                name=name,
                E=m["E"],
                nu=m["nu"],
                rho=m.get("rho", 7850.0),
                alpha=m.get("alpha", 0.0),
                allowable_stress={float(k): v for k, v in m.get("allowable_stress", {}).items()},
            )

        for name, s in data.get("sections", {}).items():
            t = s.get("type", "pipe")
            if t == "pipe":
                model.add_pipe_section(
                    name=name,
                    OD=s["OD"],
                    WT=s["WT"],
                    corrosion_allowance=s.get("corrosion_allowance", 0.0),
                )
            elif t == "bar":
                model.add_bar_section(
                    name=name,
                    OD=s["OD"],
                    WT=s["WT"],
                )
            elif t == "cable":
                model.add_cable_section(
                    name=name,
                    radius=s["radius"],
                    pretension=s.get("pretension", 0.0),
                )
            elif t == "rectangular":
                model.add_rectangular_section(
                    name=name,
                    height_y=s["height_y"],
                    height_z=s["height_z"],
                    thickness_y=s.get("thickness_y", 0.0),
                    thickness_z=s.get("thickness_z", 0.0),
                )
            elif t == "ibeam":
                sec = IBeamSection(name=name, profile_name=s["profile_name"], properties=s.get("properties", {}))
                model.sections[name] = sec

        for nid, coords in data.get("nodes", {}).items():
            model.nodes[nid] = Node(id=nid, coords=np.array(coords))
            model._index_node(nid)
            # Keep counter in sync
            num = int(nid.lstrip("N")) if nid.startswith("N") and nid[1:].isdigit() else 0
            model._node_counter = max(model._node_counter, num + 1)

        for e in data.get("elements", []):
            model.add_element(**e)

        for s in data.get("supports", []):
            model.add_support(**s)

        for name, lc in data.get("load_cases", {}).items():
            model.define_load_case(
                name=name,
                gravity=lc.get("gravity", True),
                pressure=lc.get("internal_pressure", 0.0),
                temperature=lc.get("temperature", 20.0),
                ref_temperature=lc.get("ref_temperature", 20.0),
            )

        for obs in data.get("obstacles", []):
            model.add_obstacle(**obs)

        for node_id, tee_info in data.get("tees", {}).items():
            model.define_tee(
                node=node_id,
                type=tee_info.get("type", "unreinforced_tee"),
                pad_thickness=tee_info.get("pad_thickness", 0.0)
            )

        model.groups = data.get("groups", {})
        model.placement_frames = {
            frame_id: PlacementFrame.from_dict(frame_data)
            for frame_id, frame_data in data.get("placement_frames", {}).items()
        }
        model.placement_assignments = [
            PlacementAssignment.from_dict(item)
            for item in data.get("placement_assignments", [])
        ]
        model.specs = _deserialize_specs(data.get("specs", {}))
        model.attributes = [
            AttributeAssignment.from_dict(assignment)
            for assignment in data.get("attributes", [])
        ]
        model.cad_assets = {
            asset_id: CadAsset.from_dict(asset)
            for asset_id, asset in data.get("cad_assets", {}).items()
        }
        model.imported_components = {
            component_id: ImportedComponent.from_dict(component)
            for component_id, component in data.get("imported_components", {}).items()
        }
        model.analysis_regions = {
            region_id: AnalysisRegion.from_dict(region)
            for region_id, region in data.get("analysis_regions", {}).items()
        }
        model.ports = {
            port_id: Port.from_dict(port)
            for port_id, port in data.get("ports", {}).items()
        }
        model.mesh_groups = {
            group_id: MeshGroup.from_dict(mesh_group)
            for group_id, mesh_group in data.get("mesh_groups", {}).items()
        }
        model.couplings = {
            coupling_id: CouplingSpec.from_dict(coupling)
            for coupling_id, coupling in data.get("couplings", {}).items()
        }

        return model

    @classmethod
    def from_json(cls, path: str) -> "TubaModel":
        """Load from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"TubaModel('{self.project_name}', "
            f"{len(self.nodes)} nodes, "
            f"{len(self.elements)} elements, "
            f"{len(self.supports)} supports)"
        )


_GROUP_MEMBER_KEYS = {
    "node": "nodes",
    "element": "elements",
    "support": "supports",
    "obstacle": "obstacles",
    "assembly": "assemblies",
    "route": "routes",
}


def _serialize_specs(specs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    serialized: Dict[str, Dict[str, Any]] = {}
    for kind, entries in specs.items():
        serialized[kind] = {}
        for spec_id, spec in entries.items():
            if hasattr(spec, "to_dict"):
                serialized[kind][spec_id] = spec.to_dict()
            else:
                serialized[kind][spec_id] = spec
    return serialized


def _deserialize_specs(data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    for kind, entries in data.items():
        if kind == "insulation":
            specs[kind] = {
                spec_id: InsulationSpec.from_dict(spec_id, spec_data)
                for spec_id, spec_data in entries.items()
            }
        else:
            specs[kind] = dict(entries)
    return specs


def _point_index_key(coords, tol: float = 1e-6) -> Tuple[int, int, int]:
    arr = np.asarray(coords, dtype=float)
    return tuple(int(round(float(value) / tol)) for value in arr)
