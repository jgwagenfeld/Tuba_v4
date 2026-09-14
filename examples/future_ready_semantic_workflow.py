"""Future-ready semantic workflow demo.

Execute from the repository root:

    python examples/future_ready_semantic_workflow.py

The example keeps geometry mutation patch-first, assigns insulation as semantic
data, builds a rack bay, produces quantities/BOM, evaluates route cost, analyzes
support-to-rack load paths, runs rules, and writes a benchmark summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tuba import Model
from tuba.assemblies import RackBay
from tuba.benchmarks import write_model_benchmark_summary
from tuba.external.bom import bom_to_csv, bom_to_dict
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.quantities import quantity_takeoff
from tuba.routing.cost_model import RouteCostModel
from tuba.routing.plan import RoutePlan
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    RouteEndpoint,
    RouteSegment,
    RoutingCostWeights,
)
from tuba.rules import ClashFreeRule, RuleEngine, SupportSpacingRule


def run_demo(output_dir: str | Path = ".build/generated/future_ready_semantic_workflow") -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    model = Model(project_name="FutureReadySemanticWorkflow")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    model.add_insulation_spec(
        "mw_50",
        material="mineral_wool",
        thickness_m=0.05,
        density_kg_m3=100.0,
        cost_per_m=20.0,
    )

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
        section="DN100",
        material="Steel",
        costs=RoutingCostWeights(length=1.0, bend=0.0, support_span=0.0),
    )
    candidate = PipeRouteCandidate(
        request_id=request.id,
        points=[request.start.point, request.goal.point],
        segments=[RouteSegment(request.start.point, request.goal.point, "straight")],
        cost=0.0,
        cost_breakdown={},
    )
    plan = RoutePlan.from_candidate(candidate, request)
    patch_result = ModelTransaction(model).apply(plan.to_patch(model))
    created_elements = list(patch_result.element_ids.values())

    model.groups["line_A"] = {"name": "line_A", "elements": created_elements}
    model.assign_insulation("group:line_A", "mw_50")
    model.assign_insulation("route:P-100", "mw_50")

    support_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
    support = model.add_support(node=support_node, type="rest")

    takeoff = quantity_takeoff(model)
    bom = bom_to_dict(model)
    (output / "bom.csv").write_text(bom_to_csv(model), encoding="utf-8")
    benchmark_path = write_model_benchmark_summary(model, directory=output)
    route_cost = RouteCostModel.from_routing_weights(request.costs).evaluate_candidate(model, request, candidate)
    load_paths = analyze_load_paths(model, support_reactions={support.id: (0.0, 0.0, -500.0)})
    rules = RuleEngine([SupportSpacingRule(max_span_m=5.0), ClashFreeRule()]).evaluate(model)

    summary = {
        "created_elements": created_elements,
        "line_length_m": takeoff.groups["line_A"]["length_m"],
        "bom_rows": len(bom["rows"]),
        "route_cost_total": route_cost.total,
        "rack_force_z_n": load_paths.rack_loads["rack_A"]["force_z_n"],
        "rules_passed": rules.passed,
        "benchmark_path": benchmark_path,
        "bom_csv_path": str(output / "bom.csv"),
    }
    return summary


def main() -> None:
    summary = run_demo()
    print(f"Created elements: {', '.join(summary['created_elements'])}")
    print(f"Line length: {summary['line_length_m']:.3f} m")
    print(f"Route cost: {summary['route_cost_total']:.3f}")
    print(f"Rules passed: {summary['rules_passed']}")
    print(f"BOM CSV: {summary['bom_csv_path']}")
    print(f"Benchmark: {summary['benchmark_path']}")


if __name__ == "__main__":
    main()
