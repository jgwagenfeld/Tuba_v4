"""Run real Code_Aster and publish the imported-geometry Studio review."""

from pathlib import Path

import numpy as np

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle


LOAD_CASES = ("Combined",)
SOLVER_OPTIONS = {}
VOLUME_EXPORT = None
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / "Combined"


def check(solved):
    """Require verified native artifacts and the known external-load balance."""
    run = solved.runs["Combined"]
    run.validate_for_publication(model=solved.model)
    force, moment = np.zeros(3), np.zeros(3)
    for node_id, point in run.analysis_mesh.nodes.items():
        values = run.result_state.node_reactions.get(node_id)
        if values is None:
            continue
        reaction = np.asarray(values[:3])
        force += reaction
        moment += np.cross(point, reaction)
        moment += np.asarray([0 if value is None else value for value in values[3:]])
    if not np.allclose(force, [-1000, 0, -50], atol=0.01, rtol=0):
        raise ValueError(f"Native support forces do not balance the known loads: {force}.")
    if not np.allclose(moment, [10, 85, 0], atol=0.01, rtol=0):
        raise ValueError(f"Native support moments do not balance the known loads: {moment}.")


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Import attested project evidence into the existing web-scene path."""
    if artifact_dir is None:
        raise RuntimeError("This review requires real Code_Aster evidence; use Studio Solve.")
    model = namespace["model"]
    run = import_code_aster_artifacts(model=model, work_dir=artifact_dir)
    root = Path(output) / "review_scene"
    run = stage_runs({"Combined": run}, root)["Combined"]
    write_scene_bundle(build_visualization_scene(SceneRequest(model, analysis_runs=[run])), root)
    return root
