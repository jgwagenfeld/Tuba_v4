"""Declared P&ID equipment and signal intent; no additional hydraulic physics."""

from __future__ import annotations

from dataclasses import dataclass

from .network import (
    FixedLossComponent, MassFlowSource, PressureSink, ProcessNetwork,
    _Record, _identifier, _strict,
)

PID_SCHEMA = "tuba.process-pid.v1"


@dataclass(frozen=True)
class EquipmentDefinition(_Record):
    tag: str
    component_id: str
    kind: str
    description: str

    def __post_init__(self):
        _identifier(self.tag)
        _identifier(self.component_id)
        if self.kind not in ("tank", "pump", "heat_exchanger", "manual_valve", "control_valve"):
            raise ValueError("Unsupported P&ID equipment kind")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Equipment description must be a nonempty string")


@dataclass(frozen=True)
class Instrument(_Record):
    tag: str
    kind: str
    port_id: str | None
    description: str

    def __post_init__(self):
        _identifier(self.tag)
        if self.kind not in ("PT", "FT", "PIC", "FIC"):
            raise ValueError("Supported instrument kinds are PT, FT, PIC and FIC")
        if not self.tag.startswith(self.kind + "-") or len(self.tag) <= len(self.kind) + 1:
            raise ValueError("Instrument tag must start with its kind and a hyphen, followed by an identifier")
        if self.kind in ("PT", "FT"):
            _identifier(self.port_id)
        elif self.port_id is not None:
            raise ValueError("Controller port_id must be None; controllers connect through signals")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Instrument description must be a nonempty string")


@dataclass(frozen=True)
class SignalConnection(_Record):
    source_tag: str
    target_tag: str

    def __post_init__(self):
        _identifier(self.source_tag)
        _identifier(self.target_tag)
        if self.source_tag == self.target_tag:
            raise ValueError("A signal requires different source and target tags")


@dataclass(frozen=True)
class PidDefinition(_Record):
    equipment: tuple[EquipmentDefinition, ...] = ()
    instruments: tuple[Instrument, ...] = ()
    signals: tuple[SignalConnection, ...] = ()

    def __post_init__(self):
        for name, record_type in (("equipment", EquipmentDefinition), ("instruments", Instrument),
                                  ("signals", SignalConnection)):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(type(item) is not record_type for item in values):
                raise ValueError(f"{name} must contain {record_type.__name__} records")
            object.__setattr__(self, name, tuple(values))
        tags = [item.tag for item in (*self.equipment, *self.instruments)]
        if len(tags) != len(set(tags)):
            raise ValueError("Equipment and instrument tags must be globally unique")
        component_ids = [item.component_id for item in self.equipment]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Only one equipment annotation is allowed per process component")
        if len(self.signals) != len(set(self.signals)):
            raise ValueError("Duplicate signal connections are unsupported")
        nodes = {item.tag: item for item in (*self.equipment, *self.instruments)}
        incoming, outgoing = dict.fromkeys(tags, 0), dict.fromkeys(tags, 0)
        for signal in self.signals:
            if signal.source_tag not in nodes or signal.target_tag not in nodes:
                raise ValueError("Signal references an unknown equipment or instrument tag")
            source, target = nodes[signal.source_tag], nodes[signal.target_tag]
            measurement = ((source.kind, target.kind) in (("PT", "PIC"), ("FT", "FIC")))
            actuation = source.kind in ("PIC", "FIC") and target.kind == "control_valve"
            if not measurement and not actuation:
                raise ValueError("Signals require compatible transmitter -> controller -> control_valve direction")
            incoming[target.tag] += 1
            outgoing[source.tag] += 1
        for instrument in self.instruments:
            if instrument.kind in ("PIC", "FIC") and (incoming[instrument.tag] != 1 or outgoing[instrument.tag] != 1):
                raise ValueError("Each controller requires one compatible measurement input and one valve output")
        if any(incoming[item.tag] > 1 for item in self.equipment):
            raise ValueError("Each control valve permits at most one controller")

    def validate_for(self, network: ProcessNetwork) -> None:
        components = {component.id: component for component in network.components}
        ports = {port for component in network.components
                 for port in (getattr(component, "inlet_port", None), getattr(component, "outlet_port", None))
                 if port is not None}
        for item in self.equipment:
            if item.component_id not in components:
                raise ValueError("Equipment references an unknown process component")
            if item.tag in components and item.tag != item.component_id:
                raise ValueError("Equipment tag must not shadow a different component ID")
            component = components[item.component_id]
            allowed = ((FixedLossComponent,) if item.kind in ("manual_valve", "control_valve")
                       else (MassFlowSource, PressureSink))
            if not isinstance(component, allowed):
                raise ValueError("Valves require external fixed losses; other equipment requires a source/sink boundary")
        for instrument in self.instruments:
            if instrument.tag in components:
                raise ValueError("Instrument tag must not shadow a process component ID")
            if instrument.port_id is not None and instrument.port_id not in ports:
                raise ValueError("Instrument tap references an unknown process port")

    def to_dict(self) -> dict:
        return {"schema": PID_SCHEMA, **super().to_dict()}

    @classmethod
    def from_dict(cls, data: dict):
        values = _strict(data, {"schema", "equipment", "instruments", "signals"}, cls.__name__)
        if values.pop("schema") != PID_SCHEMA:
            raise ValueError(f"Expected P&ID schema {PID_SCHEMA!r}")
        for name, record_type in (("equipment", EquipmentDefinition), ("instruments", Instrument),
                                  ("signals", SignalConnection)):
            if type(values[name]) is not list:
                raise ValueError(f"{name} must be a JSON list")
            values[name] = tuple(record_type.from_dict(item) for item in values[name])
        return cls(**values)
