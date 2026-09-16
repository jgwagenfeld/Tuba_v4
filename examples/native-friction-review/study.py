"""One nonlinear run through Cold, Hot, Cold, Lift and Cold, and the contact review it shows."""

import csv
import html
import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import stage_runs
from tuba.reporting import build_engineering_review
from tuba.visualization import add_scene_label, build_visualization_scene, write_engineering_review_with_scene

LOAD_PATH = ["Cold", "Hot", "Cold", "Lift", "Cold"]
#: The whole load path is one Code_Aster run; the refresh names it by the case it ends in.
LOAD_CASES = ("Cold",)
SOLVER_OPTIONS = {"pipe_modelization": "POU_D_T", "load_path": LOAD_PATH, "load_step": 0.1}
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
VOLUME_EXPORT = None


def _write_contact_exports(run, root: Path) -> None:
    rows = []
    for state in run.result_states:
        for contact in state.contact_results.values():
            rows.append({"result_state_id": state.id, "stage_index": state.metadata["stage_index"],
                         "stage_label": state.metadata["stage_label"], "pseudo_time": state.metadata["pseudo_time"],
                         **contact.to_dict()})
    if not rows:
        raise RuntimeError("Code_Aster supplied no contact history; no contact demonstration can be published.")
    with (root / "contacts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, (tuple, list)) else value for key, value in row.items()} for row in rows)
    travel = [row["relative_displacement"][0] * 1000 for row in rows]
    force = [row["tangential_force"][0] / 1000 for row in rows]
    limits = [row["friction_limit"] / 1000 for row in rows]
    low, high = min(travel + [0]), max(travel + [0])
    maximum = max([abs(value) for value in force] + limits + [0.001])
    x = lambda value: 65 + 640 * (value-low) / (high-low or 1)
    y = lambda value: 155 - 110 * value / maximum
    paths = []
    for support_index, support_id in enumerate(sorted({row["support_id"] for row in rows})):
        indices = [i for i,row in enumerate(rows) if row["support_id"] == support_id]
        shade = ["#2563eb", "#0f766e"][support_index % 2]
        for values, color, dash in [(force, shade, ""), (limits, shade, "6 4"), ([-value for value in limits], shade, "6 4")]:
            points = " ".join(f"{x(travel[i]):.3f},{y(values[i]):.3f}" for i in indices)
            paths.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"><title>{html.escape(support_id)}</title></polyline>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 330" role="img" aria-label="Solved contact force versus signed tangential travel">'
    svg += '<rect width="740" height="330" fill="white"/><path d="M65 35V280H710 M65 155H710" fill="none" stroke="#64748b"/>'
    svg += ''.join(paths)
    svg += f'<g font-family="sans-serif" font-size="13" fill="#1e293b"><text x="65" y="20">Force on pipe X [kN], range ±{maximum:.4g}; dashed: ±μN</text>'
    svg += f'<text x="65" y="303">Relative X travel [mm]: {low:.4g} to {high:.4g}; ordered converged states</text><text x="65" y="323">S1 blue / S2 green. Projected component, not the full friction cone; travel is not slip.</text></g></svg>'
    (root / "contact-history.svg").write_text(svg, encoding="utf-8")


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
        raise RuntimeError("The final Cold stage must reseat all four shoes.")
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
    scene = build_visualization_scene(model, analysis_runs=[run], geometry_states=geometry_states,
                                      scene_id="scene:native-friction:comparison", created_at=solved_at)
    add_scene_label(scene, "Without friction · μ = 0", [2.0, 0.0, 0.5], label_id="frictionless-copy")
    add_scene_label(scene, "With friction · μ = 0.3", [2.0, 5.0, 0.5], label_id="friction-copy")
    review = build_engineering_review(model, analysis_runs=[run], package_id="review:native-friction:comparison", created_at=solved_at)
    write_engineering_review_with_scene(review, bundle_root, scene=scene, title=model.project_name, source=namespace["__file__"])
    _write_contact_exports(run, bundle_root)
    return bundle_root
