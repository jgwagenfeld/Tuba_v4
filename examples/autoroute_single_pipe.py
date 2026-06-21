"""Single-pipe autorouting workflow with study export and report output."""

from __future__ import annotations

from tuba import Model
from tuba.routing import AutoroutingAgent, GridRouter
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def build_model() -> Model:
    model = Model("AutorouteSinglePipe")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850, alpha=12e-6, allowable_stress={20.0: 140e6})
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0)
    model.add_obstacle(
        id="equipment_box",
        type="cuboid",
        min_point=[1.5, -0.4, -0.4],
        max_point=[2.5, 0.4, 0.4],
    )
    return model


def main() -> None:
    model = build_model()
    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint("A", (0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0)),
        goal=RouteEndpoint("B", (4.0, 0.0, 0.0), direction=(0.0, -1.0, 0.0)),
        section="DN100",
        material="steel",
        constraints=RoutingConstraints(clearance=0.10, min_bend_radius=0.20),
    )
    run = AutoroutingAgent(
        router=GridRouter(RoutingGridSpec(cell_size=0.25, margin=1.0), candidate_count=3),
        solver_config=SolverLoopConfig(run_solver=False, export_study=True, max_solver_candidates=2, load_case="Hot"),
        output_root="routing_reports",
    ).route_pipe(model, request, apply=True)

    print(f"Selected route cost: {run.result.selected.cost:.3f}")
    print(f"Created elements: {', '.join(run.created_element_ids)}")
    print(f"Report: {run.report_path}")


if __name__ == "__main__":
    main()
