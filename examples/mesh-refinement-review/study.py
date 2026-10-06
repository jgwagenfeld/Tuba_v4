"""Two authentic Code_Aster levels with unchanged physics and target extents."""
from tuba.project.study import build_study_review

LOAD_CASES = ("Bending",)
SOLVER_OPTIONS = {"pipe_modelization": "TUYAU_3M"}
MESH_CONVERGENCE = {"scales": [1.0, 0.75], "relative_tolerance": 0.03}


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Publish the ordinary solved study through Tuba's verified web-scene path."""
    return build_study_review(
        namespace, output, artifact_dir=artifact_dir, force=force,
        scene_id="scene:mesh-refinement-review", title="STEP spool cantilever",
    )
