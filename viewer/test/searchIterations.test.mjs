import test from 'node:test';
import assert from 'node:assert/strict';
import { planSearchFilm } from '../src/searchFilm.js';
import { filmPresentation, conciseFilmCaption } from '../src/searchFilmPresentation.js';

const event = (sequence, kind, candidate_id, payload = {}) => ({ sequence, kind, candidate_id, payload });
const check = (constraint_id, operation = 'Hot', state = 'state:Hot') => ({ constraint_id, operation,
  result_state_id: state, verdict: 'fail', entity_refs: ['node:N0'], measured_value: 20, limit: 10, unit: 'N' });
function fixture() {
  const candidate = (id, depth, evaluations) => ({ id, parent_ids: [], parameters: { depth_m: depth },
    preview: { availability: 'available', bundle: `previews/${id}` }, attempt_reviews: evaluations.map(evaluation_id =>
      ({ evaluation_id, availability: 'available', bundle: `reviews/${id}/${evaluation_id}` })) });
  return { schema: 'tuba.search.viewer.v1', run: {}, candidates: [candidate('C1', 1, ['E1']), candidate('C2', 2, ['I2', 'E2'])], events: [
    event(1, 'candidate.proposed', 'C1'), event(2, 'candidate.proposed', 'C2'),
    event(3, 'candidate.built', 'C1', { objectives: { pipe_length_m: 5, bend_count: 4, support_count: 4 } }),
    event(4, 'evaluation.completed', 'C1', { id: 'E1', completed_operations: ['Sustained', 'Hot'], checks: [check('pump'), check('rack')] }),
    event(5, 'candidate.decision', 'C1', { evaluation_id: 'E1', outcome: 'rejected_constraint' }),
    event(6, 'candidate.built', 'C2', { objectives: { pipe_length_m: 7, bend_count: 4, support_count: 4 } }),
    event(7, 'evaluation.interrupted', 'C2', { id: 'I2', completed_operations: [], checks: [{ ...check('pump', 'Hot', null), verdict: 'unknown' }] }),
    event(8, 'evaluation.completed', 'C2', { id: 'E2', completed_operations: ['Sustained', 'Hot'], checks: [{ ...check('pump'), verdict: 'pass' }] }),
    event(9, 'candidate.decision', 'C2', { evaluation_id: 'E2', outcome: 'feasible_retained' }),
    event(10, 'candidate.decision', 'C2', { evaluation_id: 'E2', outcome: 'selected', details: { objective_fields: ['pipe_length_m'] } }),
    event(11, 'run.completed', null, { selected_candidate_id: 'C2' }) ] };
}

test('iterations group both failed supports and do not tour individual result fields', () => {
  const plan = planSearchFilm(fixture(), { events: 'iterations', holdSeconds: 8 });
  assert.deepEqual(plan.keyframes.map(f => f.event_sequence), [5, 7, 9, 11]);
  assert.ok(plan.keyframes.every(f => f.result_view === 'iteration'));
  assert.equal(plan.keyframes[0].checks.length, 2);
  assert.equal(plan.duration_seconds, 32);
  assert.equal(plan.keyframes[2].outcome, 'feasible_retained');
  assert.equal(plan.keyframes[3].outcome, 'selected');
});

test('an interrupted retry keeps its own layout and never inherits successful loads', () => {
  const frames = planSearchFilm(fixture(), { events: 'iterations' }).keyframes;
  assert.equal(frames[1].evaluation_id, 'I2'); assert.equal(frames[1].native_results, false);
  assert.equal(frames[1].view.bundle, 'previews/C2'); assert.equal(frames[1].operation, null);
  assert.equal(frames[2].view.bundle, 'reviews/C2/E2');
  assert.deepEqual(frames[1].parameter_changes, [{ key: 'depth_m', before: 1, after: 2 }]);
  assert.deepEqual(frames[2].parameter_changes, []);
  const p = filmPresentation(frames[1], {}, null, null);
  assert.equal(p.fieldId, null); assert.equal(p.annotations.length, 0);
  assert.match(conciseFilmCaption(frames[1], p, null, null), /INTERRUPTED.*no completed result/);
  assert.doesNotMatch(p.rows.join(), /20.*N/);
});

test('failures in different operations or increments remain separate iteration views', () => {
  const m = fixture(); m.events[3].payload.checks.push(check('other', 'Sustained', 'state:Sustained'), check('increment', 'Hot', 'state:Hot:2'));
  const frames = planSearchFilm(m, { events: 'iterations', start: 5, end: 5 }).keyframes;
  assert.deepEqual(frames.map(f => [f.operation, f.result_state_id, f.checks.length]),
    [['Hot', 'state:Hot', 2], ['Sustained', 'state:Sustained', 1], ['Hot', 'state:Hot:2', 1]]);
});

test('mid-run ranges still know the prior tested parameters without exposing final decisions', () => {
  const f = planSearchFilm(fixture(), { events: 'iterations', start: 7, end: 7 }).keyframes[0];
  assert.equal(f.reference_candidate_id, 'C1'); assert.equal(f.outcome, 'interrupted');
  assert.deepEqual(f.finalists, []); assert.doesNotMatch(f.caption, /selected/);
});

const scene = { objects: [{ id: 'object:element:E1', geometry_asset_id: 'E1' }],
  geometry_assets: [{ id: 'E1', generation_config: { points: [[0, 0, 0], [1, 0, 0]] } }], overlays: [
    { id: 'stress', data: { result_type: 'stress', load_case: 'Hot', result_state_id: 'state:Hot', values: { 'object:element:E1': 25e6 } } },
    { id: 'force', data: { result_type: 'reaction_force', load_case: 'Hot', result_state_id: 'state:Hot', values: { N0: [3, 4, 0] }, vectors: [{ node_id: 'N0', start: [0, 0, 0] }] } },
    { id: 'moment', data: { result_type: 'reaction_moment', load_case: 'Hot', result_state_id: 'state:Hot', values: { N0: [1, 0, 0] } } }
  ], result_fields: [{ id: 'stress:Hot', overlay_id: 'stress' }] };

test('an iteration simultaneously labels all failed supports, native support loads and pipe stress', () => {
  const f = planSearchFilm(fixture(), { events: 'iterations' }).keyframes[0];
  const p = filmPresentation(f, scene, 'Hot', 'state:Hot');
  assert.equal(p.fieldId, 'stress:Hot');
  assert.equal(p.annotations.filter(a => a.severity === 'fail').length, 2);
  assert.match(p.rows.join(), /pump: 20 \/ limit 10 N/); assert.match(p.rows.join(), /rack: 20 \/ limit 10 N/);
  assert.ok(p.annotations.some(a => /N0: F 5 N.*M 1 N m/.test(a.label)));
  assert.match(p.rows.join(), /25 MPa/);
  const missing = filmPresentation(f, scene, 'Hot', 'state:Other');
  assert.equal(missing.fieldId, null); assert.equal(missing.annotations.length, 0);
  assert.match(missing.rows.join(), /Requested solver state unavailable/);
});

test('duplicate cold checks mark each clash once, with clearance distinguished from solid overlap', () => {
  const m = fixture(), clash = { left: { id: 'pipe' }, right: { id: 'box' }, location: [1, 2, 3], penetration_m: .012, severity: 'clearance' };
  m.events[3].payload.completed_operations = [];
  m.events[3].payload.checks = ['cold.model', 'cold.clearance'].map(id => ({ ...check(id, null, null), details: { clashes: [clash] } }));
  const f = planSearchFilm(m, { events: 'iterations' }).keyframes[0];
  const p = filmPresentation(f, scene, null, null);
  assert.equal(p.annotations.length, 1); assert.match(p.annotations[0].label, /clearance deficit 12 mm/);
  assert.equal(p.fieldId, null); assert.match(p.rows.join(), /Rejected before solving/);
});
