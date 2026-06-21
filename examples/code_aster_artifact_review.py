"""Build a viewer bundle from existing Code_Aster result artifact files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model
from tuba.analysis import (
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene, write_scene_bundle


def run_example(output_dir: str | Path = ".benchmarks/code_aster_artifact_review") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, n0, n1 = _build_model()

    artifact_dir = output_path / "code_aster_artifacts"
    study = CodeAsterSolver(work_dir=artifact_dir).export_analysis_study(model, "Hot", artifact_dir)
    _write_sample_result_tables(artifact_dir, n0=n0, n1=n1)

    artifact = import_code_aster_artifacts(model=model, work_dir=artifact_dir)
    operating_state = create_operating_geometry_state(model=model, result_state=artifact.result_state)
    visual_state = create_visual_deformed_geometry_state(model=model, result_state=artifact.result_state, visual_scale=40.0)
    scene = build_visualization_scene(
        model,
        analysis_meshes=[artifact.analysis_mesh] if artifact.analysis_mesh is not None else [],
        result_states=[artifact.result_state],
        geometry_states=[operating_state, visual_state],
        scene_id="scene:code_aster_artifact_review",
        created_at="2026-06-21T00:00:00Z",
    )
    bundle = write_scene_bundle(scene, output_path / "review_scene")
    summary = {
        "project_name": model.project_name,
        "study_id": study.id,
        "artifact_dir": str(artifact_dir),
        "result_source": artifact.result_state.metadata["source"],
        "result_state_id": artifact.result_state.id,
        "bundle_root": str(bundle.root),
        "scene": str(bundle.scene_path),
        "diagnostics": artifact.diagnostics,
        "counts": {
            "scene_objects": len(scene.objects),
            "scene_geometry_assets": len(scene.geometry_assets),
            "scene_overlays": len(scene.overlays),
            "scene_issues": len(scene.issues),
        },
    }
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _build_model():
    model = Model(project_name="CodeAsterArtifactReview")
    model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
    model.add_support(node=n0, type="anchor", id="support_anchor_0")
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model, n0, n1


def _write_sample_result_tables(work_dir: Path, *, n0: str, n1: str) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "study_depl.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},0.0,0.0,0.0,0.0,0.0,0.0",
                f"{n1},0.0,0.012,0.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_effo.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                f"pipe_0,{n0},8.0,15.0,20.0,1.0,2.0,3.0",
                f"pipe_0,{n1},9.0,16.0,21.0,4.0,5.0,6.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_reac.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},900.0,0.0,-300.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_sieq.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,VMIS",
                f"pipe_0,{n0},76000000.0",
                f"pipe_0,{n1},118000000.0",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
