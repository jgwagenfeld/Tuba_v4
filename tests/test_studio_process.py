"""Portable Studio control tests; hydraulic fixtures do not represent solver evidence."""
import json
import threading
import time
from pathlib import Path
from dataclasses import replace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tuba.process.modelica import HydraulicResults
from tuba.process.pandapipes import PandapipesBackend
from tuba.process.studio import mapped_namespace, process_projection
from tuba.visualization.preview.server import ProjectStudioServer
from tests.test_process_structural import _circuit, _fixture_results

MODEL = """from tests.test_process_structural import _circuit
model, process = _circuit()
"""
STUDY = """from pathlib import Path
from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle
LOAD_CASES = ('operating',)
WALL_TEMPERATURE_MODEL = 'bulk-fluid-equals-wall-steady'
SOLVER_OPTIONS = {}
def build_review(namespace, output, *, artifact_dir=None):
    root = Path(output) / 'review_scene'
    write_scene_bundle(build_visualization_scene(SceneRequest(namespace['model'])), root)
    return root
"""


def wait_finished(server):
    deadline = time.monotonic() + 10
    while server._process_running and time.monotonic() < deadline:
        time.sleep(.01)
    assert not server._process_running
    with server._script_lock:
        pass  # Completion broadcasts finish under the same lock as source execution.


def fixture_hydraulic(bound, *, velocity=2):
    result = _fixture_results(bound)
    return replace(result, provenance={'solver': 'pandapipes', 'fixture': True},
                   segments=tuple(replace(row, velocity_m_s=velocity) for row in result.segments))


@pytest.fixture
def studio(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'model.py').write_text(MODEL)
    (project / 'study.py').write_text(STUDY)
    server = ProjectStudioServer(project, tmp_path / 'out', port=0, poll_interval_s=60)
    response, _ = server._run_script()
    assert response['ok'], response
    yield server
    wait_finished(server)


@pytest.fixture
def portable_backend(monkeypatch):
    monkeypatch.setattr(HydraulicResults, 'verify_for', lambda self, bound: None)
    monkeypatch.setattr(PandapipesBackend, 'solve', lambda self, bound, directory: fixture_hydraulic(bound))


def scene(server, bundle='build'):
    return json.loads((server.out_dir / bundle / 'scene.json').read_text())


def test_authored_declaration_is_visible_without_result_fields(studio):
    payload = scene(studio)['process']
    assert payload['schema'] == 'tuba.process.declaration.v1'
    assert payload['status'] == 'not_evaluated'
    assert payload['schematic']['components'][1]['element_ids']
    assert not {'segments', 'basis', 'provenance', 'checks'} & payload.keys()
    assert not scene(studio)['result_fields']
    assert studio.process_info()['can_run']
    assert not studio.project_info()['can_solve']
    assert studio.start_solve()[0] == 422
    assert studio.code_aster_commands('operating')[0] == 422


def test_pass_maps_only_copy_and_reuses_same_snapshot(studio, portable_backend):
    original = studio.model.to_dict()
    assert studio.start_process()[0] == 202
    wait_finished(studio)
    assert studio.process_info()['status'] == 'passed'
    assert studio.model.to_dict() == original
    namespace = studio._analysis_namespace()
    assert namespace is studio._analysis_namespace()
    assert namespace['model'] is not studio.model
    assert 'operating' in namespace['model'].operations
    assert 'operating' not in studio.model.operations
    payload = scene(studio)['process']
    assert payload['status'] == 'passed'
    assert payload['checks'] and all(check['verdict'] == 'pass' for check in payload['checks'])
    assert scene(studio)['result_fields']
    assert studio.project_info()['can_solve']
    status, comm = studio.code_aster_commands('operating')
    assert status == 200, comm
    assert 'AFFE_CHAR' in comm['code']
    assert studio._mesh_model() is namespace['model']


def test_rejection_retains_measured_fields_but_blocks_stress(studio, portable_backend, monkeypatch):
    monkeypatch.setattr(PandapipesBackend, 'solve', lambda self, bound, directory: fixture_hydraulic(bound, velocity=5))
    assert studio.start_process()[0] == 202
    wait_finished(studio)
    assert studio.process_info()['status'] == 'rejected'
    assert scene(studio)['process']['segments'][0]['velocity_m_s'] == 5
    assert any(check['verdict'] == 'fail' for check in scene(studio)['process']['checks'])
    assert studio.start_solve()[0] == 422
    assert (studio._process_attempt['directory'] / 'process_review.json').is_file()


@pytest.mark.parametrize('edit', [
    "# source changed\n",
    "from dataclasses import replace\nprocess = replace(process, scenario=replace(process.scenario, mass_flow_kg_s=11))\n",
    "from dataclasses import replace\nprocess = replace(process, requirements=replace(process.requirements, max_velocity_m_s=4))\n",
    "from dataclasses import replace\nprocess = replace(process, network=replace(process.network, id='new-network'))\n",
])
def test_source_scenario_requirements_network_edits_retire_fields(studio, portable_backend, edit):
    studio.start_process()
    wait_finished(studio)
    previous = studio._process_attempt['directory']
    studio.project.model_path.write_text(MODEL + edit)
    result, _ = studio._run_script()
    assert result['ok'], result
    assert studio.process_info()['status'] == 'stale'
    assert scene(studio)['process']['status'] == 'not_evaluated'
    assert not scene(studio)['result_fields']
    assert previous.is_dir()
    assert not studio.project_info()['can_solve']


def test_study_edit_and_source_error_retire_process(studio, portable_backend):
    studio.start_process()
    wait_finished(studio)
    studio.project.study_path.write_text(STUDY + '# edit\n')
    studio.run_once()
    assert studio.process_info()['status'] == 'stale'
    studio.project.model_path.write_text('invalid python !')
    studio.run_once()
    assert studio.process_info()['status'] == 'stale'
    assert not studio.project_info()['can_solve']
    assert scene(studio)['process']['schema'] == 'tuba.process.declaration.v1'
    assert 'Previous valid model' in scene(studio)['process']['error']
    assert not scene(studio)['result_fields']
    assert all('hydraulics' not in obj['metadata'] for obj in scene(studio)['objects'])


def test_late_hydraulics_cannot_attach_to_current_source_and_excludes_other_jobs(studio, portable_backend, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def solve(self, bound, directory):
        entered.set()
        assert release.wait(10)
        return fixture_hydraulic(bound)
    monkeypatch.setattr(PandapipesBackend, 'solve', solve)
    try:
        assert studio.start_process()[0] == 202
        assert entered.wait(10)
        assert studio.start_process()[0] == 409
        assert studio.mesh_jobs.start()[0] == 409
        assert studio.start_solve()[0] in {409, 422}
        studio.project.model_path.write_text(MODEL + '# edited during run\n')
        studio.run_once()
    finally:
        release.set()
    wait_finished(studio)
    assert studio.process_info()['status'] == 'stale'
    assert not scene(studio)['result_fields']
    assert (studio._process_attempt['directory'] / 'process_review.json').is_file()


def test_failed_replacement_keeps_previous_attempt_and_releases_claim(studio, portable_backend, monkeypatch):
    from tuba.project.claim import solve_claimed
    studio.start_process()
    wait_finished(studio)
    previous = studio._process_attempt['directory']
    def fail(*args):
        raise RuntimeError('runtime unavailable')
    monkeypatch.setattr(PandapipesBackend, 'solve', fail)
    assert studio.start_process()[0] == 202
    wait_finished(studio)
    assert studio.process_info()['status'] == 'failed'
    assert 'runtime unavailable' in studio.process_info()['error']
    assert previous.is_dir()
    assert not solve_claimed(studio.project.root)
    assert not scene(studio)['result_fields']
    assert (studio._process_attempt['directory'] / 'status.json').is_file()


def test_restart_requires_fresh_hydraulics_and_marks_retained_review_stale(studio, portable_backend):
    studio.start_process()
    wait_finished(studio)
    studio._produce_review(studio._analysis_namespace(), artifact_dir=None)
    assert scene(studio, 'review')['process']['status'] == 'passed'
    assert not studio.review_stale
    restarted = ProjectStudioServer(studio.project.root, studio.out_dir, port=0)
    restarted.run_once()
    assert restarted.process_info()['status'] == 'not_evaluated'
    assert restarted.review_stale
    assert not restarted.project_info()['can_solve']
    assert scene(restarted, 'review')['process']['status'] == 'passed'


def test_late_review_does_not_replace_retained_review(studio, portable_backend):
    studio.start_process()
    wait_finished(studio)
    namespace = studio._analysis_namespace()
    studio._produce_review(namespace, artifact_dir=None)
    retained = (studio.out_dir / 'review' / 'scene.json').read_bytes()
    original = studio.study.build_review
    def edit_during_review(*args, **kwargs):
        root = original(*args, **kwargs)
        studio.project.study_path.write_text(STUDY + '# late edit\n')
        return root
    studio.study.build_review = edit_during_review
    with pytest.raises(ValueError, match='current passing|changed'):
        studio._produce_review(namespace, artifact_dir=None)
    assert (studio.out_dir / 'review' / 'scene.json').read_bytes() == retained
    assert studio.review_stale


def test_fabricated_hydraulics_rejected_at_native_verifier(studio, monkeypatch):
    monkeypatch.setattr(PandapipesBackend, 'solve', lambda self, bound, directory: fixture_hydraulic(bound))
    studio.start_process()
    wait_finished(studio)
    assert studio.process_info()['status'] == 'failed'
    assert 'solve-issued evidence' in studio.process_info()['error']
    assert not scene(studio)['result_fields']


@pytest.mark.parametrize('study', [STUDY.replace("('operating',)", "('other',)"), STUDY.replace("WALL_TEMPERATURE_MODEL = 'bulk-fluid-equals-wall-steady'", '')])
def test_mapping_requires_matching_operation_and_explicit_wall_model(studio, portable_backend, study):
    studio.project.study_path.write_text(study)
    studio.run_once()
    studio.start_process()
    wait_finished(studio)
    assert studio.process_info()['status'] == 'passed'
    assert studio.start_solve()[0] == 422
    assert 'operating' not in studio.model.operations


def test_process_route_uses_existing_authorization_and_strict_empty_payload(studio, portable_backend):
    from tuba.visualization.preview.transport import PreviewServer
    PreviewServer.start(studio)
    try:
        def post(body, authorized=True):
            headers = {'Content-Type': 'application/json'}
            if authorized:
                headers['Authorization'] = 'Bearer ' + studio.access_token
            request = Request(studio.base_url + 'api/process/run', data=json.dumps(body).encode(), headers=headers, method='POST')
            try:
                with urlopen(request, timeout=10) as response:
                    return response.status
            except HTTPError as error:
                return error.code
        assert post({}, authorized=False) == 403
        for payload in [[], None, {'force': True}, 'run']:
            assert post(payload) == 400
        assert post({}) == 202
        wait_finished(studio)
    finally:
        studio.stop()


def test_dropping_process_does_not_make_hydraulic_review_current(studio, portable_backend):
    studio.start_process()
    wait_finished(studio)
    studio._produce_review(studio._analysis_namespace(), artifact_dir=None)
    studio.project.model_path.write_text(MODEL + 'del process\n')
    studio.run_once()
    assert not studio.process_info()['available']
    assert studio.review_stale
    assert 'process' not in scene(studio)


def test_publication_failure_cannot_orphan_project_claim(studio, monkeypatch):
    from tuba.project.claim import solve_claimed
    def fail(*args, **kwargs):
        raise RuntimeError('scene failure')
    monkeypatch.setattr(studio, '_publish_scene', fail)
    status, result = studio.start_process()
    assert status == 500
    assert 'scene failure' in result['error']
    assert not studio._solving and not studio._process_running
    assert not solve_claimed(studio.project.root)
    assert studio.process_info()['status'] == 'failed'


def test_changed_hydraulic_receipt_fails_loudly_and_withdraws_fields(studio, portable_backend, monkeypatch):
    studio.start_process()
    wait_finished(studio)
    def tampered(*args):
        raise ValueError('hydraulic CSV modified')
    monkeypatch.setattr(HydraulicResults, 'verify_for', tampered)
    studio._publish_scene()
    assert studio.process_info()['status'] == 'failed'
    assert 'CSV modified' in studio.process_info()['error']
    assert not scene(studio)['result_fields']
    assert not studio.project_info()['can_solve']


def test_mapped_worker_snapshot_and_retained_authored_inputs(studio, portable_backend, monkeypatch):
    from tests.test_studio_mesh_jobs import Process
    from tuba.visualization.preview.mesh_worker import run
    studio.start_process()
    wait_finished(studio)
    attempt = studio._process_attempt['directory']
    assert json.loads((attempt / 'model.json').read_text()) == studio.model.to_dict()
    assert (attempt / 'sources' / 'model.py').read_text() == MODEL
    assert (attempt / 'sources' / 'study.py').read_text() == STUDY
    worker = Process()
    monkeypatch.setattr(studio.mesh_jobs, '_launch', lambda *args: worker)
    monkeypatch.setattr(studio.mesh_jobs, '_monitor', lambda *args: None)
    assert studio.mesh_jobs.start()[0] == 202
    directory = Path(studio.mesh_jobs._job['directory'])
    request = json.loads((directory / 'request.json').read_text())
    assert 'operating' in request['process_model']['operations']
    run(studio.project.root, directory)
    worker.returncode = 0
    studio.mesh_jobs._complete(studio.mesh_jobs._job['id'], worker)
    assert studio.mesh_jobs.status()['state'] == 'succeeded'


def test_mesh_verification_failure_cannot_leak_claim(studio, portable_backend, monkeypatch):
    from tuba.project.claim import solve_claimed
    studio.start_process()
    wait_finished(studio)
    studio._analysis_namespace()
    def tampered(*args):
        raise ValueError('hydraulic evidence modified')
    monkeypatch.setattr(HydraulicResults, 'verify_for', tampered)
    assert studio.mesh_jobs.start()[0] == 422
    assert not solve_claimed(studio.project.root)
    assert studio.mesh_jobs._claim is None
    assert not studio.mesh_jobs.busy


def test_completion_record_failure_still_releases_slot(studio, portable_backend, monkeypatch):
    import tuba.search.artifacts as artifacts
    from tuba.project.claim import solve_claimed
    original = artifacts.atomic_json
    def fail_status(path, record):
        if Path(path).name == 'status.json':
            raise OSError('disk unavailable')
        return original(path, record)
    monkeypatch.setattr(artifacts, 'atomic_json', fail_status)
    assert studio.start_process()[0] == 202
    wait_finished(studio)
    assert not studio._solving
    assert not solve_claimed(studio.project.root)
    assert studio.process_info()['status'] == 'failed'
    assert 'disk unavailable' in studio.process_info()['error']


def test_review_poll_skips_invalid_transfer_config_without_losing_source_watcher(studio, portable_backend):
    studio.project.study_path.write_text(STUDY.replace("WALL_TEMPERATURE_MODEL = 'bulk-fluid-equals-wall-steady'", ''))
    studio.run_once()
    studio.start_process()
    wait_finished(studio)
    assert studio.process_info()['status'] == 'passed'
    assert studio.process_info()['error']
    studio.poll_review()
    studio.project.model_path.write_text(MODEL + '# source stays responsive\n')
    studio.run_once()
    assert studio.process_info()['status'] == 'stale'


def test_review_poll_handles_receipt_failure_and_retires_fields(studio, portable_backend, monkeypatch):
    studio.start_process()
    wait_finished(studio)
    monkeypatch.setattr(studio, '_external_evidence_signature', lambda: (('evidence', b'changed'),))
    def tampered(*args):
        raise RuntimeError('native runtime changed')
    monkeypatch.setattr(HydraulicResults, 'verify_for', tampered)
    studio.poll_review()
    assert studio.process_info()['status'] == 'failed'
    assert 'native runtime changed' in studio.review_error
    assert not scene(studio)['result_fields']
    studio.project.model_path.write_text(MODEL + '# source stays responsive\n')
    studio.run_once()
    assert studio.process_info()['status'] == 'stale'
