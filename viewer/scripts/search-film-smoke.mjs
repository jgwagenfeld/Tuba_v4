import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { colorForScalarValue } from '../src/resultReview.js';
const [sourceUrl, output] = process.argv.slice(2);
const url = new URL(sourceUrl); url.searchParams.set('film', '1');
const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = []; page.on('pageerror', e => errors.push(e.message));
const checks = [];
try {
  await page.goto(url.href);
  await page.waitForFunction(() => window.tubaSearchFilm, { timeout: 5000 });
  const canvasBounds = await page.locator('[data-canvas]').boundingBox();
  assert.equal(canvasBounds.x, 0); assert.ok(canvasBounds.width >= 1100);
  checks.push('Drawing occupies the full left 70 percent without hidden rail space');
  const plan = await page.evaluate(() => window.tubaSearchFilm.plan({ holdSeconds: 0.08, sectionComponents: ['N','VY','VZ','MT','MFY','MFZ'] }));
  assert.equal(new Set(plan.keyframes.map(f => f.candidate_id)).size, 12);
  checks.push('All 12 retained candidates have causal film keyframes');
  async function show(frame) {
    assert.ok(frame); return page.evaluate(f => window.tubaSearchFilm.show(f), frame);
  }
  const hot = plan.keyframes.find(f => f.candidate_id === 'C0005' && f.check?.operation === 'Hot');
  const force = plan.keyframes.find(f => f.candidate_id === 'C0007' && f.check?.constraint_id === 'pump.nozzle.force');
  const cold = plan.keyframes.find(f => f.candidate_id === 'C0001' && f.check_index != null);
  await show(cold);
  assert.ok(await page.locator('[data-search-annotations] circle').count());
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: join(output, 'collision.png') });
  let result = await show(hot); assert.equal(result.operation, 'Hot'); assert.match(result.result_state, /Hot/);
  const camera = result.camera;
  result = await show(force); assert.equal(result.operation, 'Hot'); assert.deepEqual(result.camera, camera);
  result = await show(cold); assert.equal(result.operation, 'cold'); assert.equal(result.result_state, '');
  assert.equal(result.visual_deformation_scale, 1); assert.equal(result.units, 'si'); assert.deepEqual(result.camera, camera);
  checks.push('Cold after Hot clears native scope; fixed camera, SI and physical scale 1');
  const interrupted = plan.keyframes.find(f => f.candidate_id === 'C0009' && f.event_kind === 'evaluation.interrupted');
  await show(interrupted); assert.doesNotMatch(await page.locator('[data-film-caption]').textContent(), /Recorded outcome: selected/);
  checks.push('Interrupted attempt does not inherit the later selection');
  for (const [mode, component] of [['stress',null], ['reactions',null], ...['N','VY','VZ','MT','MFY','MFZ'].map(c=>['internal_forces',c]), ['displacement',null]]) {
    const frame = plan.keyframes.find(f => f.candidate_id === 'C0007' && f.operation === 'Hot' && f.result_view === mode && (!component || f.component === component));
    const shown = await show(frame);
    assert.equal(shown.operation, 'Hot'); assert.match(shown.result_state, /Hot/);
    assert.equal(shown.result_view, mode); assert.ok(shown.field_id);
    if (mode !== 'displacement') assert.ok(shown.annotations.length > 0);
    const sourceScene = await page.request.get(new URL(`${frame.view.bundle}/scene.json`,
      new URL('./', new URL(url.searchParams.get('search'), url))).href).then(r => r.json());
    if (mode !== 'displacement') {
      const type = mode === 'internal_forces' ? mode : 'stress';
      const native = sourceScene.overlays.find(o => o.data?.result_type === type && o.data.load_case === 'Hot' && o.data.result_state_id === shown.result_state);
      assert.match(shown.field_id, new RegExp(`:${type}:`));
      assert.equal(shown.pipe_legend.unit, type === 'stress' ? 'Pa' : ['N','VY','VZ'].includes(component) ? 'N' : 'N·m');
      const index = ['N','VY','VZ','MT','MFY','MFZ'].indexOf(component);
      assert.equal(shown.pipe_colours.length, Object.keys(native.data.values).length);
      for (const pipe of shown.pipe_colours) {
        const raw = native.data.values[pipe.object_ids[0]];
        const value = type === 'stress' ? raw : raw[index];
        const expected = `#${colorForScalarValue(value, shown.pipe_legend).toString(16).padStart(6,'0')}`;
        assert.ok(pipe.materials.length);
        assert.ok(pipe.materials.every(m => m.color === expected && m.opacity >= 0.95), JSON.stringify({pipe,expected}));
      }
      const colourPixels = await page.locator('[data-canvas]').evaluate((canvas,type) => {
        const gl=canvas.getContext('webgl2'), p=new Uint8Array(canvas.width*canvas.height*4);
        gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,p);
        let coloured=0;for(let i=0;i<p.length;i+=4){
          const r=p[i],g=p[i+1],b=p[i+2];
          const yellow=r>150&&g>140&&b<120;
          const signed=(r>85&&g<55&&b>10&&b<90)||(r>45&&r<130&&b>r+60&&g<150&&b>130);
          if(yellow||(type==='internal_forces'&&signed))coloured++;
        }
        return coloured;
      },type);
      assert.ok(colourPixels>30, `No visible high-value pipe colour: ${mode}/${component} (${colourPixels} pixels)`);
    }
    for (const [kind, key, unit] of [['force', 'reaction_force_n', 'N'], ['moment', 'reaction_moment_nm', 'N m']]) {
      const native = sourceScene.overlays.find(o => o.data?.result_type === `reaction_${kind}` &&
        o.data.load_case === 'Hot' && o.data.result_state_id === shown.result_state);
      const expected = native.data.vectors.filter(v => Math.hypot(...v[key]) >= 0.005).map(v => v.node_id).sort();
      const actual = shown.support_glyphs.filter(g => g.kind === kind);
      assert.deepEqual(actual.map(g => g.node_id).sort(), expected);
      for (const glyph of actual) {
        assert.equal(glyph.unit, unit);
        assert.deepEqual(glyph.components, native.data.values[glyph.node_id]);
        assert.ok(glyph.meshes.includes(kind === 'force' ? 'reaction-force-shaft' : 'moment-rotation-arc'));
      }
    }
    const pixels = await page.locator('[data-canvas]').evaluate(canvas => {
      const gl = canvas.getContext('webgl2'); const p = new Uint8Array(canvas.width * canvas.height * 4);
      gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, p);
      let blue = 0, orange = 0;
      for (let i = 0; i < p.length; i += 4) {
        if (p[i] < 80 && p[i + 1] < 160 && p[i + 2] > 170) blue++;
        if (p[i] > 200 && p[i + 1] > 60 && p[i + 1] < 160 && p[i + 2] < 80) orange++;
      }
      return { blue, orange };
    });
    assert.ok(pixels.blue > 300 && pixels.orange > 100, JSON.stringify(pixels));
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: join(output, `${mode}${component ? `-${component}` : ''}.png`) });
  }
  checks.push('All nonzero Hot support force and moment glyphs match native nodes/components, with actual blue/orange pixels in every result view');
  checks.push('Every pipe mesh has its native stress or signed section-component colour; matching units and visible high-value pixels for all six components');
  const selected = plan.keyframes.find(f => f.candidate_id === 'C0009' && f.caption.includes('Recorded outcome: selected'));
  result = await show(selected); assert.ok(result.rendered_objects > 0); assert.match(result.result_state, /Sustained/);
  await mkdir(output, { recursive: true }); await page.screenshot({ path: join(output, 'selected.png') });
  checks.push('Selected frame displays native recorded geometry');
  await page.route('**/reviews/C0005/**/scene.json', route => route.fulfill({ status: 404, body: 'controlled missing scene' }));
  result = await show(hot); assert.equal(result.availability, 'unavailable'); assert.equal(result.rendered_objects, 0);
  assert.match(await page.locator('[data-film-caption]').textContent(), /unavailable/i);
  await page.screenshot({ path: join(output, 'unavailable.png') });
  checks.push('Missing scene clears previous native view and captions the unavailable evidence');
  url.searchParams.delete('film');
  await page.goto(url.href);
  await page.locator('[data-search-candidate="C0007"]').click();
  await page.locator('[data-search-constraint="pump.nozzle.force"]').filter({ hasText: 'Hot' }).getByRole('button', { name: 'Show finding' }).click();
  await page.waitForFunction(() => document.querySelector('[data-search-annotations] circle'));
  assert.match(await page.locator('[data-search-annotations]').textContent(), /limit/);
  await page.screenshot({ path: join(output, 'interactive-failure.png') });
  checks.push('Interactive Show finding labels the measured nozzle force and limit on the drawing');
  assert.deepEqual(errors, []);
  await writeFile(join(output, 'browser-validation.json'), JSON.stringify({ checks, page_errors: errors, keyframe_count: plan.keyframes.length }, null, 2));
  console.log(JSON.stringify({ checks: checks.length, page_errors: errors.length, keyframes: plan.keyframes.length }));
} finally { await browser.close(); }
