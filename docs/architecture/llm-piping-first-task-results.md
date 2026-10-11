# First direct-LLM piping iteration: measured result

Date: 2026-10-11. Task: L1 of the
[LLM piping design roadmap](llm-piping-design-roadmap.md).

## Outcome

A coding agent in this session evaluated a compact procedural U-loop, read its
Code_Aster reaction failures, increased the two straight loop legs from 0.4 m
to 0.8 m, and evaluated that revision. The second candidate met the unchanged
benchmark reaction limits. No genetic algorithm, parameter sweep, surrogate or
domain-specific training was used to choose the revision.

| Measured quantity | Starter, attempt 01 | Revised, attempt 02 | Fixed limit |
| --- | ---: | ---: | ---: |
| Inlet force resultant | 7496.062 N | 3639.445 N | 5000 N |
| Outlet force resultant | 7496.062 N | 3639.445 N | 5000 N |
| Inlet moment resultant | 1857.922 N m | 1334.820 N m | 5000 N m |
| Outlet moment resultant | 1857.922 N m | 1334.820 N m | 5000 N m |
| Pipe centerline length | 13.485 m | 14.285 m | Secondary objective |
| Evaluation including review generation | 52.47 s | 40.93 s | Not a comparative speed claim |
| Outcome | Rejected: both nozzle forces | Feasible for declared checks | All required checks pass |

The change reduced nozzle force by approximately 51.4% while adding 0.8 m of
pipe. All fixed model/load/support/property checks passed for both candidates.
The force limits were declared before the first solve and were not adjusted.

This demonstrates one successful agent-directed repair. It does not measure
reliability across runs, global optimality, superiority to another optimizer,
or fully autonomous multi-step orchestration. The acting agent was the Codex
session; its exact model version and token costs were not captured, so this
pilot is not the pinned-model statistical comparison required by L3.

Final validation: 71 focused tests passed. Independent review findings were
fixed with regression tests. Both real studies and their scene contracts were
reopened successfully; the final evaluator preserves the recorded outcomes and
reaction values. This did not require another solve of unchanged geometry.

## Evidence and reproduction

The retained run root is:

```text
D:/tuba-runs/Tuba_v4/llm-piping-20261011/
  attempt-01/feedback.json
  attempt-01/model.py
  attempt-01/evaluator.py
  attempt-01/evidence/Hot/
  attempt-01/review/review_scene/scene.json
  candidate-02.py
  attempt-02/feedback.json
  attempt-02/model.py
  attempt-02/evaluator.py
  attempt-02/evidence/Hot/
  attempt-02/review/review_scene/scene.json
  final-evaluator.py
  final-evaluator-recheck.json
```

Each attempt also includes the frozen requirements, fixed study, solver-input
identity, source hashes, proposal rationale and elapsed time. Both evaluations
executed Code_Aster 18.0.12 through the available Ubuntu WSL runtime.
The exact evaluator source used for these runs is retained beside their inputs.
Subsequent harness hardening does not relabel these earlier execution versions.

To reproduce, follow the [benchmark instructions](../../examples/llm-piping-benchmark/README.md)
with new output folders. For the second candidate, change only `LOOP_RISE = 0.4`
to `LOOP_RISE = 0.8` in a copy of the starter. Never overwrite the retained
attempts. The existing viewer opens either `review/review_scene` directory.

Source baseline was `6126475`, with the new benchmark files in the isolated
`codex/llm-piping-first-task-20261011` branch. Generated results remain outside
Git. Only source, documentation and this small measured summary are committed.

## Qualification boundary

This is a linear thermal-only flexibility task with two fixed anchors, one pipe
section and one material. It omits gravity, pressure, support friction, equipment
flexibility, operating-state clearance, fatigue, manufacturing checks and
piping-standard acceptance. The 5000 N and 5000 N m thresholds are benchmark
targets, not equipment-vendor limits. Passing means only that the declared
geometry, model, evidence and reaction checks passed.

The complete validation record and review disposition are maintained in the
[implementation plan](../superpowers/plans/2026-10-11-llm-piping-first-task.md).
