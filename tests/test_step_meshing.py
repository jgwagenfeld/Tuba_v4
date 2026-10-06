"""User-facing STEP meshing is real geometry and is independent of solver execution."""

import json
from pathlib import Path

import meshio
import pytest

from examples.code_aster_step_component_review import build_model
from tuba.solver.aster import CodeAsterSolver


def test_automatic_mesh_without_loads_records_resolved_sizes_and_stays_unsolved(tmp_path):
    model = build_model(mesh_size="auto", interface_mesh_sizes={"outlet": 0.003})
    model.load_cases.clear()
    mesh = model.mesh(tmp_path / "spool.med")
    assert mesh.solver_input_identity is None
    assert mesh.modelisations == {"G_spool_SOLID": "3D", "G_TUBE": "TUYAU_3M"}
    assert {c.type for c in meshio.read(mesh.files["med"]).cells} == {"tetra10", "triangle6", "line3"}
    receipt = json.loads(Path(mesh.files["mesh_manifest"]).read_text())
    assert receipt["result_status"] == "mesh_only"
    assert receipt["mesh_settings"]["max_element_size"] == pytest.approx(0.005)
    assert receipt["mesh_settings"]["interface_mesh_sizes"] == {"outlet": 0.003}
    assert "line_segments" not in receipt["mesh_settings"]
    assert receipt["analysis_mesh"].get("solver_input_identity") is None
    assert not (tmp_path / "study.rmed").exists()
    with pytest.raises(ValueError, match=".med"):
        model.mesh(tmp_path / "wrong.stl")


@pytest.mark.parametrize("solid_size", [.015, .005])
def test_default_native_line_density_is_independent_of_step_solid_size(tmp_path, solid_size):
    from tuba.meshing.policy import resolve_mesh_policy
    model = build_model(mesh_size=solid_size)
    policy = resolve_mesh_policy(model)
    assert policy.base_size("component:spool") == solid_size
    assert policy.base_size(f"element:{model.elements[0].id}") == .125
    mesh = model.mesh(tmp_path / "default.med")
    assert len(mesh.groups[f"G_LINE_{model.elements[0].id}"]) == 8
    model.add_mesh_refinement("line", target=f"element:{model.elements[0].id}", size_m=.0625)
    refined = model.mesh(tmp_path / "refined.med")
    assert len(refined.groups[f"G_LINE_{model.elements[0].id}"]) == 16
    assert len(refined.groups["G_spool_SOLID"]) == len(mesh.groups["G_spool_SOLID"])


def test_explicit_native_line_subdivision_is_preserved(tmp_path):
    model = build_model(mesh_size=0.015)
    model.load_cases.clear()
    mesh = model.mesh(tmp_path / "preview.med", line_segments=8)
    for element in model.elements:
        assert len(mesh.groups[f"G_LINE_{element.id}"]) == 8
    assert {c.type for c in meshio.read(mesh.files["med"]).cells} == {"tetra10", "triangle6", "line3"}
    assert len(mesh.surface_mesh["faces"]) > 0
    settings = json.loads(Path(mesh.files["mesh_manifest"]).read_text())["mesh_settings"]
    assert settings["line_segments"] == 8
    assert settings["max_element_size"] == .015
    assert mesh.solver_input_identity is None


def test_named_face_refinement_changes_actual_mesh_and_solve_identity(tmp_path):
    model = build_model(mesh_size=0.012)
    coarse = model.mesh(tmp_path / "coarse.med")
    first = CodeAsterSolver().export_mixed_analysis_study(model, "Bending", tmp_path / "first")
    asset = next(iter(model.cad_assets.values()))
    asset.metadata["interface_mesh_sizes"] = {"outlet": 0.003}
    refined = model.mesh(tmp_path / "refined.med")
    assert len(refined.groups["G_spool_outlet"]) > len(coarse.groups["G_spool_outlet"]) * 2
    second = CodeAsterSolver().export_mixed_analysis_study(model, "Bending", tmp_path / "second")
    assert first.solver_input_identity != second.solver_input_identity
    assert second.metadata["mesh_settings"]["interface_mesh_sizes"] == {"outlet": 0.003}
