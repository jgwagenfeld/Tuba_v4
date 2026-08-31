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
from tuba.analysis.provenance import MIXED_CODE_ASTER_COMPILER_ID, build_solver_input_identity
from tuba.refs import EntityRef
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization
from tuba.solver.aster_volume_results import parse_volume_result_artifacts
from tuba.visualization import build_visualization_scene


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


def _mixed_pressurized_pipe_model():
    model = Model("MixedPressurizedVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    nodes = [model.add_node([x, 0.0, 0.0]) for x in (-0.1, 0.0, 0.1, 0.2)]
    for element_id, n1, n2 in zip(("left", "solid", "right"), nodes, nodes[1:]):
        model.add_element(
            id=element_id,
            type="pipe_straight",
            n1=n1,
            n2=n2,
            section="Pipe",
            material="Steel",
        )
    model.add_support(nodes[0], type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
    return model, nodes


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
    assert study.metadata["tensor_stress_exported"] is True
    assert "study_sigm.csv" in Path(study.input_files["export"]).read_text(encoding="utf-8")
    assert Path(study.input_files["med"]).is_file()
    assert manifest["analysis_mesh"]["surface_mesh"]["faces"]

def test_pipe_modelization_keeps_tuyau_as_default():
    assert PipeModelization.TUYAU_3M.value == "TUYAU_3M"
    assert PipeModelization.SOLID_3D.value == "3D"


def test_exports_solve_ready_tuyau_to_solid_couplings_from_one_mesh(tmp_path):
    model, nodes = _mixed_pressurized_pipe_model()

    study = CodeAsterSolver(work_dir=tmp_path).export_volume_study(
        model,
        "Pressure",
        tmp_path,
        element_ids=["solid"],
        max_element_size=0.005,
    )

    comm = Path(study.input_files["comm"]).read_text(encoding="utf-8")
    manifest = json.loads(Path(study.input_files["manifest"]).read_text(encoding="utf-8"))
    mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    assert mesh.modelisations == {"G_SOLID_region_0": "3D", "G_TUBE": "TUYAU_3M"}
    assert "MAIL = DEFI_GROUP(" in comm
    assert "CREA_GROUP_NO=(" in comm
    assert comm.count("OPTION='3D_TUYAU'") == 2
    assert "CARA_ELEM=CARA" in comm
    assert comm.count("AXE_POUTRE=(1.00000000E+00, 0.00000000E+00, 0.00000000E+00)") == 2
    assert "FORCE_TUYAU=_F(" in comm
    assert "PRES_REP=_F(" in comm
    assert study.metadata["mixed_analysis"] is True
    assert study.metadata["code_aster_solve_ready"] is True
    assert mesh.groups[f"G_NODE_{nodes[1]}"]
    assert mesh.groups[f"G_NODE_{nodes[2]}"]


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


def test_mixed_result_parser_keeps_solid_and_tuyau_fields_distinct(tmp_path):
    model, nodes = _mixed_pressurized_pipe_model()
    compiler_inputs = {
        "element_ids": ["solid"],
        "line_element_ids": ["left", "right"],
    }
    identity = build_solver_input_identity(
        model,
        "Pressure",
        compiler_id=MIXED_CODE_ASTER_COMPILER_ID,
        compiler_inputs=compiler_inputs,
    )
    mesh = AnalysisMesh(
        id="mixed_mesh",
        model_revision=0,
        solver_name="Code_Aster",
        nodes={
            "VN1": (0.0, 0.05, 0.0),
            "VN2": (0.0, -0.05, 0.0),
            "VN10": model.nodes[nodes[0]].coords,
            "VN11": model.nodes[nodes[1]].coords,
            "VN12": (-0.05, 0.0, 0.0),
        },
        elements={
            "VM200": ("VN1", "VN2", "VN1", "VN2"),
            "LM100": ("VN10", "VN11", "VN12"),
        },
        groups={
            "G_SOLID_region_0": ("VM200",),
            "G_TUBE": ("LM100",),
            f"G_NODE_{nodes[0]}": ("VN10",),
        },
        node_sources={
            "VN1": MeshNodeSource("VN1", EntityRef("element", "solid"), "volume_node"),
            "VN2": MeshNodeSource("VN2", EntityRef("element", "solid"), "volume_node"),
            "VN10": MeshNodeSource("VN10", EntityRef("node", nodes[0]), "native_node"),
            "VN11": MeshNodeSource("VN11", EntityRef("node", nodes[1]), "native_node"),
            "VN12": MeshNodeSource("VN12", EntityRef("element", "left"), "generated_element_node"),
        },
        element_sources={
            "VM200": MeshElementSource("VM200", EntityRef("element", "solid"), "volume_cell"),
            "LM100": MeshElementSource("LM100", EntityRef("element", "left"), "native_element"),
        },
        modelisations={"G_SOLID_region_0": "3D", "G_TUBE": "TUYAU_3M"},
        solver_input_identity=identity,
        surface_mesh={
            "vertices": [[0.0, 0.05, 0.0], [0.0, -0.05, 0.0], [0.0, 0.0, 0.05]],
            "faces": [[0, 1, 2]],
            "node_ids": ["VN1", "VN2", "VN1"],
        },
    )
    study = AnalysisStudy(
        id="mixed_study",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Pressure",
        work_dir=str(tmp_path),
        input_files={},
        mesh_id=mesh.id,
        metadata={
            "mixed_analysis": True,
            "volume_analysis": True,
            "compiler_inputs": compiler_inputs,
        },
        solver_input_identity=identity,
    )
    _write_table(
        tmp_path / "study_depl.csv",
        "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
        [f"{node},0.001,0,0,0,0,0" for node in (1, 2, 10, 11, 12)],
    )
    _write_table(
        tmp_path / "study_reac.csv",
        "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
        ["10,100,0,0,0,0,0"],
    )
    _write_table(
        tmp_path / "study_sieq.csv",
        "MAILLE,NOEUD,SOUS_POINT,COOR_X,COOR_Y,COOR_Z,VMIS",
        [
            "200,1,,0,0.05,0,10",
            "200,2,,0,-0.05,0,20",
            "100,10,1,-0.1,0,0,100",
        ],
    )
    _write_table(
        tmp_path / "study_effo.csv",
        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
        [
            "100,10,1,2,3,4,5,6",
            "100,11,-1,-2,-3,-4,-5,-6",
        ],
    )

    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)

    assert results.volume_von_mises == {"VN1": 10.0, "VN2": 20.0}
    assert results.element_results["solid"].max_von_mises == 20.0
    assert results.element_results["left"].max_von_mises == 100.0
    assert results.element_results["left"].forces_n1.tolist() == [1, 2, 3, 4, 5, 6]
    assert results.node_results[nodes[0]].displacement[0] == 0.001
    assert results.node_results[nodes[0]].reaction_force[0] == 100.0
    assert len(results.tuyau_subpoints) == 1
    state = result_state_from_fea_results(
        model=model,
        study=study,
        results=results,
        analysis_mesh=mesh,
    )
    assert state.metadata["mixed_analysis"] is True
    reconstructed = fea_results_from_result_state(model=model, result_state=state)
    assert reconstructed.volume_von_mises == results.volume_von_mises
    assert len(reconstructed.tuyau_subpoints) == 1
    scene = build_visualization_scene(model, result_states=[state], analysis_meshes=[mesh])
    assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
    assert any(obj.kind == "tuyau_subpoint_field" for obj in scene.objects)


def _write_table(path, header, rows):
    path.write_text("# solver table\n" + header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
