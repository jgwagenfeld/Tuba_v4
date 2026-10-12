import { parameterDiff, replayAt } from './searchReplay.js';

// A search movie follows evaluations, not individual result fields. Keep the
// cursor at the decision that was actually known, and group reasons only when
// they belong to the same geometry/solver state.
export function iterationFrames(manifest, start, end, hold) {
  const frames = [], seen = new Set();
  let previous = null;
  for (const event of manifest.events) {
    if (event.sequence > end) break;
    if (!['candidate.decision', 'evaluation.interrupted', 'evaluation.failed', 'attempt.recovered', 'run.completed'].includes(event.kind)) continue;
    const snapshot = replayAt(manifest, event.sequence);
    const candidate = snapshot.candidates.find(c => c.id === (event.candidate_id ?? event.payload?.selected_candidate_id));
    if (!candidate) continue;
    const selection = event.kind === 'run.completed';
    const exactId = event.kind === 'candidate.decision' ? event.payload.evaluation_id
      : event.kind === 'attempt.recovered' ? `recovered:${event.payload.attempt_id}` : event.payload.id;
    const evaluation = exactId ? candidate.evaluations.find(e => e.id === exactId) : candidate.evaluations.at(-1);
    const identity = `${candidate.id}:${evaluation?.id ?? event.kind}`;
    // Later objective decisions update the final selection, not another test.
    if (!selection && seen.has(identity)) continue;
    if (!selection) seen.add(identity);
    const changes = parameterDiff(candidate, previous);
    const referenceId = previous?.id ?? null;
    if (!selection) previous = candidate;
    if (event.sequence < start) continue;
    const allChecks = evaluation?.checks ?? [];
    const completed = evaluation?.completed_operations ?? [];
    const failures = allChecks.map((check, index) => ({ check, index })).filter(c => c.check.verdict === 'fail');
    const scopes = new Map();
    if (!selection) for (const entry of failures) {
      const fluid_results = entry.check.basis === 'openmodelica';
      const operation = entry.check.operation ?? (fluid_results ? evaluation?.operations?.[0] ?? entry.check.details?.scenario_id ?? null : null);
      const result_state_id = entry.check.result_state_id ?? null;
      const key = JSON.stringify([fluid_results, operation, result_state_id]);
      if (!scopes.has(key)) scopes.set(key, { operation, result_state_id, fluid_results, check: entry.check, check_index: entry.index });
    }
    if (!scopes.size) {
      const hydraulic = allChecks.find(c => c.basis === 'openmodelica' && ['pass', 'fail'].includes(c.verdict));
      const fluid_results = !completed.length && Boolean(hydraulic);
      const operation = fluid_results ? hydraulic.operation ?? evaluation?.operations?.[0] ?? hydraulic.details?.scenario_id ?? null
        : completed.includes('Hot') ? 'Hot' : completed.at(-1) ?? null;
      const result_state_id = fluid_results ? null : allChecks.find(c => c.operation === operation && c.result_state_id)?.result_state_id ?? null;
      scopes.set('overview', { operation, result_state_id, fluid_results, check: null, check_index: null });
    }
    const outcome = selection ? candidate.outcome : event.kind === 'evaluation.interrupted' ? 'interrupted'
      : event.kind === 'evaluation.failed' ? 'evaluation_failed' : evaluation?.outcome ?? candidate.outcome;
    const finalists = selection ? snapshot.candidates.filter(c => ['selected', 'feasible_not_selected'].includes(c.outcome)).map(c => {
      const decision = c.decisions.at(-1);
      return { candidate_id: c.id, outcome: c.outcome, reason_codes: decision.reason_codes,
        details: decision.details, objectives: decision.details?.objectives ?? c.build?.objectives ?? {} };
    }) : [];
    for (const scope of scopes.values()) {
      const native = Boolean(!scope.fluid_results && scope.operation && completed.includes(scope.operation));
      // Unsolved/recovered attempts use their own reference layout. No review
      // from a later successful attempt can be substituted here.
      const view = native || scope.fluid_results ? evaluation?.review : candidate.preview;
      const checks = allChecks.filter(c => scope.fluid_results ? c.basis === 'openmodelica'
        : c.basis !== 'openmodelica' && (c.operation ?? null) === scope.operation &&
          (c.result_state_id ?? null) === scope.result_state_id);
      const caption = [`${candidate.id} · ${selection ? 'Final selection' : 'Piping iteration'}`,
        `Recorded outcome: ${outcome}`, `Proposal intent: ${candidate.intent ?? 'not recorded'}`,
        `Parameters: ${JSON.stringify(candidate.parameters ?? {})}`,
        `Search time (UTC): ${event.timestamp ?? event.at_utc ?? 'not recorded'}`,
        scope.fluid_results ? 'Recorded OpenModelica hydraulic evidence' : native ? 'Recorded Code_Aster evidence' : 'Reference geometry — no solver results'];
      frames.push({ frame_id: `F${String(frames.length + 1).padStart(5, '0')}`, event_sequence: event.sequence,
        event_kind: event.kind, search_timestamp: event.timestamp ?? event.at_utc ?? null,
        candidate_id: candidate.id, evaluation_id: evaluation?.id ?? null, attempt_id: evaluation?.attempt_id ?? null,
        event_message: event.payload?.message ?? null, reason_codes: event.payload?.reason_codes ?? [],
        ...scope, checks, evaluation_checks: allChecks, result_view: 'iteration', component: null, native_results: native,
        iteration_index: manifest.candidates.findIndex(c => c.id === candidate.id) + 1, candidate_count: manifest.candidates.length,
        phase: selection ? 'selection' : 'iteration', outcome, parameters: candidate.parameters ?? {},
        parameter_changes: changes, reference_candidate_id: referenceId, objectives: candidate.build?.objectives ?? {},
        completed_operations: completed, check_counts: {
          pass: allChecks.filter(c => c.verdict === 'pass').length,
          fail: failures.length, unknown: allChecks.filter(c => c.verdict === 'unknown').length
        }, finalists, view: view ?? { availability: 'unavailable' }, caption: caption.join('\n'),
        start_frame: frames.length * hold, end_frame: (frames.length + 1) * hold });
    }
  }
  return frames;
}
