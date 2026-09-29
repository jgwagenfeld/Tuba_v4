"""One nonlinear run through Cold, Hot, Cold, Lift and Reseat, and the review it shows."""

import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.reporting import build_engineering_review
from tuba.visualization import add_scene_label, SceneRequest, build_visualization_scene, write_engineering_review_with_scene

LOAD_PATH = ["Cold", "Hot", "Cold", "Lift", "Reseat"]
#: A load path is solved as one Code_Aster run named after its final stage, so this
#: is Reseat and the evidence folder is evidence/Reseat/. It used to be "Cold",
#: which read as though the interesting stage were the inert first one.
LOAD_CASES = ("Reseat",)
SOLVER_OPTIONS = {"pipe_modelization": "POU_D_T", "load_path": LOAD_PATH, "load_step": 0.1}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None


def check(solved):
    """The contact behaviour this comparison exists to show; a solve that misses it never becomes evidence."""
    run = solved.runs[LOAD_CASES[0]]
    friction_contacts = lambda state: {key: value for key, value in state.contact_results.items() if key.startswith("F_")}
    statuses = {contact.status for state in run.result_states for contact in friction_contacts(state).values()}
    if not {"open", "sticking", "sliding"} <= statuses:
        raise RuntimeError(f"Solved example did not resolve all required friction contact states: {sorted(statuses)}")
    hot = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 2.0))
    cooled = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 3.0))
    if not any(sum(a*b for a,b in zip(contact.tangential_force, friction_contacts(cooled)[key].tangential_force)) < 0
               for key,contact in friction_contacts(hot).items()):
        raise RuntimeError("Solved example did not demonstrate contact-force reversal on cooling.")
    uplift = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 4.0))
    if not (uplift.contact_results["F_S1"].status != "open" and uplift.contact_results["F_S2"].status == "open"
            and 0 < uplift.contact_results["F_S2"].gap < 0.01):
        raise RuntimeError("Uplift must open the friction-copy S2 by less than 10 mm while S1 remains seated.")
    if any(contact.status == "open" for contact in run.result_states[-1].contact_results.values()):
        raise RuntimeError("The final Reseat stage must put all four shoes back on the surface.")
    if any(math.hypot(*contact.tangential_force) >= 1e-8 for state in run.result_states
           for key, contact in state.contact_results.items() if key.startswith("NF_")):
        raise RuntimeError("The frictionless copy produced a nonzero tangential contact force.")


def build_review(namespace, output, *, artifact_dir=None, force=False):
    """The single-run friction comparison: checks the physics, then writes the bundle."""
    model = namespace["model"]
    output = Path(output)
    run = (import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir))
           if artifact_dir is not None else model.solve(**SOLVER_OPTIONS, force=force, work_dir=str(output / "solver")))
    run.validate_for_publication(model)
    check(SimpleNamespace(model=model, namespace=namespace, runs={LOAD_CASES[0]: run}))
    bundle_root = output / "review_scene"
    operation = run.result_state.load_case
    run = stage_runs({operation: run}, bundle_root)[operation]
    states = run.result_states or (run.result_state,)
    geometry_states = [replace(create_visual_deformed_geometry_state(model=model, result_state=state, visual_scale=20.0),
                               id=f"geometry_state:{state.id}:visual") for state in states]
    solved_at = run.result_state.metadata["solve_attestation"]["solved_at"]
    # This review is about what the shoes did, so the pipe is coloured neutrally
    # and no scalar field tints it. Every other gallery leaves review_focus unset
    # and keeps its own stress or displacement legend, shoes or no shoes.
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=[run], geometry_states=geometry_states,
                                      review_focus="contact",
                                      scene_id="scene:native-friction:comparison", created_at=solved_at))
    add_scene_label(scene, "Without friction · μ = 0", [2.0, 0.0, 0.5], label_id="frictionless-copy")
    add_scene_label(scene, "With friction · μ = 0.3", [2.0, 5.0, 0.5], label_id="friction-copy")
    review = build_engineering_review(model, analysis_runs=[run], package_id="review:native-friction:comparison", created_at=solved_at)
    write_engineering_review_with_scene(review, bundle_root, scene=scene, title=model.project_name, source=namespace["__file__"])
    return bundle_root
