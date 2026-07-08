import unittest

from tuba import Model
from tuba.analysis import (
    AnalysisMesh,
    GeometryState,
    MeshElementSource,
    MeshNodeSource,
    ResultState,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.refs import EntityRef
from tuba.visualization import build_visualization_scene


class TestVisualizationDeformedStates(unittest.TestCase):
    def test_build_scene_adds_physical_and_visual_deformed_centerlines_and_envelopes(self):
        model, result_state, analysis_mesh = _model_state_and_mesh()
        cold_n0 = model.nodes["N0"].coords.copy()
        operating_state = create_operating_geometry_state(model=model, result_state=result_state)
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(
            model,
            result_states=[result_state],
            geometry_states=[operating_state, visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:deformed_states",
        )
        scene.validate()

        physical = _deformed_object(scene, "deformed_centerline", operating_state.id)
        visual = _deformed_object(scene, "deformed_centerline", visual_state.id)
        visual_envelope = _deformed_object(scene, "deformed_envelope", visual_state.id)
        physical_asset = _asset(scene, physical.geometry_asset_id)
        visual_asset = _asset(scene, visual.geometry_asset_id)
        envelope_asset = _asset(scene, visual_envelope.geometry_asset_id)

        self.assertEqual(physical_asset.generation_config["points"], [[0.0, 0.1, 0.0], [1.0, 0.1, 0.0]])
        self.assertEqual(visual_asset.generation_config["points"], [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])
        self.assertEqual(visual_asset.generation_config["base_points"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertEqual(envelope_asset.generation_config["base_points"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertIn("deformed:physical_centerline", physical.layer_ids)
        self.assertIn("deformed:visual_centerline", visual.layer_ids)
        self.assertIn("deformed:visual_envelope", visual_envelope.layer_ids)
        self.assertEqual(visual.metadata["result_state_id"], result_state.id)
        self.assertEqual(visual.metadata["load_case"], "Hot")
        self.assertEqual(visual.metadata["displacement_scale"], 10.0)
        self.assertEqual(visual.metadata["purpose"], "visualization")
        self.assertEqual(envelope_asset.generation_config["radius_m"], 0.08)
        self.assertEqual(envelope_asset.generation_config["envelope_type"], "insulation")
        self.assertEqual(model.nodes["N0"].coords.tolist(), cold_n0.tolist())

    def test_build_scene_adds_warped_analysis_mesh_layer_when_mesh_is_available(self):
        model, result_state, analysis_mesh = _model_state_and_mesh()
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:warped_analysis_mesh",
        )

        warped = _deformed_object(scene, "deformed_analysis_mesh_element", visual_state.id)
        warped_asset = _asset(scene, warped.geometry_asset_id)

        self.assertEqual(warped_asset.format, "polyline")
        self.assertEqual(warped_asset.generation_config["source"], "tuba.deformed_analysis_mesh.element")
        self.assertEqual(warped_asset.generation_config["points"], [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])
        self.assertEqual(warped_asset.generation_config["base_points"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertEqual(warped.metadata["mesh_id"], analysis_mesh.id)
        self.assertEqual(warped.metadata["source_ref"], "element:pipe_0")
        self.assertIn("deformed:mesh", warped.layer_ids)
        self.assertIn("analysis_mesh:group:AllPipes", warped.layer_ids)


def _deformed_object(scene, kind, geometry_state_id):
    return next(
        obj
        for obj in scene.objects
        if obj.kind == kind and obj.metadata.get("geometry_state_id") == geometry_state_id
    )


def _asset(scene, asset_id):
    return next(asset for asset in scene.geometry_assets if asset.id == asset_id)


def _model_state_and_mesh():
    model = Model(project_name="DeformedScene")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    model.add_insulation_spec("mw_30", material="mineral_wool", thickness_m=0.03)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
    model.assign_insulation("element:pipe_0", "mw_30")
    model.define_load_case("Hot", gravity=True, temperature=120.0)
    result_state = ResultState(
        id="result_state:Hot",
        study_id="analysis_study:Hot",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id="analysis_mesh:Hot",
        node_displacements={
            n0: (0.0, 0.1, 0.0, 0.0, 0.0, 0.0),
            n1: (0.0, 0.1, 0.0, 0.0, 0.0, 0.0),
        },
        node_reactions={},
        element_results={},
    )
    analysis_mesh = AnalysisMesh(
        id="analysis_mesh:Hot",
        model_revision=0,
        solver_name="Code_Aster",
        nodes={n0: (0.0, 0.0, 0.0), n1: (1.0, 0.0, 0.0)},
        elements={"pipe_0": (n0, n1)},
        groups={"AllPipes": ("pipe_0",)},
        node_sources={
            n0: MeshNodeSource(node_id=n0, source_ref=EntityRef("node", n0), role="native_node"),
            n1: MeshNodeSource(node_id=n1, source_ref=EntityRef("node", n1), role="native_node"),
        },
        element_sources={
            "pipe_0": MeshElementSource(element_id="pipe_0", source_ref=EntityRef("element", "pipe_0"), role="native_element"),
        },
    )
    return model, result_state, analysis_mesh


if __name__ == "__main__":
    unittest.main()
