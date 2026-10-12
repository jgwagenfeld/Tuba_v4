import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';

const app = await readFile(new URL('../src/app.js', import.meta.url), 'utf8');
const controlSource = app.slice(app.indexOf('function renderSolveControls()'), app.indexOf('// A Code_Aster solve runs'));
const runSource = app.slice(app.indexOf('async function runHydraulics()'), app.indexOf('// One stage transition'));
const button = () => ({ hidden: true, disabled: false, dataset: {} });

function setup(process = { available: true, status: 'not_evaluated', can_run: true }) {
  const context = {
    studio: { available: true, project: { solves: true, can_solve: !process, process }, diskCode: 'model', hasReview: false },
    currentState: { embed: false }, currentBundle: { scene: { process: { schematic: {} } } },
    dom: { processActions: button(), processOpen: button(), processRun: button(), processStatus: button(), solveButton: button(),
      reviewEmptySolve: button(), reviewEmpty: button(), reviewEmptyText: button(), codeText: { value: 'model' } },
    meshClient: { snapshot: () => ({ job: { busy: false } }) },
    codePaneCases: () => ['Hot'], currentStage: () => 'build'
  };
  runInNewContext(controlSource, context);
  return context;
}

test('hydraulic gating keeps Solve visible, names its reason, and preserves projects without a process', () => {
  const context = setup(); context.renderSolveControls();
  assert.equal(context.dom.processActions.hidden, false);
  assert.equal(context.dom.processRun.disabled, false);
  assert.equal(context.dom.solveButton.hidden, false);
  assert.equal(context.dom.solveButton.disabled, true);
  assert.match(context.dom.solveButton.title, /pass its checks/);
  assert.equal(context.dom.processStatus.textContent, 'Hydraulics: Not evaluated');
  context.studio.project.can_solve = true;
  context.studio.project.process.status = 'passed'; context.renderSolveControls();
  assert.equal(context.dom.solveButton.disabled, false);
  const structural = setup(null); structural.renderSolveControls();
  assert.equal(structural.dom.processActions.hidden, true);
  assert.equal(structural.dom.solveButton.hidden, false);
  assert.equal(structural.dom.solveButton.disabled, false);
});

test('pending editor text and model jobs disable hydraulics and Solve without evaluating old disk inputs', () => {
  const context = setup(); context.studio.project.can_solve = true;
  context.dom.codeText.value = 'edited'; context.renderSolveControls();
  assert.equal(context.dom.processRun.disabled, true);
  assert.equal(context.dom.solveButton.disabled, true);
  assert.match(context.dom.processRun.title, /Run model.py to apply edits/);
  assert.match(context.dom.processOpen.title, /last executed model.py/);
  context.dom.codeText.value = 'model';
  for (const key of ['running', 'solving', 'preparing', 'processRunning']) {
    context.studio[key] = true; context.renderSolveControls();
    assert.equal(context.dom.processRun.disabled, true);
    assert.equal(context.dom.solveButton.disabled, true);
    context.studio[key] = false;
  }
  context.meshClient.snapshot = () => ({ job: { busy: true } }); context.renderSolveControls();
  assert.equal(context.dom.processRun.disabled, true);
});

test('rejection and stale state remain explicit and backend can_run is respected', () => {
  const context = setup({ available: true, status: 'rejected', can_run: false, error: 'Velocity exceeds limit' });
  context.renderSolveControls();
  assert.equal(context.dom.processRun.disabled, true);
  assert.match(context.dom.processStatus.textContent, /Rejected.*Velocity exceeds limit/);
  assert.equal(context.dom.solveButton.title, 'Velocity exceeds limit');
  context.studio.project.process = { available: true, status: 'stale', can_run: true }; context.renderSolveControls();
  assert.match(context.dom.processStatus.textContent, /Stale/);
  assert.doesNotMatch(context.dom.processStatus.textContent, /Velocity/);
});

test('Run hydraulics posts an empty job request once and surfaces a rejected start', async () => {
  const context = setup(); let calls = 0, errorMessage;
  context.render = () => context.renderSolveControls();
  context.refreshStudioProject = async () => {};
  context.setErrorStatus = error => { errorMessage = error.message; };
  context.fetch = async (url, options) => {
    calls++; assert.equal(url, '/api/process/run'); assert.equal(options.method, 'POST'); assert.equal(options.body, '{}');
    assert.equal(options.headers['Content-Type'], 'application/json');
    return { ok: false, status: 409, json: async () => ({ error: 'Another model job is running' }) };
  };
  runInNewContext(runSource, context);
  await context.runHydraulics();
  assert.equal(calls, 1); assert.equal(errorMessage, 'Another model job is running');
  assert.equal(context.studio.processRunning, false);
  context.dom.processRun.disabled = true;
  await context.runHydraulics(); assert.equal(calls, 1);
});
