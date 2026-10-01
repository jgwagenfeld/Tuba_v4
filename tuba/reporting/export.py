"""Deterministic archive export for engineering review packages."""

from __future__ import annotations

import base64
import csv
import json
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from html import escape
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from tuba.model import BendGeometry, sample_bend_geometry
from tuba.reporting.isometry import project_point
from tuba.reporting.profile_svg import section_svg

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
    "geometry/geometry_assets.json",
)


_REPORT_CSS = """
:root {
  color-scheme: light;
  --graphite: #151c22; --text: #172127; --muted: #4c5b63;
  --accent: #5ed8e5; --accent-ink: #075b66; --line: #d4dfe2;
  --mono: "IBM Plex Mono", "Cascadia Mono", Consolas, monospace;
  font-family: "Roboto Condensed", "Arial Narrow", "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 5rem; }
body { color: var(--text); background: #edf1f2; margin: 0; line-height: 1.45; }
main { max-width: 96rem; margin: auto; background: white; }
a { color: var(--accent-ink); text-underline-offset: .2em; }
:focus-visible { outline: 2px solid #0b7684; outline-offset: 3px; }
.report-header { padding: 2rem 3rem; background: var(--graphite); color: #f3f5f5; border-top: 4px solid var(--accent); }
.brand-line { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.4rem; }
.brand { font-size: 1.8rem; font-weight: 600; letter-spacing: .18em; color: var(--accent); }
.eyebrow { font-family: var(--mono); font-size: .7rem; letter-spacing: .1em; text-transform: uppercase; }
.report-header .eyebrow { color: #b9c5c9; }
h1 { max-width: 50ch; font-size: clamp(1.8rem, 3vw, 2.65rem); line-height: 1.12; margin: 0 0 .75rem; font-weight: 600; }
.meta { color: #b9c5c9; margin: 0; font-size: .9rem; }
.report-nav { position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 1.2rem; padding: .9rem 3rem; background: #fff; border-bottom: 1px solid var(--line); }
.report-nav a { font-size: .9rem; text-decoration: none; }
.report-nav a:hover { text-decoration: underline; }
.report-nav .viewer-link { margin-left: auto; }
.report-content { padding: 2rem 3rem; }
h2 { font-size: 1.7rem; font-weight: 600; margin: 0 0 .4rem; line-height: 1.2; }
h3 { font-size: 1.15rem; margin: 1.4rem 0 .5rem; font-weight: 600; }
h1, h2, h3, h4 { break-after: avoid; }
p { max-width: 80ch; }
.units, .section-intro { color: var(--muted); font-size: .9rem; margin: .4rem 0 1.2rem; }
.summary-sheet { padding: 1.6rem; border: 1px solid var(--line); border-top: 3px solid #0b7684; margin: 0 0 2rem; background: #f8fafb; }
.summary-sheet h2 { font-size: 1.1rem; }
.summary-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem 2rem; margin: 1.2rem 0 0; }
.summary-facts > div { min-width: 0; }
.summary-facts dt { color: var(--muted); font-size: .78rem; margin-bottom: .15rem; }
.summary-facts dd { margin: 0; font-size: 1rem; overflow-wrap: anywhere; }
.summary-facts .summary-result { grid-column: 1 / -1; border-top: 1px solid var(--line); padding-top: .8rem; display: grid; grid-template-columns: 13rem 1fr; gap: 1rem; }
.summary-result dt { font-weight: 600; color: var(--text); font-size: .95rem; }
.summary-result dd { color: var(--accent-ink); font-family: var(--mono); font-size: .83rem; }
.report-section { margin: 2.5rem 0; padding-top: 1.5rem; border-top: 2px solid var(--graphite); }
.report-section:first-of-type { margin-top: 0; }
.report-notes { color: var(--muted); margin: 1.5rem 0; font-size: .85rem; }
summary { cursor: pointer; }
summary:focus-visible { outline: 2px solid #0b7684; }
.detail-block { margin: .65rem 0; border: 1px solid var(--line); }
.detail-block > summary { padding: .8rem 1rem; font-weight: 600; background: #f5f8f9; }
.detail-block > summary span { float: right; font-family: var(--mono); font-size: .72rem; font-weight: 400; color: var(--muted); }
.detail-block article { padding: .3rem 1rem; }
.detail-block article > h3 { display: none; }
.unavailable { border-left: .25rem solid #6c4c00; padding: .5rem .75rem; background: #fff8e6; color: #6c4c00; }
.csv-link { font-size: .78rem; margin: 0 0 .5rem; }
.table-wrap { margin: .4rem 0 1.5rem; overflow-x: auto; }
.table-wrap:focus-visible { outline: 2px solid #0b7684; outline-offset: 2px; }
table { border-collapse: collapse; font-size: .82rem; width: auto; max-width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: .55rem .6rem; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #eaf0f2; color: #243b43; font-weight: 600; border-top: 1px solid var(--line); }
tbody tr:nth-child(even) { background: #f8fafb; }
th.num, td.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }
td.num { white-space: nowrap; }
th.num { font-family: inherit; }
td.nested { min-width: 9rem; max-width: 22rem; }
.balance-status { display: inline-block; padding: .15rem .4rem; border: 1px solid currentColor; font-size: .73rem; white-space: nowrap; }
.within_tolerance { color: #17613f; background: #dff4e8; }
.outside_tolerance { color: #8f241d; background: #fde9e7; }
.not_evaluated { color: #6c4c00; background: #fff1c2; }
.kv { list-style: none; margin: 0; padding: 0; font-size: .92em; }
.kv li { display: flex; gap: .5rem; justify-content: space-between; padding-block: .05rem; }
.kv .k { color: var(--muted); white-space: nowrap; }
.kv li > span:last-child { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; min-width: 0; overflow-wrap: anywhere; }
.model-overview { margin: 1.5rem 0 2rem; }
.model-overview figure { margin: 1rem 0 1.5rem; border: 1px solid var(--line); }
.model-overview figcaption { background: #f0f5f6; padding: .65rem 1rem; font-weight: 600; font-size: .9rem; }
.model-overview svg { display: block; width: 100%; height: auto; }
.drawing-key { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .35rem 1rem; padding: .8rem 1rem; margin: 0; list-style: none; border-top: 1px solid var(--line); }
.drawing-key li { display: flex; gap: .5rem; font-size: .73rem; min-width: 0; overflow-wrap: anywhere; }
.drawing-key b { color: var(--accent-ink); font-family: var(--mono); font-weight: 600; flex-shrink: 0; }
.section-catalogue { margin: 2rem 0; }
.profile-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.profile-card { border: 1px solid var(--line); padding: 1.2rem; display: grid; grid-template-columns: 240px 1fr; gap: 1.2rem; align-items: center; break-inside: avoid; }
.profile-card h4 { font-size: 1.3rem; margin: 0 0 .25rem; }
.profile-card p { color: var(--muted); font-size: .85rem; margin: .3rem 0; }
.profile-card dl { margin: .8rem 0 0; display: grid; grid-template-columns: auto 1fr; gap: .4rem 1rem; font-size: .83rem; }
.profile-card dd { margin: 0; font-family: var(--mono); }
.profile-diagram { width: 240px; max-width: 100%; height: auto; display: block; }
.profile-object { fill: none; stroke: #172127; stroke-width: 2.3; stroke-linejoin: round; }
.profile-bore { fill: none; stroke: #4c5b63; stroke-width: 1.6; }
.profile-hatch { stroke: #9aa7ad; stroke-width: .8; }
.profile-centreline { fill: none; stroke: #0b7684; stroke-width: .85; stroke-dasharray: 16 4 3 4; }
.profile-extension { fill: none; stroke: #0b7684; stroke-width: .85; }
.profile-dimension { fill: none; stroke: #0b7684; stroke-width: 1.05; }
.profile-dimension-label { fill: #172127; font-family: var(--mono); font-size: 10px; }
.profile-dimension-note { fill: #075b66; font-family: var(--mono); font-size: 10px; }
.back { border-top: 1px solid var(--line); padding-top: 1rem; font-size: .9rem; }
@media (max-width: 65rem) {
  .profile-cards { grid-template-columns: 1fr; }
}
@media (max-width: 44rem) {
  .report-header, .report-content { padding: 1.25rem; }
  .report-nav { padding: .75rem 1.25rem; gap: .8rem; }
  .summary-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary-facts .summary-result { display: block; }
  .drawing-key { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .profile-card { grid-template-columns: 1fr; }
}
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  html { scroll-behavior: auto; }
  body { margin: 0; max-width: none; padding: 0; background: white; font-size: 10pt; }
  main { max-width: none; }
  .report-header { padding: 4mm 5mm; background: #151c22; print-color-adjust: exact; }
  .brand-line { margin-bottom: 2mm; }
  .brand { font-size: 18pt; }
  h1 { font-size: 22pt; }
  .report-content { padding: 5mm 0 0; }
  .report-nav, .back { display: none; }
  .summary-sheet { padding: 4mm; }
  .summary-facts { gap: 2mm 5mm; }
  .summary-facts dd { font-size: 9pt; }
  .summary-result dd { font-size: 8pt; }
  .summary-facts .summary-result { padding-top: 2mm; }
  .summary-sheet-page { break-after: page; }
  .report-section { margin: 5mm 0; padding-top: 3mm; }
  h3 { margin: 3mm 0 1.5mm; }
  .balance-status { font-size: 7.5pt; line-height: 1.25; padding: 0 1mm; }
  .balance-table { break-inside: avoid; }
  .model-section { break-before: page; }
  .model-overview figure { break-inside: avoid; }
  .model-overview .model-diagram { max-height: 65mm; }
  .drawing-key { gap: 1mm 3mm; padding: 2mm 3mm; }
  .drawing-key li { font-size: 7.5pt; }
  .section-catalogue { break-before: page; }
  .profile-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .profile-card { padding: 3mm; grid-template-columns: 45mm 1fr; gap: 3mm; }
  .profile-card .profile-diagram { width: 45mm; }
  .detail-block { border: 0; }
  .detail-block > summary { list-style: none; background: white; padding: 0; margin: 4mm 0 2mm; }
  .detail-block > summary span { display: none; }
  .detail-block::details-content { content-visibility: visible; display: block; }
  .detail-block > :not(summary) { display: block !important; }
  .detail-block article { padding: 0; }
  .report-notes::details-content { content-visibility: visible; display: block; }
  a { color: inherit; text-decoration: none; }
  .csv-link a::after { content: " (" attr(href) ")"; color: #4c5b63; }
  .table-wrap { overflow: visible; }
  table { font-size: 7.5pt; }
  th, td { padding: .7mm 1mm; }
  th { print-color-adjust: exact; }
  td.nested { min-width: 8rem; max-width: 12rem; }
  tr { break-inside: avoid; }
  thead { display: table-header-group; }
}
"""


def _report_fonts() -> str:
    """Embed the existing bundled Tuba faces so an offline report keeps its type."""
    viewer = Path(__file__).parents[1] / 'visualization' / '_viewer'
    rules = []
    for family, prefix, weight in (('Roboto Condensed', 'roboto-condensed', 400),
                                    ('Roboto Condensed', 'roboto-condensed', 600),
                                    ('IBM Plex Mono', 'ibm-plex-mono', 400)):
        paths = sorted((viewer / 'assets').glob(f'{prefix}-latin-{weight}-normal-*.woff2'))
        if paths:
            data = base64.b64encode(paths[0].read_bytes()).decode('ascii')
            rules.append(f'@font-face {{font-family:"{family}";font-style:normal;font-weight:{weight};src:url(data:font/woff2;base64,{data}) format("woff2");}}')
    if rules:
        for filename in ('font-notices.txt', 'OFL-1.1.txt'):
            path = viewer / 'licenses' / filename
            if path.is_file():
                rules.append('/* ' + path.read_text(encoding='utf-8').replace('*/', '* /') + ' */')
    return '\n'.join(rules)


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
    back_uri: str = "../",
) -> EngineeringReviewOutput:
    """Write JSON, CSV, and printable HTML from one review package.

    The optional callback is the only scene integration seam. This module does
    not depend on a renderer or on :mod:`tuba.visualization`.

    ``back_uri`` is where the printed page's return link points. It is relative
    and defaults to ``"../"``, which is the viewer in every layout this is
    written into - the bundle folder sits under the viewer, so its parent is
    the app. Relative, and not absolute, because this document has to open
    from a zip in ten years with no network; a relative link degrades to
    nothing there, an absolute one rots.
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
        _render_html(review, manifest, title=title, back_uri=back_uri),
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
    "Diagnostics",
)


def _render_html(
    review: EngineeringReviewPackage,
    manifest: Mapping[str, Any],
    *,
    title: str | None,
    back_uri: str = "../",
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
        _report_fonts(),
        _REPORT_CSS,
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        '<header class="report-header">',
        '<div class="brand-line"><span class="brand">TUBA</span><span class="eyebrow">Engineering review / v4</span></div>',
        f"<h1>{escape(title or review.project_name or 'Engineering review')}</h1>",
        f'<p class="meta">Model revision {review.model_revision} · {escape(review.analysis_status.replace("_", " "))} · {escape(review.created_at[:10])}</p>',
        '</header>',
        '<nav class="report-nav" aria-label="Report sections">',
        *(f'<a href="#section-{name.lower().replace(" ", "-")}">{name}</a>' for name in _SECTION_TITLES),
        f'<a class="viewer-link" href="{escape(back_uri, quote=True)}">Back to the review viewer →</a>',
        '</nav><div class="report-content">',
    ]

    reports = manifest["reports"]
    # The summary sheet comes first and is bounded to one printed page, so the
    # detail below it is reached by turning a page rather than by scrolling past
    # it. In print the page break is what makes the tier real; on screen the rule
    # is the same idea with a border.
    content.append('<div class="summary-sheet-page">')
    content.extend(_summary_sheet(review))
    content.append("</div>")
    for section_title in _SECTION_TITLES:
        section_class = "report-section model-section" if section_title == "Model" else "report-section"
        content.append(f'<section class="{section_class}" id="section-{section_title.lower().replace(" ", "-")}"><h2>{section_title}</h2>')
        descriptions = {
            "Summary": "Governing values by load case and a check of the global load balance.",
            "Model": "Authored geometry, section profiles and model schedules.",
            "Load Cases": "Applied loads and the Code_Aster studies included in this review.",
            "Results": "Detailed Code_Aster output. Full study and result-state identities are retained in the CSV files.",
            "Diagnostics": "Warnings, unavailable data and evidence that needs attention.",
        }
        content.append(f'<p class="section-intro">{descriptions[section_title]}</p>')
        if section_title == "Model":
            content.extend(_model_overview(review))
            content.extend(_section_catalogue(review))
        section_tables = sections[section_title]
        if not section_tables:
            unavailable = _unavailable_message(review, section_title)
            if unavailable:
                content.append(f'<p class="unavailable">{escape(unavailable)}</p>')
        for table in section_tables:
            detailed = section_title in {"Model", "Load Cases", "Results"} or table.id == "project_summary"
            if detailed:
                content.append(f'<details class="detail-block"><summary>{escape(table.title)}<span>{len(table.rows)} records</span></summary>')
            content.extend(_render_table(table, csv_uri=reports.get(table.id)))
            if detailed:
                content.append('</details>')
        content.append("</section>")

    content.append('<details class="report-notes"><summary>Units and display precision</summary>')
    content.append(f'<p>{escape(_units_note(review))} Section-profile dimensions are labelled in millimetres.</p></details>')
    content.extend(
        (
            # The way out. This page used to end at </main> with no anchor to
            # the viewer anywhere on it - a different stylesheet, a different
            # type scale, and only browser Back - which made the report the
            # sharpest dead end in the product.
            f'<p class="back"><a href="{escape(back_uri, quote=True)}">'
            "&#8592; Back to the review viewer</a></p>",
            "</div></main>",
            "</body>",
            "</html>",
            "",
        )
    )
    return "\n".join(content)


def _model_overview(review: EngineeringReviewPackage) -> list[str]:
    """Short drawing keys map to the full native IDs in the accompanying legend."""
    tables = review.tables_by_id
    if "nodes" not in tables or "line_list" not in tables or not tables["line_list"].rows:
        return []
    nodes = {str(row["node_id"]): (row["x_m"], row["y_m"], row["z_m"])
             for row in tables["nodes"].rows}
    def native_order(value):
        return tuple((part.isdigit(), int(part) if part.isdigit() else part)
                     for part in re.split(r'(\d+)', value))
    nodes = dict(sorted(nodes.items(), key=lambda item: native_order(item[0])))
    lines = []
    for row in tables["line_list"].rows:
        try:
            points = [nodes[str(row["start_node"])], nodes[str(row["end_node"])]]
        except KeyError as exc:
            raise EngineeringReviewError("Model overview references a node absent from the node schedule.") from exc
        if row.get("element_type") == "pipe_bend":
            if not row.get("bend_geometry"):
                raise EngineeringReviewError(f"Model overview bend {row['element_id']!r} has no canonical geometry.")
            points = sample_bend_geometry(points[0], BendGeometry.from_dict(row["bend_geometry"]), n_segments=32)
        lines.append((str(row["element_id"]), [project_point(point) for point in points]))
    lines.sort(key=lambda item: native_order(item[0]))
    projected_nodes = {key: project_point(point) for key, point in nodes.items()}
    all_points = [point for _, points in lines for point in points] + list(projected_nodes.values())
    xmin, ymin = (min(point[index] for point in all_points) for index in (0, 1))
    xmax, ymax = (max(point[index] for point in all_points) for index in (0, 1))
    scale = min(820 / max(xmax - xmin, 1e-9), 220 / max(ymax - ymin, 1e-9))
    xoffset = (1000 - (xmax - xmin) * scale) / 2

    def screen(point):
        return (xoffset + (point[0] - xmin) * scale, 55 + (point[1] - ymin) * scale)

    content = ['<div class="model-overview"><h3>Model drawings</h3>',
               '<p class="units">Authored, undeformed centerlines. Short drawing keys are matched '
               'to exact model IDs below each sheet. Dimensions and sections are in the schedules.</p>']
    supports = tables.get("supports")
    for kind, title in (("elements", "Elements and supports"), ("nodes", "Node numbering")):
        title_id = f"model-{kind}-title"
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" class="model-diagram" viewBox="0 0 1000 340" role="img" aria-labelledby="{title_id}">',
               f'<title id="{title_id}">{title}</title>',
               '<g fill="none" stroke="#075b66" stroke-width="2.5">']
        for element_id, points in lines:
            coordinates = " ".join(f"{x:.3f},{y:.3f}" for x, y in map(screen, points))
            svg.append(f'<polyline data-element="{escape(element_id, quote=True)}" points="{coordinates}"/>')
        svg.append('</g><g font-family="Roboto Condensed, sans-serif" font-size="14" fill="#172127">')
        occupied, legend = [(0, 250, 95, 340)], []

        def label(key, entity_id, point):
            x, y = screen(point)
            width = len(key) * 9 + 6
            # ponytail: bounded greedy lanes; use dedicated route sheets for dense models.
            candidates = [(min(max(x - width / 2 + shift, 4), 996 - width),
                           min(max(y + offset, 18), 324))
                          for offset in (-12, 24, -36, 48, -60, 72, -84, 96)
                          for shift in (0, -width, width, -2*width, 2*width)]
            def score(candidate):
                cx, cy = candidate
                overlap = sum(cx < right and cx + width > left and cy - 16 < bottom and cy + 4 > top
                              for left, top, right, bottom in occupied)
                return overlap, (cx + width/2 - x)**2 + (cy - y)**2
            lx, ly = min(candidates, key=score)
            occupied.append((lx, ly - 16, lx + width, ly + 4))
            if abs(ly - y) > 24 or abs(lx + width/2 - x) > 24:
                svg.append(f'<path d="M{x:.3f},{y:.3f} L{lx + width/2:.3f},{ly - 6:.3f}" stroke="#9aa7ad" fill="none"/>')
            svg.append(f'<text class="drawing-label" data-ref="{escape(entity_id, quote=True)}" x="{lx:.3f}" y="{ly:.3f}" stroke="white" stroke-width="4" paint-order="stroke">{key}</text>')
            legend.append(f'<li><b>{key}</b><span>{escape(entity_id)}</span></li>')

        if kind == "elements":
            for index, (element_id, points) in enumerate(lines, 1):
                first, last = points[0], points[-1]
                middle = tuple((a + b)/2 for a, b in zip(first, last)) if len(points) == 2 else points[len(points)//2]
                label(f"E{index}", element_id, middle)
        else:
            for index, (node_id, point) in enumerate(projected_nodes.items(), 1):
                x, y = screen(point)
                svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="3"/>')
                label(f"N{index}", node_id, point)
        if supports is not None:
            for index, row in enumerate(supports.rows, 1):
                node_id = str(row["node"])
                if node_id not in projected_nodes:
                    raise EngineeringReviewError("Model overview support references an absent node.")
                x, y = screen(projected_nodes[node_id])
                svg.append(f'<path d="M{x:.3f},{y:.3f} l-6,10 h12 z" fill="#172127"/>')
                if kind == "elements":
                    label(f"S{index}", str(row.get('support_id') or node_id), projected_nodes[node_id])
        svg.append('</g><g stroke="#4c5b63" fill="#4c5b63" font-family="Roboto Condensed, sans-serif" font-size="12">'
                   '<path d="M40,295 l22,11 M40,295 l-22,11 M40,295 v-25" fill="none"/>'
                   '<text x="65" y="312" stroke="none">X</text><text x="6" y="312" stroke="none">Y</text>'
                   '<text x="36" y="262" stroke="none">Z</text></g></svg>')
        content.append(f'<figure><figcaption>{title} · isometric view</figcaption>{"".join(svg)}<ul class="drawing-key" aria-label="{title} drawing key">{"".join(legend)}</ul></figure>')
    content.append('</div>')
    return content


def _section_catalogue(review: EngineeringReviewPackage) -> list[str]:
    table = review.tables_by_id.get("section_schedule")
    if table is None or not table.rows:
        return []
    content = ['<div class="section-catalogue"><h3>Section profiles</h3>',
               '<p class="units">Actual section geometry, with the same dimensioned drafting style as the Tuba inspector. Dimensions in mm; profiles are individually scaled for legibility.</p>',
               '<div class="profile-cards">']
    for index, row in enumerate(table.rows, 1):
        try:
            drawing = section_svg(row, index)
        except (KeyError, TypeError, ValueError) as exc:
            drawing = f'<p class="unavailable">Diagram unavailable: {escape(str(exc))}</p>'
        content.append(f'<article class="profile-card">{drawing}<div><h4>{escape(str(row["section"]))}</h4>')
        kind = {"ibeam": "I-section", "pipe": "Pipe section", "bar": "Bar section",
                "rectangular": "Rectangular section", "cable": "Cable section"}.get(row["section_type"], row["section_type"])
        profile_name = row.get("profile_name")
        subtitle = f'{kind} · {profile_name}' if profile_name and profile_name != row["section"] else kind
        content.append(f'<p>{escape(str(subtitle))}</p><dl>')
        for key, label, unit in (("element_count", "Members", ""), ("total_length_m", "Length", "m"), ("total_mass_kg", "Mass", "kg")):
            content.append(f'<dt>{label}</dt><dd>{escape(_display_value(row.get(key)))} {unit}</dd>')
        content.append('</dl></div></article>')
    content.append('</div></div>')
    return content


def _summary_sheet(review: EngineeringReviewPackage) -> list[str]:
    """One-page identity, evidence and governing values, with the FE stress basis."""
    rows = _summary_rows(review)
    content = [
        '<section class="summary-sheet" aria-label="One-page summary">',
        "<h2>Summary sheet</h2>",
        '<p class="units">Largest available values across the published cases. Finite-element output; '
        'Tuba performs no standards evaluation.</p>',
        '<dl class="summary-facts">',
    ]
    result_labels = {
        "translation magnitude": "Maximum displacement",
        "reaction force magnitude": "Maximum support force",
        "element force magnitude": "Maximum element force",
        "fe von mises": "FE von Mises stress",
    }
    for label, value in rows:
        result = label in result_labels
        css = "summary-result" if result else "summary-fact"
        content.append(f'<div class="{css}"><dt>{escape(result_labels.get(label, label))}</dt><dd>{escape(value)}</dd></div>')
    content.extend(("</dl>", "</section>"))
    return content


def _summary_rows(review: EngineeringReviewPackage) -> list[tuple[str, str]]:
    by_id = {table.id: table for table in review.tables}
    rows: list[tuple[str, str]] = [
        ("Project", review.project_name or "unnamed"),
        ("Design standard", review.model_standard or "none declared"),
        ("Model revision", str(review.model_revision)),
        ("Analysis status", review.analysis_status),
        ("Published", review.created_at),
    ]

    studies = by_id.get("studies")
    if studies is not None and studies.rows:
        solvers = sorted(
            {
                str(row.get("solver_name"))
                for row in studies.rows
                if row.get("solver_name")
            }
        )
        rows.append(("Solver", ", ".join(solvers) or "not stated"))
        rows.append(("Studies", str(len(studies.rows))))

    provenance = review.provenance
    if provenance:
        # Only result states carry the trust bar. The builder refuses to publish a
        # review at all unless every result state has a verified attestation
        # (builder.py), and a study record is an input reference rather than
        # evidence of a solve - so counting both kinds together would report a
        # study as an unverified result and send a reader looking for a
        # problem that is not there.
        results = [record for record in provenance if record.kind == "result_state"]
        if results:
            verified = sum(
                1
                for record in results
                if record.metadata.get("result_trust") == "verified"
                and isinstance(record.metadata.get("solve_attestation"), dict)
            )
            # The one fact on this page that decides whether the rest is worth
            # reading. A review that reports eleven significant figures from an
            # unverified solve is the failure this sheet exists to make
            # impossible to miss.
            rows.append((
                "Evidence",
                f"{verified} of {len(results)} result "
                f"{'record' if len(results) == 1 else 'records'} verified"
                + ("" if verified == len(results) else " - see Diagnostics"),
            ))

    result_summary = by_id.get("result_summary")
    governing = {}
    for row in (result_summary.rows if result_summary is not None else ()):
        key = row.get("result_type")
        previous = governing.get(key)
        if previous is None or (row.get("maximum_value") is not None and
                (previous.get("maximum_value") is None or row["maximum_value"] > previous["maximum_value"])):
            governing[key] = row
    for row in governing.values():
        quantity = str(row.get("result_type", "")).replace("_", " ")
        value = row.get("maximum_value")
        unit = str(row.get("unit", "") or "")
        basis = str(row.get("result_basis", "") or "")
        entity = str(row.get("governing_entity_ref", "") or "")
        location = str(row.get("governing_location", "") or "")
        text = "unavailable" if value is None else f"{_display_number(value)} {unit}".strip()
        if basis and not basis.startswith("Code_Aster "):
            text += f" - {basis}"
        if row.get("load_case"):
            text += f" - load case {row['load_case']}"
        if entity or location:
            text += f" - at {entity}" + (f" / {location}" if location and location not in {entity, entity.removeprefix("node:")} else "")
        rows.append((quantity or "result", text))

    diagnostics = by_id.get("diagnostics")
    if diagnostics is not None and diagnostics.rows:
        severities: dict[str, int] = {}
        for row in diagnostics.rows:
            severity = str(row.get("severity", "info")).lower()
            severities[severity] = severities.get(severity, 0) + 1
        rows.append(("Diagnostics", ", ".join(f"{count} {name}" for name, count in sorted(severities.items()))))
    elif review.diagnostics:
        severities = {}
        for diagnostic in review.diagnostics:
            severities[diagnostic.severity] = severities.get(diagnostic.severity, 0) + 1
        rows.append(("Diagnostics", ", ".join(f"{count} {name}" for name, count in sorted(severities.items()))))
    else:
        rows.append(("Diagnostics", "none recorded"))
    return rows


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
        "The review viewer that links here converts the same quantities for display - "
        "millimetres, megapascals and kilonewtons unless you switch it - so a number "
        "read on the model will not match the number printed here. These are the "
        "stored values. Shown to six significant figures; the CSV files in reports/ "
        "carry the same values at full precision."
    )


def _section_for_table(table: ReportTable) -> str:
    if table.id in {"project_summary", "result_summary", "equilibrium"}:
        return "Summary"
    if table.id in {"load_cases", "studies"}:
        return "Load Cases"
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
    if table.id == "project_summary":
        table = replace(table, columns=tuple(column for column in table.columns
                        if column.id not in {"project_name", "model_standard", "model_revision", "analysis_status"}))
    elif table.id == "studies":
        table = replace(table, columns=tuple(column for column in table.columns
                        if column.id in {"study_id", "solver_name", "load_case", "model_revision"}))
    elif table.id == "section_schedule":
        table = replace(table, columns=tuple(column for column in table.columns
                        if any(row.get(column.id) is not None for row in table.rows)))
    if table.source == "result_state":
        # Full lineage stays in JSON/CSV; repeat the engineering quantities here.
        hidden = {"solver_name", "study_id", "result_state_id"}
        if any(column.id in {"node", "element", "support_id"} for column in table.columns):
            hidden.add("entity_ref")
        table = replace(table, columns=tuple(column for column in table.columns
                        if column.id not in hidden))
    # The heading names the table, the scroll region and the table itself, so a
    # screen reader entering any of the three is told which one it is - and the
    # visible text is written once.
    heading_id = f"table-{table.id}"
    content = [f'<article><h3 id="{heading_id}">{escape(table.title)}</h3>']
    if table.id == "equilibrium":
        content.append('<p class="units">Global axes; moments about (0, 0, 0) m. '
                       'Calculated applied loads + Code_Aster reactions = residual. '
                       'Tolerance is 0.001 N or N*m plus 1e-5 times the larger sum of absolute '
                       'applied or reaction components. This checks numerical balance, not a design standard.</p>')
        for row in table.rows:
            if row.get("status") == "not_evaluated":
                content.append(f'<p class="unavailable">{escape(str(row.get("load_case", "")))}: '
                               f'not evaluated - {escape(str(row.get("note", "")))}</p>')
        visible = {"load_case", "component", "applied", "reaction", "residual", "tolerance", "unit", "status"}
        table = replace(table, columns=tuple(column for column in table.columns if column.id in visible))
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
            f'<div class="table-wrap{" balance-table" if table.id == "equilibrium" else ""}" role="region" tabindex="0"'
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
                if table.id == "equilibrium" and column.id == "status":
                    status = str(value)
                    rendered = f'<span class="balance-status {escape(status, quote=True)}">{escape(status.replace("_", " "))}</span>'
                elif column.id in {"result_type", "location_kind"}:
                    rendered = escape(str(value).replace("_", " "))
                else:
                    rendered = _render_cell_html(value)
                content.append(f"<td{css}>{rendered}</td>")
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
