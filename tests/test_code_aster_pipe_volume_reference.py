import json
import math
import os
from statistics import median

import pytest

from tuba import Model
from tuba.solver.aster_volume_results import _rows, _volume_node_id
from tuba.solver.modelisation import PipeModelization
from tuba.visualization import build_visualization_scene


pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster volume references",
)


@pytest.mark.parametrize("max_element_size", [0.005, 0.004])
def test_pressurized_pipe_volume_matches_lame_and_builds_result_scene(tmp_path, max_element_size):
    pressure = 1.0e6
    outer_radius = 0.05
    inner_radius = 0.04
    length = 0.2
    model = Model("CodeAsterPipeVolumeReference")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=2.0 * outer_radius, WT=outer_radius - inner_radius)
    fixed = model.add_node([0.0, 0.0, 0.0])
    free = model.add_node([length, 0.0, 0.0])
    model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=fixed,
        n2=free,
        section="Pipe",
        material="Steel",
    )
    model.add_support(fixed, type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=pressure)

    run = model.solve(
        load_case="Pressure",
        work_dir=tmp_path,
        pipe_modelization=PipeModelization.SOLID_3D,
        volume_element_ids=["pipe_0"],
        max_element_size=max_element_size,
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    )

    assert run.analysis_mesh is not None
    assert run.study.solver_input_identity == run.analysis_mesh.solver_input_identity
    assert run.study.solver_input_identity == run.result_state.solver_input_identity
    assert run.result_state.metadata["solve_attestation"]["solver_version"]
    assert run.result_state.metadata["result_trust"] == "verified"
    assert run.results.volume_von_mises
    assert (tmp_path / "study_sigm.csv").is_file()

    hoop, radial = _midspan_inner_wall_stress(
        tmp_path / "study_sigm.csv",
        run.analysis_mesh.nodes,
        inner_radius=inner_radius,
        midspan=length / 2.0,
    )
    expected_hoop = pressure * (outer_radius**2 + inner_radius**2) / (outer_radius**2 - inner_radius**2)
    assert abs(hoop - expected_hoop) / expected_hoop < 0.05
    assert abs(radial + pressure) / pressure < 0.08

    scene = build_visualization_scene(
        model,
        result_states=[run.result_state],
        analysis_meshes=[run.analysis_mesh],
    )
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
    assert any(obj.kind == "volume_displacement_field" for obj in scene.objects)
    assert len([obj for obj in scene.objects if obj.kind == "analysis_mesh_surface"]) == 1
    assert not any(obj.kind in {"analysis_mesh_node", "analysis_mesh_element"} for obj in scene.objects)


def _midspan_inner_wall_stress(path, nodes, *, inner_radius, midspan):
    hoop_values = []
    radial_values = []
    for row in _rows(path):
        x, y, z = nodes[_volume_node_id(row["NOEUD"])]
        radius = math.hypot(y, z)
        if abs(x - midspan) > 0.02 or abs(radius - inner_radius) > 1.0e-7:
            continue
        c = y / radius
        s = z / radius
        syy = float(row["SIYY"])
        szz = float(row["SIZZ"])
        syz = float(row["SIYZ"])
        hoop_values.append(s * s * syy + c * c * szz - 2.0 * s * c * syz)
        radial_values.append(c * c * syy + s * s * szz + 2.0 * s * c * syz)
    assert hoop_values
    return median(hoop_values), median(radial_values)
