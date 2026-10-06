"""STEP freshness/dispatch checks with metadata fixtures; never generate or solve geometry."""

from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh
from tuba.project.freshness import expected_identity, export_study, stale_operations
from tuba.solver.aster import CodeAsterSolver


def _model(tmp_path):
    source = tmp_path / "fixture.step"
    source.write_text("Metadata-only readiness fixture; not executable CAD.", encoding="utf-8")
    model = Model("STEP readiness fixture")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.10, WT=0.01)
    model.add_cad_asset(
        id="asset", source_path=str(source),
        content_digest="sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
        metadata={"analysis_import_version": 1, "mesh_size": "auto",
                  "local_bounds": [0, -0.05, -0.05, 0.2, 0.05, 0.05]},
    )
    model.add_imported_component(id="component", asset="cad_asset:asset", name="Fixture", status="reviewed")
    model.add_analysis_region(
        id="solid", owner="component:component", role="solid_3d", code_aster_modelisation="3D",
        material="Steel", mesh_group="G_SOLID", metadata={"fixed_interfaces": ["base"]},
    )
    for name, position, axis in (("base", [0, 0, 0], [-1, 0, 0]), ("outlet", [0.2, 0, 0], [1, 0, 0])):
        model.add_port(
            id=name, owner="component:component", kind="annular_face", position=position,
            axis=axis, radius=0.05, face_group=f"G_{name}", status="confirmed",
            metadata={"inner_radius_m": 0.04,
                      "face_selector": {"shape": "annular_face", "position": position, "inner_radius": 0.04}},
        )
    n0, n1 = model.add_node([0.2, 0, 0]), model.add_node([1.2, 0, 0])
    model.add_element(id="pipe", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
    model.connect_pipe_to_port(pipe="element:pipe", node=f"node:{n0}", port="port:outlet")
    model.define_load_case("Applied", gravity=False).add_nodal_force(n1, [0, 100, 0])
    return model


def _refuse_mesh(*args, **kwargs):
    raise AssertionError("Readiness/option checks must never generate a mesh.")


def test_step_freshness_and_export_use_the_same_resolved_identity_without_readiness_meshing(tmp_path, monkeypatch):
    import gmsh
    import tuba.meshing.step_component as mesher
    import tuba.solver.aster_volume as volume
    import tuba.solver.mixed_study as mixed

    monkeypatch.setattr(gmsh.model.mesh, "generate", _refuse_mesh)
    monkeypatch.setattr(mesher, "build_step_component_mesh", _refuse_mesh)
    monkeypatch.delenv("TUBA_RUN_CODE_ASTER_INTEGRATION", raising=False)
    model = _model(tmp_path)
    solver = CodeAsterSolver()
    resolved = solver.mixed_study_inputs(model, "Applied")
    identity = expected_identity(model, "Applied")
    assert identity == resolved.solver_input_identity
    assert resolved.compiler_inputs["max_element_size"] == pytest.approx(0.005)
    assert resolved.compiler_inputs["line_modelisation"] == "TUYAU_3M"
    assert not (tmp_path / "study").exists()
    calls = []

    def mesh_double(selected, output, **settings):
        calls.append(settings)
        mesh = AnalysisMesh(id="readiness-test-double", model_revision=0, solver_name="Code_Aster",
                            nodes={}, elements={},
                            node_sources={}, element_sources={},
                            groups={"G_SOLID": (), "G_base": (), "G_outlet": (), "G_TUBE": ()},
                            files={"med": str(output)})
        return SimpleNamespace(analysis_mesh=mesh, groups=mesh.groups, gmsh_version="test-double", settings=settings)

    monkeypatch.setattr(mesher, "build_step_component_mesh", mesh_double)
    monkeypatch.setattr(volume, "_write_comm", lambda *args, **kwargs: None)
    monkeypatch.setattr(volume, "_write_export", lambda *args, **kwargs: None)
    monkeypatch.setattr(mixed, "dump_solver_sidecar", lambda *args, **kwargs: None)
    monkeypatch.setattr(mixed, "dump_study_manifest", lambda *args, **kwargs: None)
    study = export_study(solver, model, "Applied", tmp_path / "study", None)
    assert study.solver_input_identity == identity
    assert study.metadata["compiler_inputs"] == resolved.compiler_inputs
    assert calls[0]["max_element_size"] is None
    assert calls[0]["mesh_policy"].base_size("component:component") == pytest.approx(0.005)
    assert study.metadata["qualification_status"] == "qualified"
    assert study.metadata["result_status"] == "pending_solver"
    assert study.metadata["code_aster_solve_ready"] is True
    assert study.metadata["runtime_blocker"] is None
    # Metadata fixtures check readiness without executing synthetic study inputs.
    assert solver._require_solve_ready_study(study) is None
    dispatched = []
    monkeypatch.setattr(CodeAsterSolver, "solve_mixed_study",
                        lambda self, selected, operation, **options: dispatched.append((selected, operation, options)))
    model.solve("Applied", max_element_size=0.004)
    solver.solve(model, "Applied")
    assert len(dispatched) == 2 and all(selected is model for selected, _, _ in dispatched)
    assert dispatched[0][2]["max_element_size"] == 0.004
    asset = model.cad_assets["asset"]
    asset.metadata["mesh_size"] = 0.002
    finer = expected_identity(model, "Applied")
    assert finer != identity
    assert export_study(solver, model, "Applied", tmp_path / "finer", None).solver_input_identity == finer
    asset.metadata["mesh_size"] = "auto"
    model.get_element("pipe").type = "beam"
    coupling = next(iter(model.couplings.values()))
    model.couplings[coupling.id] = replace(coupling, code_aster_option="3D_POU")
    beam_inputs = solver.mixed_study_inputs(model, "Applied")
    assert beam_inputs.compiler_inputs["line_modelisation"] == "POU_D_T"
    assert export_study(solver, model, "Applied", tmp_path / "beam", None).solver_input_identity == expected_identity(model, "Applied")


@pytest.mark.parametrize("options", [{"pipe_modelization": "POU_D_T"}, {"line_segments": 3},
                                     {"load_path": ["Applied"]}, {"load_step": 0.2}])
def test_step_options_fail_consistently_before_readiness_export_or_solve(tmp_path, monkeypatch, options):
    import gmsh

    monkeypatch.setattr(gmsh.model.mesh, "generate", _refuse_mesh)
    model = _model(tmp_path)
    solver = CodeAsterSolver(**options)
    for call in (
        lambda: solver.mixed_study_inputs(model, "Applied"),
        lambda: solver.export_mixed_analysis_study(model, "Applied", tmp_path / "refused"),
        lambda: solver.solve_mixed_study(model, "Applied"),
        lambda: expected_identity(model, "Applied", solver_options=options),
    ):
        with pytest.raises(ValueError, match="STEP|load paths"):
            call()
    assert not (tmp_path / "refused").exists()


def test_changed_step_source_is_stale_and_native_volume_selection_is_refused(tmp_path, monkeypatch):
    import gmsh

    monkeypatch.setattr(gmsh.model.mesh, "generate", _refuse_mesh)
    model = _model(tmp_path)
    identity = expected_identity(model, "Applied")
    native = {"element_ids": ["pipe"], "max_element_size": 0.002}
    with pytest.raises(ValueError, match="VOLUME_EXPORT"):
        expected_identity(model, "Applied", volume_export=native)
    with pytest.raises(ValueError, match="VOLUME_EXPORT"):
        export_study(CodeAsterSolver(), model, "Applied", tmp_path / "refused", native)
    (tmp_path / "fixture.step").write_text("changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        expected_identity(model, "Applied")
    assert stale_operations(model, [identity], project_root=tmp_path) == ["Applied"]
