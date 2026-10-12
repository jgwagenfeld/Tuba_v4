"""Schematic projection tests; hydraulic numbers below are portable fixtures."""

from dataclasses import replace
import math

import pytest

from examples.process_network.model import build_model, process_inputs
from tuba.process.review import attach_process_review
from tuba.process.workflow import hydraulic_check_specs
from tuba.visualization import SceneRequest, build_visualization_scene


def projection(offset=1.0):
    model = build_model({"size": "larger", "offset_m": offset})
    original = process_inputs(model)
    network = replace(original.network, components=tuple(reversed(original.network.components)),
                      connections=tuple(reversed(original.network.connections)))
    bound = network.bind(model, original.scenario, original.requirements)
    payload = {
        "schema": "tuba.process.review.v1", "basis": "pandapipes",
        "operation": bound.scenario.id, "scenario_id": bound.scenario.id,
        "bound_fingerprint": bound.fingerprint, "geometry_fingerprint": bound.geometry_fingerprint,
        "segments": [{"segment_id": segment.segment_id, "component_id": segment.component_id,
                      "element_id": segment.element_id, "velocity_m_s": 1.0,
                      "pressure_in_pa": 301000.0, "pressure_out_pa": 300000.0,
                      "temperature_k": 333.15} for segment in bound.segments],
    }
    return build_visualization_scene(SceneRequest(model)), bound, payload


def test_schematic_follows_connectivity_and_retains_actual_route_and_declared_inputs():
    scene, bound, payload = projection()
    attach_process_review(scene, payload, bound=bound)
    schematic = scene.extra["process"]["schematic"]
    assert "schematic" not in payload
    assert schematic["schema"] == "tuba.process.schematic.v1"
    assert schematic["network_id"] == bound.network.id
    assert schematic["bound_fingerprint"] == bound.fingerprint
    assert [component["id"] for component in schematic["components"]] == [
        "SRC-101", "L-101", "V-101", "SNK-101"]
    source, pipe, loss, sink = schematic["components"]
    assert source["element_ids"] == loss["element_ids"] == sink["element_ids"] == []
    assert source == bound.ordered_components[0].to_dict() | {"element_ids": [], "velocity_check_ids": []}
    assert loss == bound.ordered_components[2].to_dict() | {
        "element_ids": [], "velocity_check_ids": ["flow.velocity.9"]}
    assert sink == bound.ordered_components[3].to_dict() | {"element_ids": [], "velocity_check_ids": []}
    velocity_specs = hydraulic_check_specs(bound)[:len(bound.segments)]
    assert pipe["velocity_check_ids"] + loss["velocity_check_ids"] == [spec.id for spec in velocity_specs]
    assert [list(spec.target_refs) for spec in velocity_specs[:-1]] == [
        [f"element:{element_id}"] for element_id in pipe["element_ids"]]
    assert velocity_specs[-1].target_refs == ()
    assert pipe["route_id"] == "L-101"
    assert pipe["element_ids"] == [segment.element_id for segment in bound.segments if segment.element_id]
    assert pipe["length_m"] == pytest.approx(8 + 4 * math.pi * 0.3 / 2)
    assert pipe["bore_m"] == pytest.approx(0.0889 - 2 * 0.00549)
    assert schematic["connections"] == [connection.to_dict() for connection in bound.network.connections]
    assert schematic["scenario"] == bound.scenario.to_dict()
    assert schematic["requirements"] == bound.requirements.to_dict()
    assert scene.extra["process"]["segments"] == payload["segments"]


def test_schematic_route_length_changes_with_bound_geometry():
    lengths = []
    for offset in (1.0, 3.0):
        scene, bound, payload = projection(offset)
        attach_process_review(scene, payload, bound=bound)
        lengths.append(scene.extra["process"]["schematic"]["components"][1]["length_m"])
    assert lengths[1] - lengths[0] == pytest.approx(4.0)


@pytest.mark.parametrize("change", ["geometry", "network", "scenario"])
def test_schematic_rejects_stale_or_foreign_bound_inputs_before_mutating_scene(change):
    scene, bound, payload = projection()
    if change == "geometry":
        _, bound, _ = projection(3.0)
    elif change == "network":
        bound = replace(bound, network=replace(bound.network, id="Foreign"))
    else:
        payload["scenario_id"] = "Foreign"
    with pytest.raises(ValueError, match="evaluated network/scenario"):
        attach_process_review(scene, payload, bound=bound)
    assert "process" not in scene.extra
    assert not scene.result_fields


@pytest.mark.parametrize("change", ["external_missing", "external_first", "duplicate_segment", "component", "segment_id", "element"])
def test_schematic_rejects_incomplete_or_foreign_result_associations(change):
    scene, bound, payload = projection()
    if change == "external_missing":
        payload["segments"] = [row for row in payload["segments"] if row["element_id"]]
    elif change == "external_first":
        payload["segments"] = payload["segments"][-1:] + payload["segments"][:-1]
    elif change == "duplicate_segment":
        payload["segments"].append(dict(payload["segments"][-1]))
    else:
        key = {"component": "component_id", "segment_id": "segment_id", "element": "element_id"}[change]
        payload["segments"][0][key] = "Foreign"
    with pytest.raises(ValueError, match="associations|cover"):
        attach_process_review(scene, payload, bound=bound)
    assert "process" not in scene.extra
    assert not scene.result_fields


@pytest.mark.parametrize("declared", [False, True])
def test_pid_projection_preserves_declaration_and_never_changes_measured_results(declared):
    from tests.test_process_pid import pid

    scene, bound, payload = projection()
    bound = replace(bound, network=replace(bound.network, pid=pid() if declared else None))
    payload["bound_fingerprint"] = bound.fingerprint
    attach_process_review(scene, payload, bound=bound)
    schematic = scene.extra["process"]["schematic"]
    if declared:
        assert schematic["pid"] == pid().to_dict()
        assert "value" not in schematic["pid"]["instruments"][2]
    else:
        assert "pid" not in schematic
    assert scene.extra["process"]["segments"] == payload["segments"]
    assert "schematic" not in payload
