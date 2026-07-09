import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from tuba import Model
from tuba.routing.solver_loop import SolverLoopConfig, SolverLoopScorer
from tuba.routing.thermal import SolverAcceptanceCriteria
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


class CapturingRuntimeSolver(PassingSolver):
    instances = []

    def __init__(self, work_dir, **kwargs):
        super().__init__(work_dir)
        self.kwargs = kwargs
        self.instances.append(self)


class CapturingModelSolver(PassingSolver):
    exported_models = []

    def export_study(self, model, load_case, output_dir):
        self.exported_models.append(model)
        super().export_study(model, load_case, output_dir)


class MomentHeavySolver(PassingSolver):
    def solve(self, model, load_case):
        results = FEAResults(solver_name="FakeSolver", load_case=load_case)
        for node_id in model.nodes:
            results.node_results[node_id] = NodeResult(
                node_id=node_id,
                displacement=np.zeros(6),
                reaction_force=np.array([1.0, 2.0, 2.0, 1000.0, 1000.0, 1000.0]),
            )
        for elem in model.elements:
            results.element_results[elem.id] = ElementResult(
                element_id=elem.id,
                forces_n1=np.zeros(6),
                forces_n2=np.zeros(6),
                max_von_mises=1.0,
            )
        return results


class RejectingComplianceReport:
    overall_pass = False
    worst_sustained_ratio = 0.1
    worst_expansion_ratio = 0.75
    results = []


class RejectingComplianceEvaluator:
    def evaluate(self, model, results):
        return RejectingComplianceReport()


class PassingComplianceReport:
    overall_pass = True
    worst_sustained_ratio = 0.1
    worst_expansion_ratio = 0.1
    results = []


class PassingComplianceEvaluator:
    def evaluate(self, model, results):
        return PassingComplianceReport()


class SequencedComplianceEvaluator:
    def __init__(self, reports):
        self._reports = list(reports)

    def evaluate(self, model, results):
        return self._reports.pop(0)


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

    def test_solver_loop_passes_code_aster_runtime_config_to_solver(self):
        model, request, candidate = _solver_loop_fixture()
        CapturingRuntimeSolver.instances = []

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(solver_factory=CapturingRuntimeSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=False,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Hot",
                    exec_method="wsl",
                    wsl_distro="Ubuntu",
                    docker_image=None,
                ),
            )

        self.assertEqual(CapturingRuntimeSolver.instances[0].kwargs["exec_method"], "wsl")
        self.assertEqual(CapturingRuntimeSolver.instances[0].kwargs["wsl_distro"], "Ubuntu")

    def test_solver_loop_applies_configured_candidate_supports_to_solver_model(self):
        model, request, candidate = _solver_loop_fixture()
        candidate.points = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
        candidate.segments = [RouteSegment(start=(0.0, 0.0, 0.0), end=(4.0, 0.0, 0.0), kind="straight")]
        CapturingModelSolver.exported_models = []

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(solver_factory=CapturingModelSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=False,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Hot",
                    add_supports=True,
                    support_spacing=2.0,
                    anchor_endpoints=True,
                ),
            )

        solver_model = CapturingModelSolver.exported_models[0]
        support_types = [support.type for support in solver_model.supports]
        self.assertEqual(support_types.count("anchor"), 2)
        self.assertIn("rest", support_types)

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

    def test_solver_failure_raises_in_strict_mode(self):
        model, request, candidate = _solver_loop_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                SolverLoopScorer(solver_factory=FailingSolver).score_candidates(
                    model,
                    request,
                    [candidate],
                    SolverLoopConfig(
                        run_solver=True,
                        export_study=True,
                        max_solver_candidates=1,
                        work_root=tmpdir,
                        strict=True,
                    ),
                )

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

    def test_solver_loop_marks_candidate_rejected_by_expansion_ratio(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
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

        self.assertFalse(ranked[0].metadata["solver_acceptance"]["accepted"])
        self.assertIn("expansion_ratio", ranked[0].metadata["solver_acceptance"]["failed_checks"])
        self.assertNotIn("_solver_acceptance_restore_valid", ranked[0].metadata)
        self.assertFalse(ranked[0].is_valid)

    def test_solver_loop_accepts_candidate_with_permissive_criteria(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(
                max_expansion_ratio=10.0,
                max_sustained_ratio=10.0,
                max_anchor_reaction_n=10.0,
            ),
        )

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

        self.assertTrue(ranked[0].metadata["solver_acceptance"]["accepted"])
        self.assertEqual(ranked[0].metadata["solver_acceptance"]["failed_checks"], [])
        self.assertTrue(ranked[0].is_valid)

    def test_solver_loop_ranks_accepted_candidates_before_rejected_cheaper_candidates(self):
        model, request, cheap_candidate = _solver_loop_fixture()
        request = replace(
            request,
            constraints=replace(request.constraints, min_bend_radius=0.2),
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )
        expensive_candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (1.0, 3.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (1.0, 3.0, 0.0), "straight"),
                RouteSegment((1.0, 3.0, 0.0), (2.0, 0.0, 0.0), "straight"),
            ],
            cost=3.0,
            cost_breakdown={"length": 3.0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=SequencedComplianceEvaluator(
                    [RejectingComplianceReport(), PassingComplianceReport()]
                ),
            ).score_candidates(
                model,
                request,
                [cheap_candidate, expensive_candidate],
                SolverLoopConfig(
                    run_solver=True,
                    export_study=True,
                    max_solver_candidates=2,
                    work_root=tmpdir,
                    load_case="Hot",
                ),
            )

        self.assertIs(ranked[0], expensive_candidate)
        self.assertTrue(ranked[0].metadata["solver_acceptance"]["accepted"])
        self.assertIs(ranked[1], cheap_candidate)
        self.assertFalse(ranked[1].metadata["solver_acceptance"]["accepted"])

    def test_solver_acceptance_is_idempotent_when_candidate_is_scored_repeatedly(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )
        config = SolverLoopConfig(run_solver=True, export_study=True, max_solver_candidates=1, load_case="Hot")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = replace(config, work_root=tmpdir)
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(model, request, [candidate], config)
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(model, request, [candidate], config)

            rejection_diagnostics = [
                diagnostic
                for diagnostic in candidate.diagnostics
                if diagnostic.startswith("Solver acceptance failed:")
            ]
            self.assertEqual(rejection_diagnostics, ["Solver acceptance failed: expansion_ratio"])
            self.assertFalse(candidate.is_valid)

            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=PassingComplianceEvaluator(),
            ).score_candidates(model, request, [candidate], config)

        self.assertTrue(candidate.metadata["solver_acceptance"]["accepted"])
        self.assertEqual(candidate.metadata["solver_acceptance"]["failed_checks"], [])
        self.assertTrue(candidate.is_valid)
        self.assertFalse(
            any(diagnostic.startswith("Solver acceptance failed:") for diagnostic in candidate.diagnostics)
        )

    def test_solver_loop_clears_stale_acceptance_when_solver_is_not_run(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
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
            ranked = SolverLoopScorer(solver_factory=PassingSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=False,
                    export_study=False,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Cold",
                ),
            )

        self.assertIs(ranked[0], candidate)
        self.assertFalse(ranked[0].metadata["solver"]["solver_ran"])
        self.assertNotIn("solver_name", ranked[0].metadata["solver"])
        self.assertNotIn("compliance", ranked[0].metadata)
        self.assertNotIn("reactions", ranked[0].metadata)
        self.assertNotIn("displacements", ranked[0].metadata)
        self.assertNotIn("solver_acceptance", ranked[0].metadata)
        self.assertTrue(ranked[0].is_valid)
        self.assertFalse(
            any(diagnostic.startswith("Solver acceptance failed:") for diagnostic in ranked[0].diagnostics)
        )

    def test_solver_loop_clears_stale_acceptance_when_solver_fails_before_results_attach(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
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
            ranked = SolverLoopScorer(solver_factory=FailingSolver).score_candidates(
                model,
                request,
                [candidate],
                SolverLoopConfig(
                    run_solver=True,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Cold",
                ),
            )

        self.assertIs(ranked[0], candidate)
        self.assertFalse(ranked[0].metadata["solver"]["solver_ran"])
        self.assertNotIn("solver_name", ranked[0].metadata["solver"])
        self.assertNotIn("compliance", ranked[0].metadata)
        self.assertNotIn("reactions", ranked[0].metadata)
        self.assertNotIn("displacements", ranked[0].metadata)
        self.assertNotIn("solver_acceptance", ranked[0].metadata)
        self.assertTrue(ranked[0].is_valid)
        self.assertIn("Solver loop failed", " ".join(ranked[0].diagnostics))
        self.assertFalse(
            any(diagnostic.startswith("Solver acceptance failed:") for diagnostic in ranked[0].diagnostics)
        )

    def test_solver_loop_clears_stale_acceptance_when_criteria_removed(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
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
            ranked = SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
                model,
                replace(request, solver_acceptance=None),
                [candidate],
                SolverLoopConfig(
                    run_solver=True,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Cold",
                ),
            )

        self.assertIs(ranked[0], candidate)
        self.assertTrue(ranked[0].metadata["solver"]["solver_ran"])
        self.assertIn("compliance", ranked[0].metadata)
        self.assertNotIn("solver_acceptance", ranked[0].metadata)
        self.assertTrue(ranked[0].is_valid)
        self.assertFalse(
            any(diagnostic.startswith("Solver acceptance failed:") for diagnostic in ranked[0].diagnostics)
        )

    def test_solver_loop_clears_stale_acceptance_outside_solver_candidate_window(self):
        model, request, stale_candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
        )
        fresh_candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), "straight")],
            cost=1.0,
            cost_breakdown={"length": 1.0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            SolverLoopScorer(
                solver_factory=PassingSolver,
                compliance_evaluator=RejectingComplianceEvaluator(),
            ).score_candidates(
                model,
                request,
                [stale_candidate],
                SolverLoopConfig(
                    run_solver=True,
                    export_study=True,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Hot",
                ),
            )
            ranked = SolverLoopScorer(solver_factory=PassingSolver).score_candidates(
                model,
                request,
                [fresh_candidate, stale_candidate],
                SolverLoopConfig(
                    run_solver=False,
                    export_study=False,
                    max_solver_candidates=1,
                    work_root=tmpdir,
                    load_case="Cold",
                ),
            )

        self.assertIs(ranked[0], fresh_candidate)
        self.assertIs(ranked[1], stale_candidate)
        self.assertTrue(stale_candidate.is_valid)
        self.assertNotIn("solver", stale_candidate.metadata)
        self.assertNotIn("solver_acceptance", stale_candidate.metadata)
        self.assertNotIn("compliance", stale_candidate.metadata)
        self.assertNotIn("reactions", stale_candidate.metadata)
        self.assertNotIn("displacements", stale_candidate.metadata)
        self.assertNotIn("_solver_acceptance_restore_valid", stale_candidate.metadata)
        self.assertFalse(
            any(diagnostic.startswith("Solver acceptance failed:") for diagnostic in stale_candidate.diagnostics)
        )

    def test_anchor_reaction_acceptance_uses_force_components_only(self):
        model, request, candidate = _solver_loop_fixture()
        request = replace(
            request,
            solver_acceptance=SolverAcceptanceCriteria(max_anchor_reaction_n=3.5),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ranked = SolverLoopScorer(
                solver_factory=MomentHeavySolver,
                compliance_evaluator=PassingComplianceEvaluator(),
            ).score_candidates(
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

        self.assertTrue(ranked[0].metadata["solver_acceptance"]["accepted"])
        self.assertEqual(ranked[0].metadata["solver_acceptance"]["max_reaction_n"], 3.0)
        self.assertNotIn("anchor_reaction", ranked[0].metadata["solver_acceptance"]["failed_checks"])

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
