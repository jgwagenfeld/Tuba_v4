# LLM-driven piping design roadmap

Date: 2026-10-11. Implementation baseline: `6126475`.

## Direction and evidence

Let a coding LLM drive design by editing procedural Python, inspecting the model,
running Code_Aster, and revising candidates from measured findings. Numerical
optimizers remain optional tools. No genetic optimizer, custom model training,
or multi-agent framework is a prerequisite for the first experiment.

The [broad research](automated-piping-generation-research-2026-10-11.md) inventories
commercial tools and numerical/learned methods. The
[direct-LLM follow-up](direct-llm-piping-generation-research-2026-10-11.md) revises
its algorithm priorities and qualifies the CAD/FEA evidence. Small published
demonstrations justify this experiment; they do not qualify industrial piping.
This roadmap is the current development sequence for that recommendation.

The product loop remains authored Tuba model -> Code_Aster -> processed result
review. The LLM chooses the next design; measured checks determine whether it
meets the declared task. Explanations are hypotheses until evaluated.

## Existing foundations and boundaries

Reuse `model.py`, construction units, `inspect_model`, `verify_model`,
`check_clashes`, `solve_model`, project evidence identities, and the existing
web-scene review. Preserve authored source. A solver failure, missing result,
or interrupted attempt must remain distinct from a measured constraint failure.

The [search-history roadmap](piping-search-roadmap.md) owns persistent generic
candidate/evaluation records, replay, and film. Its implementation is on a
separate branch at the L1 baseline. L2 integrates its committed M1/M2 history
and replay through `bbc19e6`, leaving ongoing M3 film work in its own checkout.
The authored-candidate runner uses that shared store, permanent-attempt evaluator
and review/export path. The original L1 attempt folders remain valid evidence.

Use a small repository script for the first benchmark, rather than a new core
optimizer package. Existing solver/evidence/visualization modules remain owners
of their respective responsibilities.

## Milestones

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| L1: First reproducible design task | A procedural hot-line starter, frozen task evaluator, retained per-attempt feedback, and a real agent-directed repair | Unchanged requirements; one measured rejection and an improved candidate evaluated by real Code_Aster; failed/incomplete attempts cannot pass; tests and a small execution report |
| L2: General design iteration and history | Arbitrary permitted route/support construction units; structured IDs/units/case feedback; integration with the existing search-history contract | Source/evidence correspondence, parent diffs, restart/review of all outcomes; requirements cannot be silently relaxed |
| L3: Repeatable comparison | Several fixed cases and repeat runs with pinned model, prompt, tools and budgets; existing deterministic/manual references | Feasibility rate, first-feasible time, solve count, total time/model cost and objective quality; invalid attempts included; fixed-family and free-topology comparisons reported separately |
| L4: Tools justified by measured failures | Optional geometric search, bounded parameter search, or evolutionary search; retrieval/surrogates only with suitable evidence | Improvement over the same agent without the tool under matched requirements and resource budgets |
| L5: Broader engineering scope | Multiple operations, gravity/pressure, operating clearance, support travel/friction, nozzle requirements, coupled racks and multiple lines | Representative real-solver cases, declared modeling/check coverage, project-owned standard evaluation and independent engineering review |

L1 and L2 are complete for their declared research scope. L3 is in progress:
the comparison foundation provides frozen thermal cases, repeated reference
trials and provider-neutral accounting. A pinned live LLM campaign and matched
design-space comparisons are still required. L4-L5 remain future work.

## L1 specification: thermal nozzle-reaction task

**Question:** can an agent improve a pipe route using actual reaction feedback,
while keeping the mechanical problem fixed?

The starter is a readable Python model with a U-shaped expansion loop. The
agent may change geometry and construction code within the declared route
envelope. This first task holds supports and pipe properties fixed to isolate
thermal flexibility. Support optimization and congested routing follow later.

- Python support remains `>=3.11,<3.15`; add no dependencies.
- Endpoints are `(0, 0, 0)` and `(12, 0, 0)` m, both ground anchors.
- One connected, unbranched DN100 line: OD `0.1143` m, WT `0.00602` m;
  steel E `2.1e11` Pa, nu `0.3`, rho `7850` kg/m3, alpha `1.2e-5` /K.
- Operation `Hot`: `200` C relative to `20` C; no gravity or pressure. These
  omissions define a thermal-only benchmark, not an operating-system design.
- Planar route centerline inside x `[0,12]`, y `[0,4]`, z `0` m; 90-degree
  bends have radius `0.3` m. No additional restraints, applied loads, material
  changes, or alternate sections. Keep at most 40 authored elements.
- Bend records must agree with their explicit arcs and endpoints. Joins must be
  tangent-continuous; collinear subdivision is allowed, sharp corners are not.
- Each endpoint force resultant must be <= `5000` N and moment resultant
  <= `5000` N m. These are benchmark targets, not equipment-vendor allowables.
- Report route length as a secondary geometric objective. A pass means only
  that the declared model, geometry, evidence and reaction checks passed.
- Cold verification must pass. Missing/nonfinite reaction components are
  `unknown`. Require verified Code_Aster provenance before interpreting results.
- Candidate source is a standalone trusted local `model.py`. This is not a
  Python sandbox. Candidate `study.py` and candidate-supplied limits are ignored;
  the evaluator writes its own fixed study and snapshots its task definition.
- Use a fresh attempt directory outside the source checkout, never overwrite
  an earlier attempt, and never rewrite the input script. Retain the source,
  requirements, checks, source hashes, timings, solver evidence and diagnostics.
- Publish JSON feedback before optional web-review generation, so a display
  failure does not lose an evaluation. Use the existing web-scene path only.
- Unit tests may use deterministic fixtures, clearly separate from engineering
  evidence. Integration validation must execute real Code_Aster.
- Commit locally; do not push.

The acceptance gate checks the compiled model, not just its source constants:
changing an applied temperature, endpoint restraint, material, or section must
be rejected before a solve. A degree/connectivity check rejects detached loops,
branches, or isolated nodes. The frozen study supplies the modelization and
mesh settings. A run manifest records the evaluator and candidate source hashes.

L1 deliberately does not claim optimality, repeat-run reliability, piping-code
compliance, fabrication qualification, or operating-state clearance. Its result
is one inspectable engineering iteration and reusable infrastructure to repeat it.

## Decision rules after L1

Keep one agent and a modest tool set initially. If diagnosis is weak, improve
feedback before changing the search algorithm. If route generation repeatedly
fails in dense geometry, compare A*. If numerical tuning consumes many calls,
compare a bounded search. If broad alternative coverage is poor, compare a
properly constrained population optimizer. Do not infer tool value from one
successful demonstration.

For L3, fix cases, starting information, allowed changes, limits and stopping
rules before running. Count model latency and failures as well as solver calls.
Do not compare an unrestricted LLM with a baseline unable to represent feasible
designs. Preserve every run, including runs with no feasible result.

## Implementation and validation record

The [L1 implementation plan](../superpowers/plans/2026-10-11-llm-piping-first-task.md)
tracks files, checks, execution outcomes and remaining limitations.
The first [measured iteration](llm-piping-first-task-results.md) reduced nozzle
force from 7496 N to 3639 N against the unchanged 5000 N target.

The [L2 implementation plan](../superpowers/plans/2026-10-11-llm-piping-iteration.md)
and [authored iteration example](../../examples/llm-piping-iteration/README.md)
cover free-form candidate submission, frozen guide policy, parent source diffs,
retry/recovery and shared retained history. This remains a coding-agent workflow;
there is no provider-specific autonomous LLM driver yet.
The [L2 measured results and validation](llm-piping-iteration-results.md) record
two qualified guided-line candidates, retained runtime failures, native evidence
reopening, browser checks and the exact limits of the qualification.

The [L3 comparison foundation](../../examples/llm-piping-comparison/README.md)
and [implementation plan](../superpowers/plans/2026-10-11-llm-piping-comparison.md)
freeze three thermal case variants, a deterministic ascending-loop reference,
per-trial budgets, method/model/prompt/tool metadata and all planned repeat slots.
Reports keep invalid candidates, failures and unstarted trials visible, verify
retained evidence, and group results by case, method and representation. Model
usage remains explicitly caller reported or unknown.

Next L3 tasks:

1. Select a provider and exact model revision; retain every prompt/response and
   measured usage in an instrumented adapter, including unsuccessful model calls.
2. Run repeated live LLM trials under the frozen protocol. Add a common fixed
   parameter interface for a matched fixed-family comparison, then add a suitable
   free-topology reference. Do not pool these representation groups.
3. Broaden the cases beyond these closely related thermal variants, and choose
   L4 tools from measured failure patterns. Two deterministic repeats qualify
   execution/accounting, not LLM reliability or optimizer superiority.
