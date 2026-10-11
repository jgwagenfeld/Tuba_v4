"""Benchmark contract tests; synthetic reactions here are unit fixtures only."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import benchmark_llm_piping as benchmark
from tuba.project import load_project


SOURCE = Path(__file__).resolve().parents[1] / 'examples/llm-piping-benchmark/model.py'


@pytest.fixture
def model():
    return load_project(SOURCE.parent).run_model()['model']


def failed(checks):
    return [check for check in checks if check['status'] != 'pass']


def test_starter_meets_fixed_problem_definition(model):
    assert not failed(benchmark.check_candidate(model))


@pytest.mark.parametrize('change', ['temperature', 'section', 'material', 'support', 'load'])
def test_changed_requirement_is_rejected(model, change):
    if change == 'temperature':
        model.load_cases['Hot'].temperature = 20.
    elif change == 'section':
        model.sections['DN100'].WT = .001
    elif change == 'material':
        model.materials['Steel'].alpha = 0.
    elif change == 'support':
        model.supports[0].type = 'guide'
    else:
        model.load_cases['Hot'].gravity = True
    assert failed(benchmark.check_candidate(model))


def test_added_restraint_is_rejected(model):
    model.add_support(model.elements[2].n1, 'anchor')
    assert failed(benchmark.check_candidate(model))


def test_disconnected_geometry_is_rejected(model):
    model.elements.pop(2)
    assert any(c['id'] == 'route_connectivity' for c in failed(benchmark.check_candidate(model)))


def test_isolated_node_is_rejected(model):
    model.add_node([1., 1., 0.])
    assert any(c['id'] == 'route_connectivity' for c in failed(benchmark.check_candidate(model)))


def test_geometry_outside_envelope_is_rejected(model):
    model.nodes[model.elements[2].n1].coords[1] = 5.
    assert failed(benchmark.check_candidate(model))


@pytest.mark.parametrize('field', ['radius', 'angle', 'center', 'start_tangent', 'end_tangent'])
def test_inconsistent_explicit_bend_geometry_is_rejected(model, field):
    bend = next(e for e in model.elements if e.type == 'pipe_bend')
    if field in {'radius', 'angle'}:
        setattr(bend.bend_geometry, field, getattr(bend.bend_geometry, field) * 2)
    else:
        values = list(getattr(bend.bend_geometry, field))
        values[0] += .2
        setattr(bend.bend_geometry, field, values)
    assert failed(benchmark.check_candidate(model))


def test_actual_large_bends_cannot_hide_behind_radius_metadata():
    namespace = {}
    exec(SOURCE.read_text().replace('BEND_RADIUS = 0.3', 'BEND_RADIUS = 0.6'), namespace)
    model = namespace['model']
    for element in model.elements:
        if element.type == 'pipe_bend':
            element.bend_radius = .3
    assert failed(benchmark.check_candidate(model))


def test_reversed_bend_normal_cannot_change_solver_geometry(model):
    bend = next(e for e in model.elements if e.type == 'pipe_bend')
    bend.bend_geometry.normal = [-value for value in bend.bend_geometry.normal]
    assert failed(benchmark.check_candidate(model))


def test_sharp_corners_cannot_replace_required_bends():
    model = benchmark._base_model()
    with model.pipe(section='DN100', material='Steel') as pipe:
        pipe.start([0., 0., 0.], support='anchor')
        for direction, length in [([1.,0.,0.],4.), ([0.,1.,0.],1.), ([1.,0.,0.],4.),
                                  ([0.,-1.,0.],1.), ([1.,0.,0.],4.)]:
            pipe.direction = np.array(direction)
            pipe.run(length)
        pipe.end(support='anchor')
    assert any(c['id'] == 'route_tangency' for c in failed(benchmark.check_candidate(model)))


def test_collinear_subdivision_is_allowed():
    model = benchmark._base_model()
    with model.pipe(section='DN100', material='Steel') as pipe:
        pipe.start([0., 0., 0.], support='anchor').run(6.).run(6.).end(support='anchor')
    assert not failed(benchmark.check_candidate(model))


def fixture_run(model, reaction):
    """Inject quantity fixtures, never publish these as solver evidence."""
    return SimpleNamespace(
        validate_for_publication=lambda candidate: None,
        results=SimpleNamespace(node_results={
            node: SimpleNamespace(reaction_force=reaction)
            for node in model.nodes
        }),
        study=SimpleNamespace(load_case='Hot'),
        result_state=SimpleNamespace(id='unit-fixture'),
    )


@pytest.mark.parametrize('reaction', [None, [1., 2.], [np.nan] * 6, [np.inf] * 6])
def test_missing_or_nonfinite_reaction_is_unknown(model, reaction):
    checks = benchmark.reaction_checks(model, fixture_run(model, reaction))
    assert len(checks) == 4
    assert all(c['status'] == 'unknown' and c['value'] is None for c in checks)


def test_force_and_moment_have_separate_units_and_limits(model):
    checks = benchmark.reaction_checks(model, fixture_run(model, [3000., 4000., 0., 6000., 0., 0.]))
    forces = [c for c in checks if c['unit'] == 'N']
    moments = [c for c in checks if c['unit'] == 'N m']
    assert all(c['value'] == 5000. and c['status'] == 'pass' for c in forces)
    assert all(c['value'] == 6000. and c['status'] == 'fail' for c in moments)
    assert all(c['operation'] == 'Hot' and c['entity'] for c in checks)


def test_unverified_results_are_refused(model):
    run = fixture_run(model, [0.] * 6)
    def unverified(candidate):
        raise ValueError('result_trust must be verified')
    run.validate_for_publication = unverified
    with pytest.raises(ValueError, match='result_trust'):
        benchmark.reaction_checks(model, run)


def test_existing_attempt_is_never_overwritten(tmp_path):
    output = tmp_path / 'attempt'
    output.mkdir()
    sentinel = output / 'feedback.json'
    sentinel.write_text('retained', encoding='utf-8')
    with pytest.raises(FileExistsError):
        benchmark.evaluate(SOURCE, output, rationale='repeat', review=False)
    assert sentinel.read_text() == 'retained'


def test_changed_load_rejected_without_solver(tmp_path, monkeypatch):
    source = tmp_path / 'model.py'
    source.write_text(SOURCE.read_text().replace('temperature=200.0', 'temperature=20.0'))
    def unexpected(*args, **kwargs):
        pytest.fail('invalid problem must not invoke Code_Aster')
    monkeypatch.setattr(benchmark.CodeAsterSolver, 'solve', unexpected)
    result = benchmark.evaluate(source, tmp_path / 'attempt', rationale='changed load', review=False)
    assert result['status'] == 'rejected_constraint'
    assert result['solver_evaluations'] == 0
    assert result['checks']


def test_runtime_failure_retains_input_and_diagnostics(tmp_path, monkeypatch):
    original = SOURCE.read_bytes()
    def unavailable(*args, **kwargs):
        raise RuntimeError('Code_Aster runtime unavailable: test fixture')
    monkeypatch.setattr(benchmark.CodeAsterSolver, 'solve', unavailable)
    output = tmp_path / 'attempt'
    result = benchmark.evaluate(SOURCE, output, rationale='baseline', review=False)
    assert result['status'] == 'evaluation_failed'
    assert result['solver_evaluations'] == 1
    assert 'runtime unavailable' in result['error']['message']
    assert json.loads((output / 'feedback.json').read_text()) == result
    assert (output / 'model.py').read_bytes() == original == SOURCE.read_bytes()
    assert (output / 'requirements.json').is_file()
    assert (output / 'failure.txt').is_file()


def test_before_solver_checkpoint_retains_checks_and_exact_evaluator(tmp_path, monkeypatch):
    output = tmp_path / 'attempt'
    observed = {}
    def crash(*args, **kwargs):
        observed.update(json.loads((output / 'feedback.json').read_text()))
        raise RuntimeError('simulate failure after observing durable checkpoint')
    monkeypatch.setattr(benchmark.CodeAsterSolver, 'solve', crash)
    benchmark.evaluate(SOURCE, output, rationale='checkpoint test', review=False)
    assert observed['status'] == 'incomplete'
    assert observed['stage'] == 'solve'
    assert observed['solver_evaluations'] == 1
    assert observed['checks'] and all(c['status'] == 'pass' for c in observed['checks'])
    assert (output / 'evaluator.py').read_bytes() == Path(benchmark.__file__).read_bytes()


def test_build_failure_retains_attempt(tmp_path):
    source = tmp_path / 'invalid.py'
    source.write_text("raise ValueError('invalid candidate fixture')")
    output = tmp_path / 'attempt'
    result = benchmark.evaluate(source, output, rationale='bad source', review=False)
    assert result['status'] == 'evaluation_failed'
    assert result['solver_evaluations'] == 0
    assert (output / 'model.py').is_file()
    assert json.loads((output / 'feedback.json').read_text())['error']['stage'] == 'build'
