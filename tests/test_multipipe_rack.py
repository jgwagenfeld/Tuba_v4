"""The multipipe gallery must carry three lines on one connected steel frame."""

from pathlib import Path

import numpy as np

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.clash import ClashEngine
from tuba.project import load_project


def test_three_lines_share_split_crossbeams_and_independent_operations():
    ns = load_project(Path(__file__).resolve().parents[1] / "examples/multipipe-rack").run_model()
    model = ns["model"]
    assert set(ns["station_nodes"]) == {"P-100", "P-200", "P-300"}
    assert len(model.groups) == 4
    assert sum(s.type == "anchor" and not s.attached_to for s in model.supports) == 10
    assert sum(s.type == "anchor" and bool(s.attached_to) for s in model.supports) == 3
    assert sum(s.type == "rest" and bool(s.attached_to) for s in model.supports) == 12
    for support in (s for s in model.supports if s.attached_to):
        pipe, frame = model.nodes[support.node].coords, model.nodes[support.attached_to].coords
        assert np.allclose(pipe[:2], frame[:2])
        cross_members = [e for e in model.elements if e.section == "RackCross"
                         and support.attached_to in (e.n1, e.n2)]
        assert len(cross_members) == 2  # connected crossbeam, not a floating support node
    operation = model.operations["Operating"]
    assert [(f.route_id, f.value) for f in operation.fields if f.quantity == "temperature"] == [
        ("P-100", 100.0), ("P-200", 200.0), ("P-300", 300.0)]
    assert [(f.route_id, f.value) for f in operation.fields if f.quantity == "pressure"] == [
        ("P-100", 1e6), ("P-200", 2e6), ("P-300", 3e6)]
    assert not ClashEngine().check_all(model)


def test_solved_rack_carries_the_total_weight_and_hotter_lines_expand_more():
    project = load_project(Path(__file__).resolve().parents[1] / "examples/multipipe-rack")
    ns = project.run_model()
    model = ns["model"]
    state = import_code_aster_artifacts(
        model=model, work_dir=project.root / "evidence/Operating",
    ).result_state
    feet = [s.node for s in model.supports if s.type == "anchor" and not s.attached_to]
    reaction = np.sum([state.node_reactions[node][:3] for node in feet], axis=0)
    weight = 0.0
    for element in model.elements:
        section = model.sections[element.section]
        area = section.properties["A"] if element.type == "beam" else section.area
        length = np.linalg.norm(model.nodes[element.n2].coords - model.nodes[element.n1].coords)
        weight += length * area * model.materials[element.material].rho * 9.81
    assert np.isclose(reaction[2], weight, rtol=1e-5)
    assert np.allclose(reaction[:2], 0.0, atol=0.1)
    assert len(state.contact_results) == 12
    assert all(c.status == "sliding" and c.status_source == "solver"
               for c in state.contact_results.values())
    expansion = []
    for nodes in ns["station_nodes"].values():
        left, right = (state.node_displacements[node][0] for node in (nodes[0], nodes[-1]))
        assert left < 0 < right
        assert np.isclose(-left, right, atol=1e-6)
        expansion.append(right)
    assert expansion[0] < expansion[1] < expansion[2]
