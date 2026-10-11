# Direct agent-driven design iterations

A coding agent edits procedural Python, submits a candidate, reads measured
feedback, and writes a revision. The script does not call an LLM API, choose
the next design, or require a parameter grid. Any trusted coding agent can use
these commands. Candidate source, parent diffs, decisions and Code_Aster evidence
live in the existing `tuba.search` archive.

This example is a **thermal-only research task**. A successful candidate meets
its declared checks; it is not a piping-code, support-capacity, fabrication or
operating-clearance qualification. Code_Aster must actually solve the model.

## Run an iteration

From the repository root, with the project's Python environment active and a
working Code_Aster runtime:

```powershell
python -m scripts.iterate_llm_piping init D:/tuba-runs/my-design --max-solver-calls 10
python -m scripts.iterate_llm_piping submit D:/tuba-runs/my-design examples/llm-piping-iteration C1 --intent "Evaluate the small loop and approach guides"
python -m tuba.search inspect --run-dir D:/tuba-runs/my-design --candidate C1
```

Edit `model.py` (or your own project copy), then submit a new ID:

```powershell
python -m scripts.iterate_llm_piping submit D:/tuba-runs/my-design examples/llm-piping-iteration C2 --parent C1 --intent "Increase loop flexibility based on C1 nozzle reactions"
python -m tuba.search replay --run-dir D:/tuba-runs/my-design --output D:/tuba-runs/my-design-replay
```

Use `python -m tuba.search --help` for inspection/review commands and
`python -m tuba.visualization.viewer --help` for opening a replay in the existing
viewer. Output directories must be fresh; keep them outside source checkouts.
The archive is retained alongside replay exports. Replay can show every buildable
candidate; a source/build failure has diagnostics but no invented geometry.

The CLI prints the decision and reason codes. `inspect` returns full checks,
including entity references, operation, result state, measured value, limit and
unit. Force and moment use separate `N` and `N m` checks. Constraint rejection,
evaluation failure, incomplete evidence and exhausted budget return a nonzero
exit status. Read the outcome before proposing a repair.

## Editable geometry and supports

The `thermal-guided-design-v1` case permits arbitrary procedural routes and
construction-unit implementations within the L1 envelope and member policy.
The two nozzle coordinates and anchors, section, material, thermal load, bend
radius and reaction limits stay fixed. At most four ideal ground guides may
restrain global Y or Z at distinct interior pipe nodes. No support stiffness,
friction, mass, imposed motion, gaps or attachments are permitted.

The example defines a parameterized `expansion_line` construction unit and
composes two approach guides separately. You can rewrite this code, split units
into project files, change route topology within the single-line contract, and
move/add/remove permitted guides. For imported project units, declare each file:

```powershell
python -m scripts.iterate_llm_piping submit D:/tuba-runs/my-design D:/my-project C3 --parent C2 --dependency units/loop.py --intent "Try a different authored loop"
```

Only `model.py` and declared Python dependencies are captured. Candidate
`study.py` and `search.py` never determine the task, loads or acceptance limits.
Snapshots preserve authored code and local file layout; they exclude caches,
environments and generated evidence. These are trusted local scripts, not a
Python sandbox. External Python package dependencies come from the environment.

## Resume and inspect failures

```powershell
python -m scripts.iterate_llm_piping recover D:/tuba-runs/my-design
python -m scripts.iterate_llm_piping retry D:/tuba-runs/my-design C1
```

Recovery seals partial attempts as interrupted and restores a missing decision
for an already-published intact evaluation. It does not infer results from
partial files. Retry uses the original retained source and a fresh attempt; it
is available for incomplete, failed or deferred candidates. Revise a completed
candidate with a new ID and parent. All actual solver invocations count against
the session budget, including failed calls. There is no automatic result reuse
or ranking between free-form candidates in this milestone.

The session freezes its requirements and evaluator source fingerprints.
The guided case gives each Code_Aster invocation 600 seconds; this wall-clock
budget accommodates runtime startup and is separate from engineering limits.
Changing either requires a new session. Candidate reviews use the candidate's
own source snapshot, compiled model and recorded solver identity. Source/attempt
integrity checks refuse missing or altered artifacts. Parent diffs are retained
as `candidate.source_diff` events in the history export.

See the [roadmap](../../docs/architecture/llm-piping-design-roadmap.md) and
[implementation plan](../../docs/superpowers/plans/2026-10-11-llm-piping-iteration.md).
