# Project and Authoring Session, Plan 4: Freshness and Trust

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A review is stale exactly when its evidence no longer matches what the current model and study would solve, a Code_Aster run executed through Docker is never verified, and volume studies stop exporting the tensor-stress table by default.

**Architecture:**
- **Expected identity (decision 15).** `CodeAsterSolver.analysis_study_inputs` and `CodeAsterSolver.volume_study_inputs` resolve the solved case and fingerprint the solver input. They write, mesh and solve nothing.
  - The exporters call them, so an expected identity and an exported one come from the same code.
  - `tuba/project/freshness.py` builds `expected_identity`, `stale_operations` and `attested_identities` on top of them.
  - The studio's `review_stale` compares the identities in its review bundle with the current model and study.
- **Trust (decision 17).** `execution_trust` in `tuba/solver/code_aster_runtime.py` is the one trust judgement; the importer and the gallery refresh both use it.
- **Tensor stress (decision 19).** Volume studies default to `export_tensor_stress=False`, matching the committed tee evidence.
- **No re-solve.** All 14 committed evidence sets already match the identity the current code expects, and a new test pins that for the nine gallery sets.

**Tech Stack:** Python 3.12, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md` (decisions 15, 17 and 19; roadmap step 4)

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-plan4` on branch `project-session/4-freshness-and-trust` (created from `main` at `412ba8a`).
  - Never commit in `D:/Gitprojects/Tuba_v4`: another session works there.
  - Never `git stash` (the stash stack is shared) and never `git pull`.
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Known worktree failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with "'vite' is not recognized" (no `viewer/node_modules`); ignore them. The suite on `412ba8a`: 1020 passed / 26 skipped / 1 pre-existing zmq warning, plus those two.
- **Line numbers** cite the files at `412ba8a`. Earlier tasks shift them; locate code by the quoted text.
- **Committed evidence is frozen.**
  - Never edit anything under `examples/*/evidence/` or `notebooks/code_aster_results/`, and never run Code_Aster.
  - No change may move a committed set's identity: `build_solver_input_identity` (`tuba/analysis/provenance.py`) and every `compiler_inputs` dict it hashes stay exactly as they are.
  - Volume `compiler_inputs` keep their `export_tensor_stress` key; removing it would change the committed tee fingerprint.
- **Identity functions have no side effects:** they write, mesh and solve nothing.
- **No compatibility shims** (ADR 0001), **no new dependencies**.
- **No commit trailer:** commits carry no `Co-Authored-By` trailer, because commit attribution is disabled for this repository.
- **Accepted consequence of Task 3:** a Code_Aster run executed through Docker imports as unverified, so the review and scene builders refuse to publish it until Plan 5 writes and shows unverified runs (decision 18). This machine solves through WSL, and all 14 committed evidence sets are WSL runs.
- **Out of scope:**
  - reuse and force (decision 13, Plan 5);
  - writing and showing unverified runs, relaxing the publication gates, and the viewer's unverified marker (decision 18, Plans 5–6);
  - a trust requirement in the Pages validator, and the refresh as a forced solve (Plan 6);
  - opening a stale session (decision 16, Plan 7);
  - the study contract, one `SOLVER_OPTIONS` including the volume options (Plan 6);
  - `load_or_run_code_aster_results` (the notebook loader);
  - the viewer's legacy `results_stale` inputs;
  - the inventory rule that treats a manifest without `tensor_stress_exported` as having exported it (`tuba/solver/code_aster_runtime.py:352`, which reads old manifests).

---

### Task 1: Volume studies export no tensor-stress table unless asked

**Files:**
- Modify: `tuba/solver/aster.py:392`, `tuba/solver/aster.py:417`
- Modify: `tuba/solver/aster_volume.py:36`
- Modify: `tests/test_code_aster_volume_study.py:82-83` (and add one test)
- Modify: `tests/test_code_aster_pipe_volume_reference.py:1-51`

**Interfaces:**
- Produces: `CodeAsterSolver.export_volume_study`, `CodeAsterSolver.solve_volume_study` and `PipeVolumeStudyExporter.export_analysis_study` default to `export_tensor_stress=False`.
  - `TubaModel.solve` passes no flag, so its volume path now attests the same identity as the committed tee evidence.
  - Explicit `export_tensor_stress=False` arguments elsewhere (the refresh, `solve_or_import`) stay.

- [ ] **Step 1: Write the failing test**

In `tests/test_code_aster_volume_study.py`, replace lines 82–83:

```python
    assert study.metadata["tensor_stress_exported"] is True
    assert "study_sigm.csv" in Path(study.input_files["export"]).read_text(encoding="utf-8")
```

with:

```python
    assert study.metadata["tensor_stress_exported"] is False
    assert study.metadata["compiler_inputs"]["export_tensor_stress"] is False
    assert "study_sigm.csv" not in Path(study.input_files["export"]).read_text(encoding="utf-8")
```

and add this test right after `test_exports_grouped_pipe_volume_study_without_claiming_results`:

```python
def test_volume_export_writes_the_tensor_stress_table_only_on_request(tmp_path):
    study = CodeAsterSolver(work_dir=tmp_path).export_volume_study(
        _pressurized_pipe_model(),
        "Pressure",
        tmp_path,
        element_ids=["pipe_0"],
        max_element_size=0.005,
        export_tensor_stress=True,
    )

    assert study.metadata["tensor_stress_exported"] is True
    assert study.metadata["compiler_inputs"]["export_tensor_stress"] is True
    assert "study_sigm.csv" in Path(study.input_files["export"]).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_code_aster_volume_study.py -q`

Expected:
- `test_exports_grouped_pipe_volume_study_without_claiming_results` FAILS: `tensor_stress_exported` is still `True`.
- `test_volume_export_writes_the_tensor_stress_table_only_on_request` PASSES; it is a guard for the explicit path.

- [ ] **Step 3: Flip the three defaults**

Change `export_tensor_stress: bool = True` to `export_tensor_stress: bool = False` in:
- `CodeAsterSolver.export_volume_study` (`tuba/solver/aster.py:392`);
- `CodeAsterSolver.solve_volume_study` (`tuba/solver/aster.py:417`);
- `PipeVolumeStudyExporter.export_analysis_study` (`tuba/solver/aster_volume.py:36`).

Leave the `"export_tensor_stress": bool(export_tensor_stress)` key in the volume `compiler_inputs` (`aster_volume.py:70`) untouched.

- [ ] **Step 4: Keep the real-solver hoop-stress reference asking for the table**

`tests/test_code_aster_pipe_volume_reference.py` reads `study_sigm.csv` in `test_pressurized_pipe_volume_matches_lame_and_builds_result_scene`, so it must request the table explicitly.
- `TubaModel.solve` does not take the flag, so that test calls the solver directly.
- The bend test in the same file reads no tensor table and stays on `model.solve`.

Add to the imports, after `from tuba.model import make_bend_geometry`:

```python
from tuba.solver.aster import CodeAsterSolver
```

and replace the `run = model.solve(...)` call at lines 44–51 with:

```python
    # This reference reads the tensor-stress table, which volume studies export only on request.
    run = CodeAsterSolver(
        work_dir=tmp_path,
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    ).solve_volume_study(
        model,
        "Pressure",
        element_ids=["pipe_0"],
        max_element_size=max_element_size,
        export_tensor_stress=True,
    )
```

This suite skips without `TUBA_RUN_CODE_ASTER_INTEGRATION=1`, so it cannot be run here. Check it by running it (expect skipped) and by reading the diff.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_code_aster_volume_study.py tests/test_code_aster_pipe_volume_reference.py tests/test_code_aster_gallery_refresh.py tests/test_code_aster_runtime.py tests/test_official_viewer_publication.py -q`

Expected: PASS, with the reference suite skipped.

- [ ] **Step 6: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider`. It takes about 20 minutes, so run it in the background and wait in bounded stretches; commit only after it finishes.

Expected: no failures other than the two known vite tests. Report the counts.

- [ ] **Step 7: Commit**

```bash
git add tuba/solver/aster.py tuba/solver/aster_volume.py tests/test_code_aster_volume_study.py tests/test_code_aster_pipe_volume_reference.py
git commit -m "fix(solver): volume studies export no tensor-stress table unless asked

Spec decision 19. The committed tee evidence was solved without it, so
TubaModel.solve now attests the same identity. The key stays in
compiler_inputs, so no committed fingerprint moves."
```

---

### Task 2: One expected identity, computed by the exporters' own code

**Files:**
- Modify: `tuba/solver/aster.py`: add `StudyInputs`, `CodeAsterSolver.analysis_study_inputs` and `CodeAsterSolver.volume_study_inputs`, and make `export_analysis_study` (lines 255–292) use the first.
- Modify: `tuba/solver/aster_volume.py`: add `VolumeStudyInputs` and `volume_study_inputs`, and make `PipeVolumeStudyExporter.export_analysis_study` (lines 38–77) use it.
- Create: `tuba/project/freshness.py`
- Create: `tests/test_project_freshness.py`
- Modify: `tests/test_official_viewer_publication.py` (one new parametrised test)

**Interfaces:**
- Consumes: Task 1's `export_tensor_stress=False` default. The volume exporter's signature keeps `export_tensor_stress: bool = False`.
- Produces:
  - `tuba.solver.aster.StudyInputs(load_case_name: str, load_case: LoadCase, compiler_inputs: dict | None, solver_input_identity: SolverInputIdentity)`
  - `CodeAsterSolver.analysis_study_inputs(model, load_case_name=None) -> StudyInputs`
  - `tuba.solver.aster_volume.VolumeStudyInputs(load_case_name, load_case, element_ids: tuple[str, ...], line_elements: list, compiler_inputs: dict, solver_input_identity)`
  - `tuba.solver.aster_volume.volume_study_inputs(model, load_case_name, *, element_ids, max_element_size, element_order=2, export_tensor_stress=False) -> VolumeStudyInputs`
  - `CodeAsterSolver.volume_study_inputs(...)` with the same arguments; it refuses a `load_path` like `export_volume_study`
  - `tuba.project.freshness.expected_identity(model, operation, *, solver_options=None, volume_export=None) -> SolverInputIdentity`
  - `tuba.project.freshness.stale_operations(model, attested, *, solver_options=None, volume_export=None) -> list[str]` (sorted operation names)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_freshness.py`:

```python
"""Freshness: a solve's expected identity comes from the exporters' own code (spec decision 15)."""

import json
from pathlib import Path

import pytest

from tuba import Model
from tuba.analysis.provenance import SolverInputIdentity
from tuba.project import run_model_script
from tuba.project.freshness import expected_identity, stale_operations
from tuba.solver.aster import CodeAsterSolver

SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"


def _hot_line():
    model = Model("FreshnessLine")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1143, WT=0.00602)
    with model.pipe(section="Pipe", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(2.0)
        builder.end(support="anchor")
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model


def _pressure_pipe():
    model = Model("FreshnessVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.2, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
    model.add_support(n0, type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
    return model


def _rack(tmp_path: Path, edit=lambda text: text):
    """The support-rack model, built from a copy of its model.py with *edit* applied."""
    script = tmp_path / "model.py"
    script.write_text(edit((SUPPORT_RACK / "model.py").read_text(encoding="utf-8")), encoding="utf-8")
    return run_model_script(script)["model"]


def _rack_attestation() -> list[SolverInputIdentity]:
    record = json.loads((SUPPORT_RACK / "evidence" / "Operating" / "study_execution.json").read_text(encoding="utf-8"))
    return [SolverInputIdentity.from_dict(record["solver_input_identity"])]


@pytest.mark.parametrize("options", [{}, {"pipe_modelization": "POU_D_T", "line_segments": 4}])
def test_expected_identity_is_the_identity_a_beam_export_writes(tmp_path, options):
    model = _hot_line()

    study = CodeAsterSolver(**options).export_analysis_study(model, "Hot", tmp_path)

    assert expected_identity(model, "Hot", solver_options=options) == study.solver_input_identity


def test_expected_identity_is_the_identity_a_volume_export_writes(tmp_path):
    model = _pressure_pipe()
    volume = {"element_ids": ["pipe_0"], "max_element_size": 0.005}

    study = CodeAsterSolver().export_volume_study(model, "Pressure", tmp_path, **volume)

    assert expected_identity(model, "Pressure", volume_export=volume) == study.solver_input_identity


def test_committed_support_rack_evidence_is_fresh(tmp_path):
    assert stale_operations(_rack(tmp_path), _rack_attestation()) == []


def test_a_rename_or_an_unsolved_load_case_leaves_the_evidence_fresh(tmp_path):
    model = _rack(
        tmp_path,
        lambda text: text.replace('Model("SupportRackReview")', 'Model("RenamedRack")')
        + 'model.define_load_case("Hydrotest", gravity=True, pressure=2.0e6)\n',
    )

    assert stale_operations(model, _rack_attestation()) == []


def test_a_moved_node_makes_the_operation_stale(tmp_path):
    model = _rack(tmp_path, lambda text: text.replace("(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)"))

    assert stale_operations(model, _rack_attestation()) == ["Operating"]


def test_a_changed_study_solver_option_makes_the_operation_stale(tmp_path):
    assert stale_operations(_rack(tmp_path), _rack_attestation(), solver_options={"line_segments": 4}) == ["Operating"]


def test_an_operation_the_model_no_longer_defines_is_stale(tmp_path):
    model = _rack(tmp_path, lambda text: text.replace('"Operating",', '"Cold",'))

    assert stale_operations(model, _rack_attestation()) == ["Operating"]
```

In `tests/test_official_viewer_publication.py`, add this after `test_committed_gallery_artifact_bytes_match_the_execution_attestation`:

```python
def _gallery_evidence() -> list[tuple[object, Path]]:
    """Each committed gallery evidence set, paired with the gallery that imports it."""
    return sorted(
        (
            (gallery, Path(root).resolve().relative_to(REPO_ROOT))
            for gallery in build_pages.OFFICIAL_GALLERIES
            if gallery.artifact_dir is not None
            for root in _gallery_evidence_roots(gallery)
        ),
        key=lambda pair: pair[1],
    )


@pytest.mark.parametrize(
    ("gallery", "artifact_root"),
    _gallery_evidence(),
    ids=lambda value: value.as_posix() if isinstance(value, Path) else value.id,
)
def test_committed_evidence_matches_the_identity_its_study_would_attest_now(gallery, artifact_root: Path) -> None:
    """Spec decision 15: the current model and study options still produce every committed attestation."""
    from tuba.analysis.provenance import SolverInputIdentity
    from tuba.project import load_project
    from tuba.project.freshness import expected_identity

    model = load_project(REPO_ROOT / gallery.project).run_model()["model"]
    attestation = json.loads((REPO_ROOT / artifact_root / "study_execution.json").read_text(encoding="utf-8"))

    assert expected_identity(
        model,
        artifact_root.name,
        solver_options=gallery.solver_options,
        volume_export=gallery.volume_export or None,
    ) == SolverInputIdentity.from_dict(attestation["solver_input_identity"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_freshness.py "tests/test_official_viewer_publication.py::test_committed_evidence_matches_the_identity_its_study_would_attest_now" -q`

Expected:
- `tests/test_project_freshness.py` errors at collection with `ModuleNotFoundError: No module named 'tuba.project.freshness'`.
- All nine parameters of the new gallery test FAIL with the same error.

- [ ] **Step 3: Extract the beam study inputs**

In `tuba/solver/aster.py`, add this class right before `class CodeAsterSolver(`:

```python
class StudyInputs(NamedTuple):
    """What a beam or TUYAU export compiles, resolved without writing anything."""

    load_case_name: str
    load_case: LoadCase
    compiler_inputs: Optional[dict[str, Any]]
    solver_input_identity: SolverInputIdentity
```

Add this method right before `def export_analysis_study(`. Its body is lines 256–292 of `export_analysis_study`, moved without changing a character, except that the identity is returned instead of being assigned:

```python
    def analysis_study_inputs(self, model: TubaModel, load_case_name: Optional[str] = None) -> StudyInputs:
        """Resolve the solved case and fingerprint what :meth:`export_analysis_study` compiles.

        It writes, meshes and solves nothing, so a caller can ask which identity an export
        of the current model would attest (spec decision 15) without exporting.
        """
        if self.load_path is not None:
            if not self.load_path or isinstance(self.load_path, str):
                raise ValueError('load_path must be a nonempty sequence of load-case names.')
            if load_case_name is not None and load_case_name != self.load_path[-1]:
                raise ValueError('The compatibility load case must be the final load_path stage.')
            load_case_name = self.load_path[-1]
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()
        compiler_inputs = (
            {"pipe_modelization": self.pipe_modelization.value, "bend_segments": self._BEND_SEGMENTS}
            if self.pipe_modelization is PipeModelization.POU_D_T else None
        )
        if any(len(self._straight_segment_node_pairs(e)) > 1 for e in model.elements if e.type != "pipe_bend"):
            compiler_inputs = dict(compiler_inputs or {}, line_segments=self.line_segments)
        from tuba.solver.aster_contact import shoes, validate_path
        contact_specs = shoes(model, self.pipe_modelization)
        if self.load_path is not None and not contact_specs:
            raise ValueError('load_path currently requires a native POU_D_T resting shoe.')
        if contact_specs:
            names, cases = validate_path(model, load_case, self.load_path)
            compiler_inputs = dict(compiler_inputs or {}, load_path=list(names), load_step=self.load_step,
                                  contact_law='DIS_CHOC', contact_stiffness_defaults=[1e10, 1e8],
                                  load_path_inputs={name: model.to_dict()['load_cases'][name] for name in names})
        solver_input_identity = build_solver_input_identity(
            model, load_case_name, compiler_inputs=compiler_inputs,
        )
        return StudyInputs(load_case_name, load_case, compiler_inputs, solver_input_identity)
```

In `export_analysis_study`, replace everything from `self._bend_node_cache.clear()` (line 255) through the `solver_input_identity = build_solver_input_identity(...)` statement (line 292) with:

```python
        self._bend_node_cache.clear()
        load_case_name, load_case, compiler_inputs, solver_input_identity = self.analysis_study_inputs(
            model, load_case_name
        )

        if output_dir is not None:
            wdir = Path(output_dir)
            wdir.mkdir(parents=True, exist_ok=True)
        elif self.work_dir is not None:
            wdir = self.work_dir
            wdir.mkdir(parents=True, exist_ok=True)
        else:
            wdir = Path(tempfile.mkdtemp(prefix="tuba_aster_"))

        model_revision = int(getattr(model, "revision", 0))
```

Everything after it, from `mail_path = wdir / "study.mail"`, stays as it is.

Add this method right after `export_volume_study`:

```python
    def volume_study_inputs(
        self,
        model: TubaModel,
        load_case_name: str | None,
        *,
        element_ids,
        max_element_size: float,
        element_order: int = 2,
        export_tensor_stress: bool = False,
    ):
        """Resolve and fingerprint what :meth:`export_volume_study` compiles, without meshing or writing."""
        if self.load_path is not None:
            raise ValueError('Native contact load paths require POU_D_T; volume/mixed paths are unsupported.')
        from tuba.solver.aster_volume import volume_study_inputs

        return volume_study_inputs(
            model,
            load_case_name,
            element_ids=element_ids,
            max_element_size=max_element_size,
            element_order=element_order,
            export_tensor_stress=export_tensor_stress,
        )
```

- [ ] **Step 4: Extract the volume study inputs**

In `tuba/solver/aster_volume.py`:
- change `from typing import Iterable` to `from typing import Any, Iterable, NamedTuple`;
- add `SolverInputIdentity,` to the `from tuba.analysis.provenance import (...)` block.

Add this before `class PipeVolumeStudyExporter:`:

```python
class VolumeStudyInputs(NamedTuple):
    """What a pipe-volume export compiles, resolved without meshing or writing."""

    load_case_name: str
    load_case: Any
    element_ids: tuple[str, ...]
    line_elements: list
    compiler_inputs: dict[str, Any]
    solver_input_identity: SolverInputIdentity


def volume_study_inputs(
    model: TubaModel,
    load_case_name: str | None,
    *,
    element_ids: Iterable[str],
    max_element_size: float,
    element_order: int = 2,
    export_tensor_stress: bool = False,
) -> VolumeStudyInputs:
    """Resolve the solved case and fingerprint what the volume export compiles (spec decision 15).

    The fingerprint never reads the Gmsh mesh, so this meshes and writes nothing.
    """
    from tuba.solver.aster_contact import shoes

    shoes(model, PipeModelization.SOLID_3D)
    load_case_name, load_case = model.resolve_load_case(load_case_name)
    model.validate()
    if any(model.get_insulation(f"element:{element.id}") for element in model.elements):
        raise ValueError("Insulated pipe-volume studies are not supported; use the pipe beam/TUYAU solver so insulation weight is included.")
    ids = tuple(element_ids)
    line_elements = [element for element in model.elements if element.id not in ids]
    mixed_analysis = bool(line_elements)
    compiler_inputs = {
        "element_ids": sorted(ids),
        **({"line_element_ids": sorted(element.id for element in line_elements)} if mixed_analysis else {}),
        "element_order": element_order,
        "max_element_size": float(max_element_size),
        "export_tensor_stress": bool(export_tensor_stress),
    }
    identity = build_solver_input_identity(
        model,
        load_case_name,
        compiler_id=(MIXED_CODE_ASTER_COMPILER_ID if mixed_analysis else VOLUME_CODE_ASTER_COMPILER_ID),
        compiler_inputs=compiler_inputs,
    )
    return VolumeStudyInputs(load_case_name, load_case, ids, line_elements, compiler_inputs, identity)
```

In `PipeVolumeStudyExporter.export_analysis_study`, replace lines 38–77, from `from tuba.solver.aster_contact import shoes` through the `identity = build_solver_input_identity(...)` statement, with:

```python
        inputs = volume_study_inputs(
            model,
            load_case_name,
            element_ids=element_ids,
            max_element_size=max_element_size,
            element_order=element_order,
            export_tensor_stress=export_tensor_stress,
        )
        load_case_name, load_case, ids = inputs.load_case_name, inputs.load_case, inputs.element_ids
        line_elements, compiler_inputs, identity = inputs.line_elements, inputs.compiler_inputs, inputs.solver_input_identity
        mixed_analysis = bool(line_elements)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        med_path = root / "study.med"
        comm_path = root / "study.comm"
        export_path = root / "study.export"
        manifest_path = root / "study_manifest.json"
        sidecar_path = root / "study_tuba_fem.json"
        _reject_unimplemented_loads(load_case)
        pressure = _selected_pressure(model, load_case, ids)

        generated = build_pipe_volume_mesh(
            model,
            med_path,
            element_ids=ids,
            max_element_size=max_element_size,
            element_order=element_order,
        )
```

Everything after it, from `analysis_mesh = replace(generated.analysis_mesh, solver_input_identity=identity)`, stays as it is. The method signature, including `export_tensor_stress: bool = False` from Task 1, is unchanged.

- [ ] **Step 5: Add the freshness module**

Create `tuba/project/freshness.py`:

```python
"""Freshness: whether a project's evidence still belongs to its model and study (spec decision 15).

A review is stale when, for any operation it was solved for, the identity a solve would attest now
differs from the attested one. "Now" means the current model plus the study's current solver options,
computed by the same code the Code_Aster exporters run, so a study-option change also makes it stale.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from tuba.analysis.provenance import SolverInputIdentity
from tuba.model import TubaModel


def expected_identity(
    model: TubaModel,
    operation: str,
    *,
    solver_options: Mapping[str, Any] | None = None,
    volume_export: Mapping[str, Any] | None = None,
) -> SolverInputIdentity:
    """The solver input identity a solve of *operation* would attest for the current model and study.

    *solver_options* and *volume_export* are the study's ``SOLVER_OPTIONS`` and ``VOLUME_EXPORT``.
    Nothing is written, meshed or solved.
    """
    from tuba.solver.aster import CodeAsterSolver

    solver = CodeAsterSolver(**dict(solver_options or {}))
    if volume_export:
        return solver.volume_study_inputs(model, operation, **dict(volume_export)).solver_input_identity
    return solver.analysis_study_inputs(model, operation).solver_input_identity


def stale_operations(
    model: TubaModel,
    attested: Iterable[SolverInputIdentity],
    *,
    solver_options: Mapping[str, Any] | None = None,
    volume_export: Mapping[str, Any] | None = None,
) -> list[str]:
    """The attested operations whose identity no longer matches what the model and study would solve.

    An operation the current model can no longer resolve or validate counts as stale.
    """
    stale = set()
    for identity in attested:
        try:
            current = expected_identity(
                model, identity.load_case, solver_options=solver_options, volume_export=volume_export
            )
        except ValueError:  # a missing operation or a model that no longer validates
            current = None
        if current != identity:
            stale.add(identity.load_case)
    return sorted(stale)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_project_freshness.py tests/test_official_viewer_publication.py tests/test_solver_input_provenance.py tests/test_code_aster_volume_study.py tests/test_code_aster_gallery_refresh.py tests/test_code_aster_friction.py tests/test_code_aster_artifact_import.py -q`

Expected: PASS, including all nine parameters of `test_committed_evidence_matches_the_identity_its_study_would_attest_now`.

- [ ] **Step 7: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 8: Commit**

```bash
git add tuba/solver/aster.py tuba/solver/aster_volume.py tuba/project/freshness.py tests/test_project_freshness.py tests/test_official_viewer_publication.py
git commit -m "feat(project): compute the expected solver input identity with the exporters' own code

Spec decision 15. analysis_study_inputs and volume_study_inputs resolve and
fingerprint what an export compiles without writing or meshing, the exporters
call them, and tuba.project.freshness compares them with attested identities.
A new test proves every committed gallery attestation still matches."
```

---

### Task 3: One trust judgement, and a Docker run is never verified

**Files:**
- Modify: `tuba/solver/code_aster_runtime.py` (add `execution_trust` after `validate_code_aster_execution_attestation`)
- Modify: `tuba/analysis/code_aster_artifacts.py:17-20` and `:262`
- Modify: `scripts/refresh_code_aster_gallery.py:15` and `:123-125`
- Modify: `tests/test_code_aster_runtime.py` (import plus one test)
- Modify: `tests/test_code_aster_artifact_import.py` (the helper at `:363-386` plus one test)

**Interfaces:**
- Produces: `tuba.solver.code_aster_runtime.execution_trust(attestation: Mapping | None) -> str`, which returns `"verified"` or `"unverified"`.
  - The importer's `result_trust` comes from it.
  - The gallery refresh refuses anything it does not call verified.

- [ ] **Step 1: Write the failing tests**

In `tests/test_code_aster_runtime.py`, add `execution_trust,` to the `from tuba.solver.code_aster_runtime import (...)` block (lines 15–25). Add this method to `TestCodeAsterRuntime`:

```python
    def test_execution_trust_is_verified_unless_code_aster_ran_through_docker(self):
        for attestation, trust in (
            (None, "unverified"),
            ({"execution_method": "docker"}, "unverified"),
            ({"execution_method": "wsl"}, "verified"),
            ({"execution_method": "command"}, "verified"),
            ({"execution_method": "python_bridge"}, "verified"),
        ):
            with self.subTest(attestation=attestation):
                self.assertEqual(execution_trust(attestation), trust)
```

In `tests/test_code_aster_artifact_import.py`, give the helper a method parameter. Change its signature to `def _write_execution_attestation(work_dir: Path, identity, execution_method: str = "wsl") -> None:` and its `"execution_method": "wsl",` line to `"execution_method": execution_method,`. Add this method to `TestCodeAsterArtifactImport`, after `test_import_preserves_validated_attestation_on_result_state`:

```python
    def test_import_marks_a_docker_executed_solve_unverified(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            study = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            _write_execution_attestation(work_dir, study.solver_input_identity, execution_method="docker")

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir)

        self.assertEqual(artifact.result_state.metadata["result_trust"], "unverified")
        self.assertEqual(artifact.result_state.metadata["solve_attestation"]["execution_method"], "docker")
        with self.assertRaisesRegex(ValueError, "result_trust == 'verified'"):
            artifact.validate_for_publication(model)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py -q`

Expected:
- `tests/test_code_aster_runtime.py` errors at collection: `ImportError: cannot import name 'execution_trust'`.
- `test_import_marks_a_docker_executed_solve_unverified` FAILS because `result_trust` is `'verified'`.

- [ ] **Step 3: Implement the judgement and use it**

In `tuba/solver/code_aster_runtime.py`, add right after `validate_code_aster_execution_attestation` (which ends with `return payload`):

```python
def execution_trust(attestation: Mapping[str, Any] | None) -> str:
    """The one trust judgement (spec decision 17): ``"verified"`` or ``"unverified"``.

    A run is verified when it has a validated attestation, whose artifact inventory is then
    complete for its profile, and Code_Aster did not run through Docker. Pass the payload that
    :func:`validate_code_aster_execution_attestation` or :func:`load_code_aster_execution_attestation`
    returned.
    """
    if attestation is None or attestation.get("execution_method") == "docker":
        return "unverified"
    return "verified"
```

In `tuba/analysis/code_aster_artifacts.py`:
- add `execution_trust,` to the `from tuba.solver.code_aster_runtime import (...)` block (lines 17–20);
- replace line 262 with:

```python
    metadata = {**result_state.metadata, "result_trust": execution_trust(attestation)}
```

In `scripts/refresh_code_aster_gallery.py`:
- add `from tuba.solver.code_aster_runtime import execution_trust` after `from tuba.solver.aster import CodeAsterSolver` (line 15);
- replace lines 123–125 with:

```python
    execution_method = attestation.get("execution_method")
    if not isinstance(execution_method, str) or not execution_method:
        raise ValueError("Canonical Code_Aster gallery attestation requires an execution_method.")
    if execution_trust(attestation) != "verified":
        raise ValueError(
            f"Canonical Code_Aster gallery attestation is unverified: execution_method {execution_method!r} "
            "is not a qualified runtime."
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py tests/test_code_aster_gallery_refresh.py tests/test_reporting_builder.py tests/test_official_viewer_publication.py tests/test_visualization_results.py tests/test_contact_results.py -q`

Expected: PASS.
- The refresh's two `execution_method` refusals still match their test (`tests/test_code_aster_gallery_refresh.py:322-323`).
- `native-python-runtime` is still accepted (`:377-389`).

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/solver/code_aster_runtime.py tuba/analysis/code_aster_artifacts.py scripts/refresh_code_aster_gallery.py tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py
git commit -m "fix(analysis): judge trust once, and never verify a Docker-executed run

Spec decision 17. execution_trust decides verified or unverified from the
validated attestation. The importer and the gallery refresh both use it, so a
Docker run imports as unverified, and the publication gates refuse it until
Plan 5 shows unverified runs."
```

---

### Task 4: The studio's stale rule is decision 15

**Files:**
- Modify: `tuba/project/freshness.py` (add `attested_identities`)
- Modify: `tuba/visualization/preview/server.py`: class docstring (`:522-527`), `__init__` (`:556`), `review_stale` (`:660-666`), `_produce_review` (`:709`), and `_model_hash` (`:761-762`, deleted)
- Modify: `tests/test_project_freshness.py` (one test)
- Modify: `tests/test_studio_project.py` (imports, `_wait`, the test at `:86-110`, one new test)

**Interfaces:**
- Consumes: Task 2's `stale_operations`.
- Produces: `tuba.project.freshness.attested_identities(review_bundle: str | Path) -> list[SolverInputIdentity]`, read from the bundle's `scene.json` `solver_input_identities`, which `tuba/visualization/builders/_core.py:353-369` writes at the top level.
- Behaviour change in `ProjectStudioServer.review_stale`:
  - true exactly when `out_dir/review` holds solver identities and `stale_operations` names at least one, given the current model and the study's `SOLVER_OPTIONS` and `VOLUME_EXPORT`;
  - a review without solver evidence is never stale;
  - the rule survives a restart, because it reads the bundle on disk.

- [ ] **Step 1: Write the failing tests**

In `tests/test_project_freshness.py`, change the import line to `from tuba.project.freshness import attested_identities, expected_identity, stale_operations` and add:

```python
def test_attested_identities_come_from_the_review_scene(tmp_path):
    identity = {
        "fingerprint": "f" * 64,
        "load_case": "Operating",
        "schema_id": "tuba.model.v4",
        "compiler_id": "tuba.code_aster.v2",
    }
    (tmp_path / "scene.json").write_text(json.dumps({"solver_input_identities": [identity]}), encoding="utf-8")

    assert attested_identities(tmp_path) == [SolverInputIdentity.from_dict(identity)]
    assert attested_identities(tmp_path / "missing") == []
```

In `tests/test_studio_project.py`:
- add `import shutil` to the imports;
- change `_wait` to take a timeout:

```python
    def _wait(self, condition, message: str, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
```

(the rest of `_wait` stays).

Rename `test_build_and_review_bundles_solve_and_go_stale` to `test_build_and_review_bundles_solve_and_an_evidence_free_review_never_goes_stale`, and replace its last four lines (107–110) with:

```python
        # This study's review carries no solver evidence, so nothing in it can go stale (spec decision 15).
        status, payload = self._post(server, "api/script", {"code": MODEL.replace("run(2.0)", "run(3.0)")})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])
        self.assertFalse(self._get(server, "api/project")["review_stale"])
```

Add this test to `StudioProjectModeTest`:

```python
    def test_an_imported_review_goes_stale_only_when_its_solver_input_changes(self):
        from tuba.visualization.preview.server import ProjectStudioServer

        root = Path(self.enterContext(TemporaryDirectory()))
        project = root / "project"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "support-rack-review", project)
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        self.addCleanup(server.stop)
        server.start()
        self._wait(
            lambda: any(event.get("type") in {"review_ready", "review_failed"} for event in server.broker.events),
            "the committed evidence never imported",
            timeout=120.0,
        )
        self.assertIsNone(server.review_error)
        self.assertFalse(self._get(server, "api/project")["review_stale"])

        model = (project / "model.py").read_text(encoding="utf-8")
        renamed = model.replace('Model("SupportRackReview")', 'Model("RenamedRack")') + (
            'model.define_load_case("Hydrotest", gravity=True, pressure=2.0e6)\n'
        )
        status, payload = self._post(server, "api/script", {"code": renamed})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])

        moved = model.replace("(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)")
        status, payload = self._post(server, "api/script", {"code": moved})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])
        self.assertTrue(self._get(server, "api/project")["review_stale"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_freshness.py tests/test_studio_project.py -q`

Expected:
- `tests/test_project_freshness.py` errors at collection: `ImportError: cannot import name 'attested_identities'`.
- `test_build_and_review_bundles_solve_and_an_evidence_free_review_never_goes_stale` FAILS: the old hash rule reports `review_stale` true after the edit.
- `test_an_imported_review_goes_stale_only_when_its_solver_input_changes` FAILS at the rename: the old rule calls a renamed project stale.

- [ ] **Step 3: Read the attested identities**

In `tuba/project/freshness.py`, add `import json` and `from pathlib import Path` to the imports, and add:

```python
def attested_identities(review_bundle: str | Path) -> list[SolverInputIdentity]:
    """The solver input identities a review bundle was built from, read from its ``scene.json``.

    A review without solver evidence (model-only or mesh-only) has none, so it is never stale.
    """
    try:
        scene = json.loads((Path(review_bundle) / "scene.json").read_text(encoding="utf-8"))
    except FileNotFoundError:  # no review yet, or a bundle being swapped
        return []
    return [SolverInputIdentity.from_dict(record) for record in scene.get("solver_input_identities", [])]
```

- [ ] **Step 4: Replace the studio's rule**

In `tuba/visualization/preview/server.py`:

1. **Class docstring** (lines 522–527). Replace it with:

```python
    """The studio for a project folder: ``model.py`` drives Build, ``study.py`` drives Review.

    The live model scene is the ``build/`` bundle and the solved or imported review is
    ``review/``. A Run never overwrites a review, and Review never shows results for a
    model that has changed since without saying so (``review_stale``): a review is stale
    when an operation it was solved for would now attest a different identity.
    """
```

2. **`__init__`.** Delete the line `self._review_model_hash: str | None = None` (line 556).

3. **`review_stale`.** Replace the property (lines 660–666) with:

```python
    @property
    def review_stale(self) -> bool:
        """Spec decision 15: an operation the review was solved for would now attest a different identity."""
        from tuba.project.freshness import attested_identities, stale_operations

        if self.model is None or self.study is None:
            return False
        attested = attested_identities(self.out_dir / "review")
        return bool(attested) and bool(
            stale_operations(
                self.model,
                attested,
                solver_options=getattr(self.study, "SOLVER_OPTIONS", None),
                volume_export=getattr(self.study, "VOLUME_EXPORT", None),
            )
        )
```

4. **`_produce_review`.** Delete the line `self._review_model_hash = _model_hash(namespace["model"])` (line 709).

5. **`_model_hash`.** Delete the function (lines 761–762) and the blank lines that separated it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_project_freshness.py tests/test_studio_project.py tests/test_studio_server.py tests/test_mcp_server.py -q`

Expected: PASS.

- [ ] **Step 6: Check that nothing still names the old rule**

Run: `git grep -n -e _review_model_hash -e "_model_hash(" -- tuba tests scripts`

Expected: no output.

- [ ] **Step 7: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 8: Commit**

```bash
git add tuba/project/freshness.py tuba/visualization/preview/server.py tests/test_project_freshness.py tests/test_studio_project.py
git commit -m "fix(studio): a review is stale when its operations would attest a different identity

Spec decision 15. The studio compared a hash of model.to_dict(), which flagged a
rename or an unsolved load case and missed a solver-option change. It now
compares the identities in its review bundle with what the current model and
study would solve."
```

---

## Finish

- [ ] If `main` has moved, rebase the branch onto it. Then run `PY -m pytest -q -p no:cacheprovider` on the tip and compare with the per-task results.
- [ ] Run `git log --oneline main..HEAD` and confirm the plan commit plus the four task commits.
- [ ] Report to the user. The branch merges into `main` only with the user's approval, and a push is the user's own decision.
