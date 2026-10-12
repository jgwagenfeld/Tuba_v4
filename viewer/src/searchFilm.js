import { hydraulicSolverLabel, replayAt, reviewForCheck } from './searchReplay.js';
import { iterationFrames } from './searchIterations.js';

const milestones = new Set(['candidate.built', 'evaluation.completed', 'evaluation.failed',
  'evaluation.interrupted', 'evaluation.diagnostic', 'attempt.recovered', 'candidate.decision', 'run.completed']);
const literal = value => typeof value === 'string' ? value : JSON.stringify(value);

export function planSearchFilm(manifest, options = {}) {
  const { start = 1, end = manifest.events.at(-1)?.sequence ?? 0, fps = 25,
    holdSeconds = 2, width = 1600, height = 900, events = 'milestones', sectionComponents = ['MFZ'] } = options;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 1 || end < start || end > (manifest.events.at(-1)?.sequence ?? 0)) throw new Error('Invalid film event range');
  if (!Number.isInteger(fps) || fps < 1 || fps > 60) throw new Error('Invalid film fps (1–60)');
  if (!Number.isFinite(holdSeconds) || holdSeconds <= 0 || holdSeconds > 30 || Math.round(fps * holdSeconds) < 1) throw new Error('Invalid film hold (one frame to 30 seconds)');
  if (![width, height].every(n => Number.isInteger(n) && n % 2 === 0) || width < 640 || width > 3840 || height < 360 || height > 2160) throw new Error('Invalid film size (even 640–3840 × 360–2160)');
  if (!['all', 'milestones', 'review', 'iterations'].includes(events)) throw new Error('Invalid film events policy');
  if (!Array.isArray(sectionComponents) || !sectionComponents.length || sectionComponents.some(c => !['N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'].includes(c)) || new Set(sectionComponents).size !== sectionComponents.length) throw new Error('Invalid film section components');
  const hold = Math.round(fps * holdSeconds);
  const keyframes = events === 'iterations' ? iterationFrames(manifest, start, end, hold) : [];
  for (const event of manifest.events.filter(e => events !== 'iterations' && e.sequence >= start && e.sequence <= end && (events === 'all' || (events === 'review' ? ['candidate.built', 'candidate.decision', 'evaluation.failed', 'evaluation.interrupted', 'run.completed'].includes(e.kind) : milestones.has(e.kind))))) {
    const snapshot = replayAt(manifest, event.sequence);
    const candidate = snapshot.candidates.find(c => c.id === (event.candidate_id ?? event.payload?.selected_candidate_id)) ?? snapshot.candidates.at(-1);
    const exactId = event.kind === 'candidate.decision' ? event.payload.evaluation_id
      : event.kind === 'attempt.recovered' ? `recovered:${event.payload.attempt_id}`
      : event.kind.startsWith('evaluation.') && event.payload.id ? event.payload.id : null;
    const evaluation = exactId ? candidate?.evaluations.find(e => e.id === exactId) : candidate?.evaluations.at(-1);
    const heading = `${candidate?.id ?? 'Run'} · Event ${event.sequence} · ${event.kind}`;
    const lines = [heading, `Search time (UTC): ${event.timestamp ?? event.at_utc ?? 'not recorded'}`];
    if (candidate?.intent) lines.push(`Proposal intent: ${literal(candidate.intent)}`);
    lines.push(`Recorded outcome: ${evaluation?.outcome ?? candidate?.outcome ?? 'not recorded'}`);
    if (event.payload?.message) lines.push(event.payload.message);
    if (evaluation?.source_event_kind === 'attempt.recovered') lines.push('No published evaluation; no checks or decision inferred.');
    if (event.kind === 'candidate.decision') {
      lines.push(`Decision reasons: ${(event.payload.reason_codes ?? []).join(', ') || 'not recorded'}`);
      if (Object.keys(event.payload.details ?? {}).length) lines.push(`Decision details: ${JSON.stringify(event.payload.details)}`);
    }
    const add = (check = null, checkIndex = null, resultView = null, operation = null, component = null) => {
      const hydraulic = hydraulicSolverLabel(check?.basis) ? check : evaluation?.checks?.find(c => hydraulicSolverLabel(c.basis) && ['pass', 'fail'].includes(c.verdict));
      const fluid_results = check ? Boolean(hydraulicSolverLabel(check.basis)) : !evaluation?.completed_operations?.length && Boolean(hydraulic);
      const hydraulic_basis = fluid_results ? hydraulic?.basis : null;
      const solver = hydraulicSolverLabel(hydraulic_basis);
      if (fluid_results) operation ??= hydraulic?.operation ?? evaluation?.operations?.[0] ?? hydraulic?.details?.scenario_id ?? null;
      const view = reviewForCheck(candidate, evaluation, check);
      const caption = [...lines];
      if (check) {
        caption.push(`${check.verdict} · ${check.constraint_id} · ${check.basis}`,
          fluid_results ? `${solver} · ${operation ?? 'scenario unavailable'} · steady hydraulics`
            : `${check.operation ?? 'cold reference'} · Solver state: ${check.result_state_id ?? 'none'}`,
          check.message ?? check.reason_text ?? check.reason_code ?? 'No checker message recorded');
        if (check.measured_value != null || check.limit != null) caption.push(`${literal(check.measured_value)} ${check.comparator ?? 'against'} ${literal(check.limit)} ${check.unit ?? ''}`.trim());
        if (check.entity_refs?.length) caption.push(`Targets: ${check.entity_refs.join(', ')}`);
        for (const clash of (check.details?.clashes ?? []).slice(0, 3)) caption.push(`Collision at ${literal(clash.location)} m; distance ${literal(clash.distance_m)} m; penetration ${literal(clash.penetration_m)} m`);
      }
      const native = !fluid_results && (check ? check.operation && evaluation?.completed_operations?.includes(check.operation) : evaluation?.completed_operations?.length);
      caption.push(view?.availability === 'available' ? (fluid_results ? `Recorded ${solver} hydraulic evidence` : native ? 'Recorded Code_Aster evidence' : 'Reference geometry — no solver results') : `View unavailable: ${view?.message ?? 'No recorded scene at this event'}`);
      if (fluid_results && !evaluation?.completed_operations?.length) caption.push('Code_Aster structural results were not evaluated.');
      keyframes.push({ frame_id: `F${String(keyframes.length + 1).padStart(5, '0')}`, event_sequence: event.sequence,
        event_kind: event.kind, search_timestamp: event.timestamp ?? event.at_utc ?? null,
        candidate_id: candidate?.id ?? null, evaluation_id: evaluation?.id ?? null, attempt_id: evaluation?.attempt_id ?? null,
        event_message: event.payload?.message ?? null, reason_codes: event.payload?.reason_codes ?? [], check_index: checkIndex, check, result_view: resultView, component, operation, fluid_results, hydraulic_basis, native_results: Boolean(native), view: view ?? { availability: 'unavailable' }, caption: caption.join('\n'),
        start_frame: keyframes.length * hold, end_frame: (keyframes.length + 1) * hold });
    };
    add();
    if ((events === 'review' ? event.kind === 'candidate.decision' : event.kind === 'evaluation.completed')) for (const operation of evaluation?.completed_operations ?? []) {
      for (const mode of ['stress', 'reactions', 'internal_forces', 'displacement']) {
        if (mode === 'internal_forces') for (const component of sectionComponents) add(null, null, mode, operation, component);
        else add(null, null, mode, operation);
      }
    }
    for (const [i, check] of (evaluation?.checks ?? []).entries()) if (['fail', 'unknown'].includes(check.verdict)) add(check, i);
  }
  if (!keyframes.length || keyframes.length > 2000 || keyframes.length * hold > 200000) throw new Error('Film segment is empty or exceeds capture frame budget');
  return { schema: 'tuba.search.film.v1', status: 'planned', source_schema: manifest.schema,
    start_event: start, end_event: end, events_policy: events, width, height, fps, hold_frames: hold,
    total_frames: keyframes.length * hold, duration_seconds: keyframes.length * hold / fps,
    presentation: { units: 'Native SI values; stress legend in MPa; force and moment legends in N and N m', visual_deformation_scale: 1, engineering_displacement_scale: 1,
      transitions: 'held recorded views; no interpolated solver states', camera: 'common segment envelope',
      colour_policy: 'replay package comparison ranges when available; native local ranges otherwise' }, keyframes };
}

function timecode(frame, fps) {
  const ms = Math.round(frame / fps * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}.${String(ms % 1000).padStart(3, '0')}`;
}
export function filmVtt(plan) {
  const escape = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replace(/\r/g, '').replace(/\n\n+/g, '\n');
  return 'WEBVTT\n\n' + plan.keyframes.map(f => `${f.frame_id}\n${timecode(f.start_frame, plan.fps)} --> ${timecode(f.end_frame, plan.fps)}\n${escape(f.caption)}\n`).join('\n');
}
