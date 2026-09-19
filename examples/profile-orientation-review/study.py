"""Solve (or import) the one load case and check the rolled sections against beam theory."""

import json
from pathlib import Path

import numpy as np

from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.geometry.section_mesh import _rotation_matrix, beam_local_frame
from tuba.reporting import build_engineering_review
from tuba.visualization import add_scene_label, SceneRequest, build_visualization_scene, write_engineering_review_with_scene
from tuba.visualization.scene import GeometryAsset, SceneLayer, SceneObject

#: One ordinary linear solve: the same 500 N tip force at every roll.
LOAD_CASES = ("global",)
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None

VISUAL_SCALE = 12.0


def check_solved_response(model, runs, *, rolls, length) -> list[dict]:
    """Fail publication if rolled stiffness, force basis or rotation sign is wrong."""
    rows = []
    properties = model.sections["IPE100"].properties
    for run in runs:
        state = run.result_state
        for roll in rolls:
            tip = model.get_element(f"roll{roll}_11").n2
            basis = np.asarray(beam_local_frame([0, 0, 0], [1, 0, 0], twist_angle_deg=roll))
            solved = np.asarray(state.node_displacements[tip])
            force = next(f for f in model.load_cases[state.load_case].nodal_forces if f.node == tip)
            local_force = basis @ np.asarray(force.components[:3])
            displacement = basis @ solved[:3]
            rotation = basis @ solved[3:]
            # Timoshenko reference for POU_D_T, including the catalog shear factors.
            # Local y bends about z, local z about y; catalog offsets add tiny torsion.
            expected_u = np.array([0, local_force[1] * length**3 / (3 * 2e11 * properties["IZ"]),
                                   local_force[2] * length**3 / (3 * 2e11 * properties["IY"])])
            shear_modulus = 2e11 / (2 * (1 + 0.3))
            expected_u[1] += local_force[1] * length * properties["AY"] / (shear_modulus * properties["A"])
            expected_u[2] += local_force[2] * length * properties["AZ"] / (shear_modulus * properties["A"])
            expected_r = np.array([0, -local_force[2] * length**2 / (2 * 2e11 * properties["IY"]),
                                   local_force[1] * length**2 / (2 * 2e11 * properties["IZ"])])
            np.testing.assert_allclose(displacement, expected_u, rtol=1e-5, atol=1e-7)
            np.testing.assert_allclose(rotation, expected_r, rtol=1e-5, atol=1e-7)
            rows.append({"load_case": state.load_case, "roll_deg": roll, "tip_global_m": solved[:3].tolist(),
                         "tip_local_m": displacement.tolist(), "rotation_local_rad": rotation.tolist()})
    global_rows = [r for r in rows if r["load_case"] == "global"]
    weak, mixed, strong = [abs(r["tip_global_m"][2]) for r in global_rows]
    assert weak > mixed > strong, "The same tip force must resolve distinct weak/mixed/strong responses."
    return rows


def check(solved):
    """Rolled stiffness, force basis and rotation sign must match beam theory before a solve becomes evidence."""
    check_solved_response(
        solved.model,
        [solved.runs[case] for case in LOAD_CASES],
        rolls=solved.namespace["ROLLS"],
        length=solved.namespace["LENGTH"],
    )


def _add_frames(scene, model, runs, states, rolls):
    colors = ("#ef4444", "#22c55e", "#3b82f6")
    for kind, label in (("original", "Original local basis (x red, y green, z blue)"),
                        ("deformed", "Solved section frames (same deformation scale)")):
        scene.layers.append(SceneLayer(id=f"profile:{kind}_axes", category="annotations", label=label))
    for roll in rolls:
        basis = beam_local_frame([0, 0, 0], [1, 0, 0], twist_angle_deg=roll)
        for station in (0, 6, 12):
            elem = model.get_element(f"roll{roll}_{min(station, 11)}")
            node = elem.n2 if station == 12 else elem.n1
            origin = model.nodes[node].coords
            variants = [("original", None, None)] + [("deformed", run.result_state, state) for run, state in zip(runs, states)]
            for kind, result, state in variants:
                deformation = np.asarray(result.node_displacements[node]) if result else np.zeros(6)
                rotation = _rotation_matrix(deformation[3:] * VISUAL_SCALE)
                for axis, direction, color in zip("xyz", basis, colors):
                    end = origin + direction * 0.27
                    side = basis[("xyz".index(axis) + 1) % 3]
                    base = [p.tolist() for p in (origin, end, end - direction * 0.06 + side * 0.03,
                                                 end, end - direction * 0.06 - side * 0.03)]
                    points = [(origin + deformation[:3] * VISUAL_SCALE + rotation @ (np.asarray(p) - origin)).tolist() for p in base]
                    key = f"profile:{kind}:{result.load_case if result else 'cold'}:{roll}:{station}:{axis}"
                    metadata = ({"geometry_state_id": state.id, "result_state_id": result.id, "load_case": result.load_case,
                                 "purpose": "visualization"} if result else {})
                    scene.objects.append(SceneObject(id=key, kind="section_frame", name=f"{kind} local {axis}, roll {roll}, station {station}",
                        geometry_asset_id=f"geometry:{key}", layer_ids=[f"profile:{kind}_axes"], metadata=metadata))
                    scene.geometry_assets.append(GeometryAsset(id=f"geometry:{key}", format="polyline", object_ids=[key],
                        bounds=[*np.min(points, axis=0), *np.max(points, axis=0)], generation_config={
                            "source": f"tuba.{kind}.section_frame", "points": points, "base_points": base, "color": color,
                            "visual_scale": VISUAL_SCALE if result else 0, "section_origins": [origin.tolist()],
                            "section_deformations": [deformation.tolist()], **metadata}))


def build_review(namespace, output, *, artifact_dir=None, force=False):
    model = namespace["model"]
    rolls = namespace["ROLLS"]
    output = Path(output).resolve()
    bundle_root = output / "review_scene"
    case = LOAD_CASES[0]
    run = (import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir)) if artifact_dir is not None else
           model.solve(load_case=case, work_dir=str(output / "solver" / case), force=force))
    run.validate_for_publication(model)
    rows = check_solved_response(model, [run], rolls=rolls, length=namespace["LENGTH"])
    run = stage_runs({case: run}, bundle_root)[case]
    state = create_visual_deformed_geometry_state(model=model, result_state=run.result_state, visual_scale=VISUAL_SCALE)
    solved_at = run.result_state.metadata["solve_attestation"]["solved_at"]
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=[run], geometry_states=[state],
                                      scene_id="scene:profile-orientation-review", created_at=solved_at))
    _add_frames(scene, model, [run], [state], rolls)
    for index, roll in enumerate(rolls):
        add_scene_label(scene, f"{roll} deg roll", [-0.2, index * 1.2, 0.3], label_id=f"roll-{roll}", height=0.15)
    review = build_engineering_review(model, analysis_runs=[run], package_id="review:profile-orientation", created_at=solved_at)
    write_engineering_review_with_scene(review, bundle_root, scene=scene, title=model.project_name, source=namespace["__file__"])
    (bundle_root / "orientation-checks.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return bundle_root
