"""Example import boundaries; no synthetic values are engineering results."""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.process_network.model import build_model, process_inputs
from examples.process_network.run import DEXPI_ASSUMPTIONS, run
from tuba.process import import_dexpi_segment

FIXTURE = Path(__file__).parents[1] / "examples/process_network/dexpi_reference/reference_pid.xml"


def test_route_edit_keeps_imported_connectivity_and_refreshes_measured_geometry():
    imported = import_dexpi_segment(FIXTURE, segment_id="PipingNetworkSegment2", route_id="L-101",
        roughness_m=4.6e-5, bend_loss_coefficient=0.2, bend_loss_source="Example assumption",
        study_assumptions=DEXPI_ASSUMPTIONS)
    first = process_inputs(build_model({"size": "larger", "offset_m": 1.0}), network=imported.network)
    second = process_inputs(build_model({"size": "larger", "offset_m": 3.0}), network=imported.network)
    assert first.network.to_dict() == second.network.to_dict()
    assert imported.network.pid is first.network.pid is second.network.pid is None
    assert "pid" not in first.network.to_dict()
    assert [part.id for part in first.ordered_components] == ["Nozzle2", "Pipe2", "Nozzle3"]
    assert first.scenario == second.scenario and first.requirements == second.requirements
    assert first.fingerprint != second.fingerprint
    assert sum(part.length_m for part in second.segments) - sum(part.length_m for part in first.segments) == pytest.approx(4.0)
    assert all(part.element_id is not None for part in first.segments)


def test_authored_pid_keeps_declared_taps_and_control_separate_from_steady_physics():
    bound = process_inputs(build_model({"size": "larger", "offset_m": 1.0}))
    pid = bound.network.pid
    assert [(item.tag, item.component_id, item.kind) for item in pid.equipment] == [
        ("TK-101", "SRC-101", "tank"), ("TK-102", "SNK-101", "tank"),
        ("FCV-101", "V-101", "control_valve"),
    ]
    assert [(item.tag, item.kind, item.port_id) for item in pid.instruments] == [
        ("PT-101", "PT", "L-101.in"), ("FT-101", "FT", "L-101.out"),
        ("FIC-101", "FIC", None),
    ]
    assert [(signal.source_tag, signal.target_tag) for signal in pid.signals] == [
        ("FT-101", "FIC-101"), ("FIC-101", "FCV-101"),
    ]
    assert [part.id for part in bound.ordered_components] == ["SRC-101", "L-101", "V-101", "SNK-101"]
    assert bound.scenario.mass_flow_kg_s == 10.0
    assert bound.ordered_components[2].loss_coefficient == 5.0
    assert bound.ordered_components[2].mechanical_domain == "external"


@pytest.mark.parametrize("arguments", [{"dexpi": FIXTURE}, {"segment": "PipingNetworkSegment2"}])
def test_import_requires_both_explicit_file_and_selection(tmp_path, arguments):
    output = tmp_path / "study"
    with pytest.raises(ValueError, match="both dexpi XML and segment"):
        run(output, **arguments)
    assert not output.exists()


@pytest.mark.parametrize("arguments, message", [
    ({"backend": "unknown"}, "backend must be"),
    ({"backend": "pandapipes", "omc": "omc"}, "omc is only valid"),
])
def test_conflicting_backend_options_fail_before_creating_evidence(tmp_path, arguments, message):
    output = tmp_path / "study"
    with pytest.raises(ValueError, match=message):
        run(output, **arguments)
    assert not output.exists()


def test_imported_nominal_size_cannot_be_silently_changed(tmp_path):
    output = tmp_path / "study"
    proposals = [{"id": "wrong-bore", "parent_ids": [],
                  "parameters": {"size": "small", "offset_m": 1.0}, "intent": "Undeclared nominal size edit"}]
    with pytest.raises(ValueError, match="DN80 example permits only"):
        run(output, dexpi=FIXTURE, segment="PipingNetworkSegment2", proposals=proposals)
    assert not output.exists()


def test_example_rejects_other_imported_nominal_diameters(tmp_path):
    source = tmp_path / "different-dn.xml"
    source.write_bytes(FIXTURE.read_bytes().replace(b"DN 80", b"DN 50"))
    output = tmp_path / "study"
    with pytest.raises(ValueError, match="requires an imported DN 80"):
        run(output, dexpi=source, segment="PipingNetworkSegment2")
    assert not output.exists()


@pytest.mark.parametrize("object_id, tag, changed", [
    ("PipingNetworkSegment2", "NominalDiameterNumericalValueRepresentation", "50"),
    ("PipingNetworkSegment2", "NominalDiameterTypeRepresentation", "NPS"),
    ("PipingNode3", "NominalDiameterRepresentation", "DN 50"),
])
def test_nominal_size_contradictions_fail_before_runtime(tmp_path, object_id, tag, changed):
    root = ET.fromstring(FIXTURE.read_bytes())
    obj = root.find(f".//Object[@id='{object_id}']")
    data = obj.find(f"Data[@property='{tag}']")
    if data is None:
        data = ET.SubElement(obj, "Data", property=tag)
        ET.SubElement(data, "String")
    data[0].text = changed
    source = tmp_path / "contradictory.xml"
    source.write_bytes(ET.tostring(root))
    output = tmp_path / "study"
    with pytest.raises(ValueError, match="Conflicting DN80 metadata"):
        run(output, dexpi=source, segment="PipingNetworkSegment2")
    assert not output.exists()
