"""Code_Aster study scaffolded by the Tuba MCP server (TUBA_MCP_MANAGED_STUDY).

LOAD_CASES is synced from model.py's load cases while this marker is present, so the
studio's .comm tabs and Solve stay available. Edit build_review freely, or delete the
marker line to take full ownership (the server then leaves this file alone). Run the
studio from the repository root so the examples import below resolves.
"""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import

LOAD_CASES = ('Operating',)
SOLVER_OPTIONS: dict = {}
VOLUME_EXPORT = None


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Solve the study cases with Code_Aster and publish the engineering review."""
    if not LOAD_CASES:
        raise ValueError("study.py defines no LOAD_CASES: add the load case to solve (e.g. LOAD_CASES = (\"Operating\",)).")
    model = namespace["model"]
    run = None if artifact_dir is not None else solve_or_import(model, LOAD_CASES[0], Path(output) / "solver", solver_options=SOLVER_OPTIONS)
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:street_rack_bridge",
        title="Street Rack Bridge review",
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
