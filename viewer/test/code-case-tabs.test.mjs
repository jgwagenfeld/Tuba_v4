import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';

const app = await readFile(new URL('../src/app.js', import.meta.url), 'utf8');
const tabsSource = app.slice(app.indexOf('function renderCodeTabs()'), app.indexOf('function renderCaseInputs()'));
const commSource = app.slice(app.indexOf('async function loadComm()'), app.indexOf('function renderSolveControls()'));
const element = () => ({ hidden: false, dataset: {}, textContent: '', setAttribute(name, value) { this[name] = value; } });

function setup() {
  const requests = [];
  const tabs = { ...element(), children: [],
    replaceChildren(...children) { this.children = children; }, append(child) { this.children.push(child); } };
  const context = {
    studio: { available: true, codeTab: 'Hot', commRequest: 0, running: false },
    currentState: { activeLoadCase: 'Cold' }, sourceView: {}, browserJob: null, browserProgress: 'Running Python…',
    bundleSourceEdited: () => false,
    dom: { codeTabs: tabs, codeCase: { ...element(), parentElement: { parentElement: {} }, replaceChildren() {} },
      codeGutter: element(), codeText: { parentElement: {} }, commText: { ...element(), textContent: 'Hot commands', scrollTop: 0 },
      codeRun: element(), codeReset: element(), codeDownload: element(), codeState: element() },
    codePaneCases: () => ['Hot', 'Cold'],
    getLoadCaseOptions: () => [{ id: 'Hot' }, { id: 'Cold' }, { id: 'Inputs only' }],
    codeTabButton: (tab, file) => ({ ...element(), dataset: { codeTab: tab ?? '' }, textContent: file }),
    Option: function Option(text, value) { this.text = text; this.value = value; },
    fetch: url => new Promise(resolve => requests.push({ url, finish: code => resolve({ json: async () => ({ ok: true, code }) }) }))
  };
  runInNewContext(tabsSource + commSource, context);
  return { context, requests };
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('an open Solver .comm follows the selected case and replaces previous input immediately', async () => {
  const { context, requests } = setup();
  context.renderCodeTabs();
  assert.equal(context.studio.codeTab, 'Cold');
  assert.equal(context.dom.commText.textContent, 'Generating…');
  assert.equal(context.dom.codeTabs.children[1]['aria-pressed'], 'true');
  assert.equal(requests[0].url, '/api/comm?case=Cold');
  context.renderCodeTabs();
  assert.equal(requests.length, 1, 'ordinary renders must not generate the same input again');
  requests[0].finish('Cold commands');
  await settle();
  assert.equal(context.dom.commText.textContent, 'Cold commands');
});

test('late input from a previous case cannot overwrite the latest selected case', async () => {
  const { context, requests } = setup();
  context.renderCodeTabs();
  context.currentState.activeLoadCase = 'Hot';
  context.renderCodeTabs();
  requests[1].finish('Latest Hot commands');
  await settle();
  requests[0].finish('Late Cold commands');
  await settle();
  assert.equal(context.studio.codeTab, 'Hot');
  assert.equal(context.dom.commText.textContent, 'Latest Hot commands');
});

test('a case with only declared inputs returns to model.py and ignores a pending .comm', async () => {
  const { context, requests } = setup();
  context.renderCodeTabs();
  context.currentState.activeLoadCase = 'Inputs only';
  context.renderCodeTabs();
  assert.equal(context.studio.codeTab, null);
  assert.equal(context.dom.commText.hidden, true);
  assert.equal(context.dom.codeText.parentElement.hidden, false);
  assert.equal(context.dom.codeTabs.children[0]['aria-pressed'], 'true');
  requests[0].finish('Cold commands');
  await settle();
  assert.notEqual(context.dom.commText.textContent, 'Cold commands');
});

test('case changes keep an authored model.py open and name the geometry update action', () => {
  const { context, requests } = setup();
  context.studio.codeTab = null;
  context.renderCodeTabs();
  assert.equal(context.studio.codeTab, null);
  assert.equal(requests.length, 0);
  assert.equal(context.dom.codeRun.textContent, 'Update geometry');
  assert.match(context.dom.codeRun.title, /Save model\.py and update geometry/);
});

test('published .comm switches cases without regenerating input from a browser draft', async () => {
  const { context, requests } = setup();
  context.studio.available = false;
  context.sourceView = { available: true, baseUrl: 'published',
    loadCases: [{ name: 'Cold', uri: 'Cold.comm' }], text: new Map([['Cold.comm', 'Published Cold commands']]) };
  context.renderCodeTabs();
  await settle();
  assert.equal(context.dom.commText.textContent, 'Published Cold commands');
  assert.equal(requests.length, 0);
});

test('browser preview keeps Stop while a geometry update is active', () => {
  const { context } = setup();
  context.studio.available = false;
  context.studio.codeTab = null;
  context.browserJob = {};
  context.renderCodeTabs();
  assert.equal(context.dom.codeRun.textContent, 'Stop');
  assert.equal(context.dom.codeRun.title, 'Stop the browser preview');
});

test('local geometry updates keep the shortcut chrome and clear the busy label', () => {
  const { context } = setup();
  const label = element();
  context.dom.codeRun.querySelector = () => label;
  context.dom.codeRun.textContent = 'Shortcut chrome';
  context.studio.codeTab = null;
  context.studio.running = true;
  context.renderCodeTabs();
  assert.equal(label.textContent, 'Updating geometry…');
  assert.equal(context.dom.codeRun.textContent, 'Shortcut chrome');
  context.studio.running = false;
  context.renderCodeTabs();
  assert.equal(label.textContent, 'Update geometry');
});
