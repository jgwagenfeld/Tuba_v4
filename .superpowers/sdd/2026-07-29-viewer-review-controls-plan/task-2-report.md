# Task 2 Report: Accessible Viewer Section and Camera Controls

## Status

DONE

## RED

Command (from `viewer/`):

```text
node --test --test-name-pattern "camera|section|scaffold"
```

Exact failing causes:

```text
SyntaxError: The requested module '../src/renderer.js' does not provide an export named 'STANDARD_VIEW_DIRECTIONS'
...
The input did not match the regular expression /<div[^>]*data-section-box-controls[^>]*><\/div>/
```

The follow-up zoom contract also failed before implementation:

```text
SyntaxError: The requested module '../src/renderer.js' does not provide an export named 'zoomCameraBy'
```

## GREEN

Focused unit command (from `viewer/`):

```text
node --test --test-name-pattern "camera|section|scaffold"
```

Output:

```text
# tests 23
# pass 23
# fail 0
```

Browser command (from `viewer/`):

```text
& 'C:\Program Files\nodejs\npm.cmd' run e2e -- section-camera
```

Output:

```text
section-camera fingerprints: zoom=3196515871 section=3474741164 reset=3196515871
section-camera ok: 4 objects, 120/2500 varied samples
```

Full viewer command (from `viewer/`):

```text
& 'C:\Program Files\nodejs\npm.cmd' test
```

Output:

```text
# tests 184
# pass 184
# fail 0
# cancelled 0
```

`npm run build` also completed successfully. Its generated `tuba/visualization/_viewer` changes were restored to HEAD because Task 2 does not own vendored build artifacts.

## Files

- `viewer/index.html`
- `viewer/src/app.js`
- `viewer/src/renderer.js`
- `viewer/src/styles.css`
- `viewer/test/scaffold.test.js`
- `viewer/test/renderer.test.js`
- `viewer/scripts/e2e-smoke.mjs`

## Self-review

- Section inputs are native labelled number controls, default to scene bounds, and reject non-finite or crossing values before `applySectionBox` mutates state.
- Standard views reuse `fitCameraToBounds`; +/-Z use Y-up to avoid a degenerate look direction. Orthographic zoom clamps to `0.05..20`, updates its projection matrix, and redraws.
- The E2E proof keyboard-activates +Z, verifies the published camera direction, checks zoom redraw, confirms the crossing smoke pipe stays renderable under real clipping, and verifies the reset framebuffer returns to the pre-section fingerprint.
- `git diff --check` passed. Git printed only expected CRLF conversion notices.

## Commit

`feat: add accessible viewer section and camera controls` (this task commit).

## Concerns

None.

## Fix Round 1

### RED

Command (from `viewer/`):

```text
node --test test/controls.test.js --test-name-pattern "section box defaults"
```

Output:

```text
SyntaxError: The requested module '../src/controls.js' does not provide an export named 'sectionBoxDefaults'
```

### GREEN

Focused command (from `viewer/`):

```text
node --test --test-name-pattern "section box defaults|applySectionBox" test/controls.test.js
```

Output:

```text
# tests 2
# pass 2
# fail 0
```

Browser command (from `viewer/`):

```text
& 'C:\Program Files\nodejs\npm.cmd' run e2e -- section-camera
```

Output:

```text
section-camera fingerprints: zoom=3196515871 section=3474741164 reset=3196515871; max channel drift=0
section-camera ok: 4 objects, 120/2500 varied samples
```

Full viewer command (from `viewer/`):

```text
& 'C:\Program Files\nodejs\npm.cmd' test
```

Output:

```text
# tests 185
# pass 185
# fail 0
```

Self-review: `sectionBoxDefaults` pads only degenerate axes by a scale-relative `1e-6`; section interaction now redraws only the canvas and updates the existing controls in place; the browser proof retains keyboard focus and uses per-channel sampled-pixel reset tolerance (one channel value) rather than numeric hash distance. +Z now requires near-zero X/Y as well as negative Z.

Concerns: none.
