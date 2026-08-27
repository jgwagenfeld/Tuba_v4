# Linear Route Pressure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve an authored linear pressure profile by route/station into per-element Code_Aster pressure groups and expose those resolved inputs in the existing review overlay.

**Architecture:** Generalize the existing linear-temperature midpoint resolver in `aster_loads.py`; do not add pressure knots to `OperationField`. Validation admits exactly `pressure + linear + route + finite station range`. The load-case overlay records authored and resolved pressure inputs as design data, never solver results.

**Tech Stack:** Python 3.10+, existing Code_Aster `AFFE_CHAR_MECA/FORCE_TUYAU`, unittest/pytest

**Spec:** `docs/superpowers/specs/2026-08-27-native-section-and-pipe-volume-meshing-design.md`

## Global Constraints

- Keep piecewise pressure unsupported because `OperationField` has no knot values.
- Use the operation base pressure at `station_start` and the field value at `station_end`.
- Resolve each selected element at the midpoint of its overlap with the authored station interval.
- Treat applied pressure as input metadata, not Code_Aster result evidence.
- Preserve the exact uniform pressure writer syntax when no local pressure field exists.

---

### Task 1: Validate and compile linear pressure

**Files:**
- Modify: `tuba/validation.py`
- Modify: `tuba/solver/aster_loads.py`
- Test: `tests/test_operation_fields.py`
- Test: `tests/test_code_aster_study.py`

**Interfaces:**
- Consumes: existing `OperationField(profile="linear", route_id=..., station_start=..., station_end=..., value=...)`.
- Produces: existing `FieldGroups = list[tuple[list[str], float]]`; no new public type.

- [ ] **Step 1: Replace the old rejection test with failing linear-pressure assertions**

```python
operating = model.define_operation("Operating", gravity=False, pressure=1.0e6)
operating.add_field("pressure", 3.0e6, route_id="P-100",
                    station_start=0.0, station_end=2.0, profile="linear")
CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
comm = (Path(tmpdir) / "study.comm").read_text()
assert "GROUP_MA='pipe_str_0'" in comm
assert "PRES=1.500000E+06" in comm
assert "GROUP_MA='pipe_str_1'" in comm
assert "PRES=2.500000E+06" in comm
```

Keep a separate piecewise-pressure rejection:

```python
operating.add_field("pressure", 3.0e6, route_id="P-100", profile="piecewise")
with pytest.raises(ModelValidationError, match="piecewise"):
    model.validate()
```

- [ ] **Step 2: Verify linear pressure fails for the current validation reason**

Run: `uv run pytest tests/test_operation_fields.py -q`

Expected: FAIL stating only uniform fields plus linear temperature are supported.

- [ ] **Step 3: Generalize the existing midpoint resolver**

```python
if field_record.profile == "linear" and quantity in {"temperature", "pressure"}:
    base = load_case.temperature if quantity == "temperature" else load_case.internal_pressure
    rows.extend(_linear_route_field_groups(model, field_record, index,
                                           quantity=quantity, base=float(base)))
```

Rename `_linear_temperature_field_groups` to `_linear_route_field_groups`; retain its overlap midpoint formula and quantity-specific error text.

- [ ] **Step 4: Admit only route-scoped linear pressure in validation**

```python
linear_supported = field_record.quantity in {"temperature", "pressure"} and field_record.profile == "linear"
if field_record.profile != "uniform" and not linear_supported:
    errors.append(f"{label} uses unsupported profile {field_record.profile!r} for {field_record.quantity!r}.")
```

Use the existing route/station checks for both linear quantities.

- [ ] **Step 5: Verify field and writer tests**

Run: `uv run pytest tests/test_operation_fields.py tests/test_code_aster_study.py -q`

Expected: PASS, including unchanged uniform syntax.

- [ ] **Step 6: Commit the solver slice**

```bash
git add tuba/validation.py tuba/solver/aster_loads.py tests/test_operation_fields.py tests/test_code_aster_study.py
git commit -m "feat: compile linear pressure profiles"
```

### Task 2: Display authored and resolved pressure inputs

**Files:**
- Modify: `tuba/visualization/builders/_loads.py`
- Test: `tests/test_visualization_layer_structure.py`

**Interfaces:**
- Consumes: `resolve_operation_field_groups(model, load_case, "pressure")`.
- Produces: `overlay.data.pressure_fields`, a list of `{element_ids, pressure_pa}` records on the existing `load_case` overlay.

- [ ] **Step 1: Write the failing overlay test**

```python
overlay = next(item for item in scene.overlays if item.id == "overlay:load_case:Operating")
assert overlay.data["pressure_fields"] == [
    {"element_ids": ["pipe_str_0"], "pressure_pa": 1.5e6},
    {"element_ids": ["pipe_str_1"], "pressure_pa": 2.5e6},
]
assert overlay.data["pressure_source"] == "authored_input"
```

- [ ] **Step 2: Verify the overlay lacks resolved pressure data**

Run: `uv run pytest tests/test_visualization_layer_structure.py -q`

Expected: FAIL with missing `pressure_fields`.

- [ ] **Step 3: Add resolved input records to the existing overlay**

```python
pressure_fields = resolve_operation_field_groups(model, load_case, "pressure")
data["pressure_fields"] = [
    {"element_ids": list(ids), "pressure_pa": value}
    for ids, value in pressure_fields
]
data["pressure_source"] = "authored_input"
```

Pass `model` into `_load_case_overlay`; do not create glyphs or result fields.

- [ ] **Step 4: Verify visualization and scene serialization**

Run: `uv run pytest tests/test_visualization_layer_structure.py tests/test_visualization_web_export.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the input-overlay slice**

```bash
git add tuba/visualization/builders/_loads.py tests/test_visualization_layer_structure.py
git commit -m "feat: expose resolved pressure inputs"
```
