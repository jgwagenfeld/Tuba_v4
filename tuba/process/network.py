"""Strict serial liquid circuits and their measured Tuba route associations.

One mass-flow source, uniform-bore pipe routes, explicitly sourced external
fixed losses and one absolute-pressure sink are supported. FE subdivisions are
hydraulic associations, not additional process ports or junctions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
import re
from typing import TYPE_CHECKING, ClassVar
from numbers import Real

import numpy as np

from tuba.model import PipeSection, TubaModel, sample_bend_geometry
from tuba.validation import _validate_bend_geometry_record
from tuba.physical import element_length

if TYPE_CHECKING:
    from .pid import PidDefinition

NETWORK_SCHEMA = "tuba.process-network.v1"
BOUND_SCHEMA = "tuba.bound-process-network.v1"
WATER_MEDIUM = "Modelica.Media.Water.ConstantPropertyLiquidWater"
SCENARIO_UNITS = {
    "mass_flow_kg_s": "kg/s", "source_temperature_k": "K",
    "sink_pressure_pa": "Pa", "external_pressure_pa": "Pa",
    "mechanical_reference_temperature_k": "K",
}
REQUIREMENT_UNITS = {
    "max_velocity_m_s": "m/s", "min_delivered_mass_flow_kg_s": "kg/s",
    "max_source_pressure_pa": "Pa", "min_sink_pressure_pa": "Pa",
}


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Expected a nonempty stable identifier using letters, numbers, _, . or -")


def _number(value: float, name: str, *, positive: bool = True) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, not Boolean")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return float(value)


def _source(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires an explicit source or declared assumption")


def _strict(data: dict, expected: set[str], name: str) -> dict:
    if type(data) is not dict or set(data) != expected:
        raise ValueError(f"{name} requires exactly {sorted(expected)}")
    return dict(data)


def _encoded(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(data) -> str:
    return hashlib.sha256(_encoded(data).encode("utf-8")).hexdigest()


class _Record:
    def to_dict(self) -> dict:
        return json.loads(_encoded(asdict(self)))

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**_strict(data, {field.name for field in fields(cls)}, cls.__name__))


class _Component(_Record):
    kind: ClassVar[str]

    def to_dict(self) -> dict:
        return {"kind": self.kind, **super().to_dict()}

    @classmethod
    def from_dict(cls, data: dict):
        values = _strict(data, {field.name for field in fields(cls)} | {"kind"}, cls.__name__)
        if values.pop("kind") != cls.kind:
            raise ValueError(f"Expected component kind {cls.kind!r}")
        return cls(**values)


@dataclass(frozen=True)
class MassFlowSource(_Component):
    id: str
    outlet_port: str
    kind: ClassVar[str] = "mass_flow_source"

    def __post_init__(self):
        _identifier(self.id)
        _identifier(self.outlet_port)


@dataclass(frozen=True)
class PressureSink(_Component):
    id: str
    inlet_port: str
    kind: ClassVar[str] = "pressure_sink"

    def __post_init__(self):
        _identifier(self.id)
        _identifier(self.inlet_port)


@dataclass(frozen=True)
class PipeComponent(_Component):
    """A whole uniform-bore route; bend K is excess loss per actual bend."""

    id: str
    inlet_port: str
    outlet_port: str
    route_id: str
    roughness_m: float
    bend_loss_coefficient: float
    bend_loss_source: str
    kind: ClassVar[str] = "pipe"

    def __post_init__(self):
        for name in ("id", "inlet_port", "outlet_port", "route_id"):
            _identifier(getattr(self, name))
        for name in ("roughness_m", "bend_loss_coefficient"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=False))
        _source(self.bend_loss_source, "bend_loss_source")


@dataclass(frozen=True)
class FixedLossComponent(_Component):
    """Sourced zero-length loss explicitly outside the mechanical study."""

    id: str
    inlet_port: str
    outlet_port: str
    bore_m: float
    loss_coefficient: float
    loss_source: str
    mechanical_domain: str = "external"
    kind: ClassVar[str] = "fixed_loss"

    def __post_init__(self):
        for name in ("id", "inlet_port", "outlet_port"):
            _identifier(getattr(self, name))
        for name in ("bore_m", "loss_coefficient"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        _source(self.loss_source, "loss_source")
        if self.mechanical_domain != "external":
            raise ValueError("Fixed losses require mechanical_domain='external'; in-domain valves need a mechanical model")


@dataclass(frozen=True)
class Connection(_Record):
    source_port: str
    target_port: str

    def __post_init__(self):
        _identifier(self.source_port)
        _identifier(self.target_port)
        if self.source_port == self.target_port:
            raise ValueError("A connection requires two different ports")


@dataclass(frozen=True)
class OperatingScenario(_Record):
    """SI boundaries; fluid and external pressures are both absolute."""

    id: str
    mass_flow_kg_s: float
    source_temperature_k: float
    sink_pressure_pa: float
    external_pressure_pa: float
    mechanical_reference_temperature_k: float
    medium: str = WATER_MEDIUM

    def __post_init__(self):
        _identifier(self.id)
        for name in SCENARIO_UNITS:
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=name != "external_pressure_pa"))
        if self.medium != WATER_MEDIUM:
            raise ValueError(f"Supported single-phase medium is {WATER_MEDIUM!r}")

    def to_dict(self) -> dict:
        return {**super().to_dict(), "units": dict(SCENARIO_UNITS), "pressure_reference": "absolute"}

    @classmethod
    def from_dict(cls, data: dict):
        values = _strict(data, {field.name for field in fields(cls)} | {"units", "pressure_reference"}, cls.__name__)
        if values.pop("units") != SCENARIO_UNITS or values.pop("pressure_reference") != "absolute":
            raise ValueError("Operating scenario requires SI units and absolute pressures")
        return cls(**values)


@dataclass(frozen=True)
class HydraulicRequirements(_Record):
    """Explicit task limits in SI; pressure limits use absolute pressure."""

    id: str
    max_velocity_m_s: float
    min_delivered_mass_flow_kg_s: float
    max_source_pressure_pa: float
    min_sink_pressure_pa: float

    def __post_init__(self):
        _identifier(self.id)
        for name in REQUIREMENT_UNITS:
            object.__setattr__(self, name, _number(getattr(self, name), name))

    def to_dict(self) -> dict:
        return {**super().to_dict(), "units": dict(REQUIREMENT_UNITS), "pressure_reference": "absolute"}

    @classmethod
    def from_dict(cls, data: dict):
        values = _strict(data, {field.name for field in fields(cls)} | {"units", "pressure_reference"}, cls.__name__)
        if values.pop("units") != REQUIREMENT_UNITS or values.pop("pressure_reference") != "absolute":
            raise ValueError("Hydraulic requirements require SI units and absolute pressure limits")
        return cls(**values)


COMPONENT_TYPES = {cls.kind: cls for cls in (MassFlowSource, PressureSink, PipeComponent, FixedLossComponent)}


@dataclass(frozen=True)
class ProcessNetwork:
    id: str
    components: tuple[MassFlowSource | PressureSink | PipeComponent | FixedLossComponent, ...]
    connections: tuple[Connection, ...]
    pid: PidDefinition | None = None

    def __post_init__(self):
        _identifier(self.id)
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "connections", tuple(self.connections))
        if any(type(component) not in COMPONENT_TYPES.values() for component in self.components):
            raise ValueError("Unsupported process component type")
        if any(type(connection) is not Connection for connection in self.connections):
            raise ValueError("Connections must be Connection records")
        self.ordered_components
        routes = [component.route_id for component in self.components if isinstance(component, PipeComponent)]
        if not routes or len(routes) != len(set(routes)):
            raise ValueError("At least one pipe and distinct whole-route bindings are required")
        if self.pid is not None:
            from .pid import PidDefinition

            if type(self.pid) is not PidDefinition:
                raise ValueError("pid must be a PidDefinition record")
            self.pid.validate_for(self)

    @property
    def ordered_components(self) -> tuple:
        """Validate all ports and return the sole supported source-to-sink path."""
        ids = [component.id for component in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("Component IDs must be unique")
        sources = [component for component in self.components if isinstance(component, MassFlowSource)]
        sinks = [component for component in self.components if isinstance(component, PressureSink)]
        if len(sources) != 1 or len(sinks) != 1:
            raise ValueError("Exactly one mass-flow source and one pressure sink are required")
        ports = {}
        for component in self.components:
            for name, direction in (("inlet_port", "in"), ("outlet_port", "out")):
                port = getattr(component, name, None)
                if port is not None:
                    if port in ports:
                        raise ValueError("Port IDs must be unique")
                    ports[port] = (component, direction)
        linked, successors = set(), {}
        for connection in self.connections:
            if connection.source_port not in ports or connection.target_port not in ports:
                raise ValueError("Connection references an unknown port")
            source, source_direction = ports[connection.source_port]
            target, target_direction = ports[connection.target_port]
            if source_direction != "out" or target_direction != "in":
                raise ValueError("Connections must join an outlet to an inlet")
            if connection.source_port in linked or connection.target_port in linked:
                raise ValueError("Branches and multiple connections per port are unsupported")
            if source.id == target.id:
                raise ValueError("Self connections and cycles are unsupported")
            linked.update((connection.source_port, connection.target_port))
            successors[source.id] = target
        if linked != set(ports):
            raise ValueError("Every process port must be connected exactly once")
        ordered, visited = [], set()
        current = sources[0]
        while current is not None:
            if current.id in visited:
                raise ValueError("Process cycles are unsupported")
            ordered.append(current)
            visited.add(current.id)
            current = successors.get(current.id)
        if ordered[-1] != sinks[0] or len(ordered) != len(self.components):
            raise ValueError("All components must form one serial path; disconnected cycles are unsupported")
        pipe_positions = [index for index, component in enumerate(ordered) if isinstance(component, PipeComponent)]
        if pipe_positions and any(isinstance(component, FixedLossComponent)
                                  for component in ordered[min(pipe_positions):max(pipe_positions)]):
            raise ValueError("External fixed losses must be outside the modeled pipe chain; in-domain equipment needs mechanical qualification")
        return tuple(ordered)

    def to_dict(self) -> dict:
        return {"schema": NETWORK_SCHEMA, "id": self.id,
                "components": [component.to_dict() for component in self.components],
                "connections": [connection.to_dict() for connection in self.connections],
                **({"pid": self.pid.to_dict()} if self.pid is not None else {})}

    @classmethod
    def from_dict(cls, data: dict):
        from .pid import PidDefinition

        expected = {"schema", "id", "components", "connections"}
        if type(data) is dict and "pid" in data:
            expected.add("pid")
        values = _strict(data, expected, cls.__name__)
        if values["schema"] != NETWORK_SCHEMA:
            raise ValueError(f"Expected schema {NETWORK_SCHEMA!r}")
        if type(values["components"]) is not list or type(values["connections"]) is not list:
            raise ValueError("components and connections must be JSON lists")
        components = []
        for component in values["components"]:
            if type(component) is not dict or component.get("kind") not in COMPONENT_TYPES:
                raise ValueError("Unsupported process component kind")
            components.append(COMPONENT_TYPES[component["kind"]].from_dict(component))
        return cls(values["id"], tuple(components), tuple(Connection.from_dict(value) for value in values["connections"]),
                   PidDefinition.from_dict(values["pid"]) if "pid" in values else None)

    def bind(self, model: TubaModel, scenario: OperatingScenario,
             requirements: HydraulicRequirements) -> BoundProcessNetwork:
        if type(scenario) is not OperatingScenario or type(requirements) is not HydraulicRequirements:
            raise ValueError("Binding requires OperatingScenario and HydraulicRequirements records")
        return _bind(self, model, scenario, requirements)


@dataclass(frozen=True)
class BoundFlowSegment(_Record):
    segment_id: str
    component_id: str
    element_id: str | None
    route_id: str | None
    length_m: float
    bore_m: float
    height_change_m: float
    roughness_m: float
    local_loss_coefficient: float
    loss_source: str | None
    start_m: tuple[float, float, float]
    end_m: tuple[float, float, float]
    station_start_m: float
    station_end_m: float
    network_station_start_m: float
    network_station_end_m: float
    n1: str | None
    n2: str | None

    def __post_init__(self):
        for name in ("segment_id", "component_id", "element_id", "route_id", "n1", "n2"):
            if getattr(self, name) is not None:
                _identifier(getattr(self, name))
        for name in ("length_m", "roughness_m", "local_loss_coefficient", "station_start_m", "station_end_m",
                     "network_station_start_m", "network_station_end_m"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=False))
        object.__setattr__(self, "bore_m", _number(self.bore_m, "bore_m"))
        if type(self.height_change_m) not in (int, float) or not math.isfinite(self.height_change_m):
            raise ValueError("height_change_m must be finite")
        for name in ("start_m", "end_m"):
            values = tuple(getattr(self, name))
            if len(values) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
                raise ValueError(f"{name} must be a finite 3-vector in metres")
            object.__setattr__(self, name, tuple(float(value) for value in values))
        if not math.isclose(self.height_change_m, self.end_m[2] - self.start_m[2], abs_tol=1e-10):
            raise ValueError("Segment elevations contradict height_change_m")
        for start, end in ((self.station_start_m, self.station_end_m),
                           (self.network_station_start_m, self.network_station_end_m)):
            if not math.isclose(end - start, self.length_m, rel_tol=1e-8, abs_tol=1e-9):
                raise ValueError("Segment station span contradicts measured length")
        if self.element_id is None:
            if self.length_m != 0 or any(value is not None for value in (self.route_id, self.n1, self.n2)):
                raise ValueError("An external fixed loss has zero length and no mechanical element association")
        elif self.length_m <= 0 or any(value is None for value in (self.route_id, self.n1, self.n2)):
            raise ValueError("A pipe segment requires positive length, route and node identities")
        if self.local_loss_coefficient > 0:
            _source(self.loss_source, "loss_source")


@dataclass(frozen=True)
class BoundProcessNetwork:
    network: ProcessNetwork
    scenario: OperatingScenario
    requirements: HydraulicRequirements
    segments: tuple[BoundFlowSegment, ...]
    geometry_json: str

    def __post_init__(self):
        object.__setattr__(self, "segments", tuple(self.segments))
        geometry = json.loads(self.geometry_json)
        if type(geometry) is not dict or not self.segments:
            raise ValueError("A bound network requires measured geometry and segments")
        object.__setattr__(self, "geometry_json", _encoded(geometry))
        if len({segment.segment_id for segment in self.segments}) != len(self.segments):
            raise ValueError("Bound segment IDs must be unique")

    @property
    def ordered_components(self) -> tuple:
        return self.network.ordered_components

    @property
    def geometry_fingerprint(self) -> str:
        return _hash({"geometry": json.loads(self.geometry_json),
                      "segments": [segment.to_dict() for segment in self.segments]})

    @property
    def fingerprint(self) -> str:
        return _hash({"network": self.network.to_dict(), "scenario": self.scenario.to_dict(),
                      "requirements": self.requirements.to_dict(), "geometry_fingerprint": self.geometry_fingerprint})

    def verify_for(self, model: TubaModel) -> None:
        """Reject stale bindings after a hydraulic route/section/topology edit."""
        current = self.network.bind(model, self.scenario, self.requirements)
        if current.fingerprint != self.fingerprint:
            raise ValueError("Process binding is stale for the current Tuba geometry")

    def to_dict(self) -> dict:
        return {"schema": BOUND_SCHEMA, "network": self.network.to_dict(),
                "scenario": self.scenario.to_dict(), "requirements": self.requirements.to_dict(),
                "segments": [segment.to_dict() for segment in self.segments],
                "geometry": json.loads(self.geometry_json), "geometry_fingerprint": self.geometry_fingerprint,
                "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, data: dict):
        values = _strict(data, {"schema", "network", "scenario", "requirements", "segments", "geometry",
                               "geometry_fingerprint", "fingerprint"}, cls.__name__)
        if values["schema"] != BOUND_SCHEMA or type(values["segments"]) is not list:
            raise ValueError("Unsupported bound-network schema or segments")
        bound = cls(ProcessNetwork.from_dict(values["network"]), OperatingScenario.from_dict(values["scenario"]),
                    HydraulicRequirements.from_dict(values["requirements"]),
                    tuple(BoundFlowSegment.from_dict(segment) for segment in values["segments"]), _encoded(values["geometry"]))
        if bound.geometry_fingerprint != values["geometry_fingerprint"] or bound.fingerprint != values["fingerprint"]:
            raise ValueError("Bound-network fingerprints disagree with serialized inputs")
        return bound


def _geometry_number(value, name: str, *, positive: bool = True) -> float:
    # The procedural builder produces NumPy scalars; authored JSON stays strict.
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real geometry value, not Boolean")
    return _number(float(value), name, positive=positive)


def _check_bend(element, start, end) -> None:
    radius = _geometry_number(element.bend_radius, "bend radius")
    if isinstance(element.bend_angle, bool) or not isinstance(element.bend_angle, Real):
        raise ValueError("Bend angle must be a finite real geometry value, not Boolean")
    angle = _geometry_number(abs(element.bend_angle), "bend angle")
    if not 0 < abs(angle) < 360:
        raise ValueError("Bend angle magnitude must be between 0 and 360 degrees")
    geometry = element.bend_geometry
    if geometry is None:
        raise ValueError("Supported bends require explicit built bend geometry")
    _geometry_number(geometry.radius, "bend geometry radius")
    if isinstance(geometry.angle, bool) or not isinstance(geometry.angle, Real):
        raise ValueError("Bend geometry angle must be a finite real value")
    _geometry_number(abs(geometry.angle), "bend geometry angle")
    errors = []
    _validate_bend_geometry_record(element, errors)
    if errors:
        raise ValueError("; ".join(errors))
    if not math.isclose(geometry.radius, radius, rel_tol=1e-10) or not math.isclose(abs(geometry.angle), abs(angle), abs_tol=1e-9):
        raise ValueError("Contradictory bend radius/angle geometry")
    radial = np.asarray(start) - np.asarray(geometry.center)
    normal = np.asarray(geometry.normal) / np.linalg.norm(geometry.normal)
    if abs(float(np.dot(normal, radial))) > max(1e-9, radius * 1e-9):
        raise ValueError("Bend radial direction must lie in its declared circular plane")
    arc = sample_bend_geometry(start, geometry, n_segments=1)
    if not np.allclose(arc, [start, end], rtol=0, atol=max(1e-9, radius * 1e-9)):
        raise ValueError("Bend arc geometry does not match its actual endpoint nodes")
    if np.dot(np.cross(normal, radial), geometry.start_tangent) < 0:
        normal = -normal
    for point, tangent in ((start, geometry.start_tangent), (end, geometry.end_tangent)):
        actual = np.asarray(tangent) / np.linalg.norm(tangent)
        expected = np.cross(normal, np.asarray(point) - geometry.center) / radius
        if not np.allclose(actual, expected, rtol=0, atol=1e-8):
            raise ValueError("Bend tangent contradicts the actual circular arc")


def _coords(model: TubaModel, node_id: str) -> tuple[float, float, float]:
    if node_id not in model.nodes:
        raise ValueError(f"Missing node {node_id!r} in process geometry")
    values = np.asarray(model.nodes[node_id].coords, dtype=float)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise ValueError(f"Node {node_id!r} requires finite 3-D coordinates")
    return tuple(float(value) for value in values)


def _bind(network: ProcessNetwork, model: TubaModel, scenario: OperatingScenario,
          requirements: HydraulicRequirements) -> BoundProcessNetwork:
    element_ids = [element.id for element in model.elements]
    if len(element_ids) != len(set(element_ids)):
        raise ValueError("Tuba element IDs must be unique")
    pipes = [component for component in network.ordered_components if isinstance(component, PipeComponent)]
    route_ids = {component.route_id for component in pipes}
    unbound = [element.id for element in model.elements
               if element.type.startswith("pipe_") and element.route_id not in route_ids]
    if unbound:
        raise ValueError(f"All mechanical pipe elements require process bindings: {unbound}")
    geometry, route_segments = [], {}
    network_station, last_node, visited_nodes, last_bore = 0.0, None, set(), None
    for component in pipes:
        elements = [element for element in model.elements if element.route_id == component.route_id]
        if not elements:
            raise ValueError(f"Missing Tuba route {component.route_id!r}")
        for element in elements:
            if element.type not in {"pipe_straight", "pipe_bend"}:
                raise ValueError(f"Unsupported hydraulic element type {element.type!r}")
            if element.station_start is None or element.station_end is None:
                raise ValueError(f"Route {component.route_id!r} requires complete station bindings")
            _geometry_number(element.station_start, "station_start", positive=False)
            _geometry_number(element.station_end, "station_end", positive=False)
        elements.sort(key=lambda element: element.station_start)
        route_station, route_bore, associated = 0.0, None, []
        for element in elements:
            if last_node is not None and element.n1 != last_node:
                raise ValueError("Bound routes must form one contiguous forward pipe chain")
            if element.n2 in visited_nodes or element.n1 == element.n2:
                raise ValueError("Physical pipe cycles and branches are unsupported")
            visited_nodes.update((element.n1, element.n2))
            last_node = element.n2
            start, end = _coords(model, element.n1), _coords(model, element.n2)
            section = model.sections.get(element.section)
            if not isinstance(section, PipeSection):
                raise ValueError(f"Element {element.id!r} requires an actual PipeSection")
            od, wt = _geometry_number(section.OD, "outside diameter"), _geometry_number(section.WT, "wall thickness")
            bore = _number(od - 2 * wt, "bore")
            if route_bore is not None and not math.isclose(bore, route_bore, rel_tol=1e-10, abs_tol=1e-12):
                raise ValueError("A route requires uniform bore; reducers are unsupported")
            if last_bore is not None and not math.isclose(bore, last_bore, rel_tol=1e-10, abs_tol=1e-12):
                raise ValueError("Bore changes between connected routes require a supported reducer")
            route_bore = last_bore = bore
            if component.roughness_m >= bore:
                raise ValueError("Pipe roughness must be smaller than bore")
            bend = element.type == "pipe_bend"
            if bend:
                _check_bend(element, start, end)
            length = _number(element_length(model, element), "measured pipe length")
            if not math.isclose(element.station_start, route_station, abs_tol=1e-8) or not math.isclose(
                    element.station_end - element.station_start, length, rel_tol=1e-8, abs_tol=1e-9):
                raise ValueError("Recorded route stations contradict measured pipe length")
            associated.append(BoundFlowSegment(
                f"{component.id}.{element.id}", component.id, element.id, component.route_id, length, bore,
                end[2] - start[2], component.roughness_m, component.bend_loss_coefficient if bend else 0.0,
                component.bend_loss_source if bend else None, start, end, float(element.station_start),
                float(element.station_end), network_station, network_station + length, element.n1, element.n2,
            ))
            record = element.to_dict()
            record.pop("material")
            geometry.append({"element": record, "outside_diameter_m": od, "wall_thickness_m": wt,
                             "start_m": start, "end_m": end})
            route_station += length
            network_station += length
        route_segments[component.id] = associated
    segments, network_station = [], 0.0
    ordered = network.ordered_components
    for index, component in enumerate(ordered):
        if isinstance(component, PipeComponent):
            associated = route_segments[component.id]
            segments.extend(associated)
            network_station = associated[-1].network_station_end_m
        elif isinstance(component, FixedLossComponent):
            preceding = next((route_segments[c.id][-1] for c in reversed(ordered[:index]) if isinstance(c, PipeComponent)), None)
            following = next((route_segments[c.id][0] for c in ordered[index + 1:] if isinstance(c, PipeComponent)), None)
            neighbours = [segment for segment in (preceding, following) if segment is not None]
            if any(not math.isclose(segment.bore_m, component.bore_m, rel_tol=1e-10, abs_tol=1e-12) for segment in neighbours):
                raise ValueError("Fixed-loss bore must match adjoining pipes; reducers are unsupported")
            point = preceding.end_m if preceding is not None else following.start_m
            segments.append(BoundFlowSegment(component.id, component.id, None, None, 0.0, component.bore_m,
                                            0.0, 0.0, component.loss_coefficient, component.loss_source, point, point,
                                            0.0, 0.0, network_station, network_station, None, None))
    return BoundProcessNetwork(network, scenario, requirements, tuple(segments), _encoded({"elements": geometry}))
