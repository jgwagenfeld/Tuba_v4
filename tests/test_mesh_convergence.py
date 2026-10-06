"""Portable contracts only; replay fixtures are not native solver evidence."""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path

import pytest

from tuba import Model
from tuba.meshing.policy import resolve_mesh_policy
from tuba.analysis.mesh_convergence import compare_measurements, mesh_topology, validate_convergence_settings
from tuba.project.study import study_settings


@pytest.mark.parametrize("factor", [0, -1, True, float("nan"), float("inf")])
def test_factor_is_positive_finite_dimensionless(factor):
    with pytest.raises(ValueError, match="dimensionless"):
        model().set_mesh_size_factor(factor)


@pytest.mark.parametrize("factor", [.5, 2.])
def test_volume_factor_applies_once_to_automatic_global_and_override(tmp_path, monkeypatch, factor):
    from tests.test_pipe_volume_mesh import _straight_pipe_model
    from tuba.solver.aster import CodeAsterSolver
    from tuba.meshing import pipe_volume
    m, *_ = _straight_pipe_model()
    m.define_load_case("case", gravity=False)
    ids = [e.id for e in m.elements]
    m.set_mesh_size_factor(factor)
    sizes = []
    def capture(geometry, size, order):
        sizes.append(size)
        raise RuntimeError("captured effective native size")
    monkeypatch.setattr(pipe_volume, "_require_mesh_settings", capture)
    for authored, override, expected in [(None,None,.005), (.004,None,.004), (.004,.003,.003)]:
        if authored:
            m.set_mesh_size(authored)
        solver = CodeAsterSolver()
        inputs = solver.volume_study_inputs(m, "case", element_ids=ids, max_element_size=override)
        assert inputs.compiler_inputs["max_element_size"] == pytest.approx(expected*factor)
        with pytest.raises(RuntimeError, match="captured"):
            solver.export_volume_study(m,"case",tmp_path / str(expected),element_ids=ids,max_element_size=override)
        assert sizes[-1] == pytest.approx(expected*factor)


def test_factor_script_roundtrip_and_compiler_identity():
    from tuba.project.script import generate_model_script
    from tuba.solver.aster import CodeAsterSolver
    m = model()
    baseline = CodeAsterSolver().analysis_study_inputs(m,"load").solver_input_identity
    m.set_mesh_size_factor(.5)
    namespace = {}
    exec(generate_model_script(m),namespace)
    assert namespace["model"].to_dict() == m.to_dict()
    assert CodeAsterSolver().analysis_study_inputs(m,"load").solver_input_identity != baseline


@pytest.mark.parametrize("factor", [.5, 2.])
def test_mixed_compiler_reports_effective_region_sizes(factor):
    from examples.code_aster_step_component_review import build_model
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    m=build_model(mesh_size=.012)
    m.set_mesh_size(.006,region="spool_solid")
    m.set_mesh_size_factor(factor)
    inputs=MixedCodeAsterStudyExporter().step_study_inputs(m,"Bending")
    assert inputs.compiler_inputs["region_mesh_sizes"]["spool_solid"]==pytest.approx(.006*factor)
    assert inputs.compiler_inputs["max_element_size"]==pytest.approx(.006*factor)


def replay(monkeypatch, *, unchanged=False, fail=False, wrong_case=False, missing=False, displacements=None):
    """Explicit portable replay; synthetic values/attestations never solver proof."""
    import numpy as np
    import tuba.analysis.mesh_convergence as module
    from tuba.analysis.provenance import build_solver_input_identity
    from tuba.solver.base import FEAResults, NodeResult
    owners = {}
    class Replay:
        def __init__(self, work_dir, **kwargs):
            self.directory = str(work_dir)
        def solve(self, m, case):
            if fail and self.directory.endswith("01"):
                raise RuntimeError("replay failure")
            owners[self.directory] = (deepcopy(m.to_dict()),case)
    def imported(*, model, work_dir):
        data,case = owners[str(work_dir)]
        assert model.to_dict() == data
        results = FEAResults("Code_Aster", case)
        if not missing:
            factor=model.mesh_settings["size_factor"]
            displacement=displacements[factor] if displacements is not None else 1/factor
            results.analysis_node_results = {"fe":NodeResult("fe",np.array([displacement,0,0,0,0,0]))}
        def validate(m):
            assert m.to_dict() == data
        return SimpleNamespace(study=SimpleNamespace(load_case="other" if wrong_case else case,
                solver_input_identity=build_solver_input_identity(model,case)),results=results,
                result_state=SimpleNamespace(metadata={"solve_attestation":{"fixture":"portable replay only","artifacts":{}}}),
                validate_for_publication=validate)
    monkeypatch.setattr("tuba.solver.aster.CodeAsterSolver",Replay)
    monkeypatch.setattr("tuba.analysis.code_aster_artifacts.import_code_aster_artifacts",imported)
    monkeypatch.setattr(module,"actual_mesh",lambda directory,attestation: {"signature":"same" if unchanged else str(directory),"node_count":2,"cell_count":1,"by_family":{"SEG2":1}})
    return module


def portable_execution_fixture(monkeypatch):
    """Synthetic portable files/receipts only; this never executes Code_Aster."""
    from tests.test_solver_input_provenance import _fake_solved_artifacts
    from tuba.solver.aster import CodeAsterSolver
    from tuba.solver.code_aster_runtime import CodeAsterExecution, CodeAsterRuntimeCandidate
    def execute(self,directory):
        from tuba.visualization.preview.mesh import read_native_line_mail
        _fake_solved_artifacts(Path(directory))
        nodes,cells=read_native_line_mail(Path(directory) / "study.mail")
        (Path(directory) / "study_depl.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"+
            "".join(f"{node},.001,0,0,0,0,0\n" for node in nodes))
        (Path(directory) / "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"+
            "".join(f"{cell},{node},1,0,0,0,0,0\n" for cell,connectivity in cells.items() for node in connectivity[:2]))
        return CodeAsterExecution(CodeAsterRuntimeCandidate("wsl",("wsl",)),("wsl",),0,"","")
    monkeypatch.setattr(CodeAsterSolver,"_execute",execute)


def test_attested_mail_ignores_unrelated_med_in_execution_reopen_and_cache(tmp_path,monkeypatch):
    import json
    import meshio
    from tuba.analysis.mesh_convergence import run_mesh_convergence,reopen_mesh_convergence
    from tuba.visualization.preview.mesh import MeshJobManager
    portable_execution_fixture(monkeypatch)
    m=model()
    m.set_mesh_size(.1)
    for index in range(2):
        directory=tmp_path / f"level-{index:02d}"
        directory.mkdir()
        meshio.write(directory / "study.med",meshio.Mesh([[0,0,0],[1,0,0],[0,1,0]],[("triangle",[[0,1,2]])]))
    report=run_mesh_convergence(m,"load",scales=[1,.5],output_dir=tmp_path)
    assert "SEG3" in report["levels"][0]["mesh"]["by_family"]
    assert report["status"]=="completed"
    assert all("study.mail" in level["attestation"]["artifacts"] and "study.med" not in level["attestation"]["artifacts"] for level in report["levels"])
    assert reopen_mesh_convergence(m,tmp_path)==report
    host=SimpleNamespace(model=m,out_dir=tmp_path / "studio")
    job={"mode":"convergence","directory":str(tmp_path)}
    manager=MeshJobManager(host)
    assert manager._validate_current(job,"fixture-source")==report
    (tmp_path / "level-00" / "study.med").write_bytes(b"unattested alternative changed")
    assert manager._validate_current(job,"fixture-source")==report # byte-verified cached reuse
    assert MeshJobManager(host)._validate_current(job,"fixture-source")==report # fresh verified import
    incomplete=deepcopy(report)
    incomplete["levels"][0]["attestation"]["artifacts"].pop("study.mail")
    (tmp_path / "comparison.json").write_text(json.dumps(incomplete))
    with pytest.raises(ValueError,match="cache inventory"):
        manager._validate_current(job,"fixture-source")
    (tmp_path / "comparison.json").write_text(json.dumps(report))
    mail=tmp_path / "level-00" / "study.mail"
    mail.write_bytes(mail.read_bytes()+b"corrupt attested mesh")
    with pytest.raises(ValueError,match="attestation"):
        manager._validate_current(job,"fixture-source")


def test_duplicate_adjacent_actual_mesh_has_explicit_no_verdict(tmp_path,monkeypatch):
    module=replay(monkeypatch,displacements={1.:1.,.5:1.02,.25:1.02})
    monkeypatch.setattr(module,"actual_mesh",lambda directory,attestation: {"signature":"A" if str(directory).endswith("00") else "B","node_count":2,"cell_count":1,"by_family":{"SEG2":1}})
    report=module.run_mesh_convergence(model(),"load",scales=[1,.5,.25],output_dir=tmp_path)
    assert report["status"]=="completed" and report["distinct_successful_meshes"]==2
    assert report["levels"][1]["changes_from_previous"][0]["relative_change"]==pytest.approx(.02)
    duplicate=report["levels"][2]["changes_from_previous"][0]
    assert duplicate["absolute_change"] is None
    assert duplicate["relative_change"] is None
    assert duplicate["within_tolerance"] is None
    assert "Actual mesh unchanged" in duplicate["reason"]
    assert report["all_available_changes_within_tolerance"] is True # only the distinct A->B pair


@pytest.mark.parametrize("artifacts",[{}, {"study.mail":{},"study.med":{}}])
def test_topology_requires_unambiguous_attested_mesh_selection(tmp_path,artifacts):
    from tuba.analysis.mesh_convergence import actual_mesh
    with pytest.raises(ValueError,match="exactly one attested"):
        actual_mesh(tmp_path,{"artifacts":artifacts})


@pytest.mark.parametrize("scenario", ["success", "unchanged", "fail", "wrong_case", "missing"])
def test_report_replays_failures_distinctness_missing_fields_and_source_ownership(tmp_path,monkeypatch,scenario):
    module = replay(monkeypatch,**({scenario:True} if scenario != "success" else {}))
    m = model()
    before = deepcopy(m.to_dict())
    report = module.run_mesh_convergence(m,"load",scales=[1,.5],output_dir=tmp_path)
    assert m.to_dict() == before
    assert report["status"] == ("failed" if scenario in {"unchanged","fail","wrong_case"} else "completed")
    if scenario == "missing":
        assert report["all_available_changes_within_tolerance"] is None
        assert all(metric["value"] is None for metric in report["levels"][0]["measurements"])
    elif scenario == "success":
        assert report["all_available_changes_within_tolerance"] is False
        assert report["levels"][1]["changes_from_previous"][0]["relative_change"] == 1.
        assert all(metric["value"] is None for metric in report["levels"][0]["measurements"][1:])
    elif scenario in {"fail","wrong_case"}:
        assert any(level["status"] == "failed" for level in report["levels"])


def test_source_edit_and_explicit_segmentation_are_actionable(tmp_path,monkeypatch):
    module = replay(monkeypatch)
    m = model()
    with pytest.raises(ValueError,match="line_segments"):
        module.run_mesh_convergence(m,"load",scales=[1,.5],output_dir=tmp_path,solver_options={"line_segments":4})
    with pytest.raises(ValueError,match="Source model changed"):
        module.run_mesh_convergence(m,"load",scales=[1,.5],output_dir=tmp_path,
            progress=lambda report:m.set_mesh_size(.05))


def test_cancellation_between_levels_persists_terminal_partial_report(tmp_path,monkeypatch):
    import json
    from tuba.solver.code_aster_process import WslExecutionController, SolverCancelled
    module=replay(monkeypatch)
    controller=WslExecutionController(tmp_path)
    def progress(report):
        if report["levels"][-1]["status"]=="succeeded":
            controller.cancel()
    with pytest.raises(SolverCancelled):
        module.run_mesh_convergence(model(),"load",scales=[1,.5],output_dir=tmp_path,
            execution_controller=controller,progress=progress)
    saved=json.loads((tmp_path / "comparison.json").read_text())
    assert saved["status"]=="cancelled"
    assert len(saved["levels"])==1
    assert not (tmp_path / "level-01").exists()


def model():
    m = Model("Convergence")
    m.add_material("steel", E=2e11, nu=.3)
    m.add_pipe_section("pipe", OD=.1, WT=.01)
    with m.pipe(section="pipe", material="steel") as b:
        b.start([0, 0, 0])
        b.run(.1)
        b.run(.3)
    m.define_load_case("load", gravity=False)
    return m


def test_relative_change_near_zero_is_explicit():
    change = compare_measurements(0.0, 1e-8, .05)
    assert change == {"absolute_change": 1e-8, "relative_change": None, "within_tolerance": None,
                      "reason": "Previous value is near zero; relative change is undefined."}
    assert compare_measurements(None, 1.0, .05)["within_tolerance"] is None
    assert compare_measurements(10., 10.2, .05)["within_tolerance"]


@pytest.mark.parametrize("scales", [[], [1], [1, 1], [1, 0], [1, float("nan")], [True, .5]])
def test_invalid_scales(scales):
    with pytest.raises(ValueError):
        validate_convergence_settings({"scales": scales})


def test_scaling_keeps_narrow_plateau_and_implicit_source_transitions():
    m = model()
    m.set_mesh_size(.1)
    m.add_mesh_refinement("narrow", target={"kind": "box", "min_m": [0, .004975, 0], "max_m": [.1, .1, .1]},
                          size_m=.001, influence_distance_m=.00498, transition_distance_m=5e-7)
    before = deepcopy(m.to_dict())
    baseline = resolve_mesh_policy(m)
    m.set_mesh_size_factor(.5)
    half = resolve_mesh_policy(m)
    assert half.size_at([.05, 0, 0]) == pytest.approx(.0005)
    assert half.to_dict()["refinements"][0]["geometry"] == baseline.to_dict()["refinements"][0]["geometry"]
    assert half.to_dict()["refinements"][0]["transition_distance_m"] == 5e-7
    assert m.mesh_refinements == before["mesh_refinements"]
    auto = model()
    auto.add_mesh_refinement("implicit", target={"kind": "sphere", "center_m": [0, 0, 0], "radius_m": .001}, size_m=.001)
    base = resolve_mesh_policy(auto)
    auto.set_mesh_size_factor(.5)
    scaled = resolve_mesh_policy(auto)
    assert base.to_dict()["refinements"][0]["transition_distances_m"] == scaled.to_dict()["refinements"][0]["transition_distances_m"]
    for e in auto.elements:
        ref = f"element:{e.id}"
        for point in ([.02, 0, 0], [.1, 0, 0]):
            assert scaled.size_at(point, source_ref=ref) == pytest.approx(.5 * base.size_at(point, source_ref=ref))
    assert resolve_mesh_policy(Model.from_dict(auto.to_dict())).to_dict() == scaled.to_dict()


def test_optional_volume_size_and_convergence_study_settings():
    settings = study_settings(SimpleNamespace(LOAD_CASES=["load"], VOLUME_EXPORT={"element_ids": ["pipe_0"]},
        MESH_CONVERGENCE={"scales": [1, .5]}))
    assert settings.volume_export["max_element_size"] is None
    assert settings.mesh_convergence == {"scales": [1., .5], "relative_tolerance": .05}


def test_actual_topology_ignores_ids_preserves_connectivity_midsides_and_coincidence():
    nodes = {"a": (0., 0., 0.), "b": (1., 0., 0.), "c": (.5, 0., 0.), "d": (.5, 0., 0.)}
    first = mesh_topology(nodes, [("SEG3", ("a", "b", "c")), ("SEG3", ("a", "b", "d"))])
    renumber = mesh_topology({"3": nodes["d"], "2": nodes["a"], "1": nodes["c"], "0": nodes["b"]},
                            [("SEG3", ("2", "0", "3")), ("SEG3", ("2", "0", "1"))])
    assert first == renumber
    shared = mesh_topology(nodes, [("SEG3", ("a", "b", "c")), ("SEG3", ("a", "b", "c"))])
    assert first["signature"] != shared["signature"]
