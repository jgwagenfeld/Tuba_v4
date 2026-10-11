# First LLM piping design task

Improve the route in `model.py` using measured Code_Aster reactions. The starter
is intentionally compact; its acceptability must be evaluated. Geometry and
procedural construction code may change. Keep the fixed engineering requirements
listed in the [roadmap](../../docs/architecture/llm-piping-design-roadmap.md).

The task is a thermal-only, planar DN100 line between two anchored nozzles 12 m
apart. At 200 C relative to 20 C, each nozzle must have force resultant <= 5000 N
and moment resultant <= 5000 N m. These are benchmark limits, not vendor
allowables. Gravity, pressure, operating clearance, fabrication qualification,
and piping-standard acceptance are outside this first task.

From the repository root, using the existing Python environment:

```powershell
# Windows: use the already installed Code_Aster runtime in Ubuntu.
$env:TUBA_CODE_ASTER_EXEC_METHOD = 'wsl'
$env:TUBA_CODE_ASTER_WSL_DISTRO = 'Ubuntu'
python -m tuba.solver.code_aster_doctor --check
python -m scripts.benchmark_llm_piping examples/llm-piping-benchmark/model.py `
  --output D:/tuba-runs/my-llm-task/attempt-01 `
  --rationale "Evaluate the compact starter before choosing a repair."
```

On Linux, use the normal Python-managed Code_Aster setup from the
[installation guide](../../docs/content/setup.md); the evaluator follows that
runtime configuration. No external LLM API or provider credentials are required:
the coding agent you are already using authors the candidate and invokes the CLI.

Use a **new directory outside source for every attempt**. The evaluator copies
only the supplied standalone script, writes its own study and requirements, and
never changes the original. Candidate-side helper files and `study.py` are not
imported as part of the benchmark project. This pilot executes trusted local
Python; it does not sandbox arbitrary code.

Read `feedback.json` after each invocation. Reaction checks contain the nozzle,
node, operation, components, resultant, SI unit, limit, status and result-state
ID. Keep the previous attempt intact, author a revised standalone candidate,
and record the hypothesis in the next `--rationale`. A hypothesis is not solver
evidence. Stop when the task passes or the experiment's budget is exhausted.

The CLI exits 0 only for `feasible`, and 1 for `rejected_constraint`, `incomplete`
or `evaluation_failed`. Nonzero exit for a constraint failure is an expected
benchmark outcome. Unavailable Code_Aster produces an explicit evaluation error;
export-only work cannot pass. Missing reaction data remains unknown.

Each attempt retains `model.py`, a fixed `study.py`, `requirements.json`, source
hashes and timings in `feedback.json`, the exact `evaluator.py`, and real solver artifacts under
`evidence/Hot`. Build/runtime failures retain `failure.txt` and any artifacts
already produced. A fresh result review is written through the existing web
scene path; its relative directory is in the feedback's `review` field. Open it
using `python -m tuba.visualization.viewer <review-directory> --open`.

`--no-review` skips scene generation while keeping the engineering feedback.
Review-generation failures are reported separately; they do not erase the
evaluation. An interrupted attempt remains incomplete and must never be counted
as a pass. There is no automatic LLM loop or multi-run statistical benchmark in
this milestone; those are subsequent roadmap tasks.

`solver_evaluations` counts attempted solver calls, including calls that fail;
it is not a count of converged or accepted designs. A checkpoint before the call
retains completed checks and that count with status `incomplete`. Feedback uses
atomic file replacement. Bends must match their explicit geometry and adjoining
members must meet tangentially; sharp corners cannot substitute for elbows.
