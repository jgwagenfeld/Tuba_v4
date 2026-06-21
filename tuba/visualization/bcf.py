"""BCF issue exchange helpers for visualization scenes."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from tuba.refs import EntityRef
from tuba.visualization.scene import Issue, VisualizationScene


def export_bcf_topics(scene: VisualizationScene, path: str | Path) -> Path:
    """Export scene issues to a compact BCF-compatible ZIP archive."""
    target = Path(path)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bcf.version", '<Version VersionId="2.1" />\n')
        for issue in scene.issues:
            topic_dir = _topic_dir(issue)
            archive.writestr(f"{topic_dir}/markup.bcf", _issue_markup(issue))
            archive.writestr(f"{topic_dir}/viewpoint.json", json.dumps(_viewpoint_payload(scene, issue), indent=2))
    return target


def import_bcf_topics(path: str | Path) -> list[Issue]:
    """Import BCF topics exported by :func:`export_bcf_topics`."""
    issues: list[Issue] = []
    with zipfile.ZipFile(Path(path)) as archive:
        markup_names = sorted(name for name in archive.namelist() if name.endswith("/markup.bcf"))
        for name in markup_names:
            topic_dir = name.rsplit("/", 1)[0]
            markup = ET.fromstring(archive.read(name).decode("utf-8"))
            topic = markup.find("Topic")
            if topic is None:
                continue
            related_refs = [
                ref
                for ref in (_parse_ref(link.text or "") for link in topic.findall("./ReferenceLinks/ReferenceLink"))
                if ref is not None
            ]
            viewpoint = _read_json_member(archive, f"{topic_dir}/viewpoint.json")
            bcf_status = topic.attrib.get("TopicStatus", "Open")
            issue = Issue(
                id=topic.attrib.get("Guid", topic_dir),
                type=(topic.attrib.get("TopicType") or "issue").lower(),
                title=_text(topic, "Title"),
                description=_text(topic, "Description"),
                severity=_severity_from_status(bcf_status),
                status=bcf_status.lower(),
                entity_refs=related_refs,
                view_id=viewpoint.get("view_id"),
                external_refs={
                    "bcf": {
                        "topic_status": bcf_status,
                        "topic_type": topic.attrib.get("TopicType", "Issue"),
                        "related_entity_refs": [str(ref) for ref in related_refs],
                        "viewpoint": viewpoint,
                    }
                },
            )
            issues.append(issue)
    return issues


def _issue_markup(issue: Issue) -> str:
    bcf = issue.external_refs.get("bcf", {})
    topic = ET.Element(
        "Topic",
        {
            "Guid": issue.id,
            "TopicType": bcf.get("topic_type", issue.type.title()),
            "TopicStatus": bcf.get("topic_status", issue.status.title()),
        },
    )
    ET.SubElement(topic, "Title").text = issue.title
    ET.SubElement(topic, "Description").text = _issue_description(issue)
    labels = ET.SubElement(topic, "Labels")
    for label in bcf.get("labels", ["tuba"]):
        ET.SubElement(labels, "Label").text = str(label)
    links = ET.SubElement(topic, "ReferenceLinks")
    related = bcf.get("related_entity_refs") or [str(ref) for ref in issue.entity_refs]
    for ref in related:
        ET.SubElement(links, "ReferenceLink").text = str(ref)
    viewpoints = ET.SubElement(topic, "Viewpoints")
    ET.SubElement(viewpoints, "Viewpoint", {"Guid": f"{issue.id}:viewpoint", "Viewpoint": "viewpoint.json"})
    markup = ET.Element("Markup")
    markup.append(topic)
    return ET.tostring(markup, encoding="unicode") + "\n"


def _viewpoint_payload(scene: VisualizationScene, issue: Issue) -> dict:
    view = next((candidate for candidate in scene.views if candidate.id == issue.view_id), None)
    clash_metadata = issue.external_refs.get("clash", {}).get("metadata", {})
    if view is None:
        payload = {"issue_id": issue.id, "entity_refs": [str(ref) for ref in issue.entity_refs]}
        if clash_metadata:
            payload["clash_metadata"] = dict(clash_metadata)
        return payload
    payload = {
        "issue_id": issue.id,
        "view_id": view.id,
        "camera": dict(view.camera),
        "selected_object_ids": list(view.selected_object_ids),
        "active_overlay_ids": list(view.active_overlay_ids),
        "entity_refs": [str(ref) for ref in issue.entity_refs],
    }
    if clash_metadata:
        payload["clash_metadata"] = dict(clash_metadata)
    return payload


def _issue_description(issue: Issue) -> str:
    description = issue.description
    clash_metadata = issue.external_refs.get("clash", {}).get("metadata", {})
    if not clash_metadata:
        return description
    details = [
        "",
        f"Load case: {clash_metadata.get('load_case')}",
        f"Geometry state: {clash_metadata.get('geometry_state')}",
        f"Cold distance m: {clash_metadata.get('cold_distance_m')}",
        f"Operating distance m: {clash_metadata.get('operating_distance_m')}",
    ]
    return description + "\n" + "\n".join(details)


def _topic_dir(issue: Issue) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", issue.id).strip("_") or "topic"


def _parse_ref(value: str) -> EntityRef | None:
    try:
        return EntityRef.parse(value)
    except ValueError:
        return None


def _read_json_member(archive: zipfile.ZipFile, name: str) -> dict:
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except KeyError:
        return {}


def _text(parent: ET.Element, tag: str) -> str:
    child = parent.find(tag)
    return child.text if child is not None and child.text is not None else ""


def _severity_from_status(status: str) -> str:
    if status.lower() in {"closed", "resolved"}:
        return "info"
    return "warning"
