# Multidomain IFC-Aware Data Model Spec

## Purpose

Update Tuba from a pipe-centered model with support helpers into a multidomain engineering model for piping, support structures, rack assemblies, load transfer, routing, clash checks, cost optimization, visualization, and IFC/BCF exchange.

The target architecture is IFC-aware but not IFC-native. Tuba stays the authoritative model for scripted generation, optimization, clash checks, routing, cost decisions, solver preparation, and agent patches. IFC becomes an adapter, vocabulary, validation target, and coordination format.

## Current Starting Point

Tuba already has the right foundation:

- `TubaModel` owns materials, sections, nodes, elements, supports, load cases, obstacles, groups, specs, and attributes.
- `EntityRef` gives stable references for nodes, elements, supports, obstacles, groups, assemblies, routes, materials, sections, and load cases.
- `InsulationSpec` and `AttributeAssignment` attach non-geometry facts to elements or groups.
- `ModelPatch` and `ModelTransaction` provide a reviewable mutation boundary.
- `RackBay` generates rack geometry through patches and group metadata.
- `analyze_load_paths()` connects supports to rack attachment points.
- Physical properties, clash, quantities, routing costs, rules, visualization scenes, BCF, and IFC export already consume parts of the semantic model.

The main limitation is that support structure is still modeled mostly as generic elements and group metadata. Relationships, ports, assemblies, support attachments, external identities, IFC property-set mappings, and performance indexes need to become explicit.

## Design Principles

1. Tuba native data is the source of truth.
2. IFC influences shape and vocabulary, but does not become the internal optimization graph.
3. Pipe systems and support structures are equally first-class.
4. Relationships are first-class data, not hidden in ad hoc metadata.
5. Type/spec data is separate from occurrence data.
6. Ports and attachments are explicit connection points.
7. Derived facts are cached or indexed, not duplicated as authoritative state.
8. Agent output must remain patch-first and reviewable.
9. All new data model features must roundtrip through JSON.
10. Every export mapping must be deterministic and testable.

## Non-Goals

- Do not rewrite `TubaModel` in one breaking migration.
- Do not require IFC for internal routing, clash, cost, or visualization.
- Do not represent every IFC entity natively.
- Do not build a full structural solver in the data-model package.
- Do not move all attributes into custom classes immediately.
- Do not remove current `groups` until assemblies and relationship indexes are proven.

## IFC Lessons To Adopt

### Identity

IFC `IfcRoot` has stable global identity, name, description, and ownership/history concepts. Tuba should add stable external identities and keep `EntityRef` as the internal identity.

Required native concepts:

```text
EntityRef
EntityRecord
ExternalIdentity
IfcGuidRegistry
```

### Occurrence And Type Split

IFC separates occurrences from type definitions. Tuba should formalize the same pattern:

```text
Pipe occurrence -> Element
Pipe type -> PipeSpec / section / material
Insulation occurrence assignment -> AttributeAssignment
Insulation type -> InsulationSpec
Rack occurrence -> Assembly
Rack type -> RackSpec
Support occurrence -> Support / SupportComponent
Support type -> SupportSpec
```

### Property Sets

IFC property sets are a good export and validation shape. Tuba should keep native specs and attributes but maintain a mapping registry to export them as property sets.

Required Tuba property-set namespaces:

- `Tuba_Identity`
- `Tuba_Pipe`
- `Tuba_Insulation`
- `Tuba_Cladding`
- `Tuba_Route`
- `Tuba_Cost`
- `Tuba_Quantity`
- `Tuba_Rack`
- `Tuba_Support`
- `Tuba_LoadPath`
- `Tuba_Clash`
- `Tuba_Rule`
- `Tuba_Agent`

### Ports And Connectivity

IFC `IfcDistributionPort` is the right model for connection points. Tuba needs native ports for:

- pipe endpoints
- equipment nozzles
- branch points
- fitting ports
- rack/support attachment points
- structural member connection points

### Assemblies

IFC `IfcElementAssembly` is the right external pattern for rack bays, frames, modules, and preassembled support structures. Tuba should add native assemblies and keep `groups` as compatibility views.

### Structural Analysis Separation

IFC separates physical products such as beams and columns from structural analysis items and analysis models. Tuba should do the same:

- physical structural members remain `Element` occurrences.
- support reactions and load transfer live in `LoadTransfer` / `StructuralAnalysisSnapshot`.
- solver-specific results remain result objects, not core authoritative geometry.

### IFC-Style Placement And Coordinate Frames

IFC's placement model is the right pattern for global/local coordinate handling. Products carry an `ObjectPlacement`; local placements may be relative to parent placements; a 3D axis placement is defined by a location, an axis, and a reference direction. Tuba should adopt this structure natively, while keeping solver-facing nodes in one authoritative global Cartesian model frame.

Required native concepts:

```text
CoordinateSystem
PlacementFrame
PlacementAssignment
FrameReference
```

Core rules:

- `TubaModel.nodes[*].coords` remain stored in model-global Cartesian coordinates.
- `CoordinateSystem` remains a right-handed orthonormal Cartesian basis with point and vector transforms.
- `PlacementFrame` represents a named local placement, optionally relative to a parent frame or entity.
- `PlacementFrame` should map directly to IFC `IfcLocalPlacement` plus `IfcAxis2Placement3D`.
- Frame composition must be deterministic: parent frame transform multiplied by local frame transform.
- Authoring APIs may accept local coordinates only when the reference frame is explicit.
- Solver export consumes global coordinates and explicit transformed global vectors unless the backend natively supports a declared local reference.
- IFC export should preserve placement hierarchy where possible instead of emitting every product as an unrelated absolute object.
- IFC import should resolve chained local placements into global coordinates for nodes and should preserve the original placement chain as `PlacementFrame` and `ExternalIdentity` metadata.

Frame taxonomy:

| Frame type | Purpose | Storage rule |
| --- | --- | --- |
| `model_global` | Tuba source-of-truth coordinate frame | implicit singleton |
| `site` / `survey` | BIM/site exchange coordinates and large-offset mapping | optional `PlacementFrame` |
| `assembly` | rack bay, skid, module, pipe spool, support frame | `PlacementFrame` tied to `Assembly` |
| `product` | IFC-style product occurrence placement | optional `PlacementAssignment` |
| `route_local` | pipe-builder cursor frame, local X is current pipe tangent | derived/ephemeral unless explicitly captured |
| `element_local` | pipe/beam local axis and section orientation | derived from element geometry plus orientation metadata |
| `support_local` | support hardware or restraint reference direction | explicit only when used by supports/loads |

Tuba should support different user-facing coordinate inputs as adapters, not as separate core geometry storage:

- Cartesian: first-class and persisted.
- Offset/station/elevation: converted through a named frame or route frame.
- Cylindrical/radial grids: accepted for plant/rack authoring when linked to a named frame, then converted to Cartesian.
- Survey coordinates: accepted through a site/survey transform, then converted to model-global.

Do not store native nodes in cylindrical, spherical, or survey coordinates. Preserve the authoring frame and original input only as metadata/provenance.

## Target Data Model

### `AnalysisStudy`

Immutable snapshot of the model as submitted to a solver backend.

```python
@dataclass(frozen=True)
class AnalysisStudy:
    id: str
    model_revision: int
    solver_name: str
    load_case: str
    work_dir: str | None = None
    input_files: dict[str, str] = field(default_factory=dict)
    mesh: EntityRef | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

The study is important because Code_Aster may use a generated analysis mesh that is more detailed than the native Tuba node/element graph. Pipe bends already create intermediate mesh nodes and segment elements. Those must be traceable back to native elements for accurate result projection, visualization, and deformed clash checks.

### `AnalysisMesh`

Traceable mesh generated for a solver.

```python
@dataclass(frozen=True)
class AnalysisMesh:
    id: str
    model_revision: int
    solver_name: str
    nodes: dict[str, tuple[float, float, float]]
    elements: dict[str, tuple[str, ...]]
    node_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    element_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
```

Examples:

```json
{
  "node_sources": {
    "pipe_bend_0_n3": {
      "entity": "element:pipe_bend_0",
      "parametric_t": 0.1875,
      "generated": true
    }
  },
  "element_sources": {
    "pipe_bend_0_s3": {
      "entity": "element:pipe_bend_0",
      "segment_index": 3
    }
  }
}
```

### `ResultState`

Solver result snapshot for one load case and one model revision.

```python
@dataclass(frozen=True)
class ResultState:
    id: str
    study: EntityRef
    model_revision: int
    solver_name: str
    load_case: str
    mesh: EntityRef | None
    node_displacements: dict[str, tuple[float, float, float, float, float, float]]
    node_reactions: dict[str, tuple[float, float, float, float, float, float]]
    element_results: dict[str, dict[str, Any]]
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

`FEAResults` can remain the in-memory result container. `ResultState` is the serializable, traceable, model-revision-aware result record used by visualization, clash, route scoring, and agent review.

### `GeometryState`

Projection of native geometry into a particular physical state.

```python
@dataclass(frozen=True)
class GeometryState:
    id: str
    model_revision: int
    state_type: str                  # cold, operating, deformed, construction, preview
    load_case: str | None = None
    result_state: EntityRef | None = None
    deformation_scale: float = 1.0
    safety_factor: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
```

Important rule:

- visualization may use `deformation_scale > 1.0`.
- clash detection and route feasibility must use physical displacement, normally `deformation_scale = 1.0`.
- if a design rule requires conservatism, use a named `safety_factor`, not the visual scale.

### `DeformedEnvelope`

Computed derived geometry for clash/routing.

```python
@dataclass(frozen=True)
class DeformedEnvelope:
    entity: EntityRef
    geometry_state: EntityRef
    envelope_type: str               # bare, insulation, clearance, maintenance, wind
    polyline: tuple[tuple[float, float, float], ...]
    radius_m: float
    bounds: tuple[float, float, float, float, float, float]
    source_mesh_elements: tuple[str, ...] = ()
```

The deformed envelope is derived. It should be cached by model revision, result state, load case, envelope type, and safety factor.

### `EntityRecord`

Lightweight metadata for every first-class entity.

```python
@dataclass(frozen=True)
class EntityRecord:
    ref: EntityRef
    name: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    status: str | None = None
    created_by: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.entity_records: dict[str, EntityRecord]
```

Key format is `str(EntityRef)`.

### `PlacementFrame`

Named local coordinate system using IFC-style relative placement semantics.

```python
@dataclass(frozen=True)
class PlacementFrame:
    id: str
    origin: tuple[float, float, float]
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    ref_direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    parent: EntityRef | None = None
    frame_type: str = "generic"          # site, assembly, product, route_local, element_local, support_local
    source: str | None = None            # native, ifc, user, agent, import
    metadata: dict[str, Any] = field(default_factory=dict)
```

Semantics:

- `origin`, `axis`, and `ref_direction` are relative to `parent` when `parent` is set.
- `axis` is the local Z direction, matching IFC `IfcAxis2Placement3D.Axis`.
- `ref_direction` is the local X direction, matching IFC `IfcAxis2Placement3D.RefDirection`.
- local Y is computed as `axis cross ref_direction` after orthonormalization and right-handed validation.
- `CoordinateSystem` remains the math object used to transform points/vectors once a placement chain is resolved.

Storage:

```python
model.placement_frames: dict[str, PlacementFrame]
```

Indexes:

```text
placement_frame_by_id
placement_frames_by_parent
placement_frames_by_type
```

Required helpers:

```python
model.add_placement_frame(...)
model.resolve_placement_frame(frame_ref) -> CoordinateSystem
model.to_global_point(point, frame=None)
model.to_global_vector(vector, frame=None)
model.to_local_point(point, frame)
```

### `PlacementAssignment`

Optional occurrence-to-frame link for products, assemblies, support components, context geometry, and imported IFC products.

```python
@dataclass(frozen=True)
class PlacementAssignment:
    target: EntityRef
    frame: EntityRef
    role: str = "object_placement"       # object_placement, authoring_frame, result_frame, import_frame
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.placement_assignments: list[PlacementAssignment]
```

Rules:

- A target may have at most one `object_placement` assignment per source system.
- Multiple authoring/provenance frames may be recorded when useful.
- A `PlacementAssignment` must never imply that node coordinates are local; native nodes remain global.
- IFC export may choose relative placement from `PlacementAssignment` while still deriving geometry from global nodes.

### `ExternalIdentity`

Stable mapping between native objects and external systems.

```python
@dataclass(frozen=True)
class ExternalIdentity:
    target: EntityRef
    system: str              # "ifc", "bcf", "speckle", "revit", "navisworks"
    external_id: str         # IFC GlobalId, BCF topic GUID, etc.
    external_type: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.external_identities: list[ExternalIdentity]
```

Indexes:

```text
by target
by system + external_id
```

### `ModelRelationship`

First-class relationship object for topology, assemblies, load transfer, and exchange mappings.

```python
@dataclass(frozen=True)
class ModelRelationship:
    id: str
    type: str
    source: EntityRef
    target: EntityRef
    source_role: str | None = None
    target_role: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
```

Core relationship types:

- `contains`
- `decomposes`
- `connects`
- `covers`
- `supports`
- `attached_to`
- `loads`
- `restrains`
- `routes_through`
- `belongs_to_system`
- `has_port`
- `uses_spec`
- `has_material`
- `has_property_set`
- `has_issue`
- `interferes_with`
- `classified_as`
- `external_reference`
- `generated_by`

Storage:

```python
model.relationships: list[ModelRelationship]
```

Required indexes:

```text
relationships_by_source
relationships_by_target
relationships_by_type
relationship_pair_index
```

### `Port`

Native connection point.

```python
@dataclass(frozen=True)
class Port:
    id: str
    owner: EntityRef
    position: tuple[float, float, float]
    direction: tuple[float, float, float] | None = None
    port_type: str = "generic"          # pipe, nozzle, support_attachment, structural_joint
    system: str | None = None           # chilled_water, steam, fuel, rack_support
    flow_direction: str | None = None   # source, sink, bidirectional, not_applicable
    nominal_diameter_m: float | None = None
    connection_spec: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.ports: dict[str, Port]
```

Connections are relationships:

```text
port:A connects port:B
element:pipe_0 has_port port:pipe_0_start
```

### `Assembly`

Native assembly object for rack bays, frames, modules, and support units.

```python
@dataclass(frozen=True)
class Assembly:
    id: str
    type: str                       # rack_bay, rack_frame, support_frame, skid, pipe_module
    name: str | None = None
    members: tuple[EntityRef, ...] = ()
    ports: tuple[EntityRef, ...] = ()
    parent: EntityRef | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.assemblies: dict[str, Assembly]
```

Compatibility:

- `model.groups` remains supported.
- New `Assembly` writes may optionally create a group view.
- Existing `RackBay.to_patch()` should migrate from `CreateGroup` only to `CreateAssembly` plus compatibility `CreateGroup`.

### `SupportComponent`

Represent a physical support item where the current `Support` boundary condition is not enough.

```python
@dataclass(frozen=True)
class SupportComponent:
    id: str
    type: str                       # shoe, clamp, guide, spring_hanger, rest, anchor, bracket
    node: str | None = None
    supported: EntityRef | None = None
    attached_to: EntityRef | None = None
    section: str | None = None
    material: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`Support` remains the solver boundary condition. `SupportComponent` is the physical/constructible object.

### `LoadTransfer`

Explicit load path between pipe/support and structure.

```python
@dataclass(frozen=True)
class LoadTransfer:
    id: str
    load_case: str
    source: EntityRef
    target: EntityRef
    via: EntityRef | None = None
    force_n: tuple[float, float, float] = (0.0, 0.0, 0.0)
    moment_nm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    dof: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
```

Storage:

```python
model.load_transfers: list[LoadTransfer]
```

### `Specification Registry`

Keep `model.specs`, but formalize typed spec families:

```text
insulation
cladding
support
rack
route
cost
connection
system
ifc_export_profile
```

Each spec must support:

- `id`
- validation
- `to_dict()`
- `from_dict()`
- optional IFC property-set mapping
- optional bSDD URI or classification URI

### `IfcMappingRegistry`

Central code-defined mapping from Tuba native concepts to IFC.

```python
@dataclass(frozen=True)
class IfcEntityMapping:
    tuba_kind: str
    tuba_type: str | None
    ifc_entity: str
    predefined_type: str | None = None
    fallback_entity: str | None = None
```

```python
@dataclass(frozen=True)
class IfcPropertyMapping:
    source_path: str
    pset_name: str
    property_name: str
    ifc_measure: str | None = None
    unit: str | None = None
    bsdd_uri: str | None = None
    export_if_missing: bool = False
```

```python
@dataclass(frozen=True)
class IfcRelationshipMapping:
    tuba_relationship: str
    ifc_relationship: str
    strategy: str
```

Required export profiles:

- `coordination_minimal`
- `coordination_with_insulation`
- `rack_and_supports`
- `analysis_results`
- `handover_enriched`

## IFC Mapping Targets

### Piping

| Tuba object | Preferred IFC target |
| --- | --- |
| placement frame | `IfcLocalPlacement` plus `IfcAxis2Placement3D` |
| product placement assignment | `IfcProduct.ObjectPlacement` |
| pipe straight element | `IfcPipeSegment` |
| pipe bend/fitting | `IfcPipeFitting` |
| pipe endpoint/nozzle | `IfcDistributionPort` |
| route/system | `IfcDistributionSystem` or custom property set |
| insulation assignment | `IfcCovering` with `INSULATION` when geometric, plus property set |
| pipe material | `IfcRelAssociatesMaterial` |

### Support Structure

| Tuba object | Preferred IFC target |
| --- | --- |
| rack/support frame placement | `IfcLocalPlacement` relative to site/building/storey or parent assembly |
| horizontal rack member | `IfcBeam` |
| vertical rack member | `IfcColumn` |
| generic brace/member | `IfcMember` |
| rack bay/frame | `IfcElementAssembly` |
| physical shoe/clamp/anchor | `IfcDiscreteAccessory`, `IfcMechanicalFastener`, or proxy fallback |
| support boundary condition | Tuba property set, optional structural analysis export |
| load transfer/reaction | Tuba property set, optional `IfcStructuralAnalysisModel` export profile |

### Issues And Review

| Tuba object | Preferred exchange |
| --- | --- |
| clash issue | BCF topic plus optional IFC interference relation/property set |
| rule issue | BCF topic plus `Tuba_Rule` property set |
| agent proposal | Tuba scene diff and patch provenance, not IFC mutation |

## JSON Shape

Add these top-level optional keys:

```json
{
  "schema_version": "0.5",
  "entity_records": {},
  "placement_frames": {},
  "placement_assignments": [],
  "external_identities": [],
  "relationships": [],
  "ports": {},
  "assemblies": {},
  "support_components": {},
  "load_transfers": [],
  "specs": {}
}
```

Backwards compatibility:

- Missing keys default to empty collections.
- Existing JSON still validates and loads.
- `groups` remains supported.
- Existing `support` solver objects remain supported.
- Existing element types remain supported.

## Patch Operations

Add patch operations in small increments:

- `SetEntityRecord`
- `AddPlacementFrame`
- `AssignPlacement`
- `RemovePlacementAssignment`
- `SetExternalIdentity`
- `AddRelationship`
- `RemoveRelationship`
- `AddPort`
- `ConnectPorts`
- `CreateAssembly`
- `AddSupportComponent`
- `AddLoadTransfer`
- `AddGenericSpec`
- `AssignSpec`
- `SetIfcExportProfile`

Patch requirements:

- Each operation serializes through `ModelPatch.to_dict()`.
- Each operation validates before mutation.
- Transaction rollback remains atomic.
- Preview and agent workspace can produce all new operations without direct mutation.

## Validation Rules

Core validation:

- All `EntityRef` targets resolve or are explicitly marked external/context.
- Placement frames form an acyclic parent graph.
- Placement frame axes are finite, nonzero, orthogonal after validation, and right-handed.
- Placement assignments reference existing targets and frames.
- A target cannot have duplicate `object_placement` assignments for the same source.
- No duplicate entity IDs within a kind.
- No duplicate IFC GUID for different targets in the same model.
- Port owner exists.
- Port connection has compatible connection specs unless override is explicit.
- Assembly members exist.
- Assembly relationship graph has no invalid cycles except allowed nested assemblies.
- Support component cannot reference a missing supported object or attachment target.
- Load transfer source/target exists.
- Load transfer load case exists.
- Property mappings reference known specs/attributes.
- Analysis study model revision matches the model revision used for result interpretation.
- Analysis mesh source maps reference known native entities.
- Result state node IDs are either native node IDs or solver mesh node IDs known to the analysis mesh.
- Geometry state using solver results references an existing result state.
- Deformed envelopes are never serialized as authoritative model data unless explicitly stored as derived cache artifacts.

Engineering validation:

- Support loads must map to at least one structure target before rack utilization checks.
- Routing cannot use a structural reserved zone unless allowed.
- Insulation envelope must be used for clash when assigned.
- Cost model must be able to distinguish pipe length, supports, rack members, insulation, and detour penalties.

IFC validation:

- IFC GUIDs are stable across repeated exports.
- IFC local placement chains resolve to the same global coordinates used by native nodes within tolerance.
- IFC import preserves product placement metadata even when native geometry is flattened to global nodes.
- IFC export diagnostics report when a native placement cannot be represented as `IfcLocalPlacement`.
- IFC entity mapping exists or fallback is explicit.
- IFC property sets contain units where values need units.
- IFC export profile determines whether insulation is property-only or geometry.
- Export diagnostics report unsupported mappings.

Solver/result validation:

- Code_Aster input generation must record mesh-to-entity source mapping.
- Thermal load cases must preserve `temperature` and `ref_temperature`.
- Post-solve displacement fields must include generated bend mesh nodes where available, not only native Tuba nodes.
- Deformed clash checks must declare the geometry state and load case used.
- Visual deformation scale must not be reused silently as clash displacement scale.

## Performance Architecture

Performance must be designed into the model update, not added after.

### Entity Indexes

Current model often scans lists for elements, supports, and group membership. Add a `ModelIndex` that is rebuilt lazily and invalidated by transactions.

Required indexes:

```text
node_by_id
element_by_id
support_by_id
support_component_by_id
assembly_by_id
port_by_id
placement_frame_by_id
placement_frames_by_parent
placement_assignments_by_target
relationships_by_source
relationships_by_target
relationships_by_type
ports_by_owner
groups_by_member
assemblies_by_member
external_identity_by_target
external_identity_by_external_id
elements_by_node
supports_by_node
```

### Spatial Indexes

Add optional spatial indexes for:

- element bounding boxes
- physical envelopes
- insulation envelopes
- clearance envelopes
- obstacles
- support components
- rack members
- external context geometry

Recommended implementation path:

1. Pure Python/Numpy AABB index for portability.
2. Optional `trimesh`/R-tree acceleration where available.
3. Cache invalidation by model revision.

### Revision And Cache Invalidation

Add:

```python
model.revision: int
model.index_revision: int
model.derived_cache_revision: int
```

Every mutation through `ModelTransaction` increments `model.revision`. Derived caches store the revision they were computed against.

### Derived Data Cache

Cache expensive derived values:

- element length
- physical properties
- collision envelope
- quantity records
- route candidate cost breakdown
- geometry asset descriptors
- IFC GUID lookup
- relationship adjacency
- analysis mesh source mapping
- result-state deformed polylines
- deformed physical envelopes

Do not cache authoritative values that can drift silently.

### Scene And IFC Export

Large exports should not rebuild everything repeatedly.

Requirements:

- deterministic geometry asset keys
- batching by section/material/envelope style
- progressive scene bundle option
- IFC export visitor over indexed model
- no IFC roundtrip inside route optimization
- export diagnostics accumulated without stopping the whole export unless strict mode is enabled

### Benchmarks

Add benchmark fixtures:

- small: 100 elements, 20 supports, 1 rack
- medium: 1,000 elements, 200 supports, 20 racks
- large: 10,000 elements, 2,000 supports, 200 racks
- stress: 100,000 lightweight elements for indexing/export smoke only

Track:

- model load time
- model serialization time
- index rebuild time
- physical properties pass
- clash broadphase candidate count and time
- route cost evaluation time
- scene build time
- IFC export time
- peak memory where practical

Initial target gates on developer hardware:

- 10,000 elements index rebuild under 2 seconds.
- 10,000 element physical property pass under 2 seconds.
- 10,000 element scene metadata build under 5 seconds.
- 1,000 element enriched IFC export under 10 seconds.
- Relationship lookup by entity under 1 ms after index build.

These gates can be tuned once real project models exist.

## Migration Strategy

### Compatibility First

Version 1 keeps the current public API working:

- `model.elements`
- `model.supports`
- `model.groups`
- `model.placement_frames`
- `model.placement_assignments`
- `model.specs`
- `model.attributes`
- existing JSON fixtures
- existing IFC export/import tests

New structures are optional and additive.

### Group To Assembly Migration

Rack groups should migrate in stages:

1. Preserve `groups`.
2. Add `assemblies`.
3. `RackBay.to_patch()` writes both.
4. Load old rack groups as virtual assemblies in indexes.
5. Later, make assemblies primary and groups a view.

### Support To SupportComponent Migration

Do not replace solver `Support` immediately.

1. Keep `Support` as boundary condition.
2. Add `SupportComponent` as physical object.
3. Link `Support` to `SupportComponent` with `represents` or `uses_spec`.
4. Export physical support components to IFC.
5. Export solver support properties in Tuba property sets.

## Acceptance Criteria

- Existing test suite passes after every package.
- Old model JSON loads without new keys.
- New model JSON roundtrips all new keys.
- Existing `RackBay` still works.
- A rack bay is represented as both native assembly and compatibility group.
- A rack bay can carry an IFC-style placement frame, and member nodes still serialize as global coordinates.
- Chained placement frames roundtrip through JSON and resolve to deterministic global transforms.
- IFC export can emit product local placements relative to site/storey/assembly frames.
- IFC import resolves local placement chains into global nodes and preserves frame metadata.
- A pipe support can link to a physical support component and rack member.
- A load transfer can be traced from pipe/support to rack member.
- Route cost model can include added structural cost and support cost.
- Clash engine can compare pipe insulation envelope against support/rack geometry.
- Visualization scene can inspect pipe, support, rack member, assembly, load path, and IFC GUID.
- IFC export can emit stable GUIDs and property sets for pipe, insulation, rack, support, and load path.
- BCF export can reference IFC GUIDs where available.
- Index benchmarks meet agreed gates.
- Code_Aster studies produce traceable analysis mesh metadata.
- Thermal expansion results can be projected into deformed geometry states.
- Deformed clash detection can find clashes that do not exist in the cold geometry.
- Bend deformation uses generated solver mesh nodes where available.
- Visual deformed shape and physical deformed clash use separate scale controls.

## Test Plan

Unit tests:

- `EntityRecord` serialization.
- `PlacementFrame` serialization, frame composition, cycle detection, and point/vector transforms.
- `PlacementAssignment` serialization and duplicate object-placement validation.
- `ExternalIdentity` registry lookup and duplicate detection.
- `ModelRelationship` serialization and adjacency indexes.
- `Port` serialization and connection validation.
- `Assembly` serialization and group compatibility.
- `SupportComponent` serialization.
- `LoadTransfer` serialization and rollup.
- `IfcMappingRegistry` mapping lookup.

Integration tests:

- old JSON fixture loads and reserializes.
- new model fixture roundtrips.
- rack bay creates assembly, group, members, ports, and relationships.
- support component attaches to rack member and pipe support.
- load path report uses relationship graph.
- clash engine uses insulation and rack/support envelopes.
- route optimizer evaluates detour versus structural addition.
- visualization scene includes assemblies, ports, relationships, load paths, and IFC GUIDs.
- IFC export/import preserves stable identity and custom property sets.
- IFC export/import preserves placement hierarchy where supported and resolves geometry to the same global points.
- BCF issue export references involved IFC GUIDs.
- Code_Aster export study writes mesh source mapping.
- Mock solver results create a `ResultState`.
- Hot load case creates deformed envelopes.
- Deformed clash check reports an operating clash absent from cold state.
- Route objective can score cold and operating/deformed clashes separately.

Benchmark tests:

- index rebuild thresholds.
- relationship lookup thresholds.
- broadphase candidate reduction.
- scene build thresholds.
- IFC export thresholds.

## Open Decisions

1. Whether `Element` should keep a free-form `type` string or move to an enum-like validated type registry.
2. Whether `Port` positions should be absolute only or allow local placement relative to owner.
3. Whether `SupportComponent` should become an `Element` subtype or a separate physical component.
4. Whether all relationships should be generic `ModelRelationship` or some should become typed dataclasses.
5. Whether IFC export should target IFC4 initially or move to IFC4.3 once IfcOpenShell project support is stable for our needed entities.
6. Whether to persist indexes or always rebuild them lazily.
7. Whether bSDD URIs should be bundled in static mappings or optional remote lookup.
8. Whether element-local frames should be persisted for all elements or computed on demand from geometry plus orientation metadata.
9. Whether imported IFC placements should always create `PlacementFrame` records or only when the placement is non-identity/nontrivial.
10. Whether route-local authoring frames should be persisted by default or only captured when an agent/user explicitly names them.

## Reference Sources

- buildingSMART IFC overview: https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/
- buildingSMART IFC technical intro: https://technical.buildingsmart.org/standards/ifc/
- buildingSMART bSDD overview: https://www.buildingsmart.org/users/services/buildingsmart-data-dictionary/
- IFC 4.3 `IfcBeam`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcBeam.htm
- IFC 4.3 `IfcElementAssembly`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcElementAssembly.htm
- IFC 4.3 `IfcDistributionPort`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcDistributionPort.htm
- IFC 4.3 `IfcStructuralAnalysisModel`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcStructuralAnalysisModel.htm
- IFC 4.3 `IfcLocalPlacement`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcLocalPlacement.htm
- IFC 4.3 `IfcAxis2Placement3D`: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcAxis2Placement3D.htm
