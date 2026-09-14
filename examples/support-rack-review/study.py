"""Solve (or import) the operating case and review the rack's load paths."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.rules import SupportSpacingRule

LOAD_CASES = ("Operating",)
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
        scene_id="scene:support_rack_review",
        title="Solved support-rack load-path review",
        include_load_paths=True,
        # An engineer-authored project limit, not a code requirement: the 4 m rack
        # span exceeds it, so the review carries a design-rule annotation beside
        # its solver evidence.
        model_rules=[SupportSpacingRule(max_span_m=3.5)],
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
