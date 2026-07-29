# Official Viewer Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce current, portable, strictly validated official viewer bundles from the two existing example producers and a genuinely refreshed Code_Aster artifact chain.

**Architecture:** Keep scene loading backward-compatible and put stronger checks only in the official publication command. Reuse `import_code_aster_artifacts`, `build_visualization_scene`, `write_scene_bundle`, and `write_engineering_review_with_scene`; the publication script supplies the small official catalog, stages portable evidence, and validates the emitted bundle.

**Tech Stack:** Python 3.10+, stdlib `argparse`/`hashlib`/`json`/`pathlib`/`shutil`, existing Tuba analysis/reporting/visualization modules, pytest, real Code_Aster through the configured WSL runtime.

## Global Constraints

- Preserve the product flow: Tuba model -> real Code_Aster solve -> processed result display.
- Keep exactly two visualization paths: `tuba/plotting/` and `tuba/visualization/` plus `viewer/`.
- Never publish deterministic fixture data as engineering results.
- Keep generic Python and JavaScript scene loaders backward-compatible with missing `layers` and `result_fields`.
- Official engineering publication requires `analysis_status == "solved"`, non-fixture Code_Aster provenance, matching non-null solver identities, stress/displacement/reaction/TUYAU fields, all four layer categories, valid geometry hashes, portable references, and visible diagnostics.
- Official model review must say it has no solver results.
- Do not modify the user's uncommitted `README.md` in this plan.

---

## File Map

- `tuba/analysis/code_aster_artifacts.py`: preserve import diagnostics on the owning `ResultState`.
- `tuba/solver/code_aster_runtime.py`: write observed execution attestation after successful real solves.
- `examples/code_aster_artifact_review.py`: derive timestamps from solved artifacts and emit current review data.
- `examples/imported_component_mixed_system.py`: retain the existing producer; remove only the direct tracked-publication helper after the shared publisher owns it.
- `examples/assets/imported_component_demo.stl`: stable model-review producer input.
- `scripts/build_pages.py`: official catalog, examples command, portable evidence staging, strict profile validation.
- `scripts/refresh_code_aster_gallery.py`: explicit real-solver refresh of the canonical gallery.
- `tests/test_code_aster_artifact_import.py`: diagnostic and current engineering-bundle assertions.
- `tests/test_official_viewer_publication.py`: catalog, portability, profiles, and deterministic staging tests.
- `notebooks/code_aster_results/viz_gallery_operating/`: refreshed real Code_Aster inputs and outputs.

### Task 1: Preserve artifact-import diagnostics on `ResultState`

**Files:**
- Modify: `tuba/analysis/code_aster_artifacts.py`
- Modify: `tests/test_code_aster_artifact_import.py`

**Interfaces:**
- Consumes: `import_code_aster_artifacts(*, model, work_dir, study=None) -> CodeAsterArtifactImport`.
- Produces: `artifact.result_state.metadata["parser_diagnostics"]`, containing both parser and RMED-import diagnostic dictionaries without duplicates; `artifact.diagnostics` remains available for callers.

- [ ] **Step 1: Write the failing RMED diagnostic ownership test**

Patch the existing artifact-import test to create an invalid `study.rmed`, import the artifacts, and assert the same warning identity reaches both surfaces:

```python
(work_dir / "study.rmed").write_bytes(b"not-an-rmed-file")
artifact = import_code_aster_artifacts(model=model, work_dir=work_dir)

warning = next(
    item for item in artifact.diagnostics
    if item["code"] == "visualization.code_aster_artifacts.rmed_read_failed"
)
self.assertIn(warning, artifact.result_state.metadata["parser_diagnostics"])
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `uv run python -m pytest tests/test_code_aster_artifact_import.py -k rmed -q`

Expected: FAIL because the warning exists only on `CodeAsterArtifactImport.diagnostics`.

- [ ] **Step 3: Merge diagnostics once at the import boundary**

After RMED parsing, replace the state metadata with the existing parser diagnostics followed by newly collected diagnostics, deduplicated by `(severity, code, source, message, target)`:

```python
existing = list(result_state.metadata.get("parser_diagnostics", ()))
combined = [*existing]
seen = {
    tuple(item.get(key) for key in ("severity", "code", "source", "message", "target"))
    for item in existing
}
for item in diagnostics:
    identity = tuple(item.get(key) for key in ("severity", "code", "source", "message", "target"))
    if identity not in seen:
        combined.append(item)
        seen.add(identity)
if combined:
    result_state = replace(
        result_state,
        metadata={**result_state.metadata, "parser_diagnostics": combined},
    )
```

- [ ] **Step 4: Run importer, reporting, and visualization diagnostic tests**

Run: `uv run python -m pytest tests/test_code_aster_artifact_import.py tests/test_reporting_builder.py tests/test_visualization_results.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add tuba/analysis/code_aster_artifacts.py tests/test_code_aster_artifact_import.py
git commit -m "fix: preserve Code_Aster import diagnostics"
```

### Task 2: Record and verify real-solve attestation

**Files:**
- Modify: `tuba/solver/code_aster_runtime.py`
- Modify: `tuba/solver/aster.py`
- Modify: `tuba/analysis/code_aster_artifacts.py`
- Modify: `tests/test_code_aster_runtime.py`
- Modify: `tests/test_code_aster_artifact_import.py`

**Interfaces:**
- Consumes: successful `run_code_aster_export(export_file, work_dir, config) -> CodeAsterExecution` and the existing study manifest identity.
- Produces: `study_execution.json` with schema `tuba.code_aster_execution.v1`.
- Produces: `load_code_aster_execution_attestation(work_dir) -> dict[str, Any] | None`.

- [ ] **Step 1: Add failing attestation tests**

In the runtime test, use a successful fake execution with a `study.mess` containing `Version 18.0.12`, then assert:

```python
attestation = json.loads((work_dir / "study_execution.json").read_text())
assert attestation["schema_version"] == "tuba.code_aster_execution.v1"
assert attestation["solver_name"] == "Code_Aster"
assert attestation["solver_version"] == "18.0.12"
assert attestation["execution_method"] == "wsl"
assert attestation["solver_input_identity"]["fingerprint"] == identity.fingerprint
assert attestation["artifacts"]["study_depl.csv"]["size_bytes"] > 0
assert len(attestation["artifacts"]["study_depl.csv"]["sha256"]) == 64
```

Add importer tests proving a tampered CSV is rejected, a missing attestation remains accepted for generic historical imports, and a validated attestation reaches `ResultState.metadata["solve_attestation"]`.

- [ ] **Step 2: Run focused tests and verify missing attestation behavior fails**

Run: `uv run python -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py -q`

Expected: FAIL because successful executions do not write or validate `study_execution.json`.

- [ ] **Step 3: Write the execution attestation after a successful solve**

Define the exact attested file inventory in `code_aster_runtime.py`:

```python
ATTESTED_CODE_ASTER_FILES = (
    "study.comm", "study.mail", "study.export", "study_manifest.json",
    "study_tuba_fem.json", "study.mess", "study.rmed", "study_depl.csv",
    "study_effo.csv", "study_reac.csv", "study_sieq.csv",
)
```

After `run_code_aster_export` succeeds, have `CodeAsterSolver.solve_exported_study` write the attestation using only observed data: execution runtime kind, first `Version X.Y.Z` from `study.mess`, UTC completion time, manifest identity, and SHA-256/byte size for every existing required artifact. Do not persist the command because it contains machine paths. Missing required result files or solver version abort attestation.

- [ ] **Step 4: Validate attestation before exposing results**

`load_code_aster_execution_attestation` returns `None` for historical directories without the file. When present, require schema/name/version/method/timestamp/identity, compare the identity with study, mesh, and sidecar, and verify every declared size/hash. Raise `ValueError` before `parse_result_artifacts` exposes values. Include `("execution", "study_execution.json")` in `_artifact_files` and place the validated mapping in result metadata.

- [ ] **Step 5: Run runtime and import tests**

Run: `uv run python -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py tests/test_solver_input_provenance.py tests/test_code_aster_sidecar.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add tuba/solver/code_aster_runtime.py tuba/solver/aster.py tuba/analysis/code_aster_artifacts.py tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py
git commit -m "feat: attest real Code_Aster executions"
```

### Task 3: Refresh the canonical gallery through an explicit real-solver command

**Files:**
- Create: `scripts/refresh_code_aster_gallery.py`
- Create: `tests/test_code_aster_gallery_refresh.py`
- Modify: `examples/code_aster_artifact_review.py`
- Modify: `notebooks/code_aster_results/viz_gallery_operating/*`

**Interfaces:**
- CLI: `uv run python scripts/refresh_code_aster_gallery.py --output <directory>`.
- Consumes: public `build_model()` from the example, `CodeAsterSolver.export_analysis_study`, `solve_exported_study`, and `import_code_aster_artifacts`.
- Produces: a real solved artifact chain with matching non-null identities and validated `study_execution.json`.

- [ ] **Step 1: Add failing refresh-command tests**

Use a fake solver only to test CLI orchestration and failure gates. Assert the command calls export then solve then import, and rejects missing RMED, result tables, identity, attestation, version, or execution method. Rename `_build_model()` to public `build_model()` and keep all notebook geometry facts identical.

- [ ] **Step 2: Run focused tests and verify missing command failure**

Run: `uv run python -m pytest tests/test_code_aster_gallery_refresh.py -q`

Expected: import failure because the command does not exist.

- [ ] **Step 3: Implement the minimal command**

```python
model = build_model()
solver = CodeAsterSolver(work_dir=output)
study = solver.export_analysis_study(model, "Operating", output)
solver.solve_exported_study(model, study)
artifact = import_code_aster_artifacts(model=model, work_dir=output)
```

Validate real files, equal identities, and attestation fields before returning zero.

- [ ] **Step 4: Run the real configured Code_Aster refresh**

```text
uv run python -m tuba.solver.code_aster_doctor --check
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
uv run python scripts/refresh_code_aster_gallery.py --output notebooks/code_aster_results/viz_gallery_operating
```

Stop if the doctor is not ready or the command reports anything except a real `wsl` execution. Never use fixture mode.

- [ ] **Step 5: Make the example use observed solve time and verify**

Read `artifact.result_state.metadata["solve_attestation"]["solved_at"]` and pass it to both scene and review builders. Add assertions for equal created times, one identity fingerprint across study/mesh/result provenance, and no hardcoded June timestamp.

Run: `uv run python -m pytest tests/test_code_aster_gallery_refresh.py tests/test_code_aster_artifact_import.py -q`

- [ ] **Step 6: Commit**

```text
git add scripts/refresh_code_aster_gallery.py tests/test_code_aster_gallery_refresh.py examples/code_aster_artifact_review.py notebooks/code_aster_results/viz_gallery_operating
git commit -m "docs: refresh attested Code_Aster gallery"
```

### Task 4: Add the official examples publisher and strict profiles

**Files:**
- Create: `examples/assets/imported_component_demo.stl`
- Create: `scripts/build_pages.py`
- Create: `tests/test_official_viewer_publication.py`
- Modify: `tuba/analysis/code_aster_artifacts.py`
- Modify: `examples/code_aster_artifact_review.py`
- Modify: `examples/imported_component_mixed_system.py`

**Interfaces:**
- Produces: `stage_code_aster_artifact_evidence(artifact, bundle_root) -> CodeAsterArtifactImport`.
- Produces: `build_examples(output: Path, *, audience: str, code_aster_artifacts: Path | None = None) -> tuple[str, ...]`.
- Produces: `validate_official_bundle(root: Path, profile: str) -> None`.
- Produces: `write_bundle_catalog(viewer_root: Path, bundle_ids: tuple[str, ...]) -> Path`.
- CLI: `uv run python scripts/build_pages.py examples --output <directory> [--audience dev|pages]`.
- Catalog record shape: `(bundle_id, producer, audiences, profile)`; no registry class or plugin interface.

- [ ] **Step 1: Write failing catalog and profile tests**

Create tests that call `build_examples`, then the catalog writer, and assert:

```python
bundle_ids = build_examples(tmp_path, audience="pages")
write_bundle_catalog(tmp_path, bundle_ids)
assert bundle_ids == ("code-aster-review", "imported_component_mixed_demo")
assert json.loads((tmp_path / "bundles.json").read_text()) == list(bundle_ids)

engineering = json.loads((tmp_path / "code-aster-review" / "scene.json").read_text())
assert len(engineering["result_fields"]) == 4
assert {layer["category"] for layer in engineering["layers"]} == {
    "design", "analysis_mesh", "results", "annotations"
}

model_review = json.loads((tmp_path / "imported_component_mixed_demo" / "scene.json").read_text())
assert model_review["result_fields"] == []
assert "no solver results" in json.dumps(model_review).lower()
```

Add negative tests for an absolute Windows path, escaping `../` reference, missing geometry payload, bad geometry hash, fixture provenance, missing result family, and an error-severity diagnostic.

- [ ] **Step 2: Run the publication tests and verify missing command failure**

Run: `uv run python -m pytest tests/test_official_viewer_publication.py -q`

Expected: collection/import failure because `scripts.build_pages` does not exist.

- [ ] **Step 3: Implement the small catalog and producer adapters**

Use one tuple in `scripts/build_pages.py`:

```python
OFFICIAL_EXAMPLES = (
    ("code-aster-review", _build_code_aster_review, frozenset({"dev", "pages"}), "engineering-review"),
    ("imported_component_mixed_demo", _build_model_review, frozenset({"dev", "pages"}), "model-review"),
)
```

The engineering adapter calls `run_example` with the committed real artifact directory. The model adapter calls `run_demo` with `examples/assets/imported_component_demo.stl` and `export_study=False`, then copies its `review_scene` directory. Before `run_demo` writes that scene, append this existing scene diagnostic shape:

```python
SceneDiagnostic(
    code="publication.model_review.no_solver_results",
    severity="info",
    message=(
        "Model-review bundle only. Code_Aster has not been run and no "
        "engineering solver results are displayed."
    ),
)
```

Remove `publish_viewer_bundle`; callers use the shared command.

- [ ] **Step 4: Stage portable evidence before scene/review construction**

Implement `stage_code_aster_artifact_evidence` at the artifact ownership boundary. Copy each unique resolved file from study, analysis mesh, and result state to `bundle/artifacts/<basename>`. Reject missing files, symlinks, traversal, and two different sources with the same basename. Return `dataclasses.replace` clones with `AnalysisStudy.work_dir=None` and POSIX-relative file mappings; duplicate roles such as `sieq` and `tuyau_subpoints` reuse one URI. Add `file_sha256` and `file_sizes` metadata maps keyed by each record's file role, using the validated attestation values. The example stages before passing records to the existing scene/review builders, so no serializer or schema fork is added.

- [ ] **Step 5: Implement recursive strict validation**

Load `scene.json`, `review.json` when required, and every geometry payload. Recompute the canonical geometry payload hash using the same sorted compact JSON contract as `write_scene_bundle`. Recursively reject `^[A-Za-z]:[\\/]`, `^\\\\`, absolute POSIX paths, and references escaping the bundle root. Enforce the two profiles exactly as stated in Global Constraints. `build_examples` returns sorted validated IDs; the CLI calls `write_bundle_catalog` only after it returns successfully.

- [ ] **Step 6: Run focused publication and package compatibility tests**

Run:

```text
uv run python -m pytest tests/test_official_viewer_publication.py tests/test_code_aster_artifact_import.py tests/test_package_release.py -q
```

Expected: PASS; package-owned `bundles.json` remains `[]`.

- [ ] **Step 7: Commit**

```text
git add tuba/analysis/code_aster_artifacts.py examples/assets/imported_component_demo.stl examples/code_aster_artifact_review.py examples/imported_component_mixed_system.py scripts/build_pages.py tests/test_official_viewer_publication.py
git commit -m "feat: publish validated official viewer examples"
```

### Task 5: Regenerate the migration-bridge bundles

**Files:**
- Modify: `viewer/public/code-aster-review/**`
- Modify: `viewer/public/imported_component_mixed_demo/**`
- Modify: `tests/test_official_viewer_publication.py`

**Interfaces:**
- Consumes: `uv run python scripts/build_pages.py examples --output viewer/public --audience dev`.
- Produces: current tracked bridge bundles until the final Pages plan proves cross-platform staged generation.

- [ ] **Step 1: Add a semantic bridge comparison test**

Materialize examples into a temporary directory and compare the normalized JSON/file inventory with the two tracked official bundle directories, excluding `bundles.json` and modification times.

- [ ] **Step 2: Run the test and confirm the stale bundle fails**

Run: `uv run python -m pytest tests/test_official_viewer_publication.py -k tracked -q`

Expected: FAIL because the tracked engineering bundle lacks current fields and layers.

- [ ] **Step 3: Regenerate through the single command**

Run: `uv run python scripts/build_pages.py examples --output viewer/public --audience dev`

Review the resulting inventory and ensure `smoke-scene` is untouched.

- [ ] **Step 4: Ignore official generated directories only after Task 4 of the final Pages plan removes them from Git**

Do not add ignore rules during the bridge commit. Add a comment to the test explaining that tracked comparison is temporary and will be deleted with the bridge.

- [ ] **Step 5: Run the bridge, viewer-unit, and artifact tests**

Run:

```text
uv run python -m pytest tests/test_official_viewer_publication.py tests/test_code_aster_artifact_import.py -q
npm.cmd test --prefix viewer
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add viewer/public/code-aster-review viewer/public/imported_component_mixed_demo tests/test_official_viewer_publication.py
git commit -m "docs: refresh official viewer bundles"
```
