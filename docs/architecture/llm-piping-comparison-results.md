# L3 comparison foundation: measured reference campaign

Date: 2026-10-11. Evaluator implementation: `6d7ab39`.

The multi-case comparison foundation is implemented and a deterministic reference
completed six trials using 12 fresh Code_Aster solves. All six trials found a
candidate satisfying their declared thermal benchmark checks. **No live LLM trials
were run.** This qualifies reference execution and accounting, not LLM superiority,
general routing capability or industrial piping compliance.

See the [roadmap](llm-piping-design-roadmap.md),
[usage and protocol](../../examples/llm-piping-comparison/README.md), and
[implementation/review ledger](../superpowers/plans/2026-10-11-llm-piping-comparison.md).

## What was implemented

- Explicit versioned cases, passed to compiled-model and reaction checks without
  changing shared globals. Existing L1/L2 defaults are preserved.
- An immutable campaign protocol with all repeat slots, case definitions,
  starting source, evaluator, method/model/prompt/tool metadata and budgets.
- One existing authored search session per trial, bound to its unique run identity.
  Candidate source, parent diffs, permanent attempts and measured checks remain in
  the existing search-history system.
- Provider-neutral start/submit/finish APIs and a deterministic reference CLI.
  Invalid proposals, submission failures, late admission rejections, partial
  initialization and unstarted trials remain visible. Pending decisions recover
  before another proposal is admitted.
- Reports verify source, compiled model and sealed result evidence before counting
  feasibility; replacing a same-case session cannot count it as another repeat.
  Model usage is caller reported or unknown. Late rejected submissions retain
  already-incurred usage. Representation groups are reported separately.

## Frozen experiment

Campaign ID: `Bfe9206cd8d784dffa5f4cc67f309aa7a`.

The `ascending-loop-v1` reference tries straight loop-leg rises 0.4, 0.8 and 1.6 m
in order and stops at first feasibility. Crown width, two ideal Z guides, DN100
section, steel properties and anchored nozzle coordinates remain fixed. The
centerline height includes another 0.6 m from the bend arcs. Each trial has at
most three admitted proposals, three solver calls and an 1800 s admission deadline;
each solve has a 600 s timeout. Repeats run fresh solves, with no result cache.

All operations are thermal only, with a 20 C reference temperature, no gravity or
pressure, and a 5000 N m nozzle moment target. Force targets are benchmark choices,
not vendor allowables. Cases are related pilot variants derived from L2, not a
held-out industrial test set.

| Case | Temperature / y envelope | Force limit | Feasible / finished | Solves per repeat | Accepted rise | Route length | Max endpoint force |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Original | 200 C / 0..4 m | 5000 N | 2 / 2 | 2, 2 | 0.8 m | 14.284956 m | 3639.423 N |
| Hotter | 300 C / 0..4 m | 5000 N | 2 / 2 | 3, 3 | 1.6 m | 15.884956 m | 2096.708 N |
| Compact | 200 C / 0..1.2 m | 8000 N | 2 / 2 | 1, 1 | 0.4 m | 13.484956 m | 7496.016 N |

The original case rejected the 0.4 m rise at 7496.016 N. The hotter case rejected
both 0.4 m and 0.8 m rises at 11660.470 N and 5661.324 N respectively. Those six
rejected candidates are retained alongside the six feasible candidates. The
accepted maximum moments were 1334.811 N m (original), 1319.022 N m (hotter) and
1857.911 N m (compact), all below their declared 5000 N m target.

This reference stops at the first feasible proposal; it does not establish a
minimum-length design. The compact case has a different force target, so its
shorter route is not an improvement under the original requirements.

## Timing and costs

| Trial | Case / repeat | Time to first feasible | Total trial wall time |
| --- | --- | --- | --- |
| T001 | Original / 1 | 175.05 s | 175.52 s |
| T002 | Original / 2 | 156.25 s | 156.73 s |
| T003 | Hotter / 1 | 120.82 s | 121.23 s |
| T004 | Hotter / 2 | 96.04 s | 96.47 s |
| T005 | Compact / 1 | 29.04 s | 29.52 s |
| T006 | Compact / 2 | 155.54 s | 156.22 s |

Summed trial time: **735.69 s (12.26 min)**. These times include the trial's source
preparation, validation, solver execution and result checks; post-campaign artifact
review is separate. Large variation between identical repeats shows why this
small, shared-machine pilot cannot establish comparative speed performance.

The reference made zero model API calls. Its model tokens and model API cost are
therefore zero; machine/engineering costs and this development session are not
included. There are no LLM feasibility, token, latency or cost measurements here.
For externally driven LLM trials, absent usage stays null rather than becoming zero.

## Validation and retained evidence

- **77 targeted Python tests passed** after the review fixes, in 106.90 s. This
  covers L1, L2, case propagation and campaign behavior. Five new reproductions
  first failed, then passed for the review issues and unsuccessful CLI exit status.
- **12 native Code_Aster 18.0.12 execution attestations**, all using the existing
  external-process Python bridge through WSL (`execution_method=command`). No
  failed or timed-out solver attempts occurred in this campaign.
- **All 12 native result sets reopened successfully** with their recorded solver
  input identities and publication validation. Three processed review bundles
  (one accepted candidate per case) passed the existing scene-contract checks.
- Independent review identified four Important findings, all fixed; no Critical
  or deferred Minor findings. Review rulings are retained in the plan ledger.
- No viewer code changed, no viewer rebuild was needed and no new browser suite
  was run for this change. Portable test fixtures are not engineering evidence.

Evidence stays outside tracked source:

- `D:/tuba-runs/Tuba_v4/llm-comparison-20261011`: immutable campaign protocol,
  six trial histories, captured Python, evaluator inventories and 12 attempts.
- `D:/tuba-runs/Tuba_v4/llm-comparison-validation/report.json`: complete metrics
  and denominators, including explicit `llm_trials_run: 0`.
- `D:/tuba-runs/Tuba_v4/llm-comparison-validation/qualification.json`: native
  reopening, exact measured reactions, execution provenance and scene validation.
- `D:/tuba-runs/Tuba_v4/llm-comparison-validation/review-T001`, `review-T003`,
  `review-T005`: processed Code_Aster web-review bundles for the three cases.
- `D:/tuba-runs/Tuba_v4/llm-comparison-reference.log`: actual proposal outcomes.
- `D:/tuba-runs/Tuba_v4/llm-comparison-final-tests.log`: complete targeted test log.

For another run, use the documented `init` and `reference` commands with a fresh
external directory. On this machine the runtime was configured as follows; use
the main checkout path after integration:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD='command'
$env:TUBA_CODE_ASTER_RUNNER_COMMAND='wsl -d Ubuntu -- /home/jan/miniforge3/envs/tuba-code-aster/bin/python /mnt/d/Gitprojects/Tuba_v4/tuba/solver/code_aster_bridge.py'
```

## Remaining L3 work

Choose a provider and exact model revision, implement an adapter retaining every
prompt/response and measured usage, and run the LLM trials. The current session
does not expose the exact revision and usage needed for that controlled comparison.
Provider metadata supplied through the API is not independently authenticated.

Then add a common fixed-family interface for a matched comparison and a suitable
free-topology reference, broaden the case set, and use measured failure patterns
to decide which L4 geometric or numerical tools help. This pilot supplies the
infrastructure and reference evidence for that work; it does not finish L3.
