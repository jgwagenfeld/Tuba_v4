"""Canonical realtime visualization review bundle without running Code_Aster."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import TrimeshClashEngine
from tuba.analysis import (
    AnalysisMesh,
    ResultState,
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene, write_scene_bundle

try:
    from examples.operating_state_clash import build_model
except ModuleNotFoundError:  # pragma: no cover - direct script execution from examples/
    from operating_state_clash import build_model


def run_example(output_dir: str | Path = ".benchmarks/realtime_visualization_review") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, n0, n1 = build_model()

    study_dir = output_path / "code_aster"
    study = CodeAsterSolver(work_dir=str(study_dir)).export_analysis_study(
        model,
        "Hot",
        output_dir=study_dir,
    )
    manifest_path = study_dir / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis_mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    result_state = ResultState(
        id="result_state:Hot:review_mock",
        study_id=study.id,
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=study.mesh_id,
        node_displacements={
            n0: (0.0, 0.05, 0.0, 0.0, 0.0, 0.0),
            n1: (0.0, 0.05, 0.0, 0.0, 0.0, 0.0),
        },
        node_reactions={
            n0: (1000.0, 250.0, 0.0, 0.0, 0.0, 0.0),
        },
        element_results={
            "pipe_hot_0": {
                "forces_n1": [0.0, 120.0, 0.0, 0.0, 0.0, 25.0],
                "forces_n2": [0.0, -120.0, 0.0, 0.0, 0.0, -25.0],
                "von_mises_n1": 42.0e6,
                "von_mises_n2": 57.0e6,
                "max_von_mises": 57.0e6,
            },
        },
        files={"manifest": str(manifest_path)},
        metadata={"source": "realtime_visualization_review_mock_result_state"},
    )
    cold_state = create_cold_geometry_state(model)
    operating_state = create_operating_geometry_state(model=model, result_state=result_state)
    visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=50.0)
    operating_clashes = TrimeshClashEngine().check_operating_state(
        model,
        cold_state=cold_state,
        operating_state=operating_state,
        result_state=result_state,
        envelope_type="insulation",
        analysis_mesh=analysis_mesh,
    )
    scene = build_visualization_scene(
        model,
        analysis_meshes=[analysis_mesh],
        operating_clash_results=operating_clashes,
        result_states=[result_state],
        geometry_states=[cold_state, operating_state, visual_state],
        scene_id="scene:realtime_visualization_review",
        created_at="2026-06-21T00:00:00Z",
    )
    bundle = write_scene_bundle(scene, output_path / "review_scene")
    summary = {
        "project_name": model.project_name,
        "study_id": study.id,
        "manifest": str(manifest_path),
        "result_state_id": result_state.id,
        "physical_geometry_state_id": operating_state.id,
        "visual_geometry_state_id": visual_state.id,
        "operating_clashes": len(operating_clashes),
        "bundle_root": str(bundle.root),
        "scene": str(bundle.scene_path),
        "object_map": str(bundle.metadata_dir / "object_map.json"),
        "geometry_assets": str(bundle.geometry_dir / "geometry_assets.json"),
        "counts": {
            "analysis_mesh_nodes": len(analysis_mesh.nodes),
            "analysis_mesh_elements": len(analysis_mesh.elements),
            "scene_objects": len(scene.objects),
            "scene_geometry_assets": len(scene.geometry_assets),
            "scene_overlays": len(scene.overlays),
            "scene_issues": len(scene.issues),
        },
    }
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
