"""Every project solve surface refuses hard clashes before touching old evidence."""

import json
import time
from urllib.request import Request, urlopen

import pytest

from tuba.project import load_project, main
from tuba.project.claim import solve_claimed
from tuba.project.solve import ProjectVerificationError, solve_project


MODEL = """from tuba import Model
model = Model('Gate')
model.add_material('Steel', E=210e9, nu=.3)
model.add_pipe_section('Pipe', OD=.1, WT=.01)
model.define_load_case('Operating', gravity=True)
with model.pipe(section='Pipe', material='Steel') as pipe:
    pipe.start([0., 0., 0.], support='anchor')
    pipe.run(4.)
model.add_obstacle('box', 'cuboid', min_point=[1., -.1, -.1], max_point=[2., .1, .1])
"""


class _NoSolve:
    def solve_exported_study(self, *_):
        pytest.fail('A blocking clash reached the solver')


@pytest.mark.parametrize('surface', ['direct', 'cli', 'mcp', 'studio'])
@pytest.mark.parametrize('force', [False, True])
def test_blocking_clash_preserves_evidence_on_every_surface(tmp_path, monkeypatch, capsys, surface, force):
    script = tmp_path / 'model.py'
    script.write_text(MODEL, encoding='utf-8')
    (tmp_path / 'study.py').write_text("LOAD_CASES = ('Operating',)\n", encoding='utf-8')
    sentinels = [tmp_path / '.tuba' / 'staging' / 'previous', tmp_path / 'evidence' / 'Operating' / 'previous']
    for path in sentinels:
        path.parent.mkdir(parents=True)
        path.write_bytes(b'previous evidence')
    solver = _NoSolve()
    if surface == 'direct':
        with pytest.raises(ProjectVerificationError, match='clashes') as error:
            solve_project(load_project(tmp_path), force=force, solver=solver)
        assert error.value.report.passed is False
        assert len(error.value.report.blocking_clashes) == 1
    elif surface == 'cli':
        args = [str(tmp_path), '--output', str(tmp_path / 'review')]
        assert main(args + (['--force'] if force else []), solver=solver) == 1
        assert 'clashes' in capsys.readouterr().err
    elif surface == 'mcp':
        from tuba.mcp import server
        from tuba.solver.aster import CodeAsterSolver

        monkeypatch.setattr(CodeAsterSolver, 'solve_exported_study', solver.solve_exported_study)
        server.init_session(file_path=str(script), load_existing=True)
        response = server.solve_model(force=force)
        assert response['status'] == 'error'
        assert response['verification']['passed'] is False
        assert 'clashes' in response['message']
    else:
        from tuba.visualization.preview.server import ProjectStudioServer

        studio = ProjectStudioServer(tmp_path, tmp_path / 'review', port=0, solver=solver).start()
        try:
            request = Request(studio.base_url + 'api/solve', method='POST',
                              data=json.dumps({'force': force}).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=10) as response:
                assert response.status == 202
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with urlopen(studio.base_url + 'api/project', timeout=10) as response:
                    info = json.load(response)
                if not info['solving']:
                    break
                time.sleep(.05)
            assert info['solving'] is False
            assert 'clashes' in info['review_error']
            assert info['has_review'] is False
        finally:
            studio.stop()
    assert script.read_text(encoding='utf-8') == MODEL
    assert all(path.read_bytes() == b'previous evidence' for path in sentinels)
    assert not solve_claimed(tmp_path)
    assert not (tmp_path / 'review' / 'review_scene').exists()
