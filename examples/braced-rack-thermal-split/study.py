"""Solve (or import) the braced-rack thermal split and review its load paths.

The review annotates the fixed point and X-braced end bays, alongside solved
rack axial displacement, relative pipe/shoe movement and ground reactions.

One line on a four-bay frame. The name says the thermal split, not the geometry,
because the case is one pipe growing at four times the rate of the steel under
it - a multi-line rack is a different question and belongs in its own example.
"""

from math import hypot, isfinite
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


def _add_rack_labels(scene, namespace, result_state):
    model = namespace["model"]

    def required(values, node, components, quantity):
        try:
            data = tuple(float(values[node][index]) for index in components)
        except (KeyError, IndexError, TypeError, ValueError):
            raise ValueError(f"Missing Code_Aster {quantity} at node {node}.") from None
        if not all(isfinite(value) for value in data):
            raise ValueError(f"Non-finite Code_Aster {quantity} at node {node}.")
        return data

    rack_nodes = {node for element in model.elements if element.type == "beam" for node in (element.n1, element.n2)}
    shoes = [support for support in model.supports if support.type == "rest" and support.attached_to]
    feet = [support.node for support in model.supports
            if support.type == "anchor" and support.attached_to is None and support.node in rack_nodes
            and any(bay * namespace["BAY_LENGTH"] <= model.nodes[support.node].coords[0]
                    <= (bay + 1) * namespace["BAY_LENGTH"] for bay in namespace["BRACED_BAYS"])]
    if not rack_nodes or not shoes or not feet:
        raise ValueError("Rack annotations require beam nodes, attached sliding shoes and end-bay ground anchors.")
    displacements = result_state.node_displacements
    rack_dx = max(abs(required(displacements, node, (0,), "DX")[0]) for node in rack_nodes)
    shoe_dx = max(abs(required(displacements, support.node, (0,), "DX")[0]
                      - required(displacements, support.attached_to, (0,), "DX")[0]) for support in shoes)
    foot_force = max(hypot(*required(result_state.node_reactions, node, (0, 1, 2), "reaction FX/FY/FZ"))
                     for node in feet)
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
        f"Rack max |DX|: {rack_dx * 1000:.1f} mm",
        [STATION_X[0], PIPE_Y, SHOE_Z - 0.3],
        label_id="label-rack-growth",
        height=0.30,
    )
    add_scene_label(
        scene,
        f"Max pipe/shoe relative |DX|: {shoe_dx * 1000:.1f} mm",
        [STATION_X[1], PIPE_Y, PIPE_Z],
        label_id="label-pipe-slide",
        height=0.30,
    )
    add_scene_label(
        scene,
        f"Max end-bay ground reaction |F|: {foot_force / 1000:.1f} kN",
        [STATION_X[0], 0.0, 0.2],
        label_id="label-braced-foot",
        height=0.25,
    )


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    run = solve_or_import(
        model, LOAD_CASES[0], Path(output) / "solver", artifact_dir=artifact_dir, solver_options=SOLVER_OPTIONS
    )
    summary = run_example(
        output,
        artifact_dir=artifact_dir,
        run=run,
        model=model,
        scene_id="scene:braced_rack_thermal_split",
        title="Solved braced-rack thermal split",
        include_load_paths=True,
        scene_modifier=lambda scene: _add_rack_labels(scene, namespace, run.result_state),
        source=namespace["__file__"],
    )
    return Path(summary["bundle_root"])
