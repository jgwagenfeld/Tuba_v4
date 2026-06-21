import tempfile
import unittest
from pathlib import Path

from tuba.routing.report import write_route_report
from tuba.routing.types import (
    NetworkRouteRequest,
    NetworkRouteResult,
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
)


class TestRoutingReport(unittest.TestCase):
    def test_writes_markdown_and_json_report(self):
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.1, insulation_thickness=0.05),
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[RouteSegment(start=(0.0, 0.0, 0.0), end=(2.0, 0.0, 0.0), kind="straight")],
            cost=2.0,
            cost_breakdown={"length": 2.0, "bends": 0, "support_span_max": 2.0},
            metadata={
                "solver": {"solver_ran": True, "solver_name": "FakeSolver", "study_dir": "studies/candidate_0"},
                "compliance": {"overall_pass": True, "worst_sustained_ratio": 0.4, "worst_expansion_ratio": 0.2},
            },
        )
        result = PipeRouteResult(request=request, candidates=[candidate], selected_index=0, diagnostics=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = write_route_report(result, tmpdir)
            self.assertTrue(report_path.exists())
            self.assertTrue((Path(tmpdir) / "route_result.json").exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("P-100", text)
            self.assertIn("Candidate Comparison", text)
            self.assertIn("Clearance", text)
            self.assertIn("Support Spans", text)
            self.assertIn("Solver / Compliance", text)
            self.assertIn("FakeSolver", text)
            self.assertNotIn("not checked in report writer", text)

    def test_network_report_lists_unresolved_conflicts(self):
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[RouteSegment(start=(0.0, 0.0, 0.0), end=(2.0, 0.0, 0.0), kind="straight")],
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )
        route = PipeRouteResult(request=request, candidates=[candidate], selected_index=0, diagnostics=[])
        result = NetworkRouteResult(
            request=NetworkRouteRequest(id="N1", pipe_requests=[request]),
            pipe_results={"P-100": route},
            accepted_candidates={"P-100": candidate},
            unresolved_conflicts=[
                {
                    "pipes": ("P-100", "P-200"),
                    "distance": 0.0,
                    "required_clearance": 0.2,
                    "segments": (0, 0),
                }
            ],
            diagnostics=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = write_route_report(result, tmpdir)
            text = report_path.read_text(encoding="utf-8")

        self.assertIn("Unresolved Conflicts", text)
        self.assertIn("P-100", text)
        self.assertIn("P-200", text)


if __name__ == "__main__":
    unittest.main()
