import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from tuba import Model, RackBay
from tuba.benchmarks import write_model_benchmark_summary
from tuba.external.bom import bom_to_dict
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.quantities import quantity_takeoff
from tuba.routing.cost_model import RouteCostModel
from tuba.routing.plan import RoutePlan
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, RouteEndpoint, RouteSegment, RoutingCostWeights
from tuba.rules import ClashFreeRule, RuleEngine, SupportSpacingRule


class TestFutureReadyIntegration(unittest.TestCase):
    def test_semantic_route_rack_quantity_cost_rule_flow(self):
        model = Model(project_name="FutureReady")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)

        rack = RackBay(
            name="rack_A",
            origin=(0.0, -0.5, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )
        ModelTransaction(model).apply(rack.to_patch())

        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 1.5)),
            goal=RouteEndpoint(id="B", point=(4.0, 0.0, 1.5)),
            section="PipeSec",
            material="Steel",
            costs=RoutingCostWeights(length=1.0, bend=0.0, support_span=0.0),
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 1.5), (4.0, 0.0, 1.5)],
            segments=[RouteSegment((0.0, 0.0, 1.5), (4.0, 0.0, 1.5), "straight")],
            cost=0.0,
            cost_breakdown={},
        )
        plan = RoutePlan.from_candidate(candidate, request)
        result = ModelTransaction(model).apply(plan.to_patch(model))
        created_elements = list(result.element_ids.values())
        model.groups["line_A"] = {"name": "line_A", "elements": created_elements}
        model.assign_insulation("group:line_A", "mw_50")
        model.assign_insulation("route:P-100", "mw_50")

        support_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        support = model.add_support(node=support_node, type="rest")

        takeoff = quantity_takeoff(model)
        bom = bom_to_dict(model)
        pipe_row = next(row for row in bom["rows"] if row["element_id"] in created_elements)
        cost = RouteCostModel.from_routing_weights(request.costs).evaluate_candidate(model, request, candidate)
        load_paths = analyze_load_paths(model, support_reactions={support.id: (0.0, 0.0, -500.0)})
        rules = RuleEngine([SupportSpacingRule(max_span_m=5.0), ClashFreeRule()]).evaluate(model)

        self.assertAlmostEqual(takeoff.groups["line_A"]["length_m"], 4.0)
        self.assertEqual(pipe_row["insulation_spec"], "mw_50")
        self.assertGreater(cost.terms["insulation"].total, 0.0)
        self.assertEqual(load_paths.rack_loads["rack_A"]["force_z_n"], -500.0)
        self.assertTrue(rules.passed)

        with TemporaryDirectory() as tmpdir:
            path = write_model_benchmark_summary(model, directory=tmpdir)
            self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
