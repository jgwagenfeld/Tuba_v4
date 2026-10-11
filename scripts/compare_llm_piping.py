"""Frozen multi-case campaigns using authored search sessions and real Code_Aster.

No provider is invoked here. External designers use start/submit/finish; reported
provider usage is caller supplied. Reference runs contain no model API calls.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import uuid

from scripts import iterate_llm_piping as iteration
from scripts.piping_comparison_cases import CASE_IDS, get_case
from tuba.search.artifacts import ArtifactStore, atomic_json, no_links
from tuba.search.contracts import CheckSpec, Evaluation, decide, safe_id
from tuba.search.export import inspect_history
from tuba.search.history import History, SCHEMA
from tuba.search.run import coordinator, digest

REPO = Path(__file__).resolve().parents[1]
STARTER = 'examples/llm-piping-iteration/model.py'
IMPLEMENTATION = (*iteration.IMPLEMENTATION, 'scripts/compare_llm_piping.py')
BUDGETS = {'max_proposals': 3, 'max_solver_calls': 3, 'max_wall_seconds': 1800}
REFERENCE = {'id': 'ascending-loop-v1', 'kind': 'reference', 'representation': 'fixed-family',
             'provider': None, 'model': None, 'settings': {'rises_m': [.4, .8, 1.6]},
             'prompt': 'Try rises 0.4, 0.8, 1.6 m in order; stop at first feasible. Keep two Z guides.',
             'tools': ['submit_trial']}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _elapsed(start, end=None):
    return max(0., (datetime.fromisoformat(end or _now()) - datetime.fromisoformat(start)).total_seconds())


def _implementation():
    return {name: hashlib.sha256((REPO / name).read_text(encoding='utf-8-sig').encode()).hexdigest()
            for name in IMPLEMENTATION}


def _methods(methods):
    methods = json.loads(json.dumps(methods, allow_nan=False))
    identifiers = set()
    for method in methods:
        safe_id(method['id'])
        if method['id'] in identifiers:
            raise ValueError('Duplicate method id')
        identifiers.add(method['id'])
        if method['kind'] == 'reference':
            if method != REFERENCE:
                raise ValueError('Reference method must match the versioned reference policy')
        elif method['kind'] == 'llm':
            for field in ('provider', 'model', 'prompt'):
                if not isinstance(method.get(field), str) or not method[field].strip():
                    raise ValueError(f'LLM method requires pinned {field}')
            if not isinstance(method.get('settings'), dict) or not method.get('tools'):
                raise ValueError('LLM method requires settings and tools')
            if not all(isinstance(t, str) and t for t in method['tools']):
                raise ValueError('Tool identities must be nonempty strings')
        else:
            raise ValueError('Expected reference or llm method')
        if method['representation'] not in {'fixed-family', 'free-topology'}:
            raise ValueError('Expected fixed-family or free-topology representation')
    if not methods:
        raise ValueError('At least one method is required')
    return methods


def create_campaign(root, *, repeats=2, case_ids=CASE_IDS, methods=None, budgets=None):
    """Freeze all trial slots and inputs before starting any timed design work."""
    methods = _methods([REFERENCE] if methods is None else methods)
    budgets = dict(BUDGETS if budgets is None else budgets)
    if set(budgets) != set(BUDGETS) or any(type(v) is not int or v <= 0 for v in budgets.values()):
        raise ValueError('Expected positive integer proposal, solver-call and wall-second budgets')
    if type(repeats) is not int or repeats <= 0 or not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError('Expected positive repeats and unique case IDs')
    cases = {identifier: get_case(identifier) for identifier in case_ids}
    trials = [{'id': f'T{index:03}', 'case_id': case_id, 'method_id': method['id'], 'repeat': repeat}
              for index, (case_id, method, repeat) in enumerate(
                  ((c, m, r) for c in case_ids for m in methods for r in range(1, repeats + 1)), 1)]
    root = Path(root).absolute()
    no_links(root)
    if any((p / '.git').exists() for p in (root, *root.parents)):
        raise ValueError('Campaign evidence must stay outside source checkouts')
    root.mkdir(parents=True, exist_ok=False)
    archive = ArtifactStore(root)
    source = archive.capture_files(REPO, (STARTER,))
    evaluator = archive.capture_files(REPO, IMPLEMENTATION)
    manifest = {'schema': SCHEMA, 'mode': 'piping-comparison', 'run_id': 'B' + uuid.uuid4().hex,
                'cases': cases, 'methods': methods, 'budgets': budgets, 'trials': trials,
                'source_manifest_ref': source, 'evaluator_manifest_ref': evaluator,
                'implementation': _implementation(), 'created_at': _now(),
                'stop_rule': 'first feasible or budget exhausted',
                'scope': 'Thermal research only; no piping-code or industrial qualification.'}
    with History.create(root / 'history.sqlite3', manifest):
        pass
    return manifest


def _open(root):
    archive = ArtifactStore(Path(root).absolute())
    no_links(archive.root)
    if not archive.path('history.sqlite3').is_file():
        raise ValueError('Initialize a campaign first')
    return archive


def _validate(archive, history, *, writing=False):
    manifest = history.manifest()
    if manifest.get('mode') != 'piping-comparison':
        raise ValueError('Expected a piping comparison campaign')
    archive.verify_inventory(manifest['source_manifest_ref'])
    archive.verify_inventory(manifest['evaluator_manifest_ref'])
    if writing and (manifest['implementation'] != _implementation()
                    or any(value != get_case(key) for key, value in manifest['cases'].items())):
        raise ValueError('Frozen campaign implementation/cases changed; initialize a new campaign')
    return manifest


def _trial(manifest, identifier):
    trial = next((t for t in manifest['trials'] if t['id'] == identifier), None)
    if trial is None:
        raise ValueError('Unknown trial ID')
    method = next(m for m in manifest['methods'] if m['id'] == trial['method_id'])
    return trial, method


def _lifecycle(history, identifier):
    events = [e for e in history.events() if e['payload'].get('trial_id') == identifier]
    start = next((e for e in events if e['kind'] == 'trial.started'), None)
    finish = next((e for e in events if e['kind'] == 'trial.finished'), None)
    return start, finish


def _binding(history, trial, recorded):
    bindings = [e['payload'] for e in history.events() if e['kind'] == 'trial.session_bound'
                and e['payload']['trial_id'] == trial['id']]
    if (len(bindings) != 1 or bindings[0]['session_run_id'] != recorded['run_id']
            or bindings[0]['manifest_digest'] != digest(recorded)):
        raise ValueError('Trial session identity does not match its campaign binding')


def _session(archive, manifest, trial, history):
    root = archive.path(f"trials/{trial['id']}")
    with History.open(root / 'history.sqlite3', readonly=True) as own:
        case = iteration._validate(ArtifactStore(root), own)
        recorded = own.manifest()
        _binding(history, trial, recorded)
        if case != manifest['cases'][trial['case_id']] or recorded['max_solver_calls'] != manifest['budgets']['max_solver_calls']:
            raise ValueError('Trial requirements disagree with campaign')
    return root


def _starter(archive, manifest, case_id, rise=.4):
    inventory = archive.verify_inventory(manifest['source_manifest_ref'])
    source = archive.path(next(f['path'] for f in inventory['files'] if f['logical_name'] == STARTER)).read_text(encoding='utf-8-sig')
    return source.replace('LOOP_RISE = 0.4', f'LOOP_RISE = {rise!r}').replace(
        'temperature=200.', f"temperature={manifest['cases'][case_id]['operation']['temperature']!r}")


def start_trial(root, trial_id):
    """Start the timer before calling an external designer; repeat calls resume it."""
    archive = _open(root)
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        manifest = _validate(archive, history, writing=True)
        trial, method = _trial(manifest, trial_id)
        start, finish = _lifecycle(history, trial_id)
        if finish:
            raise ValueError('Trial already finished')
        if start is None:
            history.append('trial.started', {'trial_id': trial_id})
        session = archive.path(f'trials/{trial_id}')
        if not session.exists():
            iteration.create_session(session, case_id=trial['case_id'],
                                     max_solver_calls=manifest['budgets']['max_solver_calls'])
        elif not (session / 'history.sqlite3').is_file():
            raise ValueError('Trial initialization interrupted; retain this incomplete campaign and start a fresh one')
        bindings = [e['payload'] for e in history.events() if e['kind'] == 'trial.session_bound']
        if not any(b['trial_id'] == trial_id for b in bindings):
            with History.open(session / 'history.sqlite3', readonly=True) as own:
                iteration._validate(ArtifactStore(session), own)
                recorded = own.manifest()
                if own.events() or own.candidates() or any(b['session_run_id'] == recorded['run_id'] for b in bindings):
                    raise ValueError('Cannot bind trial identity to a previously used session')
            history.append('trial.session_bound', {'trial_id': trial_id, 'session_run_id': recorded['run_id'],
                                                   'manifest_digest': digest(recorded)})
        _session(archive, manifest, trial, history)
        return {'trial': trial, 'method': method, 'requirements': manifest['cases'][trial['case_id']],
                'budgets': manifest['budgets'], 'session': str(session),
                'starter_source': _starter(archive, manifest, trial['case_id'])}


def _usage(usage, method):
    if usage is None:
        return None
    if method['kind'] != 'llm' or not isinstance(usage, dict):
        raise ValueError('Model usage is only valid for an LLM method')
    if usage.get('model') != method['model'] or not isinstance(usage.get('source'), str) or not usage['source'].strip():
        raise ValueError('Model usage requires matching model and provenance source')
    for key in ('input_tokens', 'output_tokens', 'cost_usd'):
        value = usage.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                                  or (key.endswith('tokens') and type(value) is not int)):
            raise ValueError(f'Invalid usage {key}')
    return json.loads(json.dumps(usage, allow_nan=False))


def submit_trial(root, trial_id, project, *, intent, dependencies=(), usage=None):
    """Retain a proposal, including bad source; enforce admission budgets.

    Usage covers design work since the previous proposal, including failed model
    calls. The external driver owns that accounting; absent fields remain unknown.
    """
    archive = _open(root)
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        manifest = _validate(archive, history, writing=True)
        trial, method = _trial(manifest, trial_id)
        start, finish = _lifecycle(history, trial_id)
        if finish:
            raise ValueError('Trial already finished')
        if start is None:
            raise ValueError('Start the trial before design work')
        usage = _usage(usage, method)
        session = _session(archive, manifest, trial, history)
        # A completed evaluation may still need its decision after an interruption.
        iteration.recover_session(session)
        with History.open(session / 'history.sqlite3', readonly=True) as own:
            events, candidates = own.events(), own.candidates()
        proposals = sum(e['kind'] == 'comparison.proposal' for e in events)
        budget = manifest['budgets']
        if (proposals >= budget['max_proposals'] or _elapsed(start['timestamp']) >= budget['max_wall_seconds']
                or sum(e['kind'] == 'solver.invoked' for e in events) >= budget['max_solver_calls']):
            with History.open(session / 'history.sqlite3') as own:
                own.append('comparison.admission_rejected', {'usage': usage, 'intent': intent, 'reason': 'budget'})
            raise ValueError('Trial admission budget exhausted')
        if any(e['kind'] == 'candidate.decision' and e['payload']['outcome'] == 'feasible_retained' for e in events):
            with History.open(session / 'history.sqlite3') as own:
                own.append('comparison.admission_rejected', {'usage': usage, 'intent': intent, 'reason': 'first feasible'})
            raise ValueError('Trial stop rule reached: first feasible candidate')
        candidate_id = f'C{proposals + 1:03}'
        with History.open(session / 'history.sqlite3') as own:
            own.append('comparison.proposal', {'proposal_id': candidate_id, 'usage': usage, 'intent': intent})
        try:
            return iteration.submit(session, project, candidate_id, intent=intent, dependencies=dependencies,
                                    parents=(candidates[-1].id,) if candidates else ())
        except BaseException as exc:
            with History.open(session / 'history.sqlite3') as own:
                own.append('comparison.submission_failed', {'proposal_id': candidate_id, 'type': type(exc).__name__,
                                                           'message': str(exc)})
            raise


def finish_trial(root, trial_id, *, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('A stop reason is required')
    archive = _open(root)
    with coordinator(archive), History.open(archive.path('history.sqlite3')) as history:
        manifest = _validate(archive, history, writing=True)
        trial, _ = _trial(manifest, trial_id)
        start, finish = _lifecycle(history, trial_id)
        if start is None:
            raise ValueError('Trial has not started')
        if finish:
            raise ValueError('Trial already finished')
        iteration.recover_session(_session(archive, manifest, trial, history))
        history.append('trial.finished', {'trial_id': trial_id, 'reason': reason})


def _qualified(archive, snapshot):
    """Return verified feasible decisions; never trust a decision label alone."""
    feasible, issues = [], []
    archive.verify_inventory(snapshot['run']['source_manifest_ref'])
    archive.verify_inventory(snapshot['run']['evaluator_manifest_ref'])
    for row in snapshot['candidates']:
        try:
            archive.verify_inventory(row['parameters']['source_manifest_ref'])
            build = row['build']
            if build and digest(json.loads(archive.path(build['model_ref']).read_text())) != build['design_digest']:
                raise ValueError('Compiled model integrity failure')
            for decision in row['decisions']:
                if decision['outcome'] != 'feasible_retained':
                    continue
                evaluation = next(e for e in row['evaluations'] if e['id'] == decision['evaluation_id'])
                if not evaluation.get('evidence_manifest_sha256'):
                    raise ValueError('Missing sealed evidence fingerprint')
                archive.verify_inventory(evaluation['evidence_manifest_ref'], expected_sha256=evaluation['evidence_manifest_sha256'])
                specs = tuple(CheckSpec.from_dict(s) for s in build['check_specs'])
                if decide(Evaluation.from_dict(evaluation), specs, ('Hot',)).outcome != 'feasible_retained':
                    raise ValueError('Decision disagrees with required checks')
                feasible.append((decision['sequence'], row['id'], build['objectives']))
        except (OSError, ValueError, KeyError, StopIteration) as exc:
            issues.append({'candidate_id': row['id'], 'message': str(exc)})
    return sorted(feasible), issues


def _trial_report(archive, manifest, history, trial, method):
    start, finish = _lifecycle(history, trial['id'])
    row = {**trial, 'representation': method['representation'], 'kind': method['kind'],
           'status': 'not_started', 'feasible': False, 'first_feasible_seconds': None,
           'first_feasible_solver_calls': None, 'wall_seconds': None, 'best_objectives': None,
           'solver_calls': 0, 'proposals': 0, 'submission_failures': 0, 'rejected_submissions': 0, 'candidate_outcomes': {},
           'model_cost_usd': None, 'input_tokens': None, 'output_tokens': None,
           'usage_basis': 'not_started', 'integrity_issues': []}
    if start is None:
        return row
    row.update(status='finished' if finish else 'open',
               stop_reason=finish['payload']['reason'] if finish else None,
               wall_seconds=_elapsed(start['timestamp'], finish['timestamp'] if finish else None))
    session = archive.path(f"trials/{trial['id']}")
    if not (session / 'history.sqlite3').is_file():
        row.update(status='finished' if finish else 'initialization_incomplete', usage_basis='unknown',
                   integrity_issues=[{'message': 'Trial history is missing'}])
        return row
    try:
        snapshot = inspect_history(session)
    except (OSError, ValueError, sqlite3.Error, KeyError) as exc:
        row.update(status='finished' if finish else 'initialization_incomplete', usage_basis='unknown',
                   integrity_issues=[{'message': f'Trial history unavailable: {exc}'}])
        return row
    try:
        _binding(history, trial, snapshot['run'])
    except ValueError as exc:
        row.update(status='finished' if finish else 'integrity_failed', usage_basis='unknown',
                   integrity_issues=[{'message': str(exc)}])
        return row
    events = snapshot['events']
    proposals = [e['payload'] for e in events if e['kind'] == 'comparison.proposal']
    rejected = [e['payload'] for e in events if e['kind'] == 'comparison.admission_rejected']
    row.update(proposals=len(proposals), solver_calls=sum(e['kind'] == 'solver.invoked' for e in events),
               rejected_submissions=len(rejected),
               submission_failures=sum(e['kind'] == 'comparison.submission_failed' for e in events),
               candidate_outcomes=dict(Counter(c['outcome'] for c in snapshot['candidates'])))
    if method['kind'] == 'reference':
        row.update(model_cost_usd=0., input_tokens=0, output_tokens=0, usage_basis='no_model_calls')
    else:
        submissions = proposals + rejected
        row['usage_basis'] = 'caller_reported' if submissions and all(p['usage'] is not None for p in submissions) else 'unknown'
        for column, key in (('model_cost_usd', 'cost_usd'), ('input_tokens', 'input_tokens'), ('output_tokens', 'output_tokens')):
            values = [(p['usage'] or {}).get(key) for p in submissions]
            row[column] = sum(values) if values and all(v is not None for v in values) else None
    try:
        recorded = snapshot['run']
        if (recorded['requirements_digest'] != digest(manifest['cases'][trial['case_id']])
                or recorded['max_solver_calls'] != manifest['budgets']['max_solver_calls']):
            raise ValueError('Trial requirements disagree with campaign')
        feasible, row['integrity_issues'] = _qualified(ArtifactStore(session), snapshot)
        if feasible:
            first_seq, identifier, objectives = feasible[0]
            event = next(e for e in events if e['sequence'] == first_seq)
            row.update(feasible=True, first_feasible_candidate=identifier,
                       first_feasible_seconds=_elapsed(start['timestamp'], event['timestamp']), best_objectives=objectives,
                       first_feasible_solver_calls=sum(e['kind'] == 'solver.invoked' and e['sequence'] <= first_seq for e in events))
    except (OSError, ValueError, KeyError) as exc:
        row['integrity_issues'].append({'message': str(exc)})
    return row


def report_campaign(root):
    """Read-only projection; running/unstarted trials are not completed failures."""
    archive = _open(root)
    with History.open(archive.path('history.sqlite3'), readonly=True) as history:
        manifest = _validate(archive, history)
        rows = [_trial_report(archive, manifest, history, trial, _trial(manifest, trial['id'])[1])
                for trial in manifest['trials']]
    groups = []
    for key in dict.fromkeys((r['case_id'], r['method_id'], r['representation']) for r in rows):
        members = [r for r in rows if (r['case_id'], r['method_id'], r['representation']) == key]
        finished = [r for r in members if r['status'] == 'finished']
        groups.append(dict(zip(('case_id', 'method_id', 'representation'), key)) | {
            'planned_runs': len(members), 'started_runs': sum(r['status'] != 'not_started' for r in members),
            'finished_runs': len(finished), 'feasible_finished_runs': sum(r['feasible'] for r in finished),
            'feasibility_rate_finished': sum(r['feasible'] for r in finished) / len(finished) if finished else None})
    return {'schema': 'tuba.piping-comparison.report.v1', 'campaign_id': manifest['run_id'],
            'scope': manifest['scope'], 'budgets': manifest['budgets'], 'methods': manifest['methods'],
            'trials': rows, 'groups': groups,
            'llm_trials_run': sum(r['kind'] == 'llm' and r['status'] != 'not_started' for r in rows)}


def run_reference(root):
    """Run/resume only the frozen deterministic slots, using fresh solver attempts."""
    archive = _open(root)
    with History.open(archive.path('history.sqlite3'), readonly=True) as history:
        manifest = _validate(archive, history, writing=True)
    for trial in manifest['trials']:
        _, method = _trial(manifest, trial['id'])
        if method['kind'] != 'reference':
            continue
        with History.open(archive.path('history.sqlite3'), readonly=True) as history:
            if _lifecycle(history, trial['id'])[1]:
                continue
        start_trial(root, trial['id'])
        session = archive.path(f"trials/{trial['id']}")
        iteration.recover_session(session)
        with History.open(session / 'history.sqlite3', readonly=True) as history:
            events = history.events()
        count = sum(e['kind'] == 'comparison.proposal' for e in events)
        reason = 'reference sequence exhausted'
        if any(e['kind'] == 'candidate.decision' and e['payload']['outcome'] == 'feasible_retained' for e in events):
            reason = 'first feasible'
        else:
            for index, rise in enumerate(method['settings']['rises_m'][count:], count + 1):
                project = archive.path(f"proposals/{trial['id']}/P{index:03}")
                project.mkdir(parents=True, exist_ok=True)
                source = _starter(archive, manifest, trial['case_id'], rise)
                target = project / 'model.py'
                if target.exists() and target.read_text(encoding='utf-8') != source:
                    raise ValueError('Reference source changed during resume')
                target.write_text(source, encoding='utf-8')
                try:
                    result = submit_trial(root, trial['id'], project, intent=f'Fixed reference rise {rise} m')
                except ValueError as exc:
                    if 'admission budget' not in str(exc):
                        raise
                    reason = 'admission budget exhausted'
                    break
                print(json.dumps({'trial': trial['id'], 'candidate': index, 'outcome': result['outcome']}), flush=True)
                if result['outcome'] == 'feasible_retained':
                    reason = 'first feasible'
                    break
        finish_trial(root, trial['id'], reason=reason)
    return report_campaign(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'reference', 'report'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--output', type=Path, help='Optional new JSON report file outside the checkout')
    args = parser.parse_args(argv)
    if args.output:
        no_links(args.output.absolute())
        if args.output.exists() or any((p / '.git').exists() for p in args.output.absolute().parents):
            parser.error('Output must be a new file outside source checkouts')
    result = create_campaign(args.root, repeats=args.repeats) if args.command == 'init' else (
        run_reference(args.root) if args.command == 'reference' else report_campaign(args.root))
    if args.output:
        atomic_json(args.output, result)
    else:
        print(json.dumps(result, indent=2, allow_nan=False))
    return int(args.command == 'reference' and any(
        r['kind'] == 'reference' and (r['status'] != 'finished' or not r['feasible']) for r in result['trials']))


if __name__ == '__main__':
    raise SystemExit(main())
