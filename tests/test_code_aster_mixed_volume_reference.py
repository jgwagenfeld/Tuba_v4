import os

import numpy as np
import pytest

from examples.code_aster_tee_volume_review import (
    TEE_VOLUME_ELEMENT_IDS,
    build_tee_mixed_model,
)
from tuba import Model
from tuba.solver.modelisation import PipeModelization
from tuba.visualization import build_visualization_scene


pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real mixed Code_Aster reference",
)


def test_tuyau_to_solid_pipe_solves_and_builds_one_result_scene(tmp_path):
    model = Model("CodeAsterMixedPipeReference")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    nodes = [model.add_node([x, 0.0, 0.0]) for x in (0.0, 0.1, 0.2, 0.3)]
    for index, (n1, n2) in enumerate(zip(nodes, nodes[1:])):
        model.add_element(
            id=f"pipe_{index}",
            type="pipe_straight",
            n1=n1,
            n2=n2,
            section="Pipe",
            material="Steel",
        )
    model.add_support(nodes[0], type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)

    run = model.solve(
        load_case="Pressure",
        work_dir=tmp_path,
        pipe_modelization=PipeModelization.SOLID_3D,
        volume_element_ids=["pipe_1"],
        max_element_size=0.005,
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    )

    assert run.analysis_mesh is not None
    assert set(run.analysis_mesh.modelisations.values()) == {"3D", "TUYAU_3M"}
    assert run.study.solver_input_identity == run.analysis_mesh.solver_input_identity
    assert run.study.solver_input_identity == run.result_state.solver_input_identity
    assert run.result_state.metadata["result_trust"] == "verified"
    assert run.result_state.metadata["mixed_analysis"] is True
    assert run.results.volume_von_mises
    assert run.results.tuyau_subpoints
    assert any(np.linalg.norm(result.reaction_force[:3]) > 0.0 for result in run.results.node_results.values())
    assert (tmp_path / "study.rmed").is_file()
    assert (tmp_path / "study_effo.csv").is_file()
    assert (tmp_path / "study_sieq.csv").is_file()

    scene = build_visualization_scene(
        model,
        result_states=[run.result_state],
        analysis_meshes=[run.analysis_mesh],
    )
    scene.validate()
    assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
    assert any(obj.kind == "tuyau_subpoint_field" for obj in scene.objects)
    assert any(obj.kind == "analysis_mesh_element" for obj in scene.objects)


def test_tuyau_extensions_solve_with_the_native_tee_and_build_one_result_scene(tmp_path):
    model = build_tee_mixed_model()

    run = model.solve(
        load_case="Operating",
        work_dir=tmp_path,
        pipe_modelization=PipeModelization.SOLID_3D,
        volume_element_ids=TEE_VOLUME_ELEMENT_IDS,
        max_element_size=0.005,
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    )

    assert run.analysis_mesh is not None
    assert run.result_state.metadata["result_trust"] == "verified"
    assert run.results.volume_von_mises
    assert run.results.tuyau_subpoints
    scene = build_visualization_scene(
        model,
        result_states=[run.result_state],
        analysis_meshes=[run.analysis_mesh],
    )
    scene.validate()
    assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
    assert any(obj.kind == "tuyau_subpoint_field" for obj in scene.objects)
