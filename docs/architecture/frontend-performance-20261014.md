# Frontend navigation performance

Measured on 2026-10-14 against local main `2a391be`, using the running Header
Tower Studio and its retained Code_Aster review. The gallery opens reviews in
the same viewer used by Studio; the gallery card list does not construct a 3D
scene. This investigation targets the shared viewer and native Build/Review
navigation, not Pages freshness or a new solver qualification.

## Cause and change

Every native stage switch fetched, parsed and validated the full scene again:
14,256,092 bytes for Build and 39,147,527 bytes for Review. The renderer then
disposed the previous scene and reconstructed its geometry, materials and GPU
programs. A browser CPU profile showed repeated scene-budget walks, bounding
calculations and shader compilation. Instrumentation counted five scene-budget
validations per load; all existing resource checks remain enabled.

Studio now retains only its two loaded stage bundles and normalized states.
Navigation can reuse them while the live notification socket is connected.
Explicit reloads fetch fresh data. Source, hydraulic and solver publication
events clear the cache; socket open clears pre-subscription snapshots, and
socket failure or close clears it and disables navigation reuse. Superseded
requests cannot seed later cache hits. Gallery and search bundles are not added
to this Studio cache.

The shared renderer retains at most two recently used scene graphs, reusing
unchanged geometry across stage switches and disposing GPU resources on
eviction. Large geometry and result payloads must retain their exact object
identity to qualify for reuse. Small display settings and unchanged overlay
wrappers compare by value. Newly visible assets, changed result fields and new
payloads still require construction. The memory tradeoff is retaining a second
scene, bounded to two graphs rather than an ever-growing history.

## Measurement

`viewer/scripts/navigation-perf.mjs` drives the same model in Chromium at
1440 x 900. Each measurement includes the stage transition and the next painted
frame. The first round warms the stages; three subsequent round trips measure
repeat navigation. These are local browser measurements, not hardware-neutral
latency guarantees.

| Repeated switch | Before, median | After, median | Reduction |
| --- | ---: | ---: | ---: |
| Build | 3,252 ms | 580 ms | 82.2% |
| Review | 6,778 ms | 930 ms | 86.3% |

Warm scene requests dropped from six to zero over the three round trips.
Model, result-state and rendered-object summaries matched across both versions.
The measured first visit to Review still took 5,477 ms: the initial scene load
and construction remain substantial.

## Verification and limits

- All 852 viewer tests passed with ordinary Node process isolation.
- Frontend-only production compilation passed, with the existing application
  chunk-size advisory. The tracked packaged viewer and Python browser runtime
  were not regenerated.
- Browser timing runs blocked API writes, found no JavaScript errors and
  verified the authored source hash stayed unchanged.
- Cache lifecycle checks inject browser-only publication notifications, then
  reload actual retained artifacts. They cover on-screen and off-screen cache
  invalidation and fresh reads after disconnection; they do not run a solver.
- Independent review found a pre-subscription freshness gap, now fixed and
  covered by a regression. The older race where competing in-flight loads can
  replace current state remains separate from retention of stage snapshots.

The native backend and existing Studio process were not restarted. No fresh
Code_Aster solve, backend suite, Pages qualification, release rebuild or remote
push is implied. The isolated source preview uses port 5189. Timing JSON,
screenshots, logs and a browser lifecycle receipt are retained under
`.tmp/frontend-performance-20261014/`, outside tracked source.

## Next priorities

1. Reduce initial scene transfer and parsing: measure duplicate numerical arrays
   and separate large geometry/result payloads so they can load on demand.
2. Consolidate repeated resource validation without weakening the receiving or
   generated-geometry limits, preferably keeping expensive work off the UI thread.
3. Profile remaining panel updates and 3D draws before changing them; the current
   renderer already draws on demand.
4. Investigate native Solver `.comm` generation separately. Its existing handler
   exports a study, potentially including meshing, for a file-tab request. Reuse
   or background compilation needs exact source, study and solver-option identity.
