"""Hot-line autorouting workflow with expansion-loop candidate generation."""

from __future__ import annotations

from pathlib import Path

from tuba import Model
from tuba.routing import (
    AutoroutingAgent,
    AutoroutingRun,
    ExpansionAwareRouter,
    ExpansionLoopGenerator,
    ExpansionLoopSpec,
    GridRouter,
    SolverAcceptanceCriteria,
    ThermalRouteRequirement,
)
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def build_model() -> Model:
    model = Model("HotLineExpansionLoop")
    model.add_material(
        "steel",
        E=210e9,
        nu=0.3,
        rho=7850.0,
        alpha=12e-6,
        allowable_stress={20.0: 140e6, 180.0: 120e6},
    )
    model.add_pipe_section("DN80", OD=0.0889, WT=0.00549)
    model.define_load_case("Hot", gravity=True, pressure=1.2e6, temperature=180.0)
    model.add_obstacle(
        id="hot_equipment",
        type="cuboid",
        min_point=(3.4, -0.35, -0.35),
        max_point=(4.6, 0.35, 0.35),
    )
    return model


def build_request() -> PipeRouteRequest:
    return PipeRouteRequest(
        id="HOT-EXP-100",
        start=RouteEndpoint("PumpDischarge", (0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0)),
        goal=RouteEndpoint("RackTieIn", (8.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0)),
        section="DN80",
        material="steel",
        constraints=RoutingConstraints(
            clearance=0.10,
            insulation_thickness=0.05,
            min_bend_radius=0.25,
        ),
        thermal_requirements=ThermalRouteRequirement(
            design_temperature_c=180.0,
            reference_temperature_c=20.0,
            line_length_m=8.0,
            thermal_expansion_coefficient=12e-6,
            metadata={"service": "hot oil"},
        ),
        solver_acceptance=SolverAcceptanceCriteria.hot_line_defaults(),
    )


def run_example(output_root: str | Path = "routing_reports") -> AutoroutingRun:
    model = build_model()
    request = build_request()
    router = ExpansionAwareRouter(
        base_router=GridRouter(
            RoutingGridSpec(cell_size=0.5, margin=1.5),
            candidate_count=1,
        ),
        loop_generator=ExpansionLoopGenerator(
            loop_specs=(
                # This loop clears the equipment envelope while staying shallower
                # than the grid cell detour around it, so it wins on route cost.
                ExpansionLoopSpec(
                    family="u_loop",
                    width_m=2.0,
                    depth_m=0.8,
                    plane="xy",
                    min_clearance_m=0.15,
                ),
            ),
        ),
    )
    return AutoroutingAgent(
        router=router,
        solver_config=SolverLoopConfig(
            run_solver=False,
            export_study=True,
            max_solver_candidates=2,
            load_case="Hot",
        ),
        output_root=output_root,
    ).route_pipe(model, request, apply=True)


def main() -> None:
    run = run_example()
    selected = run.result.selected
    route_family = selected.metadata.get("route_family", "none") if selected is not None else "none"

    print(f"Selected route family: {route_family}")
    print(f"Created elements: {', '.join(run.created_element_ids)}")
    print(f"Report: {run.report_path}")


if __name__ == "__main__":
    main()
