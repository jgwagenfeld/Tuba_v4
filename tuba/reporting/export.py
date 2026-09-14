"""Deterministic archive export for engineering review packages."""

from __future__ import annotations

import csv
import json
import stat
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
    _json_value,
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

    fixed_paths = {
        uri: _validated_exporter_destination(root, resolved_root, uri)
        for uri in ("review.json", "report_manifest.json", "index.html")
    }
    csv_destinations = {
        table.id: _validated_exporter_destination(
            root,
            resolved_root,
            f"reports/{table.id}.csv",
        )
        for table in review.tables
        if table.rows
    }
    owned_destinations = {
        path.resolve() for path in (*fixed_paths.values(), *csv_destinations.values())
    }

    _remove_previous_generated_artifacts(root, resolved_root)

    scene_uri = scene_writer(root) if scene_writer is not None else None
    if scene_uri is not None:
        scene_uri = _validated_scene_uri(
            root,
            resolved_root,
            scene_uri,
            owned_destinations=owned_destinations,
        )

    payload = review.to_dict()
    if scene_uri is not None:
        payload["scene_uri"] = scene_uri

    review_path = _validated_exporter_destination(
        root, resolved_root, "review.json"
    )
    _write_json(review_path, payload)

    csv_paths = {
        table.id: _write_table_csv(
            table,
            csv_destinations[table.id],
            resolved_reports_dir,
        )
        for table in review.tables
        if table.rows
    }
    manifest = _build_manifest(review, csv_paths, scene_uri=scene_uri, title=title)
    manifest_path = _validated_exporter_destination(
        root, resolved_root, "report_manifest.json"
    )
    _write_json(manifest_path, manifest)

    index_path = _validated_exporter_destination(root, resolved_root, "index.html")
    index_path.write_text(
        _render_html(review, manifest, title=title),
        encoding="utf-8",
        newline="\n",
    )
    if scene_uri is not None:
        scene_uri = _validated_scene_uri(
            root,
            resolved_root,
            scene_uri,
            owned_destinations=owned_destinations,
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
    destination: Path,
    resolved_reports_dir: Path,
) -> Path:
    _validate_report_table_id(table.id)
    candidate = destination
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
    normalized = _json_value(value)
    if isinstance(normalized, (dict, list)):
        return json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if normalized is None:
        return ""
    if isinstance(normalized, bool):
        return "true" if normalized else "false"
    return normalized


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
        # No web font: this document has to open from a zip in ten years with no
        # network. The faces are stacks, but the roles are chosen - a sans for
        # prose, a tabular mono for the columns you read down.
        ":root { color-scheme: light;",
        '  font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;',
        '  --mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace; }',
        "body { color: #18202a; margin: 2rem auto; max-width: 110rem; padding: 0 1rem;",
        "  line-height: 1.5; }",
        # Tables want the full width; sentences do not. Prose was set to 110rem
        # along with everything else, which is a line nobody can track back from.
        "h1, h2, h3, p { max-width: 68ch; }",
        "h1 { font-size: 1.75rem; letter-spacing: -.01em; margin: 0 0 .25rem; }",
        "h2 { font-size: 1.25rem; margin: 2.25rem 0 .5rem; }",
        "h3 { font-size: 1rem; margin: 1.5rem 0 .35rem; }",
        "h1, h2, h3 { break-after: avoid; line-height: 1.25; }",
        ".meta { color: #44505f; margin: 0 0 .35rem; }",
        ".units { color: #44505f; font-size: .85rem; margin: 0 0 1.75rem; }",
        ".unavailable { border-left: .25rem solid #a66b00; padding: .5rem .75rem; }",
        ".csv-link { font-size: .85rem; margin: 0 0 .4rem; }",
        ".table-wrap { margin: .4rem 0 2rem; overflow-x: auto; }",
        # The region is focusable so its off-screen columns are reachable from
        # the keyboard; a focusable thing must show that it has focus.
        ".table-wrap:focus-visible { outline: 2px solid #1c5f6b; outline-offset: 2px; }",
        # width:auto, not 100%: a four-column node table forced to full width
        # spread three coordinates across the page, which put every value an
        # inch from the row it belongs to. Capped instead, so narrow tables stay
        # compact and wide ones still compress to fit rather than overflow.
        "table { border-collapse: collapse; font-size: .85rem;",
        "  width: auto; max-width: 100%; }",
        "th, td { border: 1px solid #aeb7c2; padding: .35rem .45rem; text-align: left;",
        # Long identifiers and nested-value blobs are what made these tables
        # three times the width of a page. They break now instead.
        "  vertical-align: top; overflow-wrap: anywhere; }",
        "th { background: #eef1f5; }",
        # A column of magnitudes is read down, not across: mono, tabular, and
        # right-aligned so the decimal points line up.
        "th.num, td.num { text-align: right; font-family: var(--mono);",
        "  font-variant-numeric: tabular-nums; }",
        # Values must not break across lines; headings are prose and should.
        # "Corrosion allowance [m]" held on one line was 182px of a 1047px page.
        "td.num { white-space: nowrap; }",
        "th.num { font-family: inherit; }",
        # A floor as well as a cap: auto layout squeezed this column to 74px,
        # which broke the key names themselves down the middle - IYR2 over two
        # lines. Neither half of an entry may break.
        "td.nested { min-width: 9rem; max-width: 22rem; }",
        # One named quantity per line, name and value in their own columns, so a
        # twenty-key section mapping reads like the schedule it is.
        ".kv { list-style: none; margin: 0; padding: 0; font-size: .92em; }",
        ".kv li { display: flex; gap: .5rem; justify-content: space-between; }",
        # No rule between entries: at twenty rows in a 145px cell the hairlines
        # were noise, and text sat flush against every one of them. The two-column
        # alignment is what makes the list scannable.
        ".kv li { padding-block: .05rem; }",
        ".kv .k { color: #44505f; white-space: nowrap; }",
        ".kv li > span:last-child { font-family: var(--mono);",
        "  font-variant-numeric: tabular-nums; text-align: right;",
        "  white-space: nowrap; overflow-wrap: normal; }",
        "@media print {",
        # Landscape, because these are 10-to-17-column result tables. Portrait
        # dropped 41 of 147 columns off the right-hand edge of the page - every
        # displacement component, every moment - with nothing on the paper to
        # say anything was missing.
        "  @page { size: A4 landscape; margin: 10mm; }",
        "  body { margin: 0; max-width: none; padding: 0; }",
        "  a { color: inherit; text-decoration: none; }",
        # The scroll container cannot scroll on paper. Visible is right only
        # because the table now fits the page; it is what hid the loss before.
        "  .table-wrap { overflow: visible; }",
        # A link is dead on paper, so print where the file actually is.",
        '  .csv-link a::after { content: " (" attr(href) ")"; color: #44505f; }',
        "  th, td { padding: .2rem .25rem; }",
        "  td.nested { min-width: 8.5rem; max-width: 12rem; }",
        "  table { font-size: 7.5pt; }",
        "  tr { break-inside: avoid; }",
        "  thead { display: table-header-group; }",
        "}",
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>{escape(page_title)}</h1>",
        f'<p class="meta">Project: {escape(review.project_name)} | Status: {escape(review.analysis_status)}</p>',
        # Said once, at the top, because this page is rounded and the viewer that
        # links to it converts. Neither was stated anywhere before, so the same
        # quantity appeared in two unit systems across two surfaces of one
        # product with nothing to reconcile them.
        f'<p class="units">{escape(_units_note(review))}</p>',
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

    content.extend(("</main>", "</body>", "</html>", ""))
    return "\n".join(content)


def _units_note(review: EngineeringReviewPackage) -> str:
    """State the units this document is in, and that it rounds.

    Values are left exactly as the model and solver hold them - the CSVs and
    review.json beside this file are the same numbers unrounded, and stay
    byte-comparable with it. The viewer converts for display; this does not.
    """
    units = sorted(
        {column.unit for table in review.tables for column in table.columns if column.unit}
    )
    named = f" ({', '.join(units)})" if units else ""
    return (
        f"Values are unconverted, in the units named in each column heading{named}. "
        "Shown to six significant figures; the CSV files in reports/ carry the "
        "same values at full precision."
    )


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


def _numeric_column_ids(table: ReportTable) -> set[str]:
    """Columns whose every populated cell is a number.

    Decided from the data rather than from the presence of a unit: node and
    element counts carry no unit and are still columns you read down.
    """
    numeric: set[str] = set()
    for column in table.columns:
        values = [row.get(column.id) for row in table.rows]
        populated = [value for value in values if value is not None]
        if populated and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in populated
        ):
            numeric.add(column.id)
    return numeric


def _leaf_text(value: Any) -> str:
    """One nested entry as text. Deeper structure keeps its compact JSON."""
    if isinstance(value, (dict, list)):
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
    if isinstance(value, float):
        return _display_number(value)
    return str(value)


def _render_cell_html(value: Any) -> str:
    """Escaped cell content: a list for nested values, plain text otherwise.

    A section-property mapping is twenty named quantities. As one JSON blob it
    was technically complete and unreadable; as a list it is the same twenty
    quantities with their names next to them. The CSV cell keeps the compact
    JSON, so the machine-readable form is unchanged.
    """
    normalized = _rounded_for_display(_json_value(value))
    if isinstance(normalized, dict):
        entries = "".join(
            f'<li><span class="k">{escape(key)}</span>'
            f"<span>{escape(_leaf_text(item))}</span></li>"
            for key, item in normalized.items()
        )
        return f'<ul class="kv">{entries}</ul>' if entries else ""
    if isinstance(normalized, list):
        entries = "".join(
            f"<li><span>{escape(_leaf_text(item))}</span></li>" for item in normalized
        )
        return f'<ul class="kv">{entries}</ul>' if entries else ""
    return escape(_display_value(value))


def _render_table(table: ReportTable, *, csv_uri: str | None) -> list[str]:
    # The heading names the table, the scroll region and the table itself, so a
    # screen reader entering any of the three is told which one it is - and the
    # visible text is written once.
    heading_id = f"table-{table.id}"
    content = [f'<article><h3 id="{heading_id}">{escape(table.title)}</h3>']
    if table.unavailable_reason:
        content.append(f'<p class="unavailable">{escape(table.unavailable_reason)}</p>')
    if table.rows:
        if csv_uri is not None:
            # Named, because a report carries a dozen of these and "Download CSV"
            # a dozen times is indistinguishable read aloud or read on paper.
            content.append(
                f'<p class="csv-link"><a href="{escape(csv_uri, quote=True)}">'
                f"Download {escape(table.title)} as CSV</a></p>"
            )
        # tabindex, because the region scrolls: without it the columns past the
        # right edge could not be reached by keyboard at all.
        content.extend((
            f'<div class="table-wrap" role="region" tabindex="0"'
            f' aria-labelledby="{heading_id}">',
            f'<table aria-labelledby="{heading_id}">',
            "<thead><tr>",
        ))
        numeric = _numeric_column_ids(table)
        for column in table.columns:
            heading = column.label
            if column.unit:
                heading = f"{heading} [{column.unit}]"
            css = ' class="num"' if column.id in numeric else ""
            content.append(f'<th scope="col"{css}>{escape(heading)}</th>')
        content.extend(("</tr></thead>", "<tbody>"))
        for row in table.rows:
            content.append("<tr>")
            for column in table.columns:
                value = row.get(column.id)
                # A nested value is one unbroken blob, and auto table layout hands
                # the widest content the most width - so a 20-key section-property
                # mapping in one cell decided the width of the whole table and
                # pushed a column off the printed page. Capped, it wraps instead.
                if isinstance(_json_value(value), (dict, list)):
                    css = ' class="nested"'
                elif column.id in numeric:
                    css = ' class="num"'
                else:
                    css = ""
                content.append(f"<td{css}>{_render_cell_html(value)}</td>")
            content.append("</tr>")
        content.extend(("</tbody>", "</table>", "</div>"))
    content.append("</article>")
    return content


def _display_number(value: float) -> str:
    """Format one float for a person rather than for a round trip.

    ``str()`` on a float is ``repr``, which printed node coordinates as
    ``3.3000000000000003`` and an 11 mm displacement as
    ``0.011344418952524629`` - IEEE-754 artifacts quoted to eighteen
    significant figures in a document an engineer signs. Six significant
    figures is past any input precision a piping model carries. The CSV and
    ``review.json`` are unchanged and stay the full-precision record; this
    formatter is only ever reached by the HTML.
    """
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    text = f"{value:.6g}"
    if "e" not in text:
        return text
    # Six significant figures pushes ordinary magnitudes into exponent form: a
    # 1 054 503 N support reaction printed as 1.0545e+06. Plain decimal wherever
    # a reader can still count the digits; exponent only past that.
    if 1e-4 <= abs(value) < 1e9:
        return f"{float(text):f}".rstrip("0").rstrip(".")
    return text


def _rounded_for_display(value: Any) -> Any:
    """Round every float in a nested value, keeping the structure intact.

    A section-property mapping reaches the page as one JSON blob in one cell.
    Left at full repr it carried both problems at once: the last of the float
    noise (``0.009000000000000001``) and enough width to push the section
    schedule off the printed page on its own. Rounding to a real float first
    lets ``json.dumps`` print it cleanly - the structure, the keys and the
    ordering are untouched, and the CSV and review.json still hold the
    unrounded record.
    """
    if isinstance(value, dict):
        return {key: _rounded_for_display(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded_for_display(item) for item in value]
    if isinstance(value, float):
        return float(f"{value:.6g}")
    return value


def _display_value(value: Any) -> str:
    normalized = _json_value(value)
    if isinstance(normalized, (dict, list)):
        return json.dumps(
            _rounded_for_display(normalized),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if normalized is None:
        return ""
    if isinstance(normalized, bool):
        return "true" if normalized else "false"
    if isinstance(normalized, float):
        return _display_number(normalized)
    return str(normalized)


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


def _validated_scene_uri(
    root: Path,
    resolved_root: Path,
    value: str,
    *,
    owned_destinations: set[Path],
) -> str:
    uri = PurePosixPath(_relative_uri(value)).as_posix()
    scene_path = root / PurePosixPath(uri)
    if scene_path.is_symlink():
        raise EngineeringReviewError(
            f"Scene writer URI {uri!r} must not be a symbolic link."
        )
    resolved_scene_path = scene_path.resolve()
    _require_path_within(resolved_scene_path, resolved_root, description="scene URI")
    if resolved_scene_path in owned_destinations:
        raise EngineeringReviewError(
            f"Scene writer URI {uri!r} collides with an exporter-owned destination."
        )
    if not _is_regular_file(scene_path):
        raise EngineeringReviewError(
            f"Scene writer URI {uri!r} must identify an existing regular file "
            "in the output archive."
        )
    return uri


def _validated_exporter_destination(
    root: Path,
    resolved_root: Path,
    uri: str,
) -> Path:
    relative_uri = _relative_uri(uri)
    path = root / PurePosixPath(relative_uri)
    if path.is_symlink():
        raise EngineeringReviewError(
            f"Exporter-owned destination {relative_uri!r} must not be a symbolic link."
        )
    resolved_path = path.resolve()
    _require_path_within(
        resolved_path,
        resolved_root,
        description=f"exporter-owned destination {relative_uri!r}",
    )
    if path.exists() and not _is_regular_file(path):
        raise EngineeringReviewError(
            f"Exporter-owned destination {relative_uri!r} must be a regular file."
        )
    return path


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except OSError:
        return False


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
    if path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
