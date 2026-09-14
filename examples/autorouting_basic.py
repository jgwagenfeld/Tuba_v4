"""Run a basic pipe autorouting example and write review files.

Execute from the repository root:

    python examples/autorouting_basic.py
"""

from __future__ import annotations

from pathlib import Path

from tuba import Model
from tuba.routing import GridRouter
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.report import write_route_report
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def main() -> None:
    model = Model("AutoroutingBasic")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850, alpha=12e-6)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.add_obstacle(
        id="equipment_box",
        type="cuboid",
        min_point=[1.5, -0.4, -0.4],
        max_point=[2.5, 0.4, 0.4],
    )

    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
        goal=RouteEndpoint("B", (4.0, 0.0, 0.0)),
        section="DN100",
        material="steel",
        constraints=RoutingConstraints(clearance=0.10, min_bend_radius=0.20),
    )

    result = GridRouter(
        grid_spec=RoutingGridSpec(cell_size=0.25, margin=1.0),
        candidate_count=3,
    ).route(model, request)
    if result.selected is None:
        raise RuntimeError("; ".join(result.diagnostics) or "No route found.")

    created = apply_candidate_to_model(model, result.selected, request)
    report_path = write_route_report(
        result,
        Path(".build") / "generated" / "autorouting_basic",
        model=model,
    )
    print(f"Selected route has {len(result.selected.points)} points.")
    print(f"Created elements: {', '.join(created)}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
