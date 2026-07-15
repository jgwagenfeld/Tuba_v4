"""Deterministic archive export for engineering review packages."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html import escape
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from tuba.reporting.model import (
    EngineeringReviewError,
    EngineeringReviewPackage,
    ReportTable,
    _validate_report_table_id,
)


_MANIFEST_SCHEMA = "engineering_review_manifest.v1"
_SCENE_METADATA_URIS = (
    "metadata/objects.json",
    "metadata/object_map.json",
    "metadata/overlays.json",
    "metadata/issues.json",
    "metadata/route_reviews.json",
    "metadata/agent_proposals.json",
    "metadata/scene_diffs.json",
    "geometry/geometry_assets.json",
)


@dataclass(frozen=True)
class EngineeringReviewOutput:
    """Paths written for one engineering review archive."""

    root: Path
    index_path: Path
    review_path: Path
    manifest_path: Path
    csv_paths: Mapping[str, Path]
    scene_uri: str | None = None


def write_engineering_review(
    review: EngineeringReviewPackage,
    path: str | Path,
    *,
    title: str | None = None,
    scene_writer: Callable[[Path], str | None] | None = None,
) -> EngineeringReviewOutput:
    """Write JSON, CSV, and printable HTML from one review package.

    The optional callback is the only scene integration seam. This module does
    not depend on a renderer or on :mod:`tuba.visualization`.
    """
    _validate_export_inputs(review)

    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    resolved_reports_dir = reports_dir.resolve()
    _require_path_within(
        resolved_reports_dir,
        resolved_root,
        description="reports directory",
    )

    _remove_previous_generated_artifacts(root, resolved_root)

    scene_uri = scene_writer(root) if scene_writer is not None else None
    if scene_uri is not None:
        scene_uri = _validated_scene_uri(root, resolved_root, scene_uri)

    payload = review.to_dict()
    if scene_uri is not None:
        payload["scene_uri"] = scene_uri

    review_path = root / "review.json"
    _write_json(review_path, payload)

    csv_paths = {
        table.id: _write_table_csv(table, reports_dir, resolved_reports_dir)
        for table in review.tables
        if table.rows
    }
    manifest = _build_manifest(review, csv_paths, scene_uri=scene_uri, title=title)
    manifest_path = root / "report_manifest.json"
    _write_json(manifest_path, manifest)

    index_path = root / "index.html"
    index_path.write_text(
        _render_html(review, manifest, title=title),
        encoding="utf-8",
        newline="\n",
    )
    return EngineeringReviewOutput(
        root=root,
        index_path=index_path,
        review_path=review_path,
        manifest_path=manifest_path,
        csv_paths=csv_paths,
        scene_uri=scene_uri,
    )


def _write_json(path: Path, data: Any) -> None:
    text = json.dumps(
        data,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_table_csv(
    table: ReportTable,
    reports_dir: Path,
    resolved_reports_dir: Path,
) -> Path:
    _validate_report_table_id(table.id)
    candidate = reports_dir / f"{table.id}.csv"
    if candidate.is_symlink():
        raise EngineeringReviewError(
            f"CSV destination for report table {table.id!r} must not be a symbolic link."
        )
    path = candidate.resolve()
    _require_path_within(
        path,
        resolved_reports_dir,
        description=f"CSV destination for report table {table.id!r}",
    )
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    column_ids = [column.id for column in table.columns]
    writer.writerow(column_ids)
    for row in table.rows:
        writer.writerow([_csv_value(row.get(column_id)) for column_id in column_ids])
    path.write_text(stream.getvalue(), encoding="utf-8", newline="\n")
    return path


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _build_manifest(
    review: EngineeringReviewPackage,
    csv_paths: Mapping[str, Path],
    *,
    scene_uri: str | None,
    title: str | None,
) -> dict[str, Any]:
    reports = {
        table.id: f"reports/{csv_paths[table.id].name}"
        for table in review.tables
        if table.id in csv_paths
    }
    return {
        "schema_version": _MANIFEST_SCHEMA,
        "package_id": review.package_id,
        "title": title or f"{review.project_name} engineering review",
        "review_uri": "review.json",
        "reports": reports,
        **({"scene_uri": scene_uri} if scene_uri is not None else {}),
    }


_SECTION_TITLES = (
    "Summary",
    "Model",
    "Load Cases",
    "Results",
    "Compliance",
    "Diagnostics",
)


def _render_html(
    review: EngineeringReviewPackage,
    manifest: Mapping[str, Any],
    *,
    title: str | None,
) -> str:
    page_title = title or f"{review.project_name} engineering review"
    sections: dict[str, list[ReportTable]] = {name: [] for name in _SECTION_TITLES}
    for table in review.tables:
        sections[_section_for_table(table)].append(table)

    content = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(page_title)}</title>",
        "<style>",
        ":root { color-scheme: light; font-family: Arial, sans-serif; }",
        "body { color: #18202a; margin: 2rem auto; max-width: 110rem; padding: 0 1rem; }",
        "h1, h2, h3 { break-after: avoid; }",
        ".meta { color: #44505f; }",
        ".unavailable { border-left: .25rem solid #a66b00; padding: .5rem .75rem; }",
        ".table-wrap { margin: 1rem 0 2rem; overflow-x: auto; }",
        "table { border-collapse: collapse; font-size: .85rem; width: 100%; }",
        "th, td { border: 1px solid #aeb7c2; padding: .35rem .45rem; text-align: left; vertical-align: top; }",
        "th { background: #eef1f5; }",
        "@media print {",
        "  body { margin: 0; max-width: none; padding: 0; }",
        "  a { color: inherit; text-decoration: none; }",
        "  .table-wrap { overflow: visible; }",
        "  table { font-size: 7pt; }",
        "  tr { break-inside: avoid; }",
        "}",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(page_title)}</h1>",
        f'<p class="meta">Project: {escape(review.project_name)} | Status: {escape(review.analysis_status)}</p>',
    ]

    reports = manifest["reports"]
    for section_title in _SECTION_TITLES:
        content.append(f"<section><h2>{section_title}</h2>")
        section_tables = sections[section_title]
        if not section_tables:
            unavailable = _unavailable_message(review, section_title)
            if unavailable:
                content.append(f'<p class="unavailable">{escape(unavailable)}</p>')
        for table in section_tables:
            content.extend(_render_table(table, csv_uri=reports.get(table.id)))
        content.append("</section>")

    content.extend(("</body>", "</html>", ""))
    return "\n".join(content)


def _section_for_table(table: ReportTable) -> str:
    if table.id in {"project_summary", "result_summary"}:
        return "Summary"
    if table.id in {"load_cases", "studies"}:
        return "Load Cases"
    if table.id == "code_compliance" or table.source == "compliance_report":
        return "Compliance"
    if table.id == "diagnostics" or table.source == "diagnostics":
        return "Diagnostics"
    if table.source == "result_state":
        return "Results"
    return "Model"


def _render_table(table: ReportTable, *, csv_uri: str | None) -> list[str]:
    content = [f"<article><h3>{escape(table.title)}</h3>"]
    if table.unavailable_reason:
        content.append(f'<p class="unavailable">{escape(table.unavailable_reason)}</p>')
    if table.rows:
        if csv_uri is not None:
            content.append(
                f'<p><a href="{escape(csv_uri, quote=True)}">Download CSV</a></p>'
            )
        content.extend(('<div class="table-wrap">', "<table>", "<thead><tr>"))
        for column in table.columns:
            heading = column.label
            if column.unit:
                heading = f"{heading} [{column.unit}]"
            content.append(f"<th>{escape(heading)}</th>")
        content.extend(("</tr></thead>", "<tbody>"))
        for row in table.rows:
            content.append("<tr>")
            for column in table.columns:
                content.append(f"<td>{escape(_display_value(row.get(column.id)))}</td>")
            content.append("</tr>")
        content.extend(("</tbody>", "</table>", "</div>"))
    content.append("</article>")
    return content


def _display_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _unavailable_message(
    review: EngineeringReviewPackage, section_title: str
) -> str | None:
    if section_title == "Results" and review.analysis_status == "not_solved":
        return (
            "Results are unavailable because this review package has not been solved "
            "by Code_Aster."
        )
    if section_title == "Compliance" and "code_compliance" not in review.tables_by_id:
        return (
            "Compliance is unavailable because no piping-code compliance report was "
            "supplied."
        )
    return None


def _relative_uri(value: str) -> str:
    uri = value.replace("\\", "/")
    parts = urlsplit(uri)
    path = PurePosixPath(parts.path)
    if (
        parts.scheme
        or parts.netloc
        or parts.query
        or parts.fragment
        or not parts.path
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise EngineeringReviewError(
            f"Archive links must be relative paths without traversal, got {value!r}."
        )
    return uri


def _validate_export_inputs(review: EngineeringReviewPackage) -> None:
    if review.scene_uri is not None:
        raise EngineeringReviewError(
            "EngineeringReviewPackage.scene_uri cannot be exported directly; "
            "supply a scene_writer that materializes the scene in the output archive."
        )

    seen_destinations: set[str] = set()
    for table in review.tables:
        _validate_report_table_id(table.id)
        destination = f"{table.id}.csv".casefold()
        if destination in seen_destinations:
            raise EngineeringReviewError(
                f"Report table id {table.id!r} collides with another portable CSV filename."
            )
        seen_destinations.add(destination)


def _validated_scene_uri(root: Path, resolved_root: Path, value: str) -> str:
    uri = _relative_uri(value)
    scene_path = (root / PurePosixPath(uri)).resolve()
    _require_path_within(scene_path, resolved_root, description="scene URI")
    if not scene_path.is_file():
        raise EngineeringReviewError(
            f"Scene writer URI {uri!r} must identify an existing file in the output archive."
        )
    return uri


def _require_path_within(path: Path, parent: Path, *, description: str) -> None:
    try:
        path.relative_to(parent)
    except ValueError as error:
        raise EngineeringReviewError(
            f"{description.capitalize()} resolves outside the output archive: {path}."
        ) from error


def _remove_previous_generated_artifacts(root: Path, resolved_root: Path) -> None:
    for path in _previous_generated_paths(root, resolved_root):
        if path.is_file() or path.is_symlink():
            path.unlink()


def _previous_generated_paths(root: Path, resolved_root: Path) -> tuple[Path, ...]:
    manifest = _read_json_object(root / "report_manifest.json")
    if manifest is None or manifest.get("schema_version") != _MANIFEST_SCHEMA:
        return ()

    paths: set[Path] = set()
    reports = manifest.get("reports")
    if isinstance(reports, Mapping):
        for table_id, uri in reports.items():
            if not isinstance(table_id, str) or not isinstance(uri, str):
                continue
            try:
                _validate_report_table_id(table_id)
            except EngineeringReviewError:
                continue
            if uri != f"reports/{table_id}.csv":
                continue
            path = _safe_existing_generated_path(root, resolved_root, uri)
            if path is not None:
                paths.add(path)

    scene_uri = manifest.get("scene_uri")
    if isinstance(scene_uri, str):
        scene_path = _safe_existing_generated_path(root, resolved_root, scene_uri)
        if scene_path is not None:
            paths.add(scene_path)
        if scene_uri == "scene.json":
            scene_payload = _read_json_object(root / scene_uri)
            if scene_payload is not None:
                assets = scene_payload.get("geometry_assets")
                if isinstance(assets, list):
                    for asset in assets:
                        if not isinstance(asset, Mapping):
                            continue
                        asset_uri = asset.get("uri")
                        if not isinstance(asset_uri, str) or not _is_geometry_payload_uri(
                            asset_uri
                        ):
                            continue
                        asset_path = _safe_existing_generated_path(
                            root, resolved_root, asset_uri
                        )
                        if asset_path is not None:
                            paths.add(asset_path)
            for uri in _SCENE_METADATA_URIS:
                path = _safe_existing_generated_path(root, resolved_root, uri)
                if path is not None:
                    paths.add(path)

    return tuple(sorted(paths, key=lambda path: path.as_posix()))


def _safe_existing_generated_path(
    root: Path,
    resolved_root: Path,
    uri: str,
) -> Path | None:
    try:
        relative_uri = _relative_uri(uri)
        path = resolved_root / PurePosixPath(relative_uri)
        resolved_path = path.resolve()
        _require_path_within(
            resolved_path, resolved_root, description="generated artifact"
        )
    except EngineeringReviewError:
        return None
    return path if path.is_file() or path.is_symlink() else None


def _is_geometry_payload_uri(uri: str) -> bool:
    path = PurePosixPath(uri)
    return (
        len(path.parts) == 2
        and path.parts[0] == "geometry"
        and path.suffix == ".json"
        and uri == f"geometry/{path.name}"
    )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
