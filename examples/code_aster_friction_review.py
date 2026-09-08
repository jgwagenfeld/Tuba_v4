"""Real Code_Aster DIS_CHOC shoe contact, followed through a thermal load path."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import html
import json
import math
import shutil
from pathlib import Path

from tuba import Model
from tuba.model import BendGeometry
from tuba.analysis import create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts, stage_code_aster_artifact_evidence
from tuba.reporting import build_engineering_review
from tuba.visualization import add_scene_label, build_visualization_scene, write_engineering_review_with_scene, viewer_assets_path

LOAD_PATH = ["Cold", "Hot", "Cold", "Lift", "Cold"]


def _new_friction_model(project_name: str) -> Model:
    model = Model(project_name)
    model.add_material("steel", E=2e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("pipe", OD=0.1143, WT=0.006)
    for name, temperature in [("Cold",20.0), ("Hot",120.0), ("Lift",20.0)]:
        model.define_load_case(name, gravity=True, pressure=0.0, temperature=temperature, ref_temperature=20.0)
    return model


def _add_friction_copy(model: Model, prefix: str, y_offset: float, mu: float) -> None:
    """Add one independently supported copy of the qualified horizontal pipe."""
    tag = f"{prefix}_" if prefix else ""
    points = [[x,y+y_offset,z] for x,y,z in ([0,0,0], [2,0,0], [4,0,0], [4.3,0.3,0], [4.3,1.8,0], [4.3,3.3,0])]
    nodes = [model.add_node(point) for point in points]
    for i in (0,1,3,4):
        model.add_element(id=f"{tag}pipe_{i}", type="pipe_straight", n1=nodes[i], n2=nodes[i+1], section="pipe", material="steel")
    model.add_element(id=f"{tag}elbow", type="pipe_bend", n1=nodes[2], n2=nodes[3], section="pipe", material="steel",
                      bend_radius=0.3, bend_angle=90,
                      bend_geometry=BendGeometry(center=[4,0.3+y_offset,0], normal=[0,0,1], radius=0.3, angle=90,
                                                 start_tangent=[1,0,0], end_tangent=[0,1,0]))
    model.add_support(node=nodes[0], type="anchor", id=f"{tag}anchor")
    for name, node in [("S1",nodes[1]), ("S2",nodes[4])]:
        model.add_support(node=node, type="rest", id=f"{tag}{name}", direction=[0.0, 0.0, 1.0], friction_coefficient=mu,
                          normal_stiffness=1e10, tangential_stiffness=1e8)
    for name in ("Cold", "Hot", "Lift"):
        case = model.load_cases[name]
        case.add_nodal_force(nodes[1], force=[0.0,0.0,-10000.0])
        case.add_nodal_force(nodes[4], force=[0.0,0.0,600.0 if name == "Lift" else -10000.0])


def build_friction_model(mu: float = 0.3) -> Model:
    """Build the original one-copy benchmark used by qualification checks."""
    model = _new_friction_model(f"Native piping friction mu={mu:g}")
    _add_friction_copy(model, "", 0.0, mu)
    return model


def build_friction_comparison_model() -> Model:
    """Build one solve containing disconnected translated mu=0 and mu=0.3 copies."""
    model = _new_friction_model("Native piping friction comparison")
    _add_friction_copy(model, "NF", 0.0, 0.0)
    _add_friction_copy(model, "F", 5.0, 0.3)
    return model


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


def build_friction_review(output: Path, *, artifact_dir: Path | None = None, force: bool = False) -> dict:
    """Build the single-run friction comparison shared by the example and gallery."""
    model = build_friction_comparison_model()
    run = (import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir))
           if artifact_dir is not None else model.solve(pipe_modelization="POU_D_T", load_path=LOAD_PATH,
                                                       load_step=0.1, force=force, work_dir=str(output / "solver")))
    run.validate_for_publication(model)
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
    bundle_root = output
    run = stage_code_aster_artifact_evidence(run, bundle_root)
    states = run.result_states or (run.result_state,)
    geometry_states = [replace(create_visual_deformed_geometry_state(model=model, result_state=state, visual_scale=20.0),
                               id=f"geometry_state:{state.id}:visual") for state in states]
    solved_at = run.result_state.metadata["solve_attestation"]["solved_at"]
    scene = build_visualization_scene(model, analysis_runs=[run], geometry_states=geometry_states,
                                      scene_id="scene:native-friction:comparison", created_at=solved_at)
    add_scene_label(scene, "Without friction · μ = 0", [2.0, 0.0, 0.5], label_id="frictionless-copy")
    add_scene_label(scene, "With friction · μ = 0.3", [2.0, 5.0, 0.5], label_id="friction-copy")
    review = build_engineering_review(model, analysis_runs=[run], package_id="review:native-friction:comparison", created_at=solved_at)
    write_engineering_review_with_scene(review, bundle_root, scene=scene, title=model.project_name, source=__file__)
    _write_contact_exports(run, bundle_root)
    endpoints = [{"pseudo_time": state.metadata["pseudo_time"], "stage": state.metadata["stage_label"],
                  "contact": {key: value.to_dict() for key, value in state.contact_results.items()}}
                 for state in states if math.isclose(state.metadata["pseudo_time"], round(state.metadata["pseudo_time"]), abs_tol=1e-8)]
    return {"run": "comparison", "study_id": run.study.id, "states": len(states),
                      "scene": str(bundle_root / "scene.json"), "endpoints": endpoints}


def run_example(output_dir: str | Path = ".build/native-friction-review", *, artifact_dir: str | Path | None = None, force: bool = False) -> dict:
    """Solve or import one attested comparison model and write one review bundle."""
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary = build_friction_review(output, artifact_dir=Path(artifact_dir) if artifact_dir is not None else None, force=force)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shutil.copytree(Path(viewer_assets_path()), output / "viewer", dirs_exist_ok=True)
    links = '<li><a href="viewer/index.html?bundle=..">Open comparison</a> — <a href="contacts.csv">SI contact CSV</a> — <a href="contact-history.svg">history SVG</a></li>'
    (output / "index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Native piping friction</title><body><h1>Native piping friction</h1><p>One verified Code_Aster run containing two disconnected, translated copies with identical loading. No piping-code compliance verdict.</p><ul>'+links+'</ul></body></html>', encoding="utf-8")
    return {"output_dir": str(output), "run": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=".build/native-friction-review")
    parser.add_argument("--artifact-dir", help="Directory containing the combined attested solver output")
    parser.add_argument("--force", action="store_true", help="Run Code_Aster again even if matching evidence exists")
    args = parser.parse_args()
    print(json.dumps(run_example(args.output_dir, artifact_dir=args.artifact_dir, force=args.force), indent=2))
