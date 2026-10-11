"""Comparison accounting tests; fixtures are not engineering evidence."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import benchmark_llm_piping as benchmark
from scripts import iterate_llm_piping as iteration
from tuba.project import load_project
from tuba.search.history import History

SOURCE = Path(__file__).resolve().parents[1] / 'examples/llm-piping-iteration/model.py'


def case(identifier='thermal-guided-hot-v1'):
    from scripts.piping_comparison_cases import get_case
    return get_case(identifier)


def test_case_copies_and_unknown_id():
    first = case()
    first['operation']['temperature'] = 1
    assert case()['operation']['temperature'] == 300
    assert iteration.CASE['operation']['temperature'] == 200
    with pytest.raises(ValueError, match='Unknown'):
        case('invented')


def test_case_checks_use_temperature_and_envelope(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'model.py').write_text(SOURCE.read_text())
    model = load_project(project).run_model()['model']
    assert all(c['status'] == 'pass' for c in iteration.design_checks(model))
    checks = iteration.design_checks(model, case=case())
    assert any(c['id'] == 'fixed_load_cases' and c['status'] == 'fail' for c in checks)
    (project / 'model.py').write_text(SOURCE.read_text().replace('LOOP_RISE = 0.4', 'LOOP_RISE = 0.8'))
    model = load_project(project).run_model()['model']
    checks = iteration.design_checks(model, case=case('thermal-guided-compact-v1'))
    assert next(c for c in checks if c['id'] == 'route_envelope')['status'] == 'fail'


def test_case_reaction_limits_are_not_global():
    model = load_project(SOURCE.parent).run_model()['model']
    nodes = benchmark._endpoints(model).values()
    run = SimpleNamespace(validate_for_publication=lambda m: None, study=SimpleNamespace(load_case='Hot'),
        result_state=SimpleNamespace(id='fixture'), results=SimpleNamespace(node_results={
            n: SimpleNamespace(reaction_force=[7000, 0, 0, 0, 0, 0]) for n in nodes}))
    assert benchmark.reaction_checks(model, run)[0]['status'] == 'fail'
    assert benchmark.reaction_checks(model, run, case=case('thermal-guided-compact-v1'))[0]['status'] == 'pass'


def test_session_freezes_named_case_and_rejects_wrong_load(tmp_path):
    root = tmp_path / 'session'
    manifest = iteration.create_session(root, case_id='thermal-guided-hot-v1')
    assert manifest['case_id'] == 'thermal-guided-hot-v1'
    assert json.loads((root / 'requirements.json').read_text())['operation']['temperature'] == 300
    result = iteration.submit(root, SOURCE.parent, 'C1', intent='wrong load for this case')
    assert result['outcome'] == 'rejected_constraint'
    with History.open(root / 'history.sqlite3', readonly=True) as history:
        assert not any(e['kind'] == 'solver.invoked' for e in history.events())
    iteration.recover_session(root)


def campaign(tmp_path, **kwargs):
    from scripts import compare_llm_piping as comparison
    root = tmp_path / 'campaign'
    comparison.create_campaign(root, **kwargs)
    return comparison, root


def test_campaign_includes_unstarted_slots_without_fake_rates(tmp_path):
    comparison, root = campaign(tmp_path)
    report = comparison.report_campaign(root)
    assert len(report['trials']) == 6
    assert all(t['status'] == 'not_started' and t['wall_seconds'] is None for t in report['trials'])
    assert all(g['finished_runs'] == 0 and g['feasibility_rate_finished'] is None for g in report['groups'])
    assert report['llm_trials_run'] == 0


def test_invalid_proposals_consume_budget_and_remain_in_history(tmp_path):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-design-v1',),
        budgets={'max_proposals': 1, 'max_solver_calls': 1, 'max_wall_seconds': 1800})
    comparison.start_trial(root, 'T001')
    project = tmp_path / 'broken'
    project.mkdir()
    (project / 'model.py').write_text('raise ValueError("invalid proposal")')
    assert comparison.submit_trial(root, 'T001', project, intent='invalid')['outcome'] == 'evaluation_failed'
    with pytest.raises(ValueError, match='budget'):
        comparison.submit_trial(root, 'T001', SOURCE.parent, intent='over budget')
    comparison.finish_trial(root, 'T001', reason='budget')
    row = comparison.report_campaign(root)['trials'][0]
    assert row['proposals'] == 1 and row['solver_calls'] == 0
    assert row['candidate_outcomes'] == {'evaluation_failed': 1}
    assert row['feasible'] is False and row['model_cost_usd'] == 0
    assert comparison.report_campaign(root)['groups'][0]['feasibility_rate_finished'] == 0


def llm_method():
    return {'id': 'external-designer', 'kind': 'llm', 'representation': 'free-topology',
            'provider': 'test-provider', 'model': 'test-model-2026-10-11', 'settings': {'temperature': 0},
            'prompt': 'Author procedural model.py; evaluate every proposal.', 'tools': ['submit_trial']}


def test_llm_metadata_and_unknown_usage(tmp_path):
    method = llm_method()
    bad = dict(method, model='')
    from scripts import compare_llm_piping as comparison
    with pytest.raises(ValueError, match='model'):
        comparison.create_campaign(tmp_path / 'bad', methods=[bad])
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',), methods=[method])
    comparison.start_trial(root, 'T001')
    comparison.submit_trial(root, 'T001', SOURCE.parent, intent='incorrect temperature')
    comparison.finish_trial(root, 'T001', reason='driver stopped')
    row = comparison.report_campaign(root)['trials'][0]
    assert row['model_cost_usd'] is None and row['input_tokens'] is None
    assert row['usage_basis'] == 'unknown'
    assert row['first_feasible_seconds'] is None


def test_usage_provenance_and_trial_ids(tmp_path):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',), methods=[llm_method()])
    with pytest.raises(ValueError, match='Unknown trial'):
        comparison.start_trial(root, '../escape')
    comparison.start_trial(root, 'T001')
    usage = {'model': llm_method()['model'], 'input_tokens': 100, 'output_tokens': 200,
             'cost_usd': .01, 'source': 'test fixture, caller reported'}
    comparison.submit_trial(root, 'T001', SOURCE.parent, intent='wrong temperature', usage=usage)
    row = comparison.report_campaign(root)['trials'][0]
    assert row['model_cost_usd'] == .01 and row['input_tokens'] == 100
    assert row['usage_basis'] == 'caller_reported'
    with pytest.raises(ValueError, match='usage'):
        comparison.submit_trial(root, 'T001', SOURCE.parent, intent='bad telemetry', usage=dict(usage, cost_usd=float('nan')))


def test_wall_budget_and_finished_trial_reject_submission(tmp_path, monkeypatch):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',))
    comparison.start_trial(root, 'T001')
    monkeypatch.setattr(comparison, '_elapsed', lambda start, end=None: 100000)
    with pytest.raises(ValueError, match='budget'):
        comparison.submit_trial(root, 'T001', SOURCE.parent, intent='late')
    comparison.finish_trial(root, 'T001', reason='deadline')
    with pytest.raises(ValueError, match='finished'):
        comparison.submit_trial(root, 'T001', SOURCE.parent, intent='after finish')


def test_campaign_and_starter_integrity(tmp_path):
    comparison, root = campaign(tmp_path)
    with History.open(root / 'history.sqlite3', readonly=True) as history:
        ref = history.manifest()['source_manifest_ref']
    from tuba.search.artifacts import ArtifactStore
    store = ArtifactStore(root)
    inventory = store.verify_inventory(ref)
    starter = next(f for f in inventory['files'] if f['logical_name'].endswith('model.py'))
    store.path(starter['path']).write_text('changed')
    with pytest.raises(ValueError, match='integrity|changed'):
        comparison.start_trial(root, 'T001')


def test_missing_project_and_interrupted_proposal_are_not_lost(tmp_path):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-design-v1',))
    comparison.start_trial(root, 'T001')
    with pytest.raises((ValueError, FileNotFoundError)):
        comparison.submit_trial(root, 'T001', tmp_path / 'absent', intent='missing source')
    row = comparison.report_campaign(root)['trials'][0]
    assert row['proposals'] == 1 and row['submission_failures'] == 1
    comparison.finish_trial(root, 'T001', reason='source unavailable')
    assert not comparison.report_campaign(root)['trials'][0]['feasible']


def test_start_interruption_remains_visible_and_resumes(tmp_path, monkeypatch):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-design-v1',))
    original = iteration.create_session
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt('fixture')
    monkeypatch.setattr(iteration, 'create_session', interrupt)
    with pytest.raises(KeyboardInterrupt):
        comparison.start_trial(root, 'T001')
    assert comparison.report_campaign(root)['trials'][0]['status'] == 'initialization_incomplete'
    monkeypatch.setattr(iteration, 'create_session', original)
    brief = comparison.start_trial(root, 'T001')
    assert 'LOOP_RISE = 0.4' in brief['starter_source']
    with History.open(root / 'history.sqlite3', readonly=True) as history:
        assert sum(e['kind'] == 'trial.started' for e in history.events()) == 1


def test_decision_label_without_passing_evidence_cannot_count_as_feasible(tmp_path):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',))
    comparison.start_trial(root, 'T001')
    comparison.submit_trial(root, 'T001', SOURCE.parent, intent='invalid temperature')
    with History.open(root / 'trials/T001/history.sqlite3') as history:
        decision = next(e['payload'] for e in history.events() if e['kind'] == 'candidate.decision')
        history.append('candidate.decision', dict(decision, outcome='feasible_retained'), 'C001')
    row = comparison.report_campaign(root)['trials'][0]
    assert row['feasible'] is False and row['integrity_issues']


def test_changed_compiled_model_is_flagged_in_report(tmp_path):
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',))
    comparison.start_trial(root, 'T001')
    comparison.submit_trial(root, 'T001', SOURCE.parent, intent='invalid temperature')
    (root / 'trials/T001/candidates/C001/model.json').write_text('{}')
    row = comparison.report_campaign(root)['trials'][0]
    assert row['feasible'] is False
    assert 'model integrity' in row['integrity_issues'][0]['message']


def test_hot_starter_is_case_correct_and_groups_do_not_pool_representations(tmp_path):
    from scripts.compare_llm_piping import REFERENCE
    comparison, root = campaign(tmp_path, repeats=1, case_ids=('thermal-guided-hot-v1',),
                                methods=[REFERENCE, llm_method()])
    assert 'temperature=300.0' in comparison.start_trial(root, 'T002')['starter_source']
    groups = comparison.report_campaign(root)['groups']
    assert {g['representation'] for g in groups} == {'fixed-family', 'free-topology'}
