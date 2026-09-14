"""Solve (or import) the hot case and review displacement, clearance and route cost."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.visualization import SceneBuildOptions

LOAD_CASES = ("Hot",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None

#: Clearance band applied around the bare pipe radius for the operating clash
#: check, and for the envelope geometry published beside it so the reviewer sees
#: the band the check used.
#:
#: This is NOT the router's reserved corridor. The router reserves
#: ``OD/2 + insulation_thickness + clearance`` (0.194 m for this line), while
#: the model carries no insulation spec, so the published envelope is
#: ``OD/2 + 0.10`` = 0.144 m. The two numbers answer different questions and
#: are deliberately not unified here.
CLEARANCE_M = 0.10


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    run = None if artifact_dir is not None else solve_or_import(model, LOAD_CASES[0], Path(output) / "solver", solver_options=SOLVER_OPTIONS)
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:autorouted_expansion_loop",
        title="Solved autorouted expansion-loop review",
        route_results=[namespace["route_result"]],
        clash_clearance_m=CLEARANCE_M,
        scene_options=SceneBuildOptions(
            include_physical_envelopes=True,
            clearance_m=CLEARANCE_M,
            include_cost_overlays=True,
            # The default metric is insulation_cost, which is identically zero for
            # a line with no insulation spec. Mass is a quantity this model carries.
            cost_metric="total_mass_kg",
        ),
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
