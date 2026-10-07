import importlib.util
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.model import OperationField
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


def write_box_step(path: Path) -> None:
    import gmsh

    gmsh.initialize()
    try:
        gmsh.model.add("box_step_fixture")
        gmsh.model.occ.addBox(0.95, -0.05, -0.05, 0.1, 0.1, 0.1)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()


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
        self.assertIsNone(loaded_study.work_dir)
        self.assertEqual(
            set(loaded_study.input_files.values()),
            {"study.med", "study.comm", "study.export", "study_manifest.json", "study_tuba_fem.json"},
        )
        self.assertEqual(mesh.files, {"med": "study.med"})
        self.assertIn("FORMAT='MED'", comm)
        self.assertIn("MODELISATION='TUYAU_3M'", comm)
        self.assertIn("MODELISATION='3D'", comm)
        self.assertIn("OPTION='3D_TUYAU'", comm)
        self.assertIn("G_PORT_FACE", comm)
        self.assertEqual(study.metadata["result_status"], "export_only")
        self.assertEqual(study.metadata["code_aster_solve_ready"], False)
        self.assertIn("diagnostic handoff", study.metadata["runtime_blocker"])
        self.assertIn("N1", mesh.nodes)
        self.assertEqual(str(mesh.node_sources["N1"].source_ref), "node:N1")
        self.assertEqual(sidecar["mixed_analysis"]["result_status"], "export_only")
        self.assertEqual(sidecar["mixed_analysis"]["code_aster_solve_ready"], False)
        self.assertIn("diagnostic handoff", sidecar["mixed_analysis"]["runtime_blocker"])
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
            write_box_step(step_path)
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

    def test_mixed_sidecar_can_be_read_for_review_diagnostics(self):
        from tuba.solver.mixed_study import load_mixed_sidecar_diagnostics

        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            diagnostics = load_mixed_sidecar_diagnostics(study.input_files["sidecar"])

        self.assertIn("component:component_pump_body", diagnostics["refs"])
        self.assertIn("port:port_pump_nozzle_a", diagnostics["refs"])
        self.assertIn("coupling:coupling_pipe_to_pump_a", diagnostics["refs"])
        self.assertEqual(diagnostics["analysis_mesh_id"], "analysis_mesh:mixed")
        self.assertEqual(diagnostics["lineage"]["G_PORT_FACE"], "port:port_pump_nozzle_a")
        self.assertEqual(diagnostics["result_status"], "export_only")
        self.assertEqual(diagnostics["code_aster_solve_ready"], False)
        self.assertIn("diagnostic handoff", diagnostics["runtime_blocker"])

    def test_mixed_sidecar_diagnostics_rejects_non_mixed_sidecar(self):
        from tuba.solver.mixed_study import load_mixed_sidecar_diagnostics

        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "study_tuba_fem.json"
            sidecar_path.write_text(
                json.dumps({"schema_version": 1, "lineage": {}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "mixed_analysis"):
                load_mixed_sidecar_diagnostics(sidecar_path)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize("beam", [False, True])
def test_reviewed_step_export_has_authoritative_solid_face_and_endpoint_mesh(tmp_path, monkeypatch, beam):
    from test_code_aster_step_component_reference import build_step_reference

    monkeypatch.delenv("TUBA_RUN_CODE_ASTER_INTEGRATION", raising=False)
    model, connection, tip = build_step_reference(tmp_path, mesh_size=0.012, beam=beam)
    model.define_load_case("Force", gravity=False).add_nodal_force(tip, force=[1000, 0, 0])
    study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Force", tmp_path)
    manifest = json.loads(Path(study.input_files["manifest"]).read_text(encoding="utf-8"))
    mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    assert study.metadata["code_aster_solve_ready"]
    assert study.metadata["result_status"] == "pending_solver"
    assert study.metadata["runtime_blocker"] is None
    assert study.metadata["qualification_status"] == "qualified"
    sidecar = json.loads(Path(study.input_files["sidecar"]).read_text(encoding="utf-8"))
    for key in ("code_aster_solve_ready", "result_status", "runtime_blocker", "qualification_status"):
        assert manifest["study"]["metadata"][key] == sidecar["mixed_analysis"][key] == study.metadata[key]
    assert mesh.modelisations == {"G_component_SOLID": "3D", "G_TUBE": "POU_D_T" if beam else "TUYAU_3M"}
    assert all(len(mesh.elements[e]) == 10 for e in mesh.groups["G_component_SOLID"])
    assert all(len(mesh.elements[e]) == (2 if beam else 3) for e in mesh.groups["G_TUBE"])
    assert all(len(mesh.elements[e]) == 6 for e in mesh.groups["G_component_nozzle"])
    assert mesh.groups[f"G_NODE_{connection}"]
    assert mesh.node_sources[mesh.groups[f"G_NODE_{connection}"][0]].source_ref.id == connection
    assert all(mesh.element_sources[e].source_ref.kind == "component" for e in mesh.groups["G_component_SOLID"])
    assert mesh.surface_mesh["node_ids"]
    comm = Path(study.input_files["comm"]).read_text(encoding="utf-8")
    assert f"OPTION='{'3D_POU' if beam else '3D_TUYAU'}'" in comm
    assert "MECA_STATIQUE(" in comm
    assert "study_effo.csv" in Path(study.input_files["export"]).read_text(encoding="utf-8")
    from tuba.solver.code_aster_runtime import expected_code_aster_artifact_files

    assert study.metadata["tensor_stress_exported"] is False
    assert "study_sigm.csv" not in expected_code_aster_artifact_files(study.metadata, compiler_id=study.solver_input_identity.compiler_id)
    # The imported solid remains a component, never a fabricated native element.
    assert study.metadata["compiler_inputs"]["element_ids"] == []


def test_changed_step_source_fails_before_manifest(tmp_path):
    from test_code_aster_step_component_reference import build_step_reference

    model, _, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Force", gravity=False).add_nodal_force(tip, force=[1000, 0, 0])
    source = Path(next(iter(model.cad_assets.values())).source_path)
    source.write_text(source.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since import"):
        MixedCodeAsterStudyExporter().export_analysis_study(model, "Force", tmp_path)
    assert not (tmp_path / "study_manifest.json").exists()


@pytest.mark.parametrize("fault", ["placement", "port", "group_collision", "face_alias", "fixed_coupled", "decorated_anchor"])
def test_step_geometry_and_boundary_guards(tmp_path, fault):
    from test_code_aster_step_component_reference import build_step_reference

    model, connection, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Force", gravity=False).add_nodal_force(tip, force=[1000, 0, 0])
    if fault == "placement":
        asset = model.cad_assets["component_asset"]
        model.cad_assets[asset.id] = replace(asset, placement={"origin": [0.01, 0, 0], "rotation": [1, 0, 0, 0]})
    elif fault == "port":
        port = model.ports["component_nozzle"]
        model.ports[port.id] = replace(port, position=[0.21, 0, 0])
        model.nodes[connection].coords[0] = 0.21
    elif fault == "group_collision":
        region = model.analysis_regions["component_solid"]
        model.analysis_regions[region.id] = replace(region, mesh_group="G_TUBE")
    elif fault == "face_alias":
        port = model.ports["component_base"]
        model.ports["alias"] = replace(port, id="alias", face_group="G_alias")
    elif fault == "fixed_coupled":
        region = model.analysis_regions["component_solid"]
        model.analysis_regions[region.id] = replace(region, metadata={**region.metadata, "fixed_interfaces": ["component_base", "component_nozzle"]})
    else:
        model.add_support(tip, "anchor", gap=0.001)
    with pytest.raises(ValueError, match="CAD face|collid|alias|fixed and coupled|bilateral masks"):
        MixedCodeAsterStudyExporter().export_analysis_study(model, "Force", tmp_path)
    assert not (tmp_path / "study_manifest.json").exists()


def test_step_source_change_during_meshing_blocks_publication(tmp_path, monkeypatch):
    import tuba.geometry._native_worker as worker
    from test_code_aster_step_component_reference import build_step_reference

    model, _, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Force", gravity=False).add_nodal_force(tip, force=[1000, 0, 0])
    source = Path(model.cad_assets["component_asset"].source_path)
    original = worker.shutil.copyfile

    def write_and_change_source(*args, **kwargs):
        original(*args, **kwargs)
        source.write_text(source.read_text() + "\n")

    monkeypatch.setattr(worker.shutil, "copyfile", write_and_change_source)
    with pytest.raises(ValueError, match="changed during meshing"):
        MixedCodeAsterStudyExporter().export_analysis_study(model, "Force", tmp_path)
    assert not (tmp_path / "study.med").exists()
    assert not (tmp_path / "study_manifest.json").exists()


def test_step_solid_only_compiler_identity_matches_result_import_contract(tmp_path):
    from test_code_aster_step_component_reference import build_step_reference
    from tuba.solver.compiler_contract import compiler_id_for
    from tuba.solver.code_aster_runtime import expected_code_aster_artifact_files

    model, _, _ = build_step_reference(tmp_path, mesh_size=0.012)
    model.elements.clear()
    model.nodes.clear()
    model.couplings.clear()
    model.define_load_case("Gravity", gravity=True)
    study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Gravity", tmp_path)
    assert study.metadata["volume_analysis"] is True
    assert study.metadata["mixed_analysis"] is True
    assert study.metadata["solid_analysis"] is True
    assert study.metadata["shell_analysis"] is False
    assert study.metadata["line_force_exported"] is False
    assert study.solver_input_identity.compiler_id == compiler_id_for(study.metadata)
    assert study.metadata["tensor_stress_exported"] is False
    assert "study_sigm.csv" not in expected_code_aster_artifact_files(study.metadata, compiler_id=study.solver_input_identity.compiler_id)
    assert "study_effo.csv" not in expected_code_aster_artifact_files(study.metadata, compiler_id=study.solver_input_identity.compiler_id)


def test_supported_step_export_is_solve_ready_without_qualification_opt_in(tmp_path, monkeypatch):
    from test_code_aster_step_component_reference import build_step_reference
    from tuba.solver.aster import CodeAsterSolver

    model, _, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Force", gravity=False).add_nodal_force(tip, force=[1000, 0, 0])
    monkeypatch.delenv("TUBA_RUN_CODE_ASTER_INTEGRATION", raising=False)
    study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Force", tmp_path / "automatic")
    assert study.metadata["result_status"] == "pending_solver"
    assert study.metadata["code_aster_solve_ready"]
    assert study.metadata["runtime_blocker"] is None
    assert study.metadata["qualification_status"] == "qualified"
    assert CodeAsterSolver()._require_solve_ready_study(study) is None


@pytest.mark.parametrize("with_solid", [False, True])
def test_extended_pressure_respects_zero_pipe_override_without_legacy_fallback(tmp_path, with_solid):
    from tuba.solver.aster_volume import _write_comm, mixed_load_inputs

    model = build_mixed_fixture()
    case = model.load_cases["Hot"]
    case.fields.append(OperationField("pressure", 0.0, scope="elements", element_ids=["pipe_0"]))
    model.add_support(model.elements[0].n1, type="anchor")
    solid_regions = tuple(model.analysis_regions.values()) if with_solid else ()
    groups = {"G_TUBE": "TUYAU_3M"}
    if with_solid:
        groups["G_PUMP_SOLID"] = "3D"
    names = {name: name for name in [*groups, "G_LINE_pipe_0", "G_PRESSURE",
                                    *(f"G_NODE_{n}" for n in model.nodes)]}
    comm_path = tmp_path / "zero-pipe-pressure.comm"
    _write_comm(model, comm_path, name_map=names, pressure=case.internal_pressure,
                support_groups=(), couplings=(), line_elements=model.elements,
                nodal_forces=[], node_groups={}, gravity=False, material_name="Steel",
                export_tensor_stress=False, solid_group="G_PUMP_SOLID" if with_solid else None,
                skin_groups_raw=(), pressure_groups_raw=("G_PRESSURE",) if with_solid else (),
                modelisations=groups, solid_regions=solid_regions, load_case=case)
    comm = comm_path.read_text(encoding="utf-8")
    resolved = mixed_load_inputs(model, case, model.elements, solid_regions)
    assert resolved["pipe_pressure"] == {"pipe_0": 0.0}
    assert "FORCE_TUYAU=" not in comm
    assert ("PRES_REP=" in comm) is with_solid
    assert ("CHARGE=PRESSURE" in comm) is with_solid


@pytest.mark.parametrize("with_frame", [False, True])
def test_shell_internal_pressure_without_solid_or_pipe_is_rejected_before_meshing(with_frame):
    model = Model("ShellPressure")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                          thickness=0.01, material="Steel")
    base = model.add_node([0, 0, 0])
    model.add_support(base, type="anchor")
    if with_frame:
        tip = model.add_node([0, 0, 1])
        model.add_rectangular_section("Frame", height_y=0.1, height_z=0.1)
        model.add_element(id="frame", type="beam", n1=base, n2=tip, section="Frame", material="Steel")
    model.define_load_case("Pressure", gravity=False, pressure=1e6)
    with pytest.raises(ValueError, match="shells and frames do not carry internal pressure"):
        MixedCodeAsterStudyExporter().step_study_inputs(model, "Pressure")


@pytest.mark.parametrize("mode", ["shell_line", "shell_shell", "node_override_conflict"])
def test_shared_shell_corner_preserves_distinct_member_temperatures(mode):
    from tuba.solver.aster_volume import mixed_load_inputs

    model = Model("SharedCorner")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                          thickness=0.01, material="Steel")
    corner = model.add_node([0, 0, 0])
    case = model.define_load_case("Thermal", gravity=False, temperature=20)
    case.fields.append(OperationField("temperature", 30, scope="group", group="panel"))
    if mode == "shell_shell":
        model.add_shell_panel("other", polygon=[[0, 0, 0], [0, -1, 0], [1, 0, 0]],
                              thickness=0.01, material="Steel")
    else:
        tip = model.add_node([0, 0, 1])
        model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
        model.add_element(id="pipe", type="pipe_straight", n1=corner, n2=tip, section="Pipe", material="Steel")
        if mode == "shell_line":
            case.fields.append(OperationField("temperature", 25, scope="elements", element_ids=["pipe"]))
        else:
            case.fields.append(OperationField("temperature", 40, scope="nodes", node_ids=[corner]))
    resolved = mixed_load_inputs(model, case, model.elements, tuple(model.analysis_regions.values()))
    assert resolved["region_temperatures"]["G_panel_SHELL"] == 30
    if mode == "shell_shell":
        assert resolved["region_temperatures"]["G_other_SHELL"] == 20
    else:
        assert resolved["line_temperatures"]["pipe"] == (25 if mode == "shell_line" else 20)
        assert resolved["node_temperatures"] == ({corner: 40} if mode == "node_override_conflict" else {})


def test_shared_shell_corner_agrees_with_explicit_line_node_temperature():
    from tuba.solver.aster_volume import mixed_load_inputs

    model = Model("SharedNodeTemperature")
    model.add_material("Steel", E=2e11, nu=0.3)
    panel = model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                                  thickness=0.01, material="Steel")
    corner, tip = model.add_node([0, 0, 0]), model.add_node([0, 0, 1])
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    model.add_element(id="pipe", type="pipe_straight", n1=corner, n2=tip, section="Pipe", material="Steel")
    model.add_support(tip, type="anchor")
    case = model.define_load_case("Thermal", gravity=False, temperature=20)
    case.fields.append(OperationField("temperature", 40, scope="group", group="panel"))
    case.fields.append(OperationField("temperature", 40, scope="nodes", node_ids=[corner]))
    resolved = mixed_load_inputs(model, case, model.elements, (panel,))
    assert resolved["node_temperatures"] == {corner: 40.0}
    assert resolved["region_temperatures"] == {panel.mesh_group: 40.0}
    assert resolved["line_temperatures"] == {"pipe": 20.0}
    inputs = MixedCodeAsterStudyExporter().step_study_inputs(model, "Thermal")
    assert inputs.compiler_inputs["shell_coque_ncou"] == {"panel": 1}


def test_coincident_reference_does_not_create_shared_shell_temperature():
    from tuba.solver.aster_volume import mixed_load_inputs

    model = Model("SeparateReference")
    model.add_material("Steel", E=2e11, nu=0.3)
    panel = model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                                  thickness=0.01, material="Steel")
    reference = model.add_reference_point("ref", position=[0, 0, 0])
    case = model.define_load_case("Thermal", gravity=False, temperature=20)
    case.fields.append(OperationField("temperature", 30, scope="group", group="panel"))
    resolved = mixed_load_inputs(model, case, [], (panel,))
    assert resolved["region_temperatures"] == {panel.mesh_group: 30.0}
    assert reference not in resolved["node_temperatures"]


def test_extended_tuyau_generatrice_has_one_endpoint_seed_per_connected_chain(tmp_path):
    from tuba.solver.aster_volume import _write_comm, mixed_pipe_generatrices

    model = Model("PipeChainSeeds")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    x_nodes = [model.add_node([x, 0, 0]) for x in range(3)]
    z_nodes = [model.add_node([3, 0, z]) for z in range(2)]
    for element_id, n1, n2 in [("x1", x_nodes[1], x_nodes[2]), ("z0", *z_nodes),
                               ("x0", x_nodes[0], x_nodes[1])]:
        model.add_element(id=element_id, type="pipe_straight", n1=n1, n2=n2,
                          section="Pipe", material="Steel")
    panel = model.add_shell_panel("panel", polygon=[[5, 0, 0], [6, 0, 0], [5, 1, 0]],
                                  thickness=0.01, material="Steel")
    model.add_support(x_nodes[0], type="anchor")
    case = model.define_load_case("Cold", gravity=False)
    rows = mixed_pipe_generatrices(model, model.elements)
    assert rows == [
        {"element_ids": ["x0", "x1"], "start_node": x_nodes[0], "vector": [0.0, 0.0, 1.0]},
        {"element_ids": ["z0"], "start_node": z_nodes[0], "vector": [0.0, 1.0, 0.0]},
    ]
    groups = {"G_TUBE": "TUYAU_3M", panel.mesh_group: "DKT"}
    names = {name: name for name in [*groups, *(f"G_LINE_{e.id}" for e in model.elements),
                                    *(f"G_NODE_{n}" for n in model.nodes)]}
    path = tmp_path / "chain-seeds.comm"
    _write_comm(model, path, name_map=names, pressure=0, support_groups=(), couplings=(),
                line_elements=model.elements, nodal_forces=[], node_groups={}, gravity=False,
                material_name="Steel", export_tensor_stress=False, solid_group=None,
                skin_groups_raw=(), pressure_groups_raw=(), modelisations=groups,
                shell_regions=(panel,), load_case=case)
    comm = path.read_text(encoding="utf-8")
    assert comm.count("CARA='GENE_TUYAU'") == 2
    assert f"GROUP_NO='G_NODE_{x_nodes[1]}'" not in comm
    assert f"GROUP_NO='G_NODE_{z_nodes[0]}'" in comm
    assert "COQUE_NCOU=1" in comm


@pytest.mark.parametrize("positions, edges, message", [
    ([[0, 0, 0], [1, 0, 0], [2, 0, 0], [1, 1, 0]], [(0, 1), (1, 2), (1, 3)], "branching"),
    ([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [(0, 1), (2, 1)], "consistent n1-to-n2"),
    ([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [(0, 1), (1, 2), (2, 0)], "without loops"),
    ([[0, 0, 0], [1, 0, 0], [1, 1, 0]], [(0, 1), (1, 2)], "collinear"),
])
def test_unsupported_tuyau_chains_fail_before_meshing(positions, edges, message):
    from tuba.solver.aster_volume import mixed_pipe_generatrices

    model = Model("UnsupportedPipeChain")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    nodes = [model.add_node(position) for position in positions]
    for index, (start, end) in enumerate(edges):
        model.add_element(id=f"pipe{index}", type="pipe_straight", n1=nodes[start], n2=nodes[end],
                          section="Pipe", material="Steel")
    with pytest.raises(ValueError, match=message):
        mixed_pipe_generatrices(model, model.elements)


def test_native_node_rigid_patch_connects_its_frame_without_anchoring_unrelated_frames():
    model = Model("NativePatchFrame")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_rectangular_section("Frame", height_y=0.1, height_z=0.1)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                          thickness=0.01, material="Steel")
    base = model.add_node([0, 0, 0])
    model.add_support(base, type="anchor")
    reference = model.add_reference_point("ref", position=[0.2, 0.2, 0.2])
    root, tip = model.add_node([0.2, 0.2, 0.4]), model.add_node([0.2, 0.2, 1.0])
    model.add_element(id="frame", type="beam", n1=root, n2=tip, section="Frame", material="Steel")
    model.add_rigid_patch("panel_patch", reference=reference, shell="panel", vertices=[0, 1, 2])
    model.add_rigid_patch("frame_patch", reference=reference, nodes=[root])
    model.define_load_case("Cold", gravity=False)
    inputs = MixedCodeAsterStudyExporter().step_study_inputs(model, "Cold")
    assert inputs.compiler_inputs["rigid_patch_groups"] == ["G_panel_patch_PATCH", "G_frame_patch_PATCH"]
    unrelated = [model.add_node([3, 0, z]) for z in (0, 1)]
    model.add_element(id="unrelated", type="beam", n1=unrelated[0], n2=unrelated[1],
                      section="Frame", material="Steel")
    with pytest.raises(ValueError, match="Every native mixed line component must connect"):
        MixedCodeAsterStudyExporter().step_study_inputs(model, "Cold")


def test_nonextended_pipe_volume_preserves_legacy_global_generatrice_emission(tmp_path):
    from tuba.solver.aster_volume import _write_comm

    model = build_mixed_fixture()
    start, end = model.add_node([3, 0, 0]), model.add_node([3, 0, 1])
    model.add_element(id="pipe_1", type="pipe_straight", n1=start, n2=end,
                      section="PipeSec", material="Steel")
    names = {name: name for name in ["G_PUMP_SOLID", "G_TUBE", *(f"G_NODE_{n}" for n in model.nodes)]}
    path = tmp_path / "legacy-global-generatrices.comm"
    _write_comm(model, path, name_map=names, pressure=0, support_groups=(), couplings=(),
                line_elements=model.elements, nodal_forces=[], node_groups={}, gravity=False,
                material_name="Steel", export_tensor_stress=False, solid_group="G_PUMP_SOLID",
                skin_groups_raw=(), pressure_groups_raw=())
    comm = path.read_text(encoding="utf-8")
    assert comm.count("CARA='GENE_TUYAU'") == 2
    assert comm.count("VALE=(0.00000000E+00, 1.00000000E+00, 0.00000000E+00)") == 2
