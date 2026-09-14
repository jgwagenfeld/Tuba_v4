import json
import math
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.model import BendGeometry
from tuba.analysis import AnalysisMesh
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene


def _model() -> Model:
    model = Model(project_name="BendGeometry")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


class TestBendGeometry(unittest.TestCase):
    def test_compatibility_bend_stores_geometry_and_roundtrips(self):
        model = _model()
        with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
            pipe.start([0.0, 0.0, 0.0])
            pipe.bend(radius=1.0, angle=90.0, plane="XY")

        bend = model.elements[0]
        self.assertIsInstance(bend.bend_geometry, BendGeometry)
        self.assertEqual(bend.bend_geometry.generation_mode, "bend")
        self.assertAlmostEqual(bend.bend_geometry.radius, 1.0)
        self.assertAlmostEqual(bend.station_end, math.pi / 2.0)

        restored = Model.from_dict(model.to_dict())
        restored_bend = restored.elements[0]
        self.assertIsInstance(restored_bend.bend_geometry, BendGeometry)
        self.assertEqual(restored_bend.bend_geometry.to_dict(), bend.bend_geometry.to_dict())
        restored.validate()

    def test_pre_bend_geometry_fixture_loads_and_exports(self):
        fixture = json.loads(Path("tests/fixtures/pre_bend_geometry_model.json").read_text(encoding="utf-8"))
        model = Model.from_dict(fixture)
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        self.assertIsNone(bend.bend_geometry)
        model.validate()
        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Hot", tmpdir)

    def test_bend_to_requires_plane_for_ambiguous_180_degree_arc(self):
        model = _model()
        with model.pipe("PipeSec", "Steel") as pipe:
            pipe.start([0.0, 0.0, 0.0])
            with self.assertRaisesRegex(ValueError, "180-degree"):
                pipe.bend_to([2.0, 0.0, 0.0], radius=1.0)

    def test_bend_to_exports_analysis_mesh_with_geometry_metadata(self):
        model = _model()
        with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.bend_to([1.0, 1.0, 0.0], radius=1.0, plane_normal=[0.0, 0.0, 1.0])
            pipe.end(support="anchor")
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        bend = model.elements[0]
        self.assertEqual(bend.bend_geometry.generation_mode, "bend_to")
        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))
        mesh = replace(
            AnalysisMesh.from_dict(manifest["analysis_mesh"]),
            solver_input_identity=None,
        )
        generated = next(source for source in mesh.node_sources.values() if source.role == "generated_bend_node")

        self.assertEqual(generated.metadata["bend_geometry"]["generation_mode"], "bend_to")

        scene = build_visualization_scene(model, analysis_meshes=[mesh])
        bend_object = next(obj for obj in scene.objects if obj.entity_ref and str(obj.entity_ref) == f"element:{bend.id}")
        generated_node = next(obj for obj in scene.objects if obj.kind == "analysis_mesh_node" and obj.metadata["role"] == "generated_bend_node")

        self.assertEqual(bend_object.metadata["bend_geometry"]["generation_mode"], "bend_to")
        self.assertEqual(generated_node.metadata["source_metadata"]["bend_geometry"]["generation_mode"], "bend_to")


if __name__ == "__main__":
    unittest.main()
