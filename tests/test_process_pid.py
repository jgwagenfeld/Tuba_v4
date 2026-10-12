"""P&ID declarations are graph intent, never additional simulated equipment physics."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from tests.test_process_network import bound, network
from tuba.process import (
    BoundProcessNetwork, EquipmentDefinition, Instrument, PidDefinition,
    ProcessNetwork, SignalConnection,
)


def pid():
    return PidDefinition(
        equipment=(EquipmentDefinition("TK-101", "SRC-101", "tank", "Supply tank"),
                   EquipmentDefinition("FCV-101", "V-101", "control_valve", "Fixed-K approximation"),
                   EquipmentDefinition("TK-102", "SNK-101", "tank", "Receiving tank")),
        instruments=(Instrument("PT-101", "PT", "L-101.in", "Calculated inlet pressure"),
                     Instrument("FT-101", "FT", "L-101.out", "Calculated outlet mass flow"),
                     Instrument("FIC-101", "FIC", None, "Flow control intent only")),
        signals=(SignalConnection("FT-101", "FIC-101"), SignalConnection("FIC-101", "FCV-101")),
    )


def test_old_network_json_and_fingerprint_remain_byte_identical():
    _, original = bound(valve=True)
    assert "pid" not in original.network.to_dict()
    assert original.fingerprint == "703fe2d9502505bf705783db8b50884054983032b5c1896ecedc86a0aecae890"
    assert BoundProcessNetwork.from_dict(json.loads(json.dumps(original.to_dict()))) == original


def test_pid_roundtrip_preserves_graph_identity_without_changing_measured_geometry():
    model, original = bound(valve=True)
    annotated = replace(original.network, pid=pid()).bind(model, original.scenario, original.requirements)
    data = json.loads(json.dumps(annotated.to_dict()))
    assert BoundProcessNetwork.from_dict(data) == annotated
    assert data["network"]["pid"] == pid().to_dict()
    assert annotated.fingerprint != original.fingerprint
    assert annotated.geometry_fingerprint == original.geometry_fingerprint
    assert annotated.segments == original.segments
    assert annotated.network.to_dict()["components"] == original.network.to_dict()["components"]
    changed = replace(annotated.network, pid=replace(pid(), instruments=(
        replace(pid().instruments[0], port_id="L-101.out"), *pid().instruments[1:])))
    assert changed.bind(model, original.scenario, original.requirements).fingerprint != annotated.fingerprint
    data["network"]["pid"]["instruments"][0]["port_id"] = "L-101.out"
    with pytest.raises(ValueError, match="fingerprints"):
        BoundProcessNetwork.from_dict(data)
    with pytest.raises(FrozenInstanceError):
        annotated.network.pid.instruments[0].port_id = "L-101.out"


@pytest.mark.parametrize("location", ["network", "pid", "equipment", "instruments", "signals"])
def test_unknown_serialized_fields_are_rejected(location):
    data = replace(network(valve=True), pid=pid()).to_dict()
    target = data if location == "network" else data["pid"] if location == "pid" else data["pid"][location][0]
    target["unexpected"] = "not allowed"
    with pytest.raises(ValueError, match="requires exactly"):
        ProcessNetwork.from_dict(data)


@pytest.mark.parametrize("value", [None, {}, {"schema": "unknown", "equipment": [], "instruments": [], "signals": []}])
def test_present_pid_requires_a_complete_supported_declaration(value):
    data = network(valve=True).to_dict() | {"pid": value}
    with pytest.raises(ValueError):
        ProcessNetwork.from_dict(data)


@pytest.mark.parametrize("collection", ["equipment", "instruments", "signals"])
def test_pid_collections_require_typed_records_and_json_arrays(collection):
    with pytest.raises(ValueError, match="records"):
        PidDefinition(**{collection: ({},)})
    data = pid().to_dict()
    data[collection] = {}
    with pytest.raises(ValueError, match="JSON list"):
        PidDefinition.from_dict(data)


@pytest.mark.parametrize("kind,tag,port", [
    ("PT", "FT-101", "L-101.in"), ("FT", "FT-", "L-101.in"),
    ("PT", "PT-101", None), ("FIC", "FIC-101", "L-101.in"),
    ("unknown", "unknown-101", None),
])
def test_invalid_instrument_identification_or_tap_shape_is_rejected(kind, tag, port):
    with pytest.raises(ValueError):
        Instrument(tag, kind, port, "Invalid declaration")


@pytest.mark.parametrize("kind", ["tank", "pump", "heat_exchanger"])
def test_boundary_equipment_uses_existing_boundary_without_new_physics(kind):
    process = replace(network(valve=True), pid=PidDefinition(
        equipment=(EquipmentDefinition("EQ-101", "SRC-101", kind, "Boundary approximation"),)))
    assert process.pid.equipment[0].kind == kind
    assert len(process.components) == 4


@pytest.mark.parametrize("component,kind", [("L-101", "tank"), ("SRC-101", "manual_valve"), ("V-101", "pump")])
def test_equipment_cannot_change_a_components_hydraulic_meaning(component, kind):
    with pytest.raises(ValueError, match="external fixed losses"):
        replace(network(valve=True), pid=PidDefinition(
            equipment=(EquipmentDefinition("EQ-101", component, kind, "Wrong association"),)))


@pytest.mark.parametrize("case", ["unknown_component", "duplicate_component", "shadow_component", "unknown_port", "duplicate_tag"])
def test_ambiguous_or_dangling_graph_references_are_rejected(case):
    equipment, instruments = list(pid().equipment), list(pid().instruments)
    if case == "unknown_component":
        equipment[0] = replace(equipment[0], component_id="missing")
    elif case == "duplicate_component":
        equipment[2] = replace(equipment[2], component_id="SRC-101")
    elif case == "shadow_component":
        equipment[0] = replace(equipment[0], tag="L-101")
    elif case == "unknown_port":
        instruments[0] = replace(instruments[0], port_id="missing")
    else:
        equipment[0] = replace(equipment[0], tag="PT-101")
    with pytest.raises(ValueError):
        replace(network(valve=True), pid=replace(pid(), equipment=equipment, instruments=instruments))


@pytest.mark.parametrize("port", ["SRC-101.out", "L-101.in", "L-101.out", "V-101.in", "V-101.out", "SNK-101.in"])
def test_transmitters_can_tap_any_exact_declared_process_port(port):
    declaration = PidDefinition(instruments=(Instrument("PT-101", "PT", port, "Calculated pressure"),))
    assert replace(network(valve=True), pid=declaration).pid == declaration


@pytest.mark.parametrize("case", ["dangling", "duplicate", "reverse", "quantity", "cycle", "missing_input", "missing_output"])
def test_signal_direction_quantity_and_controller_assignments_are_strict(case):
    signals = list(pid().signals)
    if case == "dangling":
        signals[0] = SignalConnection("FT-102", "FIC-101")
    elif case == "duplicate":
        signals.append(signals[0])
    elif case == "reverse":
        signals[0] = SignalConnection("FIC-101", "FT-101")
    elif case == "quantity":
        signals[0] = SignalConnection("PT-101", "FIC-101")
    elif case == "cycle":
        signals.append(SignalConnection("FCV-101", "FT-101"))
    else:
        signals.pop(0 if case == "missing_input" else 1)
    with pytest.raises(ValueError):
        replace(pid(), signals=signals)


def test_control_valve_cannot_receive_two_controllers():
    with pytest.raises(ValueError, match="at most one controller"):
        replace(pid(), instruments=(*pid().instruments, Instrument("PIC-101", "PIC", None, "Pressure intent")),
                signals=(*pid().signals, SignalConnection("PT-101", "PIC-101"),
                         SignalConnection("PIC-101", "FCV-101")))


def test_controller_cannot_drive_two_valves_or_use_two_measurements():
    with pytest.raises(ValueError, match="one compatible measurement input and one valve output"):
        replace(pid(), instruments=(*pid().instruments, Instrument("FT-102", "FT", "V-101.out", "Second flow")),
                signals=(*pid().signals, SignalConnection("FT-102", "FIC-101")))
    with pytest.raises(ValueError, match="one compatible measurement input and one valve output"):
        replace(pid(), equipment=(*pid().equipment, EquipmentDefinition("FCV-102", "V-102", "control_valve", "Second valve")),
                signals=(*pid().signals, SignalConnection("FIC-101", "FCV-102")))


def test_manual_valve_is_valid_but_cannot_receive_a_controller_signal():
    declaration = PidDefinition(equipment=(EquipmentDefinition("HV-101", "V-101", "manual_valve", "Manual valve"),))
    assert replace(network(valve=True), pid=declaration).pid == declaration
    with pytest.raises(ValueError, match="compatible"):
        replace(pid(), equipment=tuple(replace(item, kind="manual_valve") if item.kind == "control_valve" else item
                                       for item in pid().equipment))
