import math
import os

import numpy as np
import pytest

from examples.code_aster_tee_volume_review import TEE_VOLUME_ELEMENT_IDS, build_tee_volume_model
from tuba.solver.aster_volume_results import _rows, _volume_node_id
from tuba.solver.modelisation import PipeModelization
from tuba.visualization import build_visualization_scene


pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster tee reference",
)


def test_pressurized_tee_volume_has_stable_reactions_and_hotspot(tmp_path):
    metrics = []
    for max_element_size in (0.005, 0.004):
        model = build_tee_volume_model()
        root = tmp_path / str(max_element_size).replace(".", "_")
        run = model.solve(
            load_case="Operating",
            work_dir=root,
            pipe_modelization=PipeModelization.SOLID_3D,
            volume_element_ids=TEE_VOLUME_ELEMENT_IDS,
            max_element_size=max_element_size,
            exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
        )
        assert run.analysis_mesh is not None
        assert run.result_state.metadata["result_trust"] == "verified"
        assert run.study.solver_input_identity == run.analysis_mesh.solver_input_identity
        assert run.study.solver_input_identity == run.result_state.solver_input_identity
        scene = build_visualization_scene(
            model,
            result_states=[run.result_state],
            analysis_meshes=[run.analysis_mesh],
        )
        scene.validate()
        assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
        force, moment = _terminal_resultant(run.result_state, run.analysis_mesh)
        peak_value, peak_point = _junction_hotspot(root / "study_sieq.csv", run.analysis_mesh.nodes)
        metrics.append((force, moment, peak_value, peak_point))

    coarse_force, coarse_moment, coarse_stress, coarse_point = metrics[0]
    fine_force, fine_moment, fine_stress, fine_point = metrics[1]
    assert _relative_vector_change(coarse_force, fine_force) < 0.05
    assert _relative_vector_change(coarse_moment, fine_moment) < 0.08
    assert abs(coarse_stress - fine_stress) / fine_stress < 0.35
    assert np.linalg.norm(coarse_point - fine_point) < 0.02
    assert np.linalg.norm(fine_point) < 0.06


def _terminal_resultant(result_state, analysis_mesh):
    origin = np.asarray([-0.08, 0.0, 0.0])
    force = np.zeros(3)
    moment = np.zeros(3)
    for node_id, reaction in result_state.node_reactions.items():
        nodal_force = np.asarray(reaction[:3], dtype=float)
        point = np.asarray(analysis_mesh.nodes[node_id], dtype=float)
        force += nodal_force
        moment += np.cross(point - origin, nodal_force)
    assert np.linalg.norm(force) > 0.0
    assert np.linalg.norm(moment) > 0.0
    return force, moment


def _junction_hotspot(path, nodes):
    peak_value = -math.inf
    peak_point = None
    for row in _rows(path):
        point = np.asarray(nodes[_volume_node_id(row["NOEUD"])], dtype=float)
        if np.linalg.norm(point) > 0.06:
            continue
        value = float(row["VMIS"])
        if value > peak_value:
            peak_value = value
            peak_point = point
    assert math.isfinite(peak_value) and peak_point is not None
    return peak_value, peak_point


def _relative_vector_change(first, second):
    return float(np.linalg.norm(first - second) / max(np.linalg.norm(second), 1.0))
