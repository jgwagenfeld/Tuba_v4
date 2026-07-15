from __future__ import annotations

from dataclasses import replace

import pytest

from tests.reporting_fixtures import build_review_model
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.compliance.asme_b313 import ComplianceReport, ElementComplianceResult
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
        input_files={"commands": "artifacts/hot/study.comm", "mesh": "artifacts/hot/study.mail"},
        mesh_id="mesh:hot",
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
        node_displacements={"N0": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)},
        node_reactions={"N0": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)},
        element_results={
            "E-20": {
                "forces_n1": [0.0] * 6,
                "forces_n2": [0.0] * 6,
                "von_mises_n1": 12.0e6,
                "von_mises_n2": 15.0e6,
                "max_von_mises": 15.0e6,
            }
        },
    )


@pytest.fixture
def full_review_compliance() -> ComplianceReport:
    return ComplianceReport(
        [
            ElementComplianceResult(
                element_id="E-20",
                node_id="N0",
                sustained_stress=82.0e6,
                sustained_allowable=120.0e6,
                sustained_ratio=82.0 / 120.0,
                sustained_pass=True,
                expansion_stress=174.0e6,
                expansion_allowable=180.0e6,
                expansion_ratio=174.0 / 180.0,
                expansion_pass=True,
                pressure=2.0e6,
                Do=0.1143,
                t=0.006,
                Z=2.9e-5,
                i_i=1.5,
                i_o=1.25,
                k=3.5,
                h=0.47,
                M_i=1200.0,
                M_o=300.0,
                M_t=200.0,
                moment_basis="bend_geometry_local_axes",
                S_h=120.0e6,
                S_c=120.0e6,
                f=1.0,
            ),
            ElementComplianceResult(
                element_id="E-20",
                node_id="N1",
                sustained_stress=90.0e6,
                sustained_allowable=120.0e6,
                sustained_ratio=0.75,
                sustained_pass=True,
                expansion_stress=150.0e6,
                expansion_allowable=180.0e6,
                expansion_ratio=150.0 / 180.0,
                expansion_pass=True,
            ),
        ],
        "Hot",
    )


@pytest.fixture
def full_review(review_model, code_aster_study, code_aster_result_state, full_review_compliance):
    return build_engineering_review(
        review_model,
        studies=[code_aster_study],
        result_states=[code_aster_result_state],
        compliance_reports=[full_review_compliance],
    )


def test_compliance_table_comes_from_compliance_report(full_review, full_review_compliance):
    row = full_review.table("code_compliance").rows[0]
    source = full_review_compliance.results[0]

    assert full_review.analysis_status == "compliance_complete"
    assert row["code_name"] == "ASME B31.3"
    assert row["code_edition"] == "2020"
    assert row["sustained_stress_pa"] == source.sustained_stress
    assert row["expansion_stress_pa"] == source.expansion_stress
    assert row["entity_ref"] == f"element:{source.element_id}"
    assert {
        key: row[key]
        for key in ("solver_name", "study_id", "result_state_id", "load_case")
    } == {
        "solver_name": "Code_Aster",
        "study_id": "study:hot",
        "result_state_id": "result:hot",
        "load_case": "Hot",
    }


def test_compliance_rows_retain_calculation_trace(full_review, full_review_compliance):
    row = full_review.table("code_compliance").rows[0]
    source = full_review_compliance.results[0]

    for key in (
        "pressure",
        "Do",
        "t",
        "Z",
        "i_i",
        "i_o",
        "k",
        "h",
        "M_i",
        "M_o",
        "M_t",
        "moment_basis",
        "S_h",
        "S_c",
        "f",
    ):
        assert row[key] == getattr(source, key)


def test_compliance_governing_summaries_have_element_and_node_locations(full_review):
    rows = full_review.table("result_summary").rows
    sustained = next(row for row in rows if row["result_type"] == "sustained_code_utilization")
    expansion = next(row for row in rows if row["result_type"] == "expansion_code_utilization")

    assert sustained["maximum_value"] == 0.75
    assert sustained["governing_entity_ref"] == "element:E-20"
    assert sustained["governing_location"] == "N1"
    assert expansion["maximum_value"] == pytest.approx(174.0 / 180.0)
    assert expansion["governing_entity_ref"] == "element:E-20"
    assert expansion["governing_location"] == "N0"


def test_compliance_report_without_matching_solved_load_case_raises(
    review_model, code_aster_study, code_aster_result_state, full_review_compliance
):
    unmatched = replace(full_review_compliance, load_case="Cold")

    with pytest.raises(EngineeringReviewError, match="no matching result state"):
        build_engineering_review(
            review_model,
            studies=[code_aster_study],
            result_states=[code_aster_result_state],
            compliance_reports=[unmatched],
        )


@pytest.mark.parametrize(
    ("element_id", "node_id", "message"),
    [
        ("E-missing", "N0", "unknown model element"),
        ("E-20", "N-missing", "unknown model node"),
        ("E-20", "N2", "is not an endpoint"),
    ],
)
def test_compliance_result_requires_authoritative_model_lineage(
    review_model,
    code_aster_study,
    code_aster_result_state,
    full_review_compliance,
    element_id,
    node_id,
    message,
):
    invalid_result = replace(
        full_review_compliance.results[0],
        element_id=element_id,
        node_id=node_id,
    )
    invalid_report = replace(full_review_compliance, results=[invalid_result])

    with pytest.raises(EngineeringReviewError, match=message):
        build_engineering_review(
            review_model,
            studies=[code_aster_study],
            result_states=[code_aster_result_state],
            compliance_reports=[invalid_report],
        )


def test_compliance_result_accepts_model_element_endpoint_lineage(
    review_model,
    code_aster_study,
    code_aster_result_state,
    full_review_compliance,
):
    review = build_engineering_review(
        review_model,
        studies=[code_aster_study],
        result_states=[code_aster_result_state],
        compliance_reports=[full_review_compliance],
    )

    assert review.analysis_status == "compliance_complete"
    assert [
        (row["element_id"], row["node_id"])
        for row in review.table("code_compliance").rows
    ] == [("E-20", "N0"), ("E-20", "N1")]


def test_compliance_report_with_ambiguous_solved_load_case_raises(
    review_model, code_aster_study, code_aster_result_state, full_review_compliance
):
    duplicate_study = replace(code_aster_study, id="study:hot:2", mesh_id="mesh:hot:2")
    duplicate_state = replace(
        code_aster_result_state,
        id="result:hot:2",
        study_id=duplicate_study.id,
        mesh_id=duplicate_study.mesh_id,
    )

    with pytest.raises(EngineeringReviewError, match="multiple result states"):
        build_engineering_review(
            review_model,
            studies=[code_aster_study, duplicate_study],
            result_states=[code_aster_result_state, duplicate_state],
            compliance_reports=[full_review_compliance],
        )


def test_solved_review_without_compliance_remains_solved(
    review_model, code_aster_study, code_aster_result_state
):
    review = build_engineering_review(
        review_model,
        studies=[code_aster_study],
        result_states=[code_aster_result_state],
    )

    assert review.analysis_status == "solved"
    assert "code_compliance" not in review.tables_by_id
