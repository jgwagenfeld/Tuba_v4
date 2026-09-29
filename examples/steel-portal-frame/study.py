"""Solve the hall's gravity and wind cases, or import its committed evidence.

The interface is the one every ``examples/`` project uses: ``LOAD_CASES``,
``SOLVER_OPTIONS``, ``VOLUME_EXPORT``, ``ARTIFACT_DIR`` and ``build_review``, so
the studio, the gallery builder and the refresh tooling all load it unchanged.

Evidence lives in ``evidence/<case>/`` and is attested to the model by
``validate_for_publication``, which is what stops a stale folder from being
presented as this hall's result.

What this study exports, and why:

* ``section-forces.csv`` - the six section forces at both ends of every member,
  per load case. For a 1D steel frame these *are* the design quantities: a
  member code consumes N, Vy, Vz, Mt, My, Mz, not an equivalent stress. Each row
  carries the member's ``twist_deg`` because that rotation decides which of the
  section's two inertias each moment refers to, and therefore which column of
  this table is the strong-axis check.
* von Mises is not exported, because Code_Aster is never asked for it on a
  pipe-free model. See the model docstring.
"""

import csv
from pathlib import Path

import numpy as np

from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.project import load_project
from tuba.project.solve import solve_project
from tuba.reporting import build_engineering_review
from tuba.visualization import (
    SceneBuildOptions,
    SceneRequest,
    add_scene_label,
    build_visualization_scene,
    write_engineering_review_with_scene,
)

LOAD_CASES = ("Gravity", "Wind")
SOLVER_OPTIONS = {"line_segments": 1}
VOLUME_EXPORT = None
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence"

#: Local element force components, in the order Code_Aster writes EFGE_ELNO.
COMPONENTS = ("N", "Vy", "Vz", "Mt", "My", "Mz")

#: The visual exaggeration for the deformed shape. A hall this size deflects a
#: few millimetres under gravity, which is invisible at true scale, so the scene
#: says how far it is scaled rather than letting the number pass unremarked.
GRAVITY_VISUAL_SCALE = 200.0
WIND_VISUAL_SCALE = 4.0


def section_force_rows(model, runs) -> list[dict]:
    """Member-end section forces for every member and case, ready for a CSV.

    These are the numbers a member check consumes. The first-order caveat travels
    with them in a column, because a moment read without it can be mistaken for a
    design value.
    """
    rows: list[dict] = []
    for case, run in runs.items():
        results = run.result_state.element_results
        for element in model.elements:
            record = results.get(element.id)
            if record is None:
                raise ValueError(f"{case}: no element results for {element.id!r}.")
            for end, suffix in (("n1", "1"), ("n2", "2")):
                key = f"forces_{end}"
                if key not in record:
                    raise ValueError(f"{case}/{element.id}: {key} missing from results.")
                values = np.asarray(record[key], dtype=float)
                if values.shape != (6,) or not np.isfinite(values).all():
                    raise ValueError(
                        f"{case}/{element.id}/{end}: missing or non-finite section forces."
                    )
                rows.append({
                    "case": case,
                    "element": element.id,
                    "end": suffix,
                    "section": element.section,
                    "type": element.type,
                    "twist_deg": float(getattr(element, "twist_angle", 0.0)),
                    "analysis": "first-order (no P-Delta)",
                    "result_state_id": run.result_state.id,
                    **dict(zip(COMPONENTS, values)),
                })
    return rows


def write_section_forces(path: Path, rows: list[dict]) -> Path:
    target = path / "section-forces.csv"
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return target


def summarise(model, runs) -> None:
    """Print what Code_Aster actually computed.

    Von Mises is deliberately absent: Tuba requests Code_Aster's ``SIEQ``
    equivalent-stress field only for models containing pipe elements, and this is
    a pure structural frame. An absent number means "not computed", never zero.
    """
    for case, run in runs.items():
        state = run.result_state
        displacements = state.node_displacements
        if not displacements:
            print(f"{case}: no displacement results")
            continue
        values = np.array([np.asarray(v, dtype=float) for v in displacements.values()])
        magnitude = np.linalg.norm(values, axis=1)
        worst = list(displacements.keys())[int(magnitude.argmax())]
        reactions = state.node_reactions
        peak = 0.0
        if reactions:
            peak = float(np.abs(np.array(
                [np.asarray(v, dtype=float) for v in reactions.values()]
            )).max())
        print(f"{case}: {len(displacements)} nodes solved, "
              f"max |u| {magnitude.max() * 1000:.2f} mm at {worst} "
              f"{np.round(model.nodes[worst].coords, 1)}, "
              f"max |reaction| {peak / 1000:.1f} kN")
        buckling = state.buckling
        if buckling and buckling.critical_factors:
            governing = buckling.governing_factor
            print(f"{case}: {len(buckling)} critical load factors "
                  f"{[round(f, 1) for f in buckling.critical_factors]}")
            print(f"{case}: governing factor {governing:.1f} x this load case "
                  f"(mode {buckling.governing_mode().mode})")
    print("von Mises stress: not computed (this model has no pipe elements)")
    print("analysis is first-order: no P-Delta, so these moments understate a "
          "second-order design")
    print("a critical factor is a linearised reference load, not a design check: "
          "no initial imperfection, and a real column buckles below it")


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    if artifact_dir is None:
        runs = solve_project(
            load_project(Path(namespace["__file__"]).parent), namespace, force=force
        ).runs
    else:
        runs = {
            case: import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir) / case)
            for case in LOAD_CASES
        }
    for run in runs.values():
        run.validate_for_publication(model)

    root = Path(output).resolve() / "review_scene"
    staged = stage_runs(runs, root)
    scales = {"Gravity": GRAVITY_VISUAL_SCALE, "Wind": WIND_VISUAL_SCALE}
    states = [
        create_visual_deformed_geometry_state(
            model=model, result_state=run.result_state,
            visual_scale=scales.get(run.result_state.load_case, 1.0),
        )
        for run in staged.values()
    ]
    solved_at = staged["Gravity"].result_state.metadata["solve_attestation"]["solved_at"]

    scene = build_visualization_scene(SceneRequest(
        model,
        analysis_runs=list(staged.values()),
        geometry_states=states,
        options=SceneBuildOptions(include_loads=True),
        scene_id="scene:steel_portal_frame_hall",
        created_at=solved_at,
    ))
    add_scene_label(
        scene,
        "7 cambered bowstring portal frames - gravity and wind",
        [0.0, 18.0, 15.0], label_id="hall", height=2.2,
    )
    review = build_engineering_review(
        model, analysis_runs=list(staged.values()),
        package_id="review:steel_portal_frame", created_at=solved_at,
    )
    write_engineering_review_with_scene(
        review, root, scene=scene,
        title=model.project_name, source=namespace["__file__"],
    )
    csv_path = write_section_forces(Path(output).resolve(), section_force_rows(model, runs))
    summarise(model, runs)
    print(f"section forces: {csv_path}")
    return root


if __name__ == "__main__":
    import runpy

    namespace = runpy.run_path(str(Path(__file__).parent / "model.py"), run_name="__main__")
    build_review({**namespace, "__file__": str(Path(__file__).parent / "model.py")},
                 Path(__file__).parent / ".build")
