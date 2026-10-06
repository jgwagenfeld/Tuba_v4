"""Portable STEP import/mesh/API checks; these do not claim solver results."""

from dataclasses import replace
import ast
import json
import math
from pathlib import Path
import re

import meshio
import numpy as np
import pytest

from tests.test_code_aster_step_component_reference import build_step_reference
from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.solver.aster_volume_results import parse_volume_result_artifacts
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import SceneRequest, build_visualization_scene


@pytest.mark.parametrize("beam", [False, True])
def test_step_import_exports_named_quadratic_solid_and_actual_line_mesh(tmp_path, beam, monkeypatch):
    monkeypatch.delenv("TUBA_RUN_CODE_ASTER_INTEGRATION", raising=False)
    model, connection, tip = build_step_reference(tmp_path, mesh_size=0.012, beam=beam)
    pressure = 0.0 if beam else 1e6
    model.define_load_case("Applied", gravity=False, pressure=pressure).add_nodal_force(tip, [1000, 0, 0])
    study = CodeAsterSolver().export_mixed_analysis_study(model, "Applied", tmp_path / "study")
    manifest = json.loads(Path(study.input_files["manifest"]).read_text())
    mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    disk_mesh = meshio.read(study.input_files["med"])
    assert {cell.type for cell in disk_mesh.cells} == {"tetra10", "triangle6", "line" if beam else "line3"}
    assert mesh.modelisations == {"G_component_SOLID": "3D", "G_TUBE": "POU_D_T" if beam else "TUYAU_3M"}
    assert len(mesh.groups["G_component_base"]) > 0
    assert len(mesh.groups["G_component_nozzle"]) > 0
    assert len(mesh.groups["G_PRESSURE_component_solid"]) > 0
    assert mesh.groups[f"G_NODE_{connection}"] and mesh.groups[f"G_NODE_{tip}"]
    assert all(len(mesh.elements[element]) == 10 for element in mesh.groups["G_component_SOLID"])
    assert all(len(mesh.elements[element]) == (2 if beam else 3) for element in mesh.groups["G_TUBE"])
    assert mesh.surface_mesh["faces"]
    assert all(mesh.element_sources[element].source_ref.id == "component" for element in mesh.groups["G_component_SOLID"])
    assert model.imported_components["component"].status == "reviewed"
    assert all(port.status == "confirmed" for port in model.ports.values())
    assert all("gmsh_face_tag" not in port.metadata["face_selector"] for port in model.ports.values())
    assert study.metadata["qualification_status"] == "qualified"
    assert study.metadata["result_status"] == "pending_solver"
    assert study.metadata["code_aster_solve_ready"] is True
    assert study.metadata["runtime_blocker"] is None
    assert study.solver_input_identity == mesh.solver_input_identity
    comm = Path(study.input_files["comm"]).read_text()
    assert "MECA_STATIQUE(" in comm and "REAC_NODA" in comm and "EFGE_ELNO" in comm
    assert f"OPTION='{'3D_POU' if beam else '3D_TUYAU'}'" in comm
    assert "DX=0.0, DY=0.0, DZ=0.0" in comm
    assert "FX=1.00000000E+03" in comm
    if pressure:
        assert "PRES_REP=_F(" in comm and "FORCE_TUYAU=_F(" in comm
    assert not (tmp_path / "study" / "study.rmed").exists()
    with pytest.raises(ValueError, match="owning result state"):
        build_visualization_scene(SceneRequest(model, analysis_meshes=[mesh]))
    scene = build_visualization_scene(SceneRequest(model))
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    assert any(obj.kind == "imported_component" for obj in scene.objects)
    assert not any(obj.kind.endswith("stress_field") for obj in scene.objects)
    # A diagnostic mesh preview carries no claim of a solved input identity.
    preview = build_visualization_scene(SceneRequest(model, analysis_meshes=[replace(mesh, solver_input_identity=None)]))
    preview.validate()
    extension = next(obj for obj in preview.objects if str(obj.entity_ref) == "element:extension")
    assert extension.geometry_asset_id is not None, "The STEP skin must not hide its 1D continuation."


def test_step_mm_scale_and_rotated_placement_apply_once_to_ports_and_volume_mesh(tmp_path):
    model, connection, tip = build_step_reference(
        tmp_path, mesh_size=0.012, unit_scale_to_m=0.001,
        placement={"origin": [2, 3, 4], "rotation": [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]})
    model.define_load_case("Placed", gravity=False).add_nodal_force(tip, [0, 1000, 0])
    assert model.ports["component_nozzle"].position == pytest.approx([2, 3.2, 4])
    assert model.ports["component_nozzle"].axis == pytest.approx([0, 1, 0])
    assert model.ports["component_nozzle"].radius == pytest.approx(0.05)
    assert model.ports["component_nozzle"].metadata["face_selector"]["position"] == pytest.approx([200, 0, 0])
    assert model.nodes[connection].coords == pytest.approx([2, 3.2, 4])
    study = CodeAsterSolver().export_mixed_analysis_study(model, "Placed", tmp_path / "study")
    mesh = AnalysisMesh.from_dict(json.loads(Path(study.input_files["manifest"]).read_text())["analysis_mesh"])
    component_nodes = {node for element in mesh.groups["G_component_SOLID"] for node in mesh.elements[element]}
    points = np.asarray([mesh.nodes[node] for node in component_nodes])
    assert points.min(axis=0) == pytest.approx([1.95, 3, 3.95], abs=0.002)
    assert points.max(axis=0) == pytest.approx([2.05, 3.2, 4.05], abs=0.002)
    assert mesh.nodes[mesh.groups[f"G_NODE_{tip}"][0]] == pytest.approx([2, 4.2, 4])


def test_step_solve_dispatch_preserves_solid_and_line_only_export_fails(tmp_path, monkeypatch):
    model, _connection, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Applied", gravity=False).add_nodal_force(tip, [1000, 0, 0])
    calls = []

    def solve_mixed(self, selected_model, load_case, **options):
        calls.append((selected_model, load_case, options))
        return "selected mixed study"

    monkeypatch.setattr(CodeAsterSolver, "solve_mixed_study", solve_mixed)
    assert model.solve("Applied", max_element_size=0.01) == "selected mixed study"
    assert CodeAsterSolver().solve(model, "Applied") == "selected mixed study"
    assert len(calls) == 2 and all(selected is model for selected, _, _ in calls)
    assert calls[0][2]["max_element_size"] == 0.01
    for export_method in ("export_study", "export_analysis_study"):
        with pytest.raises(ValueError, match="Imported solids require"):
            getattr(CodeAsterSolver(), export_method)(model, "Applied", tmp_path / export_method)
        assert not (tmp_path / export_method).exists()


def test_reference_only_model_cannot_silently_use_line_solver(tmp_path):
    model = Model("Reference-only unsupported study")
    reference = model.add_reference_point("reference", position=[0, 0, 0])
    model.add_support(reference, "anchor")
    model.define_load_case("Applied", gravity=False)
    solver = CodeAsterSolver(work_dir=tmp_path / "study")
    with pytest.raises(ValueError, match="reference carriers"):
        solver.analysis_study_inputs(model, "Applied")
    with pytest.raises(ValueError, match="explicit solid_3d or shell_2d"):
        model.solve("Applied", work_dir=tmp_path / "study")
    with pytest.raises(ValueError, match="explicit solid_3d or shell_2d"):
        solver.solve(model, "Applied")
    assert not (tmp_path / "study" / "study.med").exists()


def test_mixed_attachment_cannot_silently_discard_imposed_movement():
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    model = Model("Unsupported relative support movement")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                          thickness=0.01, material="Steel")
    base = model.add_reference_point("base", position=[0, 0, 0])
    tip = model.add_reference_point("tip", position=[1, 0, 0])
    model.add_support(base, "anchor")
    model.add_support(tip, "custom", attached_to=base, blocked_dof=[1, 1, 1, 1, 1, 1],
                      imposed_displacement=[0.08, 0, 0])
    model.define_load_case("Applied", gravity=False)
    with pytest.raises(ValueError, match="cannot impose a displacement"):
        MixedCodeAsterStudyExporter().step_study_inputs(model, "Applied")


@pytest.mark.parametrize("fault", ["changed_source", "missing_pressure_surface", "offset", "wrong_modelization"])
def test_invalid_step_study_fails_before_writing_mesh(tmp_path, fault):
    model, connection, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Applied", gravity=False, pressure=1e6).add_nodal_force(tip, [1000, 0, 0])
    if fault == "changed_source":
        source = Path(model.cad_assets["component_asset"].source_path)
        source.write_text(source.read_text() + "\nchanged\n")
        message = "source changed"
    elif fault == "missing_pressure_surface":
        region = model.analysis_regions["component_solid"]
        model.analysis_regions[region.id] = replace(region, metadata={**region.metadata, "pressure_surfaces": []})
        message = "pressure requires explicit"
    elif fault == "offset":
        model.nodes[connection].coords += np.asarray([0, 0.001, 0])
        message = "coincide"
    else:
        coupling = next(iter(model.couplings.values()))
        model.couplings[coupling.id] = replace(coupling, code_aster_option="3D_POU")
        message = "coupling|3D_TUYAU"
    with pytest.raises(ValueError, match=message):
        CodeAsterSolver().export_mixed_analysis_study(model, "Applied", tmp_path / "failed")
    assert not (tmp_path / "failed" / "study.med").exists()


@pytest.mark.parametrize("missing", ["reactions", "forces", "rotations", "reaction_moments"])
def test_step_parser_rejects_incomplete_result_tables(tmp_path, missing):
    """Deterministic parser fixture only; never published as solver evidence."""
    model = Model("Parser fixture")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n1, n2 = model.add_node([0.2, 0, 0]), model.add_node([1.2, 0, 0])
    model.add_element(id="extension", type="pipe_straight", n1=n1, n2=n2, section="Pipe", material="Steel")
    if missing == "reaction_moments":
        model.add_support(n2, "anchor")
    mesh = AnalysisMesh(
        id="parser_fixture", model_revision=0, solver_name="Code_Aster",
        nodes={"VN1": (0, 0.05, 0), "VN2": (0, -0.05, 0), "VN3": (0, 0, 0.05),
               "VN4": (0.2, 0, 0), "VN5": (1.2, 0, 0)},
        elements={"VS1": ("VN1", "VN2", "VN3"), "VM2": ("VN1", "VN2", "VN3", "VN4"), "LM3": ("VN4", "VN5")},
        groups={"base": ("VS1",), f"G_NODE_{n2}": ("VN5",)},
        node_sources={"VN4": MeshNodeSource("VN4", f"node:{n1}", "native_node"),
                      "VN5": MeshNodeSource("VN5", f"node:{n2}", "native_node")},
        element_sources={"VM2": MeshElementSource("VM2", "element:extension", "volume_cell"),
                         "LM3": MeshElementSource("LM3", "element:extension", "native_element")},
        surface_mesh={"vertices": [(0, 0.05, 0), (0, -0.05, 0), (0, 0, 0.05)],
                      "faces": [(0, 1, 2)], "node_ids": ["VN1", "VN2", "VN3"]})
    study = AnalysisStudy(id="parser_fixture", model_revision=0, solver_name="Code_Aster",
                          load_case="Fixture", work_dir=str(tmp_path), input_files={}, mesh_id=mesh.id,
                          metadata={"step_component_analysis": True, "mixed_analysis": True,
                                    "fixed_face_groups": ["base"],
                                    "compiler_inputs": {"element_ids": [], "line_element_ids": ["extension"]}})
    header = "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
    displacements = [f"{i},0,0,0,0,0,0" for i in range(1, 6)]
    if missing == "rotations":
        displacements[3] = "4,0,0,0,-,-,-"
    (tmp_path / "study_depl.csv").write_text(header + "\n".join(displacements))
    reactions = [] if missing == "reactions" else [f"{i},0,0,0,0,0,0" for i in range(1, 4)]
    if missing == "reaction_moments":
        reactions.append("5,0,0,0,-,-,-")
    (tmp_path / "study_reac.csv").write_text(header + "\n".join(reactions))
    (tmp_path / "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n2,1,10\n2,2,10\n2,3,10\n")
    (tmp_path / "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n")
    message = {"reactions": "missing reactions", "forces": "missing pipe/beam endpoint forces",
               "rotations": "component DRX", "reaction_moments": "component DRX"}[missing]
    with pytest.raises(RuntimeError, match=message):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


@pytest.mark.parametrize("options", [{"pipe_modelization": "POU_D_T"}, {"line_segments": 3},
                                    {"load_path": ["Applied"]}, {"load_step": 0.2}])
def test_direct_step_solver_rejects_unsupported_line_and_history_options(tmp_path, options):
    model, _connection, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Applied", gravity=False).add_nodal_force(tip, [1000, 0, 0])
    root = tmp_path / "unsupported"
    with pytest.raises(ValueError, match="STEP|Imported|imported|line_segments"):
        CodeAsterSolver(work_dir=root, **options).solve_mixed_study(model, "Applied")
    assert not (root / "study.med").exists()


def test_model_step_solve_rejects_ignored_line_subdivision_option(tmp_path):
    model, _connection, tip = build_step_reference(tmp_path, mesh_size=0.012)
    model.define_load_case("Applied", gravity=False).add_nodal_force(tip, [1000, 0, 0])
    root = tmp_path / "unsupported"
    with pytest.raises(ValueError, match="STEP|Imported|imported|line_segments"):
        model.solve("Applied", work_dir=root, line_segments=3)
    assert not (root / "study.med").exists()


@pytest.mark.parametrize(("placement", "expected_y"), [
    (None, [0, 1, 0]),
    ({"origin": [0, 0, 0], "rotation": [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]}, [-1, 0, 0]),
])
def test_rectangular_step_beam_section_uses_the_displayed_local_y_axis(tmp_path, placement, expected_y):
    model, _connection, tip = build_step_reference(tmp_path, mesh_size=0.012, beam=True, placement=placement)
    model.add_rectangular_section("Rectangle", height_y=0.04, height_z=0.02)
    model.get_element("extension").section = "Rectangle"
    model.define_load_case("Beam", gravity=False).add_nodal_force(tip, [0, 0, 100])
    study = CodeAsterSolver().export_mixed_analysis_study(model, "Beam", tmp_path / "study")
    comm = Path(study.input_files["comm"]).read_text()
    assert "SECTION='RECTANGLE'" in comm
    assert "CARA=('HY', 'HZ')" in comm and "VALE=(0.04, 0.02)" in comm
    vector = re.search(r"CARA='VECT_Y', VALE=(\([^)]*\))", comm)
    assert vector is not None
    assert ast.literal_eval(vector[1]) == pytest.approx(expected_y, abs=1e-12)
