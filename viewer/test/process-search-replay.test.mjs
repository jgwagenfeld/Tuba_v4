// Synthetic replay/scene fixtures test selection; they are not solver evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import { planSearchFilm } from '../src/searchFilm.js';
import { filmPresentation, conciseFilmCaption } from '../src/searchFilmPresentation.js';
import { reviewForCheck } from '../src/searchReplay.js';
import { filmPlayer } from '../src/searchFilmPlayer.js';

const flowCheck = (unit = 'm/s') => ({ constraint_id: unit === 'Pa' ? 'flow.source_pressure' : unit === 'kg/s' ? 'flow.delivery' : 'flow.velocity.0',
  basis: 'openmodelica', verdict: 'fail', operation: null, result_state_id: null,
  entity_refs: unit === 'm/s' ? ['element:E1'] : [], measured_value: unit === 'Pa' ? 700000 : unit === 'kg/s' ? 8 : 4.64,
  limit: unit === 'Pa' ? 600000 : unit === 'kg/s' ? 10 : 3, unit,
  message: 'Declared hydraulic requirement exceeded', details: { scenario_id: 'WaterOperating' } });

function fixture(checks = [flowCheck()], completed = []) {
  return { schema: 'tuba.search.viewer.v1', run: {}, candidates: [{ id: 'C1', parent_ids: [], parameters: { size: 'small', offset_m: 1 },
    preview: { availability: 'available', bundle: 'previews/C1' },
    attempt_reviews: [{ evaluation_id: 'E1', availability: 'available', bundle: 'reviews/C1/E1' }] }], events: [
      { sequence: 1, kind: 'candidate.proposed', candidate_id: 'C1', payload: {} },
      { sequence: 2, kind: 'candidate.built', candidate_id: 'C1', payload: {} },
      { sequence: 3, kind: 'evaluation.completed', candidate_id: 'C1', payload: { id: 'E1', operations: ['WaterOperating'], completed_operations: completed, checks } },
      { sequence: 4, kind: 'candidate.decision', candidate_id: 'C1', payload: { evaluation_id: 'E1', outcome: 'rejected_constraint' } }
    ] };
}

function fluidScene(operation = 'WaterOperating') {
  const overlay = (type, value, unit) => ({ id: type, data: { result_type: type, basis: 'openmodelica', load_case: operation,
    result_state_id: '', scenario_id: 'WaterOperating', unit, values: { 'object:element:E1': value } } });
  return { objects: [{ id: 'object:element:E1', geometry_asset_id: 'E1' }],
    geometry_assets: [{ id: 'E1', generation_config: { points: [[0, 0, 0], [2, 0, 0]] } }],
    overlays: [overlay('fluid_velocity', 4.64, 'm/s'), overlay('fluid_pressure', 350000, 'Pa'),
      { id: 'stress', data: { result_type: 'stress', load_case: operation, result_state_id: 'state:structural', values: { 'object:element:E1': 25e6 } } },
      { id: 'force', data: { result_type: 'reaction_force', load_case: operation, result_state_id: 'state:structural', values: { N0: [3, 4, 0] }, vectors: [{ node_id: 'N0', start: [0, 0, 0] }] } }
    ], result_fields: [{ id: 'flow-velocity', overlay_id: 'fluid_velocity' }, { id: 'flow-pressure', overlay_id: 'fluid_pressure' },
      { id: 'native-stress', overlay_id: 'stress' }] };
}

const iteration = manifest => planSearchFilm(manifest, { events: 'iterations', start: 4, end: 4 }).keyframes[0];

test('hydraulic rejection without a structural operation uses its exact sealed review', () => {
  const frame = iteration(fixture());
  assert.equal(frame.view.bundle, 'reviews/C1/E1');
  assert.equal(frame.native_results, false);
  assert.equal(frame.fluid_results, true);
  assert.equal(frame.operation, 'WaterOperating');
  assert.equal(frame.result_state_id, null);
  assert.match(frame.caption, /Recorded OpenModelica/);
  assert.doesNotMatch(frame.caption, /Reference geometry|Recorded Code_Aster/);
});

test('hydraulic and cold failures stay separate even though both lack a structural state', () => {
  const cold = { constraint_id: 'cold.clash', basis: 'geometry', verdict: 'fail', operation: null, result_state_id: null, details: { clashes: [] } };
  const frames = planSearchFilm(fixture([flowCheck(), cold]), { events: 'iterations', start: 4, end: 4 }).keyframes;
  assert.equal(frames.length, 2);
  assert.equal(frames[0].view.bundle, 'reviews/C1/E1');
  assert.equal(frames[1].view.bundle, 'previews/C1');
  assert.deepEqual(frames.map(frame => frame.checks.map(check => check.constraint_id)), [['flow.velocity.0'], ['cold.clash']]);
});

test('unavailable sealed fluid review cannot be replaced by available reference geometry', () => {
  const manifest = fixture();
  manifest.candidates[0].attempt_reviews[0] = { evaluation_id: 'E1', availability: 'unavailable', message: 'Sealed review missing' };
  const frame = iteration(manifest);
  assert.equal(frame.view.availability, 'unavailable');
  assert.equal(frame.view.bundle, undefined);
  const candidate = manifest.candidates[0];
  const evaluation = { review: frame.view };
  assert.equal(reviewForCheck(candidate, evaluation, flowCheck()), frame.view);
  assert.equal(reviewForCheck(candidate, evaluation, { ...flowCheck(), basis: 'geometry' }), candidate.preview);
});

test('a hydraulic iteration selects measured velocity and labels targets without structural values', () => {
  const frame = iteration(fixture());
  const presentation = filmPresentation(frame, fluidScene(), 'WaterOperating', null);
  assert.equal(presentation.fieldId, 'flow-velocity');
  assert.equal(presentation.fieldType, 'fluid_velocity');
  assert.equal(presentation.unitSystem, 'si');
  assert.equal(presentation.annotations.length, 1);
  assert.match(presentation.annotations[0].label, /E1: 4.64 \/ limit 3 m\/s/);
  assert.match(presentation.rows.join(), /Largest recorded fluid velocity: 4.64 m\/s/);
  assert.match(presentation.rows.join(), /Code_Aster structural results were not evaluated/);
  assert.doesNotMatch(presentation.rows.join(), /MPa|N0: F|before solving/);
  assert.match(conciseFilmCaption(frame, presentation, 'WaterOperating', null), /OpenModelica.*steady hydraulics/);
});

test('pressure findings select absolute pressure and preserve global source measurement', () => {
  const frame = iteration(fixture([flowCheck('Pa')]));
  const presentation = filmPresentation(frame, fluidScene(), 'WaterOperating', null);
  assert.equal(presentation.fieldId, 'flow-pressure');
  assert.match(presentation.rows.join(), /mean absolute fluid pressure: 350,000 Pa/);
  assert.match(presentation.rows.join(), /source_pressure: 700,000 \/ limit 600,000 Pa/);
  assert.match(presentation.rows.join(), /pressures are absolute/);
});

test('delivery findings preserve failed required flow beside the velocity context', () => {
  const frame = iteration(fixture([flowCheck('kg/s')]));
  const presentation = filmPresentation(frame, fluidScene(), 'WaterOperating', null);
  assert.equal(presentation.fieldId, 'flow-velocity');
  assert.match(presentation.rows.join(), /flow.delivery: 8 \/ limit 10 kg\/s/);
});

test('a different hydraulic operation cannot borrow fields or target annotations', () => {
  const frame = iteration(fixture());
  const presentation = filmPresentation(frame, fluidScene(), 'OtherOperation', null);
  assert.equal(presentation.fieldId, null);
  assert.equal(presentation.annotations.length, 0);
  assert.match(presentation.rows.join(), /Requested hydraulic scenario unavailable/);
  const missing = filmPresentation({ check: flowCheck() }, fluidScene(), 'OtherOperation', null);
  assert.equal(missing.fieldId, null);
  assert.equal(missing.annotations.length, 0);
});

test('fluid fields require explicit OpenModelica provenance and no fabricated structural state', () => {
  for (const changes of [{ basis: 'prediction' }, { result_state_id: 'fabricated-state' }]) {
    const scene = fluidScene();
    Object.assign(scene.overlays[0].data, changes);
    const presentation = filmPresentation({ check: flowCheck() }, scene, 'WaterOperating', null);
    assert.equal(presentation.fieldId, null);
    assert.equal(presentation.annotations.length, 0);
    assert.match(presentation.rows.join(), /unavailable/);
  }
});

test('generic review film hydraulic finding uses the same sealed scene and field', () => {
  const frame = planSearchFilm(fixture(), { events: 'review', start: 4, end: 4 }).keyframes.find(frame => frame.check);
  assert.equal(frame.view.bundle, 'reviews/C1/E1');
  assert.equal(frame.operation, 'WaterOperating');
  assert.equal(frame.fluid_results, true);
  assert.match(frame.caption, /Recorded OpenModelica hydraulic evidence/);
  assert.match(frame.caption, /structural results were not evaluated/);
  assert.equal(filmPresentation(frame, fluidScene(), 'WaterOperating', null).fieldId, 'flow-velocity');
});

test('successful hydraulics remain reviewable when required structural checks are unknown', () => {
  const hydraulic = { ...flowCheck(), verdict: 'pass', measured_value: 2 };
  const missing = { constraint_id: 'structural.displacement', verdict: 'unknown', operation: 'WaterOperating', result_state_id: null, basis: 'code_aster' };
  const frame = iteration(fixture([hydraulic, missing]));
  assert.equal(frame.fluid_results, true);
  assert.equal(frame.view.bundle, 'reviews/C1/E1');
  const presentation = filmPresentation(frame, fluidScene(), 'WaterOperating', null);
  assert.equal(presentation.fieldId, 'flow-velocity');
  assert.match(presentation.rows.join(), /1 unknown/);
  assert.match(presentation.rows.join(), /structural results were not evaluated/);
});

test('successful Code_Aster evaluation keeps native stress and reaction annotations', () => {
  const native = { constraint_id: 'structural.force', verdict: 'fail', operation: 'WaterOperating', result_state_id: 'state:structural', basis: 'code_aster',
    entity_refs: ['node:N0'], measured_value: 5, limit: 4, unit: 'N' };
  const frame = iteration(fixture([{ ...flowCheck(), verdict: 'pass' }, native], ['WaterOperating']));
  assert.equal(frame.native_results, true);
  assert.equal(frame.fluid_results, false);
  const presentation = filmPresentation(frame, fluidScene(), 'WaterOperating', 'state:structural');
  assert.equal(presentation.fieldId, 'native-stress');
  assert.ok(presentation.annotations.some(annotation => /N0: F 5 N/.test(annotation.label)));
  assert.match(presentation.rows.join(), /25 MPa/);
});

test('mechanical operation name can differ from the retained process scenario ID', () => {
  const manifest = fixture();
  manifest.events[2].payload.operations = ['HotWater'];
  const frame = iteration(manifest);
  assert.equal(frame.operation, 'HotWater');
  const presentation = filmPresentation(frame, fluidScene('HotWater'), 'HotWater', null);
  assert.equal(presentation.fieldId, 'flow-velocity');
});

test('encoded player explains hydraulic provenance and structural evaluation boundary', () => {
  const html = filmPlayer(planSearchFilm(fixture(), { events: 'iterations' }));
  assert.match(html, /Fluid fields come from retained OpenModelica evaluations/);
  assert.match(html, /absolute Pa and K/);
  assert.match(html, /Structural fields come from retained Code_Aster evaluations/);
  assert.match(html, /Hydraulic rejections show retained OpenModelica fluid fields/);
});


function multiElementVelocity(externalValue = 4.643481129787162) {
  const measured = 4.643481129787162;
  const checks = Array.from({ length: 10 }, (_, index) => ({ ...flowCheck(),
    constraint_id: `flow.velocity.${index}`, comparator: 'max', reason_code: 'flow.velocity_limit_exceeded',
    measured_value: index === 9 ? externalValue : measured,
    entity_refs: index === 9 ? [] : [`element:E${index}`] }));
  const scene = fluidScene();
  scene.objects = Array.from({ length: 9 }, (_, index) => ({ id: `object:element:E${index}`, geometry_asset_id: `E${index}` }));
  scene.geometry_assets = Array.from({ length: 9 }, (_, index) => ({ id: `E${index}`,
    generation_config: { points: [[index, 0, 0], [index + 1, 0, 0]] } }));
  scene.overlays[0].data.values = Object.fromEntries(scene.objects.map(object => [object.id, measured]));
  return { frame: iteration(fixture(checks)), scene };
}

test('ten equivalent pipe and external-loss velocity failures fit one caption row without losing checks or annotations', () => {
  const { frame, scene } = multiElementVelocity();
  const original = structuredClone(frame.checks);
  const presentation = filmPresentation(frame, scene, 'WaterOperating', null);
  const findings = presentation.rows.filter(row => row.startsWith('flow.velocity'));
  assert.deepEqual(findings, ['flow.velocity: 4.64 / limit 3 m/s across 9 pipe elements + 1 external loss.']);
  assert.equal(presentation.annotations.length, 9);
  for (let index = 0; index < 9; index++) {
    assert.ok(presentation.annotations.some(annotation => annotation.label === `E${index}: 4.64 / limit 3 m/s`));
  }
  assert.deepEqual(frame.checks, original);
  assert.equal(frame.checks.length, 10);
  assert.equal(frame.check_counts.fail, 10);
  const caption = conciseFilmCaption(frame, presentation, 'WaterOperating', null);
  assert.match(caption, /10 failed/);
  assert.match(caption, /structural results were not evaluated/);
  assert.ok(caption.split('\n').length <= 25, 'the measured summary has a bounded caption line count');
});

test('a different external-loss velocity remains a separate measured diagnostic', () => {
  const { frame, scene } = multiElementVelocity(5);
  const presentation = filmPresentation(frame, scene, 'WaterOperating', null);
  const findings = presentation.rows.filter(row => row.startsWith('flow.velocity'));
  assert.deepEqual(findings, ['flow.velocity: 4.64 / limit 3 m/s across 9 pipe elements.',
    'flow.velocity.9: 5 / limit 3 m/s']);
  assert.equal(presentation.annotations.length, 9);
  assert.equal(frame.checks.at(-1).measured_value, 5);
});

test('hydraulic grouping compares exact measurements and limits before display rounding', () => {
  const checks = [
    { ...flowCheck(), constraint_id: 'flow.velocity.0', measured_value: 4.641 },
    { ...flowCheck(), constraint_id: 'flow.velocity.1', measured_value: 4.642 },
    { ...flowCheck(), constraint_id: 'flow.velocity.2', measured_value: 4.641, limit: 2 },
    { ...flowCheck('Pa'), constraint_id: 'flow.pressure.0' }
  ];
  const presentation = filmPresentation(iteration(fixture(checks)), fluidScene(), 'WaterOperating', null);
  assert.equal(presentation.rows.filter(row => /^flow\./.test(row)).length, 4);
  assert.match(presentation.rows.join(), /flow.velocity.0: 4.64 \/ limit 3 m\/s/);
  assert.match(presentation.rows.join(), /flow.velocity.1: 4.64 \/ limit 3 m\/s/);
  assert.match(presentation.rows.join(), /flow.velocity.2: 4.64 \/ limit 2 m\/s/);
  assert.match(presentation.rows.join(), /flow.pressure.0: 700,000 \/ limit 600,000 Pa/);
});
