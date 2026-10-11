import json

import pytest

from tests.test_search_export import completed
from tests.test_search_run import author
from tuba.analysis.staged_run import read_staged_runs
from tuba.project.study import StudySettings
from tuba.search.__main__ import main
from tuba.search.run import run_search


def replay_writer():
    from tuba.search import write_search_replay
    return write_search_replay


def test_replay_keeps_native_views_and_history_without_solving(tmp_path, monkeypatch):
    run = completed(tmp_path)
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}
    monkeypatch.setattr(StudySettings, 'solver', lambda *a, **k: pytest.fail('Replay cannot solve'))
    path = replay_writer()(run, tmp_path / 'replay')
    data = json.loads(path.read_text())
    assert data['schema'] == 'tuba.search.viewer.v1'
    assert [c['outcome'] for c in data['candidates']] == ['selected', 'feasible_not_selected']
    for row in data['candidates']:
        preview = json.loads((path.parent / row['preview']['bundle'] / 'scene.json').read_text())
        assert preview['objects'] and preview['result_fields'] == []
        view = row['attempt_reviews'][0]
        assert view['availability'] == 'available'
        scene = json.loads((path.parent / view['bundle'] / 'scene.json').read_text())
        assert scene['search']['candidate_id'] == row['id']
        assert scene['search']['attempt_id'] == view['attempt_id']
        assert scene['result_fields']
        assert read_staged_runs(path.parent / view['bundle'])[0].operation == 'Operating'
    assert data['comparison_ranges']
    assert before == {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}


def test_replay_marks_damaged_results_without_hiding_recorded_outcomes(tmp_path):
    run = completed(tmp_path)
    next((run / 'attempts').rglob('study_reac.csv')).write_text('damaged')
    path = replay_writer()(run, tmp_path / 'replay')
    data = json.loads(path.read_text())
    row = data['candidates'][0]
    assert row['outcome'] == 'selected'  # Historical decision is preserved, not requalified.
    assert row['preview']['availability'] == 'available'
    assert row['attempt_reviews'][0]['availability'] == 'unavailable'
    assert row['attempt_reviews'][0]['bundle'] is None
    assert data['availability_diagnostics']


def test_replay_keeps_builder_failure_without_a_scene(tmp_path):
    project = author(tmp_path, values=(101.0,))
    script = project / 'model.py'
    text = script.read_text().replace('    return model', '    if parameters["y"] == 101.0:\n        raise ValueError("Unsupported boundary")\n    return model')
    script.write_text(text)
    run = tmp_path / 'run'
    run_search(project, run)
    data = json.loads(replay_writer()(run, tmp_path / 'replay').read_text())
    row = data['candidates'][0]
    assert row['outcome'] == 'evaluation_failed'
    assert row['preview']['availability'] == 'unavailable'
    assert row['attempt_reviews'] == []
    assert 'Unsupported boundary' in row['decisions'][0]['details']['message']


def test_replay_refuses_existing_output(tmp_path):
    run = completed(tmp_path)
    output = tmp_path / 'replay'
    output.mkdir()
    sentinel = output / 'keep'
    sentinel.write_text('preserved')
    with pytest.raises(FileExistsError):
        replay_writer()(run, output)
    assert sentinel.read_text() == 'preserved'


def test_replay_cli_exports_without_solver(tmp_path, monkeypatch):
    run = completed(tmp_path)
    monkeypatch.setattr(StudySettings, 'solver', lambda *a, **k: pytest.fail('Replay cannot solve'))
    assert main(['replay', '--run-dir', str(run), '--output', str(tmp_path / 'replay')]) == 0
    assert (tmp_path / 'replay/search_replay.json').is_file()


@pytest.mark.parametrize('damaged', ['{truncated', '[]', '{"schema":"tuba.search.inventory.v1"}',
                                   '{"schema":"tuba.search.inventory.v1","files":"wrong"}',
                                   '{"schema":"tuba.search.inventory.v1","files":[{}]}'])
def test_replay_preserves_records_when_an_inventory_is_malformed(tmp_path, damaged):
    run = completed(tmp_path)
    from tuba.search.export import inspect_history
    row = inspect_history(run)['candidates'][1]
    reference = row['evaluations'][0]['evidence_manifest_ref']
    (run / reference).write_text(damaged)
    data = json.loads(replay_writer()(run, tmp_path / 'replay').read_text())
    assert len(data['candidates']) == 2
    assert data['candidates'][0]['attempt_reviews'][0]['availability'] == 'available'
    assert data['candidates'][1]['outcome'] == 'feasible_not_selected'
    assert data['candidates'][1]['attempt_reviews'][0]['availability'] == 'unavailable'
    assert any(d['path'] == reference and d['availability'] == 'damaged' for d in data['availability_diagnostics'])


def test_replay_native_report_and_metadata_are_outcome_neutral(tmp_path):
    run = completed(tmp_path)
    path = replay_writer()(run, tmp_path / 'replay')
    row = json.loads(path.read_text())['candidates'][0]
    bundle = path.parent / row['attempt_reviews'][0]['bundle']
    metadata = json.loads((bundle / 'search_review.json').read_text())
    assert not {'outcome', 'current_candidate_outcome', 'decisions', 'attempt_decisions'} & metadata.keys()
    scene = json.loads((bundle / 'scene.json').read_text())
    assert scene['search'] == metadata
    assert 'Search candidate C0001: selected' not in (bundle / 'index.html').read_text()
    assert 'recorded evaluation' in (bundle / 'index.html').read_text()


def test_replay_keeps_previews_when_source_inventory_lacks_authored_model(tmp_path):
    from tuba.search.export import inspect_history
    run = completed(tmp_path)
    reference = inspect_history(run)['run']['source_manifest_ref']
    inventory_path = run / reference
    inventory = json.loads(inventory_path.read_text())
    for entry in inventory['files']:
        if entry['logical_name'] == 'model.py':
            entry.pop('logical_name')
    inventory_path.write_text(json.dumps(inventory))
    data = json.loads(replay_writer()(run, tmp_path / 'replay').read_text())
    assert all(c['preview']['availability'] == 'available' for c in data['candidates'])
    assert all(c['attempt_reviews'][0]['availability'] == 'unavailable' for c in data['candidates'])
    # Editing a content-addressed source inventory now fails its immutable
    # reference before review can search its entries for model.py.
    assert all('integrity' in c['attempt_reviews'][0]['message'] for c in data['candidates'])


def test_replay_retains_native_crash_recovery_before_successful_retry(tmp_path):
    from tests.project_replay import ReplaySolver
    from tests.test_search_run import RACK
    from tuba.search.export import inspect_history
    project = author(tmp_path, values=(100.0,), budget=2)
    run = tmp_path / 'run'
    class Crashed:
        def solve_exported_study(self, *args, **kwargs):
            raise OSError('Process terminated before evaluation publication')
    with pytest.raises(OSError):
        run_search(project, run, solver=Crashed())
    run_search(project, run, resume=True, solver=ReplaySolver(RACK / 'evidence'))
    snapshot = inspect_history(run)
    recovered = next(e for e in snapshot['events'] if e['kind'] == 'attempt.recovered')
    data = json.loads(replay_writer()(run, tmp_path / 'replay').read_text())
    row = data['candidates'][0]
    assert len(row['attempt_reviews']) == 2
    view = next(v for v in row['attempt_reviews'] if v['attempt_id'] == recovered['payload']['attempt_id'])
    assert view['evaluation_id'] is None
    assert view['availability'] == 'unavailable'
    assert 'No evaluation' in view['message']
    assert row['recovered_attempts'][0]['evidence_manifest_ref'] == recovered['payload']['evidence_manifest_ref']
    assert row['attempt_reviews'][-1]['availability'] == 'available'
