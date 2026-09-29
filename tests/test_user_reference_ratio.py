"""The user reference ratio.

ADR 0007. One division, by a number the user typed. What these tests mostly hold
is the *refusals*, because the arithmetic is the easy part and the refusals are
what stop a screening ratio from being read as a code check - which is the one
thing this decision is not allowed to become.
"""

from __future__ import annotations

import math

import pytest

from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.model import TubaModel
from tuba.visualization.builders._contract import SceneBuildOptions, SceneRequest
from tuba.visualization.builders._core import build_visualization_scene


def _model(*, schedule: dict | None = None, temperature: float = 20.0, fields=()) -> TubaModel:
    from tuba.model import OperationField

    model = TubaModel()
    model.project_name = "Ratio fixture"
    model.add_material(
        "carbon",
        E=210e9,
        nu=0.3,
        rho=7850.0,
        allowable_stress={20.0: 137e6, 150.0: 127e6} if schedule is None else schedule,
    )
    model.add_pipe_section("PipeSec", OD=0.1143, WT=0.00602)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(
        id="E-1", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="carbon"
    )
    model.define_load_case(
        "Hot", gravity=False, temperature=temperature, ref_temperature=20.0, fields=list(fields)
    )
    return model


def _result_state(model: TubaModel, stress: float | None = 137e6) -> ResultState:
    results = {} if stress is None else {
        "E-1": {
            "forces_n1": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "forces_n2": [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "von_mises_n1": stress,
            "von_mises_n2": stress,
            "max_von_mises": stress,
        }
    }
    return ResultState(
        id="result:hot",
        study_id="study:hot",
        model_revision=0,
        solver_name="code_aster",
        load_case="Hot",
        mesh_id="mesh:hot",
        node_displacements={"N0": (0.0,) * 6},
        node_reactions={"N0": (0.0,) * 6},
        element_results=results,
        metadata={"result_trust": "verified", "solve_attestation": {"fixture": True}},
    )


def _scene(model: TubaModel, result_state: ResultState):
    study = AnalysisStudy(
        id="study:hot",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        work_dir="artifacts/hot",
        input_files={"mesh": "artifacts/hot/study.mail"},
        mesh_id="mesh:hot",
    )
    return build_visualization_scene(
        SceneRequest(model=model, options=SceneBuildOptions(), analysis_runs=[], result_states=[result_state])
    )


def _ratio_overlay(scene):
    return next(
        (overlay for overlay in scene.overlays if overlay.data.get("result_type") == "user_reference_ratio"),
        None,
    )


def test_the_ratio_is_the_fe_stress_over_the_users_own_schedule():
    scene = _scene(_model(), _result_state(_model(), stress=137e6))
    overlay = _ratio_overlay(scene)

    assert overlay is not None
    assert overlay.data["unit"] == "1"
    assert math.isclose(overlay.data["values"]["object:element:E-1"], 1.0)
    assert overlay.data["reference"]["denominator"] == "Material.allowable_stress"
    assert overlay.data["reference"]["denominator_source"] == "user_supplied_schedule"
    assert overlay.data["reference"]["extrapolated"] is False


def test_the_ratio_states_that_it_is_not_a_code_check():
    scene = _scene(_model(), _result_state(_model()))
    overlay = _ratio_overlay(scene)
    # The field's compliance_role is what puts the notice beside the number in the
    # viewport legend, the status strip and the field details, with no viewer code
    # restating it. That is the whole argument for putting it in the field.
    assert overlay.data["compliance_role"] == "user_reference_ratio_not_a_code_check"
    fields = {field.id: field for field in scene.result_fields}
    # build_result_fields derives the field id from the overlay id, replacing the
    # leading "overlay:" - it does not wrap it.
    ratio_field = fields[overlay.id.replace("overlay:", "field:", 1)]
    assert ratio_field.compliance_role == "user_reference_ratio_not_a_code_check"
    assert ratio_field.unit == "1"
    assert "not a code check" in ratio_field.label.lower()


def test_the_ratio_becomes_a_selectable_field_without_any_being_invented():
    scene = _scene(_model(), _result_state(_model()))
    ids = [field.id for field in scene.result_fields]
    # build_result_fields catalogues whatever a solver overlay carries, so the
    # ratio arrives as one more field in the existing colouring selector rather
    # than as a second channel beside it.
    assert any("user_reference_ratio" in field_id for field_id in ids)
    ratio_field = next(field for field in scene.result_fields if "user_reference_ratio" in field.id)
    assert ratio_field.support == "cell"
    assert ratio_field.components == ("magnitude",)


def test_the_schedule_is_interpolated_between_its_points():
    model = _model(temperature=85.0)
    scene = _scene(model, _result_state(model, stress=100e6))
    overlay = _ratio_overlay(scene)
    # 137 -> 127 MPa between 20 C and 150 C: at 85 C the schedule is 132 MPa.
    expected_allowable = 137e6 + (127e6 - 137e6) * (85.0 - 20.0) / (150.0 - 20.0)
    assert math.isclose(overlay.data["reference"]["denominator_pa"]["object:element:E-1"], expected_allowable)
    assert math.isclose(overlay.data["values"]["object:element:E-1"], 100e6 / expected_allowable)


def test_a_temperature_outside_the_schedule_is_unavailable_and_never_extrapolated():
    # Clamping to an endpoint is a quiet guess, and a number outside the domain
    # of the calculation is indistinguishable from one the tool invented.
    model = _model(temperature=400.0)
    scene = _scene(model, _result_state(model))
    assert _ratio_overlay(scene) is None
    codes = {diagnostic.code for diagnostic in scene.diagnostics}
    assert "user_reference_ratio.unavailable" in codes


def test_a_material_with_no_schedule_yields_no_ratio():
    model = _model(schedule={})
    scene = _scene(model, _result_state(model))
    assert _ratio_overlay(scene) is None


def test_a_case_declaring_a_temperature_field_yields_no_ratio():
    # The uniform case temperature is not the metal temperature at the hot spot,
    # and evaluating the schedule there would understate the ratio exactly where a
    # reviewer would use it. Per-node temperatures do not reach the bundle, so the
    # honest answer is unavailable rather than a number that is quietly wrong.
    from tuba.model import OperationField

    field = OperationField(
        quantity="temperature", value=175.0, scope="all", profile="uniform",
    )
    model = _model(fields=[field])
    scene = _scene(model, _result_state(model))
    assert _ratio_overlay(scene) is None
    codes = {diagnostic.code for diagnostic in scene.diagnostics}
    assert "user_reference_ratio.spatial_temperature" in codes


def test_a_result_state_with_no_stress_yields_no_ratio():
    model = _model()
    scene = _scene(model, _result_state(model, stress=None))
    assert _ratio_overlay(scene) is None


def test_the_field_names_the_materials_and_the_temperature_it_used():
    model = _model(temperature=60.0)
    scene = _scene(model, _result_state(model))
    reference = _ratio_overlay(scene).data["reference"]

    assert reference["materials"] == ["carbon"]
    assert math.isclose(reference["temperature_c"], 60.0)
    assert reference["temperature_source"] == "load_case_uniform_temperature_c"
    assert reference["interpolation"] == "linear_between_bracketing_schedule_points"
    # The denominator is published per element, so a reader can divide it back out
    # and get the FE stress they started from.
    assert set(reference["denominator_pa"]) == set(_ratio_overlay(scene).data["values"])


def test_a_single_point_schedule_answers_only_at_its_own_temperature():
    model = _model(schedule={20.0: 137e6}, temperature=20.0)
    assert _ratio_overlay(_scene(model, _result_state(model))) is not None
    away = _model(schedule={20.0: 137e6}, temperature=120.0)
    assert _ratio_overlay(_scene(away, _result_state(away))) is None
