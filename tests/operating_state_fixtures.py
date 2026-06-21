from __future__ import annotations

"""Fixture builders for the Code_Aster operating-state clash roadmap.

These fixtures intentionally use mock ``FEAResults`` objects instead of a
Code_Aster runtime. Current limitations captured for CA00:

- deformed clash is still exercised through the legacy endpoint-displacement
  collision path.
- generated bend mesh nodes are not represented yet.
- rack members are native model elements, but operating-state rack deformation
  is not solved in these fixtures.
"""

from dataclasses import dataclass

import numpy as np

from tuba import Model, RackBay
from tuba.patches import ModelTransaction
from tuba.solver.base import ElementResult, FEAResults, NodeResult


@dataclass(frozen=True)
class OperatingStateFixture:
    model: Model
    results: FEAResults
    primary_element_id: str
    support_id: str | None = None
    support_node_id: str | None = None
    rack_group_id: str | None = None


def straight_pipe_hot_clash_fixture() -> OperatingStateFixture:
    model = _base_pipe_model("CA00Straight")
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([2.0, 0.0, 0.0])
    elem = model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
    )
    model.add_obstacle(
        id="hot_clash_box",
        type="cuboid",
        min_point=[0.5, 0.08, -0.10],
        max_point=[1.5, 0.18, 0.10],
    )
    results = mock_hot_results(model, displacements={n0: (0.0, 0.06, 0.0), n1: (0.0, 0.06, 0.0)})
    results.element_results[elem.id] = _empty_element_result(elem.id)
    return OperatingStateFixture(model=model, results=results, primary_element_id=elem.id)


def bend_near_obstacle_fixture() -> OperatingStateFixture:
    model = _base_pipe_model("CA00Bend")
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 1.0, 0.0])
    elem = model.add_element(
        id="pipe_bend_0",
        type="pipe_bend",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
        bend_radius=1.0,
        bend_angle=90.0,
    )
    model.add_obstacle(
        id="bend_clearance_box",
        type="cuboid",
        min_point=[0.35, 1.20, -0.10],
        max_point=[0.85, 1.35, 0.10],
    )
    results = mock_hot_results(model, displacements={n0: (0.0, 0.0, 0.0), n1: (0.0, 0.02, 0.0)})
    results.element_results[elem.id] = _empty_element_result(elem.id)
    return OperatingStateFixture(model=model, results=results, primary_element_id=elem.id)


def insulated_pipe_near_rack_fixture() -> OperatingStateFixture:
    model = _base_pipe_model("CA00InsulatedRack")
    model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    n0 = model.add_node([0.0, 0.25, 1.5])
    n1 = model.add_node([2.0, 0.25, 1.5])
    elem = model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
    )
    model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
    model.assign_insulation(f"element:{elem.id}", "mw_50")
    rack = RackBay(
        name="rack_A",
        origin=(0.0, 0.0, 0.0),
        length=2.0,
        width=1.0,
        height=2.0,
        levels=(1.5,),
        section="RackSec",
        material="Steel",
    )
    ModelTransaction(model).apply(rack.to_patch())
    results = mock_hot_results(model, displacements={n0: (0.0, 0.0, 0.0), n1: (0.01, 0.0, 0.0)})
    results.element_results[elem.id] = _empty_element_result(elem.id)
    return OperatingStateFixture(model=model, results=results, primary_element_id=elem.id, rack_group_id="rack_A")


def pipe_supported_by_rack_fixture() -> OperatingStateFixture:
    model = _base_pipe_model("CA00SupportedRack")
    model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    rack = RackBay(
        name="rack_A",
        origin=(0.0, 0.0, 0.0),
        length=4.0,
        width=1.0,
        height=3.0,
        levels=(1.5, 3.0),
        section="RackSec",
        material="Steel",
    )
    ModelTransaction(model).apply(rack.to_patch())
    support_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
    pipe_end = model.add_node([2.0, 0.0, 1.5])
    elem = model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=support_node,
        n2=pipe_end,
        section="PipeSec",
        material="Steel",
    )
    support = model.add_support(node=support_node, type="rest")
    results = mock_hot_results(
        model,
        displacements={support_node: (0.0, 0.0, 0.0), pipe_end: (0.005, 0.0, 0.0)},
        reactions={support_node: (100.0, 0.0, -1000.0, 0.0, 0.0, 0.0)},
    )
    results.element_results[elem.id] = _empty_element_result(elem.id)
    return OperatingStateFixture(
        model=model,
        results=results,
        primary_element_id=elem.id,
        support_id=support.id,
        support_node_id=support_node,
        rack_group_id="rack_A",
    )


def mock_hot_results(
    model: Model,
    *,
    displacements: dict[str, tuple[float, float, float]],
    reactions: dict[str, tuple[float, float, float, float, float, float]] | None = None,
) -> FEAResults:
    results = FEAResults(solver_name="mock", load_case="Hot")
    results._model = model
    reactions = reactions or {}
    for node_id in model.nodes:
        displacement = np.zeros(6)
        if node_id in displacements:
            displacement[:3] = np.asarray(displacements[node_id], dtype=float)
        reaction_force = None
        if node_id in reactions:
            reaction_force = np.asarray(reactions[node_id], dtype=float)
        results.node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=displacement,
            reaction_force=reaction_force,
        )
    return results


def _base_pipe_model(project_name: str) -> Model:
    model = Model(project_name=project_name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5, allowable_stress={20.0: 137e6})
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model


def _empty_element_result(element_id: str) -> ElementResult:
    return ElementResult(
        element_id=element_id,
        forces_n1=np.zeros(6),
        forces_n2=np.zeros(6),
        von_mises_n1=0.0,
        von_mises_n2=0.0,
        max_von_mises=0.0,
    )
