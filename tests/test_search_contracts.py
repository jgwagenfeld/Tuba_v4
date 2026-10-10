"""Search decisions must never promote missing evidence into acceptance."""

from dataclasses import replace

import pytest

from tuba.search.contracts import (
    Candidate, CheckResult, CheckSpec, Evaluation, SearchDefinition, decide,
)


def force_check(**changes):
    values = dict(
        constraint_id="pump.force", verdict="pass", required=True,
        basis="code_aster", reason_code="within_limit", message="Force checked",
        operation="Hot", result_state_id="result_state:Hot",
        measured_value=10.0, limit=1000.0, unit="N", comparator="max",
        entity_refs=("node:PumpNozzle",), evidence_refs=("attempts/A/Hot/study_reac.csv",),
    )
    values.update(changes)
    return CheckResult(**values)


def evaluation(checks=(), **changes):
    values = dict(id="E", candidate_id="C", attempt_id="A", status="complete",
                  operations=("Hot",), completed_operations=("Hot",), checks=checks,
                  evidence_manifest_ref="attempts/A/inventory.json", error_kind=None)
    values.update(changes)
    return Evaluation(**values)


def specs():
    return (CheckSpec("pump.force", "reaction_force", True, ("Hot",),
                      ("node:PumpNozzle",), 1000.0, "N", {}),)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_numeric_pass_requires_a_finite_measurement(value):
    with pytest.raises(ValueError):
        force_check(measured_value=value)


@pytest.mark.parametrize("change", [
    {"verdict": "probably"}, {"constraint_id": ""}, {"unit": "N*m"},
    {"evidence_refs": ()}, {"result_state_id": None}, {"required": 1},
    {"verdict": "not_applicable", "details": {}},
    {"verdict": "pass", "measured_value": 1001.0},
    {"basis": "prediction"},
])
def test_invalid_numeric_verdict_cannot_be_stored(change):
    with pytest.raises(ValueError):
        force_check(**change)


def test_candidate_copies_inputs_and_round_trips():
    inputs = {"dimensions": [0.8, 2.0]}
    candidate = Candidate("C", (), inputs, "Initial loop")
    inputs["dimensions"].append(3.0)
    assert candidate.to_dict()["parameters"] == {"dimensions": [0.8, 2.0]}
    assert Candidate.from_dict(candidate.to_dict()) == candidate


@pytest.mark.parametrize("parameters", [{"v": object()}, {"v": float("nan")}, {1: 2}])
def test_candidate_refuses_non_json_parameters(parameters):
    with pytest.raises(ValueError):
        Candidate("C", (), parameters, "Proposal")


@pytest.mark.parametrize("identifier", ["", "../outside", "C/other"])
def test_candidate_identifier_is_safe_for_archive_paths(identifier):
    with pytest.raises(ValueError):
        Candidate(identifier, (), {}, "Proposal")


def test_evaluation_round_trip_retains_all_check_scope():
    record = evaluation((force_check(),))
    assert Evaluation.from_dict(record.to_dict()) == record


@pytest.mark.parametrize("status,error_kind,verdict,completed,outcome", [
    ("complete", None, "pass", ("Hot",), "feasible_retained"),
    ("failed", "runtime", "unknown", (), "evaluation_failed"),
    ("complete", None, "fail", ("Hot",), "rejected_constraint"),
    ("complete", None, "unknown", ("Hot",), "incomplete"),
    ("complete", None, "pass", (), "incomplete"),
    ("interrupted", None, "unknown", (), "incomplete"),
])
def test_decision_requires_complete_operations_and_checks(status, error_kind, verdict, completed, outcome):
    check = force_check(verdict=verdict, measured_value=2000.0 if verdict == "fail" else
                        None if verdict == "unknown" else 10.0)
    record = evaluation((check,), status=status, error_kind=error_kind,
                        completed_operations=completed)
    assert decide(record, specs(), ("Hot",)).outcome == outcome


def test_absent_required_check_and_absent_inventory_are_incomplete():
    assert decide(evaluation(), specs(), ("Hot",)).outcome == "incomplete"
    assert decide(evaluation((force_check(),), evidence_manifest_ref=None), specs(), ("Hot",)).outcome == "incomplete"


def test_advisory_failure_does_not_reject_required_pass():
    advisory = force_check(constraint_id="advisory", required=False, verdict="fail", measured_value=2000.0)
    assert decide(evaluation((force_check(), advisory)), specs(), ("Hot",)).outcome == "feasible_retained"


def test_non_applicability_requires_authored_condition():
    check = force_check(verdict="not_applicable", measured_value=None,
                        details={"applicability_condition": "No equipment nozzle"})
    assert decide(evaluation((check,)), specs(), ("Hot",)).outcome == "incomplete"
    configured = replace(specs()[0], options={"applicability_condition": "No equipment nozzle"})
    assert decide(evaluation((check,)), (configured,), ("Hot",)).outcome == "feasible_retained"


@pytest.mark.parametrize("change", [{"candidate_limit": True}, {"max_solver_calls": -1},
                                    {"parameter_grid": {"x": ()}}, {"objective_fields": ()}])
def test_search_definition_rejects_unbounded_or_invalid_configuration(change):
    values = dict(parameter_grid={"x": (1, 2)}, objective_fields=("pipe_length_m",),
                  candidate_limit=2, max_solver_calls=2, max_artifact_bytes=None)
    values.update(change)
    with pytest.raises(ValueError):
        SearchDefinition(**values)
