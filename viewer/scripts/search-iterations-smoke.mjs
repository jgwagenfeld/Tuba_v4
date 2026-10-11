import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { colorForScalarValue } from '../src/resultReview.js';

const [sourceUrl, output] = process.argv.slice(2);
const url = new URL(sourceUrl); url.searchParams.set('film', '1');
const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [], captures = [];
page.on('pageerror', e => errors.push(e.message));
try {
  await mkdir(output, { recursive: true });
  await page.goto(url.href);
  await page.waitForFunction(() => window.tubaSearchFilm);
  const plan = await page.evaluate(() => window.tubaSearchFilm.plan({ events: 'iterations', holdSeconds: 8 }));
  assert.equal(new Set(plan.keyframes.map(f => f.candidate_id)).size, 12);
  assert.equal(plan.keyframes.length, 14); // 12 layouts, interrupted retry, final selection.
  assert.ok(plan.keyframes.every(f => f.result_view === 'iteration'));
  assert.deepEqual(plan.keyframes.map(f => f.event_sequence), [29,46,63,80,103,126,149,172,189,211,234,257,280,285]);
  let camera;
  for (const frame of plan.keyframes) {
    const shown = await page.evaluate(f => window.tubaSearchFilm.show(f), frame);
    assert.equal(shown.availability, 'available'); assert.ok(shown.rendered_objects > 0);
    if (camera) assert.deepEqual(shown.camera, camera); else camera = shown.camera;
    assert.equal(shown.candidate_id, frame.candidate_id);
    assert.equal(shown.visual_deformation_scale, 1);
    if (frame.native_results) {
      assert.equal(shown.operation, 'Hot'); assert.equal(shown.result_state, 'result_state:Hot');
      assert.ok(shown.field_id); assert.equal(shown.pipe_colours.length, 12);
      const scene = await page.request.get(new URL(`${frame.view.bundle}/scene.json`,
        new URL('./', new URL(url.searchParams.get('search'), url))).href).then(r => r.json());
      const stress = scene.overlays.find(o => o.data?.result_type === 'stress' && o.data.load_case === shown.operation && o.data.result_state_id === shown.result_state);
      for (const pipe of shown.pipe_colours) {
        const expected = `#${colorForScalarValue(stress.data.values[pipe.object_ids[0]], shown.pipe_legend).toString(16).padStart(6, '0')}`;
        assert.ok(pipe.materials.every(m => m.color === expected && m.opacity >= .95));
      }
      for (const kind of ['force', 'moment']) {
        const overlay = scene.overlays.find(o => o.data?.result_type === `reaction_${kind}` && o.data.load_case === shown.operation && o.data.result_state_id === shown.result_state);
        const native = overlay.data.vectors.filter(v => Math.hypot(...v[`reaction_${kind === 'force' ? 'force_n' : 'moment_nm'}`]) >= .005).map(v => v.node_id).sort();
        const glyphs = shown.support_glyphs.filter(g => g.kind === kind);
        assert.deepEqual(glyphs.map(g => g.node_id).sort(), native);
        for (const glyph of glyphs) assert.deepEqual(glyph.components, overlay.data.values[glyph.node_id]);
      }
      assert.match(shown.caption, /checks passed/);
      assert.ok(shown.annotations.some(a => /: F .* N · M .* N m/.test(a.label)));
      const pixels = await page.locator('[data-canvas]').evaluate(canvas => {
        const gl = canvas.getContext('webgl2'), p = new Uint8Array(canvas.width * canvas.height * 4);
        gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, p);
        let blue = 0, orange = 0;
        for (let i = 0; i < p.length; i += 4) {
          if (p[i] < 80 && p[i + 1] < 160 && p[i + 2] > 170) blue++;
          if (p[i] > 200 && p[i + 1] > 60 && p[i + 1] < 160 && p[i + 2] < 80) orange++;
        }
        return { blue, orange };
      });
      assert.ok(pixels.blue > 300 && pixels.orange > 100, JSON.stringify(pixels));
    } else {
      assert.equal(shown.operation, 'cold'); assert.equal(shown.result_state, '');
      assert.equal(shown.field_id, null); assert.equal(shown.support_glyphs.length, 0);
      assert.match(shown.caption, /not evaluated|unavailable/);
    }
    const failures = shown.annotations.filter(a => a.severity === 'fail');
    if (['C0001', 'C0003'].includes(frame.candidate_id)) assert.equal(failures.length, 6);
    if (['C0002', 'C0004'].includes(frame.candidate_id)) assert.equal(failures.length, 4);
    if (['C0005', 'C0006'].includes(frame.candidate_id)) {
      assert.equal(failures.length, 2); assert.match(shown.caption, /cold 128 mm → Hot/);
      assert.match(shown.caption, /Reference layout/);
    }
    if (['C0007', 'C0008'].includes(frame.candidate_id)) {
      assert.equal(failures.length, 2);
      assert.match(shown.caption, /pump.nozzle.force/); assert.match(shown.caption, /rack.tie_in.force/);
      assert.ok(failures.every(a => /limit 10,000 N/.test(a.label)));
    }
    if (frame.event_kind === 'evaluation.interrupted') assert.doesNotMatch(shown.caption, /SELECTED|FEASIBLE/);
    if (frame.event_sequence === 211) assert.match(shown.caption, /FEASIBLE/);
    if (frame.phase === 'selection') {
      assert.match(shown.caption, /C0010: feasible, tied objectives/);
      assert.match(shown.caption, /C0011: feasible, not selected/);
      assert.match(shown.caption, /C0012: feasible, not selected/);
    }
    await page.screenshot({ path: join(output, `${frame.frame_id}-${frame.candidate_id}.png`) });
    captures.push({ frame, capture: shown });
  }
  // Exercise the scope reset in reverse after viewing the selected Hot result.
  const cold = await page.evaluate(f => window.tubaSearchFilm.show(f), plan.keyframes[0]);
  assert.equal(cold.operation, 'cold'); assert.equal(cold.support_glyphs.length, 0);
  await page.route('**/reviews/C0005/**/scene.json', route => route.fulfill({ status: 404, body: 'controlled missing scene' }));
  const unavailable = await page.evaluate(f => window.tubaSearchFilm.show(f), plan.keyframes[4]);
  assert.equal(unavailable.availability, 'unavailable'); assert.equal(unavailable.rendered_objects, 0);
  assert.equal(unavailable.support_glyphs.length, 0); assert.equal(unavailable.field_id, null);
  assert.match(unavailable.caption, /unavailable/i);
  assert.deepEqual(errors, []);
  await writeFile(join(output, 'validation.json'), JSON.stringify({ status: 'passed', keyframes: 14, candidates: 12, duration_seconds: plan.duration_seconds,
    checks: ['chronological candidate evaluations', 'all failures together per operation/state', 'exact native pipe colours and support glyphs',
      'unsolved and interrupted attempts have no results', 'selection appears after comparison', 'Hot-to-cold reset', 'missing scene clears prior results'],
    page_errors: errors, captures }, null, 2));
  console.log(JSON.stringify({ status: 'passed', candidates: 12, keyframes: 14, duration: plan.duration_seconds }));
} finally { await browser.close(); }
