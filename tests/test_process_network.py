"""Portable process contracts; these tests do not supply hydraulic solver evidence."""

from dataclasses import replace
import json
import math

import pytest

from examples.process_network_starter import StarterDesign, build_model
from tuba import Model
from tuba.process import (
    BoundProcessNetwork, Connection, FixedLossComponent, HydraulicRequirements,
    MassFlowSource, OperatingScenario, PipeComponent, PressureSink, ProcessNetwork,
)


SCENARIO = OperatingScenario("operating", 10, 293.15, 300_000, 100_000, 293.15)
REQUIREMENTS = HydraulicRequirements("limits", 3, 10, 600_000, 300_000)


def network(*, valve=False, bore=0.07792):
    components = [MassFlowSource("SRC-101", "SRC-101.out"),
                  PipeComponent("L-101", "L-101.in", "L-101.out", "L-101", 4.6e-5,
                                0.2, "Explicit illustrative excess K=0.2 for each bend")]
    if valve:
        components.append(FixedLossComponent("V-101", "V-101.in", "V-101.out", bore, 5,
                                            "Explicit illustrative external valve K=5"))
    components.append(PressureSink("SNK-101", "SNK-101.in"))
    connections = tuple(Connection(a.outlet_port, b.inlet_port) for a, b in zip(components, components[1:]))
    return ProcessNetwork("water-line", tuple(components), connections)


def bound(design=StarterDesign(), *, valve=False):
    model = build_model(design)
    process = network(valve=valve, bore=model.sections["WaterPipe"].ID)
    return model, process.bind(model, SCENARIO, REQUIREMENTS)


def straight_model(*, subdivide=False):
    model = Model("Fluid pipe with structural support subdivision")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.0889, WT=0.00549)
    with model.pipe("Pipe", "Steel", route="L-101") as pipe:
        pipe.start([0, 0, 0])
        if subdivide:
            pipe.run(2)
            pipe.add_support("rest")
            pipe.run(2)
        else:
            pipe.run(4)
    return model


def test_route_edit_preserves_process_ids_and_connections_but_refreshes_actual_length():
    _, before = bound()
    _, after = bound(StarterDesign(offset_m=3))
    assert before.network == after.network
    assert before.segments[0].start_m == after.segments[0].start_m
    assert before.segments[-1].end_m == pytest.approx(after.segments[-1].end_m)
    assert sum(s.length_m for s in before.segments) == pytest.approx(8 + 2 * math.pi * 0.3)
    assert sum(s.length_m for s in after.segments) - sum(s.length_m for s in before.segments) == pytest.approx(4)
    assert before.geometry_fingerprint != after.geometry_fingerprint
    assert before.fingerprint != after.fingerprint
    assert before.fingerprint == bound()[1].fingerprint


def test_bore_comes_from_actual_section_and_edit_invalidates_freshness():
    model, before = bound()
    model.sections["WaterPipe"].OD = 0.1143
    after = before.network.bind(model, SCENARIO, REQUIREMENTS)
    assert all(segment.bore_m == pytest.approx(0.10332) for segment in after.segments)
    assert before.geometry_fingerprint != after.geometry_fingerprint
    with pytest.raises(ValueError, match="stale"):
        before.verify_for(model)


def test_geometry_order_and_station_spans_are_actual_not_list_order():
    model, before = bound()
    model.elements.reverse()
    after = before.network.bind(model, SCENARIO, REQUIREMENTS)
    assert before.fingerprint == after.fingerprint
    for segment in after.segments:
        assert segment.station_end_m - segment.station_start_m == pytest.approx(segment.length_m)
        assert segment.network_station_end_m - segment.network_station_start_m == pytest.approx(segment.length_m)
        assert segment.element_id in {element.id for element in model.elements}
    assert sum(s.local_loss_coefficient for s in after.segments) == pytest.approx(0.8)
    assert sum(s.loss_source is not None for s in after.segments) == 4


def test_bend_elevation_and_arc_length_come_from_built_geometry():
    model = straight_model()
    with model.pipe("Pipe", "Steel", route="L-102") as pipe:
        pipe.start([4, 0, 0])
        pipe.bend(radius=0.3, angle=90, plane="XZ")
        pipe.run(2)
    second = PipeComponent("L-102", "L-102.in", "L-102.out", "L-102", 4.6e-5, 0.2,
                           "Declared 90-degree bend excess loss")
    first = network().components[1]
    components = (network().components[0], second, network().components[-1], first)
    process = ProcessNetwork("two-lines", components, (
        Connection("SRC-101.out", "L-101.in"), Connection("L-101.out", "L-102.in"),
        Connection("L-102.out", "SNK-101.in")))
    result = process.bind(model, SCENARIO, REQUIREMENTS)
    assert [component.id for component in result.ordered_components] == ["SRC-101", "L-101", "L-102", "SNK-101"]
    bend = next(segment for segment in result.segments if segment.local_loss_coefficient)
    assert bend.length_m == pytest.approx(0.3 * math.pi / 2)
    assert sum(segment.height_change_m for segment in result.segments) == pytest.approx(2.3)
    assert result.segments[-1].network_station_end_m == pytest.approx(6 + 0.3 * math.pi / 2)
    assert result.segments[-1].station_end_m == pytest.approx(2 + 0.3 * math.pi / 2)


def test_support_subdivision_adds_associations_without_new_process_ports():
    original, subdivided = straight_model(), straight_model(subdivide=True)
    process = network()
    one = process.bind(original, SCENARIO, REQUIREMENTS)
    two = process.bind(subdivided, SCENARIO, REQUIREMENTS)
    assert one.network == two.network
    assert len(one.segments) == 1 and len(two.segments) == 2
    assert sum(segment.length_m for segment in one.segments) == sum(segment.length_m for segment in two.segments)
    assert len(two.network.connections) == 2
    assert two.segments[0].station_end_m == two.segments[1].station_start_m


def test_sourced_external_fixed_loss_has_no_mechanical_element():
    _, result = bound(valve=True)
    loss = result.segments[-1]
    assert loss.component_id == "V-101" and loss.element_id is None and loss.route_id is None
    assert loss.length_m == 0 and loss.local_loss_coefficient == 5
    assert loss.start_m == loss.end_m == result.segments[-2].end_m
    assert result.ordered_components[-2].mechanical_domain == "external"
    with pytest.raises(ValueError, match="in-domain"):
        replace(result.ordered_components[-2], mechanical_domain="internal")


def test_json_roundtrip_preserves_all_inputs_and_binding_identity():
    model, original = bound(valve=True)
    decoded = json.loads(json.dumps(original.to_dict()))
    reconstructed = BoundProcessNetwork.from_dict(decoded)
    assert reconstructed == original
    assert reconstructed.to_dict() == original.to_dict()
    reconstructed.verify_for(model)


def test_hydraulic_geometry_hash_excludes_new_operating_loads_and_supports():
    model, original = bound()
    model.define_operation("fluid-loads", pressure=250_000, temperature=60, ref_temperature=20)
    model.add_support(original.segments[0].n1, "anchor")
    original.verify_for(model)
    assert original.geometry_fingerprint == original.network.bind(model, SCENARIO, REQUIREMENTS).geometry_fingerprint


def test_scenario_and_requirement_changes_refresh_binding_but_not_geometry():
    model, original = bound()
    new_scenario = original.network.bind(model, replace(SCENARIO, mass_flow_kg_s=11), REQUIREMENTS)
    new_limits = original.network.bind(model, SCENARIO, replace(REQUIREMENTS, max_velocity_m_s=2))
    assert new_scenario.geometry_fingerprint == new_limits.geometry_fingerprint == original.geometry_fingerprint
    assert len({original.fingerprint, new_scenario.fingerprint, new_limits.fingerprint}) == 3


@pytest.mark.parametrize("mutation", [
    lambda model: setattr(model.elements[0], "route_id", "missing"),
    lambda model: setattr(model.elements[0], "station_end", 100),
    lambda model: setattr(model.elements[0], "station_start", None),
    lambda model: setattr(model.elements[0], "type", "pipe_tee"),
    lambda model: setattr(model.elements[1], "n1", model.elements[-1].n2),
    lambda model: setattr(model.elements[1], "bend_radius", 0),
    lambda model: setattr(model.nodes[model.elements[0].n1], "coords", [float("nan"), 0, 0]),
    lambda model: setattr(model.sections["WaterPipe"], "WT", 0.1),
])
def test_invalid_or_incomplete_actual_geometry_is_rejected(mutation):
    model = build_model(StarterDesign())
    mutation(model)
    with pytest.raises(ValueError):
        network().bind(model, SCENARIO, REQUIREMENTS)


def test_unbound_branch_cannot_be_silently_excluded():
    model = straight_model()
    with model.pipe("Pipe", "Steel", route="unbound-branch") as pipe:
        pipe.start([0, 0, 0]).run(1)
    with pytest.raises(ValueError, match="require process bindings"):
        network().bind(model, SCENARIO, REQUIREMENTS)


def test_missing_route_binding_and_duplicate_whole_route_bindings_are_rejected():
    process = network()
    missing = replace(process.components[1], route_id="unknown")
    with pytest.raises(ValueError):
        replace(process, components=(process.components[0], missing, process.components[-1])).bind(
            build_model(StarterDesign()), SCENARIO, REQUIREMENTS)
    second = replace(process.components[1], id="L2", inlet_port="L2.in", outlet_port="L2.out")
    with pytest.raises(ValueError, match="distinct whole-route"):
        ProcessNetwork("duplicate", (*process.components[:-1], second, process.components[-1]), (
            process.connections[0], Connection("L-101.out", "L2.in"), Connection("L2.out", "SNK-101.in")))


@pytest.mark.parametrize("mutation, message", [
    (lambda data: data["components"][1].update(kind="pump"), "Unsupported"),
    (lambda data: data["components"][1].update(id="SRC-101"), "IDs must be unique"),
    (lambda data: data["components"][1].update(inlet_port="SRC-101.out"), "Port IDs"),
    (lambda data: data["connections"].append(data["connections"][0]), "Branches"),
    (lambda data: data["connections"][0].update(target_port="unknown"), "unknown port"),
    (lambda data: data["connections"][0].update(target_port="L-101.out"), "outlet to an inlet"),
    (lambda data: data["connections"].pop(), "Every process port"),
    (lambda data: data.update(extra="unknown"), "requires exactly"),
    (lambda data: data["components"][1].pop("roughness_m"), "requires exactly"),
])
def test_invalid_graph_and_unknown_or_missing_json_inputs_are_rejected(mutation, message):
    data = network().to_dict()
    mutation(data)
    with pytest.raises(ValueError, match=message):
        ProcessNetwork.from_dict(data)


def test_disconnected_cycle_is_not_accepted_as_a_second_circuit():
    original = network()
    a = PipeComponent("A", "A.in", "A.out", "A", 1e-5, 0, "Declared no bend loss")
    b = PipeComponent("B", "B.in", "B.out", "B", 1e-5, 0, "Declared no bend loss")
    with pytest.raises(ValueError, match="cycles"):
        ProcessNetwork("cycle", (*original.components, a, b),
                       (*original.connections, Connection("A.out", "B.in"), Connection("B.out", "A.in")))


@pytest.mark.parametrize("changes", [
    {"mass_flow_kg_s": 0}, {"sink_pressure_pa": float("nan")}, {"source_temperature_k": True},
    {"external_pressure_pa": -1}, {"mechanical_reference_temperature_k": 0}, {"medium": "steam"},
])
def test_invalid_operating_inputs_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(SCENARIO, **changes)


def test_units_and_pressure_reference_cannot_be_coerced_silently():
    data = SCENARIO.to_dict()
    data["units"]["sink_pressure_pa"] = "bar"
    with pytest.raises(ValueError, match="SI units"):
        OperatingScenario.from_dict(data)
    data = REQUIREMENTS.to_dict()
    data["pressure_reference"] = "gauge"
    with pytest.raises(ValueError, match="absolute"):
        HydraulicRequirements.from_dict(data)
    with pytest.raises(ValueError):
        replace(REQUIREMENTS, min_delivered_mass_flow_kg_s=True)


def test_loss_source_and_fixed_loss_bore_are_explicit_inputs():
    with pytest.raises(ValueError, match="source"):
        FixedLossComponent("V", "V.in", "V.out", 0.08, 5, "")
    with pytest.raises(ValueError, match="source"):
        replace(network().components[1], bend_loss_source="")
    model = build_model(StarterDesign())
    with pytest.raises(ValueError, match="Fixed-loss bore"):
        network(valve=True, bore=0.01).bind(model, SCENARIO, REQUIREMENTS)


def test_tampered_bound_snapshot_cannot_claim_original_fingerprint():
    _, original = bound()
    data = original.to_dict()
    data["scenario"]["mass_flow_kg_s"] = 9
    with pytest.raises(ValueError, match="fingerprints"):
        BoundProcessNetwork.from_dict(data)


def test_real_procedural_example_accepts_native_numpy_bend_stations():
    from examples.process_network.model import build_model as build_circuit, process_inputs

    model = build_circuit({"size": "larger", "offset_m": 1.0})
    result = process_inputs(model)
    assert len(result.segments) == len(model.elements) + 1
    assert sum(s.length_m for s in result.segments) == pytest.approx(8 + 2 * math.pi * 0.3)
    result.verify_for(model)


@pytest.mark.parametrize("corruption", ["end_node", "center", "normal", "tangent", "angle"])
def test_freshly_rebound_inconsistent_bend_geometry_cannot_be_used(corruption):
    model = build_model(StarterDesign())
    bend = next(element for element in model.elements if element.type == "pipe_bend")
    if corruption == "end_node":
        model.nodes[bend.n2].coords[0] += 0.01
    elif corruption == "center":
        bend.bend_geometry.center[0] += 0.01
    elif corruption == "normal":
        bend.bend_geometry.normal = [1, 0, 0]
    elif corruption == "tangent":
        bend.bend_geometry.end_tangent = [0, 0, 1]
    else:
        bend.bend_angle = None
    with pytest.raises(ValueError):
        network().bind(model, SCENARIO, REQUIREMENTS)


def test_external_absolute_vacuum_is_valid_and_still_part_of_binding():
    model, original = bound()
    vacuum = replace(SCENARIO, external_pressure_pa=0)
    changed = original.network.bind(model, vacuum, REQUIREMENTS)
    assert changed.scenario.external_pressure_pa == 0
    assert changed.geometry_fingerprint == original.geometry_fingerprint
    assert changed.fingerprint != original.fingerprint


def test_external_loss_cannot_hide_equipment_inside_the_mechanical_pipe_chain():
    with pytest.raises(ValueError, match="outside the modeled pipe chain"):
        ProcessNetwork("Circuit", (
            MassFlowSource("SRC", "SRC.out"),
            PipeComponent("A", "A.in", "A.out", "A", 0.0, 0.0, "no bend losses"),
            FixedLossComponent("V", "V.in", "V.out", 0.08, 5.0, "declared loss", "external"),
            PipeComponent("B", "B.in", "B.out", "B", 0.0, 0.0, "no bend losses"),
            PressureSink("SNK", "SNK.in"),
        ), (Connection("SRC.out", "A.in"), Connection("A.out", "V.in"),
            Connection("V.out", "B.in"), Connection("B.out", "SNK.in")))


def test_bore_change_between_routes_requires_explicit_supported_reducer():
    model = straight_model()
    model.add_pipe_section("Larger", OD=0.1143, WT=0.00549)
    with model.pipe("Larger", "Steel", route="L-102") as pipe:
        pipe.start([4, 0, 0]).run(2)
    original = network()
    second = PipeComponent("L-102", "L-102.in", "L-102.out", "L-102", 4.6e-5, 0,
                           "Declared no bends on second route")
    process = ProcessNetwork("bore-change", (*original.components[:-1], second, original.components[-1]), (
        Connection("SRC-101.out", "L-101.in"), Connection("L-101.out", "L-102.in"),
        Connection("L-102.out", "SNK-101.in")))
    with pytest.raises(ValueError, match="supported reducer"):
        process.bind(model, SCENARIO, REQUIREMENTS)
