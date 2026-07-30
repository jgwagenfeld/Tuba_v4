from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import tuba.analysis as analysis
from tuba import Model
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.provenance import MIXED_CODE_ASTER_COMPILER_ID, build_solver_input_identity
from tuba.analysis.results import result_state_from_fea_results
from tuba.plotting.pipeline import build_3d_mesh_from_model
from tuba.reporting import EngineeringReviewError, build_engineering_review
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.visualization import build_visualization_scene


def _operation_model():
    model = Model(project_name="Provenance")
    model.add_material(
        "Steel",
        E=2.0e11,
        nu=0.3,
        allowable_stress={20.0: 120.0e6, 200.0: 100.0e6},
    )
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    element = model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
    )
    operation = model.define_operation("Hot", temperature=200.0, ref_temperature=20.0)
    operation.add_nodal_force(n1, [1000.0, 0.0, 0.0])
    results = FEAResults(solver_name="Code_Aster", load_case="Hot")
    results.node_results[n0] = NodeResult(n0, np.zeros(6))
    results.node_results[n1] = NodeResult(n1, np.zeros(6))
    results.element_results[element.id] = ElementResult(
        element.id,
        np.zeros(6),
        np.zeros(6),
        110.0e6,
        110.0e6,
        110.0e6,
    )
    return model, n1, results


def test_analysis_exposes_solver_input_identity_api():
    assert hasattr(analysis, "build_solver_input_identity")
    assert hasattr(analysis, "validate_solver_input_identity")


def test_operation_results_use_resolved_case_for_web_and_pyvista(tmp_path: Path):
    model, loaded_node, results = _operation_model()
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    state = result_state_from_fea_results(model=model, study=study, results=results)

    scene = build_visualization_scene(model, result_states=[state], solver_results=results)

    stress = next(overlay for overlay in scene.overlays if overlay.data.get("result_type") == "stress")
    temperature = next(overlay for overlay in scene.overlays if overlay.data.get("result_type") == "temperature")
    load = next(overlay for overlay in scene.overlays if overlay.kind == "load_case" and overlay.data["load_case"] == "Hot")
    mesh = build_3d_mesh_from_model(model, results)

    assert stress.data["utilization_values"] == {"object:element:pipe_0": 1.1}
    assert temperature.data["temperature_c"] == 200.0
    assert load.data["nodal_force_count"] == 1
    assert any(obj.metadata.get("node_id") == loaded_node for obj in scene.objects if obj.kind == "applied_load")
    assert np.all(mesh.point_data["TEMP"] == 200.0)


def test_export_persists_same_solver_input_identity_on_study_and_mesh(tmp_path: Path):
    model, _, _ = _operation_model()

    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))

    assert study.solver_input_identity is not None
    assert manifest["study"]["solver_input_identity"] == study.solver_input_identity.to_dict()
    assert manifest["analysis_mesh"]["solver_input_identity"] == study.solver_input_identity.to_dict()


def test_model_mutation_after_export_is_rejected_before_result_conversion(tmp_path: Path):
    model, _, results = _operation_model()
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    model.nodes["N1"].coords[0] = 2.0

    with pytest.raises(ValueError, match="solver input fingerprint"):
        result_state_from_fea_results(model=model, study=study, results=results)


def test_model_mutation_after_export_is_rejected_before_solver_execution(tmp_path: Path, monkeypatch):
    model, _, _ = _operation_model()
    solver = CodeAsterSolver(work_dir=tmp_path)
    study = solver.export_analysis_study(model, "Hot", tmp_path)
    model.nodes["N1"].coords[0] = 2.0
    monkeypatch.setattr(solver, "_execute", lambda _: pytest.fail("stale study reached Code_Aster execution"))

    with pytest.raises(ValueError, match="solver input fingerprint"):
        solver.solve_exported_study(model, study)


def test_stripped_caller_identity_still_validates_exported_manifest_before_execution(tmp_path: Path, monkeypatch):
    model, _, _ = _operation_model()
    solver = CodeAsterSolver(work_dir=tmp_path)
    study = solver.export_analysis_study(model, "Hot", tmp_path)
    legacy_caller = replace(study, solver_input_identity=None)
    model.nodes["N1"].coords[0] = 2.0
    monkeypatch.setattr(solver, "_execute", lambda _: pytest.fail("stale manifest reached Code_Aster execution"))

    with pytest.raises(ValueError, match="solver input fingerprint"):
        solver.solve_exported_study(model, legacy_caller)


def test_mismatched_sidecar_identity_is_rejected_before_execution(tmp_path: Path, monkeypatch):
    model, _, _ = _operation_model()
    model.define_operation("Cold", temperature=20.0)
    solver = CodeAsterSolver(work_dir=tmp_path)
    study = solver.export_analysis_study(model, "Hot", tmp_path)
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["solver_input_identity"] = analysis.build_solver_input_identity(model, "Cold").to_dict()
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(solver, "_execute", lambda _: pytest.fail("mismatched sidecar reached Code_Aster execution"))

    with pytest.raises(ValueError, match="sidecar"):
        solver.solve_exported_study(model, study)


def test_identity_free_sidecar_is_rejected_before_execution(tmp_path: Path, monkeypatch):
    model, _, _ = _operation_model()
    solver = CodeAsterSolver(work_dir=tmp_path)
    study = solver.export_analysis_study(model, "Hot", tmp_path)
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar.pop("solver_input_identity")
    sidecar["name_map"] = {"N0": "STALE_NODE"}
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(solver, "_execute", lambda _: pytest.fail("identity-free sidecar reached execution"))

    with pytest.raises(ValueError, match="sidecar.*solver input identity.*identity-bearing"):
        solver.solve_exported_study(model, study)


def test_study_identity_is_bound_to_its_declared_load_case(tmp_path: Path):
    model, _, results = _operation_model()
    model.define_operation("Cold", temperature=20.0)
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    cold_identity = analysis.build_solver_input_identity(model, "Cold")

    with pytest.raises(ValueError, match="load case"):
        result_state_from_fea_results(
            model=model,
            study=replace(study, solver_input_identity=cold_identity),
            results=results,
        )


def test_standard_study_rejects_mixed_compiler_identity(tmp_path: Path):
    model, _, results = _operation_model()
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    mixed_identity = analysis.build_solver_input_identity(
        model,
        "Hot",
        compiler_id=MIXED_CODE_ASTER_COMPILER_ID,
    )

    with pytest.raises(ValueError, match="compiler"):
        result_state_from_fea_results(
            model=model,
            study=replace(study, solver_input_identity=mixed_identity),
            results=results,
        )


def test_known_mesh_identity_rejects_mutation_when_study_is_legacy(tmp_path: Path):
    model, _, results = _operation_model()
    exported = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))
    mesh = analysis.AnalysisMesh.from_dict(manifest["analysis_mesh"])
    legacy_study = analysis.AnalysisStudy.from_dict(
        {key: value for key, value in exported.to_dict().items() if key != "solver_input_identity"}
    )
    model.nodes["N1"].coords[0] = 2.0

    with pytest.raises(ValueError, match="solver input fingerprint"):
        result_state_from_fea_results(
            model=model,
            study=legacy_study,
            results=results,
            analysis_mesh=mesh,
        )


def test_known_mesh_identity_propagates_when_study_is_legacy(tmp_path: Path):
    model, _, results = _operation_model()
    exported = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))
    mesh = analysis.AnalysisMesh.from_dict(manifest["analysis_mesh"])
    legacy_study = replace(exported, solver_input_identity=None)

    state = result_state_from_fea_results(
        model=model,
        study=legacy_study,
        results=results,
        analysis_mesh=mesh,
    )

    assert state.solver_input_identity == mesh.solver_input_identity


def test_report_rejects_known_study_mesh_mismatch_across_legacy_state(tmp_path: Path):
    model, _, results = _operation_model()
    model.define_operation("Cold", temperature=20.0)
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))
    mesh = analysis.AnalysisMesh.from_dict(manifest["analysis_mesh"])
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    cold_mesh = replace(
        mesh,
        solver_input_identity=analysis.build_solver_input_identity(model, "Cold"),
    )

    with pytest.raises(EngineeringReviewError, match="fingerprints"):
        build_engineering_review(
            model,
            studies=[study],
            analysis_meshes=[cold_mesh],
            result_states=[replace(state, solver_input_identity=None)],
        )


def test_model_mutation_after_export_is_rejected_before_artifact_import(tmp_path: Path):
    model, _, _ = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    model.nodes["N1"].coords[0] = 2.0

    with pytest.raises(ValueError, match="solver input fingerprint"):
        import_code_aster_artifacts(model=model, work_dir=tmp_path)


def test_artifact_import_rejects_manifest_study_identity_hidden_by_explicit_study(
    tmp_path: Path,
    monkeypatch,
):
    model, _, _ = _operation_model()
    model.define_operation("Cold", temperature=20.0)
    explicit_study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest_path = tmp_path / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["study"]["solver_input_identity"] = analysis.build_solver_input_identity(model, "Cold").to_dict()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        CodeAsterSolver,
        "parse_result_artifacts",
        lambda *_args, **_kwargs: pytest.fail("conflicting manifest study reached artifact parsing"),
    )

    with pytest.raises(ValueError, match="manifest study.*load case"):
        import_code_aster_artifacts(model=model, work_dir=tmp_path, study=explicit_study)


def test_artifact_import_rejects_mismatched_sidecar_identity_before_parsing(
    tmp_path: Path,
    monkeypatch,
):
    model, _, _ = _operation_model()
    model.define_operation("Cold", temperature=20.0)
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["solver_input_identity"] = analysis.build_solver_input_identity(model, "Cold").to_dict()
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(
        CodeAsterSolver,
        "parse_result_artifacts",
        lambda *_args, **_kwargs: pytest.fail("conflicting sidecar reached artifact parsing"),
    )

    with pytest.raises(ValueError, match="sidecar.*load case"):
        import_code_aster_artifacts(model=model, work_dir=tmp_path)


def test_artifact_import_rejects_identity_free_sidecar_in_modern_chain_before_parsing(
    tmp_path: Path,
    monkeypatch,
):
    model, _, _ = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar.pop("solver_input_identity")
    sidecar["name_map"] = {"N0": "STALE_NODE"}
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(
        CodeAsterSolver,
        "parse_result_artifacts",
        lambda *_args, **_kwargs: pytest.fail("identity-free sidecar reached artifact parsing"),
    )

    with pytest.raises(ValueError, match="sidecar.*solver input identity.*identity-bearing"):
        import_code_aster_artifacts(model=model, work_dir=tmp_path)


def test_direct_parse_rejects_identity_free_sidecar_before_reading_tables(
    tmp_path: Path,
    monkeypatch,
):
    model, _, _ = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar.pop("solver_input_identity")
    sidecar["name_map"] = {"N0": "STALE_NODE"}
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(
        CodeAsterSolver,
        "_parse_results",
        lambda *_args, **_kwargs: pytest.fail("identity-free sidecar reached table parsing"),
    )

    with pytest.raises(ValueError, match="sidecar.*solver input identity.*identity-bearing"):
        CodeAsterSolver().parse_result_artifacts(model, tmp_path, "Hot")


def test_direct_parse_rejects_requested_load_case_mismatch(tmp_path: Path, monkeypatch):
    model, _, results = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    monkeypatch.setattr(CodeAsterSolver, "_parse_results", lambda *_args, **_kwargs: results)

    with pytest.raises(ValueError, match="load case.*Cold.*Hot"):
        CodeAsterSolver().parse_result_artifacts(model, tmp_path, "Cold")


def test_artifact_import_preserves_fully_legacy_identity_chain(
    tmp_path: Path,
    monkeypatch,
):
    model, _, results = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest_path = tmp_path / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["study"].pop("solver_input_identity")
    manifest["analysis_mesh"].pop("solver_input_identity")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar.pop("solver_input_identity")
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(CodeAsterSolver, "_parse_result_artifacts_after_validation", lambda *_args, **_kwargs: results)

    imported = import_code_aster_artifacts(model=model, work_dir=tmp_path)

    assert imported.study.solver_input_identity is None
    assert imported.analysis_mesh is not None
    assert imported.analysis_mesh.solver_input_identity is None


def test_direct_parse_preserves_fully_legacy_identity_chain(tmp_path: Path, monkeypatch):
    model, _, results = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest_path = tmp_path / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["study"].pop("solver_input_identity")
    manifest["analysis_mesh"].pop("solver_input_identity")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sidecar_path = tmp_path / "study_tuba_fem.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar.pop("solver_input_identity")
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(CodeAsterSolver, "_parse_results", lambda *_args, **_kwargs: results)

    parsed = CodeAsterSolver().parse_result_artifacts(model, tmp_path, "Hot")

    assert parsed is results


def test_scene_rejects_ownerless_analysis_mesh_with_known_identity(tmp_path: Path):
    model, _, _ = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))
    mesh = analysis.AnalysisMesh.from_dict(manifest["analysis_mesh"])

    with pytest.raises(ValueError, match="analysis mesh.*owning result state"):
        build_visualization_scene(model, analysis_meshes=[mesh])


def test_report_rejects_ownerless_analysis_mesh_with_known_identity(tmp_path: Path):
    model, _, _ = _operation_model()
    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text(encoding="utf-8"))
    mesh = analysis.AnalysisMesh.from_dict(manifest["analysis_mesh"])

    with pytest.raises(EngineeringReviewError, match="Analysis mesh.*owning study"):
        build_engineering_review(model, analysis_meshes=[mesh])


def test_model_mutation_after_result_creation_is_rejected_by_scene_and_report(tmp_path: Path):
    model, _, results = _operation_model()
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    state = result_state_from_fea_results(model=model, study=study, results=results)
    model.nodes["N1"].coords[0] = 2.0

    with pytest.raises(ValueError, match="solver input fingerprint"):
        build_visualization_scene(model, result_states=[state])
    with pytest.raises(EngineeringReviewError, match="solver input fingerprint"):
        build_engineering_review(model, studies=[study], result_states=[state])


def test_legacy_records_without_solver_input_identity_remain_loadable():
    study = analysis.AnalysisStudy.from_dict(
        {
            "id": "study:legacy",
            "model_revision": 0,
            "solver_name": "Code_Aster",
            "load_case": "Hot",
            "input_files": {},
            "mesh_id": "mesh:legacy",
        }
    )

    assert study.solver_input_identity is None


def test_unknown_result_case_omits_allowable_utilization_instead_of_using_20_c(tmp_path: Path):
    model, _, results = _operation_model()
    study = CodeAsterSolver(work_dir=tmp_path).export_analysis_study(model, "Hot", tmp_path)
    state = result_state_from_fea_results(model=model, study=study, results=results)
    legacy_unknown = replace(state, load_case="Missing", solver_input_identity=None)

    scene = build_visualization_scene(model, result_states=[legacy_unknown])
    stress = next(overlay for overlay in scene.overlays if overlay.data.get("result_type") == "stress")

    assert stress.data["utilization_values"] == {}


def test_pyvista_rejects_unknown_named_result_case():
    model, _, results = _operation_model()
    results.load_case = "Missing"

    with pytest.raises(ValueError, match="temperature.*Missing"):
        build_3d_mesh_from_model(model, results)


def test_solver_input_identity_ignores_int_versus_float_literals():
    """The same bend authored with int literals must keep one identity.

    JSON renders 90 and 90.0 differently, so an uncoerced int would give an
    otherwise identical model a second fingerprint.
    """

    def bend_model(radius, angle):
        model = Model(project_name="Literals")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 120.0e6})
        model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
        model.define_load_case("Operating", gravity=True)
        with model.pipe(section="Pipe", material="Steel") as builder:
            builder.start([0.0, 0.0, 0.0], support="anchor")
            builder.run(3.0)
            builder.bend(radius=radius, angle=angle, plane="XY")
            builder.run(2.0)
            builder.end(support="anchor")
        return model

    integers = build_solver_input_identity(bend_model(1, 90), "Operating")
    floats = build_solver_input_identity(bend_model(1.0, 90.0), "Operating")

    assert integers == floats
