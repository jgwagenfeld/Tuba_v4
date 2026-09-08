"""Three rolled IPE100 cantilevers: real Code_Aster global/local load comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tuba import Model
from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts, stage_code_aster_artifact_evidence
from tuba.geometry.section_mesh import beam_local_frame, _rotation_matrix
from tuba.reporting import build_engineering_review
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene
from tuba.visualization.scene import GeometryAsset, SceneObject, SceneLayer

ROLLS = (0, 45, 90)
LENGTH = 3.0
FORCE = 500.0
VISUAL_SCALE = 12.0
CASES = ("global", "local")


def build_model() -> Model:
    """One model, three disconnected copies; local nodal forces resolved to global."""
    model = Model("I-section orientation: global and local loading")
    model.add_material("steel", E=2e11, nu=0.3, rho=7850, alpha=1.2e-5)
    model.add_ibeam_section("IPE100", "IPE100")
    global_case = model.define_load_case("global", gravity=False)
    local_case = model.define_load_case("local", gravity=False)
    for index, roll in enumerate(ROLLS):
        nodes = [model.add_node([station * LENGTH / 12, index * 1.2, 0]) for station in range(13)]
        for station in range(12):
            model.add_element(id=f"roll{roll}_{station}", type="beam", n1=nodes[station], n2=nodes[station+1],
                              section="IPE100", material="steel", twist_angle=roll)
        model.add_support(id=f"anchor{roll}", node=nodes[0], type="anchor")
        global_case.add_nodal_force(nodes[-1], [0, 0, -FORCE])
        _, _, local_z = beam_local_frame([0,0,0], [1,0,0], twist_angle_deg=roll)
        # Author forces to 1e-10 N: libm's last bit differs across Windows/Linux.
        local_case.add_nodal_force(nodes[-1], [round(float(value), 10) for value in -FORCE * local_z])
    return model


def check_solved_response(model, runs) -> list[dict]:
    """Fail publication if rolled stiffness, force basis or rotation sign is wrong."""
    rows = []
    properties = model.sections["IPE100"].properties
    for run in runs:
        state = run.result_state
        for roll in ROLLS:
            tip = model.get_element(f"roll{roll}_11").n2
            basis = np.asarray(beam_local_frame([0,0,0], [1,0,0], twist_angle_deg=roll))
            solved = np.asarray(state.node_displacements[tip])
            force = next(f for f in model.load_cases[state.load_case].nodal_forces if f.node == tip)
            local_force = basis @ np.asarray(force.components[:3])
            displacement = basis @ solved[:3]
            rotation = basis @ solved[3:]
            # Timoshenko reference for POU_D_T, including the catalog shear factors.
            # Local y bends about z, local z about y; catalog offsets add tiny torsion.
            expected_u = np.array([0, local_force[1] * LENGTH**3 / (3*2e11*properties["IZ"]),
                                    local_force[2] * LENGTH**3 / (3*2e11*properties["IY"])])
            shear_modulus = 2e11 / (2 * (1 + 0.3))
            expected_u[1] += local_force[1] * LENGTH * properties["AY"] / (shear_modulus * properties["A"])
            expected_u[2] += local_force[2] * LENGTH * properties["AZ"] / (shear_modulus * properties["A"])
            expected_r = np.array([0, -local_force[2]*LENGTH**2/(2*2e11*properties["IY"]),
                                     local_force[1]*LENGTH**2/(2*2e11*properties["IZ"])])
            np.testing.assert_allclose(displacement, expected_u, rtol=1e-5, atol=1e-7)
            np.testing.assert_allclose(rotation, expected_r, rtol=1e-5, atol=1e-7)
            rows.append({"load_case":state.load_case, "roll_deg":roll, "tip_global_m":solved[:3].tolist(),
                         "tip_local_m":displacement.tolist(), "rotation_local_rad":rotation.tolist()})
    local = [r["tip_local_m"] for r in rows if r["load_case"] == "local"]
    np.testing.assert_allclose(local, np.tile(local[0], (3,1)), rtol=1e-6, atol=1e-9)
    global_rows = [r for r in rows if r["load_case"] == "global"]
    weak, mixed, strong = [abs(r["tip_global_m"][2]) for r in global_rows]
    assert weak > mixed > strong, "Global loading must resolve distinct weak/mixed/strong responses."
    return rows


def _add_frames(scene, model, runs, states):
    colors = ("#ef4444", "#22c55e", "#3b82f6")
    for kind, label in (("original", "Original local basis (x red, y green, z blue)"),
                        ("deformed", "Solved section frames (same deformation scale)")):
        scene.layers.append(SceneLayer(id=f"profile:{kind}_axes", category="annotations", label=label))
    for roll in ROLLS:
        basis = beam_local_frame([0,0,0], [1,0,0], twist_angle_deg=roll)
        for station in (0,6,12):
            elem = model.get_element(f"roll{roll}_{min(station,11)}")
            node = elem.n2 if station == 12 else elem.n1
            origin = model.nodes[node].coords
            variants = [("original", None, None)] + [("deformed", run.result_state, state) for run,state in zip(runs,states)]
            for kind, result, state in variants:
                deformation = np.asarray(result.node_displacements[node]) if result else np.zeros(6)
                rotation = _rotation_matrix(deformation[3:] * VISUAL_SCALE)
                for axis, direction, color in zip("xyz",basis,colors):
                    end = origin + direction * 0.27
                    side = basis[("xyz".index(axis) + 1) % 3]
                    base = [p.tolist() for p in (origin, end, end-direction*0.06+side*0.03,
                                                 end, end-direction*0.06-side*0.03)]
                    points = [(origin+deformation[:3]*VISUAL_SCALE+rotation@(np.asarray(p)-origin)).tolist() for p in base]
                    key = f"profile:{kind}:{result.load_case if result else 'cold'}:{roll}:{station}:{axis}"
                    metadata = ({"geometry_state_id":state.id,"result_state_id":result.id,"load_case":result.load_case,
                                 "purpose":"visualization"} if result else {})
                    scene.objects.append(SceneObject(id=key, kind="section_frame", name=f"{kind} local {axis}, roll {roll}, station {station}",
                        geometry_asset_id=f"geometry:{key}", layer_ids=[f"profile:{kind}_axes"], metadata=metadata))
                    scene.geometry_assets.append(GeometryAsset(id=f"geometry:{key}",format="polyline",object_ids=[key],
                        bounds=[*np.min(points,axis=0),*np.max(points,axis=0)],generation_config={
                            "source":f"tuba.{kind}.section_frame", "points":points,"base_points":base,"color":color,
                            "visual_scale":VISUAL_SCALE if result else 0, "section_origins":[origin.tolist()],
                            "section_deformations":[deformation.tolist()], **metadata}))


def run_example(output_dir: str | Path = ".build/profile-orientation-review", *, artifact_dir: str | Path | None = None,
                force: bool = False) -> dict:
    """Solve both ordinary linear cases, or import both attested artifact folders."""
    model = build_model()
    output = Path(output_dir).resolve()
    bundle_root = output / "review_scene"
    runs = [(import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir)/case) if artifact_dir is not None else
             model.solve(load_case=case, work_dir=str(output/"solver"/case), force=force)) for case in CASES]
    for run in runs:
        run.validate_for_publication(model)
    rows = check_solved_response(model, runs)
    runs = [stage_code_aster_artifact_evidence(run,bundle_root,artifact_subdir=f"artifacts/{run.result_state.load_case}") for run in runs]
    states = [create_visual_deformed_geometry_state(model=model,result_state=run.result_state,visual_scale=VISUAL_SCALE) for run in runs]
    solved_at = runs[0].result_state.metadata["solve_attestation"]["solved_at"]
    scene = build_visualization_scene(model,analysis_runs=runs,geometry_states=states,
                                     scene_id="scene:profile-orientation-review",created_at=solved_at)
    _add_frames(scene,model,runs,states)
    from tuba.visualization import add_scene_label
    for index,roll in enumerate(ROLLS):
        add_scene_label(scene,f"{roll} deg roll",[-0.2,index*1.2,0.3],label_id=f"roll-{roll}",height=0.15)
    review = build_engineering_review(model,analysis_runs=runs,package_id="review:profile-orientation",created_at=solved_at)
    write_engineering_review_with_scene(review,bundle_root,scene=scene,title=model.project_name,source=__file__)
    (bundle_root/"orientation-checks.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    return {"scene":str(bundle_root/"scene.json"),"checks":rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",default=".build/profile-orientation-review")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    print(json.dumps(run_example(args.output_dir,artifact_dir=args.artifact_dir,force=args.force),indent=2))
