# Final Engineering Review Fix Wave Report

## Scope and outcome

This single fix wave closes only the four confirmed whole-branch review gaps:

1. authoritative compliance element/node lineage;
2. nested engineering-review table validation at the viewer loader boundary;
3. atomic result-state/load-case preservation across reloads and SceneDiffs;
4. deterministic generic `Mapping` values across JSON, CSV, and HTML export.

No documentation, generated public artifact, durable ledger, solver semantics,
or unrelated feature surface was changed.

## Root causes and fixes

### Compliance lineage

`tuba.reporting.builder._validate_lineage` validated model references from
`ResultState`, but the compliance loop checked only whether each report load
case matched exactly one result state. A `ComplianceReport` row could therefore
name an element or node absent from `TubaModel` and still produce a
`compliance_complete` package.

The validation now resolves every compliance `element_id` through
`TubaModel.get_element`, requires every `node_id` in `model.nodes`, and requires
the node to equal the resolved element's `n1` or `n2`. These are the actual
authoring-model APIs and the same two endpoints evaluated by the ASME B31.3
evaluator. Violations raise the existing `EngineeringReviewError`.

### Review table contract

`viewer/src/reviewLoader.js` accepted any object as a table. The first nested
consumer, `reviewTables.js`, then called `.map` on unvalidated `columns` and
`rows`, so a malformed optional review could crash workflow rendering after the
scene had loaded.

The loader now validates portable matching table IDs, required table strings,
column and row arrays, plain column/row mappings, unique nonempty column IDs,
nonempty labels, optional string metadata, and recursively JSON-safe finite row
values. A malformed sidecar remains `review: null`, reports
`viewer.review.invalid_contract`, and leaves the scene/3D path usable. Both the
test fixture and the committed 239-file public package shape are accepted.

### Result/load context

Full reload checked whether the prior result-state ID survived but preserved
the prior load case independently. SceneDiff preserved both prior fields without
checking the new result-state overlays. That could create an impossible pair,
such as new `result_state:Cold` with stale load case `Hot`.

`coherentResultContext` now treats the two fields atomically in both paths. It
keeps the old pair only when one new result-state option has both values;
otherwise it selects the coherent new pair/default. A genuinely absent result
context remains absent. Camera, visibility, selection, review, issue-review,
workflow, thresholds, scales, and other interactive fields retain their
existing preservation rules.

### Generic Mapping export

Package JSON already normalized `collections.abc.Mapping` through the shared
reporting JSON-safe routine. CSV and HTML instead recognized only concrete
`dict`, `list`, and `tuple`, causing custom mappings to leak object repr strings
and diverge semantically from JSON.

CSV and HTML now normalize every cell through `tuba.reporting.model._json_value`
before deterministic compact JSON formatting. Nested custom mappings therefore
match the JSON contract byte semantics and no object repr is emitted.

## TDD evidence

Production files were unchanged until focused regressions reproduced all four
gaps.

RED evidence:

- `python -m pytest tests/test_reporting_compliance.py -q`
  - `3 failed, 7 passed`; missing element, missing node, and mismatched endpoint
    were all accepted instead of raising.
- Viewer targeted RED command covering malformed nested reviews and reload/diff
  result context:
  - malformed columns, rows, row, column, and value shapes were accepted;
  - full reload retained `Hot` after falling back to `result_state:Cold`;
  - compatible SceneDiff retained `result_state:Hot` after the overlay changed
    to `result_state:Cold`.
  - the valid public contract, retained valid pair, and absence controls were
    already green.
- `python -m pytest tests/test_reporting_export.py -q -k custom_mapping`
  - `1 failed, 35 deselected`; CSV contained a memory-address-bearing
    `CustomMapping object` repr instead of compact JSON.

Focused GREEN evidence:

- compliance: `10 passed`;
- viewer review/reload/SceneDiff subset: `48 passed`;
- custom Mapping plus neighboring CSV/HTML tests: `3 passed, 33 deselected`.

## Files changed

Production:

- `tuba/reporting/builder.py`
- `tuba/reporting/export.py`
- `viewer/src/reviewLoader.js`
- `viewer/src/resultReview.js`
- `viewer/src/viewerState.js`
- `viewer/src/sceneDiff.js`

Regressions:

- `tests/test_reporting_compliance.py`
- `tests/test_reporting_export.py`
- `viewer/test/review-loader.test.js`
- `viewer/test/viewer-state.test.js`

Report:

- `.superpowers/sdd/final-fix-wave-report.md`

## Final verification

Relevant Python/reporting/visualization gate:

```text
python -m pytest tests/test_reporting_model.py tests/test_reporting_tables.py tests/test_reporting_builder.py tests/test_reporting_compliance.py tests/test_reporting_export.py tests/test_visualization_reports.py tests/test_visualization_static_report.py tests/test_visualization_web_export.py tests/test_code_aster_artifact_import.py tests/test_result_state.py tests/test_compliance_b31j.py -q
116 passed, 4 skipped
```

Viewer and build:

```text
npm.cmd test
118 passed, 0 failed

npm.cmd run build
Vite 8.0.16; 21 modules transformed; exit 0
```

Six browser workflows:

```text
review-workflow:   7 objects, 170/2500 varied samples
legacy-workflow:   5 objects, 220/2550 varied samples
embedded-review:   7 objects, 170/2500 varied samples
code-aster-results: 7 objects, 170/2500 varied samples
clash-review:      7 objects, 170/2500 varied samples
scene-inspection:  3 objects, 233/2550 varied samples
```

Artifact generation and comparison:

```text
python examples/code_aster_artifact_review.py
provenance: committed_real_code_aster_artifacts
result source: code_aster_artifact_tables
result state: result_state:Operating
scene: 216 objects, 213 geometry assets, 8 overlays

generated_count=239
published_count=239
hash_or_path_differences=0
```

The comparison covered every relative path, byte length, and SHA-256 hash. The
first local comparison attempt used `[IO.Path]::GetRelativePath`, which is not
available in this host's .NET runtime; the compatible root-prefix implementation
then completed successfully. Neither attempt modified the public tree.

Real Code_Aster:

```text
python -m tuba.solver.code_aster_doctor --check --json
Ubuntu WSL candidate: ready; run_aster found; exit 0

$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
Ran 1 test in 3.725s; OK
```

## Commit

- Branch: `codex/future-ready-workpackages`
- Commit message: `fix: close engineering review release gaps`
- SHA: reported in the final handoff (a commit cannot embed its own final SHA).

## Concerns

- The committed RMED artifact continues to emit the existing non-fatal warning
  that object `NOE` is absent. The generated package uses the authoritative
  committed Code_Aster CSV tables, remains `solved`, and matches the public
  package byte-for-byte.
- The public package intentionally has no `ComplianceReport`; the viewer must
  continue to show compliance as unavailable rather than infer a verdict.
- The known static-site documentation baseline was not repaired or changed in
  this wave. No documentation file was touched.
