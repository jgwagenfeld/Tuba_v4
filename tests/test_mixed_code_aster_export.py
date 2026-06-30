import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.solver.mixed_study import MixedCodeAsterStudyExporter


def build_mixed_fixture() -> Model:
    model = Model(project_name="MixedExport")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
    )
    model.define_load_case(
        "Hot",
        gravity=True,
        pressure=1.0e6,
        temperature=120.0,
        ref_temperature=20.0,
    )
    model.add_cad_asset(
        id="cad_asset_0",
        source_path="equipment.step",
        content_digest="sha256:test",
    )
    model.add_imported_component(
        id="component_pump_body",
        asset="cad_asset:cad_asset_0",
        name="Pump body",
    )
    model.add_analysis_region(
        id="region_pump_solid",
        owner="component:component_pump_body",
        role="solid_3d",
        code_aster_modelisation="3D",
        material="Steel",
        mesh_group="G_PUMP_SOLID",
        element_order=2,
    )
    model.add_port(
        id="port_pump_nozzle_a",
        owner="component:component_pump_body",
        kind="circular_face",
        position=[1.0, 0.0, 0.0],
        axis=[1.0, 0.0, 0.0],
        radius=0.05,
        face_group="G_PORT_FACE",
        edge_group="G_PORT_EDGE",
        status="confirmed",
    )
    model.connect_pipe_to_port(
        pipe="element:pipe_0",
        node="node:N1",
        port="port:port_pump_nozzle_a",
        method="3D_TUYAU",
        id="coupling_pipe_to_pump_a",
    )
    return model


def write_box_step(path: Path) -> bool:
    if importlib.util.find_spec("gmsh") is None:
        return False

    import gmsh

    gmsh.initialize()
    try:
        gmsh.model.add("box_step_fixture")
        gmsh.model.occ.addBox(0.95, -0.05, -0.05, 0.1, 0.1, 0.1)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return True


class TestMixedCodeAsterExport(unittest.TestCase):
    def test_export_writes_med_comm_manifest_and_sidecar(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            manifest = json.loads((root / "study_manifest.json").read_text(encoding="utf-8"))
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        loaded_study = AnalysisStudy.from_dict(manifest["study"])
        mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
        self.assertEqual(loaded_study.id, study.id)
        self.assertIn("FORMAT='MED'", comm)
        self.assertIn("MODELISATION='TUYAU_3M'", comm)
        self.assertIn("MODELISATION='3D'", comm)
        self.assertIn("OPTION='3D_TUYAU'", comm)
        self.assertIn("G_PORT_FACE", comm)
        self.assertIn("N1", mesh.nodes)
        self.assertEqual(str(mesh.node_sources["N1"].source_ref), "node:N1")
        self.assertEqual(sidecar["lineage"]["G_PUMP_SOLID"], "analysis_region:region_pump_solid")
        self.assertEqual(sidecar["lineage"]["G_PORT_FACE"], "port:port_pump_nozzle_a")
        self.assertEqual(
            sidecar["mixed_analysis"]["couplings"]["coupling_pipe_to_pump_a"]["target"],
            "port:port_pump_nozzle_a",
        )

    def test_export_rejects_structural_elements_missing_from_med_mesh(self):
        model = build_mixed_fixture()
        model.add_bar_section("BarSec", OD=0.02, WT=0.0)
        n2 = model.add_node([1.0, 1.0, 0.0])
        model.add_element(
            id="bar_0",
            type="bar",
            n1="N1",
            n2=n2,
            section="BarSec",
            material="Steel",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "mixed MED export does not support"):
                MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            self.assertFalse((Path(tmpdir) / "study_manifest.json").exists())

    def test_export_applies_solver_name_map_to_comm_groups(self):
        model = build_mixed_fixture()
        long_region_group = "G_PUMP_SOLID_WITH_A_NAME_THAT_EXCEEDS_CODE_ASTER_LIMITS"
        long_port_group = "G_PORT_FACE_WITH_A_NAME_THAT_EXCEEDS_CODE_ASTER_LIMITS"
        model.analysis_regions["region_pump_solid"] = model.analysis_regions["region_pump_solid"].__class__(
            **{
                **model.analysis_regions["region_pump_solid"].to_dict(),
                "mesh_group": long_region_group,
            }
        )
        model.ports["port_pump_nozzle_a"] = model.ports["port_pump_nozzle_a"].__class__(
            **{
                **model.ports["port_pump_nozzle_a"].to_dict(),
                "face_group": long_port_group,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        mapped_region = sidecar["name_map"][long_region_group]
        mapped_port = sidecar["name_map"][long_port_group]
        self.assertLessEqual(len(mapped_region), 24)
        self.assertLessEqual(len(mapped_port), 24)
        self.assertIn(mapped_region, comm)
        self.assertIn(mapped_port, comm)
        self.assertNotIn(long_region_group, comm)
        self.assertNotIn(long_port_group, comm)

    def test_export_file_entries_are_study_local(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            export_text = Path(study.input_files["export"]).read_text(encoding="utf-8")

        self.assertIn("F comm study.comm D 1", export_text)
        self.assertIn("F mmed study.med D 20", export_text)
        self.assertNotIn(str(Path(study.work_dir)), export_text)

    def test_med_file_is_nonempty_for_mixed_export(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            except RuntimeError as exc:
                if isinstance(exc.__cause__, ImportError):
                    self.skipTest(str(exc))
                raise
            med_path = Path(study.input_files["med"])
            self.assertEqual(med_path.name, "study.med")
            self.assertTrue(med_path.exists())
            med_size = med_path.stat().st_size

        self.assertGreater(med_size, 0)

    def test_med_writer_failure_blocks_manifest(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MixedCodeAsterStudyExporter()
            exporter._write_med_with_meshio = lambda model, path: (_ for _ in ()).throw(
                RuntimeError("MED writer failed")
            )
            with self.assertRaisesRegex(RuntimeError, "MED writer failed"):
                exporter.export_analysis_study(model, "Hot", tmpdir)
            self.assertFalse((Path(tmpdir) / "study_manifest.json").exists())
            self.assertFalse((Path(tmpdir) / "study_tuba_fem.json").exists())
            self.assertFalse((Path(tmpdir) / "study.comm").exists())

    def test_gmsh_writer_exports_step_volume_when_available(self):
        if importlib.util.find_spec("meshio") is None:
            self.skipTest("meshio is required to inspect mixed MED output.")
        import meshio

        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "box.step"
            if not write_box_step(step_path):
                self.skipTest("gmsh is required for STEP volume MED export.")
            model.cad_assets["cad_asset_0"] = model.cad_assets["cad_asset_0"].__class__(
                **{
                    **model.cad_assets["cad_asset_0"].to_dict(),
                    "source_path": str(step_path),
                    "content_digest": "sha256:box",
                }
            )
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            med_path = Path(study.input_files["med"])
            mesh = meshio.read(med_path)

        volume_cell_types = {
            "tetra",
            "tetra10",
            "hexahedron",
            "hexahedron20",
            "wedge",
            "wedge15",
            "pyramid",
            "pyramid13",
        }
        self.assertTrue(
            any(cell_block.type in volume_cell_types for cell_block in mesh.cells),
            [cell_block.type for cell_block in mesh.cells],
        )

    def test_existing_non_step_asset_uses_meshio_fallback(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "equipment.ifc"
            asset_path.write_text("not a step file", encoding="utf-8")
            model.cad_assets["cad_asset_0"] = model.cad_assets["cad_asset_0"].__class__(
                **{
                    **model.cad_assets["cad_asset_0"].to_dict(),
                    "source_path": str(asset_path),
                    "source_format": "IFC",
                }
            )
            exporter = MixedCodeAsterStudyExporter()
            exporter._write_med_with_gmsh = lambda model, path: (_ for _ in ()).throw(
                RuntimeError("gmsh should not run")
            )
            study = exporter.export_analysis_study(model, "Hot", tmpdir)

            self.assertTrue(Path(study.input_files["med"]).exists())

    def test_code_aster_solver_delegates_mixed_export(self):
        from tuba.solver.aster import CodeAsterSolver

        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_mixed_analysis_study(model, "Hot", tmpdir)
            self.assertTrue(Path(study.input_files["med"]).exists())
            self.assertTrue(Path(study.input_files["comm"]).exists())
            self.assertTrue(Path(study.input_files["sidecar"]).exists())

        self.assertEqual(study.metadata["mixed_analysis"], True)


if __name__ == "__main__":
    unittest.main()
