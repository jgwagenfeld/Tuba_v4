import test from 'node:test';
import assert from 'node:assert/strict';
import { filmPresentation } from '../src/searchFilmPresentation.js';

const overlay = (type, operation, values, extras = {}) => ({ id: `${type}:${operation}`, data: {
  result_type: type, load_case: operation, result_state_id: `state:${operation}`, values, ...extras
} });
const scene = { overlays: [
  overlay('stress', 'Hot', { 'object:element:E1': 25000000 }),
  overlay('reaction_force', 'Hot', { N0: [300, 400, 0] }, { vectors: [{ node_id: 'N0', start: [0, 0, 0] }] }),
  overlay('reaction_moment', 'Hot', { N0: [1, 2, 3] }),
  overlay('reaction_force', 'Cold', { N0: [9000, 0, 0] }, { vectors: [{ node_id: 'N0', start: [0, 0, 0] }] }),
  overlay('internal_forces', 'Hot', {}, { element_results: { 'object:element:E1': {
    forces_n1: [-100, 2, 3, 4, 5, 6], forces_n2: [20, 3, 4, 5, 6, -70]
  } } })
], objects: [{ id: 'object:element:E1', geometry_asset_id: 'E1' }],
geometry_assets: [{ id: 'E1', generation_config: { points: [[0, 0, 0], [1, 0, 0]] } }],
result_fields: [{ id: 'stress:Hot', overlay_id: 'stress:Hot' }] };

test('support and failure views colour the pipe by its own stress, with a separate nodal reaction display', () => {
  for (const frame of [{ result_view: 'reactions' }, {}]) {
    const p = filmPresentation(frame, scene, 'Hot', 'state:Hot');
    assert.equal(p.fieldId, 'stress:Hot'); assert.equal(p.fieldType, 'stress');
    assert.equal(p.unitSystem, 'engineering');
  }
  assert.equal(filmPresentation({ result_view: 'reactions' }, scene, 'Hot', 'state:Other').fieldId, null);
});

test('stress labels use recorded element maxima in MPa and identify their scope', () => {
  const p = filmPresentation({ result_view: 'stress' }, scene, 'Hot', 'state:Hot');
  assert.match(p.rows[0], /25 MPa.*E1/); assert.match(p.annotations.at(-1).label, /element max 25 MPa/);
  assert.match(p.rows.join(), /not a piping-code stress/);
  assert.match(filmPresentation({ result_view: 'stress' }, scene, 'Hot', 'state:Other').rows[0], /unavailable/);
});

test('support labels and components belong to the exact recorded operation and state', () => {
  const p = filmPresentation({ result_view: 'reactions' }, scene, 'Hot', 'state:Hot');
  assert.match(p.annotations[0].label, /500 N/);
  assert.match(p.rows[0], /300, 400, 0/);
  assert.match(p.rows[0], /1, 2, 3/);
  assert.doesNotMatch(p.rows.join(), /9,000/);
  assert.equal(filmPresentation({ result_view: 'reactions' }, scene, 'Hot', 'state:Cold').annotations.length, 0);
});
test('section-force peaks retain sign, endpoint and separate force/moment units', () => {
  const p = filmPresentation({ result_view: 'internal_forces' }, scene, 'Hot', 'state:Hot');
  assert.match(p.rows[0], /N: -100 N.*n1/);
  assert.match(p.rows[5], /MFZ: -70 N m.*n2/);
  assert.deepEqual(p.annotations.find(a => a.label.startsWith('MFZ:')).point, [1, 0, 0]);
});
test('cold collisions mark recorded locations without borrowing native results', () => {
  const p = filmPresentation({ check: { verdict: 'fail', constraint_id: 'cold.model', details: {
    clashes: [{ location: [1, 2, 3], penetration_m: 0.012 }]
  } } }, scene, null, null);
  assert.deepEqual(p.annotations[0].point, [1, 2, 3]);
  assert.match(p.annotations[0].label, /12 mm/);
  assert.equal(p.fieldId, null);
});
test('missing internal forces remain unavailable rather than displaying zero', () => {
  const p = filmPresentation({ result_view: 'internal_forces' }, scene, 'Missing', 'state:Missing');
  assert.equal(p.annotations.length, 0);
  assert.equal(p.rows.filter(row => /unavailable/.test(row)).length, 6);
});
