# Task 2 Report: Doctor And Notebook Runtime Guard

## Scope

Implemented Task 2 in the requested ownership surface:

- `tuba/solver/code_aster_doctor.py`
- `tuba/analysis/code_aster_notebook.py`
- `tests/test_code_aster_doctor.py`
- `tests/test_code_aster_notebook_loader.py`

Task 1 runtime-preflight interfaces were treated as existing inputs:

- `CodeAsterRuntimeCheck`
- `build_code_aster_preflight_command(...)`
- `preflight_code_aster_runtimes(config)`

## RED

### Added failing doctor coverage

Added `test_check_json_output_lists_runtime_readiness` to `tests/test_code_aster_doctor.py`.

What it asserted:

- `main(["--json", "--check"], return_output=True)` exposes a `checks` array
- a blocked preflight check is serialized
- `kind`, `ok`, and `reason` survive JSON output

Observed failure:

- patch target `tuba.solver.code_aster_doctor.preflight_code_aster_runtimes` did not exist
- confirms doctor had not imported or wired runtime preflight yet

### Added failing notebook guard coverage

Added `test_run_solver_true_preflight_failure_preserves_existing_tables` to `tests/test_code_aster_notebook_loader.py`.

What it asserted:

- `run_solver=True` performs a runtime preflight before solver execution
- when preflight is blocked, the solver must not run
- existing `study_*.csv` artifacts are preserved and not deleted first

Observed failure:

- patch target `tuba.analysis.code_aster_notebook.preflight_code_aster_runtimes` did not exist
- confirms notebook loader had not imported or wired runtime preflight yet

### Scoped existing notebook tests around the new guard

Per task nuance, existing fake-solver `run_solver=True` tests were patched to stub:

- `tuba.analysis.code_aster_notebook.preflight_code_aster_runtimes`

with an OK `CodeAsterRuntimeCheck`, so they continue testing loader behavior rather than being turned into runtime-probe tests.

This was applied only in the owned notebook loader test module.

### RED test command

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py -q
```

RED result:

- 6 failed, 5 passed
- failures were the expected missing-hook failures for doctor and notebook preflight patch targets

## GREEN

### Doctor wiring

Updated `tuba/solver/code_aster_doctor.py` to:

- import `preflight_code_aster_runtimes`
- add `--check`
- build a local `CodeAsterRuntimeConfig`
- run bounded preflight checks only when `--check` is set
- include `checks` in JSON output
- append readiness lines to text output

Added `_check_payload(...)` for JSON serialization of `CodeAsterRuntimeCheck`.

Result:

- doctor now reports both discovered candidates and actual readiness probes
- `--check` is opt-in, so existing non-probe flows stay unchanged

### Notebook runtime guard

Updated `tuba/analysis/code_aster_notebook.py` to:

- import `CodeAsterRuntimeCheck`, `CodeAsterRuntimeConfig`, and `preflight_code_aster_runtimes`
- add `require_code_aster_runtime(...) -> CodeAsterRuntimeCheck`
- call that guard before deleting existing result artifacts and before invoking `solve_exported_study(...)`

Behavior now:

- if any runtime preflight passes, the notebook solve path proceeds
- if all checks are blocked, the loader raises a `RuntimeError`
- the error explicitly tells the user that existing result tables were left in place and that `RUN_CODE_ASTER = False` can be used to load existing artifacts

This preserves the product contract from the repo instructions:

- no fake solver results are presented
- if Code_Aster is unavailable, notebook solve stops loudly before reporting new results

## Verification

### GREEN test command

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py -q
```

GREEN result:

```text
...........                                                              [100%]
11 passed in 4.98s
```

## Files changed

### `tuba/solver/code_aster_doctor.py`

- imported runtime preflight
- added `--check`
- added `checks` JSON payload
- added text readiness reporting
- added `_check_payload(...)`

### `tuba/analysis/code_aster_notebook.py`

- imported runtime preflight types/functions
- added `require_code_aster_runtime(...)`
- inserted runtime guard ahead of artifact deletion and solver execution

### `tests/test_code_aster_doctor.py`

- added doctor `--check` JSON readiness test

### `tests/test_code_aster_notebook_loader.py`

- added blocked-preflight artifact-preservation test
- patched existing fake-solver `run_solver=True` tests to return an OK preflight check

## Commit

Planned commit message from task brief:

```text
feat: guard notebook solves with Code_Aster preflight
```

## Concerns / residual notes

1. `require_code_aster_runtime(...)` currently treats any successful check as sufficient and returns the first `ok=True` result. That matches the brief and the runtime-discovery contract.
2. The notebook guard preflights independently from the later solver execution path, so runtime availability can still drift between probe time and actual solve time. That is normal for a bounded readiness probe and not a regression from this task.
3. The test suite here is focused by request. No broader notebook, viewer, or end-to-end Code_Aster integration run was performed in this task.

## Review fix: Docker image resolution parity

Addressed the review finding against commit `2ddeecf`.

- notebook `require_code_aster_runtime(...)` now resolves Docker image exactly like `CodeAsterSolver.__init__`:
  - explicit `docker_image` argument
  - else `TUBA_CODE_ASTER_DOCKER_IMAGE`
  - else runtime default
- doctor `--check` now builds its `CodeAsterRuntimeConfig` with the same effective Docker image resolution before running preflight probes

Focused regression coverage added:

- `tests/test_code_aster_notebook_loader.py`
  - `test_run_solver_true_preflight_uses_env_docker_image`
- `tests/test_code_aster_doctor.py`
  - `test_check_uses_env_docker_image_in_runtime_config`

Verification command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py -q
```

Result:

```text
.............                                                            [100%]
13 passed in 4.74s
```
