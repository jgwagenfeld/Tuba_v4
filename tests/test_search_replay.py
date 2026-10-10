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
