import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';

const app = await readFile(new URL('../src/app.js', import.meta.url), 'utf8');
function definition(name) {
  const source = app.match(new RegExp(`^(?:export )?function ${name}\\([^\\n]*\\) \\{[\\s\\S]*?^}`, 'm'))?.[0];
  assert.ok(source, `the actual ${name} function must be present`);
  return source.replace(/^export /, '');
}
const hints = app.slice(app.indexOf('const ERROR_HINTS ='), app.indexOf('export function humanizeError'));
const functions = [hints, ...['humanizeError', 'setStatus', 'setErrorStatus', 'renderHeader', 'openRunDiagram'].map(definition)].join('\n');

function element() {
  return {
    children: [], dataset: {}, attributes: {}, hidden: false, open: false, _text: '',
    append(...children) { this.children.push(...children); },
    set textContent(value) { this._text = value; this.children = []; },
    get textContent() { return this._text; },
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    classList: { toggle() {} }
  };
}

function setup() {
  const dom = {
    sceneMeta: element(), errorOutput: element(), errorDetail: { ...element(), hidden: true },
    status: element(), sceneTitle: element(), bundlePicker: { hidden: true }, reportLink: element(),
    reviewDrawer: element(), runDiagram: element()
  };
  const state = { sceneId: 'Live model', objects: [{ id: 'pipe' }], issues: [], review: null };
  const context = { dom, currentState: state, studio: { project: {} }, searchManifest: null,
    currentBundle: null, currentBundleUrl: 'build', document: { createElement: element } };
  const api = runInNewContext(`${functions}\n({ setErrorStatus, renderHeader, openRunDiagram })`, context);
  return { ...api, dom, state };
}

test('solver failure output survives header repaints while provenance changes', () => {
  const { setErrorStatus, renderHeader, dom, state } = setup();
  const raw = 'Traceback (most recent call last):\n  File "solver.py", line 12\nRuntimeError: native solver stopped';
  setErrorStatus({ message: raw }, 'Code_Aster did not finish. No new results were produced.');
  assert.equal(dom.errorDetail.hidden, false);
  assert.equal(dom.errorOutput.textContent, raw);
  assert.match(dom.status.textContent, /Code_Aster did not finish/);
  assert.equal(dom.status.dataset.level, 'error');
  renderHeader();
  assert.equal(dom.sceneMeta.textContent, '1 objects | 0 issues');
  assert.equal(dom.errorOutput.textContent, raw);
  state.review = { project_name: 'Recorded review', model_revision: 4, model_standard: 'EN' };
  renderHeader();
  assert.equal(dom.sceneMeta.textContent, 'EN · Revision 4');
  assert.equal(dom.errorOutput.textContent, raw);
});

test('the latest failure replaces prior output without mixing errors into provenance', () => {
  const { setErrorStatus, renderHeader, dom } = setup();
  setErrorStatus({ message: 'First solver failure' });
  renderHeader();
  setErrorStatus({ message: 'Second solver failure with a different cause' });
  renderHeader();
  assert.equal(dom.errorOutput.textContent, 'Second solver failure with a different cause');
  assert.doesNotMatch(dom.errorOutput.textContent, /First solver failure/);
  assert.equal(dom.sceneMeta.children.length, 0);
  assert.equal(dom.errorDetail.hidden, false);
});

test('opening a run diagram opens its parent drawer before scrolling to the plot', () => {
  const { openRunDiagram, dom } = setup();
  let scrolls = 0;
  dom.runDiagram.scrollIntoView = options => {
    assert.equal(dom.reviewDrawer.open, true, 'the plot cannot be scrolled into a closed drawer');
    assert.equal(dom.runDiagram.open, true);
    assert.equal(options.block, 'nearest');
    scrolls++;
  };
  openRunDiagram();
  assert.equal(scrolls, 1);
});

test('hidden and unavailable run diagrams leave the parent drawer unchanged', () => {
  for (const unavailable of ['hidden', 'missing']) {
    const { openRunDiagram, dom } = setup();
    let scrolls = 0;
    dom.runDiagram.scrollIntoView = () => { scrolls++; };
    if (unavailable === 'hidden') dom.runDiagram.hidden = true;
    else dom.runDiagram = null;
    openRunDiagram();
    assert.equal(dom.reviewDrawer.open, false);
    assert.equal(scrolls, 0);
  }
});
