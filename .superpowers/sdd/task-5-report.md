# Task 5 Report: User-Facing Example Provenance Cleanup

## Scope completed

Implemented Task 5 in the requested ownership surface:

- `examples/demo.py`
- `examples/operating_state_clash.py`
- `examples/realtime_visualization_review.py`
- `tests/test_examples.py`
- `tests/test_operating_state_example.py`
- `tests/test_realtime_visualization_bundle.py`
- `tests/realtime_visualization_fixtures.py`

Did not modify any other example or test files.

## Changes made

### 1. Added the example provenance guard test

Added `test_user_facing_examples_do_not_publish_synthetic_solver_results` to `tests/test_examples.py`.

The initial red-state run after adding the test failed on:

- `examples/demo.py`
- `examples/operating_state_clash.py`
- `examples/realtime_visualization_review.py`
- `examples/verify_features.py`

The brief expected only the first three files and the task ownership excluded `verify_features.py`, so I narrowed the guardrail to the three owned user-facing examples instead of editing an out-of-scope file.

### 2. Removed synthetic solver-result display from `examples/demo.py`

Changed the demo to keep the export workflow intact and stop before any compliance or solver-result visualization.

Removed synthetic-result imports and logic:

- `numpy`
- `FEAResults`
- `NodeResult`
- `ElementResult`
- `ASMEB313Evaluator`

Replaced the old mock-result compliance and visualization section with:

- an explicit statement that only Code_Aster handoff files were generated,
- the required real artifact filenames to import next,
- the runtime doctor command and integration-smoke command,
- an explicit statement that no compliance report or stress plot was produced from synthetic values.

Also updated the module header text so the described steps match the new behavior.

### 3. Made `examples/operating_state_clash.py` fail loudly after export

Kept the model build and `export_analysis_study(...)` flow.

Removed the synthetic `ResultState`, clash generation, scene writing, and BCF export path. The example now raises:

- `RuntimeError("Operating-state clash review requires real Code_Aster result artifacts ...")`

That error includes the exported study work directory and tells the user to execute `study.export` with Code_Aster and import the result tables before building operating geometry states.

Removed now-unused imports tied to the synthetic review path.

Updated `main()` to call `run_example()` directly so the script fails loudly instead of printing synthetic output.

### 4. Made `examples/realtime_visualization_review.py` fail loudly after export

Kept the model build and `export_analysis_study(...)` flow.

Removed the synthetic manifest parsing, synthetic `ResultState`, synthetic clash review scene creation, bundle writing, and summary export path. The example now raises:

- `RuntimeError("Realtime result review requires real Code_Aster result artifacts ...")`

That error points the user at executing `study.export` and then importing artifacts with `tuba.analysis.code_aster_artifacts.import_code_aster_artifacts` before writing a review scene.

Removed now-unused imports tied to the synthetic review path.

Updated `main()` to call `run_example()` directly so the script stops at the real-artifact boundary.

### 5. Updated the focused example tests

#### `tests/test_operating_state_example.py`

Changed the contract from "synthetic review bundle is produced" to:

- `run_example(...)` raises a `RuntimeError` mentioning real Code_Aster result artifacts,
- `code_aster/study_manifest.json` still exists after the export step.

#### `tests/test_realtime_visualization_bundle.py`

Replaced the direct call to the user-facing example with the existing deterministic fixture:

- `from tests.realtime_visualization_fixtures import operating_state_review_fixture`

The test now validates the review scene bundle from the fixture and keeps the previous scene-contract assertions:

- analysis mesh geometry objects exist,
- deformed centerline and envelope geometry exist,
- deformed analysis mesh geometry exists,
- clash marker exists,
- stress overlay exists,
- clash issue load-case grouping remains `Hot`.

### 6. Adjusted the reusable deterministic fixture only where needed

Updated `tests/realtime_visualization_fixtures.py` to pass:

```python
analysis_meshes=[analysis_mesh]
```

into `build_visualization_scene(...)`.

That was required so the fixture-backed bundle continues to contain the analysis-mesh scene objects asserted by the updated realtime review test.

## Validation

### Red-state provenance test

Ran:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_examples.py::TestExamples::test_user_facing_examples_do_not_publish_synthetic_solver_results -q
```

Observed the expected failure before the example cleanup. The failure listed the three target examples plus `verify_features.py`, which remained out of scope for this task.

### Final example test slice

Ran:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py -q
```

Result:

```text
5 passed in 9.20s
```

## Notes and boundaries

- Export-only behavior was preserved for the owned examples. They still generate Code_Aster study handoff files.
- No new mock or proxy solver-result values were added to any user-facing example.
- `examples/verify_features.py` still contains mock-result construction in the current checkout, but that file was outside the ownership list for Task 5 and was not modified here.

## Commit

Created commit:

- `fix: remove synthetic solver results from user examples`

## Review fix follow-up

Addressed the review finding on top of the earlier Task 5 work:

- cleaned `examples/verify_features.py` so `verify_tee_sifs()` still demonstrates solver-free SIF calculation but no longer constructs `FEAResults(solver_name="mock")` or prints a synthetic compliance report,
- restored `tests/test_examples.py` to scan every `examples/*.py` file for forbidden synthetic solver-result snippets instead of only three named examples.

### Follow-up validation

Ran:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py -q
```

Result:

```text
5 passed in 19.73s
```
