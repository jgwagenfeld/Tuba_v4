# Recorded Piping Search Film Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export an auditable film of retained search events and their rejection evidence.

**Architecture:** One JavaScript planner consumes the existing causal replay projection. An explicit bridge drives the existing viewer; Node captures held keyframes and encodes WebM. Python CLI serves the unchanged replay package and invokes that source-checkout capture tool.

**Tech Stack:** Existing Python, Three.js, Node, Playwright, FFmpeg VP8; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-11-piping-search-film-design.md`

## Global Constraints

- Use `viewer/` and its existing Three.js renderer; add no third renderer.
- Consume an existing `tuba.search.viewer.v1` replay package without modifying or copying its native artifacts.
- Produce a WebM film, unique PNG keyframes, WebVTT captions and `film.json` in a new output directory. Refuse existing output directories.
- Local commits only; preserve other worktrees and existing native history. Build and film outputs stay outside tracked source.
- Use existing Node, Playwright and FFmpeg installations. Do not download dependencies automatically. Report missing runtime requirements plainly.

## Review Focus

1. Concurrent/sealed earlier attempts must be selected by event evaluation ID, never by the final candidate row.
2. An unavailable or failed scene must not leave a previous native result visible under a new caption.
3. A cold finding after Hot must clear operation/state and reset physical visual scale.
4. Encoder/browser failure must retain a failed manifest and no successful movie claim.
5. Ranges, paths and caption text must remain bounded and treated as data, without shell or HTML interpretation.

### Task 1: Causal film planner

**Files:** Create `viewer/src/searchFilm.js`, `viewer/test/searchFilm.test.mjs`.

**Interfaces:** Consumes `replayAt(manifest, sequence)`; produces `planSearchFilm(manifest, options)` with ordered keyframes, integer frame ranges and captions; `filmVtt(plan)` emits WebVTT.

- [ ] Write failing tests for future outcome isolation, exact evaluation/failed check mapping, recovery without invented checks, ranged/all-event selection, deterministic timing, invalid bounds and literal caption text.

```js
const p = planSearchFilm(manifest, { start: 2, end: 2, fps: 25, holdSeconds: 2 });
assert.equal(p.keyframes[0].start_frame, 0);
assert.equal(p.keyframes[0].end_frame, 50);
assert.doesNotMatch(p.keyframes[0].caption, /selected/);
```

- [ ] Run `node --test viewer/test/searchFilm.test.mjs`. Expected: missing module/API failure.
- [ ] Implement milestone selection, event-local evaluation resolution, check keyframes, evidence-derived captions and VTT escaping/timecodes.
- [ ] Run the same command. Expected: all planner tests pass.
- [ ] Commit explicit Task 1 paths with `feat(search): plan causal film frames and evidence captions`.

### Task 2: Viewer capture bridge and encoder

**Files:** Modify `viewer/src/searchReplayPanel.js`, `viewer/src/app.js`, `viewer/src/renderer.js`, `viewer/src/style.css`; create `viewer/scripts/search-film.mjs`, `viewer/test/searchFilmCapture.test.mjs`.

**Interfaces:** Consumes Task 1 plan. Produces `window.tubaSearchFilm.plan(options)` and async `.show(keyframe)`; renderer common-envelope fit/camera snapshot; capture script accepts viewer URL/output/FFmpeg/options and produces film artifacts.

- [ ] Add failing capture tests for held image stream timing, failure status, output refusal and manifest/hash records. Add browser assertions for event-local check selection, unavailable clearing and cold-after-Hot scope.

```js
assert.equal(typeof captureFilm, 'function');
assert.equal(encoderArgs(1600, 900, 25, 'film.webm').includes('libvpx'), true);
```

- [ ] Run `node --test viewer/test/searchFilm*.test.mjs`. Expected: capture module/API absent.
- [ ] Extend replay panel with an awaited `seek(sequence, candidateId, evaluationId, checkIndex)` path, sharing existing projection/display handling. Expose the bridge only for `film=1`, render text-only captions, fix SI/physical-scale and fit the union of segment scene envelopes once. Capture after two animation frames and font readiness.
- [ ] Encode repeated JPEG bytes through FFmpeg image2pipe without duplicate disk frames; retain PNG keyframes, VTT and manifest. Bound options/output and record browser/encoder/viewer identities. Failure writes `status=failed`.
- [ ] Run the same focused Node tests. Expected: green. Build current viewer outside source and run actual native browser capture; expected: recorded cold/Hot/retry/selection frames and playable WebM.
- [ ] Commit explicit Task 2 source/test paths with `feat(viewer): capture recorded search films with auditable frames`.

### Task 3: CLI, qualification and documentation

**Files:** Create `tuba/search/film.py`, `tests/test_search_film.py`; modify `tuba/search/__main__.py`, `tuba/search/__init__.py`, `docs/content/piping-search.md`, `docs/architecture/piping-search-roadmap.md`, `examples/piping-search/README.md`.

**Interfaces:** Consumes capture script and `create_server(package)`; produces `write_search_film(package, output, *, ffmpeg, node, start, end, events, fps, hold_seconds, width, height)` and `python -m tuba.search film`.

- [ ] Write failing tests for CLI arguments, missing runtimes, existing output, confinement to a replay package and a capture subprocess failure.

```python
with pytest.raises(FileExistsError):
    write_search_film(package, existing_output, ffmpeg=encoder)
```

- [ ] Run `python -m pytest tests/test_search_film.py -q`. Expected: missing API failure.
- [ ] Implement local server/thread lifecycle and argument-list subprocess invocation, validate options before capture and check final manifest/movie. Document source-checkout requirements, event ranges, evidence semantics and exact qualification limits.
- [ ] Run Python search/replay/viewer regressions and full Node unit suite. Expected: green except the known Windows symlink-permission skip.
- [ ] Capture all native candidates through the CLI; verify representative decoded video seeks, explicit unavailable capture, hashes unchanged, exact frame/caption coverage, source provenance and retained storage. Expected: successful film, inspectable failure evidence, zero new solver calls.
- [ ] Commit explicit Task 3 paths with `feat(cli): export and qualify retained piping search films`.

## Completion

One fresh whole-range review against the spec and five focus cases; fix Important/Critical findings in one RED-to-GREEN pass, ledger deferred Minors. Retain source, final films/manifests, small validation logs and necessary failure evidence. Keep local branch/worktree; do not merge or push. Handoff links the film, plan, validation and deferred limitations.
