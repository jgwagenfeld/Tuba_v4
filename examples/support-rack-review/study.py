"""Solve (or import) the operating case and review the rack's load paths."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.rules import SupportSpacingRule
from tuba.visualization import add_scene_label

LOAD_CASES = ("Operating",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None


def _add_rack_labels(scene):
    add_scene_label(scene, "Rest shoe on rack beam (μ = 0.3)", [0.0, 0.0, 3.55], label_id="label-shoe-left", height=0.18)
    add_scene_label(scene, "Rack Crossbeam (IPE100)", [0.0, -0.6, 3.20], label_id="label-crossbeam", height=0.18)


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
        scene_modifier=_add_rack_labels,
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
