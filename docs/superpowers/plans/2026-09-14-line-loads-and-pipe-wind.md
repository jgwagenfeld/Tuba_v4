# Line Loads and Pipe Wind by Modelization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An authored wind load or line load reaches Code_Aster through the command its element's modelization accepts, and is refused loudly wherever it is not solved.

**Architecture:** `wind` and a new `line_load` operation field stay modelization-free. `tuba/solver/aster_loads.py` resolves them per element and picks the Code_Aster form per modelization: plain `FORCE_POUTRE` for line loads, `VENT` on beam-modelled elements, and Tuba's own cross-flow projection on `TUYAU_3M` pipes. Each kind of load becomes its own load concept (`WIND`, `WIND_TUY`, `LINELOAD`), and `aster_comm.py` adds them to `EXCIT`. Pipe-volume studies refuse line loads; native-contact paths already refuse every operation field.

**Tech Stack:** Python 3.11, numpy, pytest/unittest, Code_Aster 1D commands (`AFFE_CHAR_MECA`, `AFFE_CHAR_MECA_F`, `FORCE_POUTRE`, `FORMULE`), WSL Code_Aster runtime for the opt-in references.

**Spec:** `docs/superpowers/specs/2026-09-14-line-loads-and-pipe-wind-design.md`

## Global Constraints

- Base: committed `main` at `774d01f`, in the worktree `D:\tmp\tuba-line-loads` on branch `feat/line-loads-and-pipe-wind` (see Setup). The uncommitted generalized-fields change in `D:\Gitprojects\Tuba_v4` (`tuba/fields.py` plus edits to the same solver files) is not part of this work. Copy nothing from it.
- Run tests from the worktree root with the main venv: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest <paths> -q`. A fresh worktree has no `viewer/node_modules`, so the two `test_package_release` vite build tests fail there; that is expected.
- A model that validated before this change must export a byte-identical `study.comm`. Do not bump `CODE_ASTER_COMPILER_ID`. Do not move existing load blocks or `EXCIT` entries: new blocks go after the existing wind block, and new `EXCIT` entries go after `_F(CHARGE=WIND),`.
- Every (load, modelization) pair is either proven by a real Code_Aster reference test or refused with a `ValueError` or `ModelValidationError` naming the gap. Nothing is dropped silently.
- Within one `AFFE_CHAR_MECA`, Code_Aster keeps only the last `FORCE_POUTRE` occurrence on an element. This was solved: FY −1000 then FY −500 on one group gave 2000 N. So a load concept lists each element at most once, and each kind of load gets its own concept.
- Code_Aster refuses `FORCE_POUTRE(TYPE_CHARGE='VENT')` on TUYAU elements (`<EXCEPTION> <PIPE1_44> Le chargement de type vent n'est pas utilisable pour les éléments tuyaux`). Never write `VENT` for a pipe element under `TUYAU_3M`.
- Wind rule, solved on `POU_D_T` `VENT`: for the head-on line load `f = q · D_wind · ŵ` on an element with axis `t̂`, the element carries `F = (|f⊥| / |f|) · f⊥`, where `f⊥ = f − (f·t̂) t̂`. `D_wind` is `physical_properties_for_element(model, element).wind_diameter_m`, which includes insulation.
- Units: a `wind` value is dynamic pressure in Pa; a `line_load` value is force per metre in N/m. Both need a finite non-zero `direction`. Cables and bars take neither.
- Code_Aster concept names have at most 8 characters: `WIND`, `WIND_TUY`, `LINELOAD`, `TFX_<n>` / `TFY_<n>` / `TFZ_<n>`.
- Real-solver tests are opt-in: `$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"`, with the runtime taken from `TUBA_CODE_ASTER_EXEC_METHOD` / `TUBA_CODE_ASTER_WSL_DISTRO` (on this machine `wsl` / `Ubuntu`, already set).
- Every commit message ends with the line `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Setup

- [ ] **Create the worktree and commit the spec and plan into it**

```powershell
git -C D:\Gitprojects\Tuba_v4 worktree add D:\tmp\tuba-line-loads -b feat/line-loads-and-pipe-wind main
Copy-Item D:\Gitprojects\Tuba_v4\docs\superpowers\specs\2026-09-14-line-loads-and-pipe-wind-design.md D:\tmp\tuba-line-loads\docs\superpowers\specs\
Copy-Item D:\Gitprojects\Tuba_v4\docs\superpowers\plans\2026-09-14-line-loads-and-pipe-wind.md D:\tmp\tuba-line-loads\docs\superpowers\plans\
git -C D:\tmp\tuba-line-loads add docs/superpowers/specs/2026-09-14-line-loads-and-pipe-wind-design.md docs/superpowers/plans/2026-09-14-line-loads-and-pipe-wind.md
git -C D:\tmp\tuba-line-loads commit -m "docs: spec and plan for line loads and pipe wind by modelization" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

Expected: `git -C D:\tmp\tuba-line-loads log --oneline -2` shows the docs commit on top of `774d01f`.

## File Map

| File | Responsibility in this plan |
|---|---|
| `tuba/model.py` | Which element types an operation field may select |
| `tuba/validation.py` | The `line_load` quantity, direction rules, wind on pipe elements |
| `tuba/schema.py` | `line_load` in the operation-field quantity enum |
| `tuba/solver/aster_loads.py` | Resolve line loads and wind per element; choose and write the Code_Aster form per modelization |
| `tuba/solver/aster_comm.py` | Wire the `WIND`, `WIND_TUY` and `LINELOAD` concepts into the command file |
| `tuba/solver/aster_volume.py` | Refuse line loads in pipe-volume studies |
| `tests/test_operation_fields.py` | Export, validation and refusal tests |
| `tests/test_wind_cross_flow.py` (new) | Pure tests of the wind rule and of the bend `FORMULE` text |
| `tests/test_code_aster_line_loads.py` (new) | Opt-in real Code_Aster reaction checks |
| `docs/architecture/library-architecture-review.md`, `docs/content/modeling.md`, `CONTEXT.md` | Command map, inventory, gaps, glossary |

---

### Task 1: Line loads on pipes and beams

**Files:**
- Modify: `tuba/model.py:1076-1107` (`resolve_operation_field_elements`)
- Modify: `tuba/validation.py:128-204` (`_validate_operation_fields`)
- Modify: `tuba/schema.py:317`
- Modify: `tuba/solver/aster_loads.py:12-13` (type aliases) and append after `write_wind_load` (ends at line 181)
- Modify: `tuba/solver/aster_comm.py:31-41`, `:270-275`, `:702-711`, `:784-787`
- Modify: `tuba/solver/aster_volume.py:220-228`
- Modify: `docs/architecture/library-architecture-review.md:136-141`, `:318`, `:369-370`; `docs/content/modeling.md:167`; `CONTEXT.md:99-101`
- Test: `tests/test_operation_fields.py`
- Create: `tests/test_code_aster_line_loads.py`

**Interfaces:**
- Consumes: existing `Operation.add_field(quantity, value, *, direction=..., route_id=..., element_ids=..., group=...)`, and `group_ma_value(group_names, map_name)` in `tuba/solver/aster_loads.py`.
- Produces:
  - quantity name `"line_load"` (value in N/m, `direction` required);
  - `LineLoadGroups = List[tuple[List[str], float, float, float]]` in `tuba.solver.aster_loads`;
  - `resolve_line_load_groups(model: TubaModel, load_case: LoadCase) -> LineLoadGroups`: one row per distinct force vector, with each element in at most one row;
  - `write_line_load(w: LineWriter, *, map_name: NameMapper, line_loads: LineLoadGroups) -> None`: writes the concept `LINELOAD`;
  - `TubaModel.resolve_operation_field_elements` raises, for the `elements` scope, `"Operation field references elements that do not exist or cannot carry {quantity!r}: {missing!r}."`

- [ ] **Step 1: Write the failing tests**

In `tests/test_operation_fields.py`, replace the import block (lines 1-9):

```python
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.validation import ModelValidationError
from tuba.solver.aster import CodeAsterSolver
```

with:

```python
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.model import Element, OperationField
from tuba.validation import ModelValidationError
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_contact import validate_path
from tuba.solver.modelisation import PipeModelization
```

Then add these tests to `TestOperationFields`, directly before `test_piecewise_profile_fails_before_export`:

```python
    def test_line_load_exports_plain_force_poutre_on_pipes_and_beams(self):
        model = _two_element_route()
        with model.pipe("PipeSec", "Steel", route="RACK") as rack:
            rack.start([0.0, 5.0, 0.0], support="anchor")
            rack.beam(2.0)
            rack.end(support="anchor")
        beam_id = next(element.id for element in model.elements if element.type == "beam")
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("line_load", 250.0, direction=[0.0, 0.0, -2.0])

        restored = Model.from_dict(model.to_dict())
        restored.validate()
        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(restored, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        block = comm[comm.index("LINELOAD = AFFE_CHAR_MECA(") : comm.index("# ----- Solve -----")]
        self.assertIn(f"GROUP_MA=('pipe_str_0', 'pipe_str_1', '{beam_id}',)", block)
        self.assertIn("FX=0.000000E+00", block)
        self.assertIn("FZ=-2.500000E+02", block)
        self.assertNotIn("TYPE_CHARGE", block)
        self.assertIn("_F(CHARGE=LINELOAD),", comm)
        self.assertNotIn("WIND", comm)

    def test_line_load_on_beam_modelized_pipes_uses_the_same_force_poutre(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("line_load", 100.0, route_id="P-100", direction=[0.0, 1.0, 0.0])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir, pipe_modelization=PipeModelization.POU_D_T).export_study(
                model, "Operating", tmpdir
            )
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("LINELOAD = AFFE_CHAR_MECA(", comm)
        self.assertIn("FY=1.000000E+02", comm)
        self.assertIn("_F(CHARGE=LINELOAD),", comm)

    def test_line_load_and_wind_need_a_direction_and_a_carrying_element(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("line_load", 100.0)
        with self.assertRaisesRegex(ModelValidationError, "line_load field requires a finite non-zero direction"):
            model.validate()

        guyed = _model("Guy")
        base = guyed.add_node([0.0, 0.0, 0.0])
        top = guyed.add_node([0.0, 0.0, 5.0])
        guyed.elements.append(Element(id="guy", type="cable", n1=base, n2=top, section="PipeSec", material="Steel"))
        for quantity in ("line_load", "wind"):
            field_record = OperationField(
                quantity, 100.0, direction=[1.0, 0.0, 0.0], scope="elements", element_ids=["guy"]
            )
            with self.assertRaisesRegex(ValueError, f"cannot carry '{quantity}'"):
                guyed.resolve_operation_field_elements(field_record)

    def test_overlapping_line_loads_that_disagree_fail_validation(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("line_load", 100.0, route_id="P-100", direction=[0.0, 0.0, -1.0])
        operating.add_field("line_load", 300.0, element_ids=["pipe_str_0"], direction=[0.0, 0.0, -1.0])

        with self.assertRaisesRegex(ModelValidationError, "overlapping incompatible line_load fields"):
            model.validate()

    def test_line_loads_are_refused_where_they_are_not_realized(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("line_load", 100.0, direction=[0.0, 0.0, -1.0])
        with TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "Pipe-volume line loads are not implemented"):
                CodeAsterSolver().export_volume_study(
                    model, "Operating", tmpdir, element_ids=["pipe_str_0"], max_element_size=0.1
                )

        # Native contact paths already refuse every operation field; this pins that refusal.
        hot = model.define_load_case("Hot", gravity=False)
        hot.fields.append(OperationField("line_load", 100.0, direction=[0.0, 0.0, -1.0]))
        with self.assertRaisesRegex(ValueError, "Native contact load paths currently support"):
            validate_path(model, hot, None)
```

- [ ] **Step 2: Run the tests and confirm they fail for the right reason**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_operation_fields.py -q`

Expected: 5 failures. Four are raised or mismatched on `unsupported quantity 'line_load'`. The cable check fails on `references missing pipe elements ['guy']`. All earlier tests in the file still pass.

- [ ] **Step 3: Let line loads select pipes and beams**

In `tuba/model.py`, replace the start and the `elements` branch of `resolve_operation_field_elements` (lines 1076-1078 and 1101-1107):

```python
    def resolve_operation_field_elements(self, field_record: OperationField) -> List[Element]:
        allowed_types = {"beam"} if field_record.quantity == "wind" else {"pipe_straight", "pipe_bend"}
        pipe_elements = [e for e in self.elements if e.type in allowed_types]
```

```python
        if field_record.scope == "elements":
            ids = set(field_record.element_ids)
            found = {e.id for e in pipe_elements if e.id in ids}
            missing = sorted(ids - found)
            if missing:
                raise ValueError(f"Operation field references missing pipe elements {missing!r}.")
            return [e for e in pipe_elements if e.id in ids]
```

with:

```python
    def resolve_operation_field_elements(self, field_record: OperationField) -> List[Element]:
        allowed_types = {
            "wind": {"beam"},
            "line_load": {"beam", "pipe_straight", "pipe_bend"},
        }.get(field_record.quantity, {"pipe_straight", "pipe_bend"})
        pipe_elements = [e for e in self.elements if e.type in allowed_types]
```

```python
        if field_record.scope == "elements":
            ids = set(field_record.element_ids)
            found = {e.id for e in pipe_elements if e.id in ids}
            missing = sorted(ids - found)
            if missing:
                raise ValueError(
                    "Operation field references elements that do not exist or cannot carry "
                    f"{field_record.quantity!r}: {missing!r}."
                )
            return [e for e in pipe_elements if e.id in ids]
```

- [ ] **Step 4: Validate the `line_load` quantity**

In `tuba/validation.py` `_validate_operation_fields`, make three replacements.

(a) Lines 129-141:

```python
    valid_quantities = {"pressure", "temperature", "wind"}
```

```python
                    "supported quantities are pressure, temperature, and wind."
```

become:

```python
    valid_quantities = {"pressure", "temperature", "wind", "line_load"}
```

```python
                    "supported quantities are pressure, temperature, wind, and line_load."
```

(b) Lines 171-181:

```python
            if field_record.direction is not None and field_record.quantity != "wind":
                errors.append(f"{label} uses direction but only wind fields accept direction.")
                continue
            if field_record.quantity == "wind":
                if field_record.direction is None:
                    errors.append(f"{label} wind field requires a finite non-zero direction vector.")
                    continue
                direction = np.asarray(field_record.direction, dtype=float)
                if direction.shape != (3,) or not np.all(np.isfinite(direction)) or np.linalg.norm(direction) <= 1e-12:
                    errors.append(f"{label} wind field requires a finite non-zero direction vector.")
                    continue
```

become:

```python
            if field_record.direction is not None and field_record.quantity not in {"wind", "line_load"}:
                errors.append(f"{label} uses direction but only wind and line_load fields accept direction.")
                continue
            if field_record.quantity in {"wind", "line_load"}:
                if field_record.direction is None:
                    errors.append(f"{label} {field_record.quantity} field requires a finite non-zero direction vector.")
                    continue
                direction = np.asarray(field_record.direction, dtype=float)
                if direction.shape != (3,) or not np.all(np.isfinite(direction)) or np.linalg.norm(direction) <= 1e-12:
                    errors.append(f"{label} {field_record.quantity} field requires a finite non-zero direction vector.")
                    continue
```

(c) Lines 200-205:

```python
            if not selected:
                if field_record.quantity == "wind":
                    errors.append(f"{label} {_BEAM_WIND_ONLY_MESSAGE}; selected no beam-modeled elements.")
                else:
                    errors.append(f"{label} selects no pipe elements.")
                continue
```

becomes:

```python
            if not selected:
                if field_record.quantity == "wind":
                    errors.append(f"{label} {_BEAM_WIND_ONLY_MESSAGE}; selected no beam-modeled elements.")
                elif field_record.quantity == "line_load":
                    errors.append(f"{label} selects no pipe or beam elements.")
                else:
                    errors.append(f"{label} selects no pipe elements.")
                continue
```

In `tuba/schema.py` line 317, replace:

```python
                "quantity": {"enum": ["pressure", "temperature", "wind"]},
```

with:

```python
                "quantity": {"enum": ["pressure", "temperature", "wind", "line_load"]},
```

- [ ] **Step 5: Resolve and write line loads**

In `tuba/solver/aster_loads.py`, after line 13 (`WindGroups = ...`), add:

```python
LineLoadGroups = List[tuple[List[str], float, float, float]]
```

Append after `write_wind_load` (which ends at line 181):

```python
def resolve_line_load_groups(model: TubaModel, load_case: LoadCase) -> LineLoadGroups:
    """Line loads as force per metre in global axes, grouped by value.

    Code_Aster keeps only the last FORCE_POUTRE occurrence on an element within
    one AFFE_CHAR_MECA (two loads on one group solved as the second alone), so
    every element lands in exactly one row. Validation has already refused
    overlapping line loads that disagree.
    """
    forces: dict[str, tuple[float, float, float]] = {}
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.quantity != "line_load":
            continue
        if field_record.profile != "uniform":
            raise ValueError(
                f"Operation field {index} for 'line_load' uses profile "
                f"{field_record.profile!r}; only uniform fields can be exported."
            )
        direction = np.asarray(field_record.direction, dtype=float)
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-12:
            raise ValueError(f"Operation field {index} for 'line_load' requires a non-zero direction.")
        elements = model.resolve_operation_field_elements(field_record)
        if not elements:
            raise ValueError(f"Operation field {index} for 'line_load' selects no pipe or beam elements.")
        force = (
            float(field_record.value) * float(direction[0]) / norm,
            float(field_record.value) * float(direction[1]) / norm,
            float(field_record.value) * float(direction[2]) / norm,
        )
        for elem in elements:
            forces[elem.id] = force
    groups: dict[tuple[float, float, float], List[str]] = {}
    for element_id, force in forces.items():
        groups.setdefault(force, []).append(element_id)
    return [(element_ids, fx, fy, fz) for (fx, fy, fz), element_ids in groups.items()]


def write_line_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    line_loads: LineLoadGroups,
) -> None:
    w("# ----- Line loads on pipes and beams -----")
    w("LINELOAD = AFFE_CHAR_MECA(")
    w("    MODELE=MODELE,")
    w("    FORCE_POUTRE=(")
    for group_names, fx, fy, fz in line_loads:
        w("        _F(")
        w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
        w(f"            FX={fx:.6E},")
        w(f"            FY={fy:.6E},")
        w(f"            FZ={fz:.6E},")
        w("        ),")
    w("    ),")
    w(");")
    w()
```

- [ ] **Step 6: Wire `LINELOAD` into the command file**

In `tuba/solver/aster_comm.py`:

(a) Replace the `aster_loads` import (lines 31-41) with:

```python
from tuba.solver.aster_loads import (
    group_ma_value,
    has_pressure_load,
    has_temperature_load as has_thermal_load,
    has_wind_load,
    resolve_line_load_groups,
    resolve_operation_field_groups,
    resolve_wind_field_groups,
    write_line_load,
    write_pressure_load,
    write_thermal_load,
    write_wind_load,
)
```

(b) Replace lines 270-275:

```python
        wind_fields = resolve_wind_field_groups(model, load_case)
        nodal_forces = list(getattr(load_case, "nodal_forces", []))
        has_pressure = has_pressure_load(load_case, pressure_fields)
        has_temperature = has_thermal_load(load_case, temperature_fields)
        has_wind = has_wind_load(wind_fields)
        has_nodal_forces = bool(nodal_forces)
```

with:

```python
        wind_fields = resolve_wind_field_groups(model, load_case)
        line_loads = resolve_line_load_groups(model, load_case)
        nodal_forces = list(getattr(load_case, "nodal_forces", []))
        has_pressure = has_pressure_load(load_case, pressure_fields)
        has_temperature = has_thermal_load(load_case, temperature_fields)
        has_wind = has_wind_load(wind_fields)
        has_line_load = bool(line_loads)
        has_nodal_forces = bool(nodal_forces)
```

(c) Directly after the wind block (lines 702-711, ending with the closing `)` of `write_wind_load(...)`), add:

```python

            # ==============================================================
            # AFFE_CHAR_MECA — line loads on pipes and beams
            # ==============================================================
            if has_line_load:
                write_line_load(
                    w,
                    map_name=map_name,
                    line_loads=line_loads,
                )
```

(d) Replace lines 784-787:

```python
            if has_wind:
                excit_entries.append("        _F(CHARGE=WIND),")
            if has_nodal_forces:
                excit_entries.append("        _F(CHARGE=POINT_FORCE),")
```

with:

```python
            if has_wind:
                excit_entries.append("        _F(CHARGE=WIND),")
            if has_line_load:
                excit_entries.append("        _F(CHARGE=LINELOAD),")
            if has_nodal_forces:
                excit_entries.append("        _F(CHARGE=POINT_FORCE),")
```

In `tuba/solver/aster_volume.py` `_reject_unimplemented_loads` (lines 220-222), replace:

```python
def _reject_unimplemented_loads(load_case) -> None:
    if any(field.quantity == "wind" for field in load_case.fields):
        raise ValueError("Pipe-volume wind loading is not implemented.")
```

with:

```python
def _reject_unimplemented_loads(load_case) -> None:
    if any(field.quantity == "wind" for field in load_case.fields):
        raise ValueError("Pipe-volume wind loading is not implemented.")
    if any(field.quantity == "line_load" for field in load_case.fields):
        raise ValueError("Pipe-volume line loads are not implemented.")
```

- [ ] **Step 7: Run the tests and confirm they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_operation_fields.py -q`
Expected: all pass, including the existing `test_wind_field_exports_for_beam_modelized_pipe_sections_only` and `test_wind_field_rejects_tuyau_pipe_elements`.

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_schema.py tests/test_validation.py tests/test_insulation_solver.py tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_code_aster_volume_study.py tests/test_solver_input_provenance.py tests/test_reporting_tables.py -q`
Expected: all pass, with opt-in Code_Aster tests skipped.

- [ ] **Step 8: Add the real Code_Aster line-load reference and run it**

Create `tests/test_code_aster_line_loads.py`:

```python
"""Real Code_Aster references: authored distributed loads reach the pipe in full.

A statics check needs no stiffness: the support reactions of a loaded pipe
must add up to minus the applied load, whatever the modelization.
"""
import math
import os
from pathlib import Path

import pytest

from tuba import Model
from tuba.model import BendGeometry

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster line-load references",
)

RUN_LENGTH = 4.0
BEND_RADIUS = 0.5
BEND_LENGTH = BEND_RADIUS * math.pi / 2.0


def elbow_model(name: str) -> tuple[Model, tuple[str, str]]:
    """A 4 m straight along X into a 90 degree elbow turning to Y, anchored at both ends."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([RUN_LENGTH, 0.0, 0.0])
    end = model.add_node([RUN_LENGTH + BEND_RADIUS, BEND_RADIUS, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="Pipe", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="Pipe", material="Steel",
        bend_radius=BEND_RADIUS, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[RUN_LENGTH, BEND_RADIUS, 0.0], normal=[0.0, 0.0, 1.0], radius=BEND_RADIUS, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model, (start, end)


def reaction_total(run, nodes) -> list[float]:
    return [sum(float(run.results.node_results[node].reaction_force[i]) for node in nodes) for i in range(3)]


@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_line_load_reaches_straight_and_elbow_in_full(modelization):
    model, anchors = elbow_model(f"LineLoad {modelization}")
    model.define_operation("Load", gravity=False).add_field("line_load", 1000.0, direction=[1.0, 0.0, -1.0])
    root = Path(f".build/line-load-references/line-load-{modelization}").resolve()
    run = model.solve("Load", pipe_modelization=modelization, work_dir=str(root), force=True)
    # The load is not projected: every metre of straight and elbow carries the full 1000 N/m.
    total = 1000.0 * (RUN_LENGTH + BEND_LENGTH) / math.sqrt(2.0)
    expected = [-total, 0.0, total]
    observed = reaction_total(run, anchors)
    print(f"line load {modelization}: reactions {observed}, expected {expected}")
    assert observed == pytest.approx(expected, rel=1e-3, abs=1.0)
```

Run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_code_aster_line_loads.py -q -s
```

Expected: `2 passed` (not skipped). The printed reactions are about (−3383.7, 0, +3383.7) N for both modelizations. TUYAU_3M comes out about 0.2 N low because its elbow is meshed as 16 straight chords. If the run reports `skipped`, the runtime is not configured; stop and report it instead of committing.

- [ ] **Step 9: Document line loads**

In `docs/architecture/library-architecture-review.md`, replace lines 136-141:

```
Supported operation-field quantities are `pressure`, `temperature`, and `wind`.
The Code_Aster writer supports uniform fields for all three quantities. It also
supports `profile="linear"` for temperature fields scoped by route/station,
exported as per-element midpoint temperature assignments through `CREA_CHAMP`.
Non-uniform pressure, non-uniform wind, and piecewise profiles still fail
validation before export.
```

with:

```
Supported operation-field quantities are `pressure`, `temperature`, `wind`, and
`line_load`. The Code_Aster writer supports uniform fields for all four
quantities. It also supports `profile="linear"` for temperature fields scoped by
route/station, exported as per-element midpoint temperature assignments through
`CREA_CHAMP`. Non-uniform pressure, non-uniform wind, and piecewise profiles
still fail validation before export.
A line load (`line_load`, newtons per metre along one global direction) loads
pipe and beam elements in full through a plain `FORCE_POUTRE` under `TUYAU_3M`
and `POU_D_T`; pipe-volume and native-contact studies refuse it.
```

Replace the command-map row at line 318:

```
| Supports, gravity, pressure, wind, mixed couplings | `AFFE_CHAR_MECA`, `AFFE_CHAR_MECA_F` | Writes `DDL_IMPO`, `PESANTEUR`, `FORCE_TUYAU`, beam-modeled wind through `FORCE_POUTRE(TYPE_CHARGE='VENT')`, and `LIAISON_ELEM`. | [U4.44.01 AFFE_CHAR_MECA](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.01.html) |
```

with:

```
| Supports, gravity, pressure, wind, line loads, mixed couplings | `AFFE_CHAR_MECA`, `AFFE_CHAR_MECA_F` | Writes `DDL_IMPO`, `PESANTEUR`, `FORCE_TUYAU`, beam-modeled wind through `FORCE_POUTRE(TYPE_CHARGE='VENT')`, line loads through a plain `FORCE_POUTRE`, and `LIAISON_ELEM`. | [U4.44.01 AFFE_CHAR_MECA](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.01.html) |
```

Replace the inventory bullet at lines 369-370:

```
- Local uniform pressure and temperature fields compiled into Code_Aster mesh
  groups.
```

with:

```
- Local uniform pressure and temperature fields compiled into Code_Aster mesh
  groups.
- Line loads compiled into a plain `FORCE_POUTRE` on pipe and beam elements
  under `TUYAU_3M` and `POU_D_T`.
```

In `docs/content/modeling.md` line 167, replace `and wind fields without a finite non-zero direction.` with `and wind or line-load fields without a finite non-zero direction.`

In `CONTEXT.md`, replace lines 99-101:

```
**Applied input**:
An authored load, pressure, temperature, or boundary condition shown during postprocessing to explain the analysis setup.
_Avoid_: Solver result
```

with:

```
**Applied input**:
An authored load, pressure, temperature, or boundary condition shown during postprocessing to explain the analysis setup.
_Avoid_: Solver result

**Line load**:
A force per metre of pipe or beam along one fixed global direction, carried in full whatever the element's orientation.
_Avoid_: Distributed wind, nodal force
```

- [ ] **Step 10: Commit**

```powershell
git -C D:\tmp\tuba-line-loads add tuba/model.py tuba/validation.py tuba/schema.py tuba/solver/aster_loads.py tuba/solver/aster_comm.py tuba/solver/aster_volume.py tests/test_operation_fields.py tests/test_code_aster_line_loads.py docs/architecture/library-architecture-review.md docs/content/modeling.md CONTEXT.md
git -C D:\tmp\tuba-line-loads commit -m "feat(solver): compile line loads into FORCE_POUTRE on pipes and beams" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The cross-flow wind rule

**Files:**
- Modify: `tuba/solver/aster_loads.py:1-10` (imports) and append two functions at the end of the file
- Create: `tests/test_wind_cross_flow.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `cross_flow_line_load(line_load: Sequence[float], tangent: Sequence[float]) -> tuple[float, float, float]`: the force per metre an element with axis `tangent` carries from the head-on wind line load `line_load`. The tangent need not be a unit vector. A zero load gives zeros.
  - `cross_flow_formula(line_load: Sequence[float], center: Sequence[float], axis: Sequence[float]) -> tuple[str, str, str]`: the same rule along a circular bend, as Python expression text in `X`, `Y`, `Z` using `sqrt`. Numbers are written with `repr`. A zero load gives `("0.0", "0.0", "0.0")`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wind_cross_flow.py`:

```python
"""The wind rule Code_Aster applies with FORCE_POUTRE(TYPE_CHARGE='VENT'), reproduced for TUYAU_3M."""
import math

import numpy as np
import pytest

from tuba.solver.aster_loads import cross_flow_formula, cross_flow_line_load


def evaluate(texts, point):
    """Evaluate FORMULE text the way Code_Aster sees it: X, Y, Z and math's sqrt."""
    scope = {"X": float(point[0]), "Y": float(point[1]), "Z": float(point[2]), "sqrt": math.sqrt}
    return tuple(eval(compile(text, "<FORMULE>", "eval"), {"__builtins__": {}}, scope) for text in texts)


def test_head_on_wind_is_carried_in_full():
    assert cross_flow_line_load([0.0, 1000.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx((0.0, 1000.0, 0.0))


def test_wind_along_the_axis_carries_nothing():
    assert cross_flow_line_load([1000.0, 0.0, 0.0], [2.0, 0.0, 0.0]) == pytest.approx((0.0, 0.0, 0.0))


def test_oblique_wind_matches_the_solved_vent_straight():
    # Solved on POU_D_T with VENT: 1000 N/m at 30 degrees over 4 m gave 1000 N across the axis.
    angle = math.radians(30.0)
    carried = cross_flow_line_load([1000.0 * math.cos(angle), 1000.0 * math.sin(angle), 0.0], [1.0, 0.0, 0.0])
    assert carried == pytest.approx((0.0, 250.0, 0.0))


def test_no_wind_gives_no_load():
    assert cross_flow_line_load([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == (0.0, 0.0, 0.0)
    assert cross_flow_formula([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]) == ("0.0", "0.0", "0.0")


def test_bend_formula_equals_the_point_rule_on_a_tilted_bend():
    axis = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    center = np.array([2.0, -1.0, 0.5])
    start = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    across = np.cross(axis, start)
    wind = (300.0, -1000.0, 200.0)
    texts = cross_flow_formula(wind, center, axis)
    for phi in np.linspace(0.0, math.pi / 2.0, 7):
        point = center + 0.5 * (math.cos(phi) * start + math.sin(phi) * across)
        tangent = np.cross(axis, point - center)
        assert evaluate(texts, point) == pytest.approx(cross_flow_line_load(wind, tangent), abs=1e-9)


def test_bend_formula_integrates_to_the_solved_vent_elbow():
    # Solved on POU_D_T with VENT: a 90 degree, 0.5 m elbow under 1000 N/m in -Y gave
    # reactions (-166.7, +333.3) N, so the elbow carried (R/3, -2R/3) x 1000 N.
    radius = 0.5
    texts = cross_flow_formula((0.0, -1000.0, 0.0), (0.0, radius, 0.0), (0.0, 0.0, 1.0))
    steps = 400
    total = np.zeros(3)
    for i in range(steps):
        phi = (i + 0.5) * (math.pi / 2.0) / steps
        point = (radius * math.sin(phi), radius - radius * math.cos(phi), 0.0)
        total += np.array(evaluate(texts, point)) * radius * (math.pi / 2.0) / steps
    assert tuple(total) == pytest.approx((1000.0 * radius / 3.0, -2000.0 * radius / 3.0, 0.0), rel=1e-5, abs=1e-6)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_wind_cross_flow.py -q`
Expected: collection error `ImportError: cannot import name 'cross_flow_formula' from 'tuba.solver.aster_loads'`.

- [ ] **Step 3: Implement the rule**

In `tuba/solver/aster_loads.py`, replace the imports (lines 3-10):

```python
from __future__ import annotations

from typing import Callable, List

import numpy as np

from tuba.model import LoadCase, TubaModel
from tuba.physical import physical_properties_for_element
```

with:

```python
from __future__ import annotations

import math
from typing import Callable, List, Sequence

import numpy as np

from tuba.model import LoadCase, TubaModel
from tuba.physical import physical_properties_for_element
```

Append at the end of the file:

```python
def cross_flow_line_load(line_load: Sequence[float], tangent: Sequence[float]) -> tuple[float, float, float]:
    """The wind force per metre an element whose axis is ``tangent`` actually carries.

    This is the rule Code_Aster applies for FORCE_POUTRE(TYPE_CHARGE='VENT'):
    keep the part of the wind across the axis, and scale it once more by the
    sine of the angle between wind and axis. A pipe at 30 degrees to the wind
    carries a quarter of the head-on load (solved on POU_D_T: 1000 N/m at 30
    degrees over 4 m gave 1000 N). TUYAU_3M refuses VENT, so Tuba applies the
    same rule itself on pipe elements.
    """
    force = np.asarray(line_load, dtype=float)
    magnitude = float(np.linalg.norm(force))
    if magnitude == 0.0:
        return (0.0, 0.0, 0.0)
    axis = np.asarray(tangent, dtype=float)
    axis = axis / float(np.linalg.norm(axis))
    across = force - float(np.dot(force, axis)) * axis
    carried = across * (float(np.linalg.norm(across)) / magnitude)
    return (float(carried[0]), float(carried[1]), float(carried[2]))


def cross_flow_formula(
    line_load: Sequence[float],
    center: Sequence[float],
    axis: Sequence[float],
) -> tuple[str, str, str]:
    """``cross_flow_line_load`` along a circular bend, as FORMULE text in X, Y, Z.

    The bend tangent at a point P is ``axis x (P - center)``; only its direction
    matters, so it stays unnormalized. Numbers use ``repr`` so the text is exact.
    Solved on TUYAU_3M, this text matched POU_D_T VENT on an elbow within 0.06%.
    """
    fx, fy, fz = (float(value) for value in line_load)
    magnitude = math.sqrt(fx * fx + fy * fy + fz * fz)
    if magnitude == 0.0:
        return ("0.0", "0.0", "0.0")
    unit = np.asarray(axis, dtype=float)
    ax, ay, az = (float(value) for value in unit / float(np.linalg.norm(unit)))
    cx, cy, cz = (float(value) for value in center)
    rx, ry, rz = f"(X-({cx!r}))", f"(Y-({cy!r}))", f"(Z-({cz!r}))"
    tx = f"(({ay!r})*{rz}-({az!r})*{ry})"
    ty = f"(({az!r})*{rx}-({ax!r})*{rz})"
    tz = f"(({ax!r})*{ry}-({ay!r})*{rx})"
    along = f"((({fx!r})*{tx}+({fy!r})*{ty}+({fz!r})*{tz})/({tx}**2+{ty}**2+{tz}**2))"
    across = [f"(({f!r})-{along}*{t})" for f, t in ((fx, tx), (fy, ty), (fz, tz))]
    scale = f"(sqrt({across[0]}**2+{across[1]}**2+{across[2]}**2)/({magnitude!r}))"
    return (f"{scale}*{across[0]}", f"{scale}*{across[1]}", f"{scale}*{across[2]}")
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_wind_cross_flow.py tests/test_operation_fields.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git -C D:\tmp\tuba-line-loads add tuba/solver/aster_loads.py tests/test_wind_cross_flow.py
git -C D:\tmp\tuba-line-loads commit -m "feat(solver): reproduce Code_Aster's VENT cross-flow rule for pipe elements" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Wind on pipe elements, by modelization

**Files:**
- Modify: `tuba/model.py` (`resolve_operation_field_elements`, as changed in Task 1)
- Modify: `tuba/validation.py:17-21` (delete `_BEAM_WIND_ONLY_MESSAGE`), and the selection checks as changed in Task 1
- Modify: `tuba/solver/aster_loads.py` (model import, type aliases, the `resolve_wind_field_groups` message at line 134, and two new functions)
- Modify: `tuba/solver/aster_comm.py` (import, wind resolution, wind block, `EXCIT`)
- Modify: `docs/architecture/library-architecture-review.md` (lines 142-144, 318, 330-336, 371-373, 415 in the original numbering), `CONTEXT.md`
- Test: `tests/test_operation_fields.py` (replace `test_wind_field_rejects_tuyau_pipe_elements`, add three tests)
- Modify: `tests/test_code_aster_line_loads.py` (append the wind references)

**Interfaces:**
- Consumes:
  - `cross_flow_line_load` and `cross_flow_formula` (Task 2);
  - `resolve_line_load_groups`, `write_line_load`, and the `has_line_load` / `LINELOAD` wiring (Task 1);
  - `CodeAsterSolver._get_bend_geometry(model, elem) -> (center, normal, r1, theta)`, an existing staticmethod at `tuba/solver/aster_mesh.py:666-667`, reachable as `self._get_bend_geometry` inside `_CommWriterMixin`.
- Produces:
  - `TuyauWindRows = List[tuple[str, str, tuple[str, str, str]]]`: rows of (element id, `NOM_PARA` literal, the X/Y/Z `FORMULE` texts);
  - `BendFrame = Callable[[Element], tuple[Sequence[float], Sequence[float]]]`: returns (center, axis) of a bend;
  - `tuyau_wind_rows(model: TubaModel, wind_fields: WindGroups, bend_frame: BendFrame) -> TuyauWindRows`: one row per element;
  - `write_tuyau_wind_load(w: LineWriter, *, map_name: NameMapper, rows: TuyauWindRows) -> None`: writes `TFX_<n>` / `TFY_<n>` / `TFZ_<n>` and the concept `WIND_TUY`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_operation_fields.py`, replace the whole `test_wind_field_rejects_tuyau_pipe_elements` method:

```python
    def test_wind_field_rejects_tuyau_pipe_elements(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, route_id="P-100", direction=[1.0, 0.0, 0.0])

        with self.assertRaisesRegex(ModelValidationError, "FORCE_POUTRE.*TUYAU_3M.*FORCE_NODALE"):
            model.validate()
```

with:

```python
    def test_wind_on_tuyau_pipes_applies_the_cross_flow_rule_itself(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, route_id="P-100", direction=[1.0, 1.0, 0.0])
        model.validate()

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        # 1000 Pa on a 0.1 m pipe is 100 N/m head-on. At 45 degrees to the axis the pipe
        # carries 100 * sin(45)^2 = 50 N/m across it and nothing along it.
        self.assertIn("WIND_TUY = AFFE_CHAR_MECA_F(", comm)
        self.assertNotIn("TYPE_CHARGE='VENT'", comm)
        self.assertIn("GROUP_MA='pipe_str_0'", comm)
        self.assertIn("VALE='''0.000000E+00'''", comm)
        self.assertIn("VALE='''5.000000E+01'''", comm)
        self.assertIn("_F(CHARGE=WIND_TUY),", comm)

    def test_wind_on_a_tuyau_bend_follows_the_bend_axis(self):
        model = _model("BendWind")
        with model.pipe("PipeSec", "Steel", route="P-200") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.run(1.0)
            pipe.bend(radius=0.5, angle=90.0, plane="XY")
            pipe.run(1.0)
            pipe.end(support="anchor")
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, direction=[0.0, -1.0, 0.0])
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        block = comm[comm.index("WIND_TUY = AFFE_CHAR_MECA_F(") : comm.index("# ----- Solve -----")]
        self.assertIn(f"GROUP_MA='{bend.id}'", block)
        self.assertIn("NOM_PARA=('X', 'Y', 'Z')", comm)
        self.assertIn("sqrt(", comm)

    def test_wind_on_beam_modelized_pipes_keeps_code_aster_vent(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, route_id="P-100", direction=[0.0, 1.0, 0.0])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir, pipe_modelization=PipeModelization.POU_D_T).export_study(
                model, "Operating", tmpdir
            )
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("WIND = AFFE_CHAR_MECA_F(", comm)
        self.assertIn("TYPE_CHARGE='VENT'", comm)
        self.assertIn("GROUP_MA='pipe_str_0'", comm)
        self.assertNotIn("WIND_TUY", comm)

    def test_wind_and_line_load_on_one_pipe_stay_separate_loads(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, direction=[0.0, 1.0, 0.0])
        operating.add_field("line_load", 50.0, direction=[0.0, 0.0, -1.0])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        # One FORCE_POUTRE command keeps only its last occurrence per element, so the two
        # loads must be separate concepts that EXCIT adds.
        self.assertIn("WIND_TUY = AFFE_CHAR_MECA_F(", comm)
        self.assertIn("LINELOAD = AFFE_CHAR_MECA(", comm)
        excit = comm[comm.index("EXCIT=(") :]
        self.assertLess(excit.index("_F(CHARGE=WIND_TUY),"), excit.index("_F(CHARGE=LINELOAD),"))
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_operation_fields.py -q`
Expected: the three TUYAU tests fail with `ModelValidationError` naming `FORCE_POUTRE(TYPE_CHARGE='VENT') on beam-modeled elements only`. `test_wind_on_beam_modelized_pipes_keeps_code_aster_vent` fails the same way, because validation still refuses wind on pipe elements.

- [ ] **Step 3: Let wind select pipe elements**

In `tuba/model.py` `resolve_operation_field_elements`, replace the allowed-types lookup from Task 1:

```python
        allowed_types = {
            "wind": {"beam"},
            "line_load": {"beam", "pipe_straight", "pipe_bend"},
        }.get(field_record.quantity, {"pipe_straight", "pipe_bend"})
```

with:

```python
        allowed_types = (
            {"beam", "pipe_straight", "pipe_bend"}
            if field_record.quantity in {"wind", "line_load"}
            else {"pipe_straight", "pipe_bend"}
        )
```

In `tuba/validation.py`, delete the `_BEAM_WIND_ONLY_MESSAGE` constant (lines 17-21):

```python
_BEAM_WIND_ONLY_MESSAGE = (
    "uses the current Code_Aster wind slice: FORCE_POUTRE(TYPE_CHARGE='VENT') "
    "on beam-modeled elements only; TUYAU_3M pipe wind is not implemented, "
    "and FORCE_NODALE is not used as a production pipe-wind shortcut"
)
```

Replace the selection checks (the Task 1 version of the `if not selected:` block, plus the `bad` block after it):

```python
            if not selected:
                if field_record.quantity == "wind":
                    errors.append(f"{label} {_BEAM_WIND_ONLY_MESSAGE}; selected no beam-modeled elements.")
                elif field_record.quantity == "line_load":
                    errors.append(f"{label} selects no pipe or beam elements.")
                else:
                    errors.append(f"{label} selects no pipe elements.")
                continue
            if field_record.quantity == "wind":
                bad = [elem.id for elem in selected if elem.type != "beam"]
                if bad:
                    errors.append(f"{label} {_BEAM_WIND_ONLY_MESSAGE}; got {bad!r}.")
                    continue
```

with:

```python
            if not selected:
                if field_record.quantity in {"wind", "line_load"}:
                    errors.append(f"{label} selects no pipe or beam elements.")
                else:
                    errors.append(f"{label} selects no pipe elements.")
                continue
```

- [ ] **Step 4: Choose the Code_Aster form for pipe wind**

In `tuba/solver/aster_loads.py`, replace `from tuba.model import LoadCase, TubaModel` with `from tuba.model import Element, LoadCase, TubaModel`. After `LineLoadGroups = ...`, add:

```python
TuyauWindRows = List[tuple[str, str, tuple[str, str, str]]]
BendFrame = Callable[[Element], tuple[Sequence[float], Sequence[float]]]
```

In `resolve_wind_field_groups`, replace:

```python
            raise ValueError(f"Operation field {index} for 'wind' selects no beam-modelized elements.")
```

with:

```python
            raise ValueError(f"Operation field {index} for 'wind' selects no pipe or beam elements.")
```

Append at the end of the file:

```python
def tuyau_wind_rows(model: TubaModel, wind_fields: WindGroups, bend_frame: BendFrame) -> TuyauWindRows:
    """Wind on TUYAU_3M pipe elements as ``(element id, NOM_PARA, FORMULE texts)``.

    Code_Aster refuses TYPE_CHARGE='VENT' on pipe elements (PIPE1_44), so the
    cross-flow rule VENT uses on beams is applied here: a constant on a straight
    pipe, a function of X, Y, Z along a bend. One row per element, because one
    FORCE_POUTRE command keeps only its last occurrence on an element.
    """
    loads: dict[str, tuple[float, float, float]] = {}
    for group_names, fx, fy, fz in wind_fields:
        for element_id in group_names:
            loads[element_id] = (fx, fy, fz)
    rows: TuyauWindRows = []
    for element_id, line_load in loads.items():
        elem = model.get_element(element_id)
        if elem.type == "pipe_bend":
            center, axis = bend_frame(elem)
            rows.append((element_id, "('X', 'Y', 'Z')", cross_flow_formula(line_load, center, axis)))
            continue
        start = np.asarray(model.nodes[elem.n1].coords, dtype=float)
        end = np.asarray(model.nodes[elem.n2].coords, dtype=float)
        fx, fy, fz = cross_flow_line_load(line_load, end - start)
        rows.append((element_id, "'X'", (f"{fx:.6E}", f"{fy:.6E}", f"{fz:.6E}")))
    return rows


def write_tuyau_wind_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    rows: TuyauWindRows,
) -> None:
    # ponytail: Code_Aster concept names cap at 8 characters, so TFX_9999 is the last
    # formula; group equal straight-pipe loads if a model ever carries 10 000 wind elements.
    for index, (_, nom_para, texts) in enumerate(rows):
        for suffix, text in zip(("X", "Y", "Z"), texts):
            w(f"TF{suffix}_{index} = FORMULE(")
            w(f"    NOM_PARA={nom_para},")
            w(f"    VALE='''{text}''',")
            w(");")
            w()

    w("# ----- Wind line loads on TUYAU pipes (VENT's cross-flow rule, applied by Tuba) -----")
    w("WIND_TUY = AFFE_CHAR_MECA_F(")
    w("    MODELE=MODELE,")
    w("    FORCE_POUTRE=(")
    for index, (element_id, _, _) in enumerate(rows):
        w("        _F(")
        w(f"            GROUP_MA='{map_name(element_id)}',")
        w(f"            FX=TFX_{index},")
        w(f"            FY=TFY_{index},")
        w(f"            FZ=TFZ_{index},")
        w("        ),")
    w("    ),")
    w(");")
    w()
```

- [ ] **Step 5: Wire `WIND_TUY` into the command file**

In `tuba/solver/aster_comm.py`:

(a) Add `tuyau_wind_rows,` after `resolve_wind_field_groups,`, and `write_tuyau_wind_load,` after `write_thermal_load,` in the `aster_loads` import.

(b) Replace the Task 1 resolution lines:

```python
        wind_fields = resolve_wind_field_groups(model, load_case)
        line_loads = resolve_line_load_groups(model, load_case)
        nodal_forces = list(getattr(load_case, "nodal_forces", []))
        has_pressure = has_pressure_load(load_case, pressure_fields)
        has_temperature = has_thermal_load(load_case, temperature_fields)
        has_wind = has_wind_load(wind_fields)
        has_line_load = bool(line_loads)
        has_nodal_forces = bool(nodal_forces)
```

with:

```python
        wind_fields = resolve_wind_field_groups(model, load_case)
        # Wind reaches Code_Aster through the command its element's modelization
        # accepts: VENT on beam-modelled elements, Tuba's cross-flow rule on
        # TUYAU_3M pipes, which refuse VENT.
        element_types = {element.id: element.type for element in model.elements}
        beam_winds = [row for row in wind_fields if beam_pipes or element_types[row[0][0]] == "beam"]
        tuyau_winds = tuyau_wind_rows(
            model,
            [row for row in wind_fields if not (beam_pipes or element_types[row[0][0]] == "beam")],
            lambda element: self._get_bend_geometry(model, element)[:2],
        )
        line_loads = resolve_line_load_groups(model, load_case)
        nodal_forces = list(getattr(load_case, "nodal_forces", []))
        has_pressure = has_pressure_load(load_case, pressure_fields)
        has_temperature = has_thermal_load(load_case, temperature_fields)
        has_wind = has_wind_load(beam_winds)
        has_tuyau_wind = bool(tuyau_winds)
        has_line_load = bool(line_loads)
        has_nodal_forces = bool(nodal_forces)
```

(c) Replace the wind block:

```python
            # ==============================================================
            # AFFE_CHAR_MECA — wind on beam-modelized pipe
            # ==============================================================
            if has_wind:
                write_wind_load(
                    w,
                    map_name=map_name,
                    wind_fields=wind_fields,
                )
```

with:

```python
            # ==============================================================
            # AFFE_CHAR_MECA_F — wind: VENT on beam-modelled elements,
            # Tuba's cross-flow rule on TUYAU_3M pipes
            # ==============================================================
            if has_wind:
                write_wind_load(
                    w,
                    map_name=map_name,
                    wind_fields=beam_winds,
                )
            if has_tuyau_wind:
                write_tuyau_wind_load(
                    w,
                    map_name=map_name,
                    rows=tuyau_winds,
                )
```

(d) Replace:

```python
            if has_wind:
                excit_entries.append("        _F(CHARGE=WIND),")
            if has_line_load:
                excit_entries.append("        _F(CHARGE=LINELOAD),")
```

with:

```python
            if has_wind:
                excit_entries.append("        _F(CHARGE=WIND),")
            if has_tuyau_wind:
                excit_entries.append("        _F(CHARGE=WIND_TUY),")
            if has_line_load:
                excit_entries.append("        _F(CHARGE=LINELOAD),")
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_operation_fields.py tests/test_wind_cross_flow.py tests/test_insulation_solver.py tests/test_code_aster_study.py tests/test_code_aster_beam_pipes.py tests/test_validation.py tests/test_schema.py -q`
Expected: all pass. The existing beam wind test `test_wind_field_exports_for_beam_modelized_pipe_sections_only` must pass unchanged; it pins the byte-identical `VENT` output.

- [ ] **Step 7: Add the real Code_Aster wind references and run them**

Append to `tests/test_code_aster_line_loads.py`:

```python
def straight_model(name: str) -> tuple[Model, tuple[str, str]]:
    """A 4 m straight along X, anchored at both ends."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    end = model.add_node([RUN_LENGTH, 0.0, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=end, section="Pipe", material="Steel")
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model, (start, end)


def solve_wind(build, name: str, direction: list[float], modelization: str) -> list[float]:
    model, anchors = build(f"{name} {modelization}")
    # 10 kPa on the 0.1 m pipe is 1000 N/m head-on.
    model.define_operation("Wind", gravity=False).add_field("wind", 10000.0, direction=direction)
    root = Path(f".build/line-load-references/{name}-{modelization}").resolve()
    run = model.solve("Wind", pipe_modelization=modelization, work_dir=str(root), force=True)
    return reaction_total(run, anchors)


def test_tuyau_wind_matches_beam_vent_on_an_oblique_straight():
    angle = math.radians(30.0)
    direction = [math.cos(angle), math.sin(angle), 0.0]
    tuyau = solve_wind(straight_model, "wind-oblique", direction, "TUYAU_3M")
    beam = solve_wind(straight_model, "wind-oblique", direction, "POU_D_T")
    # Across the axis only, scaled once more by sin(30): 1000 * 0.25 * 4 m = 1000 N in +Y.
    expected = [0.0, -1000.0, 0.0]
    print(f"oblique wind: TUYAU {tuyau}, POU_D_T {beam}, expected {expected}")
    assert beam == pytest.approx(expected, abs=1.0)
    assert tuyau == pytest.approx(expected, abs=1.0)


def test_tuyau_wind_matches_beam_vent_along_an_elbow():
    tuyau = solve_wind(elbow_model, "wind-elbow", [0.0, -1.0, 0.0], "TUYAU_3M")
    beam = solve_wind(elbow_model, "wind-elbow", [0.0, -1.0, 0.0], "POU_D_T")
    # The 4 m run takes 1000 N/m head-on; the elbow carries (R/3, -2R/3) x 1000 N.
    expected = [-1000.0 * BEND_RADIUS / 3.0, 1000.0 * (RUN_LENGTH + 2.0 * BEND_RADIUS / 3.0), 0.0]
    print(f"elbow wind: TUYAU {tuyau}, POU_D_T {beam}, expected {expected}")
    assert beam == pytest.approx(expected, rel=2e-3, abs=1.0)
    assert tuyau == pytest.approx(beam, rel=2e-3, abs=1.0)


def test_wind_and_line_load_on_one_elbow_add_up():
    model, anchors = elbow_model("wind-plus-line-load TUYAU_3M")
    operation = model.define_operation("Both", gravity=False)
    operation.add_field("wind", 10000.0, direction=[0.0, -1.0, 0.0])
    operation.add_field("line_load", 1000.0, direction=[0.0, 0.0, -1.0])
    root = Path(".build/line-load-references/wind-plus-line-load-TUYAU_3M").resolve()
    run = model.solve("Both", pipe_modelization="TUYAU_3M", work_dir=str(root), force=True)
    observed = reaction_total(run, anchors)
    expected = [
        -1000.0 * BEND_RADIUS / 3.0,
        1000.0 * (RUN_LENGTH + 2.0 * BEND_RADIUS / 3.0),
        1000.0 * (RUN_LENGTH + BEND_LENGTH),
    ]
    print(f"wind + line load: reactions {observed}, expected {expected}")
    assert observed == pytest.approx(expected, rel=2e-3, abs=1.0)
```

Run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_code_aster_line_loads.py -q -s
```

Expected: `5 passed` (not skipped). The oblique straight prints about [0, −1000, 0] for both modelizations. The elbow prints about [−166.7, 4333.3, 0] for both; the planning spike measured TUYAU_3M at (−166.6, +333.2) for the elbow alone. If a TUYAU/POU_D_T comparison misses its tolerance, stop and report the printed numbers. Do not loosen the tolerance.

- [ ] **Step 8: Document pipe wind**

In `docs/architecture/library-architecture-review.md`, replace:

```
Wind fields are currently limited to beam-modeled elements because the writer
uses `FORCE_POUTRE(TYPE_CHARGE='VENT')`; `TUYAU_3M` pipe wind and nodal-load
shortcuts are rejected before export.
```

with:

```
Wind fields load pipe and beam elements. Beam-modelled elements use
`FORCE_POUTRE(TYPE_CHARGE='VENT')`. Code_Aster refuses `VENT` on `TUYAU_3M`
elements, so there Tuba applies VENT's cross-flow rule itself and writes a plain
`FORCE_POUTRE`: a constant on a straight pipe, a function of X, Y, Z on a bend.
```

In the command-map row, replace `beam-modeled wind through `FORCE_POUTRE(TYPE_CHARGE='VENT')`, line loads` with `beam-modeled wind through `FORCE_POUTRE(TYPE_CHARGE='VENT')`, `TUYAU_3M` wind through a plain `FORCE_POUTRE` carrying the same cross-flow rule, line loads`.

Replace the wind paragraph:

```
Wind is deliberately narrow today. Code_Aster U4.44.01 documents
`FORCE_POUTRE(TYPE_CHARGE='VENT')` for beam modelizations; Tuba emits
`AFFE_CHAR_MECA_F` with constant `FORMULE` concepts for the wind components
because the current runtime accepts function/formula values for this VENT path.
The same command page documents `FORCE_TUYAU` with pressure (`PRES`) for
`TUYAU_3M` / `TUYAU_6M`, not as a wind line-load command, so Tuba rejects
`TUYAU_3M` wind rather than approximating it with `FORCE_NODALE`.
```

with:

```
Wind follows the element's modelization. Code_Aster U4.44.01 documents
`FORCE_POUTRE(TYPE_CHARGE='VENT')` for beam modelizations; Tuba emits
`AFFE_CHAR_MECA_F` with constant `FORMULE` concepts for those wind components.
`TUYAU_3M` elements accept a plain `FORCE_POUTRE` but refuse `VENT`
(`<EXCEPTION> <PIPE1_44>`), so Tuba applies VENT's rule itself in a separate
`WIND_TUY` load: only the part of the wind across the pipe axis, scaled once
more by the sine of the angle between wind and axis. That is a constant on
straight pipes and a `FORMULE` of X, Y, Z along bends.
`tests/test_code_aster_line_loads.py` solves both against POU_D_T `VENT` on an
oblique straight and an elbow. Line loads use a plain `FORCE_POUTRE` in their
own `LINELOAD` load. Within one `AFFE_CHAR_MECA`, Code_Aster keeps only the last
`FORCE_POUTRE` occurrence on an element, so each element gets one row and each
kind of load its own concept. No `FORCE_NODALE` shortcut is used for either.
```

Replace the inventory bullet:

```
- Beam-modeled wind fields compiled into `FORCE_POUTRE(TYPE_CHARGE='VENT')`
  with constant `FORMULE` components; `TUYAU_3M` wind and `FORCE_NODALE` wind
  shortcuts are not implemented.
```

with:

```
- Wind fields compiled by modelization: `FORCE_POUTRE(TYPE_CHARGE='VENT')` on
  beam-modelled elements and a plain `FORCE_POUTRE` with VENT's cross-flow rule
  on `TUYAU_3M` pipes and bends; no `FORCE_NODALE` shortcut.
```

Replace the gaps row:

```
| Wind beyond beam-modeled elements | Wind currently works only for beam-modeled elements that can use `FORCE_POUTRE(TYPE_CHARGE='VENT')`. `TUYAU_3M` wind is rejected, and `FORCE_NODALE` is not used as a production pipe-wind shortcut. | Extend only when the chosen Code_Aster pipe modelization has a documented distributed-load command. |
```

with:

```
| Distributed loads on volume and mixed studies | 1D pipes and beams take wind and line loads under `TUYAU_3M` and `POU_D_T`. Pipe-volume studies refuse both, and the STEP mixed exporter writes no loads at all. | Apply wind and line loads to the 3D outer skin (`FORCE_FACE` on `G_OUTER_*`), checked against the 1D total reaction. |
```

In `CONTEXT.md`, replace:

```
**Line load**:
A force per metre of pipe or beam along one fixed global direction, carried in full whatever the element's orientation.
_Avoid_: Distributed wind, nodal force
```

with:

```
**Line load**:
A force per metre of pipe or beam along one fixed global direction, carried in full whatever the element's orientation.
_Avoid_: Distributed wind, nodal force

**Wind load**:
Wind pressure on a pipe's exposed diameter; only the part crossing the pipe's axis loads it, reduced once more by the sine of the angle between wind and axis.
_Avoid_: Line load
```

- [ ] **Step 9: Run the full suite**

Run (about 20 minutes; run it in the background):
`& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest -q`
Expected: no failures other than the two `tests/test_package_release.py` vite build tests that fail only in fresh worktrees.

- [ ] **Step 10: Commit**

```powershell
git -C D:\tmp\tuba-line-loads add tuba/model.py tuba/validation.py tuba/solver/aster_loads.py tuba/solver/aster_comm.py tests/test_operation_fields.py tests/test_code_aster_line_loads.py docs/architecture/library-architecture-review.md CONTEXT.md
git -C D:\tmp\tuba-line-loads commit -m "feat(solver): apply wind to TUYAU_3M pipes with VENT's cross-flow rule" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## After the plan

- The next slice is the 3D surface realization: `FORCE_FACE` on `G_OUTER_*` in `tuba/solver/aster_volume.py`, checked against these 1D reaction totals. It gets its own plan.
- The uncommitted generalized-fields change in the main tree edits the same files (`aster_loads.py`, `aster_comm.py`, `validation.py`, `model.py`, `schema.py`). Decide whether to discard or rebase it before this branch merges.
