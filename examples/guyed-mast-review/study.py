"""Solve (or import) the wind case and review which guys carry the mast."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import

LOAD_CASES = ("Wind",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    run = None if artifact_dir is not None else solve_or_import(model, LOAD_CASES[0], Path(output) / "solver", solver_options=SOLVER_OPTIONS)
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:guyed_mast_review",
        title="Cable",
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
