# L2 authored iteration implementation and qualification

Date: 2026-10-11. Implementation follows the
[roadmap](llm-piping-design-roadmap.md) and
[L2 plan](../superpowers/plans/2026-10-11-llm-piping-iteration.md).

## Delivered workflow

`scripts.iterate_llm_piping` lets a coding agent submit procedural `model.py`
and explicitly declared local units, with a candidate ID, parents and intent.
No parameter grid is required. A session freezes its task and evaluator;
compiled model checks reject changed loads, properties or forbidden restraints
before any solve. The evaluator uses native permanent-attempt Code_Aster
execution and the shared `tuba.search` records, reviews and replay.

The separate guided case allows up to four ideal Y/Z ground guides at distinct
interior nodes while retaining the L1 endpoints, anchors, DN100 steel properties,
thermal operation, geometric envelope, bend policy and force/moment targets.
The original L1 benchmark keeps its two-anchor-only policy.

Parent source diffs, exact source/dependency inventories, compiled geometry,
solver identities, scoped checks and all decisions remain inspectable. Retry
uses retained source and a new attempt. Recovery distinguishes interrupted
execution, missing publication, failed execution and measured constraint failure.
It refuses to mint a new decision from missing or damaged candidate artifacts.

The committed history/replay baseline through `bbc19e6` is integrated locally;
ongoing film work remains in its separate worktree. Candidate reviews now show
candidate-specific source. Source inventory digests bind to their immutable
references, and new evaluation records fingerprint sealed attempt inventories.
Older evaluation records remain readable without retroactively claiming those
new fingerprints existed. Original native solver attestation remains required.

## Validation record

- L1/L2 initial focused tests: 51 passed.
- Existing history/replay baseline: 157 passed, 1 skipped.
- Viewer replay unit checks: 7 passed.
- Independent read-only review: three Important integrity/recovery issues;
  each reproduced by failing regressions and fixed. No separate Minor issues.
- Final combined suite: 213 passed, 1 skipped, and one stale diagnostic-message
  assertion failed. It expected a missing authored-model message after modifying
  the source inventory; the stronger gate correctly reports an inventory-integrity
  failure first. The updated assertion passed its focused rerun in 17.36 s.
  In total, 214 distinct targeted Python tests passed across these runs, with
  one platform skip; the entire combined command was not repeated after the
  assertion-only correction.
- Final 600-second policy: all 27 authored-iteration tests passed.
- Real guided-case qualification: two completed Code_Aster solves; results below.
- Both native runs reopened with their recorded input identities and passed
  publication validation. Both exported scene contracts validated, with no
  archive availability diagnostics and the correct per-candidate source.
- Five focused browser checks passed: both candidates listed, measured C1 force
  rejection visible, C1 and C2 sealed results/source available, no page errors.
  This was a focused replay browser check, not the full browser suite.

The initial WSL shell-runner attempt timed out and is retained as an evaluation
failure in `D:/tuba-runs/Tuba_v4/llm-iteration-20261011-qualified`. No engineering
result is inferred from it. A direct Linux coordinator probe also found missing
Tuba distribution metadata in the Code_Aster-only environment, before a candidate
was evaluated. The Windows coordinator launches the existing native
`code_aster_bridge.py` through WSL's Code_Aster Python environment.

The 180-second bridge session retained a real 7496 N rejection for C1, then a
timeout for C2. The final guided-case definition therefore freezes a 600-second
execution budget and uses a fresh session:
`D:/tuba-runs/Tuba_v4/llm-iteration-20261011-600s`. This changes a resource limit,
not mechanical loads, acceptance limits or mesh settings. Earlier failed and
successful attempts remain available in `llm-iteration-20261011-final` and
`llm-iteration-20261011-qualified`; no timeout is counted as an engineering pass.

## Measured guided-case iteration

Both candidates use the same material, section, 200 C / 20 C thermal operation,
nozzle anchors, two Z guides, 0.3 m bends, 12 mesh subdivisions and fixed
5000 N / 5000 N m limits. C2 changes only the straight loop-leg rise from 0.4 m
to 0.8 m. The stored parent diff records that single source edit.

| Quantity | C1: starter | C2: child revision |
| --- | ---: | ---: |
| Inlet force resultant, N | 7496.016332 | 3639.422692 |
| Outlet force resultant, N | 7496.016325 | 3639.422679 |
| Inlet moment resultant, N m | 1857.910707 | 1334.811478 |
| Outlet moment resultant, N m | 1857.910734 | 1334.811499 |
| Pipe length, m | 13.484956 | 14.284956 |
| Operation elapsed, s | 104.514 | 49.277 |
| Decision | rejected_constraint | feasible_retained |

Force decreased about 51.4% with 0.8 m more pipe. This is one agent-directed
repair, not an optimal design or a reliability estimate. The final session used
two solver calls. Across L2 development qualification there were five calls:
three completed solves and two retained timeouts. Operation elapsed includes
native export/import/verification; it is not pure FEM time or total agent cost.

Final session: `Rfc1bae7503b94839af0d15554a225fec`.
C1 attempt: `Aac236d553db84a57bf8747db45abd9e2`.
C2 attempt: `A66d24743c2934023b5d0a665ba416ecc`.
Qualification scripts, manifest, replay and browser evidence are retained in
`D:/tuba-runs/Tuba_v4/llm-iteration-validation`.

The archive and replay use real Code_Aster 18.0.12 artifacts. To reopen the
qualified replay using the verified existing viewer build:

```powershell
$env:TUBA_VIEWER_ASSETS = 'D:/tuba-runs/Tuba_v4/search-replay-m2-20261010/viewer-build'
python -m tuba.visualization.viewer D:/tuba-runs/Tuba_v4/llm-iteration-validation/replay --open
```

The benchmark's authored source, solver attempts (including failed attempts),
review bundles, scripts and small logs are deliberately retained. Initial
measurement before browser screenshots: 223,479,901 bytes retained across the
five L2 evidence/source directories; D: had 682,706,522,112 free bytes. The
final `storage.json` includes screenshots. The unused initial empty session was
removed, and no dependency installation, new viewer build or full source archive
was created for this task. Existing shared viewer assets remain untouched.

The reused review build has identity
`sha256:80b89952c208de12c94d38a02102b8a3a2e3b9dc3ea955f6b6af8bacd217848c`,
verified against the current merged viewer source. It is the existing read-only
web renderer, not a third visualization surface or a new browser Python build.

## Boundaries

This is a local coding-agent workflow, not an autonomous LLM-provider service.
No model version, tokens or provider cost is recorded by this script; an L3
comparison must pin and record them. There is no automatic best-candidate ranking
or result reuse between arbitrary source revisions in this milestone.

Scripts are trusted Python. This task does not establish industrial nozzle
allowables, support capacity, gravity/pressure behavior, friction, operating
clearance, piping-code compliance or repeat-run design reliability.

Use the [example commands](../../examples/llm-piping-iteration/README.md) to
initialize a session, submit/revise a design, inspect checks, retry failures and
export a reviewable replay.
