import test from 'node:test';
import assert from 'node:assert/strict';
import { studioSolveGuidance } from '../src/solveGuidance.js';

const project = { has_study: true, solves: true, can_solve: true, can_mesh: true };

test('ready projects and published bundles do not add a readiness warning', () => {
  assert.equal(studioSolveGuidance({ project }), null);
  assert.equal(studioSolveGuidance(), null);
  assert.equal(studioSolveGuidance({ project, embed: true, pendingEdits: true }), null);
});

test('pending source and source errors point to the visible geometry update action', () => {
  const pending = studioSolveGuidance({ project, pendingEdits: true });
  assert.equal(pending.state, 'pending-edits');
  assert.match(pending.message, /Update geometry.*Ctrl\+Enter.*model\.py/);
  for (const options of [{ sourceError: true }, { project: { ...project, can_mesh: false } }]) {
    const failed = studioSolveGuidance({ project, ...options });
    assert.equal(failed.state, 'source-error');
    assert.match(failed.message, /Fix the model\.py error.*Update geometry/);
  }
});

test('missing studies explain where to declare load cases for real Code_Aster evaluation', () => {
  for (const missing of [{ has_study: false }, { solves: false }]) {
    const result = studioSolveGuidance({ project: { ...project, ...missing } });
    assert.equal(result.state, 'missing-study');
    assert.match(result.message, /LOAD_CASES in study\.py.*Code_Aster Solve/);
  }
});

test('hydraulic rejection, failure and freshness each have a recovery action', () => {
  const expectations = {
    not_evaluated: /Run hydraulics.*pass its checks.*Code_Aster/,
    rejected: /P&ID.*revise model\.py.*Run hydraulics/,
    failed: /Fix the error shown beside Run hydraulics.*run it again/,
    stale: /outdated.*Run hydraulics.*current model.*Code_Aster/
  };
  for (const [status, recovery] of Object.entries(expectations)) {
    const result = studioSolveGuidance({ project: { ...project, can_solve: false, process: { available: true, status } } });
    assert.match(result.message, recovery);
    assert.doesNotMatch(result.message, /results (were|are) produced/i);
  }
});

test('active jobs explain their phase rather than reporting readiness or completed results', () => {
  for (const [key, state, phase] of [
    ['running', 'updating', /Updating geometry/], ['solving', 'solving', /Code_Aster is running/],
    ['preparing', 'importing', /Importing/], ['processRunning', 'hydraulics-running', /Hydraulics is running/],
    ['meshBusy', 'mesh-running', /cancel it in Mesh detail/]
  ]) {
    const result = studioSolveGuidance({ project, [key]: true, pendingEdits: true });
    assert.equal(result.state, state);
    assert.match(result.message, phase);
  }
});
