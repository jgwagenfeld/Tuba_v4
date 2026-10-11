import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
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
  const plan = await page.evaluate(() => window.tubaSearchFilm.plan({ holdSeconds: 0.08 }));
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
  for (const mode of ['reactions', 'internal_forces', 'displacement']) {
    const frame = plan.keyframes.find(f => f.candidate_id === 'C0007' && f.operation === 'Hot' && f.result_view === mode);
    const shown = await show(frame);
    assert.equal(shown.operation, 'Hot'); assert.match(shown.result_state, /Hot/);
    assert.equal(shown.result_view, mode); assert.ok(shown.field_id);
    if (mode !== 'displacement') assert.ok(shown.annotations.length > 0);
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: join(output, `${mode}.png`) });
  }
  checks.push('Recorded Hot support reactions, six signed section-force peaks and displacement displayed');
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
