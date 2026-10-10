"""Fixed demonstration requirements, declared before real qualification."""

from pathlib import Path

from model import LOOP_NODE, PUMP_NODE, TIE_IN_NODE
from tuba.search import CheckSpec

LOAD_CASES = ("Sustained", "Hot")
SOLVER_OPTIONS = {"line_segments": 3}
VOLUME_EXPORT = None
CLEARANCE_M = 0.03
NOZZLE_FORCE_LIMIT_N = 10000.0
LOOP_DISPLACEMENT_LIMIT_M = 0.10

SEARCH_CHECKS = (
    CheckSpec("cold.clearance", "cold_clearance", True, (), (), None, None, {"clearance_m": CLEARANCE_M}),
    CheckSpec("operating.clearance", "operating_clearance", True, LOAD_CASES, (), None, None,
              {"envelope_type": "clearance", "clearance_m": CLEARANCE_M, "increments": "all"}),
    CheckSpec("pump.nozzle.force", "reaction_force", True, LOAD_CASES, (f"node:{PUMP_NODE}",), NOZZLE_FORCE_LIMIT_N, "N", {}),
    CheckSpec("rack.tie_in.force", "reaction_force", True, LOAD_CASES, (f"node:{TIE_IN_NODE}",), NOZZLE_FORCE_LIMIT_N, "N", {}),
    CheckSpec("loop.displacement", "displacement", True, LOAD_CASES, (f"node:{LOOP_NODE}",), LOOP_DISPLACEMENT_LIMIT_M, "m", {}),
)


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Publish only supplied native evidence; a one-shot project CLI solves first."""
    if artifact_dir is None:
        raise ValueError("Code_Aster evidence for both Sustained and Hot is required")
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    from tuba.analysis.staged_run import stage_runs
    from tuba.reporting import build_engineering_review
    from tuba.visualization import SceneRequest, build_visualization_scene, write_engineering_review_with_scene
    model = namespace["model"]
    runs = {op: import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir) / op) for op in LOAD_CASES}
    staged = stage_runs(runs, output)
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=tuple(staged.values())))
    review = build_engineering_review(model, analysis_runs=tuple(staged.values()))
    write_engineering_review_with_scene(review, output, scene=scene, source=namespace["__file__"])
    return Path(output)
