"""The small load-transfer lesson must use complete, correctly targeted solved loads."""

import json
from pathlib import Path

import numpy as np

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import load_project
from tuba.project.evidence import evidence_verdict
from tuba.project.freshness import expected_identity
from tuba.solver.aster_loads import resolve_line_load_groups


def test_consolidated_loads_balance_and_publish(tmp_path):
    project = load_project(Path(__file__).resolve().parents[1] / "examples/support-rack-review")
    namespace = project.run_model()
    model = namespace["model"]
    case = model.resolve_load_case("Operating")[1]
    assert not case.gravity
    assert all(support.friction_coefficient == 0 for support in model.supports)
    pipe_members, cross_members = resolve_line_load_groups(model, case)
    assert set(pipe_members[0]) == {e.id for e in model.elements if e.route_id == "P-100"}
    assert pipe_members[1:] == (0.0, 0.0, -350.0)
    assert cross_members == (namespace["loaded_crossbeam"], 500.0, 0.0, 0.0)
    crossbeam = [e for e in model.elements if e.id in cross_members[0]]
    assert len(crossbeam) == 2
    assert all(e.section == "RackCrossIPE" and namespace["mid_left"] in (e.n1, e.n2) for e in crossbeam)
    assert case.nodal_forces[0].node == namespace["loaded_pipe_node"]
    assert case.nodal_forces[0].components == [0, 0, -3500, 0, 500, 0]

    evidence = project.root / "evidence/Operating"
    assert evidence_verdict(evidence, expected_identity(model, "Operating")).reusable
    run = import_code_aster_artifacts(model=model, work_dir=evidence)
    run.validate_for_publication(model)
    ground_nodes = {support.node for support in model.supports if not support.attached_to}
    reactions = np.asarray([run.result_state.node_reactions[node] for node in ground_nodes])
    assert np.isfinite(reactions).all()
    # Independent statics: 2 m x 500 N/m sideways; 8 m x 350 N/m + 3500 N down.
    np.testing.assert_allclose(reactions[:, :3].sum(axis=0), [-1000, 0, 6300], atol=0.1)
    moment = np.sum([
        np.cross(model.nodes[node].coords, run.result_state.node_reactions[node][:3])
        + run.result_state.node_reactions[node][3:]
        for node in ground_nodes
    ], axis=0)
    # Moments about the origin: 2800 N at x=2, 3500 N at x=2, 500 N m,
    # plus 1000 N sideways at z=3. The free shoes transfer no offset couple.
    np.testing.assert_allclose(moment, [0, -16100, 0], atol=0.1)

    root = project.load_study().build_review(namespace, tmp_path, artifact_dir=evidence)
    scene = json.loads((root / "scene.json").read_text(encoding="utf-8"))
    loads = next(overlay for overlay in scene["overlays"] if overlay["kind"] == "load_case")
    assert loads["data"]["line_load_count"] == 2
    assert loads["data"]["nodal_force_count"] == 1
    assert any(object_id.endswith(":moment") for object_id in loads["object_ids"])
    assert loads["data"]["fields"][1]["affected_element_ids"] == namespace["loaded_crossbeam"]
    spacing, = [overlay for overlay in scene["overlays"] if overlay["kind"] == "rule_violation"]
    assert spacing["data"]["rule_data"] == {"span_m": 4.0, "max_span_m": 3.5}
