import { chromium } from '@playwright/test';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, writeFile, readFile, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { filmVtt } from '../src/searchFilm.js';
import { filmPlayer } from '../src/searchFilmPlayer.js';

const execute = promisify(execFile);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function encoderArgs(width, height, fps, output) {
  return ['-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(fps),
    '-i', 'pipe:0', '-an', '-c:v', 'libvpx', '-b:v', '1800k', '-deadline', 'good', '-cpu-used', '4',
    '-threads', '2', '-vf', `scale=${width}:${height}`, '-f', 'webm', '-n', output];
}
export async function writeHeldFrames(stream, bytes, count) {
  for (let i = 0; i < count; i++) await new Promise((resolve, reject) => stream.write(bytes, error => error ? reject(error) : resolve()));
}

export async function captureFilm({ url, output, ffmpeg, options = {} }) {
  const target = new URL(url);
  if (target.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname)) throw new Error('Film capture requires the local replay server');
  await mkdir(output, { recursive: false }); // Intentionally outside failure catch: never overwrite.
  let manifest = { schema: 'tuba.search.film.v1', status: 'capturing', keyframes: [] };
  let browser, encoder, encoderDone;
  const pageErrors = [];
  let encoderLog = '';
  const save = () => writeFile(join(output, 'film.json'), JSON.stringify(manifest, null, 2) + '\n');
  try {
    await save();
    const version = await execute(ffmpeg, ['-version'], { windowsHide: true, timeout: 10000, maxBuffer: 65536 });
    manifest.runtime = { node: process.version, encoder: resolve(ffmpeg), encoder_version: version.stdout.split('\n')[0].trim() };
    target.searchParams.set('film', '1');
    browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-webgl'] });
    manifest.runtime.browser = browser.version();
    // The planner independently validates the exact capture options.
    const page = await browser.newPage({ viewport: { width: options.width ?? 1600, height: options.height ?? 900 }, deviceScaleFactor: 1 });
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto(target.href, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => window.tubaSearchFilm, null, { timeout: 15000 });
    const plan = await page.evaluate(o => window.tubaSearchFilm.plan(o), options);
    manifest = { ...plan, status: 'capturing', runtime: manifest.runtime, viewer_url: target.href, page_errors: pageErrors };
    const searchUrl = new URL(target.searchParams.get('search'), target);
    const sourceBytes = await page.request.get(searchUrl.href).then(r => r.body());
    manifest.replay_sha256 = hash(sourceBytes);
    await mkdir(join(output, 'frames'));
    await save();
    encoder = spawn(ffmpeg, encoderArgs(plan.width, plan.height, plan.fps, join(output, 'film.webm')), { windowsHide: true, stdio: ['pipe', 'ignore', 'pipe'] });
    encoder.stdin.on('error', () => {});
    encoder.stderr.on('data', chunk => { encoderLog = (encoderLog + chunk).slice(-262144); });
    encoderDone = new Promise(resolve => {
      encoder.once('error', error => resolve({ error: error.message }));
      encoder.once('close', code => resolve({ code }));
    });
    for (const frame of manifest.keyframes) {
      const rendered = await page.evaluate(f => window.tubaSearchFilm.show(f), frame);
      if (pageErrors.length) throw new Error(`Browser capture failed: ${pageErrors.join('; ')}`);
      const png = await page.screenshot({ type: 'png', animations: 'disabled' });
      frame.png = `frames/${frame.frame_id}.png`; frame.png_sha256 = hash(png);
      frame.capture = rendered; frame.source_caption = frame.caption; frame.caption = rendered.caption;
      await writeFile(join(output, frame.png), png);
      const jpeg = await page.screenshot({ type: 'jpeg', quality: 94, animations: 'disabled' });
      await writeHeldFrames(encoder.stdin, jpeg, frame.end_frame - frame.start_frame);
      await save();
    }
    encoder.stdin.end();
    const result = await encoderDone;
    if (result.code !== 0) throw new Error(`FFmpeg failed: ${result.error ?? result.code}: ${encoderLog}`);
    const movie = await readFile(join(output, 'film.webm'));
    if (movie.length < 100) throw new Error('Encoder produced no usable movie');
    manifest.movie = { path: 'film.webm', sha256: hash(movie), size_bytes: movie.length };
    manifest.status = 'complete';
    await writeFile(join(output, 'captions.vtt'), filmVtt(manifest));
    if (manifest.events_policy === 'iterations') await writeFile(join(output, 'index.html'), filmPlayer(manifest));
    await save();
    return manifest;
  } catch (error) {
    manifest.status = 'failed'; manifest.error = error.message; manifest.page_errors = pageErrors;
    await save();
    throw error;
  } finally {
    if (encoder && encoder.exitCode == null) { encoder.stdin.destroy(); encoder.kill(); }
    if (encoderDone) await encoderDone;
    if (encoderLog) await writeFile(join(output, 'encoder.log'), encoderLog);
    await browser?.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [url, output, ffmpeg, json = '{}'] = process.argv.slice(2);
  if (!url || !output || !ffmpeg) throw new Error('Usage: node search-film.mjs <local-viewer-url> <new-output-dir> <ffmpeg> [options-json]');
  const film = await captureFilm({ url, output, ffmpeg, options: JSON.parse(json) });
  console.log(JSON.stringify({ status: film.status, keyframes: film.keyframes.length, frames: film.total_frames, duration: film.duration_seconds, output }));
}
