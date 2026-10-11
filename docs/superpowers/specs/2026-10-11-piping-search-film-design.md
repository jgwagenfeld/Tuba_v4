# M3: Recorded piping-search film

The accepted roadmap calls for reproducible capture of selected search timeline
segments in the existing viewer. A film explains recorded proposals, trials and
decisions; it does not claim to reveal private agent reasoning. The initial
benchmark is the recorded deterministic search, not a newly run agent.

## Contract

- Use `viewer/` and its existing Three.js renderer; add no third renderer.
- Consume an existing `tuba.search.viewer.v1` replay package without modifying or copying its native artifacts.
- Produce a WebM film, unique PNG keyframes, WebVTT captions and `film.json` in a new output directory. Refuse existing output directories.
- Derive each keyframe and caption from `replayAt(manifest, event_sequence)`. Never expose a future evaluation or decision.
- Record event sequence/kind/time, candidate, evaluation/attempt, check index, operation/state, exact caption, PNG hash and encoded frame range for each keyframe.
- Default to milestone events; allow all events and inclusive event-sequence ranges. Constant integer frame holds define presentation time, independent of search timestamps and solver pseudo-time.
- Show failed/unknown checks separately, with their actual message, basis, targets, measurements/limits, operation/state and evidence references. Selection/objective captions use recorded decisions, not invented explanations.
- Keep reference geometry clearly unsolved. Missing or damaged views yield an explicit unavailable card with no retained stale scene. Recovered/interrupted attempts do not inherit later checks or selection.
- Fix SI units, physical visual deformation scale 1, colour comparison policy and a common camera envelope for the segment. Captions distinguish engineering displacement scale from presentation timing. No interpolation between layouts.
- Capture through an explicit browser bridge that awaits the accepted scene, fonts and rendered frames. Require WebGL for geometry; abort on unexpected browser errors or encoder failure. Failed exports preserve a failure manifest and never claim completion.
- Use existing Node, Playwright and FFmpeg installations. Do not download dependencies automatically. Report missing runtime requirements plainly.
- Source-checkout capture is supported initially; installed wheels lacking the capture script report that requirement. WebM uses the existing VP8 encoder; MP4 is a later encoder option.
- Local commits only; preserve other worktrees and existing native history. Build and film outputs stay outside tracked source.

## Qualification

Portable tests cover causal projection, check/state mapping, recovery, safe ranges,
deterministic frame timing, captions, output refusal and failure reporting.
Qualification captures all 12 retained real benchmark candidates, including cold,
Hot clearance, Hot nozzle force, interrupted retry and final selection. Browser
decoding verifies the encoded duration and seeks representative frames. Verify
native package hashes before/after; this is capture qualification with zero new
Code_Aster calls, not fresh engineering or piping-standard qualification.
