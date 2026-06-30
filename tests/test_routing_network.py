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

    def test_detects_route_intrusion_into_reserved_envelope(self):
        loop = PipeRouteCandidate(
            request_id="P-LOOP",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={},
            metadata={
                "reserved_envelope": {
                    "min_point": (1.0, 1.0, -1.0),
                    "max_point": (3.0, 3.0, 1.0),
                }
            },
        )
        route = PipeRouteCandidate(
            request_id="P-200",
            points=[(2.0, 0.5, 0.0), (2.0, 3.5, 0.0)],
            segments=[RouteSegment((2.0, 0.5, 0.0), (2.0, 3.5, 0.0), "straight")],
            cost=3.0,
            cost_breakdown={},
        )

        conflicts = detect_candidate_conflicts({"P-LOOP": loop, "P-200": route}, clearance=0.1)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "reserved_envelope")
        self.assertEqual(conflicts[0]["pipes"], ("P-LOOP", "P-200"))
        self.assertEqual(conflicts[0]["reserved_envelope_owner"], "P-LOOP")
        self.assertEqual(conflicts[0]["route_id"], "P-200")
        self.assertEqual(conflicts[0]["route_segment"], 0)

    def test_reserved_envelope_tangent_route_is_not_conflict(self):
        loop = PipeRouteCandidate(
            request_id="P-LOOP",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={},
            metadata={
                "reserved_envelope": {
                    "min_point": (1.0, 1.0, -1.0),
                    "max_point": (3.0, 3.0, 1.0),
                }
            },
        )
        tangent = PipeRouteCandidate(
            request_id="P-200",
            points=[(0.0, 3.0, 0.0), (4.0, 3.0, 0.0)],
            segments=[RouteSegment((0.0, 3.0, 0.0), (4.0, 3.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={},
        )

        conflicts = detect_candidate_conflicts({"P-LOOP": loop, "P-200": tangent}, clearance=0.1)

        self.assertEqual(conflicts, [])

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

    def test_network_reports_reserved_envelope_conflict_for_later_route(self):
        model = Model(project_name="NetworkReservedEnvelope")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        loop = PipeRouteRequest(
            id="P-LOOP",
            start=RouteEndpoint(id="A1", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B1", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        route = PipeRouteRequest(
            id="P-200",
            start=RouteEndpoint(id="A2", point=(2.0, 0.5, 0.0)),
            goal=RouteEndpoint(id="B2", point=(2.0, 3.5, 0.0)),
            section="PipeSec",
            material="Steel",
        )

        result = NetworkRouter(single_router=_ReservedEnvelopeRouter()).route_network(
            model,
            NetworkRouteRequest(id="N-envelope", pipe_requests=[loop, route], max_reroute_attempts=0),
        )

        self.assertEqual(len(result.unresolved_conflicts), 1)
        self.assertEqual(result.unresolved_conflicts[0]["type"], "reserved_envelope")
        self.assertEqual(result.unresolved_conflicts[0]["pipes"], ("P-LOOP", "P-200"))
        self.assertIn("reserved envelope", " ".join(result.diagnostics))

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


class _ReservedEnvelopeRouter:
    def route(self, model, request):
        if request.id == "P-LOOP":
            points = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
            metadata = {
                "reserved_envelope": {
                    "min_point": (1.0, 1.0, -1.0),
                    "max_point": (3.0, 3.0, 1.0),
                }
            }
        else:
            points = [(2.0, 0.5, 0.0), (2.0, 3.5, 0.0)]
            metadata = {}
        candidate = PipeRouteCandidate(
            request_id=request.id,
            points=points,
            segments=[RouteSegment(points[0], points[1], "straight")],
            cost=4.0,
            cost_breakdown={"length": 4.0},
            metadata=metadata,
        )
        return PipeRouteResult(
            request=request,
            candidates=[candidate],
            selected_index=0,
            diagnostics=[],
        )
