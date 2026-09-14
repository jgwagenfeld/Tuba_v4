"""Multi-pipe autorouting workflow with network conflict reporting."""

from __future__ import annotations

from tuba import Model
from tuba.routing import NetworkRouter
from tuba.routing.report import write_route_report
from tuba.routing.types import (
    NetworkRouteRequest,
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def main() -> None:
    model = Model("AutorouteNetwork")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850, alpha=12e-6)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    common_constraints = RoutingConstraints(clearance=0.05, min_bend_radius=0.20)
    p100 = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint("P100-A", (0.0, 0.0, 0.0)),
        goal=RouteEndpoint("P100-B", (5.0, 0.0, 0.0)),
        section="DN100",
        material="steel",
        constraints=common_constraints,
    )
    p200 = PipeRouteRequest(
        id="P-200",
        start=RouteEndpoint("P200-A", (0.0, 0.0, 0.0)),
        goal=RouteEndpoint("P200-B", (5.0, 0.0, 0.0)),
        section="DN100",
        material="steel",
        constraints=common_constraints,
    )
    result = NetworkRouter(grid_spec=RoutingGridSpec(cell_size=0.5, margin=2.0)).route_network(
        model,
        NetworkRouteRequest(id="network-demo", pipe_requests=[p100, p200], order_strategy="given"),
    )
    report = write_route_report(result, "routing_reports/network-demo", model=model)
    print(f"Accepted routes: {', '.join(result.accepted_candidates)}")
    print(f"Unresolved conflicts: {len(result.unresolved_conflicts)}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
