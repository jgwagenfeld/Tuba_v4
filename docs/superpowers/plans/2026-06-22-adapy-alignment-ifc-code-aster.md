# Adapy Alignment IFC And Code Aster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transfer the useful IFC, Code_Aster, result-artifact, and optional interop lessons from `krande/adapy` into Tuba without replacing Tuba's pipe-native model, routing, or solver workflow.

**Architecture:** Keep `TubaModel` as the source of truth for scripted pipe generation, routing, stress workflows, supports, and agent patches. Add cleaner exchange boundaries around it: an IFC mapping layer, pipe-system IFC export/import, traceable Code_Aster sidecars, optional RMED artifact readers, and a default-off `adapy` bridge. Treat `adapy` as a reference and optional adapter only; do not copy GPL implementation code into Tuba.

**Tech Stack:** Python dataclasses, existing `unittest` style, `numpy`, `ifcopenshell` when installed, existing `meshio`, optional `h5py` for RMED inspection, existing `CodeAsterSolver`, existing viewer scene bundle format.

---

## Scope Check

This is an umbrella plan with independently shippable work packages:

1. License and dependency policy for `adapy`.
2. IFC mapping primitives and deterministic identity.
3. IFC pipe-system export and pipe bend geometry.
4. IFC import round-tripping for pipe sections, bends, systems, supports, and properties.
5. Code_Aster sidecars, short-name mapping, and manifest upgrades.
6. RMED/result artifact import strategy.
7. Optional `adapy` bridge.
8. Documentation, examples, and verification.

Do not implement this as one large commit. Each task below should pass tests and commit independently.

## Non-Goals

- Do not replace `TubaModel` with `ada.Assembly`.
- Do not replace `CodeAsterSolver` with `adapy`'s generic FEM exporter.
- Do not require IFC for routing, clash checks, or solver preparation.
- Do not make `ada-py` a mandatory dependency.
- Do not copy code from `adapy` into Tuba unless the project explicitly adopts GPL-compatible obligations.
- Do not remove the existing CSV result-table parser. RMED support is additive.

## Source Lessons From `adapy`

- `adapy` is GPL-3.0-or-later. Use it as a reference or optional runtime dependency only after an explicit license decision.
- `adapy` models pipe runs as `IfcDistributionSystem` with `IfcPipeSegment` and `IfcPipeFitting` flow elements contained in spatial structure.
- `adapy` round-trips pipe sections and segment composition through IFC tests.
- `adapy` writes Code_Aster MED/COMM files with name maps and solver-side lineage sidecars because solver result files do not carry all source semantics.
- `adapy` has a streaming RMED artifact strategy for large visualization payloads. Tuba should borrow the shape of that boundary, not the implementation.

## Files To Create Or Modify

- Create `docs/architecture/adapy-alignment.md`  
  Records the decision boundary: reference-only, no vendoring, optional bridge only.

- Create `tuba/external/ifc_mapping.py`  
  Owns IFC GUID reuse, typed property creation, property-set attachment, section-profile mapping, and representation helpers.

- Create `tuba/external/ifc_pipes.py`  
  Owns pipe run grouping, pipe segment export, bend axis/body geometry, and pipe-system relationships.

- Modify `tuba/external/ifc.py`  
  Use mapping helpers, delegate pipe export/import details, preserve existing public `IfcExporter` and `IfcImporter`.

- Create `tuba/solver/aster_sidecar.py`  
  Owns Code_Aster short-name mapping and Tuba solver-lineage sidecar serialization.

- Modify `tuba/solver/aster.py`  
  Write sidecars during `export_analysis_study()`, keep `.mail`, `.comm`, `.export` consistent with short names, and include sidecar paths in `AnalysisStudy`.

- Modify `tuba/analysis/code_aster_artifacts.py`  
  Load sidecars and optional RMED-derived context during artifact import.

- Create `tuba/analysis/rmed.py`  
  Optional lightweight RMED reader for mesh/field metadata and nodal displacement fallback.

- Create `tuba/external/adapy_bridge.py`  
  Default-off adapter for converting between Tuba and `ada-py` objects when `ada` is installed and license policy allows it.

- Modify `pyproject.toml`  
  Add optional extras only after the license gate is accepted. Keep core dependencies unchanged.

- Modify `README.md` and `docs/future_ready_architecture.md`  
  Document the new exchange boundary, sidecars, and optional bridge.

- Create or modify tests:
  - `tests/test_adapy_alignment_policy.py`
  - `tests/test_ifc_mapping.py`
  - `tests/test_ifc.py`
  - `tests/test_ifc_pipe_systems.py`
  - `tests/test_code_aster_study.py`
  - `tests/test_code_aster_sidecar.py`
  - `tests/test_code_aster_artifact_import.py`
  - `tests/test_rmed_artifacts.py`
  - `tests/test_adapy_bridge.py`

Use this baseline command after every task:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

---

### Task 1: Record License And Dependency Policy

**Files:**
- Create: `docs/architecture/adapy-alignment.md`
- Create: `tests/test_adapy_alignment_policy.py`
- Modify: `pyproject.toml` only if a license decision explicitly accepts an optional bridge extra

- [ ] **Step 1: Write the policy test**

Create `tests/test_adapy_alignment_policy.py`:

```python
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestAdapyAlignmentPolicy(unittest.TestCase):
    def test_policy_document_records_reference_only_boundary(self):
        text = (ROOT / "docs" / "architecture" / "adapy-alignment.md").read_text(encoding="utf-8")
        self.assertIn("Do not vendor adapy code", text)
        self.assertIn("GPL-3.0-or-later", text)
        self.assertIn("optional bridge", text)

    def test_core_dependencies_do_not_require_adapy(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dependencies_block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("ada-py", dependencies_block)
        self.assertNotIn('"ada"', dependencies_block)
```

- [ ] **Step 2: Run the failing policy test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_adapy_alignment_policy -v
```

Expected:

```text
FileNotFoundError: docs\architecture\adapy-alignment.md
```

- [ ] **Step 3: Create the policy document**

Create `docs/architecture/adapy-alignment.md`:

```markdown
# Adapy Alignment Policy

## Decision

Tuba may learn from `krande/adapy` architecture and may provide a default-off optional bridge, but Tuba must not vendor or copy `adapy` implementation code.

## License Boundary

`ada-py` is licensed GPL-3.0-or-later. Do not vendor adapy code into Tuba unless the project explicitly accepts GPL-compatible obligations. Any adapter must import `ada` at runtime behind an optional dependency and must keep Tuba's core package usable without `ada-py`.

## Product Boundary

Tuba remains pipe-native. `TubaModel`, routing, supports, Code_Aster pipe stress export, result states, deformed envelopes, and clash checks remain authoritative. IFC and `adapy` are exchange and interoperability surfaces, not internal optimization requirements.

## Allowed Transfers

- IFC pipe-system semantics.
- IFC round-trip test shape.
- Solver sidecar and name-map concepts.
- RMED artifact manifest concepts.
- Optional bridge APIs that are disabled when `ada` is not installed.

## Disallowed Transfers

- Direct source copying from `adapy`.
- Mandatory `ada-py` dependency in the core package.
- Replacing `CodeAsterSolver` with a generic FEM exporter.
- Requiring IFC import/export for routing or clash checks.
```

- [ ] **Step 4: Run the policy test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_adapy_alignment_policy -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add docs/architecture/adapy-alignment.md tests/test_adapy_alignment_policy.py
git commit -m "docs: record adapy alignment boundary"
```

---

### Task 2: Add IFC Mapping Primitives

**Files:**
- Create: `tuba/external/ifc_mapping.py`
- Modify: `tests/test_ifc_mapping.py`
- Modify: `tuba/external/ifc.py`

- [ ] **Step 1: Extend IFC mapping tests**

Replace `tests/test_ifc_mapping.py` with:

```python
import unittest

import ifcopenshell

from tuba.external.ifc import IfcExporter
from tuba.external.ifc_mapping import IfcGuidRegistry, add_property_set, ifc_property


class TestIfcMapping(unittest.TestCase):
    def test_ifc_exporter_exposes_operating_state_property_set_name(self):
        self.assertEqual(IfcExporter.OPERATING_STATE_PSET, "Pset_TubaOperatingState")

    def test_guid_registry_reuses_guid_for_same_ref(self):
        registry = IfcGuidRegistry()
        first = registry.guid_for("element:pipe_0")
        second = registry.guid_for("element:pipe_0")
        other = registry.guid_for("element:pipe_1")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 22)

    def test_property_set_helper_attaches_typed_values(self):
        f = ifcopenshell.file(schema="IFC4")
        wall = f.create_entity("IfcBuildingElementProxy", GlobalId=IfcGuidRegistry().guid_for("obstacle:x"), Name="x")
        add_property_set(
            f,
            wall,
            "Pset_Tuba_Test",
            [
                ifc_property(f, "Name", "Pipe"),
                ifc_property(f, "Count", 3),
                ifc_property(f, "Ratio", 1.25),
                ifc_property(f, "Enabled", True),
            ],
        )

        psets = [
            rel.RelatingPropertyDefinition
            for rel in wall.IsDefinedBy
            if rel.is_a("IfcRelDefinesByProperties")
        ]
        self.assertEqual(psets[0].Name, "Pset_Tuba_Test")
        values = {prop.Name: prop.NominalValue.wrappedValue for prop in psets[0].HasProperties}
        self.assertEqual(values["Name"], "Pipe")
        self.assertEqual(values["Count"], 3)
        self.assertEqual(values["Ratio"], 1.25)
        self.assertEqual(values["Enabled"], True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_mapping -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.external.ifc_mapping'
```

- [ ] **Step 3: Implement `tuba/external/ifc_mapping.py`**

Create the file with these public functions and classes:

```python
"""Shared IFC mapping helpers for Tuba exchange adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

import ifcopenshell
import ifcopenshell.guid


@dataclass
class IfcGuidRegistry:
    """Deterministic IFC GUID registry keyed by stable Tuba refs."""

    namespace: str = "tuba"
    _cache: dict[str, str] = field(default_factory=dict)

    def guid_for(self, ref: str) -> str:
        key = f"{self.namespace}:{ref}"
        if key not in self._cache:
            digest = hashlib.md5(key.encode("utf-8")).hexdigest()
            self._cache[key] = ifcopenshell.guid.compress(digest)
        return self._cache[key]


def ifc_property(ifc_file: Any, name: str, value: Any) -> Any:
    if isinstance(value, bool):
        nominal = ifc_file.create_entity("IfcBoolean", bool(value))
    elif isinstance(value, int):
        nominal = ifc_file.create_entity("IfcInteger", int(value))
    elif isinstance(value, float):
        nominal = ifc_file.create_entity("IfcReal", float(value))
    else:
        nominal = ifc_file.create_entity("IfcLabel", "" if value is None else str(value))
    return ifc_file.create_entity("IfcPropertySingleValue", Name=name, NominalValue=nominal)


def add_property_set(ifc_file: Any, product: Any, name: str, properties: Iterable[Any]) -> Any:
    guid = ifcopenshell.guid.new()
    pset = ifc_file.create_entity(
        "IfcPropertySet",
        GlobalId=guid,
        Name=name,
        HasProperties=list(properties),
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[product],
        RelatingPropertyDefinition=pset,
    )
    return pset
```

- [ ] **Step 4: Wire existing `_ifc_property` calls to the helper**

In `tuba/external/ifc.py`, import `ifc_property` and replace the local `_ifc_property` usage in `_add_operating_state_property_sets()` with the shared helper. Keep `_ifc_property` as a compatibility alias for now:

```python
from tuba.external.ifc_mapping import ifc_property


def _ifc_property(ifc_file: Any, name: str, value: Any) -> Any:
    return ifc_property(ifc_file, name, value)
```

- [ ] **Step 5: Run IFC mapping tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_mapping -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/external/ifc_mapping.py tuba/external/ifc.py tests/test_ifc_mapping.py
git commit -m "feat: add shared IFC mapping helpers"
```

---

### Task 3: Export Pipe Runs As IFC Distribution Systems

**Files:**
- Create: `tuba/external/ifc_pipes.py`
- Modify: `tuba/external/ifc.py`
- Create: `tests/test_ifc_pipe_systems.py`

- [ ] **Step 1: Write pipe-system export tests**

Create `tests/test_ifc_pipe_systems.py`:

```python
import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from tuba import Model
from tuba.external.ifc import IfcExporter


class TestIfcPipeSystems(unittest.TestCase):
    def _model(self):
        model = Model(project_name="PipeSystemIfc")
        model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        n2 = model.add_node((1.0, 1.0, 0.0))
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="DN100", material="Steel")
        model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n1,
            n2=n2,
            section="DN100",
            material="Steel",
            bend_radius=0.25,
            bend_angle=90.0,
        )
        return model

    def test_export_groups_pipe_segments_into_distribution_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        systems = f.by_type("IfcDistributionSystem")
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].Name, "PipeSystemIfc")

        segments = f.by_type("IfcPipeSegment")
        fittings = f.by_type("IfcPipeFitting")
        self.assertEqual(len(segments), 1)
        self.assertEqual(len(fittings), 1)

        assigned = []
        for rel in f.by_type("IfcRelAssignsToGroup"):
            if rel.RelatingGroup == systems[0]:
                assigned.extend(rel.RelatedObjects)
        self.assertEqual({obj.Name for obj in assigned}, {"pipe_0", "pipe_bend_0"})

    def test_pipe_products_have_axis_and_body_representations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        product = next(p for p in f.by_type("IfcPipeSegment") if p.Name == "pipe_0")
        identifiers = {rep.RepresentationIdentifier for rep in product.Representation.Representations}
        self.assertIn("Axis", identifiers)
        self.assertIn("Body", identifiers)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems -v
```

Expected:

```text
AssertionError: 0 != 1
```

- [ ] **Step 3: Implement pipe-system export helpers**

Create `tuba/external/ifc_pipes.py` with these public functions:

```python
"""IFC export helpers for Tuba pipe systems."""

from __future__ import annotations

from typing import Any

import ifcopenshell.guid
import numpy as np

from tuba.external.ifc_mapping import IfcGuidRegistry, add_property_set, ifc_property


def export_pipe_products(ifc_file: Any, model: Any, storey: Any, project_context: Any, registry: IfcGuidRegistry) -> dict[str, Any]:
    created: dict[str, Any] = {}
    pipe_elements = [elem for elem in model.elements if elem.type in ("pipe_straight", "pipe_bend")]
    if not pipe_elements:
        return created

    products = []
    for elem in pipe_elements:
        product = _create_pipe_product(ifc_file, model, elem, project_context, registry)
        created[elem.id] = product
        products.append(product)

    ifc_file.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=products,
    )
    system = ifc_file.create_entity(
        "IfcDistributionSystem",
        GlobalId=registry.guid_for(f"pipe-system:{model.project_name}"),
        Name=model.project_name,
        PredefinedType="NOTDEFINED",
    )
    ifc_file.create_entity(
        "IfcRelAssignsToGroup",
        GlobalId=ifcopenshell.guid.new(),
        Name=f"{model.project_name} pipe run",
        RelatedObjects=products,
        RelatingGroup=system,
    )
    ifc_file.create_entity(
        "IfcRelServicesBuildings",
        GlobalId=ifcopenshell.guid.new(),
        Name=f"{model.project_name} services",
        RelatingSystem=system,
        RelatedBuildings=[storey],
    )
    return created


def _create_pipe_product(ifc_file: Any, model: Any, elem: Any, context: Any, registry: IfcGuidRegistry) -> Any:
    cls_name = "IfcPipeFitting" if elem.type == "pipe_bend" else "IfcPipeSegment"
    kwargs = {}
    if elem.type == "pipe_bend":
        kwargs["PredefinedType"] = "BEND"
    product = ifc_file.create_entity(
        cls_name,
        GlobalId=registry.guid_for(f"element:{elem.id}"),
        Name=elem.id,
        Description=f"Material: {elem.material}, Section: {elem.section}",
        **kwargs,
    )
    axis_points = _pipe_axis_points(model, elem)
    body = _swept_disk_body(ifc_file, model, elem, axis_points)
    axis = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Axis",
        RepresentationType="Curve3D",
        Items=[_polyline(ifc_file, axis_points)],
    )
    body_rep = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[body],
    )
    product.Representation = ifc_file.create_entity("IfcProductDefinitionShape", Representations=[axis, body_rep])
    if elem.type == "pipe_bend":
        add_property_set(
            ifc_file,
            product,
            "Pset_TubaPipeBend",
            [
                ifc_property(ifc_file, "BendRadiusM", float(elem.bend_radius or 0.0)),
                ifc_property(ifc_file, "BendAngleDeg", float(elem.bend_angle or 0.0)),
            ],
        )
    return product


def _pipe_axis_points(model: Any, elem: Any) -> list[np.ndarray]:
    p1 = np.asarray(model.nodes[elem.n1].coords, dtype=float)
    p2 = np.asarray(model.nodes[elem.n2].coords, dtype=float)
    return [p1, p2]


def _swept_disk_body(ifc_file: Any, model: Any, elem: Any, axis_points: list[np.ndarray]) -> Any:
    section = model.sections[elem.section]
    radius = float(section.OD / 2.0)
    inner_radius = float(max(section.OD - 2.0 * section.WT, 0.0) / 2.0)
    return ifc_file.create_entity(
        "IfcSweptDiskSolid",
        Directrix=_polyline(ifc_file, axis_points),
        Radius=radius,
        InnerRadius=inner_radius,
    )


def _polyline(ifc_file: Any, points: list[np.ndarray]) -> Any:
    ifc_points = [
        ifc_file.create_entity("IfcCartesianPoint", Coordinates=[float(p[0]), float(p[1]), float(p[2])])
        for p in points
    ]
    return ifc_file.create_entity("IfcPolyline", Points=ifc_points)
```

- [ ] **Step 4: Delegate pipe export from `IfcExporter.export_model()`**

In `tuba/external/ifc.py`:

1. Create `registry = IfcGuidRegistry()` after the storey is created.
2. Call `export_pipe_products(ifc_file, model, storey, project, registry)` before the current element loop.
3. Skip pipe elements in the old generic loop.
4. Merge returned pipe products into `created_elements`.

The key control flow should become:

```python
from tuba.external.ifc_mapping import IfcGuidRegistry
from tuba.external.ifc_pipes import export_pipe_products

registry = IfcGuidRegistry()
created_elements.update(export_pipe_products(ifc_file, model, storey, project, registry))

for elem in model.elements:
    if elem.type in ("pipe_straight", "pipe_bend"):
        continue
    # Keep the existing non-pipe export branch here.
```

- [ ] **Step 5: Run pipe-system tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Run existing IFC tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc tests.test_ifc_mapping -v
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add tuba/external/ifc.py tuba/external/ifc_pipes.py tests/test_ifc_pipe_systems.py
git commit -m "feat: export pipes as IFC distribution systems"
```

---

### Task 4: Improve IFC Bend Geometry And Pipe Section Metadata

**Files:**
- Modify: `tuba/external/ifc_pipes.py`
- Modify: `tests/test_ifc_pipe_systems.py`
- Modify: `tests/test_ifc.py`

- [ ] **Step 1: Add tests for bend axis discretization and section properties**

Append to `tests/test_ifc_pipe_systems.py`:

```python
    def test_pipe_bend_body_uses_more_than_two_axis_points(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        bend = next(p for p in f.by_type("IfcPipeFitting") if p.Name == "pipe_bend_0")
        axis_rep = next(rep for rep in bend.Representation.Representations if rep.RepresentationIdentifier == "Axis")
        polyline = axis_rep.Items[0]
        self.assertGreater(len(polyline.Points), 2)

    def test_pipe_section_properties_are_exported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        segment = next(p for p in f.by_type("IfcPipeSegment") if p.Name == "pipe_0")
        psets = [
            rel.RelatingPropertyDefinition
            for rel in segment.IsDefinedBy
            if rel.is_a("IfcRelDefinesByProperties")
        ]
        pipe_pset = next(pset for pset in psets if pset.Name == "Pset_TubaPipe")
        values = {prop.Name: prop.NominalValue.wrappedValue for prop in pipe_pset.HasProperties}
        self.assertEqual(values["SectionName"], "DN100")
        self.assertAlmostEqual(values["OuterDiameterM"], 0.1143)
        self.assertAlmostEqual(values["WallThicknessM"], 0.00602)
```

- [ ] **Step 2: Run the failing bend and section tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems -v
```

Expected:

```text
FAIL: test_pipe_bend_body_uses_more_than_two_axis_points
FAIL: test_pipe_section_properties_are_exported
```

- [ ] **Step 3: Add bend axis point generation**

In `tuba/external/ifc_pipes.py`, change `_pipe_axis_points()` so bends use generated arc points. Reuse the existing `CodeAsterSolver._get_bend_geometry()` math instead of introducing an IFC-only geometry model:

```python
def _pipe_axis_points(model: Any, elem: Any) -> list[np.ndarray]:
    if elem.type != "pipe_bend":
        return [
            np.asarray(model.nodes[elem.n1].coords, dtype=float),
            np.asarray(model.nodes[elem.n2].coords, dtype=float),
        ]

    from tuba.solver.aster import CodeAsterSolver

    center, axis, r1, theta = CodeAsterSolver._get_bend_geometry(model, elem)
    steps = 8
    points = []
    for index in range(steps + 1):
        t = index / steps
        angle = theta * t
        rotated = _rotate_about_axis(r1, axis, angle)
        points.append(center + rotated)
    return points


def _rotate_about_axis(vector: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    vector = np.asarray(vector, dtype=float)
    return (
        vector * np.cos(angle)
        + np.cross(axis, vector) * np.sin(angle)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle))
    )
```

- [ ] **Step 4: Add pipe property sets to every pipe product**

In `_create_pipe_product()`, after creating `product`, add:

```python
    section = model.sections[elem.section]
    add_property_set(
        ifc_file,
        product,
        "Pset_TubaPipe",
        [
            ifc_property(ifc_file, "SectionName", elem.section),
            ifc_property(ifc_file, "MaterialName", elem.material),
            ifc_property(ifc_file, "OuterDiameterM", float(section.OD)),
            ifc_property(ifc_file, "WallThicknessM", float(section.WT)),
        ],
    )
```

- [ ] **Step 5: Run pipe-system tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/external/ifc_pipes.py tests/test_ifc_pipe_systems.py
git commit -m "feat: export pipe bend axis and section metadata"
```

---

### Task 5: Round-Trip IFC Pipe Sections, Bends, And Systems

**Files:**
- Modify: `tuba/external/ifc.py`
- Modify: `tests/test_ifc.py`
- Modify: `tests/test_ifc_pipe_systems.py`

- [ ] **Step 1: Add round-trip tests for pipe section and bend metadata**

Append to `tests/test_ifc_pipe_systems.py`:

```python
    def test_import_preserves_pipe_section_dimensions_and_bend_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            imported = __import__("tuba.external.ifc", fromlist=["IfcImporter"]).IfcImporter().import_model(path)

        self.assertIn("DN100", imported.sections)
        section = imported.sections["DN100"]
        self.assertAlmostEqual(section.OD, 0.1143)
        self.assertAlmostEqual(section.WT, 0.00602)

        bends = [elem for elem in imported.elements if elem.type == "pipe_bend"]
        self.assertEqual(len(bends), 1)
        self.assertAlmostEqual(bends[0].bend_radius, 0.25)
        self.assertAlmostEqual(bends[0].bend_angle, 90.0)
```

- [ ] **Step 2: Run the failing import test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems.TestIfcPipeSystems.test_import_preserves_pipe_section_dimensions_and_bend_metadata -v
```

Expected:

```text
FAIL: test_import_preserves_pipe_section_dimensions_and_bend_metadata
```

- [ ] **Step 3: Read `Pset_TubaPipe` in `IfcImporter.import_model()`**

Add a helper inside `IfcImporter.import_model()`:

```python
        def get_pset_values(product, pset_name: str) -> dict[str, object]:
            values = {}
            for definition in getattr(product, "IsDefinedBy", []):
                if not definition.is_a("IfcRelDefinesByProperties"):
                    continue
                pset = definition.RelatingPropertyDefinition
                if not pset.is_a("IfcPropertySet") or pset.Name != pset_name:
                    continue
                for prop in pset.HasProperties:
                    if prop.is_a("IfcPropertySingleValue") and prop.NominalValue is not None:
                        values[prop.Name] = prop.NominalValue.wrappedValue
            return values
```

- [ ] **Step 4: Use pipe property sets during pipe import**

In the `IfcPipeSegment` loop, replace the hard-coded `sec_name = "StandardPipe"` with:

```python
                pipe_props = get_pset_values(pipe, "Pset_TubaPipe")
                sec_name = str(pipe_props.get("SectionName", "StandardPipe"))
                if sec_name not in model.sections and "OuterDiameterM" in pipe_props and "WallThicknessM" in pipe_props:
                    model.add_pipe_section(
                        sec_name,
                        OD=float(pipe_props["OuterDiameterM"]),
                        WT=float(pipe_props["WallThicknessM"]),
                    )
```

In the `IfcPipeFitting` loop, use both `Pset_TubaPipe` and `Pset_TubaPipeBend`:

```python
                pipe_props = get_pset_values(fitting, "Pset_TubaPipe")
                bend_props = get_pset_values(fitting, "Pset_TubaPipeBend")
                sec_name = str(pipe_props.get("SectionName", "StandardPipe"))
                if sec_name not in model.sections and "OuterDiameterM" in pipe_props and "WallThicknessM" in pipe_props:
                    model.add_pipe_section(
                        sec_name,
                        OD=float(pipe_props["OuterDiameterM"]),
                        WT=float(pipe_props["WallThicknessM"]),
                    )
                bend_radius = float(bend_props.get("BendRadiusM", 0.15))
                bend_angle = float(bend_props.get("BendAngleDeg", 90.0))
```

Pass `section=sec_name`, `bend_radius=bend_radius`, and `bend_angle=bend_angle` into `model.add_element()`.

- [ ] **Step 5: Run IFC pipe import tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_pipe_systems tests.test_ifc -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/external/ifc.py tests/test_ifc_pipe_systems.py
git commit -m "feat: round-trip IFC pipe metadata"
```

---

### Task 6: Add Code_Aster Sidecars And Short-Name Mapping

**Files:**
- Create: `tuba/solver/aster_sidecar.py`
- Create: `tests/test_code_aster_sidecar.py`
- Modify: `tuba/solver/aster.py`
- Modify: `tests/test_code_aster_study.py`

- [ ] **Step 1: Write sidecar unit tests**

Create `tests/test_code_aster_sidecar.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar


class TestCodeAsterSidecar(unittest.TestCase):
    def test_long_names_are_mapped_to_short_deterministic_names(self):
        mapping = build_solver_name_map(["PipeStraights", "element_with_a_name_that_is_longer_than_24_chars"])

        self.assertEqual(mapping["PipeStraights"], "PipeStraights")
        self.assertLessEqual(len(mapping["element_with_a_name_that_is_longer_than_24_chars"]), 24)
        self.assertEqual(
            mapping["element_with_a_name_that_is_longer_than_24_chars"],
            build_solver_name_map(["element_with_a_name_that_is_longer_than_24_chars"])["element_with_a_name_that_is_longer_than_24_chars"],
        )

    def test_sidecar_contains_name_map_and_analysis_mesh_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "study_tuba_fem.json"
            dump_solver_sidecar(
                path,
                solver_name="Code_Aster",
                load_case="Hot",
                analysis_mesh_id="analysis_mesh:Hot",
                name_map={"long": "G000001"},
                lineage={"G000001": "element:long"},
            )
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["solver_name"], "Code_Aster")
        self.assertEqual(data["analysis_mesh_id"], "analysis_mesh:Hot")
        self.assertEqual(data["name_map"]["long"], "G000001")
        self.assertEqual(data["lineage"]["G000001"], "element:long")
```

- [ ] **Step 2: Run the failing sidecar tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_sidecar -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.solver.aster_sidecar'
```

- [ ] **Step 3: Implement sidecar helpers**

Create `tuba/solver/aster_sidecar.py`:

```python
"""Code_Aster sidecar helpers for traceable Tuba solver exports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


MAX_ASTER_NAME_LEN = 24


def build_solver_name_map(names: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        if len(name) <= MAX_ASTER_NAME_LEN and name not in used:
            mapped = name
        else:
            digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8].upper()
            mapped = f"G_{digest}"
            suffix = 1
            while mapped in used:
                mapped = f"G_{digest[:6]}_{suffix:02d}"
                suffix += 1
        mapping[name] = mapped
        used.add(mapped)
    return mapping


def dump_solver_sidecar(
    path: str | Path,
    *,
    solver_name: str,
    load_case: str,
    analysis_mesh_id: str,
    name_map: dict[str, str],
    lineage: dict[str, str],
) -> None:
    payload = {
        "schema_version": 1,
        "solver_name": solver_name,
        "load_case": load_case,
        "analysis_mesh_id": analysis_mesh_id,
        "name_map": dict(sorted(name_map.items())),
        "lineage": dict(sorted(lineage.items())),
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
```

- [ ] **Step 4: Run sidecar unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_sidecar -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Add sidecar output to `export_analysis_study()`**

In `CodeAsterSolver.export_analysis_study()`:

1. Compute `sidecar_path = wdir / "study_tuba_fem.json"`.
2. Build a name map from `analysis_mesh.groups.keys()` and `analysis_mesh.elements.keys()`.
3. Build lineage from `analysis_mesh.element_sources`.
4. Write the sidecar.
5. Add `"sidecar": str(sidecar_path)` to `study.input_files`.

Use this code shape after `analysis_mesh` is created:

```python
        from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar

        sidecar_path = wdir / "study_tuba_fem.json"
        solver_names = list(analysis_mesh.groups.keys()) + list(analysis_mesh.elements.keys())
        name_map = build_solver_name_map(solver_names)
        lineage = {
            name_map[element_id]: str(source.source_ref)
            for element_id, source in analysis_mesh.element_sources.items()
            if element_id in name_map
        }
        dump_solver_sidecar(
            sidecar_path,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            analysis_mesh_id=analysis_mesh.id,
            name_map=name_map,
            lineage=lineage,
        )
```

- [ ] **Step 6: Extend study manifest test**

In `tests/test_code_aster_study.py`, add:

```python
        self.assertIn("sidecar", loaded_study.input_files)
        sidecar_path = Path(loaded_study.input_files["sidecar"])
        self.assertTrue(sidecar_path.name.endswith("study_tuba_fem.json"))
```

- [ ] **Step 7: Run study and sidecar tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_sidecar tests.test_code_aster_study -v
```

Expected:

```text
OK
```

- [ ] **Step 8: Commit**

```powershell
git add tuba/solver/aster_sidecar.py tuba/solver/aster.py tests/test_code_aster_sidecar.py tests/test_code_aster_study.py
git commit -m "feat: write Code_Aster solver sidecars"
```

---

### Task 7: Apply Short Names Consistently In Mail And Comm Files

**Files:**
- Modify: `tuba/solver/aster.py`
- Modify: `tuba/solver/aster_sidecar.py`
- Modify: `tests/test_code_aster_study.py`
- Modify: `tests/test_code_aster_sidecar.py`

- [ ] **Step 1: Write an export test with long element names**

Add to `tests/test_code_aster_study.py`:

```python
    def test_export_analysis_study_shortens_long_solver_group_names(self):
        model = Model(project_name="LongNames")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        long_id = "pipe_segment_with_a_name_that_exceeds_code_aster_limit"
        model.add_element(id=long_id, type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.define_load_case("Hot", gravity=True)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            mail = (root / "study.mail").read_text(encoding="utf-8")
            comm = (root / "study.comm").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        short_name = sidecar["name_map"][long_id]
        self.assertLessEqual(len(short_name), 24)
        self.assertIn(short_name, mail)
        self.assertIn(short_name, comm)
        self.assertNotIn(long_id, mail)
```

- [ ] **Step 2: Run the failing long-name test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study.TestCodeAsterStudyManifest.test_export_analysis_study_shortens_long_solver_group_names -v
```

Expected:

```text
FAIL: test_export_analysis_study_shortens_long_solver_group_names
```

- [ ] **Step 3: Add a solver-name mapping object**

In `tuba/solver/aster_sidecar.py`, add:

```python
class SolverNameMap:
    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping = dict(mapping or {})

    def __call__(self, name: str) -> str:
        return self.mapping.get(name, name)
```

- [ ] **Step 4: Thread the name map through `_write_mail()` and `_write_comm()`**

Change signatures:

```python
    def _write_mail(
        self,
        model: TubaModel,
        path: Path,
        *,
        analysis_mesh_id: str | None = None,
        model_revision: int = 0,
        name_map: Callable[[str], str] | None = None,
    ) -> AnalysisMesh | None:
```

```python
    def _write_comm(
        self,
        model: TubaModel,
        load_case: LoadCase,
        path: Path,
        *,
        name_map: Callable[[str], str] | None = None,
    ) -> None:
```

At the top of each method:

```python
        map_name = name_map or (lambda value: value)
```

Apply `map_name(name)` to every solver-visible node group and element group name written to `.mail` and `.comm`. Do not change native IDs in `AnalysisMesh`; the sidecar maps native IDs to solver names.

- [ ] **Step 5: Build name map before writing files in `export_analysis_study()`**

Split `export_analysis_study()` into two phases:

1. Build analysis mesh from native names without writing files.
2. Build name map.
3. Write `.mail` and `.comm` with mapped names.
4. Write sidecar and manifest.

Keep `export_study()` behavior compatible by using identity mapping there until this flow is proven.

- [ ] **Step 6: Run Code_Aster study tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study tests.test_code_aster_sidecar -v
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add tuba/solver/aster.py tuba/solver/aster_sidecar.py tests/test_code_aster_study.py tests/test_code_aster_sidecar.py
git commit -m "feat: apply Code_Aster short-name mapping"
```

---

### Task 8: Add Optional RMED Artifact Reader

**Files:**
- Create: `tuba/analysis/rmed.py`
- Create: `tests/test_rmed_artifacts.py`
- Modify: `tuba/analysis/code_aster_artifacts.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `h5py` as an optional dependency**

In `pyproject.toml`, add:

```toml
code-aster-rmed = [
    "h5py>=3.10",
]
```

under `[project.optional-dependencies]`.

- [ ] **Step 2: Write tests using a minimal RMED-like HDF5 file**

Create `tests/test_rmed_artifacts.py`:

```python
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tuba.analysis.rmed import read_rmed_mesh_summary


class TestRmedArtifacts(unittest.TestCase):
    def test_missing_h5py_error_is_actionable_or_summary_loads(self):
        try:
            import h5py
        except ImportError:
            with self.assertRaisesRegex(ImportError, "h5py"):
                read_rmed_mesh_summary("missing.rmed")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "study.rmed"
            with h5py.File(path, "w") as f:
                mesh_root = f.create_group("ENS_MAA")
                mesh = mesh_root.create_group("mesh")
                mesh.attrs["ESP"] = 3
                noe = mesh.create_group("NOE")
                coo = noe.create_dataset("COO", data=np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]))
                coo.attrs["NBR"] = 2
                mai = mesh.create_group("MAI")
                seg2 = mai.create_group("SE2")
                nod = seg2.create_dataset("NOD", data=np.array([1, 2]))
                nod.attrs["NBR"] = 1
                seg2.create_dataset("NUM", data=np.array([10]))

            summary = read_rmed_mesh_summary(path)

        self.assertEqual(summary["node_count"], 2)
        self.assertEqual(summary["element_count"], 1)
        self.assertEqual(summary["element_types"], {"SE2": 1})
```

- [ ] **Step 3: Run the failing RMED test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rmed_artifacts -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.analysis.rmed'
```

- [ ] **Step 4: Implement `tuba/analysis/rmed.py`**

Create:

```python
"""Optional RMED/HDF5 inspection helpers for Code_Aster artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _require_h5py():
    try:
        import h5py
    except ImportError as exc:
        raise ImportError("h5py is required for RMED inspection. Install tuba[code-aster-rmed].") from exc
    return h5py


def read_rmed_mesh_summary(path: str | Path) -> dict[str, Any]:
    h5py = _require_h5py()
    with h5py.File(path, "r") as f:
        mesh_root = f["ENS_MAA"]
        mesh_name = next(iter(mesh_root.keys()))
        mesh = mesh_root[mesh_name]
        node_count = int(mesh["NOE"]["COO"].attrs["NBR"])
        element_types = {}
        element_count = 0
        if "MAI" in mesh:
            for med_type, group in mesh["MAI"].items():
                count = int(group["NOD"].attrs["NBR"])
                element_types[med_type] = count
                element_count += count
        return {
            "mesh_name": mesh_name,
            "node_count": node_count,
            "element_count": element_count,
            "element_types": element_types,
        }
```

- [ ] **Step 5: Attach RMED summary during artifact import**

In `tuba/analysis/code_aster_artifacts.py`, after artifact files are collected:

```python
from dataclasses import replace


    rmed_path = root / "study.rmed"
    if rmed_path.exists():
        try:
            from tuba.analysis.rmed import read_rmed_mesh_summary
            result_state = replace(
                result_state,
                metadata={**result_state.metadata, "rmed_summary": read_rmed_mesh_summary(rmed_path)},
            )
        except ImportError as exc:
            diagnostics.append(_diagnostic("visualization.code_aster_artifacts.rmed_optional_dependency", str(exc), str(rmed_path), severity="warning"))
        except Exception as exc:
            diagnostics.append(_diagnostic("visualization.code_aster_artifacts.rmed_read_failed", str(exc), str(rmed_path), severity="warning"))
```

When implementing this, avoid manually reconstructing `ResultState` inline if a small helper keeps the code cleaner.

- [ ] **Step 6: Run RMED tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rmed_artifacts -v
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml tuba/analysis/rmed.py tuba/analysis/code_aster_artifacts.py tests/test_rmed_artifacts.py
git commit -m "feat: add optional RMED artifact inspection"
```

---

### Task 9: Add Default-Off Adapy Bridge

**Files:**
- Create: `tuba/external/adapy_bridge.py`
- Create: `tests/test_adapy_bridge.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Add tests for optional dependency behavior**

Create `tests/test_adapy_bridge.py`:

```python
import unittest

from tuba import Model
from tuba.external.adapy_bridge import adapy_available, require_adapy, tuba_to_adapy


class TestAdapyBridge(unittest.TestCase):
    def test_require_adapy_reports_optional_dependency_when_missing(self):
        if adapy_available():
            self.skipTest("ada is installed in this environment")
        with self.assertRaisesRegex(ImportError, "optional adapy bridge"):
            require_adapy()

    def test_tuba_to_adapy_requires_adapy(self):
        if adapy_available():
            self.skipTest("covered by integration test when ada is installed")
        model = Model("Bridge")
        with self.assertRaisesRegex(ImportError, "optional adapy bridge"):
            tuba_to_adapy(model)
```

- [ ] **Step 2: Run the failing bridge tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_adapy_bridge -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.external.adapy_bridge'
```

- [ ] **Step 3: Implement the optional bridge shell**

Create `tuba/external/adapy_bridge.py`:

```python
"""Optional bridge between Tuba and ada-py.

This module must not make ada-py a core dependency. It imports `ada` only inside
helper functions and raises an actionable error when the optional dependency is
missing.
"""

from __future__ import annotations

from typing import Any


def adapy_available() -> bool:
    try:
        import ada  # noqa: F401
    except ImportError:
        return False
    return True


def require_adapy() -> Any:
    try:
        import ada
    except ImportError as exc:
        raise ImportError(
            "The optional adapy bridge requires ada-py. Install the bridge extra only after accepting the GPL-3.0-or-later dependency boundary."
        ) from exc
    return ada


def tuba_to_adapy(model: Any) -> Any:
    ada = require_adapy()
    assembly = ada.Assembly(model.project_name)
    part = ada.Part(model.project_name)
    assembly / part
    return assembly
```

- [ ] **Step 4: Add optional extra only after license acceptance**

If the project accepts the optional GPL dependency boundary, add:

```toml
adapy-bridge = [
    "ada-py>=0.25",
]
```

Do not add this extra without a project decision. The bridge module can exist without the extra.

- [ ] **Step 5: Run bridge tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_adapy_bridge -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/external/adapy_bridge.py tests/test_adapy_bridge.py README.md pyproject.toml
git commit -m "feat: add optional adapy bridge boundary"
```

---

### Task 10: Documentation And End-To-End Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/future_ready_architecture.md`
- Modify: `examples/code_aster_artifact_review.py` if sidecar/RMED metadata should appear in the sample output
- Modify: `examples/future_ready_semantic_workflow.py` if IFC pipe-system export should be demonstrated

- [ ] **Step 1: Update README IFC section**

Add a concise section to `README.md`:

```markdown
## IFC And External Interop

Tuba exports pipe runs as IFC pipe systems while keeping `TubaModel` as the source of truth. Pipe flow elements are emitted as `IfcPipeSegment` and `IfcPipeFitting` products grouped by an `IfcDistributionSystem`. Tuba property sets carry section, material, bend, support, stress, and operating-state metadata for round-trip and coordination review.

`ada-py` is treated as an optional interoperability bridge, not a core dependency. See `docs/architecture/adapy-alignment.md` before enabling the optional bridge.
```

- [ ] **Step 2: Update Code_Aster architecture docs**

In `docs/future_ready_architecture.md`, update the Code_Aster section with:

```markdown
Code_Aster exports now include `study_tuba_fem.json`, a Tuba-owned sidecar that records solver name mapping and native lineage. This sidecar is the bridge between Code_Aster solver names and stable `EntityRef` values. It is required for robust result projection when solver group names must be shortened or when generated analysis mesh entities do not exist in the native model.
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_ifc_mapping `
  tests.test_ifc_pipe_systems `
  tests.test_ifc `
  tests.test_code_aster_sidecar `
  tests.test_code_aster_study `
  tests.test_code_aster_artifact_import `
  tests.test_rmed_artifacts `
  tests.test_adapy_bridge -v
```

Expected:

```text
OK
```

- [ ] **Step 4: Run full Python tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Run representative examples**

Run:

```powershell
.\.venv\Scripts\python.exe examples\code_aster_artifact_review.py
.\.venv\Scripts\python.exe examples\future_ready_semantic_workflow.py
```

Expected:

```text
No traceback. Output directories contain scene bundles and Code_Aster artifacts.
```

- [ ] **Step 6: Inspect generated IFC manually**

Run a small export script or reuse an existing example to write IFC, then inspect with IfcOpenShell:

```powershell
.\.venv\Scripts\python.exe - <<'PY'
from pathlib import Path
import ifcopenshell
from tuba import Model
from tuba.external.ifc import IfcExporter

model = Model("IfcSmoke")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
n0 = model.add_node((0, 0, 0))
n1 = model.add_node((1, 0, 0))
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="DN100", material="Steel")
path = Path("generated/ifc-smoke.ifc")
path.parent.mkdir(exist_ok=True)
IfcExporter().export_model(model, path)
f = ifcopenshell.open(str(path))
print(len(f.by_type("IfcDistributionSystem")), len(f.by_type("IfcPipeSegment")))
PY
```

Expected:

```text
1 1
```

- [ ] **Step 7: Commit docs and verification updates**

```powershell
git add README.md docs/future_ready_architecture.md examples/code_aster_artifact_review.py examples/future_ready_semantic_workflow.py
git commit -m "docs: document IFC and Code_Aster exchange improvements"
```

---

## Execution Order

Recommended order:

1. Task 1, license and dependency policy.
2. Task 2, shared IFC mapping primitives.
3. Task 3, pipe systems in IFC.
4. Task 4, bend geometry and pipe properties.
5. Task 5, IFC import round-trip.
6. Task 6, Code_Aster sidecars.
7. Task 7, short-name mapping.
8. Task 8, RMED reader.
9. Task 9, optional `adapy` bridge.
10. Task 10, docs and verification.

Tasks 8 and 9 can be deferred if the immediate goal is IFC + Code_Aster study quality. Tasks 1-7 are the highest-value path.

## Review Checklist

- [ ] No `ada-py` dependency in core dependencies.
- [ ] No copied `adapy` source code.
- [ ] IFC export contains one `IfcDistributionSystem` for pipe runs.
- [ ] Pipe segments and fittings have `Axis` and `Body` representations.
- [ ] Pipe OD/WT and bend radius/angle round-trip.
- [ ] Existing stress and operating-state property sets still export.
- [ ] Code_Aster sidecar is listed in `study_manifest.json`.
- [ ] Long solver-visible names are mapped consistently in `.mail`, `.comm`, and sidecar.
- [ ] Missing `h5py` produces an actionable warning, not a hard failure.
- [ ] Full tests pass.
