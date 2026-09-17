"""Solve and publish one connected TUYAU_3M / native 3D tee review."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tuba.analysis.code_aster_artifacts import stage_code_aster_artifact_evidence
from tuba.project import load_project
from tuba.reporting import build_engineering_review
from tuba.solver.modelisation import PipeModelization
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene

#: The solved tee's own project: this review extends that model rather than copying it.
TEE_PROJECT = load_project(Path(__file__).resolve().parent / "pipe-tee-volume-review")
_TEE_VOLUME = TEE_PROJECT.load_study().VOLUME_EXPORT
TEE_VOLUME_ELEMENT_IDS = _TEE_VOLUME["element_ids"]
TEE_VOLUME_MAX_ELEMENT_SIZE = _TEE_VOLUME["max_element_size"]
TEE_LINE_ELEMENT_IDS = ("line_left", "line_right", "line_branch")


def build_tee_mixed_model():
    """The tee with TUYAU_3M extensions on all three arms, anchored at the far left end."""
    return TEE_PROJECT.run_model()["model"]


def run_example(
    output_dir: str | Path = ".build/benchmarks/code_aster_tee_mixed_review",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model = build_tee_mixed_model()
    run = model.solve(
        load_case="Operating",
        work_dir=output / "solve",
        pipe_modelization=PipeModelization.SOLID_3D,
        volume_element_ids=TEE_VOLUME_ELEMENT_IDS,
        max_element_size=TEE_VOLUME_MAX_ELEMENT_SIZE,
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    )
    solved_at = run.result_state.metadata["solve_attestation"]["solved_at"]
    run = stage_code_aster_artifact_evidence(run, output / "review_scene")
    scene = build_visualization_scene(
        model,
        analysis_runs=[run],
        field_notes=[
            {
                "id": "tee_mixed_scope",
                "title": "Connected mixed FE result basis",
                "text": "The tee is native 3D HEXA20; its three pipe extensions are TUYAU_3M. Both use this Code_Aster solve.",
                "position": [0.0, 0.0, 0.0],
            }
        ],
        scene_id="scene:pipe_tee_mixed_review",
        created_at=solved_at,
    )
    review = build_engineering_review(
        model,
        analysis_runs=[run],
        package_id="review:pipe_tee_mixed",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output / "review_scene",
        scene=scene,
        title="Solved connected 1D / 3D pipe-tee review",
        source=__file__,
    )
    summary = {
        "project_name": model.project_name,
        "result_status": review.analysis_status,
        "stress_label": "FE VMIS (not code stress)",
        "analysis_mesh_kind": "native_mixed_tuyau_pipe_volume",
        "study_id": run.study.id,
        "solve_dir": str(output / "solve"),
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
