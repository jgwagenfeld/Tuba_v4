"""Strict DEXPI 2.0.1 single-pipe import with declared nozzle boundary cuts.

This checks the supported profile, not the complete DEXPI XSD or plant semantics.
Diagram coordinates, design labels and equipment properties do not become
physical geometry, operating conditions or solver results.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from tuba.process.network import (
    Connection, MassFlowSource, PipeComponent, PressureSink, ProcessNetwork,
)


IMPORT_SCHEMA = "tuba.dexpi-segment-import.v1"
PROFILE = "dexpi-2.0.1-single-pipe-nozzle-boundaries.v1"
MAX_XML_BYTES = 8 * 1024 * 1024
IMPORTS = {prefix: f"https://data.dexpi.org/models/2.0.1/{prefix}.xml"
           for prefix in ("Core", "Plant")}
ENDPOINT_PROPERTIES = ("SourceItem", "SourceNode", "TargetItem", "TargetNode")
ASSUMPTIONS = {"boundary_conditions", "physical_layout", "fluid_service"}
TAG_PROPERTIES = {
    "LineNumber", "FluidCode", "NominalDiameterNumericalValueRepresentation",
    "NominalDiameterRepresentation", "NominalDiameterStandard",
    "NominalDiameterTypeRepresentation", "PipingClassCode", "SegmentNumber",
    "TagName", "SubTagName",
}
XML_TAGS = {
    "Model", "Import", "Object", "ObjectReference", "Components", "References",
    "Data", "DataReference", "AggregatedDataValue", "Boolean", "DateTime",
    "Double", "Integer", "String", "Undefined",
}


def _encoded(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class DexpiImport:
    """Immutable original source and verifiable provenance for one native graph."""

    network: ProcessNetwork
    source_xml: bytes
    provenance_json: str

    def __post_init__(self):
        if (type(self.network) is not ProcessNetwork or type(self.source_xml) is not bytes
                or type(self.provenance_json) is not str):
            raise ValueError("DEXPI import requires a ProcessNetwork, immutable bytes and JSON text")

    def to_dict(self) -> dict:
        """Return a defensive copy of the import provenance, including its graph."""
        try:
            record = json.loads(self.provenance_json)
        except (ValueError, RecursionError) as exc:
            raise ValueError("Invalid DEXPI import provenance JSON") from exc
        if type(record) is not dict:
            raise ValueError("DEXPI import provenance must be a JSON object")
        return record

    def verify_for(self, network: ProcessNetwork) -> None:
        """Recheck original XML and reject a changed graph or inconsistent record."""
        record = self.to_dict()
        if (type(network) is not ProcessNetwork or network.to_dict() != self.network.to_dict()
                or record.get("network") != network.to_dict()):
            raise ValueError("DEXPI import is stale for the current process network")
        if record.get("source_sha256") != hashlib.sha256(self.source_xml).hexdigest():
            raise ValueError("DEXPI source hash disagrees with import provenance")
        pipes = [component for component in network.components if type(component) is PipeComponent]
        selected = record.get("selected_segment")
        if len(pipes) != 1 or type(selected) is not dict:
            raise ValueError("Invalid DEXPI single-pipe import provenance")
        pipe = pipes[0]
        rebuilt, provenance = _build_import(
            self.source_xml, segment_id=selected.get("id"), route_id=pipe.route_id,
            roughness_m=pipe.roughness_m, bend_loss_coefficient=pipe.bend_loss_coefficient,
            bend_loss_source=pipe.bend_loss_source,
            study_assumptions=record.get("study_assumptions"),
            source_attribution=record.get("source_attribution"),
        )
        if rebuilt.to_dict() != network.to_dict() or provenance != record:
            raise ValueError("DEXPI provenance disagrees with the original source and declared study")


def _read_source(source: Path | bytes) -> bytes:
    if isinstance(source, Path):
        try:
            with source.open("rb") as stream:
                raw = stream.read(MAX_XML_BYTES + 1)
        except OSError as exc:
            raise ValueError(f"Cannot read DEXPI source: {source}") from exc
    elif type(source) is bytes:
        raw = source
    else:
        raise ValueError("DEXPI source must be a pathlib.Path or immutable bytes")
    if not raw or len(raw) > MAX_XML_BYTES:
        raise ValueError(f"DEXPI XML must contain 1 to {MAX_XML_BYTES} bytes")
    return raw


def _parse_source(raw: bytes):
    raw = _read_source(raw)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The supported DEXPI profile requires UTF-8 XML") from exc
    if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ValueError("DEXPI XML DTDs and entity declarations are forbidden")
    declaration = re.match(r"\s*<\?xml\s+[^?]*encoding\s*=\s*['\"]([^'\"]+)", text)
    if declaration and declaration.group(1).lower() not in {"utf-8", "utf8"}:
        raise ValueError("The supported DEXPI profile requires UTF-8 XML")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("Malformed DEXPI XML") from exc
    if root.tag != "Model" or any(node.tag not in XML_TAGS for node in root.iter()):
        raise ValueError("Expected unnamespaced DEXPI 2.0.1 Model XML")
    imports = root.findall("Import")
    if (len(imports) != 2 or any(list(node) for node in imports)
            or {node.get("prefix"): node.get("source") for node in imports} != IMPORTS
            or len(root.findall(".//Import")) != 2):
        raise ValueError("Expected only the exact DEXPI 2.0.1 Core and Plant imports")
    engineering = root.findall("Object")
    if (len(engineering) != 1 or engineering[0].get("type") != "Core/EngineeringModel"
            or any(node.tag not in {"Import", "Object"} for node in root)):
        raise ValueError("Expected one Core/EngineeringModel instance")
    parent = {child: node for node in root.iter() for child in node}
    ids = {}
    for node in root.iter():
        ident = node.get("id")
        if ident is not None:
            if not ident or ident in ids:
                raise ValueError(f"Duplicate or empty DEXPI ID: {ident!r}")
            ids[ident] = node
        for name in ("type", "data"):
            value = node.get(name)
            if value and not value.startswith("#") and value.split("/", 1)[0] not in IMPORTS:
                raise ValueError(f"Foreign DEXPI model reference: {value!r}")
    for node in root.iter():
        for name in ("objects", "object", "data"):
            value = node.get(name)
            if value is None:
                continue
            for reference in value.split():
                if reference.startswith("#"):
                    if reference[1:] not in ids:
                        raise ValueError(f"Unresolved DEXPI ID reference: {reference!r}")
                elif name != "data":
                    raise ValueError(f"Only local DEXPI object references are supported: {reference!r}")
    return root, ids, parent


def _endpoints(node) -> dict:
    references = node.findall("References")
    if (len(references) != 4 or {ref.get("property") for ref in references} != set(ENDPOINT_PROPERTIES)
            or any(list(ref) for ref in references)):
        raise ValueError(f"{node.get('id')!r} requires exactly one of each source/target item and node")
    result = {}
    for ref in references:
        value = ref.get("objects", "")
        if not value.startswith("#") or len(value.split()) != 1:
            raise ValueError("Each selected DEXPI endpoint requires one local ID reference")
        result[ref.get("property")] = value[1:]
    return result


def _tags(node) -> dict:
    tags = {}
    for data in node.findall("Data"):
        prop = data.get("property")
        if prop not in TAG_PROPERTIES:
            continue
        if prop in tags or len(data) != 1 or data[0].tag not in {"String", "DataReference"}:
            raise ValueError(f"Ambiguous or unsupported DEXPI tag {prop!r} on {node.get('id')!r}")
        value = data[0]
        if list(value) or (value.tag == "DataReference" and not value.get("data")):
            raise ValueError(f"Invalid DEXPI tag {prop!r}")
        tags[prop] = {"value_type": value.tag,
                      "value": value.get("data") if value.tag == "DataReference" else value.text or ""}
    return {"type": node.get("type"), "tags": tags}


def _build_import(raw: bytes, *, segment_id, route_id, roughness_m,
                  bend_loss_coefficient, bend_loss_source, study_assumptions, source_attribution=None):
    if (type(study_assumptions) is not dict or set(study_assumptions) != ASSUMPTIONS
            or any(not isinstance(value, str) or not value.strip()
                   for value in study_assumptions.values())):
        raise ValueError("Declare nonempty boundary_conditions, physical_layout and fluid_service study assumptions")
    if source_attribution is not None and (not isinstance(source_attribution, str) or not source_attribution.strip()):
        raise ValueError("Declared source_attribution must be a nonempty string")
    root, ids, parent = _parse_source(raw)
    if not isinstance(segment_id, str) or segment_id not in ids:
        raise ValueError(f"Selected DEXPI segment ID is unresolved: {segment_id!r}")
    segment = ids[segment_id]
    if segment.tag != "Object" or segment.get("type") != "Plant/Piping.PipingNetworkSegment":
        raise ValueError("Select a DEXPI PipingNetworkSegment")
    segment_group = parent.get(segment)
    system = parent.get(segment_group)
    if (segment_group is None or segment_group.tag != "Components"
            or segment_group.get("property") != "Segments" or system is None
            or system.tag != "Object" or system.get("type") != "Plant/Piping.PipingNetworkSystem"
            or not system.get("id")):
        raise ValueError("The selected segment must belong to an identified PipingNetworkSystem")
    systems_group = parent.get(system)
    plant = parent.get(systems_group)
    conceptual_group = parent.get(plant)
    if (systems_group is None or systems_group.tag != "Components"
            or systems_group.get("property") != "PipingNetworkSystems" or plant is None
            or plant.tag != "Object" or plant.get("type") != "Plant/PlantModel" or not plant.get("id")
            or conceptual_group is None or conceptual_group.tag != "Components"
            or conceptual_group.get("property") != "ConceptualModel"
            or parent.get(conceptual_group) is not root.find("Object")):
        raise ValueError("Selected piping system must belong to the EngineeringModel ConceptualModel PlantModel")
    groups = segment.findall("Components")
    if (len(groups) != 1 or groups[0].get("property") != "Connections"
            or len(groups[0]) != 1 or groups[0][0].tag != "Object"
            or groups[0][0].get("type") != "Plant/Piping.Pipe"):
        raise ValueError("Supported selected segment requires one Pipe connection and no Items or branches")
    pipe = groups[0][0]
    if (not pipe.get("id") or pipe.findall("Components")
            or any(node is not segment and node is not pipe for node in segment.iter("Object"))):
        raise ValueError("Selected Pipe requires an ID and no inline components")
    endpoints = _endpoints(segment)
    if _endpoints(pipe) != endpoints:
        raise ValueError("Selected Pipe and segment source/target endpoints conflict")
    boundaries = {}
    source_data = {segment_id: _tags(segment), system.get("id"): _tags(system), pipe.get("id"): _tags(pipe)}
    represented = {segment_id, pipe.get("id")}
    for side in ("Source", "Target"):
        item, node = ids[endpoints[f"{side}Item"]], ids[endpoints[f"{side}Node"]]
        nodes = item.findall("Components")
        owner_group = parent.get(item)
        owner = parent.get(owner_group)
        equipment_group = parent.get(owner)
        if (item.tag != "Object" or item.get("type") != "Plant/ProcessEquipment.ProcessNozzle"
                or node.tag != "Object" or node.get("type") != "Plant/Piping.PipingNode"
                or len(nodes) != 1 or nodes[0].get("property") != "Nodes"
                or len(nodes[0]) != 1 or nodes[0][0] is not node
                or owner_group is None or owner_group.tag != "Components"
                or owner_group.get("property") != "Nozzles" or owner is None
                or owner.tag != "Object" or not owner.get("id")
                or not owner.get("type", "").startswith("Plant/ProcessEquipment.")
                or equipment_group is None or equipment_group.tag != "Components"
                or equipment_group.get("property") != "TaggedPlantItems" or parent.get(equipment_group) is not plant
                or any(original is not item and original is not node for original in item.iter("Object"))):
            raise ValueError("Source and target must be single-node equipment nozzles with correct port ownership")
        boundaries[side.lower()] = {
            "item_id": item.get("id"), "node_id": node.get("id"),
            "equipment_id": owner.get("id"), "equipment_type": owner.get("type"),
        }
        for original in (item, node, owner):
            source_data[original.get("id")] = _tags(original)
        represented.update((item.get("id"), node.get("id")))
    boundary_nodes = {endpoints["SourceNode"], endpoints["TargetNode"]}
    for original in root.iter("Object"):
        if original is segment or original is pipe:
            continue
        for ref in original.findall("References"):
            if (ref.get("property") in {"SourceNode", "TargetNode"}
                    and boundary_nodes.intersection(value[1:] for value in ref.get("objects", "").split())):
                raise ValueError("Unsupported branch or additional connection at a selected boundary node")
    pipe_id = pipe.get("id")
    inlet, outlet = f"{pipe_id}.in", f"{pipe_id}.out"
    if inlet in ids or outlet in ids:
        raise ValueError("Generated pipe port aliases collide with original DEXPI IDs")
    network = ProcessNetwork(segment_id, (
        MassFlowSource(endpoints["SourceItem"], endpoints["SourceNode"]),
        PipeComponent(pipe_id, inlet, outlet, route_id, roughness_m, bend_loss_coefficient, bend_loss_source),
        PressureSink(endpoints["TargetItem"], endpoints["TargetNode"]),
    ), (Connection(endpoints["SourceNode"], inlet), Connection(outlet, endpoints["TargetNode"])))
    omitted = sorted(set(ids) - represented)
    record = {
        "schema": IMPORT_SCHEMA, "dexpi_version": "2.0.1", "profile": PROFILE,
        "validation": {"scope": "supported-profile", "xsd_validation": False,
                       "complete_semantic_validation": False},
        "source_sha256": hashlib.sha256(raw).hexdigest(), "source_size_bytes": len(raw),
        "source_model": {"name": root.get("name"), "uri": root.get("uri")},
        "imports": dict(IMPORTS),
        "selected_segment": {"id": segment_id, "type": segment.get("type"),
                             "system_id": system.get("id"), "plant_model_id": plant.get("id")},
        "source_associations": {
            "segment_id": segment_id, "pipe_id": pipe_id, "route_id": route_id, **boundaries,
            "pipe_port_aliases": {
                "inlet": {"native_port_id": inlet, "source_item_id": endpoints["SourceItem"],
                          "source_node_id": endpoints["SourceNode"]},
                "outlet": {"native_port_id": outlet, "source_item_id": endpoints["TargetItem"],
                           "source_node_id": endpoints["TargetNode"]},
            },
            "boundary_cuts": "Explicit source mass-flow and target pressure cuts at the selected nozzle ports; equipment behavior is omitted",
        },
        "source_data": source_data, "study_assumptions": dict(study_assumptions),
        "omitted_objects": {"ids": omitted, "count": len(omitted),
                            "anonymous_count": sum(node.get("id") is None for node in root.iter("Object"))},
        "network": network.to_dict(),
    }
    if source_attribution is not None:
        record["source_attribution"] = source_attribution
    return network, record


def import_dexpi_segment(source: Path | bytes, *, segment_id: str, route_id: str,
                         roughness_m: float, bend_loss_coefficient: float,
                         bend_loss_source: str, study_assumptions: dict,
                         source_attribution: str | None = None) -> DexpiImport:
    """Import one Pipe; assumptions declare nozzle cuts, physical layout and fluid.

    The source must contain the exact 2.0.1 Core/Plant imports. No remote imports
    or schemas are fetched. DN and diagram XY values never define bore or length;
    bind the returned network to an explicitly authored Tuba route separately.
    """
    raw = _read_source(source)
    network, record = _build_import(
        raw, segment_id=segment_id, route_id=route_id, roughness_m=roughness_m,
        bend_loss_coefficient=bend_loss_coefficient, bend_loss_source=bend_loss_source,
        study_assumptions=study_assumptions, source_attribution=source_attribution,
    )
    return DexpiImport(network, raw, _encoded(record))
