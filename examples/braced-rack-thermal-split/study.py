"""Solve (or import) the braced-rack thermal split and review its load paths.

The review annotates what an engineer checks on a rack like this: the fixed
point, the X-braced end bays, how far the steel has grown, how far the shoes
have slid, and that the 4 MPa design pressure alone nearly fills the pipe's
stress budget at 400 C.

One line on a four-bay frame. The name says the thermal split, not the geometry,
because the case is one pipe growing at four times the rate of the steel under
it - a multi-line rack is a different question and belongs in its own example.
"""

from pathlib import Path

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.visualization import add_scene_label

LOAD_CASES = ("Operating",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None

# x of each rack station: 0, 6, 12, 18, 24 m on the shoe level.
STATION_X = (0.0, 6.0, 12.0, 18.0, 24.0)
ANCHOR_STATION = 2
PIPE_Y = 1.2
SHOE_Z = 5.5
PIPE_Z = 5.5 + 0.33655
LOWER_LEVEL = 3.0


def _add_rack_labels(scene):
    add_scene_label(
        scene,
        "Fixed point at mid-run: the line's only anchor",
        [STATION_X[ANCHOR_STATION], PIPE_Y, PIPE_Z],
        label_id="label-anchor",
        height=0.30,
    )
    add_scene_label(
        scene,
        "X-braced end bay, gusseted at the crossing",
        [STATION_X[0], 0.0, LOWER_LEVEL],
        label_id="label-bracing",
        height=0.30,
    )
    add_scene_label(
        scene,
        "Rack steel 120 C: grows 13 mm per 12 m",
        [STATION_X[0], PIPE_Y, SHOE_Z - 0.3],
        label_id="label-rack-growth",
        height=0.30,
    )
    add_scene_label(
        scene,
        "Hot line 400 C: shoes slide 40 mm at the ends",
        [STATION_X[1], PIPE_Y, PIPE_Z],
        label_id="label-pipe-slide",
        height=0.30,
    )
    add_scene_label(
        scene,
        "End-bay feet: 24 kN each, the braced bay's share",
        [STATION_X[0], 0.0, 0.2],
        label_id="label-braced-foot",
        height=0.25,
    )


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    run = None if artifact_dir is not None else solve_or_import(
        model, LOAD_CASES[0], Path(output) / "solver", solver_options=SOLVER_OPTIONS
    )
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:braced_rack_thermal_split",
        title="Solved braced-rack thermal split",
        include_load_paths=True,
        scene_modifier=_add_rack_labels,
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
