"""Publish the native Gmsh/Code_Aster 3D tee result review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model
from tuba.analysis.code_aster_artifacts import (
    import_code_aster_artifacts,
    stage_code_aster_artifact_evidence,
)
from tuba.reporting import build_engineering_review
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene


TEE_VOLUME_ELEMENT_IDS = ("header_left", "header_right", "branch")
TEE_VOLUME_MAX_ELEMENT_SIZE = 0.005


def build_tee_volume_model() -> Model:
    model = Model("PipeTeeVolumeReview", standard="ASME_B31.3")
    model.add_material(
        "Steel",
        E=2.1e11,
        nu=0.3,
        rho=7850.0,
        allowable_stress={20.0: 137.0e6},
    )
    model.add_pipe_section("Header", OD=0.1, WT=0.01)
    junction = model.add_node([0.0, 0.0, 0.0])
    left = model.add_node([-0.08, 0.0, 0.0])
    right = model.add_node([0.08, 0.0, 0.0])
    branch = model.add_node([0.0, 0.08, 0.0])
    for element_id, terminal in zip(TEE_VOLUME_ELEMENT_IDS, (left, right, branch)):
        model.add_element(
            id=element_id,
            type="pipe_straight",
            n1=junction,
            n2=terminal,
            section="Header",
            material="Steel",
        )
    model.define_tee(junction, type="welding_tee")
    model.add_support(left, type="anchor")
    model.define_load_case("Operating", gravity=True, pressure=1.0e6)
    model.validate()
    return model


def run_example(
    output_dir: str | Path = ".benchmarks/code_aster_tee_volume_review",
    *,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model = build_tee_volume_model()
    artifacts = (
        Path(artifact_dir)
        if artifact_dir is not None
        else Path(__file__).resolve().parents[1]
        / "notebooks"
        / "code_aster_results"
        / "tee_volume_operating"
    )
    artifact = import_code_aster_artifacts(model=model, work_dir=artifacts)
    if not artifact.study.metadata.get("volume_analysis") or artifact.analysis_mesh is None:
        raise RuntimeError("The tee review requires an attested native pipe-volume Code_Aster study.")
    solved_at = artifact.result_state.metadata["solve_attestation"]["solved_at"]
    artifact = stage_code_aster_artifact_evidence(artifact, output / "review_scene")
    scene = build_visualization_scene(
        model,
        analysis_meshes=[artifact.analysis_mesh],
        result_states=[artifact.result_state],
        field_notes=[
            {
                "id": "tee_volume_scope",
                "title": "3D tee result basis",
                "text": "Code_Aster 3D FE VMIS is visualization-only and is not ASME piping-code stress.",
                "position": [0.0, 0.0, 0.0],
            }
        ],
        scene_id="scene:pipe_tee_volume_review",
        created_at=solved_at,
    )
    review = build_engineering_review(
        model,
        studies=[artifact.study],
        analysis_meshes=[artifact.analysis_mesh],
        result_states=[artifact.result_state],
        package_id="review:pipe_tee_volume",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output / "review_scene",
        scene=scene,
        title="Solved native 3D pipe-tee review",
    )
    summary = {
        "project_name": model.project_name,
        "result_status": review.analysis_status,
        "stress_label": "FE VMIS (not code stress)",
        "analysis_mesh_kind": "native_pipe_volume",
        "study_id": artifact.study.id,
        "artifact_dir": str(artifacts),
        "bundle_root": str(bundle.root),
        "scene": str(bundle.root / bundle.scene_uri),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
