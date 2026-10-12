"""Import contracts only: compact XML below is explicitly synthetic, not solver evidence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tuba.process import ProcessNetwork
from tuba.process import dexpi
from tuba.process.dexpi import DexpiImport, import_dexpi_segment


ASSUMPTIONS = {
    "boundary_conditions": "Declared mass-flow source and pressure sink cuts at the two nozzles",
    "physical_layout": "Physical route and section authored in Tuba; diagram XY is not geometry",
    "fluid_service": "Explicit single-phase liquid-water study; the MNb label is not fluid validation",
}
INPUTS = dict(segment_id="Segment2", route_id="physical-route", roughness_m=4.6e-5,
              bend_loss_coefficient=0.2, bend_loss_source="Declared illustrative bend excess K",
              study_assumptions=ASSUMPTIONS)


def synthetic_xml():
    """Small fabricated input for mutation tests, using the supported XML structure."""
    return b'''<Model name="synthetic-contract-fixture" uri="urn:synthetic:test">
      <Import prefix="Core" source="https://data.dexpi.org/models/2.0.1/Core.xml"/>
      <Import prefix="Plant" source="https://data.dexpi.org/models/2.0.1/Plant.xml"/>
      <Object type="Core/EngineeringModel">
        <Components property="ConceptualModel"><Object id="Plant1" type="Plant/PlantModel">
          <Components property="PipingNetworkSystems">
            <Object id="System2" type="Plant/Piping.PipingNetworkSystem">
              <Data property="LineNumber"><String>SYNTHETIC-LINE</String></Data>
              <Data property="FluidCode"><String>MNb</String></Data>
              <Data property="PipingClassCode"><String>SYNTHETIC-CLASS</String></Data>
              <Components property="Segments">
                <Object id="Segment2" type="Plant/Piping.PipingNetworkSegment">
                  <Components property="Connections">
                    <Object id="Pipe2" type="Plant/Piping.Pipe">
                      <References property="SourceItem" objects="#Nozzle2"/>
                      <References property="SourceNode" objects="#PipingNode3"/>
                      <References property="TargetItem" objects="#Nozzle3"/>
                      <References property="TargetNode" objects="#PipingNode4"/>
                    </Object>
                  </Components>
                  <Data property="FluidCode"><String>MNb</String></Data>
                  <Data property="NominalDiameterRepresentation"><String>DN 80</String></Data>
                  <Data property="NominalDiameterNumericalValueRepresentation"><String>80</String></Data>
                  <References property="SourceItem" objects="#Nozzle2"/>
                  <References property="SourceNode" objects="#PipingNode3"/>
                  <References property="TargetItem" objects="#Nozzle3"/>
                  <References property="TargetNode" objects="#PipingNode4"/>
                </Object>
              </Components>
            </Object>
          </Components>
          <Components property="TaggedPlantItems">
            <Object id="Pump1" type="Plant/ProcessEquipment.CentrifugalPump">
              <Data property="TagName"><String>SYNTHETIC-PUMP</String></Data>
              <Components property="Nozzles"><Object id="Nozzle2" type="Plant/ProcessEquipment.ProcessNozzle">
                <Components property="Nodes"><Object id="PipingNode3" type="Plant/Piping.PipingNode"/></Components>
              </Object></Components>
            </Object>
            <Object id="HeatExchanger1" type="Plant/ProcessEquipment.PlateHeatExchanger">
              <Data property="TagName"><String>SYNTHETIC-HX</String></Data>
              <Components property="Nozzles"><Object id="Nozzle3" type="Plant/ProcessEquipment.ProcessNozzle">
                <Components property="Nodes"><Object id="PipingNode4" type="Plant/Piping.PipingNode"/></Components>
              </Object></Components>
            </Object>
          </Components>
        </Object></Components>
      </Object>
    </Model>'''


def imported(raw=None, **overrides):
    return import_dexpi_segment(synthetic_xml() if raw is None else raw, **{**INPUTS, **overrides})


def test_native_graph_preserves_original_ids_and_explicit_port_aliases():
    result = imported()
    result.verify_for(result.network)
    network = result.network
    assert [component.id for component in network.ordered_components] == ["Nozzle2", "Pipe2", "Nozzle3"]
    assert [(link.source_port, link.target_port) for link in network.connections] == [
        ("PipingNode3", "Pipe2.in"), ("Pipe2.out", "PipingNode4")]
    record = result.to_dict()
    assert ProcessNetwork.from_dict(record["network"]) == network
    assert record["source_sha256"] == hashlib.sha256(synthetic_xml()).hexdigest()
    assert record["source_size_bytes"] == len(result.source_xml)
    assert record["source_associations"]["pipe_port_aliases"]["inlet"] == {
        "native_port_id": "Pipe2.in", "source_item_id": "Nozzle2", "source_node_id": "PipingNode3"}
    assert record["source_associations"]["source"]["equipment_id"] == "Pump1"
    assert record["source_associations"]["target"]["equipment_id"] == "HeatExchanger1"
    assert record["validation"] == {
        "scope": "supported-profile", "xsd_validation": False, "complete_semantic_validation": False}
    assert record["omitted_objects"]["count"] == len(record["omitted_objects"]["ids"])
    assert "Pump1" in record["omitted_objects"]["ids"]
    assert "Pipe2" not in record["omitted_objects"]["ids"]
    assert "boundary_cuts" in record["source_associations"]


def test_official_full_reference_preserves_line_and_equipment_metadata():
    fixture = Path(os.environ.get("TUBA_DEXPI_REFERENCE_XML", Path(__file__).resolve().parents[1]
                   / "examples/process_network/dexpi_reference/reference_pid.xml"))
    assert fixture.is_file(), "The exact official DEXPI 2.0.1 reference fixture must be retained"
    result = imported(fixture, segment_id="PipingNetworkSegment2")
    result.verify_for(result.network)
    record = result.to_dict()
    assert result.source_xml == fixture.read_bytes()
    assert [component.id for component in result.network.components] == ["Nozzle2", "Pipe2", "Nozzle3"]
    assert result.network.components[0].outlet_port == "PipingNode3"
    assert result.network.components[-1].inlet_port == "PipingNode4"
    assert record["selected_segment"]["system_id"] == "PipingNetworkSystem2"
    assert record["selected_segment"]["plant_model_id"] == "PlantModel1"
    data = record["source_data"]
    assert data["PipingNetworkSystem2"]["tags"]["LineNumber"]["value"] == "47122"
    assert data["PipingNetworkSegment2"]["tags"]["NominalDiameterRepresentation"]["value"] == "DN 80"
    assert data["PipingNetworkSegment2"]["tags"]["FluidCode"]["value"] == "MNb"
    assert data["PipingNetworkSegment2"]["tags"]["PipingClassCode"]["value"] == "75HB13"
    assert data["CentrifugalPump1"]["tags"]["TagName"]["value"] == "P4711"
    assert data["PlateHeatExchanger1"]["tags"]["TagName"]["value"] == "H1007"
    assert record["omitted_objects"]["count"] == 292
    assert record["omitted_objects"]["anonymous_count"] > 1000
    with pytest.raises(ValueError, match="one Pipe|inline|nozzle"):
        imported(fixture, segment_id="PipingNetworkSegment1")


def test_labels_and_diagram_values_do_not_define_physical_dimensions():
    root = ET.fromstring(synthetic_xml())
    root.find(".//Data[@property='NominalDiameterRepresentation']/String").text = "DN 15"
    position = ET.SubElement(root.find("Object"), "Data", property="DiagramPositionX")
    ET.SubElement(position, "Double").text = "1000000"
    after = imported(ET.tostring(root))
    assert after.network == imported().network
    assert after.to_dict()["source_sha256"] != imported().to_dict()["source_sha256"]


def test_import_and_provenance_are_immutable_and_defensive():
    assumptions = dict(ASSUMPTIONS)
    result = imported(study_assumptions=assumptions)
    assumptions["physical_layout"] = "changed caller data"
    record = result.to_dict()
    record["source_associations"]["source"]["item_id"] = "changed copy"
    record["study_assumptions"]["boundary_conditions"] = "changed copy"
    assert result.to_dict()["study_assumptions"] == ASSUMPTIONS
    result.verify_for(result.network)
    with pytest.raises(FrozenInstanceError):
        result.source_xml = b"changed"


def test_declared_attribution_is_preserved_without_licensing_inference():
    attribution = "Synthetic source declared by caller; no inferred license"
    result = imported(source_attribution=attribution)
    assert result.to_dict()["source_attribution"] == attribution
    result.verify_for(result.network)
    assert "source_attribution" not in imported().to_dict()
    for bad in ("", " ", 1):
        with pytest.raises(ValueError, match="source_attribution"):
            imported(source_attribution=bad)
    record = result.to_dict()
    record["source_attribution"] = 1
    with pytest.raises(ValueError, match="source_attribution"):
        replace(result, provenance_json=json.dumps(record)).verify_for(result.network)


@pytest.mark.parametrize("field", ["source_associations", "source_data", "omitted_objects", "validation", "selected_segment"])
def test_source_derived_provenance_changes_are_rejected(field):
    result = imported()
    record = result.to_dict()
    record[field] = {}
    forged = replace(result, provenance_json=json.dumps(record))
    with pytest.raises(ValueError, match="provenance|segment ID"):
        forged.verify_for(result.network)


def test_changed_network_raw_bytes_hash_and_invalid_json_are_rejected():
    result = imported()
    changed = replace(result.network, components=(
        result.network.components[0], replace(result.network.components[1], route_id="changed"),
        result.network.components[2]))
    with pytest.raises(ValueError, match="stale"):
        result.verify_for(changed)
    with pytest.raises(ValueError, match="hash"):
        replace(result, source_xml=result.source_xml + b"\n").verify_for(result.network)
    record = result.to_dict()
    record["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        replace(result, provenance_json=json.dumps(record)).verify_for(result.network)
    for bad in ("null", "[]", "invalid"):
        with pytest.raises(ValueError, match="JSON"):
            replace(result, provenance_json=bad).verify_for(result.network)
    with pytest.raises(ValueError, match="immutable"):
        DexpiImport(result.network, bytearray(result.source_xml), result.provenance_json)


@pytest.mark.parametrize("case", [
    "duplicate-id", "unresolved-reference", "conflicting-endpoint", "wrong-port-owner",
    "non-nozzle-boundary", "selected-inline-item", "pipe-inline-item", "multiple-pipes",
    "multiple-nozzle-nodes", "boundary-branch", "mixed-version", "foreign-import",
    "foreign-type", "duplicate-tag", "pipe-port-alias-collision", "wrong-conceptual-owner",
    "wrong-system-owner", "nested-physical-object", "nonlocal-reference", "omitted-dangling-reference",
    "equipment-outside-selected-plant", "nested-nozzle-item",
])
def test_unsupported_or_inconsistent_xml_fails_closed(case):
    root = ET.fromstring(synthetic_xml())
    segment = root.find(".//Object[@id='Segment2']")
    pipe = root.find(".//Object[@id='Pipe2']")
    if case == "duplicate-id":
        root.find("Object").append(deepcopy(pipe))
    elif case == "unresolved-reference":
        segment.find("References[@property='SourceNode']").set("objects", "#missing")
    elif case == "conflicting-endpoint":
        pipe.find("References[@property='SourceNode']").set("objects", "#PipingNode4")
    elif case == "wrong-port-owner":
        for original in (segment, pipe):
            original.find("References[@property='SourceNode']").set("objects", "#PipingNode4")
    elif case == "non-nozzle-boundary":
        for original in (segment, pipe):
            original.find("References[@property='SourceItem']").set("objects", "#Pump1")
    elif case in {"selected-inline-item", "pipe-inline-item", "nested-physical-object"}:
        owner = pipe if case == "pipe-inline-item" else segment
        group = ET.SubElement(owner, "Data" if case == "nested-physical-object" else "Components", property="Items")
        ET.SubElement(group, "Object", id="Valve1", type="Plant/Piping.GlobeValve")
    elif case == "multiple-pipes":
        extra = deepcopy(pipe)
        extra.set("id", "ExtraPipe")
        segment.find("Components").append(extra)
    elif case == "multiple-nozzle-nodes":
        ET.SubElement(root.find(".//Object[@id='Nozzle2']/Components"), "Object",
                      id="ExtraNode", type="Plant/Piping.PipingNode")
    elif case == "boundary-branch":
        extra = deepcopy(pipe)
        extra.set("id", "ExtraPipe")
        root.find(".//Object[@id='Plant1']/Components").append(extra)
    elif case == "mixed-version":
        root.find("Import").set("source", "https://data.dexpi.org/models/2.0.0/Core.xml")
    elif case == "foreign-import":
        ET.SubElement(root, "Import", prefix="Other", source="https://example.invalid/model.xml")
    elif case == "foreign-type":
        pipe.set("type", "Other/Piping.Pipe")
    elif case == "duplicate-tag":
        segment.append(deepcopy(segment.find("Data")))
    elif case == "pipe-port-alias-collision":
        ET.SubElement(root.find("Object"), "Object", id="Pipe2.in", type="Plant/Piping.PipingNode")
    elif case == "wrong-conceptual-owner":
        root.find("Object/Components").set("property", "Diagrams")
    elif case == "wrong-system-owner":
        root.find(".//Object[@id='Plant1']/Components").set("property", "Equipment")
    elif case == "nonlocal-reference":
        pipe.find("References").set("objects", "Nozzle2")
    elif case == "omitted-dangling-reference":
        ET.SubElement(root.find(".//Object[@id='Pump1']"), "References", property="Unimported", objects="#missing")
    elif case == "equipment-outside-selected-plant":
        plant = root.find(".//Object[@id='Plant1']")
        equipment = plant.find("Components[@property='TaggedPlantItems']")
        plant.remove(equipment)
        root.find("Object").append(equipment)
    elif case == "nested-nozzle-item":
        hidden = ET.SubElement(root.find(".//Object[@id='Nozzle2']"), "Data", property="Hidden")
        ET.SubElement(hidden, "Object", id="HiddenBranch", type="Plant/Piping.PipingNode")
    with pytest.raises(ValueError):
        imported(ET.tostring(root))


@pytest.mark.parametrize("raw", [
    b"", b"<Model>", b"<PlantModel/>", b'<Model xmlns="urn:foreign"/>',
    b'<!DOCTYPE Model [<!ENTITY secret SYSTEM "file:///secrets">]><Model>&secret;</Model>',
    b'<!DOCTYPE Model SYSTEM "https://example.invalid/remote.dtd"><Model/>',
    synthetic_xml().decode().encode("utf-16"),
])
def test_invalid_or_untrusted_xml_is_rejected(raw):
    with pytest.raises(ValueError):
        imported(raw)


def test_bounded_file_read_and_source_types(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.xml"
    path.write_bytes(synthetic_xml())
    assert imported(path).source_xml == synthetic_xml()
    monkeypatch.setattr(dexpi, "MAX_XML_BYTES", len(synthetic_xml()) - 1)
    for source in (synthetic_xml(), path, str(path), bytearray(synthetic_xml()), tmp_path / "missing.xml"):
        with pytest.raises(ValueError):
            imported(source)


@pytest.mark.parametrize("assumptions", [None, {}, {**ASSUMPTIONS, "fluid_service": ""},
                                          {**ASSUMPTIONS, "physical_layout": 1},
                                          {**ASSUMPTIONS, "undeclared": "extra"}])
def test_study_assumptions_must_be_explicit(assumptions):
    with pytest.raises(ValueError, match="study assumptions"):
        imported(study_assumptions=assumptions)


@pytest.mark.parametrize("overrides", [{"roughness_m": -1}, {"roughness_m": True},
                                      {"bend_loss_coefficient": float("nan")},
                                      {"bend_loss_source": ""}, {"route_id": "bad route"},
                                      {"segment_id": "missing"}, {"segment_id": "Pump1"}])
def test_declared_native_inputs_keep_existing_validation(overrides):
    with pytest.raises(ValueError):
        imported(**overrides)
