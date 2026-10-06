import math
import unittest

from tuba import Model
from tuba.analysis import (
    AnalysisMesh,
    MeshElementSource,
    MeshNodeSource,
    ResultState,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.refs import EntityRef
from tuba.visualization import SceneRequest, build_visualization_scene


class TestVisualizationDeformedStates(unittest.TestCase):
    def test_build_scene_adds_physical_and_visual_deformed_centerlines_and_envelopes(self):
        model, result_state, analysis_mesh = _model_state_and_mesh()
        cold_n0 = model.nodes["N0"].coords.copy()
        operating_state = create_operating_geometry_state(model=model, result_state=result_state)
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[operating_state, visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:deformed_states",
        ))
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
        self.assertFalse(next(layer for layer in scene.layers if layer.id == "deformed:visual_envelope").default_visible)
        self.assertEqual(model.nodes["N0"].coords.tolist(), cold_n0.tolist())

    def test_build_scene_adds_warped_profile_geometry_when_analysis_mesh_is_available(self):
        model, result_state, analysis_mesh = _model_state_and_mesh()
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:warped_analysis_mesh",
        ))

        warped = _deformed_object(scene, "deformed_analysis_mesh_element", visual_state.id)
        warped_asset = _asset(scene, warped.geometry_asset_id)

        self.assertEqual(warped_asset.format, "tube")
        self.assertEqual(warped_asset.generation_config["source"], "tuba.deformed_analysis_mesh.profile")
        self.assertEqual(warped_asset.generation_config["profile_kind"], "pipe")
        self.assertEqual(warped_asset.generation_config["radius_m"], 0.05)
        self.assertEqual(warped_asset.generation_config["inner_radius_m"], 0.04)
        self.assertEqual(warped_asset.generation_config["points"], [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])
        self.assertEqual(warped_asset.generation_config["base_points"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertEqual(warped.metadata["mesh_id"], analysis_mesh.id)
        self.assertEqual(warped.metadata["source_ref"], "element:pipe_0")
        self.assertIn("deformed:mesh", warped.layer_ids)
        self.assertIn("deformed:group:AllPipes", warped.layer_ids)
        self.assertIn("AllPipes", warped.group_ids)
        self.assertTrue(all(layer.category == "results" for layer in scene.layers if layer.id in warped.layer_ids))

    def test_deformed_ibeam_uses_its_profile_mesh_and_solver_rotations(self):
        model, result_state, analysis_mesh = _ibeam_model_state_and_mesh()
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=1.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:deformed_ibeam",
        ))
        warped = _deformed_object(scene, "deformed_analysis_mesh_element", visual_state.id)
        asset = _asset(scene, warped.geometry_asset_id)

        self.assertEqual(asset.format, "mesh")
        self.assertEqual(len(asset.generation_config["vertices"]), 24)
        self.assertEqual(len(asset.generation_config["base_vertices"]), 24)
        self.assertEqual(len(asset.generation_config["faces"]), 44)
        start = asset.generation_config["vertices"][:12]
        end = asset.generation_config["vertices"][12:]
        self.assertAlmostEqual(max(vertex[1] for vertex in start) - min(vertex[1] for vertex in start), 0.1)
        self.assertAlmostEqual(max(vertex[2] for vertex in start) - min(vertex[2] for vertex in start), 0.055)
        self.assertAlmostEqual(max(vertex[1] for vertex in end) - min(vertex[1] for vertex in end), 0.055)
        self.assertAlmostEqual(max(vertex[2] for vertex in end) - min(vertex[2] for vertex in end), 0.1)

    def test_deformed_volume_uses_the_solver_surface_mesh(self):
        model, result_state, analysis_mesh = _volume_model_state_and_mesh()
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:deformed_volume",
        ))
        surface = next(obj for obj in scene.objects if obj.kind == "deformed_analysis_mesh_surface")
        asset = _asset(scene, surface.geometry_asset_id)

        self.assertEqual(asset.format, "mesh")
        self.assertEqual(asset.generation_config["source"], "tuba.deformed_analysis_mesh.volume_surface")
        self.assertEqual(asset.generation_config["base_vertices"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(asset.generation_config["vertices"], [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 3.0, 0.0]])
        self.assertFalse(any(obj.metadata.get("element_id") == "VM1" for obj in scene.objects))


    def test_a_finely_meshed_member_is_drawn_as_profiled_spans_through_its_solved_nodes(self):
        model, result_state, analysis_mesh = _rhs_member_state_and_mesh(segments=100)
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:rhs_spans",
        ))
        scene.validate()
        spans = sorted(
            (obj for obj in scene.objects
             if obj.kind == "deformed_analysis_mesh_element" and obj.metadata.get("geometry_state_id") == visual_state.id),
            key=lambda obj: obj.metadata["span_index"],
        )
        assets = [_asset(scene, span.geometry_asset_id) for span in spans]

        self.assertEqual([span.metadata["span_index"] for span in spans], list(range(8)))
        self.assertTrue(all(str(span.entity_ref) == "element:rhs_0" for span in spans))
        self.assertTrue(all(asset.format == "mesh" for asset in assets))
        self.assertTrue(all(asset.generation_config["source"] == "tuba.deformed_analysis_mesh.profile" for asset in assets))
        # Spans walk the member from its n1 end and share their boundary nodes.
        chains = [asset.generation_config["node_ids"] for asset in assets]
        self.assertEqual(chains[0][0], "M0")
        self.assertEqual(chains[-1][-1], "M100")
        self.assertTrue(all(left[-1] == right[0] for left, right in zip(chains, chains[1:])))
        self.assertEqual(sorted(segment for span in spans for segment in span.metadata["element_ids"]),
                         sorted(analysis_mesh.elements))
        for asset in assets:
            config = asset.generation_config
            stations = len(config["section_origins"])
            self.assertLessEqual(stations, 4)
            self.assertEqual(len(config["section_deformations"]), stations)
            self.assertEqual(len(config["vertices"]) % stations, 0)
            # Every ring sits at its own node's solved place: the sag, not a chord.
            ring = len(config["vertices"]) // stations
            for index, origin in enumerate(config["section_origins"]):
                centre = [sum(vertex[axis] for vertex in config["vertices"][index * ring:(index + 1) * ring]) / ring
                          for axis in range(3)]
                self.assertAlmostEqual(centre[2], -10.0 * _sag(origin[0]), places=9)

    def test_a_line_model_member_keeps_one_body_per_segment(self):
        # Sixteen segments: a TUYAU_3M bend, which line-model bundles draw segment by segment.
        model, result_state, analysis_mesh = _rhs_member_state_and_mesh(segments=16)
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model,
            result_states=[result_state],
            geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh],
            scene_id="scene:rhs_segments",
        ))
        warped = [obj for obj in scene.objects if obj.kind == "deformed_analysis_mesh_element"]

        self.assertEqual(sorted(obj.metadata["element_id"] for obj in warped), sorted(analysis_mesh.elements))
        self.assertFalse(any("span_index" in obj.metadata for obj in warped))

    def test_quadratic_pipe_segments_are_walked_in_order_whatever_their_node_order(self):
        model, result_state, _ = _model_state_and_mesh()
        n0, n1 = "N0", "N1"
        nodes = {n0: (0.0, 0.0, 0.0), "P1": (0.25, 0.0, 0.0), "Q1": (0.5, 0.0, 0.0), "P2": (0.75, 0.0, 0.0),
                 n1: (1.0, 0.0, 0.0)}
        # Code_Aster's SEG3 stores (end, end, middle); a mesh importer may not.
        elements = {"T1": ("Q1", n1, "P2"), "T0": (n0, "P1", "Q1")}
        result_state.node_displacements.update({node: (0.0, 0.1, 0.0, 0.0, 0.0, 0.0) for node in ("P1", "Q1", "P2")})
        analysis_mesh = AnalysisMesh(
            id="analysis_mesh:Hot", model_revision=0, solver_name="Code_Aster", nodes=nodes, elements=elements,
            groups={"AllPipes": tuple(elements)}, node_sources={},
            element_sources={element_id: MeshElementSource(element_id=element_id, source_ref=EntityRef("element", "pipe_0"),
                                                           role="native_element") for element_id in elements},
        )
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=10.0)

        scene = build_visualization_scene(SceneRequest(
            model, result_states=[result_state], geometry_states=[visual_state],
            analysis_meshes=[analysis_mesh], scene_id="scene:seg3",
        ))
        spans = sorted((obj for obj in scene.objects if obj.kind == "deformed_analysis_mesh_element"),
                       key=lambda obj: obj.metadata["span_index"])
        assets = [_asset(scene, span.geometry_asset_id) for span in spans]

        self.assertEqual([asset.generation_config["node_ids"] for asset in assets],
                         [[n0, "P1", "Q1"], ["Q1", "P2", n1]])
        self.assertTrue(all(asset.format == "tube" for asset in assets))
        self.assertEqual(assets[0].generation_config["points"], [[0.0, 1.0, 0.0], [0.25, 1.0, 0.0], [0.5, 1.0, 0.0]])
        self.assertEqual([span.metadata["element_ids"] for span in spans], [["T0"], ["T1"]])


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


def _ibeam_model_state_and_mesh():
    model = Model(project_name="DeformedIBeam")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_ibeam_section("IBeamSec", "IPE100")
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="beam_0", type="beam", n1=n0, n2=n1, section="IBeamSec", material="Steel")
    result_state = ResultState(
        id="result_state:Beam",
        study_id="analysis_study:Beam",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Beam",
        mesh_id="analysis_mesh:Beam",
        node_displacements={
            n0: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            n1: (0.0, 0.0, 0.0, math.pi / 2.0, 0.0, 0.0),
        },
        node_reactions={},
        element_results={},
    )
    analysis_mesh = AnalysisMesh(
        id="analysis_mesh:Beam",
        model_revision=0,
        solver_name="Code_Aster",
        nodes={n0: (0.0, 0.0, 0.0), n1: (1.0, 0.0, 0.0)},
        elements={"beam_0": (n0, n1)},
        groups={"G_TUBE": ("beam_0",)},
        node_sources={
            n0: MeshNodeSource(node_id=n0, source_ref=EntityRef("node", n0), role="native_node"),
            n1: MeshNodeSource(node_id=n1, source_ref=EntityRef("node", n1), role="native_node"),
        },
        element_sources={
            "beam_0": MeshElementSource(
                element_id="beam_0",
                source_ref=EntityRef("element", "beam_0"),
                role="native_element",
            ),
        },
        modelisations={"G_TUBE": "POU_D_T"},
    )
    return model, result_state, analysis_mesh


def _volume_model_state_and_mesh():
    model, _, _ = _model_state_and_mesh()
    node_ids = ["VN1", "VN2", "VN3", "VN4"]
    result_state = ResultState(
        id="result_state:Volume",
        study_id="analysis_study:Volume",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Volume",
        mesh_id="analysis_mesh:Volume",
        node_displacements={
            "VN1": (0.0, 0.0, 0.0, None, None, None),
            "VN2": (0.1, 0.0, 0.0, None, None, None),
            "VN3": (0.0, 0.2, 0.0, None, None, None),
            "VN4": (0.0, 0.0, 0.3, None, None, None),
        },
        node_reactions={},
        element_results={},
        metadata={
            "volume_analysis": True,
            "volume_von_mises": {"VN1": 10.0, "VN2": 20.0, "VN3": 30.0},
        },
    )
    analysis_mesh = AnalysisMesh(
        id="analysis_mesh:Volume",
        model_revision=0,
        solver_name="Code_Aster",
        nodes={
            "VN1": (0.0, 0.0, 0.0),
            "VN2": (1.0, 0.0, 0.0),
            "VN3": (0.0, 1.0, 0.0),
            "VN4": (0.0, 0.0, 1.0),
        },
        elements={"VM1": tuple(node_ids)},
        groups={"G_SOLID": ("VM1",)},
        node_sources={
            node_id: MeshNodeSource(node_id, EntityRef("element", "pipe_0"), "volume_node")
            for node_id in node_ids
        },
        element_sources={
            "VM1": MeshElementSource("VM1", EntityRef("element", "pipe_0"), "volume_cell")
        },
        surface_mesh={
            "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "faces": [[0, 1, 2]],
            "node_ids": node_ids[:3],
        },
    )
    return model, result_state, analysis_mesh


def _sag(x):
    return 0.01 * math.sin(math.pi * x / 2.0)


def _rhs_member_state_and_mesh(*, segments):
    """One 2 m RHS member meshed the way gmsh hands it over: segments out of order, some reversed."""
    model = Model(project_name="DeformedRHS")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_rectangular_section("RHS", height_y=0.06, height_z=0.06, thickness_y=0.003, thickness_z=0.003)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([2.0, 0.0, 0.0])
    model.add_element(id="rhs_0", type="beam", n1=n0, n2=n1, section="RHS", material="Steel")
    nodes = {f"M{index}": (2.0 * index / segments, 0.0, 0.0) for index in range(segments + 1)}
    order = sorted(range(segments), key=lambda index: (index * 7) % segments)
    elements = {
        f"S{index}": (f"M{index + 1}", f"M{index}") if index % 3 == 0 else (f"M{index}", f"M{index + 1}")
        for index in order
    }
    result_state = ResultState(
        id="result_state:Sag",
        study_id="analysis_study:Sag",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Sag",
        mesh_id="analysis_mesh:Sag",
        node_displacements={
            node: (0.0, 0.0, -_sag(x), 0.0, -0.01 * math.pi / 2.0 * math.cos(math.pi * x / 2.0), 0.0)
            for node, (x, _, _) in nodes.items()
        },
        node_reactions={},
        element_results={},
    )
    analysis_mesh = AnalysisMesh(
        id="analysis_mesh:Sag",
        model_revision=0,
        solver_name="Code_Aster",
        nodes=nodes,
        elements=elements,
        groups={"G_FRAME": tuple(elements)},
        node_sources={},
        element_sources={
            element_id: MeshElementSource(element_id=element_id, source_ref=EntityRef("element", "rhs_0"),
                                          role="straight_segment")
            for element_id in elements
        },
        modelisations={"G_FRAME": "POU_D_T"},
    )
    return model, result_state, analysis_mesh


if __name__ == "__main__":
    unittest.main()
