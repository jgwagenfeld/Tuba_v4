# Repeatable piping comparison

This is the L3 comparison **foundation**. It runs a versioned deterministic
reference on three thermal research cases using real Code_Aster. It also provides
a provider-neutral API for externally driven LLM trials. It does not call an LLM
provider, establish LLM superiority, or qualify an industrial piping design.

The workflow is procedural Tuba source -> Code_Aster -> verified reaction checks
and processed comparison report. Export files alone cannot establish feasibility.

## Cases and reference policy

All cases retain the L2 DN100 steel line, 12 m anchored nozzle spacing, radius
0.3 m tangent bends, at most four ideal interior Y/Z guides, 5000 N m nozzle
moment limit, and the same native solver settings (12 line segments, 600 s solve
timeout). Temperature is relative to 20 C. Gravity and pressure are omitted.

| Case ID | Temperature | Centerline y envelope | Nozzle force limit |
| --- | --- | --- | --- |
| `thermal-guided-design-v1` | 200 C | 0..4 m | 5000 N |
| `thermal-guided-hot-v1` | 300 C | 0..4 m | 5000 N |
| `thermal-guided-compact-v1` | 200 C | 0..1.2 m | 8000 N |

`ascending-loop-v1` preserves the authored example's crown and two Z guides. It
tries straight loop-leg rises 0.4, 0.8 and 1.6 m in order and stops at the first
feasible result. Bend arcs add 0.6 m to the loop height. This is a small fixed
family reference, not a claim of optimality. Invalid and failed proposals still
consume proposal budget; solver failures consume solver-call budget.

## Run the reference campaign

From the repository root, with an available native Code_Aster runtime:

```powershell
python -m scripts.compare_llm_piping init D:/tuba-runs/comparison-001
python -m scripts.compare_llm_piping reference D:/tuba-runs/comparison-001 --output D:/tuba-runs/comparison-001-report.json
python -m scripts.compare_llm_piping report D:/tuba-runs/comparison-001
```

Initialization freezes all six slots (two repeats per case), source, evaluator,
method, prompt, tools and budgets. Each trial is bound to its unique session
identity; replacing a same-case session cannot count its results as another repeat.
Default admission limits per trial are three
proposals, three solver calls and 1800 wall seconds. The timer starts before
design work; pauses and restarts count. A solve already admitted may finish after
the wall deadline, and its evidence remains recorded. This is an admission limit,
not a hard process-kill deadline. Repeats do not reuse solver evidence or results.

`reference` resumes an unfinished campaign using its existing timer/history and
skips finished trials. It never rewrites requirements to accommodate a candidate.
The reference command returns nonzero if any reference trial is unfinished or
infeasible; the report command remains a successful read-only inspection.
An interruption during partial session initialization is reported explicitly; if
the session directory lacks its history, retain it and initialize a fresh campaign.
Changing evaluator code requires a fresh campaign; old archives remain inspectable
with `report` and generic search tools. Output paths must be new and outside Git.

## Drive an LLM trial

Use the API from a trusted local driver. Explicitly identify the provider's model
revision, settings, system/task prompt and available tools before initialization.
The harness records what the caller declares; it cannot verify a provider's model
identity or enforce external tool use. Use a new campaign for a changed protocol.

```python
from pathlib import Path
from scripts.compare_llm_piping import (
    REFERENCE, create_campaign, start_trial, submit_trial, finish_trial,
)

root = Path('D:/tuba-runs/comparison-with-llm-001')
# Populate method with the provider's actual revision and actual driver protocol.
method = {
    'id': 'my-designer-v1', 'kind': 'llm', 'representation': 'free-topology',
    'provider': provider_name, 'model': exact_model_revision,
    'settings': provider_settings, 'prompt': exact_system_and_task_prompt,
    'tools': available_tool_ids,
}
create_campaign(root, methods=[REFERENCE, method])
brief = start_trial(root, 'T003')  # original case, first LLM repeat
# Now invoke the designer with brief (requirements, prompt/tools, starter source).
# It writes clean procedural model.py in candidate_project.
decision = submit_trial(
    root, 'T003', candidate_project, intent=proposal_rationale,
    dependencies=(),  # explicitly list local Python unit files when used
    usage={
        'model': exact_model_revision,
        'input_tokens': measured_input_tokens,
        'output_tokens': measured_output_tokens,
        'cost_usd': measured_cost_or_none,
        'source': provider_receipt_reference,
    },
)
# Inspect measured checks in the trial history; revise and submit within budget.
finish_trial(root, 'T003', reason='first feasible')
```

Do not start the model before `start_trial`, or omit unsuccessful model calls from
usage. Each usage record covers all design calls since the previous submission.
A failed generation can be recorded through a submission with its usage and a
missing/invalid project; that failure still counts. `finish_trial` is a lifecycle
marker: its text does not set engineering feasibility. Acceptance is derived from
retained solver evidence. Candidate Python is trusted local code, not sandboxed.
If generation crosses the admission deadline, the rejected submission retains its
usage without admitting another candidate or solve. Reports distinguish these
rejected submissions from admitted proposals.

Model tokens/cost are **caller reported**, independently nullable fields. Missing
usage never becomes zero; deterministic runs report zero model calls/cost, which
excludes compute costs. This increment enforces only proposal, solver and wall
admission budgets. Provider call tracing, token/dollar caps, automatic model
identity verification and repeated live LLM runs remain future work.

## Read the results

The report separates planned, started and finished trials and reports feasibility
only among finished trials, beside its denominator. Open/unstarted trials remain
visible. Each row contains first-feasible time and solve count, total wall time,
all candidate outcome counts, solver-call count, proposal count, available model
usage, feasible route objectives and integrity diagnostics. A damaged source,
compiled model or sealed result inventory cannot supply a feasible candidate.

Groups are per case, method and representation. Compare fixed-family methods
with fixed-family methods and free-topology methods with free-topology methods;
the current fixed reference and a free-topology LLM are descriptive results,
not a matched design-space superiority experiment. Cases share thermal physics:
they are not broad congested-layout, support-friction or standards benchmarks.

Each `trials/T...` directory is an ordinary authored search session. To inspect
measured reasons or create a processed Code_Aster review, reuse existing tools:

```powershell
python -m tuba.search inspect --run-dir D:/tuba-runs/comparison-001/trials/T001 --json
python -m tuba.search review --run-dir D:/tuba-runs/comparison-001/trials/T001 --candidate C002 --output D:/tuba-runs/comparison-001-review
```

See the [roadmap](../../docs/architecture/llm-piping-design-roadmap.md) and
[implementation plan](../../docs/superpowers/plans/2026-10-11-llm-piping-comparison.md).
