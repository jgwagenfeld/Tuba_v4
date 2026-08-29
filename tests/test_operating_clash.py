import unittest

from tuba import Model
from tuba.analysis import ResultState
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import ClashEngine


class TestOperatingClash(unittest.TestCase):
    def test_operating_state_reports_deformation_introduced_clash(self):
        model = Model(project_name="OperatingClash")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_obstacle(
            id="tray_0",
            type="cuboid",
            min_point=[0.5, 0.08, -0.10],
            max_point=[1.5, 0.18, 0.10],
        )
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={
                n0: (0.0, 0.06, 0.0, 0.0, 0.0, 0.0),
                n1: (0.0, 0.06, 0.0, 0.0, 0.0, 0.0),
            },
            node_reactions={},
            element_results={},
        )
        cold_state = create_cold_geometry_state(model)
        operating_state = create_operating_geometry_state(model=model, result_state=result_state)

        cold_clashes = ClashEngine().check_model(model)
        operating_clashes = ClashEngine().check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        self.assertEqual(cold_clashes, [])
        self.assertEqual(len(operating_clashes), 1)
        clash = operating_clashes[0]
        self.assertEqual(clash.severity, "operating_only_hard")
        self.assertEqual(str(clash.left), "element:pipe_0")
        self.assertEqual(str(clash.right), "obstacle:tray_0")
        self.assertTrue(clash.metadata["introduced_by_deformation"])
        self.assertEqual(clash.metadata["load_case"], "Hot")
        self.assertEqual(clash.metadata["geometry_state"], operating_state.id)
        self.assertGreater(clash.metadata["cold_distance_m"], clash.metadata["operating_distance_m"])


if __name__ == "__main__":
    unittest.main()


class TestColdCentrelineMatchesTheOperatingOne(unittest.TestCase):
    """Both sides of an operating comparison must use the same discretisation.

    A bend's operating centreline runs through the generated interior nodes.
    Measuring the cold side on the two-point chord compared a chord against an
    arc, so part of the reported movement was the discretisation rather than
    anything the solver returned.
    """

    def test_cold_bend_centreline_follows_the_arc_not_the_chord(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        import numpy as np

        from examples.code_aster_artifact_review import build_autorouted_expansion_model
        from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
        from tuba.clash.operating import _cold_polyline

        with TemporaryDirectory() as tmpdir:
            model, _route = build_autorouted_expansion_model(Path(tmpdir) / "routing")
        run = import_code_aster_artifacts(
            model=model,
            work_dir=Path("notebooks/code_aster_results/autorouted_expansion_hot"),
        )
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        chord = _cold_polyline(model, bend)
        arc = _cold_polyline(
            model, bend, result_state=run.result_state, analysis_mesh=run.analysis_mesh
        )

        self.assertEqual(len(chord), 2)
        self.assertGreater(len(arc), 2, "a meshed bend must be discretised, not chorded")

        # Every arc point sits on the bend circle; the chord's midpoint cuts
        # inside it, which is exactly the error the old cold side introduced.
        centre = np.asarray(bend.bend_geometry.center, dtype=float)
        radius = float(
            np.linalg.norm(np.asarray(model.nodes[bend.n1].coords, dtype=float) - centre)
        )
        for point in arc:
            self.assertAlmostEqual(
                float(np.linalg.norm(np.asarray(point) - centre)), radius, places=9
            )
        chord_midpoint = (np.asarray(chord[0]) + np.asarray(chord[1])) / 2.0
        self.assertLess(
            float(np.linalg.norm(chord_midpoint - centre)),
            radius - 1e-3,
            "the chord cuts inside the arc, which is why it cannot be the cold side",
        )
