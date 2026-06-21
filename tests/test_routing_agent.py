import tempfile
import unittest
from pathlib import Path

from tuba import Model
from tuba.routing import GridRouter
from tuba.routing.agent import AutoroutingAgent
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


class TestAutoroutingAgent(unittest.TestCase):
    def test_route_pipe_exports_applies_and_reports(self):
        model = Model(project_name="AgentRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, allowable_stress={20.0: 120e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=100.0)
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.5, -0.3, -0.3],
            max_point=[2.5, 0.3, 0.3],
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.05, min_bend_radius=0.2),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            run = AutoroutingAgent(
                router=GridRouter(RoutingGridSpec(cell_size=0.5, margin=1.0), candidate_count=2),
                solver_config=SolverLoopConfig(run_solver=False, export_study=True, max_solver_candidates=1),
                output_root=tmpdir,
            ).route_pipe(model, request, apply=True)

            self.assertIsNotNone(run.result.selected)
            self.assertTrue(run.created_element_ids)
            self.assertTrue(run.report_path.exists())
            self.assertTrue((Path(tmpdir) / "P-100" / "route_result.json").exists())
            self.assertTrue((Path(tmpdir) / "P-100" / "studies" / "P-100" / "candidate_0" / "study.comm").exists())


if __name__ == "__main__":
    unittest.main()
