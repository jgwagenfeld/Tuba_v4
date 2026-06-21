import unittest

from tuba import Model
from tuba.routing.network import NetworkRouter, detect_candidate_conflicts
from tuba.routing.types import (
    NetworkRouteRequest,
    NetworkRouteResult,
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
    RoutingGridSpec,
)


class TestNetworkRouter(unittest.TestCase):
    def test_prioritized_two_pipe_route_avoids_first_pipe(self):
        model = Model(project_name="Network")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.2, WT=0.01)

        p1 = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A1", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B1", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.0),
        )
        p2 = PipeRouteRequest(
            id="P-200",
            start=RouteEndpoint(id="A2", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B2", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.0),
        )

        result = NetworkRouter(grid_spec=RoutingGridSpec(cell_size=1.0, margin=2.0)).route_network(
            model,
            NetworkRouteRequest(id="N1", pipe_requests=[p1, p2]),
        )

        self.assertIn("P-100", result.accepted_candidates)
        self.assertIn("P-200", result.accepted_candidates)
        self.assertNotEqual(
            result.accepted_candidates["P-100"].points,
            result.accepted_candidates["P-200"].points,
        )

    def test_detects_candidate_conflict(self):
        p1 = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={},
        )
        p2 = PipeRouteCandidate(
            request_id="P-200",
            points=[(2.0, -2.0, 0.0), (2.0, 2.0, 0.0)],
            segments=[RouteSegment((2.0, -2.0, 0.0), (2.0, 2.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={},
        )

        conflicts = detect_candidate_conflicts({"P-100": p1, "P-200": p2}, clearance=0.1)

        self.assertEqual(conflicts[0]["pipes"], ("P-100", "P-200"))
        self.assertLess(conflicts[0]["distance"], 0.1)

    def test_network_reports_unresolved_conflicts_when_avoidance_disabled(self):
        model = Model(project_name="NetworkConflicts")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.2, WT=0.01)
        p1 = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A1", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B1", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.0, avoid_existing_pipes=False),
        )
        p2 = PipeRouteRequest(
            id="P-200",
            start=RouteEndpoint(id="A2", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B2", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.0, avoid_existing_pipes=False),
        )

        result = NetworkRouter(grid_spec=RoutingGridSpec(cell_size=1.0, margin=1.0)).route_network(
            model,
            NetworkRouteRequest(id="N-conflict", pipe_requests=[p1, p2]),
        )

        self.assertTrue(result.unresolved_conflicts)
        self.assertIn("unresolved route conflict", " ".join(result.diagnostics))

    def test_network_uses_reroute_attempts_to_repair_conflicts(self):
        model = Model(project_name="NetworkRepair")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        p1 = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A1", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B1", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        p2 = PipeRouteRequest(
            id="P-200",
            start=RouteEndpoint(id="A2", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B2", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )

        result = NetworkRouter(single_router=_RepairingRouter()).route_network(
            model,
            NetworkRouteRequest(id="N-repair", pipe_requests=[p1, p2], max_reroute_attempts=1),
        )

        self.assertEqual(result.unresolved_conflicts, [])
        self.assertEqual(result.accepted_candidates["P-200"].points[1], (4.0, 1.0, 0.0))
        self.assertIn("rerouted P-200", " ".join(result.diagnostics))


if __name__ == "__main__":
    unittest.main()


class _RepairingRouter:
    def __init__(self):
        self.calls = {}

    def route(self, model, request):
        count = self.calls.get(request.id, 0)
        self.calls[request.id] = count + 1
        if request.id == "P-200" and count > 0:
            points = [(0.0, 1.0, 0.0), (4.0, 1.0, 0.0)]
        else:
            points = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
        candidate = PipeRouteCandidate(
            request_id=request.id,
            points=points,
            segments=[RouteSegment(points[0], points[1], "straight")],
            cost=4.0,
            cost_breakdown={"length": 4.0},
        )
        return PipeRouteResult(
            request=request,
            candidates=[candidate],
            selected_index=0,
            diagnostics=[],
        )
