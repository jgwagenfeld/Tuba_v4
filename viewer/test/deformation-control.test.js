import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('committing deformation scaling exits preview and refreshes the layer readout', () => {
  const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  const control = source.slice(source.indexOf('function deformationControl()'), source.indexOf('function animateButton()'));
  const elements = [];
  const document = { createElement() {
    const element = { dataset: {}, listeners: {}, setAttribute() {}, append() {},
      addEventListener(name, callback) { this.listeners[name] = callback; } };
    elements.push(element);
    return element;
  } };
  let active = false;
  let renderedScale = 38;
  const state = { scale: 38 };
  const viewport = { setDeformationInteraction(value) { const changed = active !== value; active = value; return changed; },
    renderDeformation() { return active; } };
  new Function('document', 'currentState', 'getVisualDeformationDisplayScale', 'formatScale',
    'stopDeformationAnimation', 'dispatch', 'viewportRenderer', 'renderCanvas', 'render', 'animateButton',
    `${control}; deformationControl();`)(document, state, s => s.scale, String, () => {},
      action => { state.scale = Number(action.scale); }, viewport, () => {},
      () => { renderedScale = state.scale; }, () => ({}));
  const input = elements.find(element => element.type === 'range');
  input.listeners.pointerdown();
  input.value = '10';
  input.listeners.input();
  input.listeners.change?.();
  input.listeners.pointerup();
  assert.equal(active, false);
  assert.equal(renderedScale, 10, 'The layer readout must match the committed slider scale');
  input.value = '20';
  input.listeners.input();
  input.listeners.change?.();
  assert.equal(renderedScale, 20, 'Keyboard changes must refresh the layer readout too');
});
