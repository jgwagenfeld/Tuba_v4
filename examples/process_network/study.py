"""Code_Aster study of the current verified steady-water operating state.

Studio maps passing pandapipes evidence onto a copy of the authored model before
calling this study. The wall-temperature approximation is an explicit input;
hydraulic success alone is not a completed structural evaluation.
"""

from tuba.project.study import build_study_review


LOAD_CASES = ("WaterOperating",)
SOLVER_OPTIONS = {"pipe_modelization": "TUYAU_3M"}
WALL_TEMPERATURE_MODEL = "bulk-fluid-equals-wall-steady"


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Publish verified Code_Aster results through Tuba's existing web scene."""
    return build_study_review(
        namespace, output, artifact_dir=artifact_dir, force=force,
        scene_id="scene:process-studio", title="Steady water operating review",
    )
