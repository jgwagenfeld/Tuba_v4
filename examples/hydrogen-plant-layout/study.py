"""Code_Aster study for the Green Hydrogen Production & Storage Facility.

Solves the Operating load case with Code_Aster and builds the reviewable
interactive 3D scene bundle.
"""

from pathlib import Path
from typing import Any

from examples.code_aster_artifact_review import run_example, solve_or_import
from tuba.visualization import add_scene_label

LOAD_CASES = ('Operating',)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None

#: Review names for the analytical obstacles, so the 3D scene names the plant
#: rather than showing bare boxes. The ids are the model's obstacle ids.
OBSTACLE_LABELS = {
    "electrolyzer_building": "Electrolyzer Hall",
    "compressor_station": "Compressor Station",
    "purification_building": "Purification & DeOxo",
    "h2_storage_bullet_1": "HP H2 Storage Bullet 1",
    "h2_storage_bullet_2": "HP H2 Storage Bullet 2",
    "substation_control_room": "Substation & Control Room",
}
LABEL_HEIGHT_M = 0.9


def _add_obstacle_labels(scene: Any, model: Any) -> None:
    """Label every cuboid/cylinder obstacle above its roof for the 3D review."""
    for obstacle in model.obstacles:
        text = OBSTACLE_LABELS.get(obstacle["id"])
        if text is None or obstacle.get("min_point") is None or obstacle.get("max_point") is None:
            continue
        low = obstacle["min_point"]
        high = obstacle["max_point"]
        position = [
            (float(low[0]) + float(high[0])) / 2.0,
            (float(low[1]) + float(high[1])) / 2.0,
            float(high[2]) + 1.0,
        ]
        add_scene_label(scene, text, position, label_id=obstacle["id"], height=LABEL_HEIGHT_M)


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """Solve the study cases with Code_Aster and publish the engineering review."""
    if not LOAD_CASES:
        raise ValueError('study.py defines no LOAD_CASES: add the load case to solve (e.g. LOAD_CASES = ("Operating",)).')
    model = namespace["model"]
    if artifact_dir is None and ARTIFACT_DIR.is_dir():
        artifact_dir = ARTIFACT_DIR
    run = None if artifact_dir is not None else solve_or_import(
        model,
        LOAD_CASES[0],
        Path(output) / "solver",
        solver_options=SOLVER_OPTIONS,
    )
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:hydrogen_plant_layout",
        title="Green Hydrogen Plant Layout Review",
        scene_modifier=lambda scene: _add_obstacle_labels(scene, model),
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
