"""V3 component equalities; native proof is a narrow 1D reference, not a header solve."""

import ast
import hashlib
import json
import os

import numpy as np
import pytest

from tuba import Model
from tuba.analysis.provenance import attached_support_coupling
from tuba.coordinates import CoordinateSystem
from tuba.fragments import ModelFragment, build_fragment_patch
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project.script import generate_model_script
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_comm import _held_dofs
from tuba.solver.aster_contact import attachment_equations, shoes
from tuba.solver.modelisation import PipeModelization


MASK = [1, 1, 0, 1, 1, 1]
DOFS = ["DX", "DY", "DRX", "DRY", "DRZ"]


def _catalog():
    model = Model("V3 node equality 1D reference")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_rectangular_section("Frame", height_y=0.1, height_z=0.1,
                                  thickness_y=0.01, thickness_z=0.01)
    return model


def _linked_cantilevers(mode="dof_equality"):
    model = _catalog()
    bases, tips = [], []
    for index, offset in enumerate((0.0, 0.01)):
        base, tip = model.add_node([offset, 0, 0]), model.add_node([1 + offset, 0, 0])
        model.add_element(id=f"beam_{index}", type="beam", n1=base, n2=tip,
                          section="Frame", material="Steel")
        model.add_support(base, "anchor")
        bases.append(base)
        tips.append(tip)
    model.add_support(tips[1], "custom", attached_to=tips[0], blocked_dof=MASK,
                      attachment_mode=mode, id="v3_link")
    model.define_load_case("Combined", gravity=False).add_nodal_force(
        tips[1], force=[100, 0, -200], moment=[10, 0, 0])
    return model, bases, tips


def _equations(model, support):
    expressions = list(attachment_equations(model, support, f"GN_{support.node}",
                                            _held_dofs(support), lambda name: name))
    records = [{key.arg: ast.literal_eval(key.value)
                for key in ast.parse(text, mode="eval").body.keywords} for text in expressions]
    return expressions, records


def test_v3_compiles_five_global_equalities_without_offset_terms(tmp_path):
    model, _, tips = _linked_cantilevers()
    support = model.supports[-1]
    expressions, records = _equations(model, support)
    assert _held_dofs(support) == DOFS
    assert len(records) == 5
    for dof, record in zip(DOFS, records):
        assert record == {"GROUP_NO": (f"GN_{tips[1]}", f"GN_{tips[0]}"),
                          "DDL": (dof, dof), "COEF_MULT": (1.0, -1.0), "COEF_IMPO": 0.0}
    study = CodeAsterSolver(pipe_modelization="POU_D_T").export_analysis_study(
        model, "Combined", tmp_path)
    comm = (tmp_path / "study.comm").read_text()
    assert all(expression in comm for expression in expressions)
    assert study.metadata["compiler_inputs"]["attached_support_coupling"] == "dof_equality"
    from tuba.mcp.server import _support_inspection
    inspected = _support_inspection(support)
    assert inspected["attachment_mode"] == "dof_equality"
    assert inspected["blocked_dof"] == MASK


def test_default_offset_coupling_and_identity_remain_distinct():
    model, _, tips = _linked_cantilevers("rigid_offset")
    support = model.supports[-1]
    _, records = _equations(model, support)
    dy = records[1]
    assert dy["DDL"] == ("DY", "DY", "DRZ")
    assert dy["COEF_MULT"] == pytest.approx((1, -1, -0.01))
    assert "attachment_mode" not in support.to_dict()
    assert attached_support_coupling(model) == "rotation_offset"
    solver = CodeAsterSolver(pipe_modelization="POU_D_T")
    old_identity = solver.analysis_study_inputs(model, "Combined").solver_input_identity
    support.attachment_mode = "dof_equality"
    assert attached_support_coupling(model) == "dof_equality"
    assert solver.analysis_study_inputs(model, "Combined").solver_input_identity != old_identity
    model.add_support(tips[1], "custom", attached_to=tips[0], blocked_dof=MASK)
    assert attached_support_coupling(model) == "rotation_offset+dof_equality"
    assert solver.analysis_study_inputs(model, "Combined").solver_input_identity != old_identity


def test_coincident_equality_still_binds_its_authored_mode_to_identity():
    model, _, tips = _linked_cantilevers()
    model.nodes[tips[1]].coords = model.nodes[tips[0]].coords.copy()
    solver = CodeAsterSolver(pipe_modelization="POU_D_T")
    equality = solver.analysis_study_inputs(model, "Combined").solver_input_identity
    assert attached_support_coupling(model) == "dof_equality"
    model.supports[-1].attachment_mode = "rigid_offset"
    assert attached_support_coupling(model) is None
    assert solver.analysis_study_inputs(model, "Combined").solver_input_identity != equality


def test_mutated_equality_is_revalidated_before_contact_or_attachment_compilation():
    model, _, _ = _linked_cantilevers()
    support = model.supports[-1]
    support.mass = 1
    with pytest.raises(ValueError, match="DOF equality"):
        shoes(model, PipeModelization.POU_D_T)
    with pytest.raises(ValueError, match="DOF equality"):
        _equations(model, support)


def test_json_and_generated_python_replay_preserve_selected_mode():
    model, _, _ = _linked_cantilevers()
    payload = model.to_dict()
    assert payload["supports"][-1]["attachment_mode"] == "dof_equality"
    assert Model.from_dict(json.loads(model.to_json())).to_dict() == payload
    script = generate_model_script(model, pipe_runs=False)
    namespace = {}
    exec(script, namespace)
    assert namespace["model"].to_dict() == payload
    for changes in ({"attachment_mode": "unknown"}, {"mass": 1}, {"attached_to": None}):
        changed = json.loads(model.to_json())
        changed["supports"][-1].update(changes)
        with pytest.raises(ValueError):
            Model.from_dict(changed)


def test_builder_and_fragment_patch_preserve_selected_mode():
    model = _catalog()
    frame_node = model.add_node([1, 0, 0])
    with model.pipe(section="Frame", material="Steel") as builder:
        builder.start([0.01, 0, 0]).beam(1)
        builder.add_support("custom", attached_to=frame_node, blocked_dof=MASK,
                            attachment_mode="dof_equality")
    script = generate_model_script(model)
    assert "builder.add_support" in script and "attachment_mode='dof_equality'" in script
    namespace = {}
    exec(script, namespace)
    assert namespace["model"].to_dict() == model.to_dict()
    fragment = ModelFragment("V3 fragment", model=model)
    patch = build_fragment_patch(fragment, CoordinateSystem(origin=[3, 0, 0]), name="placed")
    restored = ModelPatch.from_dict(patch.to_dict())
    parent = _catalog()
    result = ModelTransaction(parent).apply(restored)
    support = parent.supports[-1]
    assert support.attachment_mode == "dof_equality"
    assert support.attached_to == result.node_ids[frame_node]
    assert support.blocked_dof == MASK


@pytest.mark.parametrize("changes", [
    {"attachment_mode": "unknown"}, {"attached_to": None}, {"type": "rest"},
    {"type": "spring"}, {"type": "hanger"}, {"mass": 1},
    {"stiffness": 1e6}, {"stiffness_matrix": [0] * 6},
    {"imposed_displacement": [0, 0, 0]}, {"friction_coefficient": 0.3},
    {"gap": 0.01}, {"normal_stiffness": 1e6}, {"tangential_stiffness": 1e6},
])
def test_invalid_equality_paths_fail_at_construction(changes):
    model = _catalog()
    first, second = model.add_node([0, 0, 0]), model.add_node([0.01, 0, 0])
    options = dict(node=second, type="custom", attached_to=first,
                   blocked_dof=MASK, attachment_mode="dof_equality")
    options.update(changes)
    with pytest.raises(ValueError, match="attachment_mode|DOF equality"):
        model.add_support(**options)
    assert not model.supports


def test_v3_offset_equalities_exclude_a_common_rigid_body_yaw():
    """Source fidelity deliberately differs from a physically rigid offset joint."""
    model, _, tips = _linked_cantilevers()
    offset = model.nodes[tips[1]].coords - model.nodes[tips[0]].coords
    yaw = np.array([0.0, 0.0, 1.0])
    relative_translation = np.cross(yaw, offset)
    _, equations = _equations(model, model.supports[-1])
    assert equations[1]["DDL"] == ("DY", "DY")
    assert relative_translation[1] == pytest.approx(0.01)
    assert relative_translation[1] != 0  # V3's equal-DY relation rejects this rigid motion.
    model.supports[-1].attachment_mode = "rigid_offset"
    _, equations = _equations(model, model.supports[-1])
    assert relative_translation[1] + equations[1]["COEF_MULT"][2] * yaw[2] == pytest.approx(0)


@pytest.mark.skipif(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
                    reason="enable integration only for the real narrow 1D V3 node-link reference")
def test_real_code_aster_v3_equality_1d_reference(tmp_path):
    model, bases, tips = _linked_cantilevers()
    run = CodeAsterSolver(work_dir=tmp_path, pipe_modelization="POU_D_T",
                          exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto")).solve(model, "Combined")
    assert run.result_state.metadata["result_trust"] == "verified"
    relative = (np.asarray(run.result_state.node_displacements[tips[1]])
                - np.asarray(run.result_state.node_displacements[tips[0]]))
    np.testing.assert_allclose(relative[[0, 1, 3, 4, 5]], 0, atol=1e-10, rtol=0)
    assert abs(relative[2]) > 1e-6
    force, moment = np.zeros(3), np.zeros(3)
    for node in bases:
        reaction = np.asarray(run.result_state.node_reactions[node], dtype=float)
        force += reaction[:3]
        moment += np.cross(model.nodes[node].coords, reaction[:3]) + reaction[3:]
    applied_force = np.asarray([100.0, 0, -200])
    applied_moment = np.cross(model.nodes[tips[1]].coords, applied_force) + [10, 0, 0]
    np.testing.assert_allclose(force, -applied_force, atol=1e-3, rtol=0)
    assert np.isfinite(moment).all()
    summary = {
        "scope": "narrow 1D V3 node-link fidelity reference; not header or STEP qualification",
        "attachment_mode": "dof_equality", "blocked_dof": MASK, "offset_m": [0.01, 0, 0],
        "relative_displacement_rotation": relative.tolist(),
        "reaction_force_resultant_N": force.tolist(),
        "reaction_moment_resultant_Nm": moment.tolist(),
        "physical_moment_balance_residual_Nm": (moment + applied_moment).tolist(),
        "moment_check": "measured independently; offset equalities do not guarantee rigid-body yaw",
        "result_trust": run.result_state.metadata["result_trust"],
        "solver_version": run.result_state.metadata["solve_attestation"].get("solver_version"),
        "solver_input_identity": run.study.solver_input_identity.to_dict(),
        "rmed_sha256": hashlib.sha256((tmp_path / "study.rmed").read_bytes()).hexdigest(),
    }
    (tmp_path / "v3-node-link-summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, allow_nan=False))
