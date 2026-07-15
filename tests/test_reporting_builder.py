from __future__ import annotations

from dataclasses import replace

import pytest

from tests.reporting_fixtures import build_review_model
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.reporting import EngineeringReviewError, build_engineering_review


@pytest.fixture
def review_model():
    return build_review_model()


@pytest.fixture
def code_aster_study() -> AnalysisStudy:
    return AnalysisStudy(
        id="study:hot",
        model_revision=4,
        solver_name="Code_Aster",
        load_case="Hot",
        work_dir="artifacts/hot",
        input_files={
            "commands": "artifacts/hot/study.comm",
            "mesh": "artifacts/hot/study.mail",
        },
        mesh_id="mesh:hot",
        metadata={"code_aster_version": "17.2"},
    )


@pytest.fixture
def code_aster_result_state() -> ResultState:
    return ResultState(
        id="result:hot",
        study_id="study:hot",
        model_revision=4,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id="mesh:hot",
        node_displacements={
            "N0": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "N1": (0.003, 0.004, 0.0, 0.01, 0.02, 0.02),
        },
        node_reactions={
            "N0": (300.0, 400.0, 0.0, 10.0, 20.0, 20.0),
        },
        element_results={
            "E-20": {
                "forces_n1": [100.0, 200.0, 200.0, 10.0, 20.0, 20.0],
                "forces_n2": [-100.0, -200.0, -200.0, -10.0, -20.0, -20.0],
                "von_mises_n1": 12.0e6,
                "von_mises_n2": 15.0e6,
                "max_von_mises": 15.0e6,
            }
        },
        files={"result": "artifacts/hot/study.rmed"},
        metadata={"parser_diagnostics": ["SIEQ table omitted one optional component."]},
    )


@pytest.fixture
def solved_review(review_model, code_aster_study, code_aster_result_state):
    return build_engineering_review(
        review_model,
        studies=[code_aster_study],
        result_states=[code_aster_result_state],
        package_id="review:solved",
        created_at="2026-07-15T00:00:00Z",
    )


def test_model_only_review_is_not_solved_and_has_no_result_tables(review_model):
    review = build_engineering_review(
        review_model,
        package_id="review:model-only",
        created_at="2026-07-15T00:00:00Z",
    )

    assert review.package_id == "review:model-only"
    assert review.created_at == "2026-07-15T00:00:00Z"
    assert review.analysis_status == "not_solved"
    assert "displacements" not in review.tables_by_id
    assert "code_compliance" not in review.tables_by_id
    assert "diagnostics" in review.tables_by_id


def test_study_without_results_is_listed_but_not_solved(review_model, code_aster_study):
    review = build_engineering_review(review_model, studies=[code_aster_study])

    assert review.analysis_status == "not_solved"
    assert review.table("studies").rows == (
        {
            "study_id": "study:hot",
            "solver_name": "Code_Aster",
            "load_case": "Hot",
            "model_revision": 4,
            "mesh_id": "mesh:hot",
            "work_dir": "artifacts/hot",
            "input_files": {
                "commands": "artifacts/hot/study.comm",
                "mesh": "artifacts/hot/study.mail",
            },
            "metadata": {"code_aster_version": "17.2"},
        },
    )
    assert "result_summary" not in review.tables_by_id


@pytest.mark.parametrize(
    ("record", "field", "value", "message"),
    [
        ("result", "model_revision", 9, "model revision"),
        ("result", "study_id", "study:missing", "supplied study"),
        ("result", "mesh_id", "mesh:other", "mesh"),
        ("result", "load_case", "Cold", "load case"),
        ("result", "solver_name", "OtherSolver", "solver"),
        ("study", "model_revision", 9, "model revision"),
    ],
)
def test_lineage_mismatches_raise(
    review_model,
    code_aster_study,
    code_aster_result_state,
    record,
    field,
    value,
    message,
):
    study = code_aster_study
    result = code_aster_result_state
    if record == "study":
        study = replace(study, **{field: value})
    else:
        result = replace(result, **{field: value})

    with pytest.raises(EngineeringReviewError, match=message):
        build_engineering_review(review_model, studies=[study], result_states=[result])


def test_non_code_aster_production_results_raise(
    review_model, code_aster_study, code_aster_result_state
):
    study = replace(code_aster_study, solver_name="Calculix")
    result = replace(code_aster_result_state, solver_name="calculix")

    with pytest.raises(EngineeringReviewError, match="Code_Aster"):
        build_engineering_review(review_model, studies=[study], result_states=[result])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("node_displacements", {"UNKNOWN": (0, 0, 0, 0, 0, 0)}, "node"),
        ("node_reactions", {"UNKNOWN": (0, 0, 0, 0, 0, 0)}, "node"),
        (
            "element_results",
            {
                "UNKNOWN": {
                    "forces_n1": [0, 0, 0, 0, 0, 0],
                    "forces_n2": [0, 0, 0, 0, 0, 0],
                    "von_mises_n1": 0,
                    "von_mises_n2": 0,
                    "max_von_mises": 0,
                }
            },
            "element",
        ),
    ],
)
def test_unknown_result_entities_raise(
    review_model,
    code_aster_study,
    code_aster_result_state,
    field,
    value,
    message,
):
    bad = replace(code_aster_result_state, **{field: value})

    with pytest.raises(EngineeringReviewError, match=message):
        build_engineering_review(review_model, studies=[code_aster_study], result_states=[bad])


def test_solver_result_tables_are_traceable_and_explicit(solved_review):
    assert solved_review.analysis_status == "solved"
    assert tuple(solved_review.tables_by_id)[-7:] == (
        "studies",
        "result_summary",
        "displacements",
        "reactions",
        "element_forces",
        "fe_stress",
        "diagnostics",
    )

    for table_id in (
        "result_summary",
        "displacements",
        "reactions",
        "element_forces",
        "fe_stress",
        "diagnostics",
    ):
        for row in solved_review.table(table_id).rows:
            assert {
                key: row[key]
                for key in ("solver_name", "study_id", "result_state_id", "load_case")
            } == {
                "solver_name": "Code_Aster",
                "study_id": "study:hot",
                "result_state_id": "result:hot",
                "load_case": "Hot",
            }


def test_result_rows_use_six_dofs_magnitudes_and_both_element_ends(solved_review):
    displacement = next(
        row for row in solved_review.table("displacements").rows if row["node_id"] == "N1"
    )
    assert {key: displacement[key] for key in ("dx", "dy", "dz", "drx", "dry", "drz")} == {
        "dx": 0.003,
        "dy": 0.004,
        "dz": 0.0,
        "drx": 0.01,
        "dry": 0.02,
        "drz": 0.02,
    }
    assert displacement["translation_magnitude"] == pytest.approx(0.005)
    assert displacement["rotation_magnitude"] == pytest.approx(0.03)
    assert displacement["entity_ref"] == "node:N1"

    reaction = solved_review.table("reactions").rows[0]
    assert {key: reaction[key] for key in ("fx", "fy", "fz", "mx", "my", "mz")} == {
        "fx": 300.0,
        "fy": 400.0,
        "fz": 0.0,
        "mx": 10.0,
        "my": 20.0,
        "mz": 20.0,
    }
    assert reaction["force_magnitude"] == pytest.approx(500.0)
    assert reaction["moment_magnitude"] == pytest.approx(30.0)
    assert reaction["support_ids"] == ["SUP-1"]

    force_rows = solved_review.table("element_forces").rows
    assert [(row["element_id"], row["element_end"], row["node_id"]) for row in force_rows] == [
        ("E-20", "n1", "N0"),
        ("E-20", "n2", "N1"),
    ]
    assert all(row["entity_ref"] == "element:E-20" for row in force_rows)


def test_fe_stress_is_explicitly_not_code_stress(solved_review):
    row = solved_review.table("fe_stress").rows[0]

    assert row["result_basis"] == "FE Von Mises (not piping-code stress)"
    assert row["von_mises_n1_pa"] == 12.0e6
    assert row["von_mises_n2_pa"] == 15.0e6
    assert row["max_von_mises_pa"] == 15.0e6
    assert "code_utilization" not in row
    assert "compliance" not in row


def test_result_summary_has_governing_locations(solved_review):
    rows = solved_review.table("result_summary").rows

    assert {row["result_type"] for row in rows} == {
        "translation_magnitude",
        "reaction_force_magnitude",
        "element_force_magnitude",
        "fe_von_mises",
    }
    assert all(row["governing_entity_ref"] for row in rows)
    assert next(row for row in rows if row["result_type"] == "translation_magnitude")[
        "governing_entity_ref"
    ] == "node:N1"
    assert next(row for row in rows if row["result_type"] == "fe_von_mises")[
        "governing_entity_ref"
    ] == "element:E-20"


def test_parser_diagnostics_are_package_and_table_records(solved_review):
    diagnostic = solved_review.diagnostics[0]

    assert diagnostic.severity == "warning"
    assert diagnostic.code == "SOLVER_PARSER_DIAGNOSTIC"
    assert diagnostic.source == "result_state:result:hot"
    assert diagnostic.target == "result_state:result:hot"
    assert solved_review.table("diagnostics").rows[0] == {
        "solver_name": "Code_Aster",
        "study_id": "study:hot",
        "result_state_id": "result:hot",
        "load_case": "Hot",
        **diagnostic.to_dict(),
    }


def test_multiple_studies_with_only_one_result_are_partial(
    review_model, code_aster_study, code_aster_result_state
):
    cold_study = replace(code_aster_study, id="study:cold", load_case="Cold", mesh_id="mesh:cold")

    review = build_engineering_review(
        review_model,
        studies=[code_aster_study, cold_study],
        result_states=[code_aster_result_state],
    )

    assert review.analysis_status == "partial"


def test_review_provenance_retains_supplied_study_and_result_artifacts(solved_review):
    assert [(record.kind, record.id) for record in solved_review.provenance] == [
        ("study", "study:hot"),
        ("result_state", "result:hot"),
    ]
    assert solved_review.provenance[0].files["commands"] == "artifacts/hot/study.comm"
    assert solved_review.provenance[1].files["result"] == "artifacts/hot/study.rmed"
    assert solved_review.provenance[1].metadata["parser_diagnostics"] == [
        "SIEQ table omitted one optional component."
    ]
