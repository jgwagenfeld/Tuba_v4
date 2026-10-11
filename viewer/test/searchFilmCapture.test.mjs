import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Writable } from 'node:stream';
import { encoderArgs, writeHeldFrames, captureFilm } from '../scripts/search-film.mjs';

test('encoding sets explicit fps, VP8 and dimensions without a shell', () => {
  const args = encoderArgs(1600, 900, 25, 'path with spaces/film.webm');
  assert.ok(args.includes('libvpx')); assert.ok(args.includes('25'));
  assert.equal(args.at(-1), 'path with spaces/film.webm');
});
test('held image stream sends exactly the declared integer frame count, respecting backpressure', async () => {
  const chunks = [];
  const stream = new Writable({ highWaterMark: 1, write(chunk, encoding, callback) { chunks.push(Buffer.from(chunk)); setImmediate(callback); } });
  await writeHeldFrames(stream, Buffer.from('image'), 3);
  assert.equal(Buffer.concat(chunks).toString(), 'imageimageimage');
});
test('encoder startup failure preserves an explicit failed manifest', async () => {
  const root = await mkdtemp(join(tmpdir(), 'tuba-film-failure-'));
  const output = join(root, 'export');
  await assert.rejects(captureFilm({ url: 'http://127.0.0.1:1/', output, ffmpeg: join(root, 'missing-ffmpeg.exe') }));
  const manifest = JSON.parse(await readFile(join(output, 'film.json')));
  assert.equal(manifest.status, 'failed'); assert.ok(manifest.error);
});
test('existing output is refused without overwriting data', async () => {
  const output = await mkdtemp(join(tmpdir(), 'tuba-film-existing-'));
  await mkdir(join(output, 'evidence'));
  await assert.rejects(captureFilm({ url: 'http://127.0.0.1:1/', output, ffmpeg: 'ffmpeg' }), /EEXIST/);
});
