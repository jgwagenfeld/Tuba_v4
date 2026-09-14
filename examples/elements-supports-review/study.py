"""Solve (or import) the load case and review the element and support definitions."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import

LOAD_CASES = ("LoadCase1",)
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
        scene_id="scene:elements_supports_review",
        title="Solved mixed element and support review",
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
