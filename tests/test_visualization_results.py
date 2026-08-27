import unittest

import numpy as np

from tuba import Model
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import (
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.clash import TrimeshClashEngine
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.visualization import build_visualization_scene
from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture


class TestVisualizationResults(unittest.TestCase):
    def _model_and_results(self):
        model = Model(project_name="ResultReview")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.define_load_case("Hot", gravity=True, temperature=100.0)
        results = FEAResults(solver_name="mock", load_case="Hot")
        results.node_results[n0] = NodeResult(
            node_id=n0,
            displacement=np.zeros(6),
            reaction_force=np.array([100.0, 0.0, -500.0, 25.0, 0.0, -75.0]),
        )
        results.node_results[n1] = NodeResult(
            node_id=n1,
            displacement=np.array([0.01, 0.0, 0.0, 0.0, 0.0, 0.0]),
            reaction_force=np.zeros(6),
        )
        results.element_results[elem.id] = ElementResult(
            element_id=elem.id,
            forces_n1=np.zeros(6),
            forces_n2=np.zeros(6),
            von_mises_n1=80.0e6,
            von_mises_n2=120.0e6,
            max_von_mises=120.0e6,
        )
        return model, results

    def test_build_scene_adds_deformed_shape_and_stress_overlay(self):
        model, results = self._model_and_results()

        scene = build_visualization_scene(
            model,
            solver_results=results,
            result_deformation_scale=10.0,
            scene_id="scene_result_review",
        )
        scene.validate()

        deformed = next(obj for obj in scene.objects if obj.kind == "deformed_result")
        asset = next(asset for asset in scene.geometry_assets if asset.id == deformed.geometry_asset_id)
        self.assertEqual(asset.format, "polyline")
        self.assertEqual(asset.generation_config["points"], [[0.0, 0.0, 0.0], [1.1, 0.0, 0.0]])
        self.assertEqual(deformed.metadata["load_case"], "Hot")
        self.assertEqual(deformed.metadata["deformation_scale"], 10.0)

        stress = next(overlay for overlay in scene.overlays if overlay.kind == "solver_result" and overlay.data["result_type"] == "stress")
        self.assertEqual(stress.data["values"], {"object:element:pipe_0": 120.0e6})
        self.assertEqual(stress.data["range"], {"min": 120.0e6, "max": 120.0e6})

    def test_build_scene_adds_reactions_and_keeps_temperature_as_input(self):
        model, results = self._model_and_results()

        scene = build_visualization_scene(model, solver_results=results, scene_id="scene_result_review")

        reactions = [obj for obj in scene.objects if obj.kind == "reaction_vector"]
        reaction_force = next(obj for obj in reactions if obj.metadata["result_type"] == "reaction_force")
        reaction_moment = next(obj for obj in reactions if obj.metadata["result_type"] == "reaction_moment")
        self.assertEqual(reaction_force.metadata["reaction_force_n"], [100.0, 0.0, -500.0])
        self.assertEqual(reaction_moment.metadata["reaction_moment_nm"], [25.0, 0.0, -75.0])
        self.assertIn("result:reaction_force", reaction_force.layer_ids)
        self.assertIn("result:reaction_moment", reaction_moment.layer_ids)

        self.assertFalse(
            any(
                overlay.kind == "solver_result" and overlay.data.get("result_type") == "temperature"
                for overlay in scene.overlays
            )
        )
        inputs = next(overlay for overlay in scene.overlays if overlay.kind == "load_case")
        self.assertEqual(inputs.data["load_case"], "Hot")
        self.assertEqual(inputs.data["temperature_c"], 100.0)

    def test_build_scene_adds_result_and_geometry_state_records(self):
        fixture = straight_pipe_hot_clash_fixture()
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name=fixture.results.solver_name,
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
        )
        result_state = result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)
        visual_state = create_visual_deformed_geometry_state(model=fixture.model, result_state=result_state, visual_scale=50.0)
        operating_clashes = TrimeshClashEngine().check_operating_state(
            fixture.model,
            cold_state=create_cold_geometry_state(fixture.model),
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        scene = build_visualization_scene(
            fixture.model,
            result_states=[result_state],
            geometry_states=[operating_state, visual_state],
            operating_clash_results=operating_clashes,
            scene_id="scene_operating_state",
        )
        scene.validate()

        result_object = next(obj for obj in scene.objects if obj.kind == "result_state")
        geometry_objects = [obj for obj in scene.objects if obj.kind == "geometry_state"]
        issue = scene.issues[0]
        marker = next(obj for obj in scene.objects if obj.kind == "clash_marker")

        self.assertEqual(result_object.metadata["load_case"], "Hot")
        self.assertEqual({obj.metadata["purpose"] for obj in geometry_objects}, {"engineering", "visualization"})
        self.assertEqual(issue.external_refs["clash"]["metadata"]["geometry_state"], operating_state.id)
        self.assertEqual(marker.metadata["clash_metadata"]["load_case"], "Hot")
        self.assertEqual(issue.severity, "error")


if __name__ == "__main__":
    unittest.main()
