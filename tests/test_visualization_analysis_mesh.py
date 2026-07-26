import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.refs import EntityRef
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.postprocess import build_segments
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, RouteEndpoint, RoutingConstraints
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene


class TestVisualizationAnalysisMesh(unittest.TestCase):
    def test_build_scene_adds_selectable_analysis_mesh_nodes_and_elements(self):
        model = _model_with_exportable_bend()
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))
        mesh = replace(
            AnalysisMesh.from_dict(manifest["analysis_mesh"]),
            solver_input_identity=None,
        )

        scene = build_visualization_scene(model, analysis_meshes=[mesh], scene_id="scene:analysis_mesh")
        scene.validate()

        node_objects = [obj for obj in scene.objects if obj.kind == "analysis_mesh_node"]
        element_objects = [obj for obj in scene.objects if obj.kind == "analysis_mesh_element"]
        generated_node = next(obj for obj in node_objects if obj.metadata["role"] == "generated_bend_node")
        native_node = next(obj for obj in node_objects if obj.metadata["role"] == "native_node")
        bend_segment = next(obj for obj in element_objects if obj.metadata["role"] == "bend_segment")
        bend_object = next(obj for obj in scene.objects if obj.entity_ref and str(obj.entity_ref) == f"element:{bend.id}")

        self.assertEqual(len(node_objects), len(mesh.nodes))
        self.assertEqual(len(element_objects), len(mesh.elements))
        self.assertEqual(str(native_node.entity_ref), native_node.metadata["source_ref"])
        self.assertTrue(native_node.metadata["source_ref"].startswith("node:"))
        self.assertEqual(str(generated_node.entity_ref), f"element:{bend.id}")
        self.assertEqual(generated_node.metadata["mesh_id"], mesh.id)
        self.assertEqual(generated_node.metadata["source_ref"], f"element:{bend.id}")
        self.assertEqual(generated_node.metadata["source_metadata"]["bend_geometry"]["generation_mode"], "autoroute")
        self.assertEqual(generated_node.metadata["segment_index"], 1)
        self.assertGreater(generated_node.metadata["parametric_t"], 0.0)
        self.assertIn("analysis_mesh:nodes", generated_node.layer_ids)
        self.assertIn("analysis_mesh:generated_bend_nodes", generated_node.layer_ids)
        self.assertEqual(bend_segment.metadata["source_ref"], f"element:{bend.id}")
        self.assertEqual(bend_segment.metadata["source_metadata"]["bend_geometry"]["generation_mode"], "autoroute")
        self.assertIn("PipeElbows", bend_segment.metadata["groups"])
        self.assertEqual(bend_object.metadata["bend_geometry"]["generation_mode"], "autoroute")
        self.assertIn("analysis_mesh:elements", bend_segment.layer_ids)
        self.assertIn("analysis_mesh:groups", bend_segment.layer_ids)
        self.assertIn("analysis_mesh:group:PipeElbows", bend_segment.layer_ids)

        node_asset = next(asset for asset in scene.geometry_assets if asset.id == generated_node.geometry_asset_id)
        element_asset = next(asset for asset in scene.geometry_assets if asset.id == bend_segment.geometry_asset_id)
        self.assertEqual(node_asset.format, "point")
        self.assertEqual(element_asset.format, "polyline")
        self.assertEqual(node_asset.generation_config["source"], "tuba.analysis_mesh.node")
        self.assertEqual(element_asset.generation_config["source"], "tuba.analysis_mesh.element")

    def test_build_scene_reports_analysis_mesh_missing_provenance(self):
        model = Model(project_name="AnalysisMeshDiagnostics")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        mesh = AnalysisMesh(
            id="analysis_mesh:diagnostics",
            model_revision=0,
            solver_name="Code_Aster",
            nodes={n0: (0.0, 0.0, 0.0), n1: (1.0, 0.0, 0.0)},
            elements={elem.id: (n0, n1)},
            groups={"AllPipes": (elem.id,)},
            node_sources={
                n0: MeshNodeSource(node_id=n0, source_ref=EntityRef("node", n0), role="native_node"),
            },
            element_sources={},
        )

        scene = build_visualization_scene(model, analysis_meshes=[mesh], scene_id="scene:analysis_mesh_diagnostics")
        scene.validate()

        diagnostic_codes = {diagnostic.code for diagnostic in scene.diagnostics}
        unmapped_node = next(
            obj for obj in scene.objects if obj.kind == "analysis_mesh_node" and obj.id.endswith(f":node:{n1}")
        )
        unmapped_element = next(
            obj
            for obj in scene.objects
            if obj.kind == "analysis_mesh_element" and obj.id.endswith(f":element:{elem.id}")
        )

        self.assertIn("analysis_mesh.missing_node_source", diagnostic_codes)
        self.assertIn("analysis_mesh.missing_element_source", diagnostic_codes)
        self.assertEqual(unmapped_node.metadata["role"], "unmapped_node")
        self.assertEqual(unmapped_element.metadata["role"], "unmapped_element")


if __name__ == "__main__":
    unittest.main()


def _model_with_exportable_bend() -> Model:
    model = Model(project_name="AnalysisMeshScene")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
        goal=RouteEndpoint(id="B", point=(2.0, 2.0, 0.0)),
        section="PipeSec",
        material="Steel",
        constraints=RoutingConstraints(min_bend_radius=0.5),
    )
    points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
    apply_candidate_to_model(
        model,
        PipeRouteCandidate(
            request_id="P-100",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=4.0,
            cost_breakdown={"length": 4.0, "bends": 1},
        ),
        request,
    )
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
    return model
