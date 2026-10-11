import test from 'node:test';
import assert from 'node:assert/strict';
import { createViewerState, applyResultFieldPreset } from '../src/sceneLoader.js';
import { createThreeSceneGraph, prepareAssetRenderConfig, disposeThreeSceneGraph } from '../src/renderer.js';

function fixture() {
  const assets = ['force', 'moment'].map((kind, i) => ({ id: `geometry:${kind}`, format: 'vector', object_ids: [kind],
    generation_config: { source: 'tuba.result_state', result_type: `reaction_${kind}`, node_id: 'N0',
      load_case: 'Hot', result_state_id: 'hot', start: [0, 0, 0], end: [1, 0, 0],
      [kind === 'force' ? 'reaction_force_n' : 'reaction_moment_nm']: i ? [0, 0, -100] : [300, -400, 0] } }));
  const state = createViewerState({ scene: { scene_id: 'fixture:reactions', geometry_assets: assets,
    objects: assets.map((a, i) => ({ id: i ? 'moment' : 'force', kind: 'reaction_vector', geometry_asset_id: a.id,
      layer_ids: [`result:reaction_${i ? 'moment' : 'force'}`], metadata: { load_case: 'Hot', result_state_id: 'hot' } })),
    layers: ['force', 'moment'].map(k => ({ id: `result:reaction_${k}`, category: 'results', default_visible: true })),
    overlays: assets.map((a, i) => ({ id: i ? 'm' : 'f', kind: 'solver_result', object_ids: [i ? 'moment' : 'force'],
      data: { result_type: `reaction_${i ? 'moment' : 'force'}`, load_case: 'Hot', result_state_id: 'hot', values: { N0: i ? [0, 0, -100] : [300, -400, 0] } } })),
    result_fields: [{ id: 'force-field', overlay_id: 'f', load_case: 'Hot', result_state_id: 'hot', components: ['magnitude'], unit: 'N' }]
  } });
  return { ...state, stage: 'review', activeLoadCase: 'Hot', activeResultStateId: 'hot',
    colorChannel: 'results', supportReactionPresentation: true, bounds: [0, 0, 0, 8, 2, 3] };
}

test('support reaction presentation retains both force and moment layers when a field is selected', () => {
  const state = applyResultFieldPreset(fixture());
  assert.equal(state.layers['result:reaction_force'].visible, true);
  assert.equal(state.layers['result:reaction_moment'].visible, true);
});
test('readable force/moment render config preserves measured vectors and separates display scales', () => {
  const s = fixture();
  const f = prepareAssetRenderConfig(s.geometryAssets[0], {}, s);
  const m = prepareAssetRenderConfig(s.geometryAssets[1], {}, s);
  assert.equal(f.reaction_display, true); assert.equal(m.reaction_display, true);
  assert.equal(f.color, '#2563eb'); assert.equal(m.color, '#f97316');
  assert.deepEqual(f.reaction_force_n, [300, -400, 0]); assert.deepEqual(m.reaction_moment_nm, [0, 0, -100]);
  assert.ok(f.end[0] > 0 && f.end[1] < 0); assert.ok(m.end[2] < 0);
  assert.equal(s.geometryAssets[0].generation_config.end[1], 0, 'native source geometry is not rewritten');
});
test('actual scene graph contains a thick force shaft and visible right-hand-rule moment arc', () => {
  const graph = createThreeSceneGraph(applyResultFieldPreset(fixture()));
  const f = graph.objectsByObjectId.get('force'); const m = graph.objectsByObjectId.get('moment');
  assert.equal(f.getObjectByName('reaction-force-shaft')?.isMesh, true);
  assert.equal(m.getObjectByName('moment-rotation-arc')?.isMesh, true);
  for (const glyph of [f, m]) glyph.traverse(p => { if (p.material && !p.isSprite) assert.equal(p.material.depthTest, false); });
  disposeThreeSceneGraph(graph);
});
test('other load cases and missing measured vectors cannot acquire readable reaction glyphs', () => {
  const s = fixture();
  const asset = structuredClone(s.geometryAssets[0]); asset.generation_config.load_case = 'Other';
  assert.notEqual(prepareAssetRenderConfig(asset, {}, s).reaction_display, true);
  asset.generation_config.load_case = 'Hot'; delete asset.generation_config.reaction_force_n;
  assert.notEqual(prepareAssetRenderConfig(asset, {}, s).reaction_display, true);
});
test('build views retain opaque authored obstacles and do not enable reaction presentation', () => {
  const s = { ...fixture(), stage: 'build' };
  assert.notEqual(prepareAssetRenderConfig(s.geometryAssets[0], {}, s).reaction_display, true);
  const obstacle = { id: 'box', format: 'aabb', generation_config: { source: 'tuba.obstacle', opacity: 1 } };
  assert.equal(prepareAssetRenderConfig(obstacle, {}, s).opacity, 1);
});
