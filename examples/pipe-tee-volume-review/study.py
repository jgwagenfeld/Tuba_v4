"""Solve (or import) the tee as native 3D solids and publish the stress review."""

from pathlib import Path
from types import SimpleNamespace

from tuba.analysis.code_aster_artifacts import stage_code_aster_artifact_evidence
from tuba.reporting import build_engineering_review
from tuba.visualization import (
    add_scene_label,
    SceneRequest,
    build_visualization_scene,
    write_engineering_review_with_scene,
)

LOAD_CASES = ("Operating",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
#: Which elements become 3D solids, and how finely Gmsh meshes them.
VOLUME_EXPORT = {"element_ids": ("header_left", "header_right", "branch"), "max_element_size": 0.005}


def check(solved):
    """The tee is reviewed as native 3D solids; a run without its volume mesh never becomes evidence."""
    run = solved.runs[LOAD_CASES[0]]
    if not run.study.metadata.get("volume_analysis") or run.analysis_mesh is None:
        raise RuntimeError("The tee review requires an attested native pipe-volume Code_Aster study.")


def build_review(namespace, output, *, artifact_dir=None, force=False):
    # Imported here: loading this study for VOLUME_EXPORT alone must not need examples/.
    from examples.code_aster_artifact_review import solve_or_import

    model = namespace["model"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    artifact = solve_or_import(
        model,
        LOAD_CASES[0],
        output / "solver",
        artifact_dir=artifact_dir,
        solver_options=SOLVER_OPTIONS,
        volume_export=VOLUME_EXPORT,
    )
    check(SimpleNamespace(model=model, namespace=namespace, runs={LOAD_CASES[0]: artifact}))
    solved_at = artifact.result_state.metadata["solve_attestation"]["solved_at"]
    artifact = stage_code_aster_artifact_evidence(artifact, output / "review_scene")
    scene = build_visualization_scene(SceneRequest(
        model,
        analysis_runs=[artifact],
        field_notes=[
            {
                "id": "tee_volume_scope",
                "title": "3D tee result basis",
                "text": "Code_Aster 3D FE VMIS is visualization-only and is not piping-code stress.",
                "position": [0.0, 0.0, 0.0],
            }
        ],
        scene_id="scene:pipe_tee_volume_review",
        created_at=solved_at,
    ))
    add_scene_label(scene, "3D Solid Tee (HEXA20)", [0.0, 0.04, 0.09], label_id="label-solid-tee", height=0.035)
    add_scene_label(scene, "1D Pipe Run (TUYAU_3M)", [-0.15, 0.0, 0.08], label_id="label-1d-pipe", height=0.035)
    add_scene_label(scene, "Kinematic Coupling (3D_TUYAU)", [0.0, 0.14, 0.08], label_id="label-coupling", height=0.035)
    review = build_engineering_review(
        model,
        analysis_runs=[artifact],
        package_id="review:pipe_tee_volume",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output / "review_scene",
        scene=scene,
        title="Solved native 3D pipe-tee review",
        source=namespace["__file__"],
    )
    return bundle.root
