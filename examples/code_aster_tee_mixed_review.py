"""Solve and publish one connected TUYAU_3M / native 3D tee review."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from .code_aster_tee_volume_review import (
        TEE_VOLUME_ELEMENT_IDS,
        TEE_VOLUME_MAX_ELEMENT_SIZE,
        build_tee_mixed_model,
    )
except ImportError:
    from code_aster_tee_volume_review import (
        TEE_VOLUME_ELEMENT_IDS,
        TEE_VOLUME_MAX_ELEMENT_SIZE,
        build_tee_mixed_model,
    )
from tuba.analysis.code_aster_artifacts import stage_code_aster_artifact_evidence
from tuba.reporting import build_engineering_review
from tuba.solver.modelisation import PipeModelization
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene


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
