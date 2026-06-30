import unittest

from tuba import Model
from tuba.routing.astar import GridRouter
from tuba.routing.expansion import ExpansionLoopGenerator
from tuba.routing.hybrid import ExpansionAwareRouter
from tuba.routing.thermal import ExpansionLoopSpec, ThermalRouteRequirement
from tuba.routing.types import PipeRouteRequest, PipeRouteResult, RouteEndpoint, RoutingConstraints, RoutingGridSpec


def _model():
    model = Model("Expansion")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    return model


class TestRoutingExpansion(unittest.TestCase):
    def test_u_loop_candidate_has_reserved_envelope_metadata(self):
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        model = _model()
        spec = ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0, plane="xy")
        candidates = ExpansionLoopGenerator(loop_specs=(spec,)).generate(model, request)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertTrue(candidate.is_valid)
        self.assertEqual(candidate.diagnostics, [])
        self.assertEqual(candidate.metadata["route_family"], "u_loop")
        self.assertEqual(candidate.metadata["expansion_loop"], {"width_m": 2.0, "depth_m": 1.0, "plane": "xy"})
        self.assertIn("reserved_envelope", candidate.metadata)
        self.assertGreater(len(candidate.points), 4)

        xs = [point[0] for point in candidate.points]
        ys = [point[1] for point in candidate.points]
        zs = [point[2] for point in candidate.points]
        envelope_radius = (
            model.sections[request.section].OD / 2.0
            + request.constraints.insulation_thickness
            + request.constraints.clearance
            + spec.min_clearance_m
        )
        self.assertEqual(
            candidate.metadata["reserved_envelope"]["min_point"],
            (min(xs) - envelope_radius, min(ys) - envelope_radius, min(zs) - envelope_radius),
        )
        self.assertEqual(
            candidate.metadata["reserved_envelope"]["max_point"],
            (max(xs) + envelope_radius, max(ys) + envelope_radius, max(zs) + envelope_radius),
        )

    def test_effective_bend_radius_rejects_tight_loop_when_request_has_no_radius(self):
        request = PipeRouteRequest(
            id="HOT-102",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (1.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        candidate = ExpansionLoopGenerator(
            loop_specs=(ExpansionLoopSpec("u_loop", width_m=0.2, depth_m=0.1, plane="xy"),)
        ).generate(_model(), request)[0]

        fallback_radius = _model().sections[request.section].OD * 1.5
        bend_radii = [segment.bend_radius for segment in candidate.segments if segment.kind == "bend"]
        self.assertFalse(candidate.is_valid)
        self.assertTrue(candidate.diagnostics)
        self.assertTrue(all(radius == fallback_radius for radius in bend_radii))

    def test_plane_direction_mismatch_returns_invalid_candidate(self):
        request = PipeRouteRequest(
            id="HOT-103",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (0.0, 0.0, 10.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        candidate = ExpansionLoopGenerator(
            loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0, plane="xy"),)
        ).generate(_model(), request)[0]

        self.assertFalse(candidate.is_valid)
        self.assertTrue(any("plane/direction mismatch" in diagnostic for diagnostic in candidate.diagnostics))

    def test_returns_no_candidates_without_thermal_requirements(self):
        request = PipeRouteRequest(
            id="COLD-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1),
        )

        candidates = ExpansionLoopGenerator(
            loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0),)
        ).generate(_model(), request)

        self.assertEqual(candidates, [])

    def test_identical_endpoints_are_rejected(self):
        request = PipeRouteRequest(
            id="HOT-101",
            start=RouteEndpoint("A", (1.0, 1.0, 1.0)),
            goal=RouteEndpoint("B", (1.0, 1.0, 1.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        with self.assertRaisesRegex(ValueError, "Expansion loop endpoints must be distinct."):
            ExpansionLoopGenerator(
                loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0),)
            ).generate(_model(), request)


class TestExpansionAwareRouter(unittest.TestCase):
    def test_hybrid_router_returns_grid_and_loop_candidates(self):
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        result = ExpansionAwareRouter(
            base_router=GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0), candidate_count=1),
            loop_generator=ExpansionLoopGenerator(
                loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0),)
            ),
        ).route(_model(), request)

        families = {candidate.metadata.get("route_family") for candidate in result.candidates}
        self.assertIn("grid", families)
        self.assertIn("u_loop", families)
        self.assertTrue(
            all(
                candidate.cost > 0.0 and candidate.cost_breakdown
                for candidate in result.candidates
                if candidate.metadata.get("route_family") == "u_loop"
            )
        )
        self.assertIsNotNone(result.selected_index)
        self.assertGreaterEqual(result.selected_index, 0)
        self.assertLess(result.selected_index, len(result.candidates))

    def test_grid_failure_diagnostic_is_scoped_when_loop_fallback_succeeds(self):
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        class FailingGridRouter:
            def route(self, model, request):
                return PipeRouteResult(
                    request=request,
                    candidates=[],
                    selected_index=None,
                    diagnostics=["No route found for request HOT-100"],
                )

        result = ExpansionAwareRouter(
            base_router=FailingGridRouter(),
            loop_generator=ExpansionLoopGenerator(
                loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0),)
            ),
        ).route(_model(), request)

        self.assertIsNotNone(result.selected)
        self.assertTrue(result.selected.is_valid)
        self.assertEqual(result.selected.metadata.get("route_family"), "u_loop")
        self.assertNotIn("No route found for request HOT-100", result.diagnostics)
        self.assertIn("Grid router: No route found for request HOT-100", result.diagnostics)


if __name__ == "__main__":
    unittest.main()
