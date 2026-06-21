import tempfile
import unittest
from pathlib import Path

import numpy as np

from tuba import Model
from tuba.routing.solver_loop import SolverLoopConfig, SolverLoopScorer
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
    RoutingCostWeights,
)
from tuba.routing.cost import score_candidate
from tuba.solver.base import ElementResult, FEAResults, NodeResult


class FailingSolver:
    def __init__(self, work_dir):
        self.work_dir = work_dir

    def export_study(self, model, load_case, output_dir):
        raise FileNotFoundError("as_run not available")


class PassingSolver:
    def __init__(self, work_dir):
        self.work_dir = work_dir

    def export_study(self, model, load_case, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def solve(self, model, load_case):
        results = FEAResults(solver_name="FakeSolver", load_case=load_case)
        for node_id in model.nodes:
            results.node_results[node_id] = NodeResult(
                node_id=node_id,
                displacement=np.zeros(6),
                reaction_force=np.ones(6),
            )
        for elem in model.elements:
            results.element_results[elem.id] = ElementResult(
                element_id=elem.id,
                forces_n1=np.array([0.0, 0.0, 0.0, 0.0, 10.0, 0.0]),
                forces_n2=np.array([0.0, 0.0, 0.0, 0.0, 10.0, 0.0]),
                max_von_mises=1.0,
            )
        return results


class TestSolverLoop(unittest.TestCase):
    def test_exports_candidate_studies_without_running_solver(self):
        model = Model(project_name="SolverLoop")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, allowable_stress={20.0: 120e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=100.0)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(),
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[RouteSegment(start=(0.0, 0.0, 0.0), end=(2.0, 0.0, 0.0), kind="straight")],
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer().score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=False,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Hot",
                ),
            )
            study_dir = Path(ranked[0].metadata["solver"]["study_dir"])
            self.assertTrue((study_dir / "study.comm").exists())
            self.assertFalse(ranked[0].metadata["solver"]["solver_ran"])

    def test_solver_failure_is_nonfatal(self):
        model, request, candidate = _solver_loop_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer(solver_factory=FailingSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(run_solver=True, export_study=True, max_solver_candidates=1, work_root=tmpdir),
            )

        self.assertFalse(ranked[0].metadata["solver"]["solver_ran"])
        self.assertIn("Solver loop failed", " ".join(ranked[0].diagnostics))

    def test_compliance_metadata_added_when_results_available(self):
        model, request, candidate = _solver_loop_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer(solver_factory=PassingSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=True,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Hot",
                ),
            )

        self.assertTrue(ranked[0].metadata["solver"]["solver_ran"])
        self.assertEqual(ranked[0].metadata["solver"]["solver_name"], "FakeSolver")
        self.assertIn("compliance", ranked[0].metadata)
        self.assertTrue(ranked[0].metadata["compliance"]["overall_pass"])
        self.assertIn("worst_sustained_ratio", ranked[0].metadata["compliance"])
        self.assertIn("reactions", ranked[0].metadata)
        self.assertIn("displacements", ranked[0].metadata)

    def test_cheap_score_penalizes_long_unsupported_spans(self):
        model, request, _candidate = _solver_loop_fixture()
        request = PipeRouteRequest(
            id=request.id,
            start=request.start,
            goal=request.goal,
            section=request.section,
            material=request.material,
            constraints=request.constraints,
            costs=RoutingCostWeights(length=1.0, bend=0.0, support_span=2.0),
        )
        long_span = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=0.0,
            cost_breakdown={},
        )
        split_span = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), "straight"),
                RouteSegment((2.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight"),
            ],
            cost=0.0,
            cost_breakdown={},
        )

        score_candidate(long_span, model, request)
        score_candidate(split_span, model, request)

        self.assertGreater(long_span.cost, split_span.cost)
        self.assertEqual(long_span.cost_breakdown["support_span_max"], 4.0)
        self.assertEqual(split_span.cost_breakdown["support_span_max"], 2.0)


def _solver_loop_fixture():
    model = Model(project_name="SolverLoopFixture")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, allowable_stress={20.0: 120e6, 100.0: 110e6})
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=100.0)
    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
        goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
        section="PipeSec",
        material="Steel",
        constraints=RoutingConstraints(),
    )
    candidate = PipeRouteCandidate(
        request_id="P-100",
        points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        segments=[RouteSegment(start=(0.0, 0.0, 0.0), end=(2.0, 0.0, 0.0), kind="straight")],
        cost=2.0,
        cost_breakdown={"length": 2.0},
    )
    return model, request, candidate


if __name__ == "__main__":
    unittest.main()
