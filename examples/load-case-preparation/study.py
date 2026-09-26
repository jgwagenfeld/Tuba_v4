"""Solve four states and export signed components for independently verified checks."""

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.project import load_project
from tuba.project.solve import solve_project
from tuba.reporting import build_engineering_review
from tuba.visualization import SceneBuildOptions, SceneRequest, add_scene_label, build_visualization_scene, write_engineering_review_with_scene

LOAD_CASES = ("Sustained", "OperatingHot", "Occasional", "PressureOnly")
SOLVER_OPTIONS = {"pipe_modelization": "TUYAU_3M"}
VOLUME_EXPORT = None
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence"
COMPONENTS = ("N_N", "Vy_N", "Vz_N", "Mx_Nm", "My_Nm", "Mz_Nm")


def force_rows(model, runs):
    """Element-end local forces; expansion is a signed difference, never VMIS subtraction.

    End values are a starting point for checks, not an envelope of interior mesh stations.
    Linear elastic response and unchanged supports are assumptions of this example.
    """
    rows = []
    for element in model.elements:
        for end in ("n1", "n2"):
            vectors = {}
            for case in LOAD_CASES:
                state = runs[case].result_state
                if state.load_case != case:
                    raise ValueError(f"Expected {case} evidence, got {state.load_case}.")
                vector = np.asarray(state.element_results[element.id][f"forces_{end}"], dtype=float)
                if vector.shape != (6,) or not np.isfinite(vector).all():
                    raise ValueError(f"Missing or non-finite forces: {case}/{element.id}/{end}.")
                vectors[case] = vector
                rows.append({"case": case, "element": element.id, "end": end,
                             "result_state_id": state.id, "reference_result_state_id": "",
                             **dict(zip(COMPONENTS, vector))})
            difference = vectors["OperatingHot"] - vectors["Sustained"]
            rows.append({"case": "ExpansionRange", "element": element.id, "end": end,
                         "result_state_id": runs["OperatingHot"].result_state.id,
                         "reference_result_state_id": runs["Sustained"].result_state.id,
                         **dict(zip(COMPONENTS, difference))})
    return rows


def check(solved):
    """Require complete solved components and distinguish the thermal/event responses."""
    rows = force_rows(solved.model, solved.runs)
    by_case = {case: np.array([[row[key] for key in COMPONENTS] for row in rows if row["case"] == case])
               for case in (*LOAD_CASES, "ExpansionRange")}
    for case in ("OperatingHot", "Occasional", "PressureOnly"):
        if np.allclose(by_case[case], by_case["Sustained"], rtol=1e-6, atol=1e-6):
            raise ValueError(f"{case} did not produce a distinct response from Sustained.")


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    if artifact_dir is None:
        runs = solve_project(load_project(Path(namespace["__file__"]).parent), namespace, force=force).runs
    else:
        runs = {case: import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir) / case)
                for case in LOAD_CASES}
    for run in runs.values():
        run.validate_for_publication(model)
    check(SimpleNamespace(model=model, runs=runs))
    rows = force_rows(model, runs)
    root = Path(output).resolve() / "review_scene"
    runs = stage_runs(runs, root)
    states = [create_visual_deformed_geometry_state(model=model, result_state=run.result_state, visual_scale=20.0)
              for run in runs.values()]
    solved_at = runs["OperatingHot"].result_state.metadata["solve_attestation"]["solved_at"]
    scene = build_visualization_scene(SceneRequest(
        model, analysis_runs=list(runs.values()), geometry_states=states,
        options=SceneBuildOptions(include_loads=True),
        scene_id="scene:load-case-preparation", created_at=solved_at))
    add_scene_label(scene, "Four solved states - user-owned checks", [0.0, 0.0, -0.5], label_id="check-basis")
    review = build_engineering_review(model, analysis_runs=list(runs.values()),
                                      package_id="review:load-case-preparation", created_at=solved_at)
    write_engineering_review_with_scene(review, root, scene=scene,
                                        title=model.project_name, source=namespace["__file__"])
    with (root / "user-check-forces.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return root
