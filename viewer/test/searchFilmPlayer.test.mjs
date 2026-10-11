import test from 'node:test';
import assert from 'node:assert/strict';
import { filmPlayer } from '../src/searchFilmPlayer.js';

test('movie chapters use the capture timing, show the retry and escape evidence text', () => {
  const html = filmPlayer({ fps: 25, duration_seconds: 112, keyframes: [
    { candidate_id: 'C1', start_frame: 0, png: 'frames/F1.png', caption: 'C1 · iteration\n\nREJECTED </script><script>alert(1)</script>' },
    { candidate_id: 'C2', start_frame: 200, outcome: 'interrupted', caption: 'C2 · iteration\n\nINTERRUPTED' },
    { candidate_id: 'C2', start_frame: 400, phase: 'selection', caption: 'C2 · final choice\n\nSELECTED' }
  ] });
  assert.match(html, /Play all iterations \(1:52\)/);
  assert.match(html, /C2 · interrupted/); assert.match(html, /Final choice/);
  assert.match(html, /"time":8/); assert.match(html, /"time":16/);
  assert.match(html, /\\u003c\/script>/); assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;\/script&gt;/);
});
