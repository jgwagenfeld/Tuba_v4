"""Solve or import the shared rack's attested Code_Aster Operating case."""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.visualization import add_scene_label

LOAD_CASES = ("Operating",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    run = None if artifact_dir is not None else solve_or_import(
        model, LOAD_CASES[0], Path(output) / "solver", solver_options=SOLVER_OPTIONS,
    )

    def labels(scene):
        for route, section, od, wall, y, temperature, pressure in namespace["LINES"]:
            add_scene_label(scene, f"{route} · {section} · {temperature:g} C · {pressure / 1e6:g} MPa",
                            [0.0, y, namespace["RACK_HEIGHT"] + 0.8],
                            label_id=f"label-{route}", height=0.18)

    summary = run_example(
        output, artifact_dir=artifact_dir, run=run, model=model,
        scene_id="scene:multipipe_rack", title="Three lines on one shared rack",
        include_load_paths=True, scene_modifier=labels, source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
