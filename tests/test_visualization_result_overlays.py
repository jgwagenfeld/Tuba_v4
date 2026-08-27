import unittest
from dataclasses import replace

from tuba import Model
from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource, ResultState
from tuba.refs import EntityRef
from tuba.visualization import build_visualization_scene


class TestVisualizationResultOverlays(unittest.TestCase):
    def test_result_state_labels_fe_stress_without_code_utilization(self):
        model, result_state = _model_and_result_state()

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:result_overlays")
        scene.validate()

        stress = _result_overlay(scene, "stress")
        values = stress.data["values"]
        hotspot = stress.data["hotspots"][0]
        element_metadata = stress.data["element_results"]["object:element:pipe_0"]

        self.assertEqual(stress.data["result_state_id"], result_state.id)
        self.assertEqual(stress.data["load_case"], "Hot")
        self.assertEqual(values, {"object:element:pipe_0": 120.0e6})
        self.assertNotIn("utilization_values", stress.data)
        self.assertEqual(stress.name, "FE VMIS (not code stress) Hot")
        self.assertEqual(stress.data["compliance_role"], "visualization_only_not_asme_code_stress")
        self.assertEqual(stress.data["legend"]["field"], "FE VMIS (not code stress)")
        self.assertEqual(stress.data["legend"]["unit"], "Pa")
        self.assertEqual(stress.data["legend"]["range"], {"min": 120.0e6, "max": 120.0e6})
        self.assertEqual(stress.data["legend"]["color_map"], "turbo")
        self.assertEqual(stress.data["legend"]["thresholds"], {})
        self.assertEqual(hotspot["object_id"], "object:element:pipe_0")
        self.assertEqual(hotspot["value"], 120.0e6)
        self.assertNotIn("utilization", hotspot)
        self.assertEqual(element_metadata["forces_n1"], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        self.assertEqual(element_metadata["forces_n2"], [6.0, 5.0, 4.0, 3.0, 2.0, 1.0])

    def test_result_state_preserves_unavailable_force_components_as_null(self):
        model, result_state = _model_and_result_state()
        element_result = dict(result_state.element_results["pipe_0"])
        element_result["forces_n1"] = [100.0, None, None, None, None, None]
        result_state = replace(result_state, element_results={"pipe_0": element_result})

        scene = build_visualization_scene(model, result_states=[result_state])
        metadata = _result_overlay(scene, "stress").data["element_results"]["object:element:pipe_0"]

        self.assertEqual(metadata["forces_n1"], [100.0, None, None, None, None, None])

    def test_result_state_adds_displacement_reaction_and_parser_diagnostic_overlays(self):
        model, result_state = _model_and_result_state()

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:result_vectors")
        scene.validate()

        displacement = _result_overlay(scene, "displacement")
        reaction_force = _result_overlay(scene, "reaction_force")
        reaction_moment = _result_overlay(scene, "reaction_moment")
        diagnostics = _result_overlay(scene, "parser_diagnostics")

        self.assertEqual(displacement.data["result_state_id"], result_state.id)
        self.assertEqual(displacement.data["vectors"][0]["node_id"], "N0")
        self.assertEqual(displacement.data["vectors"][0]["displacement_m"], [0.001, 0.002, 0.0])
        self.assertEqual(displacement.data["values"]["N0"], [0.001, 0.002, 0.0])
        self.assertAlmostEqual(displacement.data["vectors"][0]["magnitude_m"], 0.0022360679, places=9)
        self.assertEqual(displacement.data["legend"]["unit"], "m")
        self.assertEqual(reaction_force.data["vectors"][0]["reaction_force_n"], [100.0, 0.0, -500.0])
        self.assertEqual(reaction_force.data["values"]["N0"], [100.0, 0.0, -500.0])
        self.assertEqual(reaction_force.data["legend"]["unit"], "N")
        self.assertEqual(reaction_moment.data["vectors"][0]["reaction_moment_nm"], [25.0, 0.0, -75.0])
        self.assertEqual(reaction_moment.data["values"]["N0"], [25.0, 0.0, -75.0])
        self.assertEqual(reaction_moment.data["legend"]["unit"], "N*m")
        self.assertEqual(diagnostics.data["diagnostics"], ["parser diagnostic"])
        displacement_vector = next(obj for obj in scene.objects if obj.kind == "displacement_vector")
        reaction_vectors = [obj for obj in scene.objects if obj.kind == "reaction_vector"]
        force_vector = next(obj for obj in reaction_vectors if obj.metadata["result_type"] == "reaction_force")
        moment_vector = next(obj for obj in reaction_vectors if obj.metadata["result_type"] == "reaction_moment")
        force_asset = next(asset for asset in scene.geometry_assets if asset.id == force_vector.geometry_asset_id)
        moment_asset = next(asset for asset in scene.geometry_assets if asset.id == moment_vector.geometry_asset_id)
        self.assertIn("result:displacement", displacement_vector.layer_ids)
        self.assertIn("result:reaction_force", force_vector.layer_ids)
        self.assertIn("result:reaction_moment", moment_vector.layer_ids)
        self.assertIn(force_vector.id, reaction_force.object_ids)
        self.assertIn(moment_vector.id, reaction_moment.object_ids)
        self.assertEqual(force_asset.generation_config["reaction_force_n"], [100.0, 0.0, -500.0])
        self.assertEqual(moment_asset.generation_config["reaction_moment_nm"], [25.0, 0.0, -75.0])

    def test_result_state_missing_element_results_emit_diagnostics(self):
        model, result_state = _model_and_result_state(element_results=False)

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:missing_result_overlay")
        scene.validate()

        diagnostic_codes = {diagnostic.code for diagnostic in scene.diagnostics}
        self.assertIn("result_state.missing_element_result", diagnostic_codes)

    def test_non_finite_stress_is_unavailable_instead_of_rendered(self):
        model, result_state = _model_and_result_state()
        data = dict(result_state.element_results["pipe_0"])
        data["max_von_mises"] = float("nan")
        result_state = replace(result_state, element_results={"pipe_0": data})

        scene = build_visualization_scene(model, result_states=[result_state])

        self.assertNotIn(
            "stress",
            {overlay.data.get("result_type") for overlay in scene.overlays},
        )
        self.assertIn("result_state.invalid_stress", {item.code for item in scene.diagnostics})

    def test_analysis_mesh_displacement_uses_mesh_node_without_duplicate_vector_geometry(self):
        model, result_state = _model_and_result_state()
        generated_node = "pipe_0_mid"
        result_state = replace(
            result_state,
            node_displacements={
                **result_state.node_displacements,
                generated_node: (0.003, 0.004, 0.0, 0.0, 0.0, 0.0),
            },
        )
        mesh = AnalysisMesh(
            id=result_state.mesh_id,
            model_revision=0,
            solver_name="Code_Aster",
            nodes={"N0": (0.0, 0.0, 0.0), "N1": (1.0, 0.0, 0.0), generated_node: (0.5, 0.0, 0.0)},
            elements={"pipe_0": ("N0", generated_node, "N1")},
            groups={"AllPipes": ("pipe_0",)},
            node_sources={
                "N0": MeshNodeSource("N0", EntityRef("node", "N0"), "native_node"),
                "N1": MeshNodeSource("N1", EntityRef("node", "N1"), "native_node"),
                generated_node: MeshNodeSource(
                    generated_node,
                    EntityRef("element", "pipe_0"),
                    "generated_mid_node",
                    parametric_t=0.5,
                ),
            },
            element_sources={
                "pipe_0": MeshElementSource("pipe_0", EntityRef("element", "pipe_0"), "native_element")
            },
        )

        scene = build_visualization_scene(
            model,
            result_states=[result_state],
            analysis_meshes=[mesh],
            scene_id="scene:mapped_displacement",
        )
        scene.validate()

        displacement = _result_overlay(scene, "displacement")
        vector = next(item for item in displacement.data["vectors"] if item["node_id"] == generated_node)
        mesh_node_object_id = f"object:analysis_mesh:{mesh.id}:node:{generated_node}"
        self.assertEqual(vector["start"], [0.5, 0.0, 0.0])
        self.assertEqual(vector["end"], [0.503, 0.004, 0.0])
        self.assertEqual(vector["object_ids"], [mesh_node_object_id])
        self.assertIn(mesh_node_object_id, displacement.object_ids)
        self.assertNotIn("result_state.missing_node_geometry", {item.code for item in scene.diagnostics})
        self.assertEqual(len([obj for obj in scene.objects if obj.kind == "displacement_vector"]), 2)

    def test_result_state_node_absent_from_model_and_analysis_mesh_still_warns(self):
        model, result_state = _model_and_result_state()
        result_state = replace(
            result_state,
            node_displacements={**result_state.node_displacements, "missing_node": (0.1, 0.0, 0.0, 0.0, 0.0, 0.0)},
        )

        scene = build_visualization_scene(model, result_states=[result_state], scene_id="scene:unmapped_displacement")

        self.assertIn("result_state.missing_node_geometry", {item.code for item in scene.diagnostics})

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
        result_state_overlay = next(item for item in scene.overlays if item.kind == "result_state")
        result_state_object = next(item for item in scene.objects if item.kind == "result_state")

        self.assertEqual(asset.format, "tuyau_subpoint_glyphs")
        self.assertEqual(asset.generation_config["source"], "tuba.tuyau_subpoint_field")
        self.assertEqual(asset.generation_config["legend"]["field"], "FE VMIS (not code stress)")
        self.assertEqual(asset.generation_config["compliance_role"], "visualization_only_not_asme_code_stress")
        self.assertEqual(len(asset.generation_config["starts"]), 2)
        self.assertEqual(len(asset.generation_config["ends"]), 2)
        self.assertEqual(asset.generation_config["values"], [42.0e6, 84.0e6])
        self.assertLess(asset.generation_config["starts"][0][2], 0.04)
        self.assertGreater(asset.generation_config["ends"][0][2], 0.04)
        self.assertEqual(asset.generation_config["radius_m"], 0.006)
        self.assertIn("solver_result:tuyau_subpoints", subpoint.layer_ids)
        self.assertEqual(subpoint.name, "TUYAU FE VMIS (not code stress) Hot")
        self.assertEqual(subpoint.metadata["compliance_role"], "visualization_only_not_asme_code_stress")
        self.assertEqual(subpoint.metadata["position_source"], "code_aster_tuyau_subpoint_formula")
        self.assertEqual(subpoint.metadata["count"], 2)
        self.assertEqual(overlay.name, "TUYAU FE VMIS (not code stress) Hot")
        self.assertEqual(overlay.data["total_count"], 2)
        self.assertEqual(overlay.data["rendered_count"], 2)
        self.assertEqual(overlay.data["legend"]["field"], "FE VMIS (not code stress)")
        self.assertEqual(overlay.data["compliance_role"], "visualization_only_not_asme_code_stress")
        self.assertNotIn("render_limit", overlay.data)
        self.assertEqual(overlay.data["range"], {"min": 42.0e6, "max": 84.0e6})
        self.assertEqual(overlay.data["source_file"], "study_sieq.csv")
        self.assertEqual(overlay.data["position_source"], "code_aster_tuyau_subpoint_formula")
        # The sub-point grid and the peak's place in the wall, decoded from the
        # Code_Aster index so the viewer never re-derives the convention.
        self.assertEqual(overlay.data["section_profile"]["nsec"], 16)
        self.assertEqual(overlay.data["section_profile"]["ncou"], 3)
        self.assertEqual(overlay.data["section_profile"]["sectors"], 33)
        self.assertEqual(overlay.data["section_profile"]["layers"], 7)
        self.assertEqual(asset.generation_config["section_profile"], overlay.data["section_profile"])
        self.assertEqual(asset.generation_config["sector_indices"], [2, 3])
        self.assertEqual(asset.generation_config["layer_indices"], [0, 0])
        self.assertEqual(overlay.data["peak"]["value"], 84.0e6)
        self.assertEqual(overlay.data["peak"]["subpoint_index"], 4)
        self.assertEqual(overlay.data["peak"]["sector_index"], 3)
        self.assertEqual(overlay.data["peak"]["wall_position"], "bore")
        self.assertAlmostEqual(overlay.data["peak"]["angle_deg"], 360.0 * 3 / 32.0)
        self.assertNotIn("tuyau_subpoints", result_state_overlay.data["metadata"])
        self.assertEqual(result_state_overlay.data["metadata"]["tuyau_subpoint_count"], 2)
        self.assertNotIn("tuyau_subpoints", result_state_object.source["tuba_result_state"]["metadata"])


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
            n0: (100.0, 0.0, -500.0, 25.0, 0.0, -75.0),
        },
        element_results=results,
        metadata={"parser_diagnostics": ["parser diagnostic"]},
    )


if __name__ == "__main__":
    unittest.main()
