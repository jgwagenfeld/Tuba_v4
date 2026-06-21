# Model Fragments And Transactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable local-coordinate model fragments, explicit coordinate-system placement, transactional model mutation, and schema-ready interfaces for future GUI and agent workflows.

**Architecture:** Keep `TubaModel` as the solver-facing source of truth, but stop making every creator mutate it directly. Builders and routers should produce model patches or local `ModelFragment` objects; parent models apply those through one transaction seam. Coordinate-system placement becomes a first-class operation that can later support GUI groups, agent-generated assemblies, and repeated subassembly instances.

**Tech Stack:** Python dataclasses, `numpy`, existing `unittest` test style, existing `jsonschema` dependency, PyVista for current visualization adapters.

---

## Scope

This plan implements the direct system first:

- Define structures in a local coordinate system.
- Treat them as named groups or fragments.
- Place them into a parent model using an explicit coordinate system.
- Keep solver export compatible by flattening placed geometry into normal `nodes`, `elements`, and `supports`.

Then it adds the general architecture needed for agents and GUIs:

- Transactional mutation and rollback.
- Validation and schema checks.
- Provenance and group metadata.
- Scene-first visualization adapters.

## Files To Create Or Modify

- Create `tuba/coordinates.py`  
  Owns `CoordinateSystem` and point/vector transform behavior.

- Create `tuba/validation.py`  
  Owns model integrity checks: references, finite coordinates, duplicate IDs, dimensions, supports, groups.

- Create `tuba/patches.py`  
  Owns `ModelPatch`, mutation operations, `ModelTransaction`, and rollback behavior.

- Create `tuba/fragments.py`  
  Owns `ModelFragment`, `FragmentPlacement`, `PlacementResult`, and placement/merge behavior.

- Create `tuba/schema.py`  
  Owns JSON Schema dictionaries and schema validation helpers for model and patch contracts.

- Create `tuba/visualizer/scenes.py`  
  Owns scene-construction functions returning PyVista plotters without showing them.

- Modify `tuba/model.py`  
  Add group/placement metadata, validation hooks, serialization support, `place_fragment()`, and transaction helpers.

- Modify `tuba/builder.py`  
  Make builder usable for fragments through the same existing `PipingBuilder` class.

- Modify `tuba/routing/adapter.py`  
  Split route candidate mutation into `build_candidate_patch()` plus a compatibility `apply_candidate_to_model()`.

- Modify `tuba/routing/solver_loop.py`  
  Use the patch/transaction seam when applying candidate geometry to scratch models.

- Modify `tuba/visualizer/plots.py`  
  Reuse scene-first functions and keep old public plotting functions as compatibility wrappers.

- Modify `tuba/__init__.py`  
  Export the new public interfaces.

- Create `tests/test_coordinates.py`
- Create `tests/test_validation.py`
- Create `tests/test_patches.py`
- Create `tests/test_fragments.py`
- Create `tests/test_schema.py`
- Create `tests/test_visualizer_scenes.py`
- Modify `tests/test_routing_adapter.py`
- Modify `tests/test_tuba_core.py`

Use this command for the full test baseline after every task:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected output:

```text
Ran 48+ tests
OK
```

---

### Task 1: Add CoordinateSystem

**Files:**
- Create: `tuba/coordinates.py`
- Create: `tests/test_coordinates.py`
- Modify: `tuba/__init__.py`

- [ ] **Step 1: Write tests for coordinate transforms**

Create `tests/test_coordinates.py`:

```python
import unittest

import numpy as np

from tuba.coordinates import CoordinateSystem


class TestCoordinateSystem(unittest.TestCase):
    def test_identity_transform_keeps_point(self):
        cs = CoordinateSystem.identity()
        self.assertTrue(np.allclose(cs.to_global_point((1.0, 2.0, 3.0)), (1.0, 2.0, 3.0)))

    def test_translation_and_rotation_transform_point(self):
        cs = CoordinateSystem(
            origin=(10.0, 20.0, 30.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        point = cs.to_global_point((2.0, 3.0, 4.0))

        self.assertTrue(np.allclose(point, (7.0, 22.0, 34.0)))

    def test_inverse_roundtrip(self):
        cs = CoordinateSystem(
            origin=(4.0, -2.0, 1.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
            z_axis=(1.0, 0.0, 0.0),
        )

        local = np.array((1.5, 2.5, -3.0))
        global_point = cs.to_global_point(local)
        roundtrip = cs.to_local_point(global_point)

        self.assertTrue(np.allclose(roundtrip, local))

    def test_non_orthogonal_axes_are_rejected(self):
        with self.assertRaises(ValueError):
            CoordinateSystem(
                origin=(0.0, 0.0, 0.0),
                x_axis=(1.0, 0.0, 0.0),
                y_axis=(1.0, 0.0, 0.0),
                z_axis=(0.0, 0.0, 1.0),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_coordinates -v
```

Expected:

```text
ImportError: No module named 'tuba.coordinates'
```

- [ ] **Step 3: Implement `CoordinateSystem`**

Create `tuba/coordinates.py`:

```python
"""Coordinate-system utilities for reusable model fragments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


VectorLike = Sequence[float] | np.ndarray


@dataclass(frozen=True)
class CoordinateSystem:
    """Right-handed local coordinate system embedded in global coordinates."""

    origin: VectorLike
    x_axis: VectorLike = (1.0, 0.0, 0.0)
    y_axis: VectorLike = (0.0, 1.0, 0.0)
    z_axis: VectorLike = (0.0, 0.0, 1.0)
    tolerance: float = 1e-9

    def __post_init__(self) -> None:
        origin = _as_vector(self.origin, "origin")
        x_axis = _unit(self.x_axis, "x_axis")
        y_axis = _unit(self.y_axis, "y_axis")
        z_axis = _unit(self.z_axis, "z_axis")

        if abs(float(np.dot(x_axis, y_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: x_axis dot y_axis is not zero.")
        if abs(float(np.dot(x_axis, z_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: x_axis dot z_axis is not zero.")
        if abs(float(np.dot(y_axis, z_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: y_axis dot z_axis is not zero.")

        handedness = float(np.dot(np.cross(x_axis, y_axis), z_axis))
        if handedness <= 0.0:
            raise ValueError("CoordinateSystem axes must form a right-handed basis.")

        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)
        object.__setattr__(self, "z_axis", z_axis)

    @classmethod
    def identity(cls) -> "CoordinateSystem":
        return cls(origin=(0.0, 0.0, 0.0))

    @property
    def basis(self) -> np.ndarray:
        return np.column_stack([self.x_axis, self.y_axis, self.z_axis])

    def to_global_point(self, point: VectorLike) -> np.ndarray:
        local = _as_vector(point, "point")
        return np.asarray(self.origin, dtype=float) + self.basis @ local

    def to_global_vector(self, vector: VectorLike) -> np.ndarray:
        local = _as_vector(vector, "vector")
        return self.basis @ local

    def to_local_point(self, point: VectorLike) -> np.ndarray:
        global_point = _as_vector(point, "point")
        return self.basis.T @ (global_point - np.asarray(self.origin, dtype=float))

    def to_dict(self) -> dict:
        return {
            "origin": np.asarray(self.origin, dtype=float).tolist(),
            "x_axis": np.asarray(self.x_axis, dtype=float).tolist(),
            "y_axis": np.asarray(self.y_axis, dtype=float).tolist(),
            "z_axis": np.asarray(self.z_axis, dtype=float).tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CoordinateSystem":
        return cls(
            origin=data["origin"],
            x_axis=data.get("x_axis", (1.0, 0.0, 0.0)),
            y_axis=data.get("y_axis", (0.0, 1.0, 0.0)),
            z_axis=data.get("z_axis", (0.0, 0.0, 1.0)),
        )


def _as_vector(value: VectorLike, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"{name} must contain exactly three numeric values.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite numeric values.")
    return arr


def _unit(value: VectorLike, name: str) -> np.ndarray:
    arr = _as_vector(value, name)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{name} must not be the zero vector.")
    return arr / norm
```

- [ ] **Step 4: Export from `tuba/__init__.py`**

Modify `tuba/__init__.py`:

```python
from tuba.coordinates import CoordinateSystem
```

Add `"CoordinateSystem"` to `__all__`.

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_coordinates -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/coordinates.py tuba/__init__.py tests/test_coordinates.py
git commit -m "feat: add coordinate systems"
```

---

### Task 2: Add Model Validation

**Files:**
- Create: `tuba/validation.py`
- Create: `tests/test_validation.py`
- Modify: `tuba/model.py`
- Modify: `tuba/__init__.py`

- [ ] **Step 1: Write validation tests**

Create `tests/test_validation.py`:

```python
import unittest

from tuba import Model
from tuba.validation import ModelValidationError, validate_model


class TestModelValidation(unittest.TestCase):
    def test_valid_model_passes(self):
        model = Model(project_name="Valid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        model.add_element(
            id="pipe_str_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )

        validate_model(model)

    def test_missing_node_reference_fails(self):
        model = Model(project_name="Invalid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        model.add_element(
            id="pipe_str_0",
            type="pipe_straight",
            n1=n0,
            n2="N999",
            section="PipeSec",
            material="Steel",
        )

        with self.assertRaises(ModelValidationError) as ctx:
            validate_model(model)

        self.assertIn("references missing node", str(ctx.exception))

    def test_duplicate_element_id_fails(self):
        model = Model(project_name="Invalid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        kwargs = {
            "id": "pipe_str_0",
            "type": "pipe_straight",
            "n1": n0,
            "n2": n1,
            "section": "PipeSec",
            "material": "Steel",
        }
        model.add_element(**kwargs)
        model.add_element(**kwargs)

        with self.assertRaises(ModelValidationError) as ctx:
            validate_model(model)

        self.assertIn("Duplicate element id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_validation -v
```

Expected:

```text
ImportError: No module named 'tuba.validation'
```

- [ ] **Step 3: Implement `validate_model`**

Create `tuba/validation.py`:

```python
"""Validation helpers for Tuba models."""

from __future__ import annotations

from collections import Counter

import numpy as np

from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection, TubaModel


class ModelValidationError(ValueError):
    """Raised when a model violates structural invariants."""


def validate_model(model: TubaModel) -> None:
    errors: list[str] = []

    for node_id, node in model.nodes.items():
        coords = np.asarray(node.coords, dtype=float)
        if coords.shape != (3,) or not np.all(np.isfinite(coords)):
            errors.append(f"Node {node_id!r} has invalid coordinates.")

    element_ids = [elem.id for elem in model.elements]
    for elem_id, count in Counter(element_ids).items():
        if count > 1:
            errors.append(f"Duplicate element id {elem_id!r}.")

    for elem in model.elements:
        if elem.n1 not in model.nodes:
            errors.append(f"Element {elem.id!r} references missing node {elem.n1!r}.")
        if elem.n2 not in model.nodes:
            errors.append(f"Element {elem.id!r} references missing node {elem.n2!r}.")
        if elem.section not in model.sections:
            errors.append(f"Element {elem.id!r} references missing section {elem.section!r}.")
        if elem.material not in model.materials:
            errors.append(f"Element {elem.id!r} references missing material {elem.material!r}.")
        if elem.n1 == elem.n2:
            errors.append(f"Element {elem.id!r} has identical start and end nodes.")

    for support in model.supports:
        if support.node not in model.nodes:
            errors.append(f"Support references missing node {support.node!r}.")

    for name, section in model.sections.items():
        _validate_section(name, section, errors)

    for group_name, group in getattr(model, "groups", {}).items():
        for node_id in group.get("nodes", []):
            if node_id not in model.nodes:
                errors.append(f"Group {group_name!r} references missing node {node_id!r}.")
        for element_id in group.get("elements", []):
            if element_id not in element_ids:
                errors.append(f"Group {group_name!r} references missing element {element_id!r}.")

    if errors:
        raise ModelValidationError("\n".join(errors))


def _validate_section(name: str, section, errors: list[str]) -> None:
    if isinstance(section, PipeSection):
        if section.OD <= 0.0:
            errors.append(f"Pipe section {name!r} OD must be positive.")
        if section.WT <= 0.0:
            errors.append(f"Pipe section {name!r} WT must be positive.")
        if section.WT * 2.0 >= section.OD:
            errors.append(f"Pipe section {name!r} WT is too large for OD.")
    elif isinstance(section, BarSection):
        if section.OD <= 0.0:
            errors.append(f"Bar section {name!r} OD must be positive.")
    elif isinstance(section, CableSection):
        if section.radius <= 0.0:
            errors.append(f"Cable section {name!r} radius must be positive.")
    elif isinstance(section, RectangularSection):
        if section.height_y <= 0.0 or section.height_z <= 0.0:
            errors.append(f"Rectangular section {name!r} dimensions must be positive.")
    elif isinstance(section, IBeamSection):
        if not section.profile_name:
            errors.append(f"I-beam section {name!r} profile_name must not be empty.")
    else:
        errors.append(f"Section {name!r} has unsupported type {type(section).__name__}.")
```

- [ ] **Step 4: Add model convenience method**

Modify `TubaModel` in `tuba/model.py`:

```python
    def validate(self) -> None:
        """Validate model references and structural invariants."""
        from tuba.validation import validate_model

        validate_model(self)
```

Place the method before `to_dict()`.

- [ ] **Step 5: Export from `tuba/__init__.py`**

Add:

```python
from tuba.validation import ModelValidationError, validate_model
```

Add `"ModelValidationError"` and `"validate_model"` to `__all__`.

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_validation -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add tuba/validation.py tuba/model.py tuba/__init__.py tests/test_validation.py
git commit -m "feat: add model validation"
```

---

### Task 3: Add ModelPatch And ModelTransaction

**Files:**
- Create: `tuba/patches.py`
- Create: `tests/test_patches.py`
- Modify: `tuba/__init__.py`

- [ ] **Step 1: Write transaction tests**

Create `tests/test_patches.py`:

```python
import unittest

from tuba import Model
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction


class TestModelPatch(unittest.TestCase):
    def test_patch_applies_nodes_elements_and_supports(self):
        model = Model(project_name="Patch")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="e0",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                AddSupport(node="a", type="anchor"),
            ]
        )

        result = ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 2)
        self.assertEqual(len(model.elements), 1)
        self.assertEqual(len(model.supports), 1)
        self.assertIn("a", result.node_ids)
        self.assertIn("e0", result.element_ids)

    def test_patch_rolls_back_on_invalid_element_reference(self):
        model = Model(project_name="Rollback")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddElement(
                    local_id="bad",
                    type="pipe_straight",
                    n1="a",
                    n2="missing",
                    section="PipeSec",
                    material="Steel",
                ),
            ]
        )

        with self.assertRaises(ValueError):
            ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patches -v
```

Expected:

```text
ImportError: No module named 'tuba.patches'
```

- [ ] **Step 3: Implement patches**

Create `tuba/patches.py`:

```python
"""Transactional model patches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from tuba.model import TubaModel
from tuba.validation import validate_model


@dataclass(frozen=True)
class AddNode:
    local_id: str
    coords: Sequence[float]
    reuse_existing: bool = True
    tolerance: float = 1e-6


@dataclass(frozen=True)
class AddElement:
    local_id: str
    type: str
    n1: str
    n2: str
    section: str
    material: str
    bend_radius: float | None = None
    bend_angle: float | None = None
    twist_angle: float = 0.0
    id_prefix: str | None = None


@dataclass(frozen=True)
class AddSupport:
    node: str
    type: str
    direction: list[float] | None = None
    stiffness: float | None = None
    imposed_displacement: list[float] | None = None
    stiffness_matrix: list[float] | None = None
    blocked_dof: list[Any] | None = None
    mass: float = 0.0
    friction_coefficient: float = 0.0


PatchOperation = AddNode | AddElement | AddSupport


@dataclass(frozen=True)
class ModelPatch:
    operations: list[PatchOperation] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatchResult:
    node_ids: dict[str, str] = field(default_factory=dict)
    element_ids: dict[str, str] = field(default_factory=dict)
    support_count: int = 0


class ModelTransaction:
    """Apply patches atomically to a TubaModel."""

    def __init__(self, model: TubaModel):
        self.model = model

    def apply(self, patch: ModelPatch, *, validate: bool = True) -> PatchResult:
        snapshot = self.model.to_dict()
        result = PatchResult()
        try:
            for operation in patch.operations:
                if isinstance(operation, AddNode):
                    node_id = self._apply_add_node(operation)
                    result.node_ids[operation.local_id] = node_id
                elif isinstance(operation, AddElement):
                    elem_id = self._apply_add_element(operation, result.node_ids)
                    result.element_ids[operation.local_id] = elem_id
                elif isinstance(operation, AddSupport):
                    self._apply_add_support(operation, result.node_ids)
                    result.support_count += 1
                else:
                    raise TypeError(f"Unsupported patch operation {type(operation).__name__}.")
            if validate:
                validate_model(self.model)
            return result
        except Exception:
            restored = TubaModel.from_dict(snapshot)
            self.model.__dict__.clear()
            self.model.__dict__.update(restored.__dict__)
            raise

    def _apply_add_node(self, operation: AddNode) -> str:
        if operation.reuse_existing:
            from tuba.routing.adapter import _node_for_point

            return _node_for_point(self.model, tuple(float(v) for v in operation.coords), tol=operation.tolerance)
        return self.model.add_node(operation.coords)

    def _apply_add_element(self, operation: AddElement, node_ids: dict[str, str]) -> str:
        n1 = node_ids.get(operation.n1, operation.n1)
        n2 = node_ids.get(operation.n2, operation.n2)
        prefix = operation.id_prefix or _prefix_for_element_type(operation.type)
        elem_id = self.model.next_element_id(prefix)
        self.model.add_element(
            id=elem_id,
            type=operation.type,
            n1=n1,
            n2=n2,
            section=operation.section,
            material=operation.material,
            bend_radius=operation.bend_radius,
            bend_angle=operation.bend_angle,
            twist_angle=operation.twist_angle,
        )
        return elem_id

    def _apply_add_support(self, operation: AddSupport, node_ids: dict[str, str]) -> None:
        node = node_ids.get(operation.node, operation.node)
        self.model.add_support(
            node=node,
            type=operation.type,
            direction=operation.direction,
            stiffness=operation.stiffness,
            imposed_displacement=operation.imposed_displacement,
            stiffness_matrix=operation.stiffness_matrix,
            blocked_dof=operation.blocked_dof,
            mass=operation.mass,
            friction_coefficient=operation.friction_coefficient,
        )


def _prefix_for_element_type(element_type: str) -> str:
    if element_type == "pipe_bend":
        return "pipe_bend"
    if element_type == "beam":
        return "beam"
    if element_type == "bar":
        return "bar"
    if element_type == "cable":
        return "cable"
    return "pipe_str"
```

- [ ] **Step 4: Export from `tuba/__init__.py`**

Add imports:

```python
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction, PatchResult
```

Add these names to `__all__`.

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patches -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/patches.py tuba/__init__.py tests/test_patches.py
git commit -m "feat: add transactional model patches"
```

---

### Task 4: Refactor Route Candidate Application To Patches

**Files:**
- Modify: `tuba/routing/adapter.py`
- Modify: `tuba/routing/solver_loop.py`
- Modify: `tests/test_routing_adapter.py`

- [ ] **Step 1: Add tests for route patch creation and rollback**

Append to `tests/test_routing_adapter.py`:

```python
    def test_build_candidate_patch_does_not_mutate_model(self):
        model = Model(project_name="PatchRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=build_segments([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], request.constraints),
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )

        from tuba.routing.adapter import build_candidate_patch

        patch = build_candidate_patch(model, candidate, request)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)
        self.assertGreaterEqual(len(patch.operations), 3)

    def test_apply_candidate_rolls_back_on_invalid_bend(self):
        model = Model(project_name="RollbackRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(0.2, 0.2, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(min_bend_radius=1.0),
        )
        points = [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.2, 0.2, 0.0)]
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=0.4,
            cost_breakdown={"length": 0.4, "bends": 1},
        )

        with self.assertRaises(ValueError):
            apply_candidate_to_model(model, candidate, request)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter -v
```

Expected:

```text
ImportError: cannot import name 'build_candidate_patch'
```

- [ ] **Step 3: Add `build_candidate_patch()`**

In `tuba/routing/adapter.py`, add imports:

```python
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction
```

Add this public function above `apply_candidate_to_model()`:

```python
def build_candidate_patch(
    model: TubaModel,
    candidate: PipeRouteCandidate,
    request: PipeRouteRequest,
    *,
    add_supports: bool = False,
    support_spacing: float | None = None,
) -> ModelPatch:
    """Build a mutation patch for a route candidate without mutating model."""
    if len(candidate.points) < 2:
        return ModelPatch(provenance={"request_id": request.id, "candidate_points": len(candidate.points)})

    operations = []
    created_node_names: list[str] = []
    support_points: list[Point3D] = [candidate.points[0]]
    support_node_names: list[str] = []

    current_point = np.asarray(candidate.points[0], dtype=float)
    current_name = "route_node_0"
    operations.append(AddNode(local_id=current_name, coords=candidate.points[0]))
    created_node_names.append(current_name)
    support_node_names.append(current_name)

    element_index = 0
    node_index = 1
    for idx in range(1, len(candidate.points) - 1):
        corner = np.asarray(candidate.points[idx], dtype=float)
        nxt = np.asarray(candidate.points[idx + 1], dtype=float)
        in_vec = corner - current_point
        out_vec = nxt - corner
        in_len = float(np.linalg.norm(in_vec))
        out_len = float(np.linalg.norm(out_vec))
        if in_len <= 1e-9 or out_len <= 1e-9:
            continue

        in_dir = in_vec / in_len
        out_dir = out_vec / out_len
        angle = _turn_angle_degrees(in_dir, out_dir)
        if angle <= 1e-6:
            continue

        bend_segment = _bend_segment_for_corner(candidate.segments, candidate.points[idx])
        radius = _bend_radius(model, request, bend_segment)
        tangent = radius * math.tan(math.radians(angle) / 2.0)
        if tangent >= in_len - 1e-9 or tangent >= out_len - 1e-9:
            raise ValueError(
                f"Route bend at {candidate.points[idx]!r} needs tangent length "
                f"{tangent:.6g}, but adjacent straight lengths are {in_len:.6g} and {out_len:.6g}."
            )

        bend_entry = _as_point(corner - in_dir * tangent)
        bend_exit = _as_point(corner + out_dir * tangent)

        entry_name = f"route_node_{node_index}"
        node_index += 1
        operations.append(AddNode(local_id=entry_name, coords=bend_entry))
        operations.append(
            AddElement(
                local_id=f"route_element_{element_index}",
                type="pipe_straight",
                n1=current_name,
                n2=entry_name,
                section=request.section,
                material=request.material,
                id_prefix="pipe_str",
            )
        )
        element_index += 1
        support_points.append(bend_entry)
        support_node_names.append(entry_name)

        exit_name = f"route_node_{node_index}"
        node_index += 1
        operations.append(AddNode(local_id=exit_name, coords=bend_exit))
        operations.append(
            AddElement(
                local_id=f"route_element_{element_index}",
                type="pipe_bend",
                n1=entry_name,
                n2=exit_name,
                section=request.section,
                material=request.material,
                bend_radius=radius,
                bend_angle=angle,
                id_prefix="pipe_bend",
            )
        )
        element_index += 1
        support_points.append(bend_exit)
        support_node_names.append(exit_name)
        current_point = np.asarray(bend_exit, dtype=float)
        current_name = exit_name

    end_name = f"route_node_{node_index}"
    operations.append(AddNode(local_id=end_name, coords=candidate.points[-1]))
    operations.append(
        AddElement(
            local_id=f"route_element_{element_index}",
            type="pipe_straight",
            n1=current_name,
            n2=end_name,
            section=request.section,
            material=request.material,
            id_prefix="pipe_str",
        )
    )
    support_points.append(candidate.points[-1])
    support_node_names.append(end_name)

    if add_supports and support_spacing:
        operations.extend(_support_operations(support_points, support_node_names, support_spacing))

    return ModelPatch(
        operations=operations,
        provenance={"request_id": request.id, "candidate_points": len(candidate.points)},
    )
```

Add this helper near `_add_simple_supports()`:

```python
def _support_operations(
    points: list[Point3D],
    node_names: list[str],
    support_spacing: float,
) -> list[AddSupport]:
    operations: list[AddSupport] = []
    if support_spacing <= 0:
        return operations
    running = 0.0
    for idx in range(1, len(points) - 1):
        prev = np.asarray(points[idx - 1], dtype=float)
        cur = np.asarray(points[idx], dtype=float)
        running += float(np.linalg.norm(cur - prev))
        if running >= support_spacing:
            operations.append(AddSupport(node=node_names[idx], type="rest"))
            running = 0.0
    return operations
```

- [ ] **Step 4: Change `apply_candidate_to_model()` to use transaction**

Replace the body of `apply_candidate_to_model()` with:

```python
    patch = build_candidate_patch(
        model,
        candidate,
        request,
        add_supports=add_supports,
        support_spacing=support_spacing,
    )
    result = ModelTransaction(model).apply(patch)
    created = list(result.element_ids.values())
    candidate.metadata["created_element_ids"] = created
    return created
```

Keep the metadata line for backward compatibility. New agent/GUI code should use `build_candidate_patch()` and `ModelTransaction` directly.

- [ ] **Step 5: Update solver loop to use the new seam**

In `tuba/routing/solver_loop.py`, keep behavior identical but replace direct candidate mutation with the compatibility function for now. No public behavior change is expected in this task. The next performance task can replace deep copies after this seam exists.

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add tuba/routing/adapter.py tuba/routing/solver_loop.py tests/test_routing_adapter.py
git commit -m "feat: build route candidates as patches"
```

---

### Task 5: Add ModelFragment And Placement

**Files:**
- Create: `tuba/fragments.py`
- Create: `tests/test_fragments.py`
- Modify: `tuba/model.py`
- Modify: `tuba/__init__.py`

- [ ] **Step 1: Write fragment placement tests**

Create `tests/test_fragments.py`:

```python
import unittest

import numpy as np

from tuba import CoordinateSystem, Model
from tuba.fragments import ModelFragment, place_fragment


class TestModelFragment(unittest.TestCase):
    def test_fragment_places_local_geometry_into_parent_coordinate_system(self):
        fragment = ModelFragment("rack_template")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0], support="anchor")
            b.run(2.0)

        parent = Model(project_name="Parent")
        parent.add_material("Steel", E=2.0e11, nu=0.3)
        parent.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        placement = CoordinateSystem(
            origin=(10.0, 20.0, 0.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        result = place_fragment(parent, fragment, placement, name="rack_A")

        coords = [node.coords for node in parent.nodes.values()]
        self.assertTrue(any(np.allclose(coord, (10.0, 20.0, 0.0)) for coord in coords))
        self.assertTrue(any(np.allclose(coord, (10.0, 22.0, 0.0)) for coord in coords))
        self.assertEqual(len(parent.elements), 1)
        self.assertIn("rack_A", parent.groups)
        self.assertEqual(result.group_name, "rack_A")

    def test_same_fragment_can_be_placed_twice(self):
        fragment = ModelFragment("pipe_module")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        parent = Model(project_name="Parent")
        parent.add_material("Steel", E=2.0e11, nu=0.3)
        parent.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        place_fragment(parent, fragment, CoordinateSystem(origin=(0.0, 0.0, 0.0)), name="pipe_A")
        place_fragment(parent, fragment, CoordinateSystem(origin=(0.0, 5.0, 0.0)), name="pipe_B")

        self.assertEqual(len(parent.elements), 2)
        self.assertIn("pipe_A", parent.groups)
        self.assertIn("pipe_B", parent.groups)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fragments -v
```

Expected:

```text
ImportError: No module named 'tuba.fragments'
```

- [ ] **Step 3: Add group storage to `TubaModel`**

Modify `TubaModel.__init__()` in `tuba/model.py`:

```python
        self.groups: Dict[str, Dict[str, Any]] = {}
```

Modify `to_dict()` to include:

```python
            "groups": self.groups,
```

Modify `from_dict()` before `return model`:

```python
        model.groups = data.get("groups", {})
```

- [ ] **Step 4: Implement fragments**

Create `tuba/fragments.py`:

```python
"""Reusable local-coordinate model fragments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.coordinates import CoordinateSystem
from tuba.model import TubaModel
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction


@dataclass
class ModelFragment:
    """A reusable local-coordinate model subassembly."""

    name: str
    model: TubaModel = field(default_factory=lambda: TubaModel(project_name="Fragment"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.model.project_name = self.name

    def pipe(self, section: str, material: str):
        return self.model.pipe(section=section, material=material)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metadata": self.metadata,
            "model": self.model.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelFragment":
        return cls(
            name=data["name"],
            model=TubaModel.from_dict(data["model"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PlacementResult:
    group_name: str
    node_ids: dict[str, str]
    element_ids: dict[str, str]


def place_fragment(
    model: TubaModel,
    fragment: ModelFragment,
    coordinate_system: CoordinateSystem,
    *,
    name: str,
) -> PlacementResult:
    """Place a local-coordinate fragment into a parent model."""
    patch = build_fragment_patch(model, fragment, coordinate_system, name=name)
    result = ModelTransaction(model).apply(patch)
    group = {
        "name": name,
        "fragment": fragment.name,
        "coordinate_system": coordinate_system.to_dict(),
        "nodes": list(result.node_ids.values()),
        "elements": list(result.element_ids.values()),
        "supports": [],
    }
    model.groups[name] = group
    return PlacementResult(group_name=name, node_ids=result.node_ids, element_ids=result.element_ids)


def build_fragment_patch(
    model: TubaModel,
    fragment: ModelFragment,
    coordinate_system: CoordinateSystem,
    *,
    name: str,
) -> ModelPatch:
    operations = []

    for material_name, material in fragment.model.materials.items():
        if material_name not in model.materials:
            model.materials[material_name] = material

    for section_name, section in fragment.model.sections.items():
        if section_name not in model.sections:
            model.sections[section_name] = section

    for local_node_id, node in fragment.model.nodes.items():
        operations.append(
            AddNode(
                local_id=local_node_id,
                coords=coordinate_system.to_global_point(node.coords).tolist(),
            )
        )

    for elem in fragment.model.elements:
        operations.append(
            AddElement(
                local_id=elem.id,
                type=elem.type,
                n1=elem.n1,
                n2=elem.n2,
                section=elem.section,
                material=elem.material,
                bend_radius=elem.bend_radius,
                bend_angle=elem.bend_angle,
                twist_angle=elem.twist_angle,
                id_prefix=_prefix_from_id(elem.id),
            )
        )

    for support in fragment.model.supports:
        operations.append(
            AddSupport(
                node=support.node,
                type=support.type,
                direction=support.direction,
                stiffness=support.stiffness,
                imposed_displacement=support.imposed_displacement,
                stiffness_matrix=support.stiffness_matrix,
                blocked_dof=support.blocked_dof,
                mass=support.mass,
                friction_coefficient=support.friction_coefficient,
            )
        )

    return ModelPatch(
        operations=operations,
        provenance={"fragment": fragment.name, "placement": name},
    )


def _prefix_from_id(element_id: str) -> str:
    if "_" not in element_id:
        return "elem"
    return element_id.rsplit("_", 1)[0]
```

- [ ] **Step 5: Add model convenience method**

Modify `TubaModel` in `tuba/model.py`:

```python
    def place_fragment(self, fragment, coordinate_system, *, name: str):
        """Place a local-coordinate fragment into this model."""
        from tuba.fragments import place_fragment

        return place_fragment(self, fragment, coordinate_system, name=name)
```

Place the method near `pipe()`.

- [ ] **Step 6: Export from `tuba/__init__.py`**

Add:

```python
from tuba.fragments import ModelFragment, PlacementResult, place_fragment
```

Add `"ModelFragment"`, `"PlacementResult"`, and `"place_fragment"` to `__all__`.

- [ ] **Step 7: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fragments -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 8: Commit**

```powershell
git add tuba/fragments.py tuba/model.py tuba/__init__.py tests/test_fragments.py
git commit -m "feat: add local-coordinate model fragments"
```

---

### Task 6: Add JSON Schema Contracts

**Files:**
- Create: `tuba/schema.py`
- Create: `tests/test_schema.py`
- Modify: `tuba/model.py`
- Modify: `tuba/__init__.py`

- [ ] **Step 1: Write schema tests**

Create `tests/test_schema.py`:

```python
import unittest

from tuba import Model
from tuba.schema import SchemaValidationError, validate_model_dict


class TestSchema(unittest.TestCase):
    def test_model_dict_validates(self):
        model = Model(project_name="Schema")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        validate_model_dict(model.to_dict())

    def test_missing_sections_fails(self):
        data = {
            "meta": {"project_name": "Bad", "standard": "ASME_B31.3", "version": "4.0.0"},
            "materials": {},
            "nodes": {},
            "elements": [],
            "supports": [],
            "load_cases": {},
        }

        with self.assertRaises(SchemaValidationError):
            validate_model_dict(data)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_schema -v
```

Expected:

```text
ImportError: No module named 'tuba.schema'
```

- [ ] **Step 3: Implement schema helper**

Create `tuba/schema.py`:

```python
"""JSON Schema contracts for model and agent-facing payloads."""

from __future__ import annotations

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


class SchemaValidationError(ValueError):
    """Raised when a JSON-like payload does not match a Tuba schema."""


MODEL_SCHEMA_V4 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TubaModelV4",
    "type": "object",
    "required": ["meta", "materials", "sections", "nodes", "elements", "supports", "load_cases"],
    "properties": {
        "meta": {
            "type": "object",
            "required": ["project_name", "standard", "version"],
            "properties": {
                "project_name": {"type": "string"},
                "standard": {"type": "string"},
                "version": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "materials": {"type": "object"},
        "sections": {"type": "object"},
        "nodes": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "number"},
            },
        },
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "n1", "n2", "section", "material"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "n1": {"type": "string"},
                    "n2": {"type": "string"},
                    "section": {"type": "string"},
                    "material": {"type": "string"},
                    "bend_radius": {"type": "number"},
                    "bend_angle": {"type": "number"},
                    "twist_angle": {"type": "number"},
                },
                "additionalProperties": True,
            },
        },
        "supports": {"type": "array"},
        "load_cases": {"type": "object"},
        "obstacles": {"type": "array"},
        "tees": {"type": "object"},
        "groups": {"type": "object"},
    },
    "additionalProperties": True,
}


def validate_model_dict(data: dict) -> None:
    validator = Draft202012Validator(MODEL_SCHEMA_V4)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        message = "\n".join(_format_error(error) for error in errors)
        raise SchemaValidationError(message)


def _format_error(error: ValidationError) -> str:
    path = ".".join(str(item) for item in error.path)
    if not path:
        path = "<root>"
    return f"{path}: {error.message}"
```

- [ ] **Step 4: Use schema in model loading**

Modify `TubaModel.from_dict()` at the top:

```python
        from tuba.schema import validate_model_dict

        validate_model_dict(data)
```

- [ ] **Step 5: Export from `tuba/__init__.py`**

Add:

```python
from tuba.schema import MODEL_SCHEMA_V4, SchemaValidationError, validate_model_dict
```

Add names to `__all__`.

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_schema -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add tuba/schema.py tuba/model.py tuba/__init__.py tests/test_schema.py
git commit -m "feat: add model schema validation"
```

---

### Task 7: Preserve Load Case Roundtrip Completeness

**Files:**
- Modify: `tuba/model.py`
- Modify: `tests/test_tuba_core.py`

- [ ] **Step 1: Add a regression test**

Append to `TestModelAndBuilder` in `tests/test_tuba_core.py`:

```python
    def test_load_case_ref_temperature_roundtrip(self):
        model = Model(project_name="LoadCaseRoundtrip")
        model.define_load_case(
            "Hot",
            gravity=True,
            pressure=1.0e6,
            temperature=120.0,
            ref_temperature=20.0,
        )

        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(loaded.load_cases["Hot"].ref_temperature, 20.0)
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tuba_core.TestModelAndBuilder.test_load_case_ref_temperature_roundtrip -v
```

Expected:

```text
FAIL
```

- [ ] **Step 3: Serialize `ref_temperature`**

Modify `TubaModel.to_dict()` load case section:

```python
            "load_cases": {
                name: {
                    "gravity": lc.gravity,
                    "internal_pressure": lc.internal_pressure,
                    "temperature": lc.temperature,
                    "ref_temperature": lc.ref_temperature,
                }
                for name, lc in self.load_cases.items()
            },
```

Modify `TubaModel.from_dict()` load case reconstruction:

```python
                ref_temperature=lc.get("ref_temperature", 20.0),
```

- [ ] **Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tuba_core.TestModelAndBuilder.test_load_case_ref_temperature_roundtrip -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add tuba/model.py tests/test_tuba_core.py
git commit -m "fix: preserve load case reference temperature"
```

---

### Task 8: Add Scene-First Visualization

**Files:**
- Create: `tuba/visualizer/scenes.py`
- Create: `tests/test_visualizer_scenes.py`
- Modify: `tuba/visualizer/plots.py`

- [ ] **Step 1: Write scene tests**

Create `tests/test_visualizer_scenes.py`:

```python
import unittest

from tuba import Model
from tuba.visualizer.scenes import build_model_scene


class TestVisualizerScenes(unittest.TestCase):
    def test_build_model_scene_returns_plotter(self):
        model = Model(project_name="Scene")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        plotter = build_model_scene(model, off_screen=True)
        try:
            self.assertTrue(hasattr(plotter, "add_mesh"))
        finally:
            plotter.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualizer_scenes -v
```

Expected:

```text
ImportError: No module named 'tuba.visualizer.scenes'
```

- [ ] **Step 3: Implement `build_model_scene()`**

Create `tuba/visualizer/scenes.py`:

```python
"""Scene-first visualization builders."""

from __future__ import annotations

from typing import Optional

from tuba.model import TubaModel
from tuba.solver.base import FEAResults


def build_model_scene(
    model: TubaModel,
    results: Optional[FEAResults] = None,
    *,
    off_screen: bool = False,
    title: str = "Tuba v4",
):
    """Return a PyVista plotter without showing it."""
    import pyvista as pv

    from tuba.visualizer.pipeline import build_3d_mesh_from_model, get_section_radius, inflate_tubes

    plotter = pv.Plotter(off_screen=off_screen)
    plotter.set_background("#1a1a2e")
    mesh = build_3d_mesh_from_model(model, results)
    radius = get_section_radius(next(iter(model.sections.values()))) if model.sections else 0.05
    tubes = inflate_tubes(mesh, radius=radius) if mesh.n_points else mesh
    if tubes.n_points:
        plotter.add_mesh(
            tubes,
            scalars="VMIS" if "VMIS" in tubes.point_data else None,
            cmap="turbo",
        )
    plotter.add_axes()
    plotter.add_title(title, color="white")
    return plotter
```

- [ ] **Step 4: Refactor one existing plotting wrapper**

Modify `plot_deformed_stress()` in `tuba/visualizer/plots.py` to delegate to `build_model_scene()` when possible:

```python
    mdl = model or getattr(results, "_model", None)
    if mdl is not None:
        from tuba.visualizer.scenes import build_model_scene

        p = build_model_scene(mdl, results, off_screen=bool(export_html), title="Deformed Stress")
        if export_html:
            p.export_html(export_html)
            p.close()
            return
        p.show()
        return
```

Place this block immediately after `_require_pyvista()`. Leave the existing implementation below as fallback for unusual inputs.

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualizer_scenes -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/visualizer/scenes.py tuba/visualizer/plots.py tests/test_visualizer_scenes.py
git commit -m "feat: add scene-first visualization"
```

---

### Task 9: Add Agent-Facing Patch Workflow Documentation

**Files:**
- Create: `docs/agent_model_workflow.md`
- Modify: `README.md`

- [ ] **Step 1: Create workflow documentation**

Create `docs/agent_model_workflow.md`:

```markdown
# Agent Model Workflow

Agents should not mutate `TubaModel` by directly calling low-level model methods.

Preferred workflow:

1. Generate or select a `ModelFragment` in local coordinates.
2. Generate a `CoordinateSystem` describing placement in the parent model.
3. Build a `ModelPatch`.
4. Validate the patch payload against schema.
5. Apply the patch through `ModelTransaction`.
6. Validate the resulting `TubaModel`.
7. Render or export from the validated model.

Example:

```python
from tuba import CoordinateSystem, Model, ModelFragment

fragment = ModelFragment("rack_template")
fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

with fragment.pipe(section="PipeSec", material="Steel") as b:
    b.start([0.0, 0.0, 0.0]).run(2.0)

model = Model("Plant")
model.add_material("Steel", E=2.0e11, nu=0.3)
model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

model.place_fragment(
    fragment,
    CoordinateSystem(origin=(10.0, 20.0, 0.0)),
    name="rack_A",
)

model.validate()
```

The fragment remains editable as a local object. The parent model stores a named group for GUI selection and solver export remains based on ordinary nodes and elements.
```
```

- [ ] **Step 2: Add README link**

Add this section to `README.md` after the autorouting limitations:

```markdown
## Reusable Fragments And Agent Workflows

Reusable local-coordinate assemblies are represented as `ModelFragment` objects and placed into parent models with `CoordinateSystem`. This supports templates, repeated subassemblies, GUI groups, and safer agent-generated model changes.

See [`docs/agent_model_workflow.md`](docs/agent_model_workflow.md).
```

- [ ] **Step 3: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 4: Commit**

```powershell
git add docs/agent_model_workflow.md README.md
git commit -m "docs: describe agent model workflow"
```

---

### Task 10: Reduce Obvious Copy And Lookup Pressure

**Files:**
- Modify: `tuba/model.py`
- Modify: `tuba/routing/adapter.py`
- Create: `tests/test_model_indexes.py`

- [ ] **Step 1: Write node index tests**

Create `tests/test_model_indexes.py`:

```python
import unittest

from tuba import Model


class TestModelIndexes(unittest.TestCase):
    def test_find_node_by_point_reuses_existing_node(self):
        model = Model(project_name="Indexes")
        existing = model.add_node((1.0, 2.0, 3.0))

        found = model.find_node_by_point((1.0, 2.0, 3.0))

        self.assertEqual(found, existing)

    def test_find_node_by_point_returns_none_for_missing_node(self):
        model = Model(project_name="Indexes")

        self.assertIsNone(model.find_node_by_point((1.0, 2.0, 3.0)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_indexes -v
```

Expected:

```text
AttributeError: 'TubaModel' object has no attribute 'find_node_by_point'
```

- [ ] **Step 3: Add coordinate index helper**

Modify `TubaModel` in `tuba/model.py`:

```python
    def find_node_by_point(self, coords, *, tol: float = 1e-6) -> Optional[str]:
        """Return an existing node id at coords, if one exists within tolerance."""
        target = np.asarray(coords, dtype=float)
        for nid, node in self.nodes.items():
            if np.allclose(node.coords, target, atol=tol):
                return nid
        return None
```

This keeps behavior identical while moving node lookup behind the model interface. A later optimization can replace the implementation with a rounded coordinate index without changing callers.

- [ ] **Step 4: Use model helper in route adapter**

Modify `_node_for_point()` in `tuba/routing/adapter.py`:

```python
def _node_for_point(model: TubaModel, point: Point3D, tol: float = 1e-6) -> str:
    coords = np.asarray(point, dtype=float)
    if hasattr(model, "find_node_by_point"):
        existing = model.find_node_by_point(coords, tol=tol)
        if existing is not None:
            return existing
    for nid, node in model.nodes.items():
        if np.allclose(node.coords, coords, atol=tol):
            return nid
    return model.add_node(coords)
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_indexes -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/model.py tuba/routing/adapter.py tests/test_model_indexes.py
git commit -m "refactor: centralize node point lookup"
```

---

## Execution Order

Implement in this order:

1. Coordinate systems.
2. Validation.
3. Patches and transactions.
4. Route candidate patch refactor.
5. Model fragments and placement.
6. JSON schema contracts.
7. Load case serialization fix.
8. Scene-first visualization.
9. Agent workflow documentation.
10. Node lookup seam.

Do not start scene-first visualization before fragments and transactions are working. The GUI layer should consume the safer model interfaces, not drive them.

## Design Decisions Locked By This Plan

- `TubaModel` remains the solver-facing flattened model.
- `ModelFragment` is the reusable local-coordinate authoring unit.
- `CoordinateSystem` owns the local-to-global mapping.
- `ModelTransaction` owns mutation atomicity.
- `ModelPatch` is the agent/GUI commit format.
- Groups are metadata in `TubaModel.groups`; solvers can ignore them.
- Existing builder and routing public interfaces remain compatible.
- Existing `unittest` workflow remains the test runner.

## Out Of Scope For This Plan

- Rewriting the package into `src/` layout.
- Replacing dataclasses with Pydantic.
- Replacing PyVista with Three.js.
- Replacing Code_Aster exporter internals.
- Full spatial indexing for route conflict detection.
- Full undo/redo UI.

These are later improvements once the mutation and placement seams exist.

## Self-Review

- Spec coverage: reusable local-coordinate structures are covered by Tasks 1 and 5. Transactional mutation is covered by Tasks 3 and 4. Agent-safe generation is covered by Tasks 6 and 9. GUI-ready visualization is covered by Task 8. Current inefficiency risks are started in Task 10.
- Placeholder scan: no task depends on undefined behavior; each code task contains concrete tests, implementation snippets, commands, and expected results.
- Type consistency: `CoordinateSystem`, `ModelPatch`, `ModelTransaction`, `ModelFragment`, `PlacementResult`, and `validate_model` are introduced before later tasks depend on them.
