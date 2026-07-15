"""Static visualization report export helpers."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tuba.visualization.reports import build_reports, write_report_csvs
from tuba.visualization.scene import SceneDiagnostic, VisualizationScene
from tuba.visualization.web_export import SceneBundle, write_scene_bundle

_REPORT_TITLES = {
    "line_list": "Line list",
    "section_schedule": "Cross-section schedule",
    "load_case_summary": "Load case summary",
    "stress": "FE Von Mises (not piping-code stress)",
    "reactions": "Support reactions",
    "displacements": "Nodal displacements",
}


@dataclass(frozen=True)
class StaticReport:
    root: Path
    index_path: Path
    bundle: SceneBundle
    manifest_path: Path
    issue_summary_path: Path
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    screenshot_path: Path | None = None


def write_static_report(
    scene: VisualizationScene,
    path: str | Path,
    *,
    title: str | None = None,
    include_screenshot: bool = False,
    screenshot_backend: str = "playwright",
    screenshot_name: str = "report.png",
) -> StaticReport:
    """Write a local, shareable report folder around a VisualizationScene bundle."""
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    report_title = title or scene.scene_id
    bundle = write_scene_bundle(scene, root)
    diagnostics: list[dict[str, Any]] = []
    screenshot_path: Path | None = None

    issue_summary = _issue_summary(scene)
    issue_summary_path = root / "issue_summary.json"
    _write_json(issue_summary_path, issue_summary)
    _write_json(root / "metadata" / "issue_summary.json", issue_summary)

    csv_paths = write_report_csvs(scene, root / "reports")

    index_path = root / "index.html"
    manifest = {
        "report_kind": "legacy_scene_derived",
        "code_compliance": "unavailable",
        "reports": {path.stem: f"reports/{path.name}" for path in csv_paths},
        "title": report_title,
        "scene_id": scene.scene_id,
        "model_id": scene.model_id,
        "scene_uri": "scene.json",
        "issue_summary_uri": "issue_summary.json",
        "object_count": len(scene.objects),
        "issue_count": len(scene.issues),
        "screenshot_uri": f"snapshots/{screenshot_name}" if include_screenshot else None,
        "diagnostics": [],
    }
    index_path.write_text(_report_html(report_title, scene, issue_summary, manifest), encoding="utf-8")

    if include_screenshot:
        screenshot_path = root / "snapshots" / screenshot_name
        diagnostic = _try_capture_screenshot(index_path, screenshot_path, backend=screenshot_backend)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            screenshot_path = None

    manifest["screenshot_uri"] = f"snapshots/{screenshot_name}" if screenshot_path else None
    manifest["diagnostics"] = diagnostics
    manifest_path = root / "report_manifest.json"
    _write_json(manifest_path, manifest)
    index_path.write_text(_report_html(report_title, scene, issue_summary, manifest), encoding="utf-8")

    return StaticReport(
        root=root,
        index_path=index_path,
        bundle=bundle,
        manifest_path=manifest_path,
        issue_summary_path=issue_summary_path,
        diagnostics=diagnostics,
        screenshot_path=screenshot_path,
    )


def notebook_iframe_html(
    report_path: str | Path,
    *,
    width: str | int = "100%",
    height: str | int = 720,
    title: str = "Tuba visualization report",
) -> str:
    """Return iframe HTML suitable for notebook display."""
    path = Path(report_path)
    src = path if path.suffix.lower() == ".html" else path / "index.html"
    return (
        f'<iframe src="{html.escape(src.as_posix(), quote=True)}" '
        f'width="{html.escape(str(width), quote=True)}" '
        f'height="{html.escape(str(height), quote=True)}" '
        f'title="{html.escape(title, quote=True)}" '
        'style="border:0; width:100%; min-height:480px;" loading="lazy"></iframe>'
    )


def _issue_summary(scene: VisualizationScene) -> dict[str, Any]:
    counts_by_severity: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    issues = []
    for issue in scene.issues:
        counts_by_severity[issue.severity] = counts_by_severity.get(issue.severity, 0) + 1
        counts_by_status[issue.status] = counts_by_status.get(issue.status, 0) + 1
        issues.append(
            {
                "id": issue.id,
                "type": issue.type,
                "title": issue.title,
                "severity": issue.severity,
                "status": issue.status,
                "description": issue.description,
                "entity_refs": [str(ref) for ref in issue.entity_refs],
            }
        )
    return {
        "issue_count": len(scene.issues),
        "counts": counts_by_severity,
        "counts_by_severity": counts_by_severity,
        "counts_by_status": counts_by_status,
        "issues": issues,
    }


def _report_html(title: str, scene: VisualizationScene, issue_summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    data = {
        "manifest": manifest,
        "scene": scene.to_dict(),
        "issue_summary": issue_summary,
    }
    json_data = json.dumps(data, indent=2, sort_keys=True).replace("</", "<\\/")
    scene_json = json.dumps(scene.to_dict(), indent=2, sort_keys=True).replace("</", "<\\/")
    escaped_title = html.escape(title)
    object_rows = "\n".join(
        f"<tr><td>{html.escape(obj.id)}</td><td>{html.escape(obj.kind)}</td><td>{html.escape(obj.name)}</td></tr>"
        for obj in scene.objects
    )
    issue_rows = "\n".join(
        f"<tr><td>{html.escape(issue['id'])}</td><td>{html.escape(issue['severity'])}</td><td>{html.escape(issue['status'])}</td><td>{html.escape(issue['title'])}</td></tr>"
        for issue in issue_summary["issues"]
    )
    report_sections = _reports_html(scene, manifest.get("reports", {}))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; color: #111827; background: #f8fafc; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #e5e7eb; }}
    .meta {{ color: #4b5563; margin-bottom: 20px; }}
    .legacy-warning {{ border-left: 4px solid #b45309; background: #fffbeb; padding: 12px 16px; margin: 18px 0; }}
    .viewer-link {{ display: inline-block; margin: 8px 0 18px; }}
  </style>
</head>
<body>
  <main>
    <h1>{escaped_title}</h1>
    <div class="meta">{html.escape(scene.scene_id)} | {len(scene.objects)} objects | {len(scene.issues)} issues</div>
    <aside class="legacy-warning"><strong>Legacy scene-derived report</strong><br>
      Code compliance unavailable. Scene overlays may show FE Von Mises (not piping-code stress),
      reactions, or displacements, but they do not establish piping-code compliance.</aside>
    <a class="viewer-link" href="scene.json">Open scene manifest</a>
    <h2>Objects</h2>
    <table><thead><tr><th>ID</th><th>Kind</th><th>Name</th></tr></thead><tbody>{object_rows}</tbody></table>
    <h2>Issues</h2>
    <table><thead><tr><th>ID</th><th>Severity</th><th>Status</th><th>Title</th></tr></thead><tbody>{issue_rows}</tbody></table>
    {report_sections}
  </main>
  <script id="tuba-scene" type="application/json">{scene_json}</script>
  <script id="tuba-report-data" type="application/json">{json_data}</script>
</body>
</html>
"""


def _reports_html(scene: VisualizationScene, report_uris: dict[str, str]) -> str:
    sections = []
    for name, rows in build_reports(scene).items():
        if not rows:
            continue
        title = _REPORT_TITLES.get(name, name)
        headers = list(rows[0].keys())
        head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        body = "\n".join(
            "<tr>" + "".join(f"<td>{html.escape(_cell(row.get(header)))}</td>" for header in headers) + "</tr>"
            for row in rows
        )
        csv_uri = report_uris.get(name)
        link = f' <a class="viewer-link" href="{html.escape(csv_uri, quote=True)}">CSV</a>' if csv_uri else ""
        sections.append(
            f"<h2>{html.escape(title)}{link}</h2>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        )
    return "\n".join(sections)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _try_capture_screenshot(index_path: Path, screenshot_path: Path, *, backend: str) -> dict[str, Any] | None:
    if backend != "playwright":
        return SceneDiagnostic(
            severity="warning",
            code="visualization.static_report.screenshot_unavailable",
            message=f"Unsupported screenshot backend {backend!r}.",
            source="visualization.static_report",
        ).to_dict()
    try:
        from playwright.sync_api import sync_playwright

        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(index_path.resolve().as_uri())
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
        return None
    except Exception as exc:
        return SceneDiagnostic(
            severity="warning",
            code="visualization.static_report.screenshot_unavailable",
            message=str(exc),
            source="visualization.static_report",
        ).to_dict()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
