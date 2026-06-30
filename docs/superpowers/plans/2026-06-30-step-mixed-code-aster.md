# STEP Mixed Code_Aster Studies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Tuba v4 mixed-analysis slice: a STEP-derived solid component with one confirmed port connected to one native Tuba pipe endpoint and exported as a traceable Code_Aster MED study.

**Architecture:** Keep `TubaModel.elements` pipe-native and add imported CAD/analysis records beside it. Use explicit refs, validation, sidecar lineage, and a new mixed-study exporter so export-only artifacts remain diagnostic while displayed engineering results still require a real Code_Aster solve.

**Tech Stack:** Python dataclasses, existing `TubaModel` serialization, `EntityRef`, `AnalysisMesh`, `AnalysisStudy`, Gmsh/OpenCASCADE, MED, Code_Aster `LIRE_MAILLAGE`, `AFFE_MODELE`, `AFFE_CHAR_MECA`, pytest/unittest.

---

## Source Spec

Implement from `docs/superpowers/specs/2026-06-30-step-mixed-code-aster-design.md`.

This plan covers the first vertical slice only:

```text
one imported STEP solid component
  -> one confirmed circular face port
  -> one native pipe endpoint
  -> one Code_Aster mixed MED export
  -> optional real Code_Aster execution
  -> provenance-safe result review
```

Shell extraction, imported 1D centerline extraction, Arlequin, nonlinear contact,
SALOME automation, and UI-based port review are outside this plan.

## File Structure

- Create `tuba/mixed.py`: dataclasses for `CadAsset`, `ImportedComponent`, `AnalysisRegion`, `Port`, `MeshGroup`, `CouplingSpec`, and helpers for dict conversion.
- Modify `tuba/model.py`: add mixed-analysis containers, serialization, and low-level methods such as `add_cad_asset`, `add_analysis_region`, `confirm_port`, and `connect_pipe_to_port`.
- Modify `tuba/refs.py`: add mixed-analysis `EntityRef` kinds and resolution support.
- Modify `tuba/schema.py`: allow mixed-analysis sections in model JSON while keeping old models valid.
- Modify `tuba/validation.py`: validate mixed-analysis refs, confirmed ports, material assignments, and pipe-to-port compatibility.
- Create `tuba/geometry/step_analysis_importer.py`: Gmsh/OpenCASCADE importer that produces reviewable mixed-analysis records and detected port candidates.
- Create `tuba/solver/mixed_study.py`: export the first mixed Code_Aster study, including MED handoff, `.comm`, `.export`, manifest, sidecar, and `AnalysisMesh`.
- Modify `tuba/solver/aster_sidecar.py`: extend sidecar payload support without breaking existing pure-1D sidecars.
- Modify `tuba/solver/aster.py`: add a small public entry point that delegates mixed studies to `tuba.solver.mixed_study` and reuses runtime execution.
- Modify `tuba/visualization/builders.py`: include imported components, ports, and coupling diagnostics in scenes after the solver provenance path exists.
- Create tests:
  - `tests/test_mixed_model.py`
  - `tests/test_step_analysis_importer.py`
  - `tests/test_mixed_code_aster_export.py`
  - `tests/integration/test_mixed_code_aster_runtime.py`

## Global Rules

- Do not revert unrelated dirty worktree changes.
- Keep pure 1D `CodeAsterSolver.export_analysis_study()` behavior unchanged.
- Every result display path must require real Code_Aster artifacts or raise a clear runtime/provenance error.
- Use export-only tests for portable CI and mark real Code_Aster tests as integration tests.
- Commit after each task when tests pass.

---

### Task 1: Mixed Data Records, Refs, And Serialization

**Files:**
- Create: `tuba/mixed.py`
- Modify: `tuba/refs.py`
- Modify: `tuba/model.py`
- Modify: `tuba/schema.py`
- Test: `tests/test_mixed_model.py`

- [ ] **Step 1: Write failing serialization and ref tests**

Create `tests/test_mixed_model.py`:

```python
import unittest

from tuba import Model
from tuba.refs import EntityRef, resolve_entity_ref


class TestMixedModelRecords(unittest.TestCase):
    def test_mixed_records_roundtrip_and_resolve_refs(self):
        model = Model(project_name="MixedRecords")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        asset = model.add_cad_asset(
            id="cad_asset_0",
            source_path="equipment.step",
            source_format="STEP",
            unit_scale_to_m=0.001,
            placement={
                "origin": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
            content_digest="sha256:test",
            importer="gmsh-occ",
        )
        component = model.add_imported_component(
            id="component_pump_body",
            asset="cad_asset:cad_asset_0",
            name="Pump body",
            role="equipment",
            status="reviewed",
        )
        region = model.add_analysis_region(
            id="region_pump_solid",
            owner="component:component_pump_body",
            role="solid_3d",
            code_aster_modelisation="3D",
            material="Steel",
            mesh_group="G_PUMP_SOLID",
            element_order=2,
            status="reviewed",
        )
        port = model.add_port(
            id="port_pump_nozzle_a",
            owner="component:component_pump_body",
            kind="circular_face",
            position=[1.0, 0.0, 0.0],
            axis=[1.0, 0.0, 0.0],
            radius=0.05,
            face_group="G_PORT_FACE",
            edge_group="G_PORT_EDGE",
            status="confirmed",
        )

        data = model.to_dict()
        self.assertEqual(data["cad_assets"]["cad_asset_0"]["source_path"], "equipment.step")
        self.assertEqual(data["imported_components"]["component_pump_body"]["asset"], "cad_asset:cad_asset_0")
        self.assertEqual(data["analysis_regions"]["region_pump_solid"]["mesh_group"], "G_PUMP_SOLID")
        self.assertEqual(data["ports"]["port_pump_nozzle_a"]["status"], "confirmed")

        loaded = Model.from_dict(data)
        self.assertEqual(loaded.cad_assets["cad_asset_0"], asset)
        self.assertEqual(loaded.imported_components["component_pump_body"], component)
        self.assertEqual(loaded.analysis_regions["region_pump_solid"], region)
        self.assertEqual(loaded.ports["port_pump_nozzle_a"], port)
        self.assertIs(resolve_entity_ref(loaded, EntityRef("cad_asset", "cad_asset_0")), loaded.cad_assets["cad_asset_0"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("component", "component_pump_body")), loaded.imported_components["component_pump_body"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("analysis_region", "region_pump_solid")), loaded.analysis_regions["region_pump_solid"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("port", "port_pump_nozzle_a")), loaded.ports["port_pump_nozzle_a"])

    def test_old_model_payload_without_mixed_records_still_loads(self):
        model = Model(project_name="OldShape")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        data = model.to_dict()
        data.pop("cad_assets", None)
        data.pop("imported_components", None)
        data.pop("analysis_regions", None)
        data.pop("ports", None)
        data.pop("mesh_groups", None)
        data.pop("couplings", None)

        loaded = Model.from_dict(data)

        self.assertEqual(loaded.cad_assets, {})
        self.assertEqual(loaded.imported_components, {})
        self.assertEqual(loaded.analysis_regions, {})
        self.assertEqual(loaded.ports, {})
        self.assertEqual(loaded.mesh_groups, {})
        self.assertEqual(loaded.couplings, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest tests\test_mixed_model.py -q
```

Expected: failures mentioning missing `add_cad_asset` or unknown `EntityRef` kind.

- [ ] **Step 3: Add the mixed-analysis dataclasses**

Create `tuba/mixed.py`:

```python
"""Mixed CAD/analysis records for STEP-backed Code_Aster studies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.refs import EntityRef


@dataclass(frozen=True)
class CadAsset:
    id: str
    source_path: str
    source_format: str = "STEP"
    unit_scale_to_m: float = 1.0
    placement: dict[str, Any] = field(default_factory=dict)
    content_digest: str | None = None
    importer: str = "gmsh-occ"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "CadAsset id")
        if not self.source_path:
            raise ValueError("CadAsset source_path must not be empty.")
        if self.unit_scale_to_m <= 0.0:
            raise ValueError("CadAsset unit_scale_to_m must be positive.")
        object.__setattr__(self, "placement", dict(self.placement))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "unit_scale_to_m": self.unit_scale_to_m,
            "placement": dict(self.placement),
            "importer": self.importer,
            "metadata": dict(self.metadata),
        }
        if self.content_digest is not None:
            data["content_digest"] = self.content_digest
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CadAsset":
        return cls(
            id=data["id"],
            source_path=data["source_path"],
            source_format=data.get("source_format", "STEP"),
            unit_scale_to_m=float(data.get("unit_scale_to_m", 1.0)),
            placement=dict(data.get("placement", {})),
            content_digest=data.get("content_digest"),
            importer=data.get("importer", "gmsh-occ"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ImportedComponent:
    id: str
    asset: EntityRef | str | dict[str, str]
    name: str
    role: str = "equipment"
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "ImportedComponent id")
        object.__setattr__(self, "asset", _coerce_ref(self.asset))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset": str(self.asset),
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportedComponent":
        return cls(
            id=data["id"],
            asset=data["asset"],
            name=data.get("name", data["id"]),
            role=data.get("role", "equipment"),
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AnalysisRegion:
    id: str
    owner: EntityRef | str | dict[str, str]
    role: str
    code_aster_modelisation: str
    material: str
    mesh_group: str
    element_order: int = 2
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "AnalysisRegion id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        if self.element_order < 1:
            raise ValueError("AnalysisRegion element_order must be positive.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner": str(self.owner),
            "role": self.role,
            "code_aster_modelisation": self.code_aster_modelisation,
            "material": self.material,
            "mesh_group": self.mesh_group,
            "element_order": self.element_order,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisRegion":
        return cls(
            id=data["id"],
            owner=data["owner"],
            role=data["role"],
            code_aster_modelisation=data["code_aster_modelisation"],
            material=data["material"],
            mesh_group=data["mesh_group"],
            element_order=int(data.get("element_order", 2)),
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class Port:
    id: str
    owner: EntityRef | str | dict[str, str]
    kind: str
    position: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius: float
    face_group: str | None = None
    edge_group: str | None = None
    status: str = "detected"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "Port id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        object.__setattr__(self, "position", _float_tuple(self.position, "Port position"))
        object.__setattr__(self, "axis", _float_tuple(self.axis, "Port axis"))
        if self.radius <= 0.0:
            raise ValueError("Port radius must be positive.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "owner": str(self.owner),
            "kind": self.kind,
            "position": list(self.position),
            "axis": list(self.axis),
            "radius": self.radius,
            "status": self.status,
            "metadata": dict(self.metadata),
        }
        if self.face_group is not None:
            data["face_group"] = self.face_group
        if self.edge_group is not None:
            data["edge_group"] = self.edge_group
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Port":
        return cls(
            id=data["id"],
            owner=data["owner"],
            kind=data["kind"],
            position=tuple(data["position"]),
            axis=tuple(data["axis"]),
            radius=float(data["radius"]),
            face_group=data.get("face_group"),
            edge_group=data.get("edge_group"),
            status=data.get("status", "detected"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MeshGroup:
    id: str
    owner: EntityRef | str | dict[str, str]
    solver_name: str
    dimension: int
    members: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "MeshGroup id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        object.__setattr__(self, "members", tuple(self.members))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner": str(self.owner),
            "solver_name": self.solver_name,
            "dimension": self.dimension,
            "members": list(self.members),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeshGroup":
        return cls(
            id=data["id"],
            owner=data["owner"],
            solver_name=data["solver_name"],
            dimension=int(data["dimension"]),
            members=tuple(data.get("members", ())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class CouplingSpec:
    id: str
    kind: str
    source: EntityRef | str | dict[str, str]
    source_node: EntityRef | str | dict[str, str]
    target: EntityRef | str | dict[str, str]
    code_aster_keyword: str
    code_aster_option: str
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.id, "CouplingSpec id")
        object.__setattr__(self, "source", _coerce_ref(self.source))
        object.__setattr__(self, "source_node", _coerce_ref(self.source_node))
        object.__setattr__(self, "target", _coerce_ref(self.target))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": str(self.source),
            "source_node": str(self.source_node),
            "target": str(self.target),
            "code_aster_keyword": self.code_aster_keyword,
            "code_aster_option": self.code_aster_option,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouplingSpec":
        return cls(
            id=data["id"],
            kind=data["kind"],
            source=data["source"],
            source_node=data["source_node"],
            target=data["target"],
            code_aster_keyword=data["code_aster_keyword"],
            code_aster_option=data["code_aster_option"],
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


def _coerce_ref(value: EntityRef | str | dict[str, str]) -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, str):
        return EntityRef.parse(value)
    if isinstance(value, dict):
        return EntityRef.from_dict(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to EntityRef.")


def _float_tuple(values: object, label: str) -> tuple[float, float, float]:
    data = tuple(float(value) for value in values)  # type: ignore[arg-type]
    if len(data) != 3:
        raise ValueError(f"{label} must contain 3 values.")
    return data  # type: ignore[return-value]


def _require_id(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")
```

- [ ] **Step 4: Extend refs, model containers, and serialization**

Modify `tuba/refs.py`:

```python
ENTITY_REF_KINDS = frozenset(
    {
        "node",
        "element",
        "support",
        "obstacle",
        "group",
        "assembly",
        "route",
        "material",
        "section",
        "load_case",
        "placement_frame",
        "cad_asset",
        "component",
        "analysis_region",
        "port",
        "mesh_group",
        "coupling",
    }
)
```

Add resolution branches before the final `raise KeyError(str(ref))`:

```python
    if ref.kind == "cad_asset":
        return _lookup_mapping(getattr(model, "cad_assets", {}), ref)
    if ref.kind == "component":
        return _lookup_mapping(getattr(model, "imported_components", {}), ref)
    if ref.kind == "analysis_region":
        return _lookup_mapping(getattr(model, "analysis_regions", {}), ref)
    if ref.kind == "port":
        return _lookup_mapping(getattr(model, "ports", {}), ref)
    if ref.kind == "mesh_group":
        return _lookup_mapping(getattr(model, "mesh_groups", {}), ref)
    if ref.kind == "coupling":
        return _lookup_mapping(getattr(model, "couplings", {}), ref)
```

Modify `tuba/model.py` imports:

```python
from tuba.mixed import AnalysisRegion, CadAsset, CouplingSpec, ImportedComponent, MeshGroup, Port
```

Add containers in `TubaModel.__init__`:

```python
        self.cad_assets: Dict[str, CadAsset] = {}
        self.imported_components: Dict[str, ImportedComponent] = {}
        self.analysis_regions: Dict[str, AnalysisRegion] = {}
        self.ports: Dict[str, Port] = {}
        self.mesh_groups: Dict[str, MeshGroup] = {}
        self.couplings: Dict[str, CouplingSpec] = {}
```

Add low-level methods near the obstacle/group methods:

```python
    def add_cad_asset(self, **kwargs) -> CadAsset:
        asset = CadAsset(**kwargs)
        self.cad_assets[asset.id] = asset
        return asset

    def add_imported_component(self, **kwargs) -> ImportedComponent:
        component = ImportedComponent(**kwargs)
        self.imported_components[component.id] = component
        return component

    def add_analysis_region(self, **kwargs) -> AnalysisRegion:
        region = AnalysisRegion(**kwargs)
        self.analysis_regions[region.id] = region
        return region

    def add_port(self, **kwargs) -> Port:
        port = Port(**kwargs)
        self.ports[port.id] = port
        return port

    def add_mesh_group(self, **kwargs) -> MeshGroup:
        mesh_group = MeshGroup(**kwargs)
        self.mesh_groups[mesh_group.id] = mesh_group
        return mesh_group

    def add_coupling(self, **kwargs) -> CouplingSpec:
        coupling = CouplingSpec(**kwargs)
        self.couplings[coupling.id] = coupling
        return coupling
```

Add these keys to `to_dict()`:

```python
            "cad_assets": {key: value.to_dict() for key, value in self.cad_assets.items()},
            "imported_components": {
                key: value.to_dict()
                for key, value in self.imported_components.items()
            },
            "analysis_regions": {
                key: value.to_dict()
                for key, value in self.analysis_regions.items()
            },
            "ports": {key: value.to_dict() for key, value in self.ports.items()},
            "mesh_groups": {
                key: value.to_dict()
                for key, value in self.mesh_groups.items()
            },
            "couplings": {
                key: value.to_dict()
                for key, value in self.couplings.items()
            },
```

Add these loads in `from_dict()` after attributes:

```python
        model.cad_assets = {
            key: CadAsset.from_dict(value)
            for key, value in data.get("cad_assets", {}).items()
        }
        model.imported_components = {
            key: ImportedComponent.from_dict(value)
            for key, value in data.get("imported_components", {}).items()
        }
        model.analysis_regions = {
            key: AnalysisRegion.from_dict(value)
            for key, value in data.get("analysis_regions", {}).items()
        }
        model.ports = {
            key: Port.from_dict(value)
            for key, value in data.get("ports", {}).items()
        }
        model.mesh_groups = {
            key: MeshGroup.from_dict(value)
            for key, value in data.get("mesh_groups", {}).items()
        }
        model.couplings = {
            key: CouplingSpec.from_dict(value)
            for key, value in data.get("couplings", {}).items()
        }
```

Modify `tuba/schema.py` by adding permissive top-level object properties:

```python
        "cad_assets": {"type": "object", "additionalProperties": {"type": "object"}},
        "imported_components": {"type": "object", "additionalProperties": {"type": "object"}},
        "analysis_regions": {"type": "object", "additionalProperties": {"type": "object"}},
        "ports": {"type": "object", "additionalProperties": {"type": "object"}},
        "mesh_groups": {"type": "object", "additionalProperties": {"type": "object"}},
        "couplings": {"type": "object", "additionalProperties": {"type": "object"}},
```

- [ ] **Step 5: Run the task tests**

Run:

```powershell
python -m pytest tests\test_mixed_model.py -q
python -m pytest tests\test_tuba_core.py::TestModelAndBuilder::test_builder_and_json -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add tuba\mixed.py tuba\refs.py tuba\model.py tuba\schema.py tests\test_mixed_model.py
git commit -m "feat: add mixed analysis model records"
```

---

### Task 2: Pipe-To-Port Coupling API And Validation

**Files:**
- Modify: `tuba/model.py`
- Modify: `tuba/validation.py`
- Test: `tests/test_mixed_model.py`

- [ ] **Step 1: Add failing coupling tests**

Append to `tests/test_mixed_model.py`:

```python
from tuba.validation import ModelValidationError


class TestMixedCouplingValidation(unittest.TestCase):
    def _model_with_pipe_and_port(self):
        model = Model(project_name="CouplingValidation")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        model.add_cad_asset(
            id="cad_asset_0",
            source_path="equipment.step",
            content_digest="sha256:test",
        )
        model.add_imported_component(
            id="component_pump_body",
            asset="cad_asset:cad_asset_0",
            name="Pump body",
            role="equipment",
        )
        model.add_analysis_region(
            id="region_pump_solid",
            owner="component:component_pump_body",
            role="solid_3d",
            code_aster_modelisation="3D",
            material="Steel",
            mesh_group="G_PUMP_SOLID",
            element_order=2,
        )
        model.add_port(
            id="port_pump_nozzle_a",
            owner="component:component_pump_body",
            kind="circular_face",
            position=[1.0, 0.0, 0.0],
            axis=[1.0, 0.0, 0.0],
            radius=0.05,
            face_group="G_PORT_FACE",
            edge_group="G_PORT_EDGE",
            status="confirmed",
        )
        return model

    def test_connect_pipe_to_confirmed_solid_port(self):
        model = self._model_with_pipe_and_port()

        coupling = model.connect_pipe_to_port(
            pipe="element:pipe_0",
            node="node:N1",
            port="port:port_pump_nozzle_a",
            method="3D_TUYAU",
            id="coupling_pipe_to_pump_a",
        )

        self.assertEqual(coupling.code_aster_keyword, "LIAISON_ELEM")
        self.assertEqual(coupling.code_aster_option, "3D_TUYAU")
        self.assertEqual(str(coupling.source), "element:pipe_0")
        self.assertEqual(str(coupling.source_node), "node:N1")
        self.assertEqual(str(coupling.target), "port:port_pump_nozzle_a")
        model.validate()

    def test_unconfirmed_port_blocks_validation(self):
        model = self._model_with_pipe_and_port()
        unconfirmed = model.ports["port_pump_nozzle_a"].to_dict()
        unconfirmed["status"] = "detected"
        model.add_port(**unconfirmed)
        model.connect_pipe_to_port(
            pipe="element:pipe_0",
            node="node:N1",
            port="port:port_pump_nozzle_a",
            method="3D_TUYAU",
            id="coupling_pipe_to_pump_a",
        )

        with self.assertRaisesRegex(ModelValidationError, "is not confirmed"):
            model.validate()

    def test_pipe_radius_mismatch_blocks_connection(self):
        model = self._model_with_pipe_and_port()
        changed = model.ports["port_pump_nozzle_a"].to_dict()
        changed["radius"] = 0.08
        model.add_port(**changed)

        with self.assertRaisesRegex(ValueError, "diameter"):
            model.connect_pipe_to_port(
                pipe="element:pipe_0",
                node="node:N1",
                port="port:port_pump_nozzle_a",
                method="3D_TUYAU",
                id="coupling_pipe_to_pump_a",
            )
```

- [ ] **Step 2: Run failing coupling tests**

Run:

```powershell
python -m pytest tests\test_mixed_model.py::TestMixedCouplingValidation -q
```

Expected: failures for missing `connect_pipe_to_port`.

- [ ] **Step 3: Implement `connect_pipe_to_port`**

Modify `tuba/model.py` imports:

```python
from tuba.refs import EntityRef
```

Add helper methods to `TubaModel`:

```python
    def connect_pipe_to_port(
        self,
        *,
        pipe: str | EntityRef,
        node: str | EntityRef,
        port: str | EntityRef,
        method: str = "3D_TUYAU",
        id: str | None = None,
    ) -> CouplingSpec:
        pipe_ref = pipe if isinstance(pipe, EntityRef) else EntityRef.parse(pipe)
        node_ref = node if isinstance(node, EntityRef) else EntityRef.parse(node)
        port_ref = port if isinstance(port, EntityRef) else EntityRef.parse(port)
        if pipe_ref.kind != "element":
            raise ValueError("pipe must be an element ref.")
        if node_ref.kind != "node":
            raise ValueError("node must be a node ref.")
        if port_ref.kind != "port":
            raise ValueError("port must be a port ref.")
        if method not in {"3D_TUYAU", "3D_POU", "COQ_TUYAU", "COQ_POU"}:
            raise ValueError(f"Unsupported pipe-to-port coupling method {method!r}.")

        element = self.get_element(pipe_ref.id)
        if element is None:
            raise ValueError(f"Element {pipe_ref.id!r} does not exist.")
        if element.type not in {"pipe_straight", "pipe_bend", "beam"}:
            raise ValueError(f"Element {element.id!r} is not a pipe or beam.")
        if node_ref.id not in {element.n1, element.n2}:
            raise ValueError(f"Node {node_ref.id!r} is not an endpoint of element {element.id!r}.")
        target_port = self.ports.get(port_ref.id)
        if target_port is None:
            raise ValueError(f"Port {port_ref.id!r} does not exist.")
        if target_port.status != "confirmed":
            raise ValueError(f"Port {target_port.id!r} is not confirmed.")
        if not target_port.face_group:
            raise ValueError(f"Port {target_port.id!r} has no face_group.")

        section = self.sections[element.section]
        pipe_radius = getattr(section, "OD", 0.0) / 2.0
        tolerance = max(0.001, pipe_radius * 0.02)
        if abs(pipe_radius - target_port.radius) > tolerance:
            raise ValueError(
                f"Pipe/port diameter mismatch for {element.id!r} and {target_port.id!r}."
            )

        coupling_id = id or f"coupling_{len(self.couplings)}"
        keyword = "LIAISON_ELEM"
        coupling = CouplingSpec(
            id=coupling_id,
            kind="pipe_to_solid_port",
            source=pipe_ref,
            source_node=node_ref,
            target=port_ref,
            code_aster_keyword=keyword,
            code_aster_option=method,
        )
        self.couplings[coupling.id] = coupling
        return coupling
```

- [ ] **Step 4: Implement mixed validation**

Modify `tuba/validation.py` by adding calls in `validate_model` after existing attribute validation:

```python
    _validate_mixed_records(model, errors)
```

Add helper functions:

```python
def _validate_mixed_records(model: TubaModel, errors: list[str]) -> None:
    for asset_id, asset in getattr(model, "cad_assets", {}).items():
        if asset_id != asset.id:
            errors.append(f"CAD asset key {asset_id!r} does not match id {asset.id!r}.")
        if asset.unit_scale_to_m <= 0.0:
            errors.append(f"CAD asset {asset_id!r} unit_scale_to_m must be positive.")

    for component_id, component in getattr(model, "imported_components", {}).items():
        if component_id != component.id:
            errors.append(f"Imported component key {component_id!r} does not match id {component.id!r}.")
        if component.asset.id not in getattr(model, "cad_assets", {}):
            errors.append(f"Imported component {component_id!r} references missing asset {component.asset}.")

    for region_id, region in getattr(model, "analysis_regions", {}).items():
        if region_id != region.id:
            errors.append(f"Analysis region key {region_id!r} does not match id {region.id!r}.")
        if region.owner.id not in getattr(model, "imported_components", {}):
            errors.append(f"Analysis region {region_id!r} references missing owner {region.owner}.")
        if region.material not in model.materials:
            errors.append(f"Analysis region {region_id!r} references missing material {region.material!r}.")
        if region.role == "solid_3d" and region.code_aster_modelisation != "3D":
            errors.append(f"Analysis region {region_id!r} solid_3d must use Code_Aster modelisation '3D'.")

    for port_id, port in getattr(model, "ports", {}).items():
        if port_id != port.id:
            errors.append(f"Port key {port_id!r} does not match id {port.id!r}.")
        if port.owner.id not in getattr(model, "imported_components", {}):
            errors.append(f"Port {port_id!r} references missing owner {port.owner}.")
        if port.status == "confirmed" and not port.face_group:
            errors.append(f"Confirmed port {port_id!r} has no face_group.")

    for coupling_id, coupling in getattr(model, "couplings", {}).items():
        if coupling_id != coupling.id:
            errors.append(f"Coupling key {coupling_id!r} does not match id {coupling.id!r}.")
        if coupling.source.kind != "element" or model.get_element(coupling.source.id) is None:
            errors.append(f"Coupling {coupling_id!r} references missing source {coupling.source}.")
        if coupling.source_node.kind != "node" or coupling.source_node.id not in model.nodes:
            errors.append(f"Coupling {coupling_id!r} references missing source node {coupling.source_node}.")
        port = getattr(model, "ports", {}).get(coupling.target.id)
        if coupling.target.kind != "port" or port is None:
            errors.append(f"Coupling {coupling_id!r} references missing target {coupling.target}.")
            continue
        if port.status != "confirmed":
            errors.append(f"Coupling {coupling_id!r} target port {port.id!r} is not confirmed.")
        if coupling.code_aster_keyword == "LIAISON_ELEM" and coupling.code_aster_option == "3D_TUYAU":
            _validate_pipe_to_solid_port(model, coupling_id, coupling, port, errors)


def _validate_pipe_to_solid_port(model: TubaModel, coupling_id: str, coupling, port, errors: list[str]) -> None:
    element = model.get_element(coupling.source.id)
    if element is None:
        return
    if element.type not in {"pipe_straight", "pipe_bend"}:
        errors.append(f"Coupling {coupling_id!r} option '3D_TUYAU' requires a pipe element.")
    if coupling.source_node.id not in {element.n1, element.n2}:
        errors.append(f"Coupling {coupling_id!r} source node is not an endpoint of {element.id!r}.")
    if not _component_has_solid_region(model, port.owner.id):
        errors.append(f"Coupling {coupling_id!r} target port owner has no solid_3d analysis region.")


def _component_has_solid_region(model: TubaModel, component_id: str) -> bool:
    for region in getattr(model, "analysis_regions", {}).values():
        if region.owner.kind == "component" and region.owner.id == component_id and region.role == "solid_3d":
            return True
    return False
```

- [ ] **Step 5: Run validation tests**

Run:

```powershell
python -m pytest tests\test_mixed_model.py -q
```

Expected: all tests in `tests/test_mixed_model.py` pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add tuba\model.py tuba\validation.py tests\test_mixed_model.py
git commit -m "feat: validate mixed pipe-to-port couplings"
```

---

### Task 3: STEP Analysis Importer With Reviewable Port Candidates

**Files:**
- Create: `tuba/geometry/step_analysis_importer.py`
- Test: `tests/test_step_analysis_importer.py`

- [ ] **Step 1: Write failing importer tests**

Create `tests/test_step_analysis_importer.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tuba import Model
from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError


class TestStepAnalysisImporter(unittest.TestCase):
    def test_missing_step_file_raises_clear_error(self):
        model = Model(project_name="MissingStep")
        importer = StepAnalysisImporter()

        with self.assertRaisesRegex(FileNotFoundError, "missing.step"):
            importer.import_component(model, "missing.step", id="component_missing")

    def test_missing_gmsh_raises_optional_dependency_error(self):
        model = Model(project_name="NoGmsh")
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "part.step"
            step_path.write_text("ISO-10303-21; ENDSEC; END-ISO-10303-21;", encoding="utf-8")
            importer = StepAnalysisImporter()
            with patch("tuba.geometry.step_analysis_importer.gmsh", None):
                with self.assertRaisesRegex(StepImportError, "gmsh is required"):
                    importer.import_component(model, step_path, id="component_part")

    def test_manual_candidate_can_be_recorded_without_solver_activation(self):
        model = Model(project_name="ManualCandidate")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        importer = StepAnalysisImporter()
        component = importer.record_component_from_metadata(
            model,
            source_path="part.step",
            component_id="component_part",
            asset_id="cad_asset_0",
            ports=[
                {
                    "id": "port_candidate_0",
                    "kind": "circular_face",
                    "position": [0.0, 0.0, 0.0],
                    "axis": [1.0, 0.0, 0.0],
                    "radius": 0.05,
                    "face_group": "G_FACE_0",
                }
            ],
        )

        self.assertEqual(component.id, "component_part")
        self.assertEqual(model.ports["port_candidate_0"].status, "detected")
        self.assertEqual(model.ports["port_candidate_0"].face_group, "G_FACE_0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing importer tests**

Run:

```powershell
python -m pytest tests\test_step_analysis_importer.py -q
```

Expected: import failure for missing `tuba.geometry.step_analysis_importer`.

- [ ] **Step 3: Implement the importer scaffold and metadata recording**

Create `tuba/geometry/step_analysis_importer.py`:

```python
"""STEP import helpers for reviewable mixed Code_Aster studies."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

try:
    import gmsh
except ImportError:  # pragma: no cover - covered by explicit None patch in tests
    gmsh = None

from tuba.model import TubaModel
from tuba.mixed import ImportedComponent


class StepImportError(RuntimeError):
    """Raised when a STEP file cannot be imported for analysis review."""


class StepAnalysisImporter:
    def import_component(
        self,
        model: TubaModel,
        file_path: str | Path,
        *,
        id: str,
        asset_id: str = "cad_asset_0",
        role: str = "equipment",
        unit_scale_to_m: float = 1.0,
    ) -> ImportedComponent:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"STEP file not found: {path}")
        if gmsh is None:
            raise StepImportError("gmsh is required to import STEP files for mixed analysis.")
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        gmsh.initialize()
        try:
            gmsh.model.add(id)
            imported = gmsh.model.occ.importShapes(str(path))
            gmsh.model.occ.synchronize()
            component = self.record_component_from_metadata(
                model,
                source_path=str(path),
                component_id=id,
                asset_id=asset_id,
                role=role,
                unit_scale_to_m=unit_scale_to_m,
                content_digest=digest,
                ports=self._detect_port_candidates(imported),
            )
        finally:
            gmsh.finalize()
        return component

    def record_component_from_metadata(
        self,
        model: TubaModel,
        *,
        source_path: str,
        component_id: str,
        asset_id: str,
        role: str = "equipment",
        unit_scale_to_m: float = 1.0,
        content_digest: str | None = None,
        ports: list[dict[str, Any]] | None = None,
    ) -> ImportedComponent:
        model.add_cad_asset(
            id=asset_id,
            source_path=source_path,
            source_format="STEP",
            unit_scale_to_m=unit_scale_to_m,
            placement={"origin": [0.0, 0.0, 0.0], "rotation": [1.0, 0.0, 0.0, 0.0]},
            content_digest=content_digest,
            importer="gmsh-occ",
        )
        component = model.add_imported_component(
            id=component_id,
            asset=f"cad_asset:{asset_id}",
            name=component_id,
            role=role,
            status="review",
        )
        for port in ports or []:
            model.add_port(
                id=port["id"],
                owner=f"component:{component_id}",
                kind=port.get("kind", "circular_face"),
                position=port["position"],
                axis=port["axis"],
                radius=port["radius"],
                face_group=port.get("face_group"),
                edge_group=port.get("edge_group"),
                status=port.get("status", "detected"),
                metadata=dict(port.get("metadata", {})),
            )
        return component

    def _detect_port_candidates(self, imported: list[tuple[int, int]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if gmsh is None:
            return candidates
        index = 0
        for dim, tag in imported:
            if dim != 3:
                continue
            boundary = gmsh.model.getBoundary([(dim, tag)], oriented=False, recursive=False)
            for face_dim, face_tag in boundary:
                if face_dim != 2:
                    continue
                bbox = gmsh.model.getBoundingBox(face_dim, face_tag)
                dx = bbox[3] - bbox[0]
                dy = bbox[4] - bbox[1]
                dz = bbox[5] - bbox[2]
                radius = max(dx, dy, dz) / 2.0
                if radius <= 0.0:
                    continue
                candidates.append(
                    {
                        "id": f"port_candidate_{index}",
                        "kind": "circular_face",
                        "position": [
                            (bbox[0] + bbox[3]) / 2.0,
                            (bbox[1] + bbox[4]) / 2.0,
                            (bbox[2] + bbox[5]) / 2.0,
                        ],
                        "axis": [1.0, 0.0, 0.0],
                        "radius": radius,
                        "face_group": f"G_PORT_CANDIDATE_{index}",
                        "metadata": {"gmsh_face_tag": face_tag},
                    }
                )
                index += 1
        return candidates
```

- [ ] **Step 4: Run importer tests**

Run:

```powershell
python -m pytest tests\test_step_analysis_importer.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add tuba\geometry\step_analysis_importer.py tests\test_step_analysis_importer.py
git commit -m "feat: add reviewable STEP analysis importer"
```

---

### Task 4: Mixed Study Command And Sidecar Export

**Files:**
- Create: `tuba/solver/mixed_study.py`
- Modify: `tuba/solver/aster_sidecar.py`
- Test: `tests/test_mixed_code_aster_export.py`

- [ ] **Step 1: Write failing export-only tests**

Create `tests/test_mixed_code_aster_export.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.solver.mixed_study import MixedCodeAsterStudyExporter


def build_mixed_fixture() -> Model:
    model = Model(project_name="MixedExport")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
    model.add_cad_asset(id="cad_asset_0", source_path="equipment.step", content_digest="sha256:test")
    model.add_imported_component(id="component_pump_body", asset="cad_asset:cad_asset_0", name="Pump body")
    model.add_analysis_region(
        id="region_pump_solid",
        owner="component:component_pump_body",
        role="solid_3d",
        code_aster_modelisation="3D",
        material="Steel",
        mesh_group="G_PUMP_SOLID",
        element_order=2,
    )
    model.add_port(
        id="port_pump_nozzle_a",
        owner="component:component_pump_body",
        kind="circular_face",
        position=[1.0, 0.0, 0.0],
        axis=[1.0, 0.0, 0.0],
        radius=0.05,
        face_group="G_PORT_FACE",
        edge_group="G_PORT_EDGE",
        status="confirmed",
    )
    model.connect_pipe_to_port(
        pipe="element:pipe_0",
        node="node:N1",
        port="port:port_pump_nozzle_a",
        method="3D_TUYAU",
        id="coupling_pipe_to_pump_a",
    )
    return model


class TestMixedCodeAsterExport(unittest.TestCase):
    def test_export_writes_med_comm_manifest_and_sidecar(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            manifest = json.loads((root / "study_manifest.json").read_text(encoding="utf-8"))
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        loaded_study = AnalysisStudy.from_dict(manifest["study"])
        mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
        self.assertEqual(loaded_study.id, study.id)
        self.assertIn("FORMAT='MED'", comm)
        self.assertIn("MODELISATION='TUYAU_3M'", comm)
        self.assertIn("MODELISATION='3D'", comm)
        self.assertIn("OPTION='3D_TUYAU'", comm)
        self.assertIn("G_PORT_FACE", comm)
        self.assertIn("N1", mesh.nodes)
        self.assertEqual(str(mesh.node_sources["N1"].source_ref), "node:N1")
        self.assertEqual(sidecar["lineage"]["G_PUMP_SOLID"], "analysis_region:region_pump_solid")
        self.assertEqual(sidecar["lineage"]["G_PORT_FACE"], "port:port_pump_nozzle_a")
        self.assertEqual(sidecar["mixed_analysis"]["couplings"]["coupling_pipe_to_pump_a"]["target"], "port:port_pump_nozzle_a")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing export test**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py -q
```

Expected: import failure for missing `tuba.solver.mixed_study`.

- [ ] **Step 3: Extend sidecar writer with optional mixed payload**

Modify `tuba/solver/aster_sidecar.py`:

```python
def dump_solver_sidecar(
    path: str | Path,
    *,
    solver_name: str,
    load_case: str,
    analysis_mesh_id: str,
    name_map: dict[str, str],
    lineage: dict[str, str],
    mixed_analysis: dict | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "solver_name": solver_name,
        "load_case": load_case,
        "analysis_mesh_id": analysis_mesh_id,
        "name_map": dict(sorted(name_map.items())),
        "lineage": dict(sorted(lineage.items())),
    }
    if mixed_analysis is not None:
        payload["mixed_analysis"] = mixed_analysis
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
```

Existing callers keep working because the new argument defaults to `None`.

- [ ] **Step 4: Implement mixed export scaffold**

Create `tuba/solver/mixed_study.py`:

```python
"""Mixed MED-backed Code_Aster study export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar


class MixedCodeAsterStudyExporter:
    SOLVER_NAME = "Code_Aster"

    def export_analysis_study(self, model: TubaModel, load_case_name: str, output_dir: str | Path) -> AnalysisStudy:
        if load_case_name not in model.load_cases:
            raise ValueError(f"Load case {load_case_name!r} not found.")
        model.validate()
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        med_path = root / "study.med"
        comm_path = root / "study.comm"
        export_path = root / "study.export"
        manifest_path = root / "study_manifest.json"
        sidecar_path = root / "study_tuba_fem.json"
        self._write_med(model, med_path)
        analysis_mesh = self._build_analysis_mesh(model, med_path)
        self._write_comm(model, load_case_name, comm_path)
        self._write_export(root, export_path)
        solver_names = list(analysis_mesh.groups.keys())
        name_map = build_solver_name_map(solver_names)
        lineage = self._build_lineage(model)
        dump_solver_sidecar(
            sidecar_path,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            analysis_mesh_id=analysis_mesh.id,
            name_map=name_map,
            lineage=lineage,
            mixed_analysis=self._mixed_payload(model),
        )
        study = AnalysisStudy(
            id=f"mixed_analysis_study:{load_case_name}",
            model_revision=int(getattr(model, "revision", 0)),
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            work_dir=str(root),
            input_files={
                "med": str(med_path),
                "comm": str(comm_path),
                "export": str(export_path),
                "manifest": str(manifest_path),
                "sidecar": str(sidecar_path),
            },
            mesh_id=analysis_mesh.id,
            metadata={"project_name": model.project_name, "mixed_analysis": True},
        )
        manifest = {"study": study.to_dict(), "analysis_mesh": analysis_mesh.to_dict()}
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return study

    def _write_med(self, model: TubaModel, path: Path) -> None:
        try:
            import meshio
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("meshio and numpy are required to write mixed MED studies.") from exc

        point_ids = list(model.nodes.keys())
        points = np.array([model.nodes[node_id].coords for node_id in point_ids], dtype=float)
        point_index = {node_id: index for index, node_id in enumerate(point_ids)}
        line_cells = [
            [point_index[element.n1], point_index[element.n2]]
            for element in model.elements
            if element.type in {"pipe_straight", "pipe_bend", "beam"}
        ]
        cells = []
        cell_sets: dict[str, list[list[int]]] = {}
        if line_cells:
            cells.append(("line", np.array(line_cells, dtype=int)))
            cell_sets["G_TUBE"] = [list(range(len(line_cells)))]
        for region in model.analysis_regions.values():
            cell_sets[region.mesh_group] = [[] for _ in cells]
        for port in model.ports.values():
            if port.face_group:
                cell_sets[port.face_group] = [[] for _ in cells]
        mesh = meshio.Mesh(points=points, cells=cells, cell_sets=cell_sets)
        try:
            meshio.write(path, mesh, file_format="med")
        except Exception as exc:
            raise RuntimeError(f"Failed to write MED mesh {path}: {exc}") from exc
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"MED writer produced an empty file: {path}")

    def _build_analysis_mesh(self, model: TubaModel, med_path: Path) -> AnalysisMesh:
        nodes = {node_id: tuple(float(value) for value in node.coords) for node_id, node in model.nodes.items()}
        elements = {element.id: (element.n1, element.n2) for element in model.elements}
        groups: dict[str, tuple[str, ...]] = {"G_TUBE": tuple(elements.keys())}
        node_sources = {
            node_id: MeshNodeSource(node_id=node_id, source_ref=EntityRef("node", node_id), role="native_node")
            for node_id in nodes
        }
        element_sources = {
            element_id: MeshElementSource(
                element_id=element_id,
                source_ref=EntityRef("element", element_id),
                role="native_element",
            )
            for element_id in elements
        }
        for region in model.analysis_regions.values():
            groups[region.mesh_group] = tuple()
        for port in model.ports.values():
            if port.face_group:
                groups[port.face_group] = tuple()
        return AnalysisMesh(
            id="analysis_mesh:mixed",
            model_revision=int(getattr(model, "revision", 0)),
            solver_name=self.SOLVER_NAME,
            nodes=nodes,
            elements=elements,
            groups=groups,
            node_sources=node_sources,
            element_sources=element_sources,
            files={"med": str(med_path)},
        )

    def _write_comm(self, model: TubaModel, load_case_name: str, path: Path) -> None:
        load_case = model.load_cases[load_case_name]
        lines = [
            "DEBUT()",
            "MAIL0 = LIRE_MAILLAGE(FORMAT='MED', UNITE=20)",
            "MODELE = AFFE_MODELE(",
            "    MAILLAGE=MAIL0,",
            "    AFFE=(",
            "        _F(GROUP_MA=('G_TUBE',), PHENOMENE='MECANIQUE', MODELISATION='TUYAU_3M'),",
        ]
        for region in model.analysis_regions.values():
            lines.append(
                f"        _F(GROUP_MA=('{region.mesh_group}',), PHENOMENE='MECANIQUE', MODELISATION='{region.code_aster_modelisation}'),"
            )
        lines.extend(["    ),", ")"])
        lines.extend(
            [
                "CHAR = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
                "    LIAISON_ELEM=(",
            ]
        )
        for coupling in model.couplings.values():
            port = model.ports[coupling.target.id]
            lines.extend(
                [
                    "        _F(",
                    f"            OPTION='{coupling.code_aster_option}',",
                    f"            GROUP_MA_1='{port.face_group}',",
                    f"            GROUP_NO_2='{coupling.source_node.id}',",
                    "        ),",
                ]
            )
        lines.extend(["    ),", ")", "FIN()"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_export(self, root: Path, path: Path) -> None:
        path.write_text(
            "\n".join(
                [
                    "P actions make_etude",
                    "P memjob 1024",
                    "P time_limit 60",
                    f"F comm {root / 'study.comm'} D 1",
                    f"F mmed {root / 'study.med'} D 20",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _build_lineage(self, model: TubaModel) -> dict[str, str]:
        lineage = {"G_TUBE": "group:G_TUBE"}
        for region in model.analysis_regions.values():
            lineage[region.mesh_group] = f"analysis_region:{region.id}"
        for port in model.ports.values():
            if port.face_group:
                lineage[port.face_group] = f"port:{port.id}"
        return lineage

    def _mixed_payload(self, model: TubaModel) -> dict[str, Any]:
        return {
            "cad_assets": {key: value.to_dict() for key, value in model.cad_assets.items()},
            "components": {key: value.to_dict() for key, value in model.imported_components.items()},
            "analysis_regions": {key: value.to_dict() for key, value in model.analysis_regions.items()},
            "ports": {key: value.to_dict() for key, value in model.ports.items()},
            "couplings": {key: value.to_dict() for key, value in model.couplings.items()},
        }
```

This task writes a real nonempty MED file through `meshio` or fails before
emitting a completed study manifest. The first writer only includes native 1D
cells and named empty imported groups; follow-up tasks can populate imported 3D
cells from Gmsh topology, but the exported handoff file is never an empty stand-in.

- [ ] **Step 5: Run export-only tests**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py -q
python -m pytest tests\test_code_aster_study.py::TestCodeAsterStudyManifest::test_export_analysis_study_writes_manifest_with_mesh_provenance -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add tuba\solver\mixed_study.py tuba\solver\aster_sidecar.py tests\test_mixed_code_aster_export.py
git commit -m "feat: export mixed Code_Aster study contract"
```

---

### Task 5: MED Writer Failure Gate

**Files:**
- Modify: `tuba/solver/mixed_study.py`
- Test: `tests/test_mixed_code_aster_export.py`

- [ ] **Step 1: Add MED failure propagation test**

Append to `TestMixedCodeAsterExport`:

```python
    def test_med_file_is_nonempty_for_mixed_export(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            med_path = Path(study.input_files["med"])

        self.assertGreater(med_path.stat().st_size, 0)

    def test_med_writer_failure_blocks_manifest(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MixedCodeAsterStudyExporter()
            exporter._write_med_with_meshio = lambda model, path: (_ for _ in ()).throw(RuntimeError("MED writer failed"))
            with self.assertRaisesRegex(RuntimeError, "MED writer failed"):
                exporter.export_analysis_study(model, "Hot", tmpdir)
            self.assertFalse((Path(tmpdir) / "study_manifest.json").exists())
```

- [ ] **Step 2: Run MED gate tests**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_med_file_is_nonempty_for_mixed_export -q
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_med_writer_failure_blocks_manifest -q
```

Expected: first test passes when local MED support is available or is skipped
with the explicit MED support reason added below. The second test fails until
`_write_med` delegates through `_write_med_with_meshio`.

- [ ] **Step 3: Add a patchable writer seam**

Modify `tuba/solver/mixed_study.py`:

```python
    def _write_med(self, model: TubaModel, path: Path) -> None:
        self._write_med_with_meshio(model, path)

    def _write_med_with_meshio(self, model: TubaModel, path: Path) -> None:
        try:
            import meshio
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("meshio and numpy are required to write mixed MED studies.") from exc

        point_ids = list(model.nodes.keys())
        points = np.array([model.nodes[node_id].coords for node_id in point_ids], dtype=float)
        point_index = {node_id: index for index, node_id in enumerate(point_ids)}
        line_cells = [
            [point_index[element.n1], point_index[element.n2]]
            for element in model.elements
            if element.type in {"pipe_straight", "pipe_bend", "beam"}
        ]
        cells = []
        cell_sets: dict[str, list[list[int]]] = {}
        if line_cells:
            cells.append(("line", np.array(line_cells, dtype=int)))
            cell_sets["G_TUBE"] = [list(range(len(line_cells)))]
        for region in model.analysis_regions.values():
            cell_sets[region.mesh_group] = [[] for _ in cells]
        for port in model.ports.values():
            if port.face_group:
                cell_sets[port.face_group] = [[] for _ in cells]
        mesh = meshio.Mesh(points=points, cells=cells, cell_sets=cell_sets)
        try:
            meshio.write(path, mesh, file_format="med")
        except Exception as exc:
            raise RuntimeError(f"Failed to write MED mesh {path}: {exc}") from exc
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"MED writer produced an empty file: {path}")
```

No test update is needed after this step. The failing test from Step 1 now
patches the method that `_write_med` actually calls.

- [ ] **Step 4: Run MED writer tests**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py -q
```

Expected: all mixed export tests pass when meshio MED support is available. If
the local environment lacks MED support, capture the exact `RuntimeError` and
mark only `test_med_file_is_nonempty_for_mixed_export` with:

```python
try:
    study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
except RuntimeError as exc:
    if "MED" not in str(exc) and "meshio" not in str(exc):
        raise
    self.skipTest(str(exc))
```

- [ ] **Step 5: Commit Task 5**

```powershell
git add tuba\solver\mixed_study.py tests\test_mixed_code_aster_export.py
git commit -m "feat: require real MED output for mixed studies"
```

---

### Task 6: Gmsh STEP Volume MED Population

**Files:**
- Modify: `tuba/solver/mixed_study.py`
- Modify: `tuba/geometry/step_analysis_importer.py`
- Test: `tests/test_mixed_code_aster_export.py`

- [ ] **Step 1: Add optional Gmsh-backed STEP volume test**

Append to `tests/test_mixed_code_aster_export.py`:

```python
import importlib.util


def write_box_step(path: Path) -> bool:
    if importlib.util.find_spec("gmsh") is None:
        return False
    import gmsh

    gmsh.initialize()
    try:
        gmsh.model.add("box_step_fixture")
        gmsh.model.occ.addBox(0.95, -0.05, -0.05, 0.1, 0.1, 0.1)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return True
```

Append this test to `TestMixedCodeAsterExport`:

```python
    def test_gmsh_writer_exports_step_volume_when_available(self):
        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "box.step"
            if not write_box_step(step_path):
                self.skipTest("gmsh is required for STEP volume MED export.")
            model.cad_assets["cad_asset_0"] = model.cad_assets["cad_asset_0"].__class__(
                **{
                    **model.cad_assets["cad_asset_0"].to_dict(),
                    "source_path": str(step_path),
                    "content_digest": "sha256:box",
                }
            )
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            med_path = Path(study.input_files["med"])

        self.assertGreater(med_path.stat().st_size, 0)
```

- [ ] **Step 2: Run optional Gmsh test**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_gmsh_writer_exports_step_volume_when_available -q
```

Expected: skipped when `gmsh` is unavailable; otherwise the test fails until
the writer chooses the Gmsh path for real STEP assets.

- [ ] **Step 3: Add a Gmsh writer path before the meshio fallback**

Modify `tuba/solver/mixed_study.py`:

```python
    def _write_med(self, model: TubaModel, path: Path) -> None:
        if self._has_existing_step_assets(model):
            self._write_med_with_gmsh(model, path)
        else:
            self._write_med_with_meshio(model, path)

    def _has_existing_step_assets(self, model: TubaModel) -> bool:
        return any(Path(asset.source_path).exists() for asset in model.cad_assets.values())
```

Add the Gmsh writer:

```python
    def _write_med_with_gmsh(self, model: TubaModel, path: Path) -> None:
        try:
            import gmsh
        except ImportError as exc:
            raise RuntimeError("gmsh is required to write MED studies from STEP assets.") from exc

        gmsh.initialize()
        try:
            gmsh.model.add("tuba_mixed")
            for asset in model.cad_assets.values():
                source = Path(asset.source_path)
                if not source.exists():
                    raise RuntimeError(f"STEP asset file does not exist: {source}")
                gmsh.model.occ.importShapes(str(source))
            gmsh.model.occ.synchronize()

            volume_tags = [tag for _, tag in gmsh.model.getEntities(3)]
            for region in model.analysis_regions.values():
                if region.role == "solid_3d" and volume_tags:
                    gmsh.model.addPhysicalGroup(3, volume_tags, name=region.mesh_group)

            pipe_line_tags = []
            for element in model.elements:
                if element.type not in {"pipe_straight", "pipe_bend", "beam"}:
                    continue
                n1 = model.nodes[element.n1].coords
                n2 = model.nodes[element.n2].coords
                p1 = gmsh.model.geo.addPoint(float(n1[0]), float(n1[1]), float(n1[2]), 1.0)
                p2 = gmsh.model.geo.addPoint(float(n2[0]), float(n2[1]), float(n2[2]), 1.0)
                pipe_line_tags.append(gmsh.model.geo.addLine(p1, p2))
            gmsh.model.geo.synchronize()
            if pipe_line_tags:
                gmsh.model.addPhysicalGroup(1, pipe_line_tags, name="G_TUBE")

            for port in model.ports.values():
                face_tag = port.metadata.get("gmsh_face_tag")
                if port.face_group and isinstance(face_tag, int):
                    gmsh.model.addPhysicalGroup(2, [face_tag], name=port.face_group)

            gmsh.model.mesh.generate(3)
            gmsh.write(str(path))
        except Exception as exc:
            raise RuntimeError(f"Failed to write Gmsh MED mesh {path}: {exc}") from exc
        finally:
            gmsh.finalize()
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Gmsh MED writer produced an empty file: {path}")
```

This is the first real imported-solid path. The meshio path remains a portable
writer for unit fixtures that do not have a STEP file on disk.

- [ ] **Step 4: Preserve Gmsh face tags from detected ports**

In `tuba/geometry/step_analysis_importer.py`, keep the detected face tag in
port metadata. The existing `_detect_port_candidates` code already returns:

```python
"metadata": {"gmsh_face_tag": face_tag},
```

Verify `record_component_from_metadata` passes this metadata into `model.add_port(...)`.

- [ ] **Step 5: Run Gmsh and export tests**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py -q
python -m pytest tests\test_step_analysis_importer.py -q
```

Expected: portable tests pass; Gmsh-specific test skips when Gmsh is missing and
passes when Gmsh is installed.

- [ ] **Step 6: Commit Task 6**

```powershell
git add tuba\solver\mixed_study.py tuba\geometry\step_analysis_importer.py tests\test_mixed_code_aster_export.py
git commit -m "feat: populate mixed MED studies from STEP volumes"
```

---

### Task 7: Public CodeAsterSolver Mixed Entry Point

**Files:**
- Modify: `tuba/solver/aster.py`
- Test: `tests/test_mixed_code_aster_export.py`

- [ ] **Step 1: Add failing public API test**

Append to `TestMixedCodeAsterExport`:

```python
    def test_code_aster_solver_delegates_mixed_export(self):
        from tuba.solver.aster import CodeAsterSolver

        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_mixed_analysis_study(model, "Hot", tmpdir)

        self.assertEqual(study.metadata["mixed_analysis"], True)
        self.assertTrue(Path(study.input_files["comm"]).exists())
        self.assertTrue(Path(study.input_files["sidecar"]).exists())
```

- [ ] **Step 2: Run failing public API test**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_code_aster_solver_delegates_mixed_export -q
```

Expected: `AttributeError` for missing `export_mixed_analysis_study`.

- [ ] **Step 3: Add delegating method**

Modify `tuba/solver/aster.py` inside `CodeAsterSolver` near `export_analysis_study`:

```python
    def export_mixed_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str,
        output_dir: str | Path,
    ) -> AnalysisStudy:
        """Generate a MED-backed mixed Code_Aster study without running the solver."""
        from tuba.solver.mixed_study import MixedCodeAsterStudyExporter

        return MixedCodeAsterStudyExporter().export_analysis_study(model, load_case_name, output_dir)
```

- [ ] **Step 4: Run public API and existing solver tests**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_code_aster_solver_delegates_mixed_export -q
python -m pytest tests\test_code_aster_study.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add tuba\solver\aster.py tests\test_mixed_code_aster_export.py
git commit -m "feat: expose mixed Code_Aster study export"
```

---

### Task 8: Result-Provenance Review Diagnostics

**Files:**
- Modify: `tuba/visualization/builders.py`
- Test: `tests/test_mixed_code_aster_export.py`

- [ ] **Step 1: Add failing diagnostics test**

Append to `TestMixedCodeAsterExport`:

```python
    def test_mixed_sidecar_can_be_read_for_review_diagnostics(self):
        from tuba.solver.mixed_study import load_mixed_sidecar_diagnostics

        model = build_mixed_fixture()
        with tempfile.TemporaryDirectory() as tmpdir:
            study = MixedCodeAsterStudyExporter().export_analysis_study(model, "Hot", tmpdir)
            diagnostics = load_mixed_sidecar_diagnostics(study.input_files["sidecar"])

        self.assertIn("component:component_pump_body", diagnostics["refs"])
        self.assertIn("port:port_pump_nozzle_a", diagnostics["refs"])
        self.assertIn("coupling:coupling_pipe_to_pump_a", diagnostics["refs"])
        self.assertEqual(diagnostics["result_status"], "export_only")
```

- [ ] **Step 2: Run failing diagnostics test**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_mixed_sidecar_can_be_read_for_review_diagnostics -q
```

Expected: import failure for missing `load_mixed_sidecar_diagnostics`.

- [ ] **Step 3: Add sidecar diagnostics helper**

Append to `tuba/solver/mixed_study.py`:

```python
def load_mixed_sidecar_diagnostics(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mixed = payload.get("mixed_analysis", {})
    refs: list[str] = []
    refs.extend(f"cad_asset:{key}" for key in mixed.get("cad_assets", {}))
    refs.extend(f"component:{key}" for key in mixed.get("components", {}))
    refs.extend(f"analysis_region:{key}" for key in mixed.get("analysis_regions", {}))
    refs.extend(f"port:{key}" for key in mixed.get("ports", {}))
    refs.extend(f"coupling:{key}" for key in mixed.get("couplings", {}))
    return {
        "result_status": "export_only",
        "refs": refs,
        "lineage": dict(payload.get("lineage", {})),
        "analysis_mesh_id": payload.get("analysis_mesh_id"),
    }
```

- [ ] **Step 4: Run diagnostics test**

Run:

```powershell
python -m pytest tests\test_mixed_code_aster_export.py::TestMixedCodeAsterExport::test_mixed_sidecar_can_be_read_for_review_diagnostics -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 7**

```powershell
git add tuba\solver\mixed_study.py tests\test_mixed_code_aster_export.py
git commit -m "feat: expose mixed study provenance diagnostics"
```

---

### Task 9: Optional Real Code_Aster Integration Gate

**Files:**
- Create: `tests/integration/test_mixed_code_aster_runtime.py`

- [ ] **Step 1: Write integration test guarded by runtime availability**

Create `tests/integration/test_mixed_code_aster_runtime.py`:

```python
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import discover_code_aster_runtime
from tests.test_mixed_code_aster_export import build_mixed_fixture


class TestMixedCodeAsterRuntime(unittest.TestCase):
    def test_mixed_export_runtime_gate_is_explicit(self):
        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_mixed_analysis_study(model, "Hot", tmpdir)
            self.assertTrue(Path(study.input_files["comm"]).exists())
            self.assertTrue(Path(study.input_files["med"]).exists())

    def test_mixed_study_runs_when_code_aster_is_configured(self):
        if not os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION"):
            self.skipTest("Set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster mixed studies.")
        runtime = discover_code_aster_runtime()
        if not runtime.available:
            self.skipTest(runtime.reason or "No Code_Aster runtime available.")
        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            solver = CodeAsterSolver(work_dir=tmpdir)
            study = solver.export_mixed_analysis_study(model, "Hot", tmpdir)
            results = solver.solve_exported_study(model, study)

        self.assertEqual(results.solver, "Code_Aster")
        self.assertTrue(results.node_results or results.element_results)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run portable integration gate**

Run:

```powershell
python -m pytest tests\integration\test_mixed_code_aster_runtime.py::TestMixedCodeAsterRuntime::test_mixed_export_runtime_gate_is_explicit -q
```

Expected: pass without requiring Code_Aster.

- [ ] **Step 3: Run optional real solver test when available**

Run only in a configured Code_Aster environment:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
python -m pytest tests\integration\test_mixed_code_aster_runtime.py::TestMixedCodeAsterRuntime::test_mixed_study_runs_when_code_aster_is_configured -q
```

Expected when Code_Aster is unavailable: skipped with a clear runtime reason.
Expected when Code_Aster is available: pass with real result artifacts.

- [ ] **Step 4: Commit Task 8**

```powershell
git add tests\integration\test_mixed_code_aster_runtime.py
git commit -m "test: add mixed Code_Aster runtime gate"
```

---

### Task 10: Documentation And Example Guardrails

**Files:**
- Modify: `docs/superpowers/specs/2026-06-30-step-mixed-code-aster-design.md`
- Create: `docs/architecture/step-mixed-code-aster.md`
- Test: `tests/test_examples.py` if examples are added

- [ ] **Step 1: Add concise architecture doc**

Create `docs/architecture/step-mixed-code-aster.md`:

```markdown
# STEP Mixed Code_Aster Studies

Tuba can import STEP geometry for mixed Code_Aster studies only after the imported
geometry has explicit analysis regions, confirmed ports, material assignments,
mesh groups, and coupling specs.

Exported `.med`, `.comm`, `.export`, `study_manifest.json`, and
`study_tuba_fem.json` files are solver handoff artifacts. They are not completed
engineering results.

Production stress, displacement, reaction, compliance, operating-state clash, and
result visualization workflows must use artifacts produced by a real Code_Aster
run. If Code_Aster is unavailable, Tuba may export the study for inspection but
must stop before displaying solver results.

First supported slice:

```text
native Tuba pipe endpoint
  -> confirmed imported solid port
  -> LIAISON_ELEM OPTION='3D_TUYAU'
  -> MED-backed Code_Aster study
```
```

- [ ] **Step 2: Link the architecture doc from the spec**

Append to the references in `docs/superpowers/specs/2026-06-30-step-mixed-code-aster-design.md`:

```markdown
- Implementation architecture summary: `docs/architecture/step-mixed-code-aster.md`
```

- [ ] **Step 3: Run docs-sensitive tests**

Run:

```powershell
python -m pytest tests\test_examples.py -q
```

Expected: pass. If this repo has no docs-link validation in that test file, passing existing example tests is enough.

- [ ] **Step 4: Commit Task 9**

```powershell
git add docs\architecture\step-mixed-code-aster.md docs\superpowers\specs\2026-06-30-step-mixed-code-aster-design.md
git commit -m "docs: document STEP mixed Code_Aster guardrails"
```

---

## Final Verification

- [ ] **Step 1: Run portable mixed feature tests**

```powershell
python -m pytest tests\test_mixed_model.py tests\test_step_analysis_importer.py tests\test_mixed_code_aster_export.py -q
```

Expected: pass, with only environment-specific MED tests skipped if local MED support is missing.

- [ ] **Step 2: Run existing Code_Aster and core smoke tests**

```powershell
python -m pytest tests\test_code_aster_study.py tests\test_code_aster_bridge.py tests\test_tuba_core.py -q
```

Expected: pass.

- [ ] **Step 3: Check result provenance guardrail**

Run:

```powershell
rg -n "mock|fabricated|fake" notebooks examples tuba tests
```

Expected: no new result-display path presents fabricated values as Code_Aster solver results. Existing negative tests or explicit guardrail text are acceptable.

- [ ] **Step 4: Run real Code_Aster integration when configured**

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
python -m pytest tests\integration\test_mixed_code_aster_runtime.py -q
```

Expected when runtime is absent: skipped with runtime reason.
Expected when runtime is present: pass with real Code_Aster result artifacts.

- [ ] **Step 5: Inspect final git state**

```powershell
git status --short
git log --oneline -9
```

Expected: only intentional task commits for this feature are present; unrelated dirty files from before the plan remain untouched.
