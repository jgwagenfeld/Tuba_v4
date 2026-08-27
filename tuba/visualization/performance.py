"""Small performance probes for visualization scene generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from tuba import Model
from tuba.model import TubaModel
from tuba.visualization.builders import SceneBuildOptions, build_visualization_scene
from tuba.visualization.scene import SceneDiagnostic
from tuba.visualization.web_export import write_scene_bundle


def benchmark_scene_build(
    model: TubaModel,
    *,
    output_dir: str | Path | None = None,
    limits: dict[str, float] | None = None,
    options: SceneBuildOptions | None = None,
) -> dict[str, Any]:
    """Build a scene once and return/write basic performance metrics."""
    started = perf_counter()
    scene = build_visualization_scene(model, options=options)
    build_seconds = perf_counter() - started
    diagnostics = _limit_diagnostics(scene, build_seconds, limits or {})
    scene.diagnostics.extend(SceneDiagnostic.from_dict(item) for item in diagnostics)
    bundle_size_bytes = 0
    asset_hashes = _asset_hashes_for_scene(scene)

    report: dict[str, Any] = {
        "scene_id": scene.scene_id,
        "model_id": scene.model_id,
        "object_count": len(scene.objects),
        "geometry_asset_count": len(scene.geometry_assets),
        "overlay_count": len(scene.overlays),
        "issue_count": len(scene.issues),
        "build_seconds": build_seconds,
        "bundle_size_bytes": bundle_size_bytes,
        "asset_hashes": asset_hashes,
        "diagnostics": diagnostics,
        "report_path": None,
    }
    if output_dir is not None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        bundle = write_scene_bundle(scene, output_path / "scene_bundle")
        bundle_size_bytes = _directory_size(bundle.root)
        asset_hashes = _asset_hashes_from_bundle(bundle.scene_path)
        report["bundle_root"] = str(bundle.root)
        report["bundle_size_bytes"] = bundle_size_bytes
        report["asset_hashes"] = asset_hashes
        report_path = output_path / f"visualization_benchmark_{_timestamp()}.json"
        report["report_path"] = str(report_path)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def benchmark_viewer_smoke(
    *,
    output_dir: str | Path = ".build/benchmarks",
    model: TubaModel | None = None,
    limits: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Write a deterministic local viewer-smoke benchmark summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    bench_model = model or _moderate_model()
    build_report = benchmark_scene_build(bench_model, output_dir=output_path / "viewer_smoke_build", limits=limits)
    bundle_root = Path(build_report["bundle_root"])

    started = perf_counter()
    scene = _read_json(bundle_root / "scene.json")
    objects = _read_json(bundle_root / "metadata" / "objects.json")
    overlays = _read_json(bundle_root / "metadata" / "overlays.json")
    _read_json(bundle_root / "geometry" / "geometry_assets.json")
    viewer_load_ms = (perf_counter() - started) * 1000.0

    started = perf_counter()
    selected = _select_first_object(objects)
    selection_latency_ms = (perf_counter() - started) * 1000.0

    started = perf_counter()
    visible_ids = _simulate_overlay_toggle(objects, overlays)
    overlay_toggle_latency_ms = (perf_counter() - started) * 1000.0

    diagnostics = _viewer_limit_diagnostics(
        viewer_load_ms=viewer_load_ms,
        selection_latency_ms=selection_latency_ms,
        overlay_toggle_latency_ms=overlay_toggle_latency_ms,
        limits=limits or {},
    )
    report = {
        "scenario": "viewer-smoke",
        "scene_id": scene["scene_id"],
        "object_count": len(objects),
        "selected_object_id": selected,
        "visible_after_overlay_toggle": len(visible_ids),
        "bundle_root": str(bundle_root),
        "bundle_size_bytes": build_report["bundle_size_bytes"],
        "asset_hashes": build_report["asset_hashes"],
        "build_seconds": build_report["build_seconds"],
        "viewer_load_ms": viewer_load_ms,
        "selection_latency_ms": selection_latency_ms,
        "overlay_toggle_latency_ms": overlay_toggle_latency_ms,
        "diagnostics": [*build_report["diagnostics"], *diagnostics],
    }
    report_path = output_path / "viewer_smoke_latest.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _limit_diagnostics(scene, build_seconds: float, limits: dict[str, float]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    max_objects = limits.get("max_objects")
    if max_objects is not None and len(scene.objects) > max_objects:
        diagnostics.append(
            SceneDiagnostic(
                severity="warning",
                code="visualization.performance.object_limit",
                message=f"Scene object count {len(scene.objects)} exceeds configured object count limit {max_objects}.",
                source="visualization.performance",
            ).to_dict()
        )
    max_assets = limits.get("max_geometry_assets")
    if max_assets is not None and len(scene.geometry_assets) > max_assets:
        diagnostics.append(
            SceneDiagnostic(
                severity="warning",
                code="visualization.performance.geometry_asset_limit",
                message=f"Scene geometry asset count {len(scene.geometry_assets)} exceeds configured limit {max_assets}.",
                source="visualization.performance",
            ).to_dict()
        )
    max_seconds = limits.get("max_build_seconds")
    if max_seconds is not None and build_seconds > max_seconds:
        diagnostics.append(
            SceneDiagnostic(
                severity="warning",
                code="visualization.performance.build_time_limit",
                message=f"Scene build time {build_seconds:.6f}s exceeds configured limit {max_seconds:.6f}s.",
                source="visualization.performance",
            ).to_dict()
        )
    return diagnostics


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _asset_hashes_for_scene(scene) -> dict[str, str]:
    result: dict[str, str] = {}
    for asset in scene.geometry_assets:
        if asset.hash:
            result[asset.id] = asset.hash
    return result


def _asset_hashes_from_bundle(scene_path: Path) -> dict[str, str]:
    scene = _read_json(scene_path)
    return {asset["id"]: asset["hash"] for asset in scene.get("geometry_assets", []) if asset.get("hash")}


def _directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_first_object(objects: list[dict[str, Any]]) -> str | None:
    return objects[0]["id"] if objects else None


def _simulate_overlay_toggle(objects: list[dict[str, Any]], overlays: list[dict[str, Any]]) -> set[str]:
    visible = {obj["id"] for obj in objects}
    if not overlays:
        return visible
    for object_id in overlays[0].get("object_ids", []):
        visible.discard(object_id)
    return visible


def _viewer_limit_diagnostics(
    *,
    viewer_load_ms: float,
    selection_latency_ms: float,
    overlay_toggle_latency_ms: float,
    limits: dict[str, float],
) -> list[dict[str, Any]]:
    checks = [
        ("max_viewer_load_ms", viewer_load_ms, "visualization.performance.viewer_load_limit", "viewer load"),
        ("max_selection_latency_ms", selection_latency_ms, "visualization.performance.selection_latency_limit", "selection latency"),
        ("max_overlay_toggle_latency_ms", overlay_toggle_latency_ms, "visualization.performance.overlay_toggle_limit", "overlay toggle"),
    ]
    diagnostics = []
    for limit_name, value, code, label in checks:
        limit = limits.get(limit_name)
        if limit is not None and value > limit:
            diagnostics.append(
                SceneDiagnostic(
                    severity="warning",
                    code=code,
                    message=f"{label} {value:.3f}ms exceeds configured limit {limit:.3f}ms.",
                    source="visualization.performance",
                ).to_dict()
            )
    return diagnostics


def _moderate_model(count: int = 25) -> TubaModel:
    model = Model(project_name="ViewerSmokeBenchmark")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    previous = model.add_node([0.0, 0.0, 0.0])
    for index in range(count):
        node = model.add_node([float(index + 1), 0.0, 0.0])
        model.add_element(
            id=f"pipe_{index}",
            type="pipe_straight",
            n1=previous,
            n2=node,
            section="PipeSec",
            material="Steel",
        )
        previous = node
    return model
