"""Submit trusted authored piping designs to a frozen, retained Code_Aster session."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import sqlite3
import uuid

from scripts import benchmark_llm_piping as benchmark
from tuba.project import load_project
from tuba.project.freshness import expected_identity
from tuba.project.study import StudySettings
from tuba.search.artifacts import ArtifactStore, atomic_json, digest_file, no_links
from tuba.search.contracts import Candidate, CheckResult, CheckSpec, Decision, Evaluation, EvaluationContext, decide
from tuba.search.evaluate import evaluate_candidate
from tuba.search.export import inspect_history
from tuba.search.history import History, SCHEMA
from tuba.search.run import coordinator, digest, objective_values


REPO = Path(__file__).resolve().parents[1]
CASE = {**benchmark.CASE, 'id': 'thermal-guided-design-v1',
        'support_policy': {'max_guides': 4, 'directions': [[0., 1., 0.], [0., 0., 1.]],
                           'placement': 'Distinct interior nodes; ideal bilateral ground guides only.'}}
IMPLEMENTATION = ('scripts/iterate_llm_piping.py', 'scripts/benchmark_llm_piping.py',
                  'tuba/search/contracts.py', 'tuba/search/checks.py', 'tuba/search/evaluate.py')


def design_checks(model):
    """Keep L1's fixed engineering problem; apply this case's explicit guide policy."""
    checks = [c for c in benchmark.check_candidate(model) if c['id'] != 'fixed_supports']
    endpoints = set(benchmark._endpoints(model).values())
    restraints = [{k: v for k, v in support.to_dict().items() if k != 'id'} for support in model.supports]
    anchors = [r for r in restraints if r['node'] in endpoints]
    guides = [r for r in restraints if r['node'] not in endpoints]
    correct = (len(anchors) == 2 and all({'node': node, 'type': 'anchor'} in anchors for node in endpoints)
               and len(guides) <= CASE['support_policy']['max_guides']
               and len({r['node'] for r in guides}) == len(guides)
               and all(r['node'] in model.nodes and set(r) == {'node', 'type', 'direction'}
                       and r['type'] == 'guide' and r['direction'] in CASE['support_policy']['directions']
                       for r in guides))
    checks.append(benchmark._check('allowed_supports', correct,
                  'Keep nozzle anchors; allow up to four distinct interior ideal Y/Z ground guides.'))
    return checks


def _implementation():
    return {name: digest_file(REPO / name) for name in IMPLEMENTATION}


def create_session(root: Path, *, max_solver_calls: int = 10):
    root = Path(root).absolute()
    no_links(root)
    if root.resolve().is_relative_to(REPO) or any((parent / '.git').exists() for parent in (root, *root.parents)):
        raise ValueError('Session evidence must stay outside the source checkout.')
    if type(max_solver_calls) is not int or max_solver_calls < 0:
        raise ValueError('max_solver_calls must be a nonnegative integer')
    root.mkdir(parents=True, exist_ok=False)
    archive = ArtifactStore(root)
    atomic_json(root / 'requirements.json', CASE)
    source = archive.capture_files(root, ('requirements.json',))
    evaluator = archive.capture_files(REPO, IMPLEMENTATION)
    manifest = {'schema': SCHEMA, 'run_id': 'R' + uuid.uuid4().hex,
                'mode': 'authored-piping', 'case_id': CASE['id'], 'scope': CASE['scope'],
                'source_manifest_ref': source, 'evaluator_manifest_ref': evaluator,
                'requirements_digest': digest(CASE), 'implementation': _implementation(),
                'max_solver_calls': max_solver_calls,
                'settings': {'operations': ['Hot'], 'solver_options': CASE['solver_options'], 'volume_export': None}}
    with History.create(root / 'history.sqlite3', manifest):
        pass
    return manifest


def _open(root):
    root = Path(root).absolute()
    no_links(root)
    if not (root / 'history.sqlite3').is_file():
        raise FileNotFoundError('Initialize an authored session first.')
    return ArtifactStore(root)


def _validate(archive, history):
    manifest = history.manifest()
    if manifest.get('mode') != 'authored-piping':
        raise ValueError('Expected an authored piping session')
    if (manifest['requirements_digest'] != digest(CASE)
            or manifest['implementation'] != _implementation()
            or digest(json.loads(archive.path('requirements.json').read_text())) != digest(CASE)):
        raise ValueError('Session frozen requirements/evaluator changed; initialize a new session.')
    archive.verify_inventory(manifest['source_manifest_ref'])
    archive.verify_inventory(manifest['evaluator_manifest_ref'])


def _source_files(archive, candidate):
    inventory = archive.verify_inventory(candidate.parameters['source_manifest_ref'])
    return {entry['logical_name']: archive.path(entry['path']) for entry in inventory['files']}


def _source_events(archive, history, candidate):
    files = _source_files(archive, candidate)
    recorded = {(e['candidate_id'], e['payload'].get('parent_id')) for e in history.events()
                if e['kind'] == 'candidate.source_diff'}
    candidates = {c.id: c for c in history.candidates()}
    for parent in candidate.parent_ids:
        if (candidate.id, parent) in recorded:
            continue
        before = _source_files(archive, candidates[parent])
        diffs = {}
        for name in sorted(set(before) | set(files)):
            old = before[name].read_text(encoding='utf-8-sig').splitlines(True) if name in before else []
            new = files[name].read_text(encoding='utf-8-sig').splitlines(True) if name in files else []
            if old != new:
                diffs[name] = ''.join(difflib.unified_diff(old, new, fromfile=f'{parent}/{name}', tofile=f'{candidate.id}/{name}'))
        history.append('candidate.source_diff', {'parent_id': parent, 'files': diffs}, candidate.id)
    return files


def _reaction_specs(model):
    return tuple(CheckSpec(f'{label}_{quantity}', 'user_evaluator', True, ('Hot',), (f'node:{node}',),
                           CASE[f'{quantity}_limit_{suffix}'], unit, {})
                 for label, node in benchmark._endpoints(model).items()
                 for quantity, suffix, unit in (('force', 'N', 'N'), ('moment', 'Nm', 'N m')))


def _reactions(context):
    run = context.runs['Hot']
    evidence = (str(Path(run.study.work_dir) / 'study_reac.csv'),)
    return tuple(CheckResult(check['id'], check['status'], True, 'code_aster',
                   'reaction_unavailable' if check['status'] == 'unknown' else
                   'reaction_limit_exceeded' if check['status'] == 'fail' else 'reaction_within_limit',
                   check['message'], (check['entity'],), evidence, {'components': check['components']},
                   operation='Hot', result_state_id=check['result_state_id'], measured_value=check['value'],
                   limit=check['limit'], unit=check['unit'], comparator='max')
                 for check in benchmark.reaction_checks(context.model, run))


def _decision(history, decision):
    history.append('candidate.decision', decision.to_dict(), decision.candidate_id)
    return decision.to_dict()


def _recover(archive, history):
    events = history.events()
    decisions = {e['payload']['evaluation_id'] for e in events if e['kind'] == 'candidate.decision'}
    builds = {e['candidate_id']: e['payload'] for e in events if e['kind'] == 'candidate.built'}
    for event in events:
        if event['kind'] not in {'evaluation.completed', 'evaluation.failed', 'evaluation.interrupted'}:
            continue
        evaluation = Evaluation.from_dict(event['payload'])
        if evaluation.id not in decisions:
            archive.verify_inventory(evaluation.evidence_manifest_ref)
            specs = tuple(CheckSpec.from_dict(s) for s in builds[evaluation.candidate_id]['check_specs'])
            _decision(history, decide(evaluation, specs, ('Hot',)))
    archive.recover(history)
    # Recovery publishes no invented evaluation or measurement.
    for event in history.events():
        if event['kind'] == 'attempt.recovered':
            identifier = 'recovered-' + event['payload']['attempt_id']
            if identifier not in decisions:
                _decision(history, Decision(event['candidate_id'], identifier, 'incomplete', ('attempt_interrupted',)))
                decisions.add(identifier)


def recover_session(root):
    archive = _open(root)
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        _validate(archive, history)
        _recover(archive, history)
    return inspect_history(root)


def _evaluate(archive, history, candidate):
    files = _source_events(archive, history, candidate)
    source = files['model.py']
    parameters_path = archive.path(f'candidates/{candidate.id}/parameters.json')
    if not parameters_path.exists():
        atomic_json(parameters_path, candidate.parameters)
    try:
        namespace = load_project(source.parent).run_model()
        dependencies = {Path(p).resolve() for p in namespace['__tuba_project_dependencies__']}
        if not dependencies <= {p.resolve() for p in files.values()}:
            raise ValueError('Candidate loaded undeclared local dependencies; snapshot them explicitly.')
        model = namespace['model']
        checks = tuple(CheckResult(c['id'], c['status'], True, 'model',
                                  'requirement_satisfied' if c['status'] == 'pass' else 'requirement_changed', c['message'])
                       for c in design_checks(model))
        specs = (CheckSpec('cold.model', 'cold_model', True, (), (), None, None, {}),
                 CheckSpec('evidence.Hot', 'evidence_verified', True, ('Hot',), (), None, None, {}),
                 *(CheckSpec(c.constraint_id, 'design_requirement', True, (), (), None, None, {}) for c in checks),
                 *_reaction_specs(model))
        settings = StudySettings(('Hot',), dict(CASE['solver_options']), None)
        # Only well-formed candidates need solver export identities/objectives.
        valid = all(c.verdict == 'pass' for c in checks)
        data = {'design_digest': digest(model.to_dict()), 'source_manifest_ref': candidate.parameters['source_manifest_ref'],
                'solver_identities': {'Hot': expected_identity(model, 'Hot', solver_options=settings.solver_options).to_dict()} if valid else {},
                'objectives': objective_values(model, ('pipe_length_m', 'bend_count', 'support_count')) if valid else {},
                'check_specs': [s.to_dict() for s in specs]}
        builds = [e['payload'] for e in history.events() if e['kind'] == 'candidate.built' and e['candidate_id'] == candidate.id]
        if builds and builds[-1]['design_digest'] != data['design_digest']:
            raise ValueError('Retained source no longer reproduces its candidate model')
        model_ref = f'candidates/{candidate.id}/model.json'
        if archive.path(model_ref).exists():
            if digest(json.loads(archive.path(model_ref).read_text())) != data['design_digest']:
                raise ValueError('Retained model integrity failure')
        else:
            archive.save_model(candidate.id, model)
        if not builds:
            history.append('candidate.built', data | {'model_ref': model_ref}, candidate.id)
    except (OSError, sqlite3.Error):
        raise
    except Exception as exc:
        # Source errors are not measured engineering rejections.
        return _decision(history, Decision(candidate.id, 'build-' + uuid.uuid4().hex, 'evaluation_failed',
                          ('candidate_build_failed',), details={'type': type(exc).__name__, 'message': str(exc)}))
    context = EvaluationContext({'__search_model_script__': source.read_text(encoding='utf-8-sig')}, settings, specs, _reactions)
    if valid and sum(e['kind'] == 'solver.invoked' for e in history.events()) >= history.manifest()['max_solver_calls']:
        return _decision(history, Decision(candidate.id, 'budget-' + uuid.uuid4().hex, 'deferred', ('solver_call_budget',)))

    class RecordedSolver:
        def solve_exported_study(self, model, study):
            history.append('solver.invoked', {'operation': 'Hot', 'attempt_id': Path(study.work_dir).parent.name}, candidate.id)
            return settings.solver(study.work_dir).solve_exported_study(model, study)

    evaluation = evaluate_candidate(candidate, model, context, archive=archive, history=history,
                                    solver=RecordedSolver(), pre_checks=checks)
    return _decision(history, decide(evaluation, specs, settings.operations))


def submit(root, project, candidate_id, *, parents=(), intent, dependencies=()):
    archive = _open(root)
    project = Path(project).absolute()
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        _validate(archive, history)
        _recover(archive, history)
        existing = {c.id for c in history.candidates()}
        if candidate_id in existing:
            raise ValueError('Candidate already exists; revise with a new ID or retry retained source.')
        if not set(parents) <= existing:
            raise ValueError('Parents must already exist in this session')
        # Validate metadata before retaining files; copy only declared Python units.
        Candidate(candidate_id, tuple(parents), {}, intent)
        paths = ('model.py', *dependencies)
        if any(Path(p).is_absolute() or '..' in Path(p).parts or Path(p).suffix != '.py'
               or Path(p).name in {'study.py', 'search.py'} for p in paths):
            raise ValueError('Dependencies must be Python units; study/search policies are evaluator-owned.')
        reference = archive.capture_files(project, paths)
        candidate = Candidate(candidate_id, tuple(parents), {'source_manifest_ref': reference}, intent)
        history.record_candidate(candidate)
        return _evaluate(archive, history, candidate)


def retry(root, candidate_id):
    archive = _open(root)
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        _validate(archive, history)
        _recover(archive, history)
        candidate = next((c for c in history.candidates() if c.id == candidate_id), None)
        if candidate is None:
            raise ValueError('Unknown candidate')
        decisions = [e['payload'] for e in history.events() if e['kind'] == 'candidate.decision' and e['candidate_id'] == candidate_id]
        if decisions and decisions[-1]['outcome'] not in {'incomplete', 'evaluation_failed', 'deferred'}:
            raise ValueError('Completed candidate: submit a revision with a new ID.')
        return _evaluate(archive, history, candidate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('session', type=Path)
    init.add_argument('--max-solver-calls', type=int, default=10)
    propose = commands.add_parser('submit')
    propose.add_argument('session', type=Path)
    propose.add_argument('project', type=Path, help='Folder with procedural model.py')
    propose.add_argument('candidate_id')
    propose.add_argument('--parent', action='append', default=[])
    propose.add_argument('--intent', required=True)
    propose.add_argument('--dependency', action='append', default=[])
    again = commands.add_parser('retry')
    again.add_argument('session', type=Path)
    again.add_argument('candidate_id')
    recover = commands.add_parser('recover')
    recover.add_argument('session', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = create_session(args.session, max_solver_calls=args.max_solver_calls)
        elif args.command == 'submit':
            result = submit(args.session, args.project, args.candidate_id, parents=args.parent,
                            intent=args.intent, dependencies=args.dependency)
        elif args.command == 'retry':
            result = retry(args.session, args.candidate_id)
        else:
            snapshot = recover_session(args.session)
            result = {'candidates': [{k: row[k] for k in ('id', 'outcome', 'reason_codes')} for row in snapshot['candidates']]}
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'error: {exc}\n')
    print(json.dumps(result, indent=2))
    return 1 if result.get('outcome') in {'evaluation_failed', 'incomplete', 'deferred', 'rejected_constraint'} else 0


if __name__ == '__main__':
    raise SystemExit(main())
