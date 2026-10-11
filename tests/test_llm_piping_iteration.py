"""Authored iteration contracts; solver fixtures are not engineering evidence."""

import json
from pathlib import Path

import pytest

from scripts import iterate_llm_piping as iteration
from scripts import benchmark_llm_piping as benchmark
from tuba.project import load_project
from tuba.search.artifacts import ArtifactStore
from tuba.search.contracts import CheckResult
from tuba.search.export import export_history, inspect_history, write_candidate_review
from tuba.search.history import History

SOURCE = Path(__file__).resolve().parents[1] / 'examples/llm-piping-benchmark/model.py'


def author(tmp_path, text=None):
    root = tmp_path / 'project'
    root.mkdir(exist_ok=True)
    (root / 'model.py').write_text(text or SOURCE.read_text(), encoding='utf-8')
    return root


def session(tmp_path, **kwargs):
    root = tmp_path / 'session'
    iteration.create_session(root, **kwargs)
    return root


def test_explicit_source_capture_does_not_copy_other_payloads(tmp_path):
    project = author(tmp_path)
    (project / 'units').mkdir()
    (project / 'units/loop.py').write_text('def build(model): pass')
    (project / 'ignored.py').write_text('not a dependency')
    store = ArtifactStore(tmp_path / 'archive')
    ref = store.capture_files(project, ('model.py', 'units/loop.py'))
    inventory = store.verify_inventory(ref)
    assert {f['logical_name'] for f in inventory['files']} == {'model.py', 'units/loop.py'}
    with pytest.raises(ValueError):
        store.capture_files(project, ('../outside.py',))


def test_moment_numeric_contract_enforces_limit():
    data = dict(constraint_id='moment', required=True, basis='code_aster', reason_code='limit',
                message='Measured fixture', operation='Hot', result_state_id='S',
                evidence_refs=('attempts/A/Hot/study_reac.csv',), measured_value=6000.,
                limit=5000., unit='N m', comparator='max')
    assert CheckResult(verdict='fail', **data).unit == 'N m'
    with pytest.raises(ValueError, match='disagrees'):
        CheckResult(verdict='pass', **data)


@pytest.mark.parametrize('direction', [[0., 1., 0.], [0., 0., 1.]])
def test_guides_allowed_only_in_new_case(direction):
    model = load_project(SOURCE.parent).run_model()['model']
    model.add_support(model.elements[0].n2, 'guide', direction=direction)
    assert all(c['status'] == 'pass' for c in iteration.design_checks(model))
    assert any(c['status'] == 'fail' for c in benchmark.check_candidate(model))


@pytest.mark.parametrize('change', ['direction', 'stiffness', 'friction_coefficient', 'imposed_displacement', 'attached_to', 'mass', 'anchor'])
def test_unpermitted_support_changes_fail(change):
    model = load_project(SOURCE.parent).run_model()['model']
    support = model.add_support(model.elements[0].n2, 'guide', direction=[0., 1., 0.])
    if change == 'anchor':
        model.supports[0].type = 'guide'
    else:
        setattr(support, change, {'direction': [1.,0.,0.], 'stiffness': 10.,
            'friction_coefficient': .1, 'imposed_displacement': [0.,.1,0.],
            'attached_to': model.elements[0].n1, 'mass': 1.}[change])
    assert any(c['status'] == 'fail' for c in iteration.design_checks(model))


def test_parent_diff_and_changed_requirements_rejected_before_solver(tmp_path):
    root = session(tmp_path)
    project = author(tmp_path, SOURCE.read_text().replace('temperature=200.0', 'temperature=20.0'))
    first = iteration.submit(root, project, 'C1', intent='invalid changed temperature')
    assert first['outcome'] == 'rejected_constraint'
    project.joinpath('model.py').write_text(SOURCE.read_text().replace('temperature=200.0', 'temperature=30.0'))
    second = iteration.submit(root, project, 'C2', parents=('C1',), intent='another invalid load')
    assert second['outcome'] == 'rejected_constraint'
    history = inspect_history(root)
    assert not any(e['kind'] == 'solver.invoked' for e in history['events'])
    diff = next(e['payload'] for e in history['events'] if e['kind'] == 'candidate.source_diff')
    assert diff['parent_id'] == 'C1' and 'temperature=30.0' in diff['files']['model.py']
    assert history['candidates'][1]['parent_ids'] == ['C1']
    exported = json.loads(export_history(root, tmp_path / 'export').read_text())
    refs = {row['parameters']['source_manifest_ref'] for row in exported['candidates']}
    assert refs <= {item['manifest']['path'] for item in exported['inventories']}
    review = write_candidate_review(root, 'C2', tmp_path / 'review')
    assert 'temperature=30.0' in (review.parent / 'source.py').read_text()
    assert json.loads(review.read_text())['search']['result_status'] == 'unsolved_preview'


def test_dependency_is_snapshotted_and_build_failure_retained(tmp_path):
    root = session(tmp_path)
    project = author(tmp_path, 'from units.loop import fail\nfail()\n')
    (project / 'units').mkdir()
    (project / 'units/loop.py').write_text("def fail():\n    raise ValueError('from captured unit')\n")
    result = iteration.submit(root, project, 'C1', dependencies=('units/loop.py',), intent='bad builder')
    assert result['outcome'] == 'evaluation_failed'
    assert 'from captured unit' in result['details']['message']
    row = inspect_history(root)['candidates'][0]
    store = ArtifactStore(root)
    inv = store.verify_inventory(row['parameters']['source_manifest_ref'])
    assert {f['logical_name'] for f in inv['files']} == {'model.py', 'units/loop.py'}


def test_retry_never_accepts_new_source_and_frozen_session_cannot_drift(tmp_path):
    root = session(tmp_path)
    project = author(tmp_path, "raise ValueError('bad source')")
    iteration.submit(root, project, 'C1', intent='bad builder')
    with pytest.raises(ValueError, match='already exists'):
        iteration.submit(root, project, 'C1', intent='overwrite')
    (root / 'requirements.json').write_text('{}')
    with pytest.raises(ValueError, match='frozen|integrity'):
        iteration.retry(root, 'C1')


def test_failed_runtime_retry_uses_fresh_attempt_and_retains_previous(tmp_path, monkeypatch):
    from tuba.solver.aster import CodeAsterSolver
    def unavailable(*args, **kwargs):
        raise RuntimeError('Code_Aster runtime unavailable: unit fixture')
    monkeypatch.setattr(CodeAsterSolver, 'solve_exported_study', unavailable)
    root = session(tmp_path)
    project = author(tmp_path)
    assert iteration.submit(root, project, 'C1', intent='runtime fixture')['outcome'] == 'evaluation_failed'
    assert iteration.retry(root, 'C1')['outcome'] == 'evaluation_failed'
    rows = inspect_history(root)['candidates']
    assert len(rows[0]['evaluations']) == 2
    assert len({e['attempt_id'] for e in rows[0]['evaluations']}) == 2
    for evaluation in rows[0]['evaluations']:
        ArtifactStore(root).verify_inventory(evaluation['evidence_manifest_ref'])


def test_recovery_seals_interruption_and_repairs_decision_gap(tmp_path, monkeypatch):
    root = session(tmp_path)
    project = author(tmp_path, SOURCE.read_text().replace('temperature=200.0', 'temperature=20.0'))
    original = History.append
    def crash(self, kind, payload, candidate_id=None):
        if kind == 'candidate.decision':
            raise KeyboardInterrupt()
        return original(self, kind, payload, candidate_id)
    monkeypatch.setattr(History, 'append', crash)
    with pytest.raises(KeyboardInterrupt):
        iteration.submit(root, project, 'C1', intent='interrupt at decision')
    monkeypatch.setattr(History, 'append', original)
    store = ArtifactStore(root)
    attempt = store.begin_attempt('C1')
    iteration.recover_session(root)
    row = inspect_history(root)['candidates'][0]
    assert row['outcome'] == 'incomplete'
    assert row['decisions'][0]['outcome'] == 'rejected_constraint'
    assert row['recovered_attempts'][0]['attempt_id'] == attempt
    assert len(row['evaluations']) == 1
    iteration.recover_session(root)
    assert len(inspect_history(root)['candidates'][0]['decisions']) == 2


def test_solver_budget_is_enforced_before_execution(tmp_path):
    root = session(tmp_path, max_solver_calls=0)
    project = author(tmp_path)
    result = iteration.submit(root, project, 'C1', intent='budget exhausted')
    assert result['outcome'] == 'deferred'
    assert not any(e['kind'] == 'solver.invoked' for e in inspect_history(root)['events'])


def test_omitted_required_precheck_stops_native_solver(tmp_path):
    from dataclasses import replace
    from tests.test_search_evaluate import setup
    from tuba.search.contracts import CheckSpec, decide
    from tuba.search.evaluate import evaluate_candidate
    candidate, model, loaded, archive, history = setup(tmp_path)
    spec = CheckSpec('fixed.problem', 'design_requirement', True, (), (), None, None, {})
    loaded = replace(loaded, check_specs=(*loaded.check_specs, spec))
    class UnexpectedSolver:
        def solve_exported_study(self, *args):
            pytest.fail('missing precheck cannot invoke solver')
    with history:
        evaluation = evaluate_candidate(candidate, model, loaded, archive=archive, history=history, solver=UnexpectedSolver())
        assert decide(evaluation, loaded.check_specs, ('Operating',)).outcome == 'incomplete'
        assert any(c.constraint_id == 'fixed.problem' and c.verdict == 'unknown' for c in evaluation.checks)


def test_tampered_candidate_source_is_refused_on_retry(tmp_path):
    root = session(tmp_path)
    project = author(tmp_path, "raise ValueError('bad source')")
    iteration.submit(root, project, 'C1', intent='bad source')
    row = inspect_history(root)['candidates'][0]
    store = ArtifactStore(root)
    inventory = store.verify_inventory(row['parameters']['source_manifest_ref'])
    store.path(inventory['files'][0]['path']).write_text('changed')
    with pytest.raises(ValueError, match='integrity'):
        iteration.retry(root, 'C1')


def test_changed_evaluator_cannot_resume_session(tmp_path, monkeypatch):
    root = session(tmp_path)
    monkeypatch.setattr(iteration, '_implementation', lambda: {'changed': 'yes'})
    with pytest.raises(ValueError, match='frozen'):
        iteration.recover_session(root)


def test_equivalent_checkout_line_endings_do_not_change_evaluator(tmp_path, monkeypatch):
    source = tmp_path / 'evaluator.py'
    source.write_bytes(b'x = 1\n')
    monkeypatch.setattr(iteration, 'REPO', tmp_path)
    monkeypatch.setattr(iteration, 'IMPLEMENTATION', ('evaluator.py',))
    before = iteration._implementation()
    source.write_bytes(b'x = 1\r\n')
    assert iteration._implementation() == before


def test_guided_example_uses_allowed_procedural_units():
    source = SOURCE.parents[1] / 'llm-piping-iteration'
    model = load_project(source).run_model()['model']
    assert len(model.supports) == 4
    assert all(c['status'] == 'pass' for c in iteration.design_checks(model))


def test_source_and_edited_inventory_cannot_replace_retained_candidate(tmp_path):
    import hashlib
    root = session(tmp_path)
    project = author(tmp_path, "raise ValueError('ORIGINAL')")
    iteration.submit(root, project, 'C1', intent='source integrity fixture')
    row = inspect_history(root)['candidates'][0]
    store = ArtifactStore(root)
    ref = row['parameters']['source_manifest_ref']
    inventory = store.verify_inventory(ref)
    file = store.path(inventory['files'][0]['path'])
    file.write_bytes(b"raise ValueError('REPLACED')")
    inventory['files'][0].update(sha256=hashlib.sha256(file.read_bytes()).hexdigest(), size_bytes=file.stat().st_size)
    store.path(ref).write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match='integrity'):
        iteration.retry(root, 'C1')


def test_attempt_metadata_crash_does_not_block_recovery(tmp_path, monkeypatch):
    from tuba.search import artifacts
    root = session(tmp_path, max_solver_calls=1)
    project = author(tmp_path)
    original = artifacts.atomic_json
    def crash(path, value, **kwargs):
        if path.name == 'attempt.json':
            path.parent.mkdir(parents=True)
            path.with_name('.attempt.json.crash.partial').write_text('{')
            raise KeyboardInterrupt()
        return original(path, value, **kwargs)
    monkeypatch.setattr(artifacts, 'atomic_json', crash)
    with pytest.raises(KeyboardInterrupt):
        iteration.submit(root, project, 'C1', intent='hard metadata crash')
    monkeypatch.setattr(artifacts, 'atomic_json', original)
    snapshot = iteration.recover_session(root)
    assert snapshot['candidates'][0]['outcome'] == 'incomplete'
    assert not snapshot['candidates'][0]['evaluations']
    event = next(e for e in snapshot['events'] if e['kind'] == 'attempt.orphaned')
    assert event['candidate_id'] is None
    inventory = ArtifactStore(root).verify_inventory(event['payload']['evidence_manifest_ref'])
    assert inventory['status'] == 'interrupted' and inventory['files']
    assert len(iteration.recover_session(root)['events']) == len(snapshot['events'])


@pytest.mark.parametrize('missing', ['source', 'model'])
def test_decision_gap_cannot_publish_without_candidate_integrity(tmp_path, monkeypatch, missing):
    root = session(tmp_path)
    project = author(tmp_path, SOURCE.read_text().replace('temperature=200.0', 'temperature=20.0'))
    original = History.append
    def crash(self, kind, payload, candidate_id=None):
        if kind == 'candidate.decision':
            raise KeyboardInterrupt()
        return original(self, kind, payload, candidate_id)
    monkeypatch.setattr(History, 'append', crash)
    with pytest.raises(KeyboardInterrupt):
        iteration.submit(root, project, 'C1', intent='decision gap')
    monkeypatch.setattr(History, 'append', original)
    store = ArtifactStore(root)
    row = inspect_history(root)['candidates'][0]
    ref = row['build']['model_ref']
    if missing == 'source':
        ref = store.verify_inventory(row['parameters']['source_manifest_ref'])['files'][0]['path']
    store.path(ref).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        iteration.recover_session(root)
    assert not inspect_history(root)['candidates'][0]['decisions']


def test_edited_attempt_inventory_cannot_rewrite_review_evidence(tmp_path):
    root = session(tmp_path)
    project = author(tmp_path, SOURCE.read_text().replace('temperature=200.0', 'temperature=20.0'))
    iteration.submit(root, project, 'C1', intent='seal integrity fixture')
    row = inspect_history(root)['candidates'][0]
    evaluation = row['evaluations'][0]
    inventory_path = ArtifactStore(root).path(evaluation['evidence_manifest_ref'])
    inventory = json.loads(inventory_path.read_text())
    inventory['status'] = 'complete'
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match='integrity'):
        write_candidate_review(root, 'C1', tmp_path / 'review')
