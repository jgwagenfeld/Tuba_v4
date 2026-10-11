import test from 'node:test';
import assert from 'node:assert/strict';
import { planSearchFilm, filmVtt } from '../src/searchFilm.js';

const event = (sequence, kind, payload = {}) => ({ sequence, kind, candidate_id: 'C1', timestamp: `time-${sequence}`, payload });
function fixture() {
  const check = { constraint_id: 'nozzle', verdict: 'fail', basis: 'code_aster', operation: 'Hot', result_state_id: 'hot:2', message: 'Nozzle force exceeded', measured_value: 20, comparator: '<=', limit: 10, unit: 'N', entity_refs: ['node:pump'], evidence_refs: ['Hot/reac.csv'] };
  return { schema: 'tuba.search.viewer.v1', run: { settings: { operations: ['Hot'] } }, candidates: [{ id: 'C1', parent_ids: [], parameters: { depth: 2 }, intent: 'Explore <deeper> & wider', outcome: 'selected', preview: { availability: 'available', bundle: 'previews/C1' }, attempt_reviews: [{ evaluation_id: 'E1', attempt_id: 'A1', availability: 'available', bundle: 'reviews/C1/E1' }] }], events: [
    event(1, 'candidate.proposed'), event(2, 'candidate.built', { objectives: { length: 5 } }),
    event(3, 'evaluation.completed', { id: 'E1', attempt_id: 'A1', checks: [check], completed_operations: ['Hot'] }),
    event(4, 'candidate.decision', { evaluation_id: 'E1', outcome: 'rejected_constraint', reason_codes: ['overload'] }),
    event(5, 'attempt.recovered', { attempt_id: 'A2' }),
    event(6, 'candidate.decision', { evaluation_id: 'E1', outcome: 'selected', reason_codes: ['objective'] }) ] };
}

test('compact review retains failures and only plans completed operation result views', () => {
  const plan = planSearchFilm(fixture(), { events: 'review', start: 2, end: 4 });
  const results = plan.keyframes.filter(frame => frame.result_view);
  assert.deepEqual(results.map(frame => frame.result_view), ['stress', 'reactions', 'internal_forces', 'displacement']);
  assert.ok(results.every(frame => frame.operation === 'Hot' && frame.evaluation_id === 'E1' && frame.event_sequence === 4));
  assert.ok(plan.keyframes.some(frame => frame.check?.verdict === 'fail'));
  assert.ok(!plan.keyframes.some(frame => frame.event_kind === 'evaluation.completed'));
});

test('all six signed section components can be planned as separate views of the same native operation', () => {
  const sectionComponents = ['N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'];
  const plan = planSearchFilm(fixture(), { events: 'review', start: 4, end: 4, sectionComponents });
  assert.deepEqual(plan.keyframes.filter(f => f.result_view === 'internal_forces').map(f => f.component), sectionComponents);
  for (const components of [[], ['unknown'], ['N', 'N'], 'N']) {
    assert.throws(() => planSearchFilm(fixture(), { sectionComponents: components }), /section components/);
  }
});

test('frames use the cursor, without final decision or future evaluation leakage', () => {
  const plan = planSearchFilm(fixture(), { start: 2, end: 2 });
  assert.equal(plan.keyframes.length, 1);
  assert.equal(plan.keyframes[0].evaluation_id, null);
  assert.doesNotMatch(plan.keyframes[0].caption, /selected|Nozzle/);
  assert.match(plan.keyframes[0].caption, /Reference geometry/);
});
test('failed check preserves exact attempt, state, measurements and evidence links', () => {
  const plan = planSearchFilm(fixture(), { start: 4, end: 4 });
  const frame = plan.keyframes.find(f => f.check_index === 0);
  assert.equal(frame.evaluation_id, 'E1'); assert.equal(frame.attempt_id, 'A1');
  assert.equal(frame.check.result_state_id, 'hot:2');
  assert.match(frame.caption, /20 <= 10 N/); assert.match(frame.caption, /rejected_constraint/);
  assert.deepEqual(frame.check.evidence_refs, ['Hot/reac.csv']);
});
test('recovery creates no checks, no decision and no inherited successful attempt', () => {
  const frame = planSearchFilm(fixture(), { start: 5, end: 5 }).keyframes[0];
  assert.equal(frame.evaluation_id, 'recovered:A2'); assert.equal(frame.check, null);
  assert.match(frame.caption, /No published evaluation/); assert.doesNotMatch(frame.caption, /selected|Nozzle/);
});
test('an unknown operation without completed native results is labelled unsolved', () => {
  const m = fixture();
  m.events[2].kind = 'evaluation.interrupted';
  m.events[2].payload.completed_operations = [];
  m.events[2].payload.checks[0].verdict = 'unknown';
  const frame = planSearchFilm(m, { start: 3, end: 3 }).keyframes[1];
  assert.match(frame.caption, /no solver results/);
});
test('integer timing is deterministic; VTT escapes literal caption markup', () => {
  const a = planSearchFilm(fixture(), { events: 'all', fps: 25, holdSeconds: 1.21 });
  assert.deepEqual(a, planSearchFilm(fixture(), { events: 'all', fps: 25, holdSeconds: 1.21 }));
  assert.equal(a.hold_frames, 30); assert.equal(a.keyframes[1].start_frame, 30);
  assert.match(filmVtt(a), /00:00:00.000 --> 00:00:01.200/);
  assert.match(filmVtt(a), /&lt;deeper&gt; &amp; wider/);
});
test('decision chooses its earlier evaluation ID even after a later sealed attempt', () => {
  const m = fixture(); m.events.splice(4, 0, event(5, 'evaluation.completed', { id: 'E2', attempt_id: 'A2', checks: [], completed_operations: [] }));
  m.events = m.events.slice(0, 5).concat(event(6, 'candidate.decision', { evaluation_id: 'E1', outcome: 'rejected_constraint' }));
  assert.equal(planSearchFilm(m, { start: 6, end: 6 }).keyframes[0].evaluation_id, 'E1');
});
test('all-event ranges include proposals; milestones skip proposals', () => {
  assert.equal(planSearchFilm(fixture(), { events: 'all', start: 1, end: 2 }).keyframes.length, 2);
  assert.equal(planSearchFilm(fixture(), { start: 1, end: 2 }).keyframes.length, 1);
});
for (const options of [{ start: -1 }, { end: 100 }, { start: 4, end: 2 }, { fps: 0 }, { fps: 3.5 }, { holdSeconds: NaN }, { holdSeconds: 0 }, { width: 1601 }, { height: 20 }, { events: 'invalid' }]) {
  test(`invalid capture options are rejected: ${JSON.stringify(options)}`, () => assert.throws(() => planSearchFilm(fixture(), options), /film|range|hold|fps|size|events/i));
}
