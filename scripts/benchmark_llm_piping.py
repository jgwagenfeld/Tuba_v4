"""Evaluate one trusted, standalone Python candidate for the frozen hot-line task.

Run as ``python -m scripts.benchmark_llm_piping`` from the repository root.
This small research harness is not the generic search/history subsystem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import traceback
from typing import Any

import numpy as np

from tuba import Model
from tuba.analysis.run import AnalysisRun
from tuba.model import TubaModel
from tuba.physical import element_length
from tuba.project import load_project
from tuba.project.solve import ProjectVerificationError, verify_project
from tuba.solver.aster import CodeAsterSolver


CASE = {
    'id': 'thermal-nozzle-repair-v1',
    'scope': 'Thermal-only reaction benchmark; not piping-code or fabrication qualification.',
    'endpoints_m': {'inlet': [0., 0., 0.], 'outlet': [12., 0., 0.]},
    'centerline_bounds_m': [[0., 0., 0.], [12., 4., 0.]],
    'material': {'E': 2.1e11, 'nu': .3, 'rho': 7850., 'alpha': 1.2e-5},
    'section': {'OD': .1143, 'WT': .00602},
    'operation': {'gravity': False, 'temperature': 200., 'ref_temperature': 20.},
    'force_limit_N': 5000.,
    'moment_limit_Nm': 5000.,
    'bend_radius_m': .3,
    'max_elements': 40,
    'solver_options': {'line_segments': 12, 'timeout_seconds': 180},
}


def _base_model() -> TubaModel:
    model = Model('Benchmark requirements')
    model.add_material('Steel', **CASE['material'])
    model.add_pipe_section('DN100', **CASE['section'])
    model.define_load_case('Hot', **CASE['operation'])
    return model


def _check(identifier: str, passed: bool, message: str) -> dict:
    return {'id': identifier, 'status': 'pass' if passed else 'fail', 'message': message}


def _endpoints(model: TubaModel) -> dict[str, str | None]:
    return {
        label: next((node.id for node in model.nodes.values()
                     if np.allclose(node.coords, point, rtol=0., atol=1e-8)), None)
        for label, point in CASE['endpoints_m'].items()
    }


def _bend_data(model, element):
    """Validate the actual quarter-circle; include exact axis extrema for bounds."""
    geometry = element.bend_geometry
    valid = (element.bend_radius == CASE['bend_radius_m']
             and abs(element.bend_angle or 0.) == 90. and geometry is not None)
    if not valid or element.n1 not in model.nodes or element.n2 not in model.nodes:
        return False, [], None, None
    # Builder geometry stores a positive arc angle and encodes turning direction
    # in its normal; the authored element angle may be negative.
    if geometry.radius != element.bend_radius or geometry.angle != abs(element.bend_angle):
        return False, [], None, None
    vectors = [np.asarray(value, dtype=float) for value in (
        geometry.center, geometry.normal, model.nodes[element.n1].coords,
        model.nodes[element.n2].coords, geometry.start_tangent, geometry.end_tangent,
    )]
    if any(value.shape != (3,) or not np.isfinite(value).all() for value in vectors):
        return False, [], None, None
    center, normal, start_point, end_point, start_tangent, end_tangent = vectors
    normal_length = np.linalg.norm(normal)
    if normal_length <= 1e-12:
        return False, [], None, None
    normal = normal / normal_length
    radial = start_point - center
    # Match the solver's supplied normal and radius vector. The general preview
    # sampler repairs normal orientation, which would hide a malformed solver arc.
    tangent = np.cross(normal, radial)
    start_direction, end_direction = tangent / geometry.radius, -radial / geometry.radius
    valid = (np.isclose(np.linalg.norm(radial), geometry.radius, rtol=0., atol=1e-8)
             and np.isclose(np.dot(radial, normal), 0., rtol=0., atol=1e-10)
             and np.allclose(center + tangent, end_point, rtol=0., atol=1e-8)
             and np.allclose(start_direction, start_tangent, rtol=0., atol=1e-8)
             and np.allclose(end_direction, end_tangent, rtol=0., atol=1e-8))
    points = [start_point, center + tangent]
    for axis in range(3):
        phase = np.arctan2(tangent[axis], radial[axis]) % (2 * np.pi)
        for angle in (phase, (phase + np.pi) % (2 * np.pi)):
            if angle <= np.pi / 2:
                points.append(center + radial * np.cos(angle) + tangent * np.sin(angle))
    return bool(valid), points, start_direction, end_direction


def check_candidate(model: TubaModel) -> list[dict]:
    """Check compiled engineering requirements independently of candidate source."""
    payload, expected = model.to_dict(), _base_model().to_dict()
    geometry_fields = {'meta', 'nodes', 'elements', 'supports', 'groups'}
    checks = [
        _check(f'fixed_{key}', payload.get(key) == value,
               f'{key} must match the frozen thermal benchmark.')
        for key, value in expected.items() if key not in geometry_fields
    ]
    meta = {key: value for key, value in payload['meta'].items() if key != 'project_name'}
    expected_meta = {key: value for key, value in expected['meta'].items() if key != 'project_name'}
    checks.append(_check('fixed_model_settings', meta == expected_meta, 'Keep default model/mesh settings.'))
    endpoints = _endpoints(model)
    checks.append(_check('fixed_endpoints', all(endpoints.values()), 'Keep both nozzle coordinates.'))
    restraints = [{key: value for key, value in support.to_dict().items() if key != 'id'}
                  for support in model.supports]
    required = [{'node': node, 'type': 'anchor'} for node in endpoints.values()]
    checks.append(_check('fixed_supports', len(restraints) == 2 and all(r in restraints for r in required),
                         'Only two unchanged ground anchors at the nozzles are permitted.'))
    valid_elements = bool(model.elements) and len(model.elements) <= CASE['max_elements']
    points = [node.coords for node in model.nodes.values()]
    adjacency = {node: [] for node in model.nodes}
    tangents = {node: [] for node in model.nodes}
    for element in model.elements:
        valid_elements &= (element.type in {'pipe_straight', 'pipe_bend'}
                           and element.material == 'Steel' and element.section == 'DN100')
        if element.n1 in adjacency and element.n2 in adjacency:
            adjacency[element.n1].append(element.n2)
            adjacency[element.n2].append(element.n1)
        else:
            valid_elements = False
        if element.type == 'pipe_bend':
            valid_bend, arc, start, end = _bend_data(model, element)
            valid_elements &= valid_bend
            points.extend(arc)
            if start is not None:
                tangents[element.n1].append(start)
                tangents[element.n2].append(-end)
        elif element.n1 in model.nodes and element.n2 in model.nodes:
            vector = model.nodes[element.n2].coords - model.nodes[element.n1].coords
            length = np.linalg.norm(vector)
            if np.isfinite(length) and length > 1e-8:
                tangents[element.n1].append(vector / length)
                tangents[element.n2].append(-vector / length)
            else:
                valid_elements = False
    checks.append(_check('allowed_elements', bool(valid_elements),
                         'Use at most 40 DN100 steel straights and 0.3 m radius 90-degree bends.'))
    visited, pending = set(), [endpoints['inlet']] if endpoints['inlet'] else []
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(adjacency[node])
    connected = bool(adjacency) and len(visited) == len(adjacency) and all(
        len(neighbors) == (1 if node in endpoints.values() else 2)
        for node, neighbors in adjacency.items()
    )
    checks.append(_check('route_connectivity', connected,
                         'One connected unbranched route must use every node between the nozzles.'))
    continuous = all(len(directions) == 2 and np.allclose(directions[0], -directions[1],
                                                        rtol=0., atol=1e-8)
                     for node, directions in tangents.items() if node not in endpoints.values())
    checks.append(_check('route_tangency', continuous,
                         'Join members tangentially; sharp corners cannot replace the specified bends.'))
    coordinates = np.asarray(points)
    low, high = np.asarray(CASE['centerline_bounds_m'])
    inside = (coordinates.size > 0 and np.isfinite(coordinates).all()
              and (coordinates >= low - 1e-8).all() and (coordinates <= high + 1e-8).all())
    checks.append(_check('route_envelope', bool(inside),
                         'Keep the planar centerline in x=[0,12], y=[0,4], z=0 m.'))
    return checks


def reaction_checks(model: TubaModel, run: AnalysisRun) -> list[dict]:
    """Return measured endpoint resultants; absent or nonfinite data stays unknown."""
    run.validate_for_publication(model)
    if run.study.load_case != 'Hot':
        raise ValueError('Benchmark results must belong to operation Hot.')
    checks = []
    for label, node in _endpoints(model).items():
        result = run.results.node_results.get(node)
        raw = None if result is None else result.reaction_force
        values = np.asarray(raw, dtype=float) if raw is not None else np.array([])
        available = values.shape == (6,) and np.isfinite(values).all()
        for quantity, indices, limit, unit in (
            ('force', slice(0, 3), CASE['force_limit_N'], 'N'),
            ('moment', slice(3, 6), CASE['moment_limit_Nm'], 'N m'),
        ):
            value = float(np.linalg.norm(values[indices])) if available else None
            checks.append({
                'id': f'{label}_{quantity}', 'entity': f'node:{node}', 'nozzle': label,
                'operation': 'Hot', 'result_state_id': run.result_state.id,
                'value': value, 'components': values[indices].tolist() if available else None,
                'unit': unit, 'comparator': '<=', 'limit': limit,
                'status': 'unknown' if value is None else 'pass' if value <= limit else 'fail',
                'message': 'Verified Code_Aster reaction.' if available else 'Required reaction data unavailable.',
            })
    return checks


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def _review(model: TubaModel, run: AnalysisRun, output: Path) -> str:
    from examples.code_aster_artifact_review import run_example

    result = run_example(output / 'review', model=model, run=run,
                         title='Thermal benchmark: Code_Aster results; see feedback.json for task acceptance',
                         source=output / 'model.py')
    return str(Path(result['bundle_root']).relative_to(output))


def evaluate(candidate: Path, output: Path, *, rationale: str, review: bool = True) -> dict:
    """Retain and evaluate one candidate; never overwrite input or another attempt."""
    candidate, output = Path(candidate).resolve(), Path(output).resolve()
    repo = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repo):
        raise ValueError('Benchmark output must be outside the source checkout.')
    source = candidate.read_bytes()
    evaluator_source = Path(__file__).read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'model.py').write_bytes(source)
    (output / 'evaluator.py').write_bytes(evaluator_source)
    _write_json(output / 'requirements.json', CASE)
    (output / 'study.py').write_text(
        f"LOAD_CASES = ('Hot',)\nSOLVER_OPTIONS = {CASE['solver_options']!r}\n", encoding='utf-8')
    started = time.monotonic()
    report: dict[str, Any] = {
        'schema': 'tuba.llm-piping-benchmark.v1', 'case_id': CASE['id'], 'scope': CASE['scope'],
        'status': 'incomplete', 'proposal_rationale': rationale, 'checks': [],
        'candidate_sha256': hashlib.sha256(source).hexdigest(),
        'evaluator_sha256': hashlib.sha256(evaluator_source).hexdigest(),
        'requirements_sha256': hashlib.sha256((output / 'requirements.json').read_bytes()).hexdigest(),
        'solver_evaluations': 0, 'elapsed_seconds': 0.,
    }
    _write_json(output / 'feedback.json', report)
    stage = 'build'
    try:
        project = load_project(output)
        namespace = project.run_model()
        model = namespace['model']
        stage = 'verification'
        try:
            verification = verify_project(project, namespace)
        except ProjectVerificationError as exc:
            report['verification'] = exc.report.to_dict()
            report['checks'].append(_check('cold_verification', False, str(exc)))
            report['status'] = 'rejected_constraint'
            return report
        report['verification'] = verification.to_dict()
        report['checks'] = [_check('cold_verification', True, 'Tuba model verification passed.')]
        report['checks'].extend(check_candidate(model))
        if any(check['status'] != 'pass' for check in report['checks']):
            report['status'] = 'rejected_constraint'
            return report
        report['route_length_m'] = sum(element_length(model, element) for element in model.elements)
        stage = 'solve'
        report['solver_evaluations'] = 1
        report['stage'] = stage
        report['elapsed_seconds'] = time.monotonic() - started
        _write_json(output / 'feedback.json', report)
        # Direct native execution preserves failed-solver artifacts; project.solve's
        # transient staging is intentionally avoided for this research attempt.
        solver = CodeAsterSolver(work_dir=output / 'evidence' / 'Hot', **CASE['solver_options'])
        run = solver.solve(model, 'Hot', force=True)
        stage = 'results'
        report['checks'].extend(reaction_checks(model, run))
        report['evidence'] = 'evidence/Hot'
        report['solver_input_identity'] = run.study.solver_input_identity.to_dict()
        statuses = {check['status'] for check in report['checks']}
        report['status'] = ('rejected_constraint' if 'fail' in statuses else
                            'incomplete' if 'unknown' in statuses else 'feasible')
        report['elapsed_seconds'] = time.monotonic() - started
        _write_json(output / 'feedback.json', report)
        if review:
            try:
                report['review'] = _review(model, run, output)
            except Exception as exc:
                report['review_error'] = f'{type(exc).__name__}: {exc}'
                (output / 'review-failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    except Exception as exc:
        report['status'] = 'evaluation_failed'
        report['error'] = {'stage': stage, 'type': type(exc).__name__, 'message': str(exc)}
        (output / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        report['stage'] = stage
        report['elapsed_seconds'] = time.monotonic() - started
        _write_json(output / 'feedback.json', report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path, help='Trusted standalone procedural model.py')
    parser.add_argument('--output', type=Path, required=True, help='New attempt directory outside source')
    parser.add_argument('--rationale', required=True, help='Proposal rationale recorded before evaluation')
    parser.add_argument('--no-review', action='store_true', help='Skip the optional web scene')
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.candidate, args.output, rationale=args.rationale, review=not args.no_review)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'error: {exc}\n')
    print(json.dumps({'status': report['status'], 'feedback': str(args.output.resolve() / 'feedback.json'),
                      'error': report.get('error'), 'review_error': report.get('review_error')}))
    return 0 if report['status'] == 'feasible' else 1


if __name__ == '__main__':
    raise SystemExit(main())
