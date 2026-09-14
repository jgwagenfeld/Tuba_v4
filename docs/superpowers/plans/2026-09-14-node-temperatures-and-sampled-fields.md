# Node Temperatures and Sampled Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Temperatures can be given per node and reach every Code_Aster solver node, and helpers put CFD clouds, Python functions and route tables onto ordinary operation fields.

**Architecture:**
- **Authoring.** A `nodes` scope on `OperationField` (`node_ids`) carries uniform temperatures.
- **Compiler.**
  - `tuba/solver/aster_loads.py` resolves the node temperatures of one load case. It interpolates every solver node of each touched element.
  - The mesh mixin lists those nodes with their fractions and adds `GN_` groups.
  - `_write_temperature_field` appends one `GROUP_NO` row per node.
- **Helpers.** `tuba/sampling.py` evaluates a source in Python and writes plain fields, so the model stores numbers only.

**Tech Stack:** Python 3.11, numpy, pytest/unittest, Code_Aster 1D (`CREA_CHAMP` `NOEU_TEMP_R`, `AFFE_MATERIAU` `AFFE_VARC`), and the WSL Code_Aster runtime for the opt-in reference.

**Spec:** `docs/superpowers/specs/2026-09-14-node-temperatures-and-sampled-fields-design.md`

## Global Constraints

- **Base.**
  - Start from committed `main` at `e155b2d`, in the worktree `D:\tmp\tuba-node-temperatures` on branch `feat/node-temperatures-and-sampled-fields` (see Setup).
  - `stash@{0}` (the generalized-fields WIP) is not part of this work. Copy nothing from it, and never drop it.
- **Files off limits.** Do not edit `tuba/solver/aster.py` or `tuba/solver/aster_volume.py`. Plan 4 is refactoring both in `D:\tmp\tuba-plan4`.
- **Running tests.**
  - Run from the worktree root with the main venv: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest <paths> -q`.
  - A fresh worktree has no `viewer/node_modules`, so the two `test_package_release` vite build tests fail there. That is expected.
- **Byte identity.**
  - A model with no node temperatures exports a byte-identical `study.comm` and `study.mail`.
  - Do not bump `CODE_ASTER_COMPILER_ID`.
  - `_operation_field_payload` and `_operation_field_dict` add `node_ids` only when it is non-empty.
- **Numbers only.** Store only what the solver receives: no formula strings, clouds, tables or file references in the model, and no `eval`.
- **Node-scoped fields.**
  - A node-scoped field is a uniform `temperature` with non-empty `node_ids`. It has no `group`, `route_id`, station range, `element_ids` or direction.
  - Its nodes exist and lie on a pipe element.
  - Disagreeing node values are refused; identical duplicates are allowed.
  - A node with a node temperature that belongs to an element selected by any element temperature field is refused.
- **Written nodes.**
  - The compiler writes every solver node of every element, of any type, that has an end node carrying a node temperature.
  - Fractions along the element:
    - interior node `i` of `N` segments: `i/N`;
    - midside of bend segment `k`: `(k + 0.5)/N`;
    - midside of a TUYAU straight: `0.5`.
  - A generated node takes `(1 - t) * start + t * end`.
- **Uncovered ends.** An end without a node temperature takes the value of the last row of `resolve_operation_field_groups(model, load_case, "temperature")` whose elements include an element at that node. With no such row it takes `load_case.temperature`.
- **`CREA_CHAMP` rows.**
  - The order is `TOUT`, then today's `GROUP_MA` rows, then one `GROUP_NO='GN_<node>'` row per written node.
  - `TEMP_FIELD` and `TEMP_HOT_FIELD` get the node rows. `TEMP_REF_FIELD` stays uniform.
- **Helpers.**
  - Helpers select elements through `model.resolve_operation_field_elements`.
  - They compute every value before writing, so a refusal writes nothing.
  - They take `group`, `route_id`, `station_start`, `station_end` and `element_ids` the way `add_field` does.
  - Cloud distances are computed with NumPy, one target at a time; no SciPy.
- **Units.**
  - Coordinates, points and the capture radius are in metres.
  - Temperature is in °C, pressure in Pa, wind in Pa (dynamic pressure), and line load in N/m.
- **Real solver.**
  - Real-solver tests are opt-in: `$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"`.
  - The runtime comes from `TUBA_CODE_ASTER_EXEC_METHOD` / `TUBA_CODE_ASTER_WSL_DISTRO`, which on this machine are `wsl` / `Ubuntu` and already set.
  - Never fabricate solver results.
- **Commits.** Commit messages carry no `Co-Authored-By` trailer.

## Setup

- [ ] **Create the worktree and commit the spec and plan into it**

```powershell
git -C D:\Gitprojects\Tuba_v4 worktree add D:\tmp\tuba-node-temperatures -b feat/node-temperatures-and-sampled-fields main
Copy-Item D:\Gitprojects\Tuba_v4\docs\superpowers\specs\2026-09-14-node-temperatures-and-sampled-fields-design.md D:\tmp\tuba-node-temperatures\docs\superpowers\specs\
Copy-Item D:\Gitprojects\Tuba_v4\docs\superpowers\plans\2026-09-14-node-temperatures-and-sampled-fields.md D:\tmp\tuba-node-temperatures\docs\superpowers\plans\
git -C D:\tmp\tuba-node-temperatures add docs/superpowers/specs/2026-09-14-node-temperatures-and-sampled-fields-design.md docs/superpowers/plans/2026-09-14-node-temperatures-and-sampled-fields.md
git -C D:\tmp\tuba-node-temperatures commit -m "docs: spec and plan for node temperatures and sampled fields"
```

Expected: `git -C D:\tmp\tuba-node-temperatures log --oneline -2` shows the docs commit on top of `e155b2d`.

## File Map

| File | Responsibility in this plan |
|---|---|
| `tuba/model.py` | `OperationField.node_ids`, `add_field(node_ids=...)`, serialization |
| `tuba/validation.py` | Node-scope rules and the node/element temperature overlap |
| `tuba/schema.py` | The `nodes` scope and `node_ids` in `operationField` |
| `tuba/analysis/provenance.py`, `tuba/reporting/tables.py` | `node_ids` in fingerprint and report rows, only when present |
| `tuba/solver/aster_loads.py` | Resolve node temperatures, interpolate solver nodes, write `GROUP_NO` rows |
| `tuba/solver/aster_mesh.py` | An element's solver nodes with their fractions; `GN_` groups in `.mail` and `AnalysisMesh` |
| `tuba/solver/aster_comm.py` | Wire node temperatures into the thermal load |
| `tuba/sampling.py` (new) | `field_from_cloud`, `field_from_function`, `field_from_route_table` |
| `tests/test_node_temperatures.py` (new) | Authoring, validation and compiler tests |
| `tests/test_sampling.py` (new) | Helper tests |
| `tests/test_code_aster_node_temperatures.py` (new) | Opt-in real Code_Aster reference |
| `docs/content/modeling.md`, `CONTEXT.md`, `docs/architecture/library-architecture-review.md` | User docs, glossary, command map and inventory |

---

### Task 1: Node-scoped temperature fields

**Files:**
- Modify: `tuba/model.py:398-411` (`OperationField`), `:505-538` (`add_field`), `:1664-1683` (`_operation_field_to_dict`)
- Modify: `tuba/validation.py:123-218` (`_validate_operation_fields`), plus a new `_node_field_problem`
- Modify: `tuba/schema.py:313-332` (`operationField`)
- Modify: `tuba/analysis/provenance.py:171-183`, `tuba/reporting/tables.py:1181-1193`
- Create: `tests/test_node_temperatures.py`

**Interfaces:**
- Produces:
  - `OperationField.node_ids: List[str]`, empty by default.
  - `Operation.add_field(..., node_ids: Optional[List[str]] = None)`, which sets `scope="nodes"` when `group`, `route_id` and `element_ids` are all `None`.
  - `_node_field_problem(field_record, model, pipe_nodes) -> str | None` in `tuba/validation.py`.
- Validation messages (exact text):
  - `"{label} lists node_ids but has scope {scope!r}; node_ids need scope 'nodes'."`
  - `"{label} scopes {quantity!r} to nodes; only uniform temperature fields take node_ids."`
  - `"{label} has scope 'nodes' but no node_ids."`
  - `"{label} scopes to nodes, so it takes no group, route_id, station range, element_ids or direction."`
  - `"{label} references missing nodes {missing!r}."`
  - `"{label} gives a temperature to nodes on no pipe element: {off_pipe!r}."`
  - `"Operation {name!r} has overlapping incompatible temperature fields on node {node_id!r}: {previous!r} vs {value!r}."`
  - `"Operation {name!r} gives nodes {shared!r} a node temperature, but they belong to elements that element temperature fields {indices!r} cover; a node takes one or the other."`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_node_temperatures.py`:

```python
import unittest

from tuba import Model
from tuba.analysis.provenance import _operation_field_payload
from tuba.model import OperationField, _operation_field_to_dict
from tuba.reporting.tables import _operation_field_dict
from tuba.schema import validate_model_dict
from tuba.validation import ModelValidationError


def _model(name: str = "NodeTemperatures") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route(name: str = "NodeTemperatures") -> Model:
    """pipe_str_0 runs N0 to N1 and pipe_str_1 runs N1 to N2, 1 m each along X, anchored at N0 and N2."""
    model = _model(name)
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


class TestNodeTemperatureAuthoring(unittest.TestCase):
    def test_node_ids_set_the_nodes_scope_and_round_trip(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        field_record = operating.add_field("temperature", 180.0, node_ids=["N1"])
        self.assertEqual(field_record.scope, "nodes")
        self.assertEqual(field_record.node_ids, ["N1"])
        model.validate()

        data = model.to_dict()
        validate_model_dict(data)
        self.assertEqual(
            data["operations"]["Operating"]["fields"],
            [{"quantity": "temperature", "value": 180.0, "scope": "nodes", "profile": "uniform", "node_ids": ["N1"]}],
        )
        restored = Model.from_dict(data)
        self.assertEqual(restored.operations["Operating"].fields[0].node_ids, ["N1"])
        self.assertEqual(restored.operations["Operating"].fields[0].scope, "nodes")
        restored.validate()

    def test_element_fields_keep_their_serialized_shape(self):
        element_field = OperationField("temperature", 120.0, scope="route", route_id="P-100")
        self.assertNotIn("node_ids", _operation_field_to_dict(element_field))
        self.assertNotIn("node_ids", _operation_field_payload(element_field))
        self.assertNotIn("node_ids", _operation_field_dict(element_field))

        node_field = OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"])
        self.assertEqual(_operation_field_to_dict(node_field)["node_ids"], ["N1"])
        self.assertEqual(_operation_field_payload(node_field)["node_ids"], ["N1"])
        self.assertEqual(_operation_field_dict(node_field)["node_ids"], ["N1"])

    def test_node_fields_take_only_uniform_temperatures_on_existing_nodes(self):
        cases = (
            ("pressure", 1.0e6, {"node_ids": ["N1"]}, "scopes 'pressure' to nodes; only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "profile": "linear"}, "only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"scope": "nodes"}, "has scope 'nodes' but no node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "route_id": "P-100"}, "lists node_ids but has scope 'route'"),
            (
                "temperature",
                80.0,
                {"node_ids": ["N1"], "station_start": 0.0},
                "takes no group, route_id, station range, element_ids or direction",
            ),
            ("temperature", 80.0, {"node_ids": ["N9"]}, r"references missing nodes \['N9'\]"),
        )
        for quantity, value, kwargs, message in cases:
            model = _two_element_route()
            model.define_operation("Operating", gravity=False).add_field(quantity, value, **kwargs)
            with self.subTest(message=message):
                with self.assertRaisesRegex(ModelValidationError, message):
                    model.validate()

    def test_node_temperatures_need_a_pipe_node(self):
        model = _model("RackNode")
        with model.pipe("PipeSec", "Steel", route="RACK") as rack:
            rack.start([0.0, 0.0, 0.0], support="anchor")
            rack.run(1.0)
            rack.beam(1.0)
            rack.end(support="anchor")
        # pipe_str_0 runs N0 to N1 and beam_0 runs N1 to N2, so N2 touches only the beam.
        model.define_operation("Operating", gravity=False).add_field("temperature", 80.0, node_ids=["N2"])
        with self.assertRaisesRegex(ModelValidationError, r"nodes on no pipe element: \['N2'\]"):
            model.validate()

    def test_node_temperatures_are_states(self):
        agreeing = _two_element_route()
        operating = agreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 150.0, node_ids=["N1", "N2"])
        agreeing.validate()

        disagreeing = _two_element_route()
        operating = disagreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, node_ids=["N1"])
        with self.assertRaisesRegex(
            ModelValidationError, r"overlapping incompatible temperature fields on node 'N1': 150\.0 vs 90\.0"
        ):
            disagreeing.validate()

    def test_node_and_element_temperatures_may_not_meet_at_a_node(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        with self.assertRaisesRegex(
            ModelValidationError,
            r"gives nodes \['N1'\] a node temperature, but they belong to elements that "
            r"element temperature fields \[1\] cover; a node takes one or the other",
        ):
            model.validate()

        # N0 lies only on pipe_str_0, which no element field covers.
        apart = _two_element_route()
        operating = apart.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N0"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        apart.validate()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_node_temperatures.py -q`
Expected: FAIL. Most tests stop at `TypeError: add_field() got an unexpected keyword argument 'node_ids'`, or at `OperationField.__init__() got an unexpected keyword argument 'node_ids'`.

- [ ] **Step 3: Add `node_ids` to the model**

In `tuba/model.py`, give `OperationField` the new field after `element_ids`:

```python
    element_ids: List[str] = field(default_factory=list)
    node_ids: List[str] = field(default_factory=list)
```

In `Operation.add_field`, add the keyword after `element_ids`, extend the scope precedence, and pass it on:

```python
        element_ids: Optional[List[str]] = None,
        node_ids: Optional[List[str]] = None,
        direction: Optional[List[float]] = None,
    ) -> OperationField:
        if group is not None:
            scope = "group"
        elif route_id is not None:
            scope = "route"
        elif element_ids is not None:
            scope = "elements"
        elif node_ids is not None:
            scope = "nodes"
        field_record = OperationField(
            quantity=quantity,
            value=float(value),
            direction=(None if direction is None else [float(value) for value in direction]),
            scope=scope,
            profile=profile,
            group=group,
            route_id=route_id,
            station_start=station_start,
            station_end=station_end,
            element_ids=list(element_ids or []),
            node_ids=list(node_ids or []),
        )
```

In `_operation_field_to_dict`, write `node_ids` only when there are some, right after the `element_ids` lines:

```python
    if field_record.element_ids:
        data["element_ids"] = list(field_record.element_ids)
    if field_record.node_ids:
        data["node_ids"] = list(field_record.node_ids)
```

- [ ] **Step 4: Schema, fingerprint payload and report row**

In `tuba/schema.py` `operationField`, replace the scope enum and add `node_ids` after `element_ids`:

```python
                "scope": {"enum": ["all", "group", "route", "elements", "nodes"]},
```

```python
                "element_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
```

Replace `_operation_field_payload` in `tuba/analysis/provenance.py`:

```python
def _operation_field_payload(field: Any) -> dict[str, Any]:
    payload = {
        "quantity": field.quantity,
        "value": float(field.value),
        "direction": list(field.direction) if field.direction is not None else None,
        "scope": field.scope,
        "profile": field.profile,
        "group": field.group,
        "route_id": field.route_id,
        "station_start": field.station_start,
        "station_end": field.station_end,
        "element_ids": list(field.element_ids),
    }
    # Only node-scoped fields carry node_ids, so every other fingerprint stays as it was.
    if field.node_ids:
        payload["node_ids"] = list(field.node_ids)
    return payload
```

Replace `_operation_field_dict` in `tuba/reporting/tables.py`:

```python
def _operation_field_dict(field: OperationField) -> dict[str, Any]:
    row = {
        "quantity": field.quantity,
        "value": field.value,
        "direction": _optional_list(field.direction),
        "scope": field.scope,
        "profile": field.profile,
        "group": field.group,
        "route_id": field.route_id,
        "station_start": field.station_start,
        "station_end": field.station_end,
        "element_ids": list(field.element_ids),
    }
    if field.node_ids:
        row["node_ids"] = list(field.node_ids)
    return row
```

- [ ] **Step 5: Validate node-scoped fields**

In `tuba/validation.py` `_validate_operation_fields`, make four edits.

First, replace the opening lines up to the `for index, field_record` loop header:

```python
def _validate_operation_fields(model: TubaModel, errors: list[str]) -> None:
    valid_quantities = {"pressure", "temperature", "wind", "line_load"}
    valid_scopes = {"all", "group", "route", "elements", "nodes"}
    valid_profiles = {"uniform", "linear", "piecewise"}
    pipe_nodes = {
        node_id
        for elem in model.elements
        if elem.type in {"pipe_straight", "pipe_bend"}
        for node_id in (elem.n1, elem.n2)
    }

    for operation_name, operation in getattr(model, "operations", {}).items():
        seen: dict[str, dict[str, float]] = {}
        node_temperatures: dict[str, float] = {}
        element_temperature_nodes: dict[str, set[int]] = {}
        for index, field_record in enumerate(getattr(operation, "fields", [])):
```

Second, directly after the existing non-finite value check, which is these lines:

```python
            if not np.isfinite(float(field_record.value)):
                errors.append(f"{label} has a non-finite value.")
                continue
```

insert the node branch:

```python
            if field_record.scope == "nodes" or field_record.node_ids:
                problem = _node_field_problem(field_record, model, pipe_nodes)
                if problem is not None:
                    errors.append(f"{label} {problem}")
                    continue
                value = float(field_record.value)
                for node_id in field_record.node_ids:
                    previous = node_temperatures.get(node_id)
                    if previous is not None and previous != value:
                        errors.append(
                            f"Operation {operation_name!r} has overlapping incompatible temperature fields "
                            f"on node {node_id!r}: {previous!r} vs {value!r}."
                        )
                    node_temperatures[node_id] = value
                continue
```

Third, replace the line `quantity_values = seen.setdefault(field_record.quantity, {})` with:

```python
            if field_record.quantity == "temperature":
                for elem in selected:
                    for node_id in (elem.n1, elem.n2):
                        element_temperature_nodes.setdefault(node_id, set()).add(index)

            quantity_values = seen.setdefault(field_record.quantity, {})
```

Fourth, after the inner `for index, field_record` loop ends and still inside the `for operation_name` loop, add the overlap check. It goes after the existing `quantity_values[elem.id] = value_key` block, dedented to the level of the inner `for` statement:

```python
        shared = sorted(set(node_temperatures) & set(element_temperature_nodes))
        if shared:
            indices = sorted({index for node_id in shared for index in element_temperature_nodes[node_id]})
            errors.append(
                f"Operation {operation_name!r} gives nodes {shared!r} a node temperature, but they belong to "
                f"elements that element temperature fields {indices!r} cover; a node takes one or the other."
            )
```

Add the helper right after `_validate_operation_fields`, before `_operation_field_value_key`:

```python
def _node_field_problem(field_record, model: TubaModel, pipe_nodes: set[str]) -> str | None:
    """The first reason a node-scoped operation field is invalid, or None."""
    if field_record.scope != "nodes":
        return f"lists node_ids but has scope {field_record.scope!r}; node_ids need scope 'nodes'."
    if field_record.quantity != "temperature" or field_record.profile != "uniform":
        return f"scopes {field_record.quantity!r} to nodes; only uniform temperature fields take node_ids."
    if not field_record.node_ids:
        return "has scope 'nodes' but no node_ids."
    if (
        field_record.group is not None
        or field_record.route_id is not None
        or field_record.station_start is not None
        or field_record.station_end is not None
        or field_record.element_ids
        or field_record.direction is not None
    ):
        return "scopes to nodes, so it takes no group, route_id, station range, element_ids or direction."
    missing = [node_id for node_id in field_record.node_ids if node_id not in model.nodes]
    if missing:
        return f"references missing nodes {missing!r}."
    off_pipe = [node_id for node_id in field_record.node_ids if node_id not in pipe_nodes]
    if off_pipe:
        return f"gives a temperature to nodes on no pipe element: {off_pipe!r}."
    return None
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_node_temperatures.py tests/test_operation_fields.py tests/test_reporting_tables.py tests/test_solver_input_provenance.py -q`
Expected: all pass. `test_materials_and_load_cases_preserve_nested_authoritative_definitions` still matches its exact field dict, because an element field has no `node_ids` key.

- [ ] **Step 7: Commit**

```powershell
git add tuba/model.py tuba/validation.py tuba/schema.py tuba/analysis/provenance.py tuba/reporting/tables.py tests/test_node_temperatures.py
git commit -m "feat(model): scope uniform temperature fields to nodes"
```

### Task 2: Compile node temperatures into a nodal field

**Files:**
- Modify: `tuba/solver/aster_loads.py`:
  - the type aliases at the top;
  - `resolve_operation_field_groups`, `has_temperature_load`, `write_thermal_load` and `_write_temperature_field`;
  - add `resolve_node_temperatures` and `node_temperature_entries`.
- Modify: `tuba/solver/aster_mesh.py`: add `_element_solver_nodes` and `_node_temperature_node_ids`, and use the second at `:312` and `:479`.
- Modify: `tuba/solver/aster_comm.py:31-45` (imports), `:273`, `:288`, `:769-776`
- Modify: `tests/test_node_temperatures.py`

**Interfaces:**
- Consumes: `OperationField.node_ids` and scope `"nodes"` (Task 1).
- Produces:
  - `resolve_node_temperatures(model, load_case) -> dict[str, float]`
  - `node_temperature_entries(model, load_case, temperature_fields, solver_nodes) -> list[tuple[str, float]]`, where
    `solver_nodes: Callable[[Element], Sequence[tuple[str, float]]]`
  - `has_temperature_load(load_case, temperature_fields, node_temperatures=())`
  - `write_thermal_load(..., node_temperatures=...)`, a required keyword
  - `_MeshWriterMixin._element_solver_nodes(elem) -> list[tuple[str, float]]`: node id and fraction, from `n1` to `n2`
  - `_MeshWriterMixin._node_temperature_node_ids(model) -> set[str]`
- Refusal messages (exact text):
  - `"Operation field {index} scopes {quantity!r} to nodes; only uniform temperature fields take node_ids."`
  - `"Operation field {index} references missing node {node_id!r}."`
  - `"Operation field {index} gives node {node_id!r} {value!r}, but an earlier node field gives it {previous!r}."`
  - `"Nodes {shared!r} have a node temperature and belong to elements an element temperature field covers; a node takes one or the other."`

- [ ] **Step 1: Pin today's temperature text**

In `tests/test_node_temperatures.py`, replace the import block with:

```python
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis import AnalysisMesh
from tuba.analysis.provenance import _operation_field_payload
from tuba.model import BendGeometry, OperationField, _operation_field_to_dict
from tuba.reporting.tables import _operation_field_dict
from tuba.schema import validate_model_dict
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization
from tuba.validation import ModelValidationError
```

Append to the end of the file. The text below was captured from `main` at `e155b2d`; do not regenerate it after changing the writer.

```python
# Captured from main at e155b2d: what an element-temperature model exports before node temperatures exist.
TEMP_FIELD_TODAY = """TEMP_FIELD = CREA_CHAMP(
    TYPE_CHAM='NOEU_TEMP_R',
    OPERATION='AFFE',
    MODELE=MODELE,
    AFFE=(
        _F(
            TOUT='OUI',
            NOM_CMP='TEMP',
            VALE=6.000000E+01,
        ),
        _F(
            GROUP_MA='pipe_str_0',
            NOM_CMP='TEMP',
            VALE=9.000000E+01,
        ),
        _F(
            GROUP_MA='pipe_str_1',
            NOM_CMP='TEMP',
            VALE=1.000000E+02,
        ),
    ),
);
"""
TEMP_HOT_FIELD_TODAY = TEMP_FIELD_TODAY.replace("TEMP_FIELD = ", "TEMP_HOT_FIELD = ", 1)
TEMP_REF_FIELD_TODAY = """TEMP_REF_FIELD = CREA_CHAMP(
    TYPE_CHAM='NOEU_TEMP_R',
    OPERATION='AFFE',
    MAILLAGE=MAIL,
    AFFE=_F(
        TOUT='OUI',
        NOM_CMP='TEMP',
        VALE=2.000000E+01,
    ),
);
"""


def _export(model: Model, case: str, **solver_options) -> tuple[str, str]:
    with TemporaryDirectory() as tmpdir:
        CodeAsterSolver(work_dir=tmpdir, **solver_options).export_study(model, case, tmpdir)
        root = Path(tmpdir)
        return (root / "study.comm").read_text(encoding="utf-8"), (root / "study.mail").read_text(encoding="utf-8")


def _crea_champ(comm: str, name: str) -> str:
    start = comm.index(f"{name} = CREA_CHAMP(")
    return comm[start : comm.index(");\n", start) + len(");\n")]


def _group_no_lines(mail: str) -> list[str]:
    return [line for line in mail.splitlines() if line.startswith("GROUP_NO NOM=")]


def _node_rows(block: str) -> list[tuple[str, str]]:
    """(GROUP_NO name, VALE text) of each node row of a CREA_CHAMP block, in order."""
    return re.findall(r"GROUP_NO='([^']+)',\n\s+NOM_CMP='TEMP',\n\s+VALE=([^,]+),", block)


def _element_temperature_model(*, rest: bool) -> Model:
    model = _two_element_route("ElementTemperatures")
    if rest:
        model.add_support("N1", type="rest")
    operating = model.define_operation("Operating", gravity=False, temperature=60.0, ref_temperature=20.0)
    operating.add_field("temperature", 120.0, route_id="P-100", station_start=0.0, station_end=1.0, profile="linear")
    operating.add_field("temperature", 100.0, element_ids=["pipe_str_1"])
    return model


def _elbow_model() -> Model:
    """run: N0 (0, 0, 0) to N1 (4, 0, 0); elbow: 90 degrees, R 0.5, N1 to N2 (4.5, 0.5, 0); anchored at N0 and N2."""
    model = _model("NodeTemperatureElbow")
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([4.0, 0.0, 0.0])
    end = model.add_node([4.5, 0.5, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="PipeSec", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="PipeSec", material="Steel",
        bend_radius=0.5, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[4.0, 0.5, 0.0], normal=[0.0, 0.0, 1.0], radius=0.5, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model


class TestNodeTemperatureCompiler(unittest.TestCase):
    def test_models_without_node_temperatures_export_todays_text(self):
        comm, mail = _export(_element_temperature_model(rest=False), "Operating")
        self.assertEqual(_crea_champ(comm, "TEMP_FIELD"), TEMP_FIELD_TODAY)
        self.assertEqual(
            _group_no_lines(mail),
            ["GROUP_NO NOM=PipeOrientationNodes", "GROUP_NO NOM=GN_N0", "GROUP_NO NOM=GN_N2", "GROUP_NO NOM=AllSupports"],
        )

        # A rest support makes the case nonlinear: a uniform reference field, then the hot field.
        comm, mail = _export(_element_temperature_model(rest=True), "Operating")
        self.assertEqual(_crea_champ(comm, "TEMP_REF_FIELD"), TEMP_REF_FIELD_TODAY)
        self.assertEqual(_crea_champ(comm, "TEMP_HOT_FIELD"), TEMP_HOT_FIELD_TODAY)
        self.assertEqual(
            _group_no_lines(mail),
            [
                "GROUP_NO NOM=PipeOrientationNodes",
                "GROUP_NO NOM=GN_N0",
                "GROUP_NO NOM=GN_N1",
                "GROUP_NO NOM=GN_N2",
                "GROUP_NO NOM=AllSupports",
            ],
        )
```

- [ ] **Step 2: Run the pin on today's writer**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_node_temperatures.py -q`
Expected: PASS. The pin must hold before the writer changes. If it fails here, stop and report; do not edit the captured text.

- [ ] **Step 3: Write the failing compiler tests**

Add `from tuba.solver.aster_loads import resolve_node_temperatures` to the imports, after `from tuba.solver.aster import CodeAsterSolver`. Then append these methods to `TestNodeTemperatureCompiler`:

```python
    def test_node_temperatures_interpolate_along_subdivided_beam_pipes(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 100.0, node_ids=["N0"])
        operating.add_field("temperature", 180.0, node_ids=["N1"])

        comm, mail = _export(model, "Operating", pipe_modelization=PipeModelization.POU_D_T)

        # The operation temperature equals the reference, so only the node temperatures make this a thermal case.
        block = _crea_champ(comm, "TEMP_FIELD")
        self.assertIn("MODELE=MODELE,", block)
        self.assertNotIn("GROUP_MA=", block)
        # Eight SEG2 spans per straight: N0 (100) to N1 (180) in 10-degree steps. Then N1 back to N2, which
        # nothing covers, so N2 keeps the operation temperature (20).
        expected = [("GN_N0", 100.0)]
        expected += [(f"GN_pipe_str_0_n{k}", 100.0 + 10.0 * k) for k in range(1, 8)]
        expected += [("GN_N1", 180.0)]
        expected += [(f"GN_pipe_str_1_n{k}", 180.0 - 20.0 * k) for k in range(1, 8)]
        expected += [("GN_N2", 20.0)]
        self.assertEqual(_node_rows(block), [(name, f"{value:.6E}") for name, value in expected])
        for name, _ in expected:
            self.assertIn(f"GROUP_NO NOM={name}", mail)

    def test_node_temperatures_interpolate_along_tuyau_bend_segments_and_midsides(self):
        model = _elbow_model()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 40.0, node_ids=["N1"])
        operating.add_field("temperature", 200.0, node_ids=["N2"])

        comm, mail = _export(model, "Operating")

        # The run is touched through N1: N0 keeps the operation temperature, and the SEG3 midside sits halfway.
        expected = [("GN_N0", 20.0), ("GN_run_mid", 30.0), ("GN_N1", 40.0)]
        # Sixteen SEG3 segments along the elbow: 10 degrees per segment, each midside halfway between.
        for k in range(16):
            expected.append((f"GN_elbow_s{k}_mid", 45.0 + 10.0 * k))
            expected.append((f"GN_elbow_n{k + 1}" if k < 15 else "GN_N2", 50.0 + 10.0 * k))
        self.assertEqual(_node_rows(_crea_champ(comm, "TEMP_FIELD")), [(name, f"{value:.6E}") for name, value in expected])
        self.assertIn("GROUP_NO NOM=GN_elbow_s0_mid", mail)

    def test_an_uncovered_end_takes_the_value_its_neighbour_field_gives_it(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 60.0, node_ids=["N0"])
        operating.add_field("temperature", 140.0, element_ids=["pipe_str_1"])
        model.validate()

        comm, _ = _export(model, "Operating")

        block = _crea_champ(comm, "TEMP_FIELD")
        # pipe_str_1's field gives N1 140 degrees, so pipe_str_0 runs 60 to 140 with its midside at 100.
        self.assertEqual(
            _node_rows(block),
            [("GN_N0", "6.000000E+01"), ("GN_pipe_str_0_mid", "1.000000E+02"), ("GN_N1", "1.400000E+02")],
        )
        self.assertLess(block.index("GROUP_MA='pipe_str_1'"), block.index("GROUP_NO="))

    def test_nonlinear_cases_ramp_to_the_node_temperatures(self):
        model = _two_element_route()
        model.add_support("N1", type="rest")
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 120.0, node_ids=["N0"])

        comm, _ = _export(model, "Operating")

        self.assertEqual(_crea_champ(comm, "TEMP_REF_FIELD"), TEMP_REF_FIELD_TODAY)
        self.assertEqual(
            _node_rows(_crea_champ(comm, "TEMP_HOT_FIELD")),
            [("GN_N0", "1.200000E+02"), ("GN_pipe_str_0_mid", "7.000000E+01"), ("GN_N1", "2.000000E+01")],
        )

    def test_groups_serve_every_study_but_rows_only_their_own_case(self):
        model = _two_element_route()
        model.define_operation("Hot", gravity=False).add_field("temperature", 120.0, node_ids=["N0"])
        model.define_operation("Warm", gravity=False, temperature=60.0, ref_temperature=20.0)

        comm, mail = _export(model, "Warm")

        self.assertNotIn("GROUP_NO=", _crea_champ(comm, "TEMP_FIELD"))
        self.assertIn("GROUP_NO NOM=GN_pipe_str_0_mid", mail)

    def test_the_analysis_mesh_records_the_node_temperature_groups(self):
        model = _two_element_route()
        model.define_operation("Hot", gravity=False).add_field("temperature", 120.0, node_ids=["N0"])

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))

        mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
        self.assertEqual(tuple(mesh.groups["GN_pipe_str_0_mid"]), ("pipe_str_0_mid",))
        self.assertEqual(mesh.node_sources["pipe_str_0_mid"].parametric_t, 0.5)

    def test_load_case_node_fields_are_checked_at_export(self):
        # Validation walks only operations, so the export resolver repeats the node rules for load cases.
        model = _two_element_route()
        load_case = model.define_load_case("Hot", gravity=False)
        load_case.fields.append(OperationField("temperature", 120.0, scope="nodes", node_ids=["N9"]))
        with self.assertRaisesRegex(ValueError, "field 0 references missing node 'N9'"):
            resolve_node_temperatures(model, load_case)

        load_case.fields[:] = [
            OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"]),
            OperationField("temperature", 90.0, scope="nodes", node_ids=["N1"]),
        ]
        with self.assertRaisesRegex(ValueError, r"field 1 gives node 'N1' 90\.0, but an earlier node field gives it 120\.0"):
            resolve_node_temperatures(model, load_case)

        load_case.fields[:] = [
            OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"]),
            OperationField("temperature", 90.0, scope="elements", element_ids=["pipe_str_1"]),
        ]
        with self.assertRaisesRegex(ValueError, r"Nodes \['N1'\] have a node temperature and belong to elements"):
            resolve_node_temperatures(model, load_case)

        load_case.fields[:] = [OperationField("pressure", 1.0e6, scope="nodes", node_ids=["N1"])]
        with self.assertRaisesRegex(ValueError, "field 0 scopes 'pressure' to nodes"):
            resolve_node_temperatures(model, load_case)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_node_temperatures.py -q`
Expected: FAIL at collection with `ImportError: cannot import name 'resolve_node_temperatures'`.

- [ ] **Step 5: Resolve and write node temperatures in `aster_loads.py`**

After `LineWriter = Callable[[str], None]`, add:

```python
NodeTemperatureEntries = Sequence[tuple[str, float]]
SolverNodes = Callable[[Element], Sequence[tuple[str, float]]]
```

In `resolve_operation_field_groups`, skip node-scoped temperature fields:

```python
        if field_record.quantity != quantity:
            continue
        if quantity == "temperature" and field_record.scope == "nodes":
            continue  # Node temperatures reach the field through node_temperature_entries.
```

Replace `has_temperature_load` with the version below, and add the two new functions right after it:

```python
def has_temperature_load(
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    node_temperatures: NodeTemperatureEntries = (),
) -> bool:
    delta_t = load_case.temperature - load_case.ref_temperature
    return (
        abs(delta_t) > 1e-10
        or any(abs(value - load_case.ref_temperature) > 1e-10 for _, value in temperature_fields)
        or any(abs(value - load_case.ref_temperature) > 1e-10 for _, value in node_temperatures)
    )


def resolve_node_temperatures(model: TubaModel, load_case: LoadCase) -> dict[str, float]:
    """Node-scoped temperature fields of one load case, as model node id -> temperature.

    Validation walks only operations, so this repeats its node rules for load-case fields.
    """
    values: dict[str, float] = {}
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.scope != "nodes":
            continue
        if field_record.quantity != "temperature" or field_record.profile != "uniform":
            raise ValueError(
                f"Operation field {index} scopes {field_record.quantity!r} to nodes; "
                "only uniform temperature fields take node_ids."
            )
        value = float(field_record.value)
        for node_id in field_record.node_ids:
            if node_id not in model.nodes:
                raise ValueError(f"Operation field {index} references missing node {node_id!r}.")
            previous = values.get(node_id)
            if previous is not None and previous != value:
                raise ValueError(
                    f"Operation field {index} gives node {node_id!r} {value!r}, "
                    f"but an earlier node field gives it {previous!r}."
                )
            values[node_id] = value
    if not values:
        return values
    covered: set[str] = set()
    for field_record in getattr(load_case, "fields", []):
        if field_record.quantity == "temperature" and field_record.scope != "nodes":
            for elem in model.resolve_operation_field_elements(field_record):
                covered.update((elem.n1, elem.n2))
    shared = sorted(set(values) & covered)
    if shared:
        raise ValueError(
            f"Nodes {shared!r} have a node temperature and belong to elements an element temperature "
            "field covers; a node takes one or the other."
        )
    return values


def node_temperature_entries(
    model: TubaModel,
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    solver_nodes: SolverNodes,
) -> list[tuple[str, float]]:
    """Temperatures for every solver node of the elements a node temperature touches, in write order.

    Code_Aster's temperature field has one value per node, and the solver mesh has
    nodes the model does not: bend and subdivision nodes, TUYAU midsides. A touched
    element gets its two end values and interpolates its generated nodes linearly at
    the fractions ``solver_nodes`` gives. An end without a node temperature keeps
    what the rest of the field gives it: the last element row covering it, else the
    case temperature.
    """
    node_values = resolve_node_temperatures(model, load_case)
    if not node_values:
        return []
    row_values: dict[str, float] = {}
    for element_ids, value in temperature_fields:
        for element_id in element_ids:
            elem = model.get_element(element_id)
            row_values[elem.n1] = value
            row_values[elem.n2] = value

    def end_value(node_id: str) -> float:
        if node_id in node_values:
            return node_values[node_id]
        return row_values.get(node_id, float(load_case.temperature))

    entries: dict[str, float] = {}
    for elem in model.elements:
        if elem.n1 not in node_values and elem.n2 not in node_values:
            continue
        start, end = end_value(elem.n1), end_value(elem.n2)
        for node_id, fraction in solver_nodes(elem):
            entries.setdefault(node_id, (1.0 - fraction) * start + fraction * end)
    return list(entries.items())
```

Replace `write_thermal_load` and `_write_temperature_field` with:

```python
def write_thermal_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    node_temperatures: NodeTemperatureEntries,
    affe_entries: List[str],
    is_nonlinear: bool,
) -> None:
    w("# ----- Thermal expansion -----")
    if is_nonlinear:
        _write_temperature_field(
            w,
            name="TEMP_REF_FIELD",
            value=load_case.ref_temperature,
            map_name=map_name,
            temperature_fields=[],
            node_temperatures=[],
        )
        _write_temperature_field(
            w,
            name="TEMP_HOT_FIELD",
            value=load_case.temperature,
            map_name=map_name,
            temperature_fields=temperature_fields,
            node_temperatures=node_temperatures,
        )
        w("TEMP_EVOL = CREA_RESU(")
        w("    OPERATION='AFFE',")
        w("    TYPE_RESU='EVOL_THER',")
        w("    NOM_CHAM='TEMP',")
        w("    AFFE=(")
        w("        _F(CHAM_GD=TEMP_REF_FIELD, INST=0.0),")
        w("        _F(CHAM_GD=TEMP_HOT_FIELD, INST=1.0),")
        w("    ),")
        w(");")
        w()
    else:
        _write_temperature_field(
            w,
            name="TEMP_FIELD",
            value=load_case.temperature,
            map_name=map_name,
            temperature_fields=temperature_fields,
            node_temperatures=node_temperatures,
        )

    w("CHMAT = AFFE_MATERIAU(")
    w("    MAILLAGE=MAIL,")
    w("    AFFE=(")
    for entry in affe_entries:
        w(entry)
    w("    ),")
    w("    AFFE_VARC=_F(")
    w("        TOUT='OUI',")
    w("        NOM_VARC='TEMP',")
    if is_nonlinear:
        w("        EVOL=TEMP_EVOL,")
        w("        NOM_CHAM='TEMP',")
    else:
        w("        CHAM_GD=TEMP_FIELD,")
    w(f"        VALE_REF={load_case.ref_temperature:.6E},")
    w("    ),")
    w(");")
    w()


def _write_temperature_field(
    w: LineWriter,
    *,
    name: str,
    value: float,
    map_name: NameMapper,
    temperature_fields: FieldGroups,
    node_temperatures: NodeTemperatureEntries,
) -> None:
    w(f"{name} = CREA_CHAMP(")
    w("    TYPE_CHAM='NOEU_TEMP_R',")
    w("    OPERATION='AFFE',")
    if temperature_fields or node_temperatures:
        w("    MODELE=MODELE,")
        w("    AFFE=(")
        w("        _F(")
        w("            TOUT='OUI',")
        w("            NOM_CMP='TEMP',")
        w(f"            VALE={value:.6E},")
        w("        ),")
        for group_names, field_value in temperature_fields:
            w("        _F(")
            w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
            w("            NOM_CMP='TEMP',")
            w(f"            VALE={field_value:.6E},")
            w("        ),")
        # A later occurrence overwrites an earlier one on a node, so the node rows go last.
        for node_id, node_value in node_temperatures:
            w("        _F(")
            w(f"            GROUP_NO='{map_name(f'GN_{node_id}')}',")
            w("            NOM_CMP='TEMP',")
            w(f"            VALE={node_value:.6E},")
            w("        ),")
        w("    ),")
    else:
        w("    MAILLAGE=MAIL,")
        w("    AFFE=_F(")
        w("        TOUT='OUI',")
        w("        NOM_CMP='TEMP',")
        w(f"        VALE={value:.6E},")
        w("    ),")
    w(");")
    w()
```

- [ ] **Step 6: List an element's solver nodes and group them in the mesh**

In `tuba/solver/aster_mesh.py`, add these two methods to `_MeshWriterMixin`, right after `_generated_midpoint_node_id`:

```python
    def _element_solver_nodes(self, elem: Element) -> list[tuple[str, float]]:
        """Every solver node of one model element with its fraction along it, from n1 to n2.

        The fractions match the ``parametric_t`` the analysis mesh records: equal steps
        along subdivided straights and bends (bend nodes sit at equal angles), and TUYAU
        SEG3 midsides halfway along their segment.
        """
        if elem.type == "pipe_bend":
            pairs = self._bend_segment_node_pairs(elem, self._BEND_SEGMENTS)
        else:
            pairs = self._straight_segment_node_pairs(elem)
        midsides = elem.type in ("pipe_straight", "pipe_bend") and self.pipe_modelization is not PipeModelization.POU_D_T
        nodes = [(elem.n1, 0.0)]
        for index, (segment_id, _, end) in enumerate(pairs):
            if midsides:
                nodes.append((self._generated_midpoint_node_id(segment_id), (index + 0.5) / len(pairs)))
            nodes.append((end, (index + 1) / len(pairs)))
        return nodes

    def _node_temperature_node_ids(self, model: TubaModel) -> set[str]:
        """Solver nodes that any load case's or operation's node temperatures write, for their GN_ groups."""
        node_ids: set[str] = set()
        cases = list(getattr(model, "load_cases", {}).values()) + list(getattr(model, "operations", {}).values())
        for case in cases:
            touched = {node_id for f in getattr(case, "fields", []) if f.scope == "nodes" for node_id in f.node_ids}
            for elem in model.elements:
                if elem.n1 in touched or elem.n2 in touched:
                    node_ids.update(node_id for node_id, _ in self._element_solver_nodes(elem))
        return node_ids
```

A TUYAU straight is one segment whose id is the element id, so `_generated_midpoint_node_id(segment_id)` gives `{element id}_mid`, as `_pipe_straight_midpoint_nodes` does.

In `_write_mail`, replace:

```python
        grouped_node_ids = sorted({sup.node for sup in model.supports} | _nodal_force_node_ids(model))
```

with:

```python
        grouped_node_ids = sorted(
            {sup.node for sup in model.supports} | _nodal_force_node_ids(model) | self._node_temperature_node_ids(model)
        )
```

In `_build_analysis_mesh_from_mail_parts`, replace:

```python
        for node_id in sorted({support.node for support in model.supports} | _nodal_force_node_ids(model)):
```

with:

```python
        for node_id in sorted(
            {support.node for support in model.supports}
            | _nodal_force_node_ids(model)
            | self._node_temperature_node_ids(model)
        ):
```

The solver name map is built from `AnalysisMesh.groups`, so `export_analysis_study` hashes the long `GN_` names without further changes.

- [ ] **Step 7: Wire node temperatures into the command file**

In `tuba/solver/aster_comm.py`, add `node_temperature_entries,` to the `tuba.solver.aster_loads` import list, after `has_wind_load,`.

After `temperature_fields = resolve_operation_field_groups(model, load_case, "temperature")`, add:

```python
        node_temperatures = node_temperature_entries(model, load_case, temperature_fields, self._element_solver_nodes)
```

Replace `has_temperature = has_thermal_load(load_case, temperature_fields)` with:

```python
        has_temperature = has_thermal_load(load_case, temperature_fields, node_temperatures)
```

In the `write_thermal_load(` call, add `node_temperatures=node_temperatures,` on the line after `temperature_fields=temperature_fields,`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_node_temperatures.py tests/test_operation_fields.py tests/test_code_aster_study.py tests/test_code_aster_beam_pipes.py tests/test_bend_geometry.py tests/test_straight_discretisation.py tests/test_analysis_mesh.py -q`
Expected: all pass, including `test_models_without_node_temperatures_export_todays_text` unchanged.

- [ ] **Step 9: Commit**

```powershell
git add tuba/solver/aster_loads.py tuba/solver/aster_mesh.py tuba/solver/aster_comm.py tests/test_node_temperatures.py
git commit -m "feat(solver): write node temperatures to every solver node of the elements they touch"
```

### Task 3: Sampling helpers

**Files:**
- Create: `tuba/sampling.py`
- Create: `tests/test_sampling.py`

**Interfaces:**
- Consumes:
  - `Operation.add_field(..., node_ids=...)` (Task 1);
  - `TubaModel.resolve_operation_field_elements`, `sample_bend_geometry` and `physical_properties_for_element` (existing).
- Produces (all return the `OperationField` records written, in target order):
  - `field_from_cloud(model, operation, quantity, points, values, *, capture_radius=None, direction=None, group=None, route_id=None, station_start=None, station_end=None, element_ids=None)`
  - `field_from_function(model, operation, quantity, function, *, direction=None, group=None, route_id=None, station_start=None, station_end=None, element_ids=None)`
  - `field_from_route_table(model, operation, quantity, route_id, table, *, direction=None, station_start=None, station_end=None)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sampling.py`:

```python
import math
import unittest

import numpy as np

from tuba import Model
from tuba.model import BendGeometry
from tuba.sampling import field_from_cloud, field_from_function, field_from_route_table


def _model(name: str = "Sampling") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route() -> Model:
    """pipe_str_0 runs N0 (0, 0, 0) to N1 (1, 0, 0), pipe_str_1 runs N1 to N2 (2, 0, 0); stations 0 to 2 on P-100."""
    model = _model()
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


def _elbow_model(*, stored_geometry: bool = True) -> Model:
    """run: N0 (0, 0, 0) to N1 (4, 0, 0); elbow: 90 degrees, R 0.5, N1 to N2 (4.5, 0.5, 0); anchored at N0 and N2."""
    model = _model("SamplingElbow")
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([4.0, 0.0, 0.0])
    end = model.add_node([4.5, 0.5, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="PipeSec", material="Steel")
    geometry = BendGeometry(
        center=[4.0, 0.5, 0.0], normal=[0.0, 0.0, 1.0], radius=0.5, angle=90,
        start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
    )
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="PipeSec", material="Steel",
        bend_radius=0.5, bend_angle=90, bend_geometry=geometry if stored_geometry else None,
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model


class TestFieldFromCloud(unittest.TestCase):
    def test_a_ring_of_wall_points_gives_the_node_its_circumferential_mean(self):
        model = _two_element_route()
        operation = model.define_operation("CFD", gravity=False)
        # Eight wall points on the 0.05 m pipe radius around N1, plus one point on each end node.
        ring = [[1.0, 0.05 * math.cos(angle), 0.05 * math.sin(angle)] for angle in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False)]
        points = ring + [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        values = [100.0 + 10.0 * k for k in range(8)] + [50.0, 70.0]

        fields = field_from_cloud(model, operation, "temperature", points, values)

        self.assertEqual([(f.node_ids, f.value) for f in fields], [(["N0"], 50.0), (["N1"], 135.0), (["N2"], 70.0)])
        model.validate()

    def test_targets_without_a_point_are_refused_and_nothing_is_written(self):
        model = _two_element_route()
        operation = model.define_operation("CFD", gravity=False)
        # The default radius is 1.25 x the 0.05 m bare radius; only N0 has a point that close.
        with self.assertRaisesRegex(
            ValueError,
            r"2 target\(s\) have no cloud point within the capture radius: 'N1' nearest point 1 m, radius 0\.0625 m; "
            r"'N2' nearest point 2 m.*units \(mm vs m\)",
        ):
            field_from_cloud(model, operation, "temperature", [[0.0, 0.0, 0.0]], [80.0])
        self.assertEqual(operation.fields, [])

        fields = field_from_cloud(model, operation, "temperature", [[0.0, 0.0, 0.0]], [80.0], capture_radius=2.5)
        self.assertEqual([f.value for f in fields], [80.0, 80.0, 80.0])

        with self.assertRaisesRegex(ValueError, r"points must have shape \(N, 3\)"):
            field_from_cloud(model, operation, "temperature", [[0.0, 0.0]], [80.0])


class TestFieldFromFunction(unittest.TestCase):
    def test_values_land_on_nodes_and_on_the_bend_arc_midpoint(self):
        model = _elbow_model()
        operation = model.define_operation("Formula", gravity=False)

        temperatures = field_from_function(model, operation, "temperature", lambda x, y, z: 20.0 + 10.0 * x + 100.0 * y)
        self.assertEqual([(f.node_ids, f.value) for f in temperatures], [(["N0"], 20.0), (["N1"], 60.0), (["N2"], 115.0)])

        winds = field_from_function(model, operation, "wind", lambda x, y, z: 1000.0 * y, direction=[0.0, 1.0, 0.0])
        # The run's midpoint is (2, 0, 0); the elbow's arc midpoint is the centre (4, 0.5) plus R (sin 45, -cos 45).
        self.assertEqual([f.element_ids for f in winds], [["run"], ["elbow"]])
        self.assertAlmostEqual(winds[0].value, 0.0)
        self.assertAlmostEqual(winds[1].value, 1000.0 * (0.5 - 0.5 * math.cos(math.pi / 4.0)))
        self.assertEqual(winds[1].direction, [0.0, 1.0, 0.0])
        model.validate()

    def test_helpers_follow_the_field_rules(self):
        model = _two_element_route()
        operation = model.define_operation("Rules", gravity=False)
        with self.assertRaisesRegex(ValueError, "wind needs a direction"):
            field_from_function(model, operation, "wind", lambda x, y, z: 1000.0)
        with self.assertRaisesRegex(ValueError, "temperature takes no direction"):
            field_from_function(model, operation, "temperature", lambda x, y, z: 80.0, direction=[1.0, 0.0, 0.0])
        with self.assertRaisesRegex(TypeError, "formula strings are not evaluated"):
            field_from_function(model, operation, "temperature", "20 + 10 * x")
        with self.assertRaisesRegex(ValueError, "function returned nan at 'N0'"):
            field_from_function(model, operation, "temperature", lambda x, y, z: float("nan"))
        with self.assertRaisesRegex(ValueError, r"line_load station range 0 to 0\.5 only partly covers 'pipe_str_0'"):
            field_from_function(
                model, operation, "line_load", lambda x, y, z: 100.0, direction=[0.0, 0.0, -1.0],
                route_id="P-100", station_start=0.0, station_end=0.5,
            )
        self.assertEqual(operation.fields, [])

        rack = _model("Rack")
        with rack.pipe("PipeSec", "Steel", route="RACK") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.run(2.0)
            pipe.bar(2.0)
            pipe.end(support="anchor")
        with self.assertRaisesRegex(ValueError, r"cannot carry 'wind': \['bar_0'\]"):
            field_from_function(
                rack, rack.define_operation("Wind", gravity=False), "wind", lambda x, y, z: 1000.0,
                direction=[0.0, 1.0, 0.0], route_id="RACK",
            )

    def test_bends_without_stored_geometry_have_no_known_midpoint(self):
        model = _elbow_model(stored_geometry=False)
        operation = model.define_operation("Formula", gravity=False)
        with self.assertRaisesRegex(ValueError, "Bend 'elbow' has no stored bend_geometry"):
            field_from_function(model, operation, "pressure", lambda x, y, z: 1.0e6)
        self.assertEqual(operation.fields, [])


class TestFieldFromRouteTable(unittest.TestCase):
    def test_tables_interpolate_by_station_and_refuse_stations_outside_them(self):
        model = _two_element_route()
        operation = model.define_operation("Table", gravity=False)

        pressures = field_from_route_table(model, operation, "pressure", "P-100", [(0.0, 1.0e6), (2.0, 3.0e6)])
        # Element stations are their midpoints, 0.5 and 1.5.
        self.assertEqual(
            [(f.element_ids, f.value) for f in pressures], [(["pipe_str_0"], 1.5e6), (["pipe_str_1"], 2.5e6)]
        )

        with self.assertRaisesRegex(
            ValueError, r"'N2' sits at station 2, outside the table's stations 0 to 1; narrow the selection"
        ):
            field_from_route_table(model, operation, "temperature", "P-100", [(0.0, 100.0), (1.0, 200.0)])
        self.assertEqual(len(operation.fields), 2)

        temperatures = field_from_route_table(
            model, operation, "temperature", "P-100", [(0.0, 100.0), (1.0, 200.0)], station_start=0.0, station_end=1.0
        )
        self.assertEqual([(f.node_ids, f.value) for f in temperatures], [(["N0"], 100.0), (["N1"], 200.0)])

        with self.assertRaisesRegex(ValueError, "strictly increasing stations"):
            field_from_route_table(model, operation, "temperature", "P-100", [(1.0, 100.0), (0.0, 200.0)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_sampling.py -q`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'tuba.sampling'`.

- [ ] **Step 3: Write `tuba/sampling.py`**

```python
"""Put CFD clouds, Python functions and route tables onto operation fields.

Each helper evaluates its source once, in Python, and writes ordinary operation
fields: node temperatures for ``temperature``, and one element field per element
for ``pressure``, ``wind`` and ``line_load``. The model keeps only the numbers the
solver receives, so fingerprints, saved models and reports stay exact.
"""

from __future__ import annotations

import math
from typing import Callable, List, NamedTuple, Optional, Sequence

import numpy as np

from tuba.model import Element, Operation, OperationField, TubaModel, sample_bend_geometry
from tuba.physical import physical_properties_for_element

_QUANTITIES = ("temperature", "pressure", "wind", "line_load")
_DIRECTED = ("wind", "line_load")
# Builder stations are running float sums, so a table ending exactly at a route's last
# station can miss it by float noise; the line-load station check uses the same tolerance.
_STATION_NOISE = 1e-9


class _Target(NamedTuple):
    name: str  # node id for temperature, element id otherwise
    position: np.ndarray
    station: Optional[float]
    elements: tuple[Element, ...]  # the selected elements at this target


def field_from_cloud(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    points,
    values,
    *,
    capture_radius: Optional[float] = None,
    direction: Optional[Sequence[float]] = None,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> List[OperationField]:
    """Average a point cloud onto nodes (temperature) or elements (pressure, wind, line_load).

    A target takes the mean of the values within ``capture_radius`` metres of it, by
    default 1.25 x the largest bare outer radius of the selected elements there, so a
    ring of wall points around a centreline node gives its circumferential mean.
    Targets with no point inside are refused, and then nothing is written.
    """
    targets = _targets(
        model, quantity, direction, group=group, route_id=route_id,
        station_start=station_start, station_end=station_end, element_ids=element_ids,
    )
    cloud = np.asarray(points, dtype=float)
    samples = np.asarray(values, dtype=float)
    if cloud.ndim != 2 or cloud.shape[1] != 3 or cloud.shape[0] == 0 or samples.shape != (cloud.shape[0],):
        raise ValueError("points must have shape (N, 3) and values shape (N,), with N >= 1.")
    if not (np.all(np.isfinite(cloud)) and np.all(np.isfinite(samples))):
        raise ValueError("points and values must be finite.")
    if capture_radius is not None and not (math.isfinite(capture_radius) and capture_radius > 0.0):
        raise ValueError("capture_radius must be a finite distance greater than zero, in metres.")

    sampled: list[tuple[_Target, float]] = []
    missed: list[tuple[_Target, float, float]] = []
    for target in targets:
        radius = capture_radius
        if radius is None:
            radius = 1.25 * max(physical_properties_for_element(model, elem).bare_radius_m for elem in target.elements)
        # ponytail: one target at a time keeps memory at O(points) but time at O(targets x points);
        # switch to a KD-tree if clouds or models outgrow it.
        distances = np.linalg.norm(cloud - target.position, axis=1)
        inside = distances <= radius
        if inside.any():
            sampled.append((target, float(samples[inside].mean())))
        else:
            missed.append((target, float(distances.min()), radius))
    if missed:
        listed = "; ".join(
            f"{target.name!r} nearest point {nearest:.4g} m, radius {radius:.4g} m" for target, nearest, radius in missed[:10]
        )
        more = f"; and {len(missed) - 10} more" if len(missed) > 10 else ""
        raise ValueError(
            f"{len(missed)} target(s) have no cloud point within the capture radius: {listed}{more}. "
            "Check the cloud's units (mm vs m), its coordinate frame and that it covers the selection, "
            "or pass a larger capture_radius."
        )
    return _write(operation, quantity, direction, sampled)


def field_from_function(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    function: Callable[[float, float, float], float],
    *,
    direction: Optional[Sequence[float]] = None,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> List[OperationField]:
    """Evaluate ``function(x, y, z)`` at each node, or at each element's midpoint (arc midpoint on bends)."""
    if not callable(function):
        raise TypeError("function must be a Python callable taking x, y, z; formula strings are not evaluated.")
    sampled: list[tuple[_Target, float]] = []
    for target in _targets(
        model, quantity, direction, group=group, route_id=route_id,
        station_start=station_start, station_end=station_end, element_ids=element_ids,
    ):
        x, y, z = (float(value) for value in target.position)
        value = float(function(x, y, z))
        if not math.isfinite(value):
            raise ValueError(f"function returned {value} at {target.name!r}.")
        sampled.append((target, value))
    return _write(operation, quantity, direction, sampled)


def field_from_route_table(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    route_id: str,
    table: Sequence[Sequence[float]],
    *,
    direction: Optional[Sequence[float]] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
) -> List[OperationField]:
    """Interpolate a ``(station, value)`` table linearly along one route.

    Targets outside the table's stations are refused rather than extrapolated;
    ``station_start`` and ``station_end`` limit the helper to the part the table covers.
    """
    rows = [(float(station), float(value)) for station, value in table]
    stations = np.array([station for station, _ in rows])
    table_values = np.array([value for _, value in rows])
    if (
        len(rows) < 2
        or not (np.all(np.isfinite(stations)) and np.all(np.isfinite(table_values)))
        or np.any(np.diff(stations) <= 0.0)
    ):
        raise ValueError("table needs at least 2 finite (station, value) rows with strictly increasing stations.")
    sampled: list[tuple[_Target, float]] = []
    for target in _targets(
        model, quantity, direction, route_id=route_id, station_start=station_start, station_end=station_end
    ):
        if target.station is None:
            raise ValueError(f"{target.name!r} has no station metadata, so the route table cannot place it.")
        if not stations[0] - _STATION_NOISE <= target.station <= stations[-1] + _STATION_NOISE:
            raise ValueError(
                f"{target.name!r} sits at station {target.station:g}, outside the table's stations "
                f"{stations[0]:g} to {stations[-1]:g}; narrow the selection with station_start/station_end."
            )
        sampled.append((target, float(np.interp(target.station, stations, table_values))))
    return _write(operation, quantity, direction, sampled)


def _targets(
    model: TubaModel,
    quantity: str,
    direction: Optional[Sequence[float]],
    *,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> list[_Target]:
    if quantity not in _QUANTITIES:
        raise ValueError(f"quantity must be one of {', '.join(_QUANTITIES)}; got {quantity!r}.")
    if (direction is None) == (quantity in _DIRECTED):
        raise ValueError(f"{quantity} {'needs a direction' if quantity in _DIRECTED else 'takes no direction'}.")
    # A probe field picks the scope exactly as add_field does, and selection applies the field rules.
    probe = Operation("probe").add_field(
        quantity, 0.0, group=group, route_id=route_id, station_start=station_start,
        station_end=station_end, element_ids=element_ids, direction=direction,
    )
    selected = model.resolve_operation_field_elements(probe)
    if not selected:
        raise ValueError(f"The selection holds no elements that can carry {quantity!r}.")
    if quantity != "temperature":
        return [
            _Target(
                elem.id,
                _midpoint(model, elem),
                None if elem.station_start is None or elem.station_end is None
                else (float(elem.station_start) + float(elem.station_end)) / 2.0,
                (elem,),
            )
            for elem in selected
        ]
    nodes: dict[str, _Target] = {}
    for elem in selected:
        for node_id, station in ((elem.n1, elem.station_start), (elem.n2, elem.station_end)):
            known = nodes.get(node_id)
            if known is None:
                nodes[node_id] = _Target(
                    node_id,
                    np.asarray(model.nodes[node_id].coords, dtype=float),
                    None if station is None else float(station),
                    (elem,),
                )
            else:
                nodes[node_id] = known._replace(
                    station=known.station if known.station is not None else (None if station is None else float(station)),
                    elements=known.elements + (elem,),
                )
    return list(nodes.values())


def _midpoint(model: TubaModel, elem: Element) -> np.ndarray:
    start = np.asarray(model.nodes[elem.n1].coords, dtype=float)
    if elem.type != "pipe_bend":
        return (start + np.asarray(model.nodes[elem.n2].coords, dtype=float)) / 2.0
    if elem.bend_geometry is None:
        raise ValueError(f"Bend {elem.id!r} has no stored bend_geometry, so its arc midpoint is unknown.")
    return sample_bend_geometry(start, elem.bend_geometry, n_segments=2)[1]


def _write(
    operation: Operation,
    quantity: str,
    direction: Optional[Sequence[float]],
    sampled: list[tuple[_Target, float]],
) -> List[OperationField]:
    if quantity == "temperature":
        return [operation.add_field("temperature", value, node_ids=[target.name]) for target, value in sampled]
    return [
        operation.add_field(quantity, value, element_ids=[target.name], direction=direction)
        for target, value in sampled
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_sampling.py tests/test_node_temperatures.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add tuba/sampling.py tests/test_sampling.py
git commit -m "feat(sampling): write operation fields from CFD clouds, Python functions and route tables"
```

### Task 4: Real Code_Aster reference and docs

**Files:**
- Create: `tests/test_code_aster_node_temperatures.py`
- Modify: `docs/content/modeling.md` (a new section right before `## Schemas and serialized models`)
- Modify: `CONTEXT.md` (after the **Wind load** entry)
- Modify: `docs/architecture/library-architecture-review.md:136-141`, `:323`, `:379-380`

**Interfaces:**
- Consumes: `field_from_function` (Task 3), and the compiler's node temperatures (Task 2).

- [ ] **Step 1: Write the reference test**

Create `tests/test_code_aster_node_temperatures.py`:

```python
"""Real Code_Aster reference: node temperatures reach every solver node, generated ones included.

A cantilever held at one end expands freely, so its tip moves by
alpha * integral of (T - T_ref) t(s) ds along the centreline, with t the unit tangent.
That integral needs the temperature at every solver node. If the TUYAU midside of the
4 m run kept the 20 degree base, Simpson's rule over its three nodes would give the run
4/6 * (100 + 0 + 180) = 187 instead of 560 degree-metres, so the check would fail.
"""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.model import BendGeometry
from tuba.sampling import field_from_function

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster node-temperature reference",
)

ALPHA = 1.2e-5
T_REF = 20.0
RUN_LENGTH = 4.0
BEND_RADIUS = 0.5


def cantilever(name: str) -> tuple[Model, str]:
    """A 4 m straight along X into a 90 degree elbow turning to Y, anchored at the start only."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=ALPHA)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([RUN_LENGTH, 0.0, 0.0])
    tip = model.add_node([RUN_LENGTH + BEND_RADIUS, BEND_RADIUS, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="Pipe", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=tip, section="Pipe", material="Steel",
        bend_radius=BEND_RADIUS, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[RUN_LENGTH, BEND_RADIUS, 0.0], normal=[0.0, 0.0, 1.0], radius=BEND_RADIUS, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    return model, tip


def temperature(x: float, y: float, z: float) -> float:
    """120 degrees at the anchor, 200 at the corner, 260 at the tip."""
    return 120.0 + 20.0 * x + 100.0 * y


def free_expansion(t_start: float, t_corner: float, t_tip: float) -> np.ndarray:
    """Tip displacement: alpha * integral of (T - T_ref) t(s) ds, with T linear along each element."""
    run = RUN_LENGTH * ((t_start + t_corner) / 2.0 - T_REF) * np.array([1.0, 0.0, 0.0])
    # Along the elbow theta runs 0 to pi/2, t = (cos theta, sin theta, 0) and T - T_ref = d + slope * theta.
    # The integral of (d + slope*theta) cos(theta) is d + slope*(pi/2 - 1); with sin(theta) it is d + slope.
    d, slope = t_corner - T_REF, (t_tip - t_corner) / (math.pi / 2.0)
    elbow = BEND_RADIUS * np.array([d + slope * (math.pi / 2.0 - 1.0), d + slope, 0.0])
    return ALPHA * (run + elbow)


@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_node_temperatures_expand_the_whole_cantilever(modelization):
    model, tip = cantilever(f"NodeTemperatures {modelization}")
    operation = model.define_operation("Hot", gravity=False, temperature=T_REF, ref_temperature=T_REF)
    written = field_from_function(model, operation, "temperature", temperature)
    assert [(field.node_ids, field.value) for field in written] == [(["N0"], 120.0), (["N1"], 200.0), (["N2"], 260.0)]

    root = Path(f".build/node-temperature-references/{modelization}").resolve()
    run = model.solve("Hot", pipe_modelization=modelization, work_dir=str(root), force=True)

    observed = np.asarray(run.results.node_results[tip].displacement[:3], dtype=float)
    expected = free_expansion(120.0, 200.0, 260.0)
    print(f"node temperatures {modelization}: tip {observed.tolist()}, expected {expected.tolist()}")
    assert float(np.linalg.norm(observed - expected)) <= 0.01 * float(np.linalg.norm(expected))
```

- [ ] **Step 2: Solve the references with the real runtime**

Run: `$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"; & D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_code_aster_node_temperatures.py -q -s`

Expected: `2 passed`. The printed tip is about `[7.93e-03, 1.31e-03, 0.0]` m on both modelizations.

If a check fails:
- Do not loosen the 1% tolerance and do not change `free_expansion`.
- Read `.build/node-temperature-references/<modelization>/study.comm` (the `TEMP_FIELD` block) and the Code_Aster message file there.
- Then report what you found with the observed and expected vectors.

Afterwards, run `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_code_aster_node_temperatures.py -q` without the variable (in a fresh shell, or after `Remove-Item Env:TUBA_RUN_CODE_ASTER_INTEGRATION`). Expected: `2 skipped`.

- [ ] **Step 3: User docs**

In `docs/content/modeling.md`, insert this section directly before the line `## Schemas and serialized models`:

````markdown
## Operation temperatures and sampled fields

An operation sets one temperature for the whole model, and operation fields change it locally. An element field gives whole elements one value. It selects them by `element_ids`, by a route with an optional station range, by a group, or all pipe elements:

```python
hot = model.define_operation("Hot", temperature=20.0, ref_temperature=20.0)
hot.add_field("temperature", 180.0, route_id="P-100", station_start=0.0, station_end=12.0)
```

Each element then holds a single temperature, so a profile along a route becomes a staircase. A node temperature gives a model node its own value instead:

```python
hot.add_field("temperature", 180.0, node_ids=["N3", "N4"])
```

Every element that touches a node temperature varies linearly between its two end values:

- Code_Aster receives a value at each of that element's solver nodes. These include bend, subdivision and `TUYAU_3M` midside nodes that the model does not have.
- An end without a node temperature keeps what the rest of the operation gives it.
- A node cannot have a node temperature and also belong to an element that an element temperature field covers. Validation names such nodes.

`tuba.sampling` turns a source into these fields once, so the saved model holds only the numbers the solver receives:

| Helper | Source |
| --- | --- |
| `field_from_cloud(model, operation, quantity, points, values)` | A CFD point cloud, averaged within a capture radius |
| `field_from_function(model, operation, quantity, function)` | A Python callable `function(x, y, z)` |
| `field_from_route_table(model, operation, quantity, route_id, table)` | `(station, value)` rows along one route |

What the helpers write depends on the quantity:

- For `temperature` they write node temperatures.
- For `pressure`, `wind` and `line_load` they write one field per element, evaluated at its midpoint. Wind and line loads also need `direction=`.
- `group=`, `route_id=`, `station_start=`, `station_end=` and `element_ids=` select targets as they do for `add_field`.

```python
import numpy as np
from tuba.sampling import field_from_cloud

cloud = np.loadtxt("wall_temperature.csv", delimiter=",", skiprows=1)  # x, y, z in metres, then T in degrees C
field_from_cloud(model, hot, "temperature", cloud[:, :3], cloud[:, 3])
model.validate()
```

A cloud value is the mean of the points within the capture radius:

- The default radius is 1.25 times the pipe's bare outer radius, so wall points around a centreline node give its circumferential mean.
- A node or element with no point inside is refused, and the error lists the nearest distances. Check the cloud's units, coordinate frame and coverage, or pass `capture_radius=`.
- A refused call writes nothing.

````

In `CONTEXT.md`, insert this entry after the **Wind load** entry (its `_Avoid_: Line load` line) and before **Solver result**, with one blank line on each side:

```markdown
**Node temperature**:
An operation temperature given to one model node; each element touching the node varies linearly between its end values, at every solver node.
_Avoid_: Element temperature, nodal field
```

In `docs/architecture/library-architecture-review.md`, make three edits.

1. Replace:

```markdown
`CREA_CHAMP`. Non-uniform pressure, non-uniform wind, and piecewise profiles
still fail validation before export.
```

with:

```markdown
`CREA_CHAMP`. Non-uniform pressure, non-uniform wind, and piecewise profiles
still fail validation before export.
Temperature fields can also be scoped to nodes (`node_ids`). The writer then
gives every solver node of each touched element a `GROUP_NO` value in the same
`CREA_CHAMP`, interpolated along the element, including generated bend,
subdivision and `TUYAU_3M` midside nodes. `tuba.sampling` writes such fields,
and per-element pressure, wind and line-load fields, from CFD clouds, Python
functions and route tables.
```

2. Replace `Creates temperature fields for uniform and route/station-linear thermal expansion.` with:

```markdown
Creates temperature fields for uniform, route/station-linear and node-scoped thermal expansion: `GROUP_MA` rows per element, then `GROUP_NO` rows per solver node.
```

3. Replace:

```markdown
- Local uniform pressure and temperature fields compiled into Code_Aster mesh
  groups.
```

with:

```markdown
- Local uniform pressure and temperature fields compiled into Code_Aster mesh
  groups.
- Node temperatures compiled into per-solver-node `GROUP_NO` values,
  interpolated along each touched element; `tuba.sampling` builds fields from
  CFD clouds, Python functions and route tables.
```

- [ ] **Step 4: Run the docs tests**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest tests/test_static_site_docs.py -q`
Expected: all pass. The JSON sample under "Schemas and serialized models" is still the first `json` block after that heading.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_code_aster_node_temperatures.py docs/content/modeling.md CONTEXT.md docs/architecture/library-architecture-review.md
git commit -m "test(solver): solve node temperatures on a free cantilever and document sampled fields"
```

- [ ] **Step 6: Full suite**

Run: `& D:\Gitprojects\Tuba_v4\.venv\Scripts\python.exe -m pytest -q` (about 20 minutes).
Expected: everything passes except the two known `test_package_release` vite build tests. Report the pass/skip/fail counts.
