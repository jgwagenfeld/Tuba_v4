from dataclasses import replace
import math
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import load_project
from tuba.search.checks import compare_scalar, evaluate_checks, render_reason, verification_checks
from tuba.search.contracts import CheckResult, CheckSpec, Evaluation, decide

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def native():
    project = load_project(EXAMPLES / "autorouted-expansion-loop")
    model = project.run_model()["model"]
    return model, import_code_aster_artifacts(model=model, work_dir=project.root / "evidence/Hot")


def spec(kind, refs, *, limit=1000.0, operations=("Hot",), **options):
    unit = "N" if kind == "reaction_force" else "m" if kind == "displacement" else None
    return CheckSpec("test.check", kind, True, operations, refs, limit if unit else None, unit, options)


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True])
def test_unavailable_reaction_is_unknown(value):
    result = compare_scalar(constraint_id="pump.force", value=value, limit=1000.0,
                            unit="N", comparator="max", required=True, basis="code_aster",
                            operation="Hot", result_state_id="result_state:Hot",
                            entity_refs=("node:PumpNozzle",), evidence_refs=("attempts/A/Hot/study_reac.csv",))
    assert result.verdict == "unknown"
    assert result.reason_code == "measurement_unavailable"
    assert result.measured_value is None


def test_force_uses_only_translation_and_explanation_keeps_scope(native):
    model, run = native
    node = next(iter(run.result_state.node_reactions))
    vector = run.result_state.node_reactions[node]
    expected = math.hypot(*vector[:3])
    result, = evaluate_checks(model, {"Hot": run}, (spec("reaction_force", (f"node:{node}",)),))
    assert result.measured_value == expected
    assert result.unit == "N"
    text = render_reason(result)
    assert all(part in text for part in ("test.check", "Hot", run.result_state.id, f"node:{node}", "1000", "N", "study_reac.csv"))


def test_missing_target_cannot_be_hidden_by_an_available_target(native):
    model, run = native
    node = next(iter(run.result_state.node_reactions))
    checks = evaluate_checks(model, {"Hot": run}, (spec("reaction_force", (f"node:{node}", "node:absent")),))
    assert len(checks) == 2
    assert checks[1].verdict == "unknown"
    assert checks[1].entity_refs == ("node:absent",)


def test_missing_operation_and_corrupted_component_are_unknown(native):
    model, run = native
    node = next(iter(run.result_state.node_reactions))
    checks = evaluate_checks(model, {"Hot": run}, (spec("reaction_force", (f"node:{node}",), operations=("Hot", "Cold")),))
    assert checks[-1].operation == "Cold" and checks[-1].verdict == "unknown"
    # Fault injection into imported native data, never a production solver result.
    reactions = dict(run.result_state.node_reactions)
    reactions[node] = (None, *reactions[node][1:])
    damaged = replace(run, result_state=replace(run.result_state, node_reactions=reactions), result_states=())
    result, = evaluate_checks(model, {"Hot": damaged}, (spec("reaction_force", (f"node:{node}",)),))
    assert result.verdict == "unknown"


def test_operating_clash_keeps_native_entities_and_location(native):
    model, run = native
    first = model.elements[0]
    point = model.nodes[first.n1].coords
    model.add_obstacle(id="test_collision", type="cuboid", min_point=[v - 0.2 for v in point], max_point=[v + 0.2 for v in point])
    checks = evaluate_checks(model, {"Hot": run}, (spec("operating_clearance", (), envelope_type="bare"),))
    assert checks[0].verdict == "fail"
    assert "obstacle:test_collision" in checks[0].entity_refs
    assert checks[0].details["clashes"][0]["location"]
    assert checks[0].details["displacement_scale"] == 1.0


def test_unconfigured_insulation_coverage_is_unknown(native):
    model, run = native
    # This model has no declared insulation assignment.
    checks = evaluate_checks(model, {"Hot": run}, (spec("operating_clearance", (), envelope_type="insulation"),))
    assert checks[0].verdict == "unknown"
    assert checks[0].reason_code == "coverage_unavailable"


def test_missing_or_incorrect_authored_evaluator_does_not_pass(native):
    model, run = native
    policy = CheckSpec("code.check", "user_evaluator", True, ("Hot",), (), None, None, {})
    result, = evaluate_checks(model, {"Hot": run}, (policy,))
    assert result.verdict == "unknown"
    def wrong(context):
        return (CheckResult("other", "pass", True, "code_aster", "ok", "Wrong ID"),)
    with pytest.raises(ValueError, match="requested|declared"):
        evaluate_checks(model, {"Hot": run}, (policy,), user_evaluator=wrong)


def test_all_native_contact_increments_are_checked():
    project = load_project(EXAMPLES / "native-friction-review")
    model = project.run_model()["model"]
    run = import_code_aster_artifacts(model=model, work_dir=project.root / "evidence/Reseat")
    node = next(iter(run.result_state.node_displacements))
    checks = evaluate_checks(model, {"Reseat": run}, (spec("displacement", (f"node:{node}",), operations=("Reseat",), limit=1.0),))
    assert [c.result_state_id for c in checks] == [s.id for s in run.result_states]


def test_authored_evaluator_must_cover_every_target_in_every_state():
    project = load_project(EXAMPLES / "native-friction-review")
    model = project.run_model()["model"]
    run = import_code_aster_artifacts(model=model, work_dir=project.root / "evidence/Reseat")
    refs = tuple(f"node:{node}" for node in list(model.nodes)[:2])
    policy = CheckSpec("code.targets", "user_evaluator", True, ("Reseat",), refs, None, None, {})
    def incomplete(context):
        return tuple(CheckResult(policy.id, "pass", True, "code_aster", "fixture_check", "Incomplete target coverage",
                    entity_refs=(refs[index % 2],), operation="Reseat", result_state_id=state.id,
                    evidence_refs=(str(Path(run.study.work_dir) / "study_depl.csv"),))
                    for index, state in enumerate(run.result_states))
    raw = Evaluation("E", "C", "A", "complete", ("Reseat",), ("Reseat",), incomplete(None), "inventory.json")
    assert decide(raw, (policy,), ("Reseat",)).outcome == "incomplete"
    checks = evaluate_checks(model, {"Reseat": run}, (policy,), user_evaluator=incomplete)
    evaluation = Evaluation("E", "C", "A", "complete", ("Reseat",), ("Reseat",), checks, "inventory.json")
    assert decide(evaluation, (policy,), ("Reseat",)).outcome == "incomplete"
    for index, state in enumerate(run.result_states):
        missing = [c for c in checks if c.result_state_id == state.id and c.verdict == "unknown"]
        assert len(missing) == 1 and set(missing[0].entity_refs) == set(refs) - {refs[index % 2]}


def test_cold_collision_keeps_entities_and_location(native):
    model, _ = native
    point = model.nodes[model.elements[0].n1].coords
    model.add_obstacle(id="blocking", type="cuboid", min_point=[v - 0.2 for v in point], max_point=[v + 0.2 for v in point])
    policy = CheckSpec("cold.model", "cold_model", True, (), (), None, None, {})
    result, = verification_checks(model.verify(), (policy,))
    assert result.verdict == "fail"
    assert "obstacle:blocking" in result.entity_refs
    assert result.details["clashes"][0]["location"]
