# IFC-Style Placement Frames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add IFC-style local placement frames to Tuba while keeping native nodes in model-global Cartesian coordinates.

**Architecture:** Add `PlacementFrame` and `PlacementAssignment` as additive model records. Use existing `CoordinateSystem` for resolved transform math, preserve current solver/global node behavior, and teach IFC import/export to preserve or emit `IfcLocalPlacement` / `IfcAxis2Placement3D` hierarchies. Generated changes continue through `ModelPatch` and validation.

**Tech Stack:** Python dataclasses, `numpy`, existing `unittest` tests, existing JSON schema helpers, optional IfcOpenShell for IFC integration tests.

---

## Spec References

- Primary spec: `.agents/SPECS/multidomain-ifc-aware-data-model.md`
- Decision log: `.agents/DECISIONS/multidomain-ifc-aware-data-model.md`
- Current math primitive: `tuba/coordinates.py`
- Current fragment placement flow: `tuba/fragments.py`
- Current IFC exporter/importer: `tuba/external/ifc.py`, `tuba/external/ifc_pipes.py`

## Files To Create Or Modify

- Create `tuba/placements.py`  
  Owns `PlacementFrame`, `PlacementAssignment`, IFC-style axis/ref-direction conversion, frame-chain resolution, and serialization helpers.

- Create `tests/test_placements.py`  
  Unit tests for frame math, composition, invalid axes, serialization, and duplicate assignment semantics.

- Modify `tuba/model.py`  
  Add `placement_frames`, `placement_assignments`, helper methods, and JSON roundtrip support.

- Modify `tuba/refs.py`  
  Add `placement_frame` and `placement_assignment` ref resolution where useful for validation and relationships.

- Modify `tuba/validation.py`  
  Validate frame axes, parent graph cycles, assignment targets, and duplicate object-placement assignments.

- Modify `tuba/schema.py`  
  Add model schema entries and patch schema entries for placement frames and assignments.

- Modify `tuba/patches.py`  
  Add `AddPlacementFrame`, `AssignPlacement`, and `RemovePlacementAssignment` patch operations.

- Modify `tuba/fragments.py`  
  Make fragment placement optionally create placement frame metadata and assignment records while preserving existing group metadata.

- Create `tuba/external/ifc_placements.py`  
  Isolate IFC placement creation and import resolution so `ifc.py` does not grow more coordinate-system logic.

- Modify `tuba/external/ifc.py` and `tuba/external/ifc_pipes.py`  
  Use placement helpers during export/import and preserve current fallback behavior.

- Modify `tuba/__init__.py`  
  Export `PlacementFrame` and `PlacementAssignment`.

- Modify or add IFC tests:
  - `tests/test_ifc_placements.py`
  - `tests/test_ifc.py`
  - `tests/test_fragments.py`
  - `tests/test_schema.py`
  - `tests/test_patches.py`

---

### Task 1: Add Placement Math Unit Tests

**Files:**
- Create: `tests/test_placements.py`

- [ ] **Step 1: Write failing tests for frame conversion and composition**

Create `tests/test_placements.py` with:

```python
import unittest

import numpy as np

from tuba.coordinates import CoordinateSystem
from tuba.placements import PlacementFrame, resolve_placement_frame


class TestPlacementFrame(unittest.TestCase):
    def test_axis_ref_direction_match_ifc_semantics(self):
        frame = PlacementFrame(
            id="rack_A",
            origin=(10.0, 20.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
        )

        cs = frame.to_coordinate_system()

        self.assertTrue(np.allclose(cs.to_global_point((2.0, 0.0, 0.0)), (10.0, 22.0, 0.0)))
        self.assertTrue(np.allclose(cs.to_global_vector((0.0, 1.0, 0.0)), (-1.0, 0.0, 0.0)))

    def test_parent_child_frames_compose(self):
        parent = PlacementFrame(
            id="site",
            origin=(100.0, 0.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
        )
        child = PlacementFrame(
            id="rack_A",
            origin=(2.0, 3.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(1.0, 0.0, 0.0),
            parent="placement_frame:site",
        )

        cs = resolve_placement_frame(
            "rack_A",
            {"site": parent, "rack_A": child},
        )

        self.assertTrue(np.allclose(cs.to_global_point((1.0, 0.0, 0.0)), (97.0, 3.0, 0.0)))

    def test_colinear_axis_and_ref_direction_are_rejected(self):
        with self.assertRaises(ValueError):
            PlacementFrame(
                id="bad",
                origin=(0.0, 0.0, 0.0),
                axis=(0.0, 0.0, 1.0),
                ref_direction=(0.0, 0.0, 2.0),
            ).to_coordinate_system()

    def test_coordinate_system_roundtrip(self):
        cs = CoordinateSystem(
            origin=(4.0, 5.0, 6.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        frame = PlacementFrame.from_coordinate_system("rack_A", cs)
        restored = frame.to_coordinate_system()

        self.assertEqual(frame.axis, (0.0, 0.0, 1.0))
        self.assertEqual(frame.ref_direction, (0.0, 1.0, 0.0))
        self.assertTrue(np.allclose(restored.to_global_point((1.0, 2.0, 3.0)), cs.to_global_point((1.0, 2.0, 3.0))))
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_placements -v
```

Expected:

```text
ImportError: No module named 'tuba.placements'
```

### Task 2: Implement `tuba.placements`

**Files:**
- Create: `tuba/placements.py`
- Test: `tests/test_placements.py`

- [ ] **Step 1: Add placement dataclasses and transform helpers**

Create `tuba/placements.py` with these public objects:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from tuba.coordinates import CoordinateSystem


@dataclass(frozen=True)
class PlacementFrame:
    id: str
    origin: tuple[float, float, float]
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    ref_direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    parent: str | None = None
    frame_type: str = "generic"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_coordinate_system(self) -> CoordinateSystem:
        origin = _vector(self.origin, "origin")
        z_axis = _unit(self.axis, "axis")
        raw_x = _unit(self.ref_direction, "ref_direction")
        x_axis = raw_x - z_axis * float(np.dot(raw_x, z_axis))
        x_norm = float(np.linalg.norm(x_axis))
        if x_norm <= 1e-12:
            raise ValueError("PlacementFrame ref_direction must not be colinear with axis.")
        x_axis = x_axis / x_norm
        y_axis = np.cross(z_axis, x_axis)
        return CoordinateSystem(
            origin=tuple(float(value) for value in origin),
            x_axis=tuple(float(value) for value in x_axis),
            y_axis=tuple(float(value) for value in y_axis),
            z_axis=tuple(float(value) for value in z_axis),
        )

    @classmethod
    def from_coordinate_system(
        cls,
        id: str,
        coordinate_system: CoordinateSystem,
        *,
        parent: str | None = None,
        frame_type: str = "generic",
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PlacementFrame":
        return cls(
            id=id,
            origin=_tuple3(coordinate_system.origin),
            axis=_tuple3(coordinate_system.z_axis),
            ref_direction=_tuple3(coordinate_system.x_axis),
            parent=parent,
            frame_type=frame_type,
            source=source,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "origin": list(self.origin),
            "axis": list(self.axis),
            "ref_direction": list(self.ref_direction),
            "frame_type": self.frame_type,
            "metadata": self.metadata,
        }
        if self.parent is not None:
            data["parent"] = self.parent
        if self.source is not None:
            data["source"] = self.source
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementFrame":
        return cls(
            id=str(data["id"]),
            origin=_tuple3(data["origin"]),
            axis=_tuple3(data.get("axis", (0.0, 0.0, 1.0))),
            ref_direction=_tuple3(data.get("ref_direction", (1.0, 0.0, 0.0))),
            parent=data.get("parent"),
            frame_type=str(data.get("frame_type", "generic")),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class PlacementAssignment:
    target: str
    frame: str
    role: str = "object_placement"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target": self.target,
            "frame": self.frame,
            "role": self.role,
            "metadata": self.metadata,
        }
        if self.source is not None:
            data["source"] = self.source
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementAssignment":
        return cls(
            target=str(data["target"]),
            frame=str(data["frame"]),
            role=str(data.get("role", "object_placement")),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )


def resolve_placement_frame(frame_id: str, frames: Mapping[str, PlacementFrame]) -> CoordinateSystem:
    ordered: list[PlacementFrame] = []
    seen: set[str] = set()
    current_id: str | None = frame_id
    while current_id is not None:
        if current_id in seen:
            raise ValueError(f"Placement frame cycle detected at {current_id!r}.")
        seen.add(current_id)
        frame = frames[current_id]
        ordered.append(frame)
        current_id = _ref_id(frame.parent)

    cs = CoordinateSystem.identity()
    for frame in reversed(ordered):
        local = frame.to_coordinate_system()
        cs = CoordinateSystem(
            origin=cs.to_global_point(local.origin),
            x_axis=cs.to_global_vector(local.x_axis),
            y_axis=cs.to_global_vector(local.y_axis),
            z_axis=cs.to_global_vector(local.z_axis),
        )
    return cs


def _ref_id(ref: str | None) -> str | None:
    if ref is None:
        return None
    if ref.startswith("placement_frame:"):
        return ref.split(":", 1)[1]
    return ref


def _vector(value: Any, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain three finite values.")
    return arr


def _unit(value: Any, name: str) -> np.ndarray:
    arr = _vector(value, name)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{name} must not be the zero vector.")
    return arr / norm


def _tuple3(value: Any) -> tuple[float, float, float]:
    arr = _vector(value, "value")
    return tuple(float(item) for item in arr)
```

- [ ] **Step 2: Run focused placement tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_placements -v
```

Expected:

```text
Ran 4 tests
OK
```

### Task 3: Add Model Storage And JSON Roundtrip

**Files:**
- Modify: `tuba/model.py`
- Modify: `tuba/__init__.py`
- Test: `tests/test_placements.py`

- [ ] **Step 1: Add model roundtrip tests**

Append to `tests/test_placements.py`:

```python
from tuba import Model
from tuba.placements import PlacementAssignment


class TestPlacementModelStorage(unittest.TestCase):
    def test_model_roundtrips_placement_frames_and_assignments(self):
        model = Model("PlacementTest")
        model.placement_frames["site"] = PlacementFrame(
            id="site",
            origin=(100.0, 0.0, 0.0),
            frame_type="site",
        )
        model.placement_frames["rack_A"] = PlacementFrame(
            id="rack_A",
            origin=(2.0, 0.0, 0.0),
            parent="placement_frame:site",
            frame_type="assembly",
        )
        model.placement_assignments.append(
            PlacementAssignment(
                target="group:rack_A",
                frame="placement_frame:rack_A",
                role="object_placement",
                source="native",
            )
        )

        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(set(loaded.placement_frames), {"site", "rack_A"})
        self.assertEqual(loaded.placement_frames["rack_A"].parent, "placement_frame:site")
        self.assertEqual(len(loaded.placement_assignments), 1)
        self.assertEqual(loaded.placement_assignments[0].target, "group:rack_A")
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_placements.TestPlacementModelStorage -v
```

Expected:

```text
AttributeError: 'TubaModel' object has no attribute 'placement_frames'
```

- [ ] **Step 3: Implement model storage**

In `TubaModel.__init__`, initialize:

```python
self.placement_frames: dict[str, PlacementFrame] = {}
self.placement_assignments: list[PlacementAssignment] = []
```

Add local import or top-level import:

```python
from tuba.placements import PlacementAssignment, PlacementFrame, resolve_placement_frame
```

Add helper methods:

```python
def add_placement_frame(self, frame: PlacementFrame) -> PlacementFrame:
    if frame.id in self.placement_frames:
        raise ValueError(f"Placement frame {frame.id!r} already exists.")
    self.placement_frames[frame.id] = frame
    return frame

def assign_placement(self, assignment: PlacementAssignment) -> PlacementAssignment:
    self.placement_assignments.append(assignment)
    return assignment

def resolve_placement_frame(self, frame: str) -> CoordinateSystem:
    frame_id = frame.split(":", 1)[1] if frame.startswith("placement_frame:") else frame
    return resolve_placement_frame(frame_id, self.placement_frames)

def to_global_point(self, point, frame: str | None = None):
    if frame is None:
        return np.asarray(point, dtype=float)
    return self.resolve_placement_frame(frame).to_global_point(point)

def to_global_vector(self, vector, frame: str | None = None):
    if frame is None:
        return np.asarray(vector, dtype=float)
    return self.resolve_placement_frame(frame).to_global_vector(vector)

def to_local_point(self, point, frame: str):
    return self.resolve_placement_frame(frame).to_local_point(point)
```

Extend `to_dict()`:

```python
"placement_frames": {
    frame_id: frame.to_dict()
    for frame_id, frame in self.placement_frames.items()
},
"placement_assignments": [
    assignment.to_dict()
    for assignment in self.placement_assignments
],
```

Extend `from_dict()`:

```python
model.placement_frames = {
    frame_id: PlacementFrame.from_dict(frame_data)
    for frame_id, frame_data in data.get("placement_frames", {}).items()
}
model.placement_assignments = [
    PlacementAssignment.from_dict(item)
    for item in data.get("placement_assignments", [])
]
```

Export from `tuba/__init__.py`:

```python
from tuba.placements import PlacementAssignment, PlacementFrame
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_placements -v
```

Expected:

```text
OK
```

### Task 4: Add Validation And Schema Coverage

**Files:**
- Modify: `tuba/validation.py`
- Modify: `tuba/schema.py`
- Test: `tests/test_placements.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Add validation tests**

Append to `tests/test_placements.py`:

```python
from tuba.validation import ModelValidationError


class TestPlacementValidation(unittest.TestCase):
    def test_cycle_in_placement_frames_fails_model_validation(self):
        model = Model("BadFrames")
        model.placement_frames["a"] = PlacementFrame(id="a", origin=(0.0, 0.0, 0.0), parent="placement_frame:b")
        model.placement_frames["b"] = PlacementFrame(id="b", origin=(0.0, 0.0, 0.0), parent="placement_frame:a")

        with self.assertRaises(ModelValidationError) as ctx:
            model.validate()

        self.assertIn("Placement frame cycle", str(ctx.exception))

    def test_duplicate_object_placement_assignment_fails_validation(self):
        model = Model("DuplicateAssignments")
        model.groups["rack_A"] = {"name": "rack_A", "nodes": [], "elements": [], "supports": []}
        model.placement_frames["rack_A_frame"] = PlacementFrame(id="rack_A_frame", origin=(0.0, 0.0, 0.0))
        assignment = PlacementAssignment(
            target="group:rack_A",
            frame="placement_frame:rack_A_frame",
            role="object_placement",
            source="native",
        )
        model.placement_assignments.extend([assignment, assignment])

        with self.assertRaises(ModelValidationError) as ctx:
            model.validate()

        self.assertIn("duplicate object placement", str(ctx.exception).lower())
```

- [ ] **Step 2: Implement validation**

Add validation helpers in `tuba/validation.py`:

```python
def _validate_placement_frames(model: TubaModel, errors: list[str]) -> None:
    frames = getattr(model, "placement_frames", {})
    for frame_id, frame in frames.items():
        if frame_id != frame.id:
            errors.append(f"Placement frame key {frame_id!r} does not match id {frame.id!r}.")
        try:
            frame.to_coordinate_system()
        except Exception as exc:
            errors.append(f"Placement frame {frame_id!r} is invalid: {exc}")
        parent_id = _placement_frame_id(frame.parent)
        if parent_id is not None and parent_id not in frames:
            errors.append(f"Placement frame {frame_id!r} references missing parent {parent_id!r}.")
    for frame_id in frames:
        try:
            resolve_placement_frame(frame_id, frames)
        except Exception as exc:
            errors.append(f"Placement frame cycle or resolution error at {frame_id!r}: {exc}")


def _validate_placement_assignments(model: TubaModel, errors: list[str]) -> None:
    frames = getattr(model, "placement_frames", {})
    seen: set[tuple[str, str | None]] = set()
    for assignment in getattr(model, "placement_assignments", []):
        frame_id = _placement_frame_id(assignment.frame)
        if frame_id not in frames:
            errors.append(f"Placement assignment references missing frame {assignment.frame!r}.")
        try:
            resolve_entity_ref(model, coerce_entity_ref(assignment.target))
        except Exception:
            errors.append(f"Placement assignment references missing target {assignment.target!r}.")
        if assignment.role == "object_placement":
            key = (assignment.target, assignment.source)
            if key in seen:
                errors.append(f"Duplicate object placement assignment for {assignment.target!r}.")
            seen.add(key)


def _placement_frame_id(ref: str | None) -> str | None:
    if ref is None:
        return None
    if ref.startswith("placement_frame:"):
        return ref.split(":", 1)[1]
    return ref
```

Call both helpers from `validate_model()`.

- [ ] **Step 3: Extend schema**

In `MODEL_SCHEMA_V4["properties"]`, add:

```python
"placement_frames": {
    "type": "object",
    "additionalProperties": {"$ref": "#/$defs/placementFrame"},
},
"placement_assignments": {
    "type": "array",
    "items": {"$ref": "#/$defs/placementAssignment"},
},
```

In `$defs`, add:

```python
"placementFrame": {
    "type": "object",
    "required": ["id", "origin"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "origin": {"$ref": "#/$defs/vector3"},
        "axis": {"$ref": "#/$defs/vector3"},
        "ref_direction": {"$ref": "#/$defs/vector3"},
        "parent": {"type": "string"},
        "frame_type": {"type": "string"},
        "source": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": False,
},
"placementAssignment": {
    "type": "object",
    "required": ["target", "frame"],
    "properties": {
        "target": {"type": "string", "pattern": "^[^:]+:.+$"},
        "frame": {"type": "string", "pattern": "^placement_frame:.+$"},
        "role": {"type": "string"},
        "source": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": False,
},
```

- [ ] **Step 4: Run validation and schema tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_placements tests.test_schema -v
```

Expected:

```text
OK
```

### Task 5: Add Patch Operations

**Files:**
- Modify: `tuba/patches.py`
- Modify: `tuba/schema.py`
- Test: `tests/test_patches.py`
- Test: `tests/test_placements.py`

- [ ] **Step 1: Add patch roundtrip tests**

Add tests to `tests/test_patches.py`:

```python
from tuba.patches import AddPlacementFrame, AssignPlacement, ModelPatch, ModelTransaction


def test_patch_adds_placement_frame_and_assignment(self):
    model = Model("PatchPlacement")
    model.groups["rack_A"] = {"name": "rack_A", "nodes": [], "elements": [], "supports": []}
    patch = ModelPatch(
        operations=[
            AddPlacementFrame(id="rack_A_frame", origin=(1.0, 2.0, 3.0), frame_type="assembly"),
            AssignPlacement(target="group:rack_A", frame="placement_frame:rack_A_frame", source="native"),
        ]
    )

    ModelTransaction(model).apply(patch)

    self.assertIn("rack_A_frame", model.placement_frames)
    self.assertEqual(model.placement_assignments[0].target, "group:rack_A")


def test_placement_patch_serializes_and_loads(self):
    patch = ModelPatch(
        operations=[
            AddPlacementFrame(id="site", origin=(100.0, 0.0, 0.0), frame_type="site"),
            AssignPlacement(target="group:rack_A", frame="placement_frame:site", source="ifc"),
        ]
    )

    loaded = ModelPatch.from_dict(patch.to_dict())

    self.assertEqual(loaded.to_dict(), patch.to_dict())
```

- [ ] **Step 2: Add patch dataclasses and transaction handlers**

In `tuba/patches.py`, add:

```python
@dataclass(frozen=True)
class AddPlacementFrame:
    id: str
    origin: Sequence[float]
    axis: Sequence[float] = (0.0, 0.0, 1.0)
    ref_direction: Sequence[float] = (1.0, 0.0, 0.0)
    parent: str | None = None
    frame_type: str = "generic"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssignPlacement:
    target: str
    frame: str
    role: str = "object_placement"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemovePlacementAssignment:
    target: str
    role: str = "object_placement"
    source: str | None = None
```

Add them to `PatchOperation`, `_operation_to_dict`, `ModelPatch.from_dict`, and `ModelTransaction.apply`.

Handlers:

```python
def _apply_add_placement_frame(self, operation: AddPlacementFrame) -> None:
    self.model.add_placement_frame(
        PlacementFrame(
            id=operation.id,
            origin=tuple(operation.origin),
            axis=tuple(operation.axis),
            ref_direction=tuple(operation.ref_direction),
            parent=operation.parent,
            frame_type=operation.frame_type,
            source=operation.source,
            metadata=operation.metadata,
        )
    )

def _apply_assign_placement(self, operation: AssignPlacement) -> None:
    self.model.assign_placement(
        PlacementAssignment(
            target=_resolve_metadata_refs(operation.target, PatchResult()),
            frame=operation.frame,
            role=operation.role,
            source=operation.source,
            metadata=operation.metadata,
        )
    )

def _apply_remove_placement_assignment(self, operation: RemovePlacementAssignment) -> None:
    self.model.placement_assignments = [
        assignment
        for assignment in self.model.placement_assignments
        if not (
            assignment.target == operation.target
            and assignment.role == operation.role
            and assignment.source == operation.source
        )
    ]
```

- [ ] **Step 3: Add patch schema entries**

Add `oneOf` entries for:

```json
{"op": "add_placement_frame", "id": "rack_A_frame", "origin": [0, 0, 0]}
{"op": "assign_placement", "target": "group:rack_A", "frame": "placement_frame:rack_A_frame"}
{"op": "remove_placement_assignment", "target": "group:rack_A"}
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patches tests.test_placements tests.test_schema -v
```

Expected:

```text
OK
```

### Task 6: Integrate Fragment Placement Metadata

**Files:**
- Modify: `tuba/fragments.py`
- Test: `tests/test_fragments.py`

- [ ] **Step 1: Add fragment placement metadata test**

Add to `tests/test_fragments.py`:

```python
def test_fragment_placement_creates_ifc_style_frame_metadata(self):
    fragment = ModelFragment("rack_template")
    fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
    fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    with fragment.pipe(section="PipeSec", material="Steel") as b:
        b.start([0.0, 0.0, 0.0]).run(1.0)

    parent = Model(project_name="Parent")
    placement = CoordinateSystem(
        origin=(10.0, 20.0, 0.0),
        x_axis=(0.0, 1.0, 0.0),
        y_axis=(-1.0, 0.0, 0.0),
        z_axis=(0.0, 0.0, 1.0),
    )

    parent.place_fragment(fragment, placement, name="rack_A")

    self.assertIn("rack_A", parent.placement_frames)
    self.assertEqual(parent.placement_frames["rack_A"].frame_type, "assembly")
    self.assertTrue(
        any(
            item.target == "group:rack_A" and item.frame == "placement_frame:rack_A"
            for item in parent.placement_assignments
        )
    )
```

- [ ] **Step 2: Update `place_fragment()`**

After the group is created, add:

```python
from tuba.placements import PlacementAssignment, PlacementFrame

frame = PlacementFrame.from_coordinate_system(
    name,
    coordinate_system,
    frame_type="assembly",
    source="fragment",
    metadata={"fragment": fragment.name},
)
model.placement_frames[name] = frame
model.placement_assignments.append(
    PlacementAssignment(
        target=f"group:{name}",
        frame=f"placement_frame:{name}",
        role="object_placement",
        source="fragment",
    )
)
```

Keep existing group `coordinate_system` metadata for compatibility until downstream code uses placement frames.

- [ ] **Step 3: Run fragment tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fragments tests.test_placements -v
```

Expected:

```text
OK
```

### Task 7: Add IFC Placement Helper Module

**Files:**
- Create: `tuba/external/ifc_placements.py`
- Test: `tests/test_ifc_placements.py`

- [ ] **Step 1: Add helper tests**

Create `tests/test_ifc_placements.py`:

```python
import unittest

from tuba.external.ifc import _HAS_IFCOPENSHELL
from tuba.placements import PlacementFrame


@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacements(unittest.TestCase):
    def test_create_axis2placement_from_frame(self):
        import ifcopenshell

        from tuba.external.ifc_placements import create_axis2placement3d

        ifc_file = ifcopenshell.file(schema="IFC4")
        placement = create_axis2placement3d(
            ifc_file,
            PlacementFrame(
                id="rack_A",
                origin=(1.0, 2.0, 3.0),
                axis=(0.0, 0.0, 1.0),
                ref_direction=(0.0, 1.0, 0.0),
            ),
        )

        self.assertTrue(placement.is_a("IfcAxis2Placement3D"))
        self.assertEqual(tuple(float(v) for v in placement.Location.Coordinates), (1.0, 2.0, 3.0))
        self.assertEqual(tuple(float(v) for v in placement.RefDirection.DirectionRatios), (0.0, 1.0, 0.0))
```

- [ ] **Step 2: Implement helper module**

Create `tuba/external/ifc_placements.py`:

```python
from __future__ import annotations

from typing import Any

from tuba.placements import PlacementFrame


def create_axis2placement3d(ifc_file: Any, frame: PlacementFrame) -> Any:
    point = ifc_file.create_entity("IfcCartesianPoint", Coordinates=[float(v) for v in frame.origin])
    axis = ifc_file.create_entity("IfcDirection", DirectionRatios=[float(v) for v in frame.axis])
    ref_direction = ifc_file.create_entity("IfcDirection", DirectionRatios=[float(v) for v in frame.ref_direction])
    return ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=point,
        Axis=axis,
        RefDirection=ref_direction,
    )


def create_local_placement(ifc_file: Any, frame: PlacementFrame, parent_placement: Any | None = None) -> Any:
    return ifc_file.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=parent_placement,
        RelativePlacement=create_axis2placement3d(ifc_file, frame),
    )
```

- [ ] **Step 3: Run helper tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_placements -v
```

Expected:

```text
OK
```

If IfcOpenShell is not installed, expected:

```text
OK (skipped=1)
```

### Task 8: Export IFC Local Placements

**Files:**
- Modify: `tuba/external/ifc.py`
- Modify: `tuba/external/ifc_pipes.py`
- Test: `tests/test_ifc_placements.py`
- Test: `tests/test_ifc.py`

- [ ] **Step 1: Add IFC export test for placement metadata**

Add to `tests/test_ifc_placements.py`:

```python
@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacementExport(unittest.TestCase):
    def test_export_uses_native_product_placement_when_available(self):
        import ifcopenshell
        import tempfile
        from pathlib import Path

        from tuba import Model
        from tuba.external.ifc import IfcExporter
        from tuba.placements import PlacementAssignment, PlacementFrame

        model = Model("IfcPlacement")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([10.0, 20.0, 0.0]).run(1.0)
        elem = model.elements[0]
        model.placement_frames["pipe_frame"] = PlacementFrame(id="pipe_frame", origin=(10.0, 20.0, 0.0), frame_type="product")
        model.placement_assignments.append(
            PlacementAssignment(
                target=f"element:{elem.id}",
                frame="placement_frame:pipe_frame",
                role="object_placement",
                source="native",
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "placement.ifc"
            IfcExporter().export_model(model, path)
            ifc_file = ifcopenshell.open(str(path))
            product = ifc_file.by_type("IfcPipeSegment")[0]

        self.assertIsNotNone(product.ObjectPlacement)
        self.assertTrue(product.ObjectPlacement.RelativePlacement.is_a("IfcAxis2Placement3D"))
```

- [ ] **Step 2: Implement placement selection in exporter**

Add helper:

```python
def _placement_for_target(model, target: str):
    for assignment in getattr(model, "placement_assignments", []):
        if assignment.target == target and assignment.role == "object_placement":
            frame_id = assignment.frame.split(":", 1)[1]
            return model.placement_frames.get(frame_id)
    return None
```

When creating a product, set:

```python
frame = _placement_for_target(model, f"element:{elem.id}")
if frame is not None:
    product.ObjectPlacement = create_local_placement(ifc_file, frame)
```

Keep geometry coordinates unchanged for now. This produces a valid coordination signal without changing current swept directrix behavior. A later enrichment can emit product-local geometry when the exporter consistently supports relative body geometry.

- [ ] **Step 3: Run IFC tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_placements tests.test_ifc -v
```

Expected:

```text
OK
```

### Task 9: Import IFC Placement Chains As Metadata

**Files:**
- Modify: `tuba/external/ifc_placements.py`
- Modify: `tuba/external/ifc.py`
- Test: `tests/test_ifc_placements.py`

- [ ] **Step 1: Add importer helper tests**

Add to `tests/test_ifc_placements.py`:

```python
@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacementImport(unittest.TestCase):
    def test_extract_frame_from_ifc_local_placement(self):
        import ifcopenshell

        from tuba.external.ifc_placements import create_local_placement, frame_from_local_placement

        ifc_file = ifcopenshell.file(schema="IFC4")
        original = PlacementFrame(
            id="frame_1",
            origin=(1.0, 2.0, 3.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
            source="ifc",
        )
        local_placement = create_local_placement(ifc_file, original)

        imported = frame_from_local_placement("frame_1", local_placement)

        self.assertEqual(imported.origin, original.origin)
        self.assertEqual(imported.axis, original.axis)
        self.assertEqual(imported.ref_direction, original.ref_direction)
```

- [ ] **Step 2: Implement placement extraction**

In `tuba/external/ifc_placements.py`, add:

```python
def frame_from_local_placement(frame_id: str, local_placement: Any) -> PlacementFrame:
    relative = local_placement.RelativePlacement
    loc = tuple(float(v) for v in relative.Location.Coordinates)
    axis = (0.0, 0.0, 1.0)
    ref_direction = (1.0, 0.0, 0.0)
    if relative.Axis is not None:
        axis = tuple(float(v) for v in relative.Axis.DirectionRatios)
    if relative.RefDirection is not None:
        ref_direction = tuple(float(v) for v in relative.RefDirection.DirectionRatios)
    parent = None
    if local_placement.PlacementRelTo is not None:
        parent = f"ifc_placement:{local_placement.PlacementRelTo.id()}"
    return PlacementFrame(
        id=frame_id,
        origin=loc,
        axis=axis,
        ref_direction=ref_direction,
        parent=parent,
        frame_type="product",
        source="ifc",
        metadata={"ifc_local_placement_id": int(local_placement.id())},
    )
```

- [ ] **Step 3: Preserve imported placement metadata**

In `IfcImporter.import_model()`, when a product has `ObjectPlacement`, create a deterministic frame ID:

```python
frame_id = f"ifc_product_{product.id()}_placement"
model.placement_frames[frame_id] = frame_from_local_placement(frame_id, product.ObjectPlacement)
model.placement_assignments.append(
    PlacementAssignment(
        target=f"element:{created_element_id}",
        frame=f"placement_frame:{frame_id}",
        role="object_placement",
        source="ifc",
    )
)
```

Apply this after each imported pipe/beam element is created. If a product creates multiple Tuba elements, create one assignment per created element with the same frame.

- [ ] **Step 4: Run IFC import tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_placements tests.test_ifc -v
```

Expected:

```text
OK
```

### Task 10: Add Documentation And Final Verification

**Files:**
- Modify: `docs/agent_model_workflow.md`
- Modify: `docs/future_ready_architecture.md`
- Test: full suite

- [ ] **Step 1: Update docs**

In `docs/agent_model_workflow.md`, add a short section after the placement example:

````markdown
## IFC-Style Placement Frames

Placed fragments may also create a named `PlacementFrame`. The parent model still stores node coordinates in model-global Cartesian coordinates, but the frame is retained for GUI selection, IFC export, import provenance, and repeatable local editing.

Use explicit frames when authoring local coordinates:

```python
frame = model.placement_frames["rack_A"]
global_point = model.to_global_point((1.0, 0.0, 0.0), frame="placement_frame:rack_A")
```

Do not assume node coordinates are local just because a placement assignment exists.
````

In `docs/future_ready_architecture.md`, add one paragraph to `Core Direction`:

```markdown
Coordinate handling follows IFC placement semantics without making IFC the internal model. Native nodes remain in the model-global Cartesian frame; optional placement frames preserve site, assembly, product, and imported local placements for authoring and exchange.
```

- [ ] **Step 2: Run focused docs-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_coordinates tests.test_placements tests.test_fragments tests.test_ifc_placements -v
```

Expected:

```text
OK
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Expected:

```text
OK
```

- [ ] **Step 4: Optional viewer regression**

Run only if placement metadata is added to scene payloads during implementation:

```powershell
npm --prefix viewer test
```

Expected:

```text
all tests pass
```

## Implementation Notes

- Keep this additive. Old JSON without `placement_frames` and `placement_assignments` must load unchanged.
- Do not change solver export semantics in this slice. Code_Aster continues to receive global nodes and global vectors.
- Do not make route optimization depend on IFC import/export.
- Do not convert existing `groups["..."]["coordinate_system"]` metadata away immediately; use it as compatibility data until all downstream consumers understand `PlacementFrame`.
- For IFC export, prefer emitting placement metadata first, then localizing body geometry in a later dedicated exporter cleanup if needed. This prevents a large geometry regression in the first placement slice.
- If a local support/load reference is requested and the exporter cannot represent it correctly, reject it explicitly rather than silently treating it as global.
