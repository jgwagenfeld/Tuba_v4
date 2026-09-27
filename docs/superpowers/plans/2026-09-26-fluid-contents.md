# Fluid Contents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Preserve native implementation in this session; use one fresh reviewer at the end.

**Goal:** Define empty, operating-fluid and hydrotest contents independently of pressure, calculate their masses, and qualify their Code_Aster gravity response.

**Architecture:** Add `fluid_density` to existing operation fields and reuse their selection, serialization and identity mechanisms. Resolve contents once per batch in `tuba/physical.py`, then reuse the compiler's insulation density override. Keep report masses as model inputs and imported solver results as a separate source.

**Tech Stack:** Existing Python, dataclasses, NumPy, pytest, external-process Code_Aster, and the existing web-scene/report exporters. No new dependencies.

**Spec:** [Approved design](../specs/2026-09-26-fluid-contents-design.md).

**Status:** Implemented and solver-qualified, 2026-09-26. Regression checks and independent review passed. Browser visual inspection remains policy-blocked; see the evidence and limitation below.

## Global Constraints

- Work only in `D:/Gitprojects/Tuba_v4/.worktrees/fluid-contents`, branch `codex/fluid-contents`, based on reliability milestone `ca17624`.
- Existing models remain empty by default. Density and pressure are independent.
- This package supports fully filled 1D straight pipes and bends in `TUYAU_3M` and `POU_D_T`.
- It does not add partial filling, free surfaces, fluid dynamics, pressure head, material curves, reducers, native solids or nonlinear contact histories.
- Existing formulation restrictions remain: `POU_D_T` rejects internal pressure; pressurized hydrotest evidence therefore uses `TUYAU_3M`.
- No automatic element splitting. Whole-element station selection uses the existing 1e-9 m endpoint tolerance.
- Authored Python must never be rewritten. Old empty load-case JSON and generated calls stay unchanged.
- New dataclass fields are appended with defaults to preserve existing constructor calls.
- No global caches, fluid object hierarchy, new visualization surface or general preflight framework.
- Missing Code_Aster fails loudly before result publication. Required real references must pass with zero skips.
- No merge, push or publication is part of this package. Preserve unrelated work in shared checkouts.

## Review Focus

1. Mutated/deserialized fields, including booleans and finite inputs whose products overflow, must fail before solver writes (Tasks 1 and 2).
2. An all-pipes selection must exclude structural members, while an explicit mixed group must reject; equal overlapping densities count once (Task 1).
3. Forced project solves and histories with fluid only in an earlier/repeated stage must preserve existing evidence and staging on rejection (Task 2).
4. Two pipes sharing one material but carrying different fluids must retain distinct masses and unchanged stiffness (Tasks 2 and 3).
5. An unselected fluid operation must not prevent an otherwise supported empty study, and old dry model identities/compiler bytes must remain stable (Tasks 1 and 2).

## Execution environment and file ownership

Run all commands from the fluid-contents worktree. In each PowerShell test process:

```powershell
$env:UV_NO_SYNC='1'
$env:UV_PROJECT_ENVIRONMENT='D:\Gitprojects\Tuba_v4\.venv'
$env:PYTHONPATH=(Get-Location).Path
```

Use existing test helpers where their geometry matches; independent expected mass and reaction formulas must not call the new physical helpers. Add focused cases to existing owning suites rather than creating competing harnesses.

| Owner | Responsibility |
| --- | --- |
| `tuba/model.py`, `tuba/validation.py`, `tuba/schema.py` | Field construction, selection, strict admission and persistence |
| `tuba/project/script.py` | Generated legacy load-case field replay; preserve authored files |
| `tuba/physical.py`, `tuba/quantities.py` | One contents calculation and batch takeoff |
| `tuba/solver/aster_comm.py` | Per-element density overrides |
| `tuba/solver/compiler_contract.py`, `aster.py`, `aster_volume.py`, `mixed_study.py`, `aster_contact.py` under `tuba/solver/` | Existing compilation/preflight boundaries |
| `tuba/project/solve.py` | Preflight all selected cases before forced staging replacement |
| `tuba/reporting/tables.py` | Model-source operation mass table |
| `examples/fluid_contents.py` | Procedural real-solver example |
| `tests/test_fluid_contents.py`, `tests/test_code_aster_fluid_contents.py` | Portable contents regression and mandatory real references |
| `scripts/check_code_aster_references.py` | Include the new real reference file in the existing gate |

Do not change provenance code unless a failing test proves the existing resolved-field projection omits a required dependency. Do not change frontend code: this adds a table through the existing registry.

### Task 1: Admission, persistence and quantities

**Files:** Modify `tuba/model.py` (`Operation.add_field`, `define_load_case`, `define_operation`, `resolve_operation_field_elements`, `to_dict`, `from_dict`), `tuba/validation.py` (`operation_field_problem`, `operation_fields_problem`, `_validate_operation_fields`), `tuba/schema.py` (operation-field enum), `tuba/project/script.py` (load-case writer), `tuba/physical.py`, and `tuba/quantities.py`. Create `tests/test_fluid_contents.py`; extend `tests/test_model_script.py` for authored-file protection.

**Interfaces:**

```python
# Existing public functions gain only this keyword-only option.
physical_properties_for_element(model, element, *, operation: str | None = None) -> ElementPhysicalProperties
element_quantities(model, element, *, operation: str | None = None) -> ElementQuantities
quantity_takeoff(model, *, operation: str | None = None) -> QuantityTakeoff

# Existing define_load_case gains trailing fields=None, matching define_operation.
# Existing operation_field_problem / operation_fields_problem remain validation owners.
# Private helpers in physical.py, consumed by takeoff and the compiler:
_fluid_density_by_element(model: TubaModel, case: LoadCase | None) -> dict[str, float]
_physical_properties_for_element(model: TubaModel, elem: Element, fluid_density: float) -> ElementPhysicalProperties
_element_quantities(model: TubaModel, elem: Element, props: ElementPhysicalProperties) -> ElementQuantities
```

Public functions resolve an explicit case name with `model.resolve_load_case(operation)`; `None` passes no case and remains dry. The density resolver validates fields through `operation_fields_problem`, selects each field once, and assigns by element ID. Identical overlaps overwrite with the same value; conflicts have already failed validation. The calculation helper is the existing physical calculation extended with contents, not a second formula implementation.

- [x] **1. Write the failing public mass and admission checks.** Put the following procedural helper and tests in `tests/test_fluid_contents.py`:

```python
import math
import pytest
from tuba import Model
from tuba.model import OperationField
from tuba.physical import physical_properties_for_element, element_quantities
from tuba.quantities import quantity_takeoff


def contents_model(*, bent=False, insulated=True):
    model = Model('FluidContents')
    model.add_material('Steel', E=2e11, nu=0.3, rho=7850)
    model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
    with model.pipe('Pipe', 'Steel', route='P-100') as pipe:
        pipe.start([0, 0, 0], support='anchor')
        pipe.run(2.0)
        if bent:
            pipe.bend(radius=0.5, angle=90, plane='XY')
            pipe.run(1.0)
    if insulated:
        model.add_insulation_spec('wool', material='mineral wool',
                                  thickness_m=0.02, density_kg_m3=100)
        for element in model.elements:
            model.assign_insulation(f'element:{element.id}', 'wool')
    return model


@pytest.mark.parametrize('bent', [False, True])
@pytest.mark.parametrize('density', [0.0, 800.0, 1000.0])
def test_contents_mass_is_independent_and_dry_default_is_preserved(bent, density):
    model = contents_model(bent=bent)
    model.define_operation('Filled', gravity=False).add_field(
        'fluid_density', density, route_id='P-100')
    length = 3 + math.pi / 4 if bent else 2.0
    pipe_mass = math.pi / 4 * (0.1**2 - 0.08**2) * 7850 * length
    insulation_mass = math.pi / 4 * (0.14**2 - 0.1**2) * 100 * length
    fluid_mass = math.pi / 4 * 0.08**2 * density * length
    wet = quantity_takeoff(model, operation='Filled')
    dry = quantity_takeoff(model)
    for key, expected in [('pipe_mass_kg', pipe_mass),
                          ('insulation_mass_kg', insulation_mass),
                          ('fluid_mass_kg', fluid_mass),
                          ('total_mass_kg', pipe_mass + insulation_mass + fluid_mass)]:
        assert wet.totals[key] == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert dry.totals['fluid_mass_kg'] == 0
    assert 'operation' not in dry.to_dict()
    assert wet.to_dict()['operation'] == 'Filled'
    for element in model.elements:
        before = physical_properties_for_element(model, element)
        after = physical_properties_for_element(model, element, operation='Filled')
        assert after.metal_area_m2 == before.metal_area_m2
        assert after.wind_diameter_m == before.wind_diameter_m
        assert after.effective_radius_m == before.effective_radius_m
        assert after.fluid_density_kg_m3 == density
        assert element_quantities(model, element, operation='Filled').fluid_mass_kg >= 0


@pytest.mark.parametrize('value', [True, False, '800', None, 1+0j,
                                  -1, float('nan'), float('inf')])
def test_invalid_density_is_not_coerced(value):
    model = contents_model()
    operation = model.define_operation('Bad')
    with pytest.raises(ValueError, match='fluid_density'):
        operation.add_field('fluid_density', value)
    operation.fields[:] = [OperationField(quantity='fluid_density', value=value)]
    with pytest.raises(ValueError, match='fluid_density'):
        model.validate()
    with pytest.raises(ValueError, match='fluid_density'):
        quantity_takeoff(model, operation='Bad')
```

- [x] **2. Run the first red check.** `uv run python -m pytest tests/test_fluid_contents.py -q`. Expect failures for the missing operation keyword and absent strict density admission, not import/setup errors.
- [x] **3. Implement strict construction and selection.** Keep `_number` in `validation.py` as the strict finite-real check. Factor current `Operation.add_field` record creation into one private model helper used by both operation construction and `define_load_case(fields=...)`; it must reject invalid density before `float` conversion. Keep other quantities' existing behavior. Revalidate mutable records through `operation_field_problem` and include both named case dictionaries in `_validate_operation_fields`.

For fluid fields accept only uniform `all/group/route/elements`, with at most one nonempty selector family. Reject explicit scope/selector conflicts, node IDs, direction and non-route stations. Extend whole-element station checking without adding fluid to the set that allows beam loads. For `all`, filter to `pipe_straight`/`pipe_bend`; for explicit scopes reject every selected non-pipe and every missing element. Require `PipeSection` and nonempty selection. Use the existing overlap owner for equal-versus-conflicting densities, independent of gravity.

- [x] **4. Implement the shared mass calculation and append defaulted fields.** The calculation is:

```python
bore_area = math.pi * (section.OD - 2 * section.WT)**2 / 4
fluid_mass = fluid_density * bore_area
mass = pipe_mass + insulation_mass + fluid_mass
```

Only pipe elements with `PipeSection` acquire contents; other elements have fluid mass zero. Corrosion allowance does not alter this nominal bore. Check finiteness of bore, per-length components, effective density and length-multiplied masses, converting arithmetic overflow into a contextual `ValueError`. Append the three physical fields and `ElementQuantities.fluid_mass_kg` with zero defaults. Add defaulted `QuantityRecord.pipe_mass_kg`/`fluid_mass_kg` and `QuantityTakeoff.operation`; sum them in existing total/group owners. Resolve the density map outside the takeoff loop, and pass computed properties to `_element_quantities`.

- [x] **5. Pin selector and overlap edge cases.** Extend the new test file with the following test and cases:

```python
def test_equal_overlaps_apply_once_and_conflicts_fail_without_gravity():
    model = contents_model()
    case = model.define_operation('Filled', gravity=False)
    case.add_field('fluid_density', 800, route_id='P-100')
    duplicate = case.add_field('fluid_density', 800,
                               element_ids=[model.elements[0].id])
    expected = math.pi * 0.08**2 / 4 * 800 * 2
    assert quantity_takeoff(model, operation='Filled').totals['fluid_mass_kg'] == pytest.approx(expected)
    duplicate.value = 1000
    with pytest.raises(ValueError, match='overlapping incompatible'):
        quantity_takeoff(model, operation='Filled')


@pytest.mark.parametrize('selectors', [
    {'route_id': 'P-100', 'element_ids': ['missing']},
    {'node_ids': ['missing']},
    {'direction': [0, 0, -1]},
    {'station_start': 0, 'station_end': 2},
    {'route_id': 'P-100', 'station_start': 0.5, 'station_end': 2},
    {'route_id': 'P-100', 'profile': 'linear'},
    {'element_ids': ['missing']},
])
def test_unsupported_selection_never_silently_changes_meaning(selectors):
    model = contents_model()
    with pytest.raises(ValueError):
        model.define_operation('Bad').add_field('fluid_density', 800, **selectors)
        model.validate()
```

Also pin complete spans ending at `2 + 5e-10` as admitted, `2 - 1e-5` as a rejected cut, all-pipes excluding a structural beam, mixed explicit groups rejecting that same beam, empty groups, missing routes and unknown operation names. Use two route runs to ensure a boundary selects one element rather than its neighbor. Set a selected pipe to a non-pipe section and reject. Use a normal 2 m pipe with `OD=10`, `WT=1`, density `1e308` to exercise finite-input multiplication overflow, without invalid geometry or an infinite input masking it.

- [x] **6. Preserve JSON and script replay.** Add `fluid_density` to the schema enum. Emit legacy `fields` only when nonempty; reconstruct through the same field path. Add a `fields=...` suffix to generated `define_load_case` calls only when needed. Pin replay using:

```python
def test_legacy_and_operation_fields_survive_json_and_generated_python():
    from tuba.project.script import generate_model_script
    model = contents_model()
    model.define_load_case('Empty')
    model.define_load_case('Legacy', fields=[{
        'quantity': 'fluid_density', 'value': 800, 'route_id': 'P-100'}])
    model.define_operation('Hydro').add_field('fluid_density', 1000)
    data = model.to_dict()
    assert 'fields' not in data['load_cases']['Empty']
    restored = Model.from_dict(data)
    namespace = {'__name__': 'fluid_replay'}
    exec(compile(generate_model_script(restored), 'model.py', 'exec'), namespace)
    assert namespace['model'].to_dict() == restored.to_dict() == data
```

Extend existing authored-project tests with an authored file containing the same three states; reload it, verify quantities and byte-for-byte original file content after the existing refused generated-write operation.

- [x] **7. Run the portable owning suites and commit Task 1.**

```powershell
uv run python -m pytest tests/test_fluid_contents.py tests/test_operation_fields.py tests/test_model_script.py tests/test_insulation_solver.py -q
git add tuba/model.py tuba/validation.py tuba/schema.py tuba/project/script.py tuba/physical.py tuba/quantities.py tests/test_fluid_contents.py tests/test_model_script.py
git commit -m "feat: model operation-specific fluid contents and quantities"
```

Expected: portable tests pass; real insulation test can skip in this portable run only. Record the actual result before marking this task done.

### Task 2: Compiler, preflight and evidence identity

**Files:** Modify the existing solver/preflight owners listed in the ownership table and `tuba/project/solve.py` only where the boundary requires it. Extend `tests/test_fluid_contents.py`, `tests/test_export_validation.py`, `tests/test_project_solve.py`, and `tests/test_solver_input_provenance.py`.

**Interfaces:** Consume Task 1's density resolver and physical calculation. Keep public solver signatures unchanged. Use existing `analysis_study_inputs`, `volume_study_inputs`, `beam_contract`, `validate_path`, and project `expected_identity` as the side-effect-free owners. Keep the source model/material immutable.

- [x] **1. Write a failing compiler isolation check.**

```python
def test_compiler_assigns_contents_per_element_without_mutating_material(tmp_path):
    from tuba.solver.aster import CodeAsterSolver
    model = contents_model(insulated=False)
    with model.pipe('Pipe', 'Steel', route='P-200') as pipe:
        pipe.start([0, 2, 0], support='anchor')
        pipe.run(2)
    case = model.define_operation('Filled')
    case.add_field('fluid_density', 800, route_id='P-100')
    case.add_field('fluid_density', 1000, route_id='P-200')
    before = model.to_dict()
    CodeAsterSolver().export_study(model, 'Filled', tmp_path)
    comm = (tmp_path / 'study.comm').read_text()
    area = math.pi / 4 * (0.1**2 - 0.08**2)
    for density in (800, 1000):
        effective = 7850 + density * math.pi / 4 * 0.08**2 / area
        assert f'RHO={effective:.12E}' in comm
    assert model.to_dict() == before
```

Run `uv run python -m pytest tests/test_fluid_contents.py -q`; expect missing effective densities.

- [x] **2. Extend the existing insulation override.** Resolve the selected case's density map once before iterating elements in `aster_comm.py`. Visit an element if it has insulation or assigned nonzero contents; compute the combined mass through Task 1. Preserve the existing positive insulation-density gravity guard. Emit one per-element material override with original E, nu and alpha and `RHO=props.mass_kg_per_m / props.metal_area_m2`. Keep existing variable names/order/comments for no-fluid models. Use existing gravity loading exactly once; no new contents nodal loads.
- [x] **3. Add rejection tests before changing preflight.** For each diagnostic/full/volume/mixed/Model.solve boundary, snapshot a directory containing `study.comm`, `study.mail` and a sentinel; invoke an unsupported selected fluid field with densities both zero and positive; assert `ValueError` mentioning contents/fluid and exact directory byte equality. For a fresh path assert the path remains absent. Use existing volume/mixed fixtures so missing CAD or section prerequisites cannot be the reason for passing. Pin overflow on the ordinary diagnostic and full exporters too.

For project solves, extend the current `force=True` rejection test with contents in a SOLID_3D selected operation; seed both evidence and `.tuba/staging` sentinels and assert they remain unchanged. For contact paths, use the existing shoe fixture with fluid only in the first stage, then a repeated first/final stage; both must reject before writes. Also test a single selected contact case without `load_path`.

- [x] **4. Route guards through existing owners.** Validate derived masses during side-effect-free beam input resolution, before any file allocation. Make diagnostic export obtain that same preflight before its `mkdir`/writers. Reject a selected fluid field, including explicit zero, before volume geometry construction and before mixed export's root creation. Check all selected contact/history cases, preserving existing thermal/pressure rules. For project solves compute every selected operation's `expected_identity` before entering the claim/staging mutation block, even with `force=True`, and reuse those identities for the existing evidence verdict. This makes the existing exporter contracts own the checks; do not duplicate their contents/formulation policy in the project layer.
- [x] **5. Pin identity and dry compatibility.** Test separate changes to density, scope, selected group membership, nominal bore and selected case. Each must change `build_solver_input_identity(...).fingerprint`; an attested real fixture mutated this way must fail the existing evidence reuse/verdict path. Use the established provenance fixture machinery; do not invent solver output. Verify an unselected valid fluid operation does not block a supported empty volume/mixed selection.

The following baseline was captured from `b8bc0b5` before product changes on 2026-09-26. Add this permanent regression for `tests/fixtures/pre_operation_model.json`:

```python
def test_pre_contents_model_keeps_canonical_inputs_script_and_compiler(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    from tuba.project.script import generate_model_script
    from tuba.solver.aster import CodeAsterSolver
    from tuba.analysis.provenance import build_solver_input_identity
    model = Model.from_dict(json.loads(Path('tests/fixtures/pre_operation_model.json').read_text()))
    canonical = json.dumps(model.to_dict(), sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(canonical).hexdigest() == '079723f441084622c16582f7f1bd99922a096df084567e612966be7a709f7838'
    assert hashlib.sha256(generate_model_script(model).encode()).hexdigest() == 'ab29cffcc7d5c81f86ec479cbdd3c3c3a6f63e9ae332f5ca8c6cc0462baf7751'
    CodeAsterSolver().export_study(model, 'Hot', tmp_path)
    text = (tmp_path / 'study.comm').read_text().replace('\r\n', '\n').encode()
    assert hashlib.sha256(text).hexdigest() == '9767c67601af67b4ba119c9e920cbd5dae798ec883f23144d38483884b4f8884'
    assert build_solver_input_identity(model, 'Hot').fingerprint == 'c67e5e0fee6c935b961c85cc38a51ccdc39aad418616f418b087af91d44e5ed8'
```

If a mismatch is intentional, investigate and document the exact semantic change before deciding whether a compiler/schema identity bump is necessary. Do not simply regenerate expectations.

- [x] **6. Run the owning regressions and commit Task 2.**

```powershell
uv run python -m pytest tests/test_fluid_contents.py tests/test_export_validation.py tests/test_project_solve.py tests/test_solver_input_provenance.py tests/test_insulation_solver.py tests/test_operation_fields.py -q
git add tuba/solver/aster_comm.py tuba/solver/compiler_contract.py tuba/solver/aster.py tuba/solver/aster_volume.py tuba/solver/mixed_study.py tuba/solver/aster_contact.py tuba/project/solve.py tests/test_fluid_contents.py tests/test_export_validation.py tests/test_project_solve.py tests/test_solver_input_provenance.py
git commit -m "feat: compile fluid weight with fail-before-write preflight"
```

Stage only files actually changed. Expected: all portable checks pass; no baseline changes and no evidence/staging side effects on rejected inputs.

### Task 3: Reports, example and real Code_Aster qualification

**Files:** Modify `tuba/reporting/tables.py` and `scripts/check_code_aster_references.py`. Create `examples/fluid_contents.py` and `tests/test_code_aster_fluid_contents.py`; extend `tests/test_fluid_contents.py` and the existing report expectations only where the added input table requires it.

**Interfaces:** Add `build_operation_quantities_table(model: TubaModel) -> ReportTable` to `MODEL_TABLE_BUILDERS`, ID `operation_quantities`, source `model`. Consume `quantity_takeoff(model, operation=name)` and existing `build_engineering_review`, `write_engineering_review`, `SceneRequest`, `build_visualization_scene`, `write_scene_bundle`. No new result contract.

- [x] **1. Pin the model-source report before implementation.**

```python
def test_operation_quantities_are_model_inputs():
    from tuba.reporting.tables import build_model_tables
    model = contents_model()
    model.define_load_case('Empty', gravity=False)
    model.define_operation('Operating').add_field('fluid_density', 800)
    table = next(table for table in build_model_tables(model)
                 if table.id == 'operation_quantities')
    assert table.source == 'model'
    rows = {row['name']: row for row in table.rows}
    assert rows['Empty']['fluid_mass_kg'] == 0
    assert rows['Empty']['gravity'] is False
    assert rows['Operating']['fluid_mass_kg'] == pytest.approx(math.pi * 0.08**2 / 4 * 800 * 2)
    for row in rows.values():
        assert row['total_mass_kg'] == pytest.approx(
            row['pipe_mass_kg'] + row['insulation_mass_kg'] + row['fluid_mass_kg'])
    empty_table = next(table for table in build_model_tables(Model('Empty'))
                       if table.id == 'operation_quantities')
    assert not empty_table.rows
```

Run this test red, then implement the table in the existing registry with columns `name`, `gravity`, `pipe_mass_kg`, `insulation_mass_kg`, `fluid_mass_kg`, `total_mass_kg`. One row for every named operation/load case; no invented default case. Ensure CSV/JSON report export includes the table through existing generic exporters.

- [x] **2. Write the mandatory real matrix using the Task 1 procedural helper.** No skip conditions other than the existing `TUBA_RUN_CODE_ASTER_INTEGRATION != '1'` portable-suite marker. Runtime selection is `os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto')`, never hardcoded WSL. Use per-case `tmp_path` work directories.

```python
import math
import os
import pytest
from tests.test_fluid_contents import contents_model

pytestmark = pytest.mark.skipif(
    os.environ.get('TUBA_RUN_CODE_ASTER_INTEGRATION') != '1',
    reason='real Code_Aster required')


@pytest.mark.parametrize('formulation', ['TUYAU_3M', 'POU_D_T'])
@pytest.mark.parametrize('bent', [False, True])
@pytest.mark.parametrize('insulated', [False, True])
def test_contents_gravity_matrix(tmp_path, formulation, bent, insulated):
    model = contents_model(bent=bent, insulated=insulated)
    fixed, tip = model.elements[0].n1, model.elements[-1].n2
    area = math.pi / 4 * (0.1**2 - 0.08**2)
    bore = math.pi / 4 * 0.08**2
    dry = 7850 * area + (100 * math.pi / 4 * (0.14**2 - 0.1**2) if insulated else 0)
    length = 3 + math.pi / 4 if bent else 2
    ix = 4.75 + math.pi / 2 if bent else 2
    iy = 0.75 + math.pi / 8 if bent else 0
    inertia = math.pi / 64 * (0.1**4 - 0.08**4)
    empty_displacement = None
    for density in (0, 800, 1000):
        name = f'Density{density}'
        model.define_operation(name, gravity=True).add_field('fluid_density', density)
        run = model.solve(operation=name, pipe_modelization=formulation,
                          work_dir=str(tmp_path / name),
                          exec_method=os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto'))
        reaction = run.results.node_results[fixed].reaction_force
        q = (dry + density * bore) * 9.81
        tolerance = 5e-3 if bent else 1e-5
        assert reaction[2] == pytest.approx(q * length, rel=tolerance, abs=1e-6)
        assert reaction[3] == pytest.approx(q * iy, rel=tolerance, abs=1e-6)
        assert reaction[4] == pytest.approx(-q * ix, rel=tolerance, abs=1e-6)
        if not bent:
            displacement = abs(run.results.node_results[tip].displacement[2])
            assert displacement == pytest.approx(q * length**4 / (8 * 2e11 * inertia), rel=0.03)
            if density == 0:
                empty_displacement = displacement
            else:
                assert displacement / empty_displacement == pytest.approx(
                    (dry + density * bore) / dry, rel=1e-3)
```

This is 24 actual solves across eight pytest cases. `NodeResult.displacement` is the existing six-component imported vector in `tuba/solver/base.py`; use its translation at index 2, not a separately calculated substitute.

- [x] **3. Add the independent isolation/reference cases.** Use these fixed assertions in additional real tests:

```python
# Gravity disabled, downward 100 N tip load, each formulation, densities 0 and 1000:
expected_tip = 100 * 2**3 / (3 * 2e11 * (math.pi / 64 * (0.1**4 - 0.08**4)))
assert reaction[2] == pytest.approx(100, rel=1e-5, abs=1e-6)
assert reaction[4] == pytest.approx(-200, rel=1e-5, abs=1e-6)
assert abs(tip_displacement[2]) == pytest.approx(expected_tip, rel=0.03)
# Compare the two imported displacements directly at rel=1e-6 too.

# Two independent 2 m cantilevers sharing Steel, fluid densities 800 and 1000:
for density, reaction in reactions_by_density.items():
    expected_weight = (7850 * math.pi / 4 * (0.1**2 - 0.08**2)
                       + density * math.pi / 4 * 0.08**2) * 2 * 9.81
    assert reaction[2] == pytest.approx(expected_weight, rel=1e-5, abs=1e-6)
```

For TUYAU add gravity-only and 1.5e6 Pa pressurized cases at densities 0 and 1000 on the same straight route: vertical reaction and bending moment must match the independent weight formulas; compare the pressure-induced axial displacement increment across densities to prove the two inputs remain independent. Retain a portable assertion that POU_D_T rejects that pressure. Use `add_nodal_force` and existing result accessors; preserve force signs. Do not weaken tolerances after seeing results; investigate any discrepancy in geometry, discretization, formulation or extraction first.

- [x] **4. Add the procedural example and gate entry.** `examples/fluid_contents.py` defines an insulated route using constants and builder calls, three operations (empty, 800 kg/m3 operating at 1e6 Pa, 1000 kg/m3 hydrotest at 1.5e6 Pa), and solves each with TUYAU. Build the engineering review from all returned runs and a scene from the imported result state using the existing example conventions. Write review/scene only after every solve succeeds. Add `tests/test_code_aster_fluid_contents.py` to `REFERENCE_TESTS`. Missing runtime must raise, with no manufactured result fallback.
- [x] **5. Run real qualification, the example and the full regression suite.**

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD='wsl'
$env:TUBA_RUN_CODE_ASTER_INTEGRATION='1'
uv run python -m tuba.solver.code_aster_doctor --check
uv run python -m pytest tests/test_code_aster_fluid_contents.py -q --junitxml=.build/qualification/fluid-contents.xml
uv run python -m examples.fluid_contents
uv run python scripts/check_code_aster_references.py --report .build/qualification/code-aster-references.xml
Remove-Item Env:TUBA_RUN_CODE_ASTER_INTEGRATION
uv run python -m pytest -q --junitxml=.build/qualification/python-suite.xml
```

Execute commands sequentially and inspect each exit code. The WSL setting is this developer machine's configured backend, not a test requirement. If the full suite needs viewer dependencies, reuse the main checkout's installed `viewer/node_modules` via the same ignored junction pattern as the reliability worktree. Do not resync the environment or alter main. Portable-suite optional skips are reported separately; the mandatory real gate permits none.

Inspect the example's emitted review JSON/CSV and scene manifest: three solved cases, genuine Code_Aster lineage, three mass rows, masses matching the independent values, and imported displacement/reaction data. If the added table is not exposed by the existing generic review UI, investigate that failing acceptance before calling the example complete.

- [x] **6. Commit Task 3, perform one final review, and hand off.** Stage only this task's files, commit `feat: report and qualify operation-specific fluid contents`, and build the review package against `ca17624`. Request one fresh read-only whole-branch review as required by executing-plans, with the approved spec, this plan, tests and exact qualification evidence. Fix actionable findings, rerun affected checks, and update this plan with actual results and remaining limitations. Do not rerun the entire gate without a relevant code/test change or unresolved concern. Leave the branch ready for review; do not merge or push.

## Self-review of this plan

- Admission/scopes/overlap/mutation, legacy persistence, dry defaults and quantities map to Task 1.
- Compiler mass/stiffness isolation, unsupported combinations, overflow before writes, forced staging protection, evidence identity and baseline compatibility map to Task 2.
- Input table, procedural real-solver example, fixed numerical matrix, mandatory gate and final review map to Task 3.
- All five Review Focus conditions have named checks in their owning tasks. The physical formula is shared; numerical expected values remain independent.
- The four dry compatibility hashes above were measured before product implementation. They are compatibility evidence only, not proof of fluid functionality.
- Execution will record actual outcomes; unchecked items and planned commands do not claim implementation or solver verification.


## Final execution record

- Implementation commits: `e6aab55` (fields/persistence/quantities), `6113c3d`
  (compiler/preflight), `816da68` (reports/example/reference gate plus final boundary checks).
- Portable owning suites: Task 1 97 passed / 1 optional integration skip / 5 subtests;
  Task 2 189 passed / 3 optional integration skips / 5 subtests; report/quantity/gate
  suites 138 passed / 4 optional integration skips. Aggregate-overflow owning checks
  subsequently passed 111 tests, and the legacy JSON-schema regression passed.
- Real contents references: 13 passed, zero skips, 34 actual Code_Aster solves,
  179.06 seconds. Evidence: `.build/qualification/fluid-contents.xml`.
- Procedural example: three real solves and imported review/scene artifacts at
  `.build/fluid-contents/review/`. Masses match independent formulas at 1e-12
  relative tolerance. Anchor reactions: Empty 450.265939646 N, Operating
  529.162640912 N, Hydrotest 548.886816228 N. The current compiler reproduces all
  three solved command files byte-for-byte.
- One independent gpt-6-astra review of `ca17624..816da68`: no findings; 35 additional
  read-only boundary assertions passed. No review fixes or deferred minors.
- Input reports preserve incomplete-model review: missing material/section definitions
  produce unavailable masses with an explicit reason. Malformed contents still fail
  quantity/solver admission. Rows use stable case-name ordering.
- The shared editable environment points direct file execution at main. Run this
  worktree's example as `python -m examples.fluid_contents` and pin `PYTHONPATH` for
  qualification subprocesses. The first unpinned broad run was interrupted and
  restarted; it is not qualification evidence.
- Browser security policy rejected local file-URL inspection. No workaround was
  attempted. JSON/CSV/HTML and scene-lineage checks passed; interactive rendering
  remains unverified.
- Full Python regression run: **1747 passed, 55 skipped, 138 subtests passed** in
  1319.57 seconds. One existing Windows ZMQ event-loop warning. Evidence:
  `.build/qualification/python-suite.xml`. The aggregate-overflow and legacy-schema
  tests were added after that run collected its tests; both passed separately at
  the final implementation revision in `.build/qualification/final-boundaries.xml`.
  This covers all 1804 currently collected tests (1749 passes across the full run
  and those two additional checks, 55 portable-run skips).
- Mandatory real gate: **45 passed, zero skips, 2 subtests passed**, 1179.36 seconds.
  Evidence: `.build/qualification/code-aster-references.xml`. Execution uses the
  configured WSL Ubuntu backend; the example attests Code_Aster **18.0.12**.
- JUnit artifacts were independently parsed for failures/errors and, for both real
  solver qualification files, forbidden skips. Logs, rulings and the review package
  remain in the ignored `.superpowers/sdd/2026-09-26-fluid-contents/` evidence folder.
- Subsequently merged locally into `main` as `5be87fc` on 2026-09-27. The merged
  tree passed 442 regression tests (one optional skip) and all 13 real fluid
  Code_Aster references. No push or publication has occurred. Next planned package
  is B, temperature-dependent material physics; it has not been started.
