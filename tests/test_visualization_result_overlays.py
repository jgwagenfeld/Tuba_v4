import unittest
from dataclasses import replace

from tuba import Model
from tuba.analysis import ResultState
from tuba.visualization import build_visualization_scene


class TestVisualizationResultOverlays(unittest.TestCase):
    def test_result_state_adds_stress_utilization_legend_and_hotspots(self):
        model, result_state = _model_and_result_state()

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:result_overlays")
        scene.validate()

        stress = _result_overlay(scene, "stress")
        values = stress.data["values"]
        utilization = stress.data["utilization_values"]
        hotspot = stress.data["hotspots"][0]
        element_metadata = stress.data["element_results"]["object:element:pipe_0"]

        self.assertEqual(stress.data["result_state_id"], result_state.id)
        self.assertEqual(stress.data["load_case"], "Hot")
        self.assertEqual(values, {"object:element:pipe_0": 120.0e6})
        self.assertEqual(utilization, {"object:element:pipe_0": 0.6})
        self.assertEqual(stress.data["legend"]["field"], "max_von_mises")
        self.assertEqual(stress.data["legend"]["unit"], "Pa")
        self.assertEqual(stress.data["legend"]["range"], {"min": 120.0e6, "max": 120.0e6})
        self.assertEqual(stress.data["legend"]["color_map"], "turbo")
        self.assertEqual(stress.data["legend"]["thresholds"]["critical"], 1.0)
        self.assertEqual(hotspot["object_id"], "object:element:pipe_0")
        self.assertEqual(hotspot["value"], 120.0e6)
        self.assertEqual(hotspot["utilization"], 0.6)
        self.assertEqual(element_metadata["forces_n1"], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        self.assertEqual(element_metadata["forces_n2"], [6.0, 5.0, 4.0, 3.0, 2.0, 1.0])

    def test_result_state_adds_displacement_reaction_and_parser_diagnostic_overlays(self):
        model, result_state = _model_and_result_state()

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:result_vectors")
        scene.validate()

        displacement = _result_overlay(scene, "displacement")
        reaction = _result_overlay(scene, "reaction")
        diagnostics = _result_overlay(scene, "parser_diagnostics")

        self.assertEqual(displacement.data["result_state_id"], result_state.id)
        self.assertEqual(displacement.data["vectors"][0]["node_id"], "N0")
        self.assertEqual(displacement.data["vectors"][0]["displacement_m"], [0.001, 0.002, 0.0])
        self.assertAlmostEqual(displacement.data["vectors"][0]["magnitude_m"], 0.0022360679, places=9)
        self.assertEqual(displacement.data["legend"]["unit"], "m")
        self.assertEqual(reaction.data["vectors"][0]["node_id"], "N0")
        self.assertEqual(reaction.data["vectors"][0]["reaction_force_n"], [100.0, 0.0, -500.0])
        self.assertEqual(reaction.data["legend"]["unit"], "N")
        self.assertEqual(diagnostics.data["diagnostics"], ["parser diagnostic"])

    def test_result_state_missing_element_results_emit_diagnostics(self):
        model, result_state = _model_and_result_state(element_results=False)

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:missing_result_overlay")
        scene.validate()

        diagnostic_codes = {diagnostic.code for diagnostic in scene.diagnostics}
        self.assertIn("result_state.missing_element_result", diagnostic_codes)

    def test_result_state_adds_batched_tuyau_subpoint_layer(self):
        model, result_state = _model_and_result_state()
        result_state = replace(
            result_state,
            files={**result_state.files, "tuyau_subpoints": "study_sieq.csv"},
            metadata={
                **result_state.metadata,
                "tuyau_subpoints": [
                    {
                        "field": "SIEQ_ELNO",
                        "component": "VMIS",
                        "unit": "Pa",
                        "value": 42.0e6,
                        "element_id": "pipe_0",
                        "analysis_element_id": "pipe_0",
                        "solver_element_label": "M1",
                        "node_id": "N0",
                        "solver_node_label": "N1",
                        "subpoint_index": 3,
                        "centerline_position": [0.0, 0.0, 0.0],
                        "display_position": [0.0, 0.0, 0.04],
                        "position_source": "code_aster_tuyau_subpoint_formula",
                    },
                    {
                        "field": "SIEQ_ELNO",
                        "component": "VMIS",
                        "unit": "Pa",
                        "value": 84.0e6,
                        "element_id": "pipe_0",
                        "analysis_element_id": "pipe_0",
                        "solver_element_label": "M1",
                        "node_id": "N0",
                        "solver_node_label": "N1",
                        "subpoint_index": 4,
                        "centerline_position": [0.0, 0.0, 0.0],
                        "display_position": [0.0, 0.02, 0.034641],
                        "position_source": "code_aster_tuyau_subpoint_formula",
                    }
                ],
            },
        )

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:tuyau_subpoints")
        scene.validate()

        subpoint = next(obj for obj in scene.objects if obj.kind == "tuyau_subpoint_field")
        asset = next(asset for asset in scene.geometry_assets if asset.id == subpoint.geometry_asset_id)
        overlay = _result_overlay(scene, "tuyau_subpoints")

        self.assertEqual(asset.format, "tuyau_subpoint_glyphs")
        self.assertEqual(asset.generation_config["source"], "tuba.tuyau_subpoint_field")
        self.assertEqual(len(asset.generation_config["starts"]), 2)
        self.assertEqual(len(asset.generation_config["ends"]), 2)
        self.assertEqual(asset.generation_config["values"], [42.0e6, 84.0e6])
        self.assertLess(asset.generation_config["starts"][0][2], 0.04)
        self.assertGreater(asset.generation_config["ends"][0][2], 0.04)
        self.assertEqual(asset.generation_config["radius_m"], 0.006)
        self.assertIn("solver_result:tuyau_subpoints", subpoint.layer_ids)
        self.assertEqual(subpoint.metadata["position_source"], "code_aster_tuyau_subpoint_formula")
        self.assertEqual(subpoint.metadata["count"], 2)
        self.assertEqual(overlay.data["total_count"], 2)
        self.assertEqual(overlay.data["rendered_count"], 2)
        self.assertNotIn("render_limit", overlay.data)
        self.assertEqual(overlay.data["range"], {"min": 42.0e6, "max": 84.0e6})
        self.assertEqual(overlay.data["source_file"], "study_sieq.csv")
        self.assertEqual(overlay.data["position_source"], "code_aster_tuyau_subpoint_formula")


def _result_overlay(scene, result_type):
    return next(
        overlay
        for overlay in scene.overlays
        if overlay.kind == "solver_result" and overlay.data.get("result_type") == result_type
    )


def _model_and_result_state(*, element_results=True):
    model = Model(project_name="ResultOverlays")
    model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={100.0: 200.0e6})
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
    model.define_load_case("Hot", gravity=True, temperature=100.0)
    results = {}
    if element_results:
        results["pipe_0"] = {
            "forces_n1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "forces_n2": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
            "von_mises_n1": 80.0e6,
            "von_mises_n2": 120.0e6,
            "max_von_mises": 120.0e6,
        }
    return model, ResultState(
        id="result_state:Hot",
        study_id="analysis_study:Hot",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id="analysis_mesh:Hot",
        node_displacements={
            n0: (0.001, 0.002, 0.0, 0.0, 0.0, 0.0),
            n1: (0.002, 0.0, 0.0, 0.0, 0.0, 0.0),
        },
        node_reactions={
            n0: (100.0, 0.0, -500.0, 0.0, 0.0, 0.0),
        },
        element_results=results,
        metadata={"parser_diagnostics": ["parser diagnostic"]},
    )


if __name__ == "__main__":
    unittest.main()
