import json
from pathlib import Path
from tuba import Model
from tuba.analysis import (
    AnalysisMesh,
    AnalysisStudy,
    MeshElementSource,
    MeshNodeSource,
)
from tuba.analysis.results import fea_results_from_result_state, result_state_from_fea_results
from tuba.refs import EntityRef
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization
from tuba.solver.aster_volume_results import parse_volume_result_artifacts


def _pressurized_pipe_model():
    model = Model("PressurizedVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.2, 0.0, 0.0])
    model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
    )
    model.add_support(n0, type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
    return model


def test_exports_grouped_pipe_volume_study_without_claiming_results(tmp_path):
    model = _pressurized_pipe_model()
    solver = CodeAsterSolver(work_dir=tmp_path)

    study = solver.export_volume_study(
        model,
        "Pressure",
        tmp_path,
        element_ids=["pipe_0"],
        max_element_size=0.005,
    )

    comm = Path(study.input_files["comm"]).read_text(encoding="utf-8")
    manifest = json.loads(Path(study.input_files["manifest"]).read_text(encoding="utf-8"))
    assert "LIRE_MAILLAGE(FORMAT='MED'" in comm
    assert "MODELISATION='3D'" in comm
    assert "GROUP_MA='G_SOLID_region_0'" in comm
    assert "PRES_REP=_F(" in comm
    assert "GROUP_MA='G_INNER_region_0'" in comm
    assert "RESU = MECA_STATIQUE(" in comm
    assert "RESU = CALC_CHAMP(" in comm
    assert "IMPR_RESU(" in comm
    assert study.metadata["pipe_modelization"] == PipeModelization.SOLID_3D.value
    assert study.metadata["result_status"] == "pending_solver"
    assert study.metadata["code_aster_solve_ready"] is True
    assert Path(study.input_files["med"]).is_file()
    assert manifest["analysis_mesh"]["surface_mesh"]["faces"]

def test_pipe_modelization_keeps_tuyau_as_default():
    assert PipeModelization.TUYAU_3M.value == "TUYAU_3M"
    assert PipeModelization.SOLID_3D.value == "3D"


def test_parses_real_volume_fields_on_analysis_nodes(tmp_path):
    model = _pressurized_pipe_model()
    node_ids = [f"VN{index}" for index in range(1, 5)]
    mesh = AnalysisMesh(
        id="volume_mesh",
        model_revision=0,
        solver_name="Code_Aster",
        nodes={node_id: (float(index), 0.0, 0.0) for index, node_id in enumerate(node_ids)},
        elements={"VM1": tuple(node_ids)},
        groups={"G_SOLID_region_0": ("VM1",)},
        node_sources={
            node_id: MeshNodeSource(node_id, EntityRef("element", "pipe_0"), "volume_node")
            for node_id in node_ids
        },
        element_sources={
            "VM1": MeshElementSource("VM1", EntityRef("element", "pipe_0"), "volume_cell")
        },
        surface_mesh={
            "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            "faces": [[0, 1, 2]],
            "node_ids": node_ids[:3],
        },
    )
    study = AnalysisStudy(
        id="volume_study",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Pressure",
        work_dir=str(tmp_path),
        input_files={},
        mesh_id=mesh.id,
        metadata={"compiler_inputs": {"element_ids": ["pipe_0"]}},
    )
    _write_table(
        tmp_path / "study_depl.csv",
        "NOEUD,DX,DY,DZ",
        [f"{index},{index * 0.001},0,0" for index in range(1, 5)],
    )
    _write_table(
        tmp_path / "study_reac.csv",
        "NOEUD,DX,DY,DZ",
        [f"{index},{index},0,0" for index in range(1, 5)],
    )
    _write_table(
        tmp_path / "study_sieq.csv",
        "NOEUD,VMIS",
        ["1,10", "1,14", "2,20", "3,30", "4,40"],
    )

    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)

    assert results.analysis_node_results["VN2"].displacement[0] == 0.002
    assert results.analysis_node_results["VN1"].reaction_force[0] == 1.0
    assert results.analysis_node_results["VN2"].reaction_force is None
    assert results.volume_von_mises == {"VN1": 12.0, "VN2": 20.0, "VN3": 30.0}
    assert results.element_results["pipe_0"].max_von_mises == 40.0
    state = result_state_from_fea_results(
        model=model,
        study=study,
        results=results,
        analysis_mesh=mesh,
    )
    reconstructed = fea_results_from_result_state(model=model, result_state=state)
    assert reconstructed.analysis_node_results["VN1"].reaction_force[0] == 1.0
    assert reconstructed.volume_von_mises == results.volume_von_mises


def _write_table(path, header, rows):
    path.write_text("# solver table\n" + header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
