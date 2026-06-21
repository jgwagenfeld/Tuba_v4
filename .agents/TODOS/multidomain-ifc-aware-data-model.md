# Multidomain IFC-Aware Data Model Roadmap

## Purpose

Implement the data-model changes required for Tuba to handle piping, support structures, rack assemblies, load paths, routing, cost optimization, clash review, visualization, IFC export, and BCF coordination as one coherent engineering model.

This roadmap is intentionally package-based. Each package must be independently testable and must keep existing tests green before the next package starts.

## Execution Rules

- Keep IFC as adapter and mapping vocabulary, not internal source of truth.
- Preserve old JSON compatibility throughout.
- Use `ModelPatch` for all generated model mutations.
- Add tests before or with every package.
- Run focused tests after each package.
- Run full Python test suite after every three packages or after shared model changes.
- Add benchmarks before optimizing, then measure deltas.
- Do not remove `groups` or current `Support` until replacement paths are proven.

## Status Legend

- `Pending`: not started.
- `In Progress`: active package.
- `Complete`: implemented and verified.
- `Blocked`: cannot continue without external decision.

## Milestones

| Milestone | Outcome | Packages |
| --- | --- | --- |
| MD0 | Compatibility baseline and decisions frozen | MD00, MD01 |
| MD1 | Stable identity and external IDs | MD02, MD03 |
| MD2 | Relationships and ports | MD04, MD05 |
| MD3 | Assemblies and physical supports | MD06, MD07 |
| MD4 | Load transfer and structural cost | MD08, MD09 |
| MD5 | IFC-aware mapping layer | MD10, MD11, MD12 |
| MD6 | Visualization, issues, and agents | MD13, MD14, MD15 |
| MD7 | Performance and migration hardening | MD16, MD17, MD18 |
| MD8 | Code_Aster result-state and deformed clash | MD21, MD22, MD23, MD24 |
| MD9 | Documentation and release readiness | MD19, MD20 |

## Dependency Graph

```text
MD00 -> MD01 -> MD02 -> MD03
              -> MD04 -> MD05
                      -> MD06 -> MD07 -> MD08 -> MD09
MD03 + MD04 + MD06 -> MD10 -> MD11 -> MD12
MD04 + MD05 + MD08 -> MD13 -> MD14 -> MD15
MD02 + MD04 + MD06 -> MD16 -> MD17 -> MD18
all -> MD19 -> MD20
MD01 + MD16 -> MD21 -> MD22 -> MD23 -> MD24
```

## Package Checklist

| ID | Package | Status | Verification Gate |
| --- | --- | --- | --- |
| MD00 | Baseline fixtures and compatibility audit | Pending | current full suite and fixture inventory |
| MD01 | Schema version and migration hooks | Pending | old JSON compatibility tests |
| MD02 | Entity records and stable metadata | Pending | entity record roundtrip tests |
| MD03 | External identities and IFC GUID registry | Pending | stable GUID export tests |
| MD04 | Generic model relationship graph | Pending | relationship adjacency/index tests |
| MD05 | Native ports and connection validation | Pending | port/connectivity tests |
| MD06 | Native assemblies with group compatibility | Pending | rack group and assembly roundtrip tests |
| MD07 | Physical support components | Pending | support component attachment tests |
| MD08 | Load transfer model | Pending | support-to-rack load path tests |
| MD09 | Structural and support-aware cost model | Pending | detour versus structure cost tests |
| MD10 | Typed spec/property-set registry | Pending | generic spec and property-set tests |
| MD11 | IFC mapping registry and export profiles | Pending | mapping lookup and diagnostics tests |
| MD12 | IFC exporter upgrade for piping, racks, supports | Pending | enriched IFC roundtrip/property tests |
| MD13 | Clash/rule/BCF relationship integration | Pending | issue to relationship to BCF tests |
| MD14 | Visualization scene model integration | Pending | scene objects for ports/assemblies/load paths |
| MD15 | Agent patch operations for new model features | Pending | patch preview and transaction tests |
| MD16 | Model indexes and cache invalidation | Pending | index correctness and speed tests |
| MD17 | Spatial indexes and broadphase performance | Pending | clash broadphase benchmark tests |
| MD18 | Large-model benchmarks and performance budgets | Pending | benchmark report gates |
| MD19 | Migration tools and docs | Pending | migration fixture tests |
| MD20 | Release readiness and examples | Pending | examples, docs, and full suite |
| MD21 | Code_Aster analysis study and mesh provenance | Pending | study export and mesh mapping tests |
| MD22 | Serializable result states | Pending | result-state roundtrip tests |
| MD23 | Physical geometry states and deformed envelopes | Pending | deformed envelope tests |
| MD24 | Operating/deformed clash integration | Pending | thermal expansion clash tests |

Detailed implementation packages for MD21-MD24 are tracked in `.agents/TODOS/code-aster-operating-state-clash.md`.

## MD00 - Baseline Fixtures And Compatibility Audit

**Goal:** Freeze current behavior before changing the data model.

**Tasks:**

- Inventory current JSON schema fields.
- Add or identify canonical fixtures:
  - pipe-only model
  - insulated pipe model
  - pipe plus rack model
  - pipe plus support model
  - route candidate model
  - clash/report model
  - IFC roundtrip model
- Record current serialization behavior.
- Record current `IfcExporter` behavior and limitations.
- Add a compatibility matrix to docs.

**Acceptance Criteria:**

- Existing full suite passes.
- Canonical fixtures are committed or referenced.
- Current unsupported IFC concepts are listed.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## MD01 - Schema Version And Migration Hooks

**Goal:** Make future model changes additive and migratable.

**Tasks:**

- Add explicit `schema_version` to serialized model output.
- Load old models without `schema_version`.
- Add `tuba.migrations` package with no-op migration from legacy to current.
- Add migration diagnostics.
- Add tests for old fixtures and new fixtures.

**Acceptance Criteria:**

- Old fixtures load with empty new collections.
- New serialized output includes schema version.
- Migration hooks are called exactly once during load.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_serialization -v
```

## MD02 - Entity Records And Stable Metadata

**Goal:** Add optional common metadata for all first-class objects without polluting each dataclass.

**Tasks:**

- Add `EntityRecord` dataclass.
- Add `model.entity_records`.
- Add helpers:
  - `set_entity_record(ref, ...)`
  - `get_entity_record(ref)`
  - `entity_name(ref)`
- Extend JSON serialization.
- Add validation for resolvable refs.
- Add `SetEntityRecord` patch operation.

**Acceptance Criteria:**

- Any `EntityRef` can have name, description, tags, status, and provenance.
- Missing records are allowed.
- Records roundtrip through JSON.
- Patch transaction rolls back invalid records.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_entity_records tests.test_patches -v
```

## MD03 - External Identities And IFC GUID Registry

**Goal:** Make IFC GUIDs and other external IDs stable across repeated exports.

**Tasks:**

- Add `ExternalIdentity` dataclass.
- Add `model.external_identities`.
- Add `ExternalIdentityRegistry` or indexed helpers.
- Add `IfcGuidRegistry`:
  - reuse existing GUID for target
  - create deterministic or persisted GUID for new target
  - reject duplicate GUID ownership
- Update IFC exporter to use registry for products it creates.
- Add patch operation `SetExternalIdentity`.

**Acceptance Criteria:**

- Exporting the same model twice reuses object GUIDs.
- Different objects cannot claim the same IFC GUID.
- Imported IFC GUIDs can be attached to native refs.
- BCF export can reference stable IFC GUIDs.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_external_identity tests.test_ifc tests.test_visualization_ifc tests.test_visualization_bcf -v
```

## MD04 - Generic Model Relationship Graph

**Goal:** Make containment, decomposition, support, connectivity, issue links, and provenance explicit.

**Tasks:**

- Add `ModelRelationship` dataclass.
- Add `model.relationships`.
- Add relationship type constants.
- Add helpers:
  - `add_relationship()`
  - `relationships_for_source()`
  - `relationships_for_target()`
  - `relationships_of_type()`
  - `related_entities()`
- Add validation for refs and duplicate relationship IDs.
- Add patch operations `AddRelationship` and `RemoveRelationship`.

**Acceptance Criteria:**

- Relationships roundtrip through JSON.
- Adjacency lookup does not scan every relationship after index build.
- Existing group membership can be represented as relationships without replacing groups.
- Invalid refs fail clearly.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_relationships tests.test_patches -v
```

## MD05 - Native Ports And Connection Validation

**Goal:** Add connection-point topology for pipes, equipment, nozzles, fittings, and supports.

**Tasks:**

- Add `Port` dataclass.
- Add `model.ports`.
- Add helper to create endpoint ports for pipe elements.
- Add `ConnectPorts` patch operation.
- Add compatibility checks:
  - port type
  - system
  - flow direction
  - nominal diameter
  - connection spec
- Add optional override metadata for deliberate mismatches.
- Add IFC mapping notes to port metadata.

**Acceptance Criteria:**

- Pipe endpoints can be resolved as ports.
- Connected ports are represented as relationships.
- Invalid connections fail unless explicit override is supplied.
- Port graph supports route start/end and agent routing contexts.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ports tests.test_routing_adapter -v
```

## MD06 - Native Assemblies With Group Compatibility

**Goal:** Promote racks and support frames from group metadata to native assemblies.

**Tasks:**

- Add `Assembly` dataclass.
- Add `model.assemblies`.
- Add `CreateAssembly` patch operation.
- Update `RackBay.to_patch()` to create:
  - nodes
  - structural elements
  - assembly
  - compatibility group
  - containment/decomposition relationships
  - attachment ports
- Add loader that creates virtual assembly view for legacy rack groups.

**Acceptance Criteria:**

- Existing rack tests still pass.
- New rack bay has an `assembly:rack_A` ref.
- Rack members can be queried by assembly.
- Group compatibility remains intact.
- IFC mapping can see the rack as an assembly.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_assemblies tests.test_load_path tests.test_visualization_racks -v
```

## MD07 - Physical Support Components

**Goal:** Separate solver boundary supports from physical support hardware.

**Tasks:**

- Add `SupportComponent` dataclass.
- Add `model.support_components`.
- Add support component specs:
  - shoe
  - clamp
  - guide
  - spring hanger
  - anchor
  - bracket
- Add relationships:
  - support component supports pipe
  - support component attaches to rack/member
  - solver support represented by support component
- Add `AddSupportComponent` patch operation.
- Add IFC mapping candidates for support hardware.

**Acceptance Criteria:**

- Current `Support` behavior remains unchanged.
- Physical support component can be inspected, costed, visualized, and exported.
- Support component can be attached to rack assembly/member.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_support_components tests.test_visualization_racks -v
```

## MD08 - Load Transfer Model

**Goal:** Make pipe-to-support-to-rack load flow explicit and queryable.

**Tasks:**

- Add `LoadTransfer` dataclass.
- Add `model.load_transfers`.
- Update `analyze_load_paths()` to use:
  - support component relationships
  - assembly attachment ports
  - legacy group attachment metadata fallback
- Add rollups:
  - by support
  - by rack assembly
  - by structural member
  - by load case
- Add `AddLoadTransfer` patch operation.

**Acceptance Criteria:**

- A support reaction can be traced to support component and rack member.
- Legacy rack metadata still works.
- Visualization can draw load path vectors.
- IFC export can include load path property sets.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_load_path tests.test_visualization_racks tests.test_visualization_results -v
```

## MD09 - Structural And Support-Aware Cost Model

**Goal:** Let optimization compare pipe detours against added support/rack structure.

**Tasks:**

- Extend cost specs for:
  - pipe length
  - fittings
  - insulation
  - support components
  - rack members by section/material/length
  - added assembly fixed cost
  - labor/complexity multipliers
- Add route cost terms:
  - added support count
  - new steel length
  - rack utilization penalty
  - clearance violation penalty
  - maintenance access penalty
- Add quantity rollups across pipe and support structure.
- Add tests for detour versus structure tradeoff.

**Acceptance Criteria:**

- Cost breakdown identifies whether cost comes from pipe, insulation, support, or steel.
- Route optimizer can rank alternatives using support/rack costs.
- Quantity takeoff includes support/rack material.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_cost tests.test_quantities tests.test_visualization_costs -v
```

## MD10 - Typed Spec And Property-Set Registry

**Goal:** Move from ad hoc attributes to typed specs with predictable export mapping.

**Tasks:**

- Add base spec protocol:
  - `id`
  - `to_dict`
  - `from_dict`
  - `validate`
  - optional `property_set_name`
- Add generic spec serialization in `model.specs`.
- Add specs:
  - `CladdingSpec`
  - `SupportSpec`
  - `RackSpec`
  - `ConnectionSpec`
  - `CostSpec`
  - `SystemSpec`
- Add `AssignSpec` patch operation.
- Add namespaced property set mapping.

**Acceptance Criteria:**

- New specs roundtrip.
- Insulation remains compatible.
- Unknown specs remain preserved but flagged as generic.
- Export mapping can enumerate all property sets for an entity.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_specs tests.test_attributes tests.test_patches -v
```

## MD11 - IFC Mapping Registry And Export Profiles

**Goal:** Centralize all IFC decisions instead of scattering them through `IfcExporter`.

**Tasks:**

- Add `tuba.external.ifc_mapping`.
- Add:
  - `IfcEntityMapping`
  - `IfcPropertyMapping`
  - `IfcRelationshipMapping`
  - `IfcExportProfile`
  - `IfcMappingRegistry`
- Define default mappings:
  - pipe segment
  - pipe fitting
  - pipe port
  - insulation
  - rack assembly
  - beam/column/member
  - support component
  - load transfer
  - clash/rule issue references
- Add strict and permissive export modes.
- Add diagnostics object for unmapped concepts.

**Acceptance Criteria:**

- Exporter asks registry for mapping decisions.
- Missing mapping produces diagnostic, not silent loss.
- Tests cover every native first-class concept.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc_mapping tests.test_ifc -v
```

## MD12 - IFC Exporter Upgrade For Piping, Racks, Supports

**Goal:** Emit a coordination-quality IFC with stable identity and support-structure semantics.

**Tasks:**

- Refactor `IfcExporter` around mapping registry and GUID registry.
- Export pipe segments with standard pipe properties.
- Export insulation as:
  - property set by default
  - optional `IfcCovering` geometry in enriched profile
- Export rack assemblies as `IfcElementAssembly`.
- Export rack members as `IfcBeam`, `IfcColumn`, or `IfcMember`.
- Export support components as best-fit IFC component or proxy fallback.
- Export custom Tuba property sets.
- Add export diagnostics.
- Keep importer compatibility.

**Acceptance Criteria:**

- Existing IFC tests pass.
- Stable GUIDs are reused.
- Rack assembly decomposes into members.
- Support structure metadata survives export inspection.
- Unsupported support component types are explicit diagnostics.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc tests.test_ifc_mapping tests.test_visualization_ifc -v
```

## MD13 - Clash, Rule, And BCF Relationship Integration

**Goal:** Connect issues to first-class relationships and external identity.

**Tasks:**

- Represent clashes with `interferes_with` relationships.
- Attach issue refs to involved objects.
- Add issue property mappings.
- Ensure BCF export uses IFC GUIDs where available.
- Add rule issue relationships.
- Add import behavior for BCF comments/status mapped back to issues.

**Acceptance Criteria:**

- Clash issue can find involved pipe/support/rack objects.
- BCF topic can reference IFC GUID and Tuba `EntityRef`.
- Rule issues are included in same issue workflow.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_clash_engine tests.test_visualization_issues tests.test_visualization_bcf tests.test_visualization_rules -v
```

## MD14 - Visualization Scene Model Integration

**Goal:** Make new data model visible and inspectable.

**Tasks:**

- Add scene metadata for:
  - entity records
  - external identities
  - relationships
  - ports
  - assemblies
  - support components
  - load transfers
- Add overlays:
  - ports/connectivity
  - assembly membership
  - support attachments
  - load path
  - IFC identity
- Add viewer filters for pipes, supports, racks, ports, issues, load paths.

**Acceptance Criteria:**

- Selecting a pipe shows route, ports, insulation, supports, load path, and IFC GUID.
- Selecting a rack member shows assembly, loads, cost, and IFC GUID.
- Selecting a support component shows supported pipe and attached structure.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_racks tests.test_visualization_ifc tests.test_visualization_results -v
npm --prefix viewer test
```

## MD15 - Agent Patch Operations For New Model Features

**Goal:** Let agents propose support/rack/IFC-aware model changes without direct mutation.

**Tasks:**

- Add patch operations for all new entities.
- Update patch schema validation.
- Update live preview.
- Update agent workspace examples:
  - add support component
  - add rack assembly
  - connect ports
  - assign IFC external identity
  - add load transfer
- Add safety checks for invalid graph mutations.

**Acceptance Criteria:**

- Agent can propose a rack/support change as `ModelPatch`.
- Preview shows scene diff before mutation.
- Invalid refs fail before mutation.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_python_workspace tests.test_visualization_live_preview tests.test_patches -v
```

## MD16 - Model Indexes And Cache Invalidation

**Goal:** Prevent data-model growth from making normal operations scan-heavy.

**Tasks:**

- Add `ModelIndex` object.
- Add lazy rebuild and revision checks.
- Add indexes for:
  - elements by ID
  - supports by ID
  - support components by ID
  - ports by owner
  - relationships by source/target/type
  - assemblies by member
  - external identities
  - groups by member
- Add transaction invalidation.
- Replace high-frequency scans with index lookups.

**Acceptance Criteria:**

- Index returns same results as scan implementation.
- Rebuild is lazy and deterministic.
- Mutations invalidate indexes.
- Relationship lookup by entity is bounded by local adjacency, not total relationship count.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_index tests.test_relationships tests.test_load_path -v
```

## MD17 - Spatial Indexes And Broadphase Performance

**Goal:** Make clash, routing, and envelope queries scale with model size.

**Tasks:**

- Add AABB generation for:
  - bare elements
  - insulation envelope
  - clearance envelope
  - support components
  - rack members
  - obstacles
- Add pure Python/Numpy broadphase index.
- Optionally use accelerated backend when installed.
- Add invalidation by model revision and envelope options.
- Update clash engine to use spatial broadphase where possible.
- Update routing obstacle inflation to reuse envelope cache.

**Acceptance Criteria:**

- Broadphase candidate count is much smaller than all-pairs on fixture.
- Results match current clash engine for small fixtures.
- Missing optional acceleration does not break tests.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_spatial_index tests.test_clash_engine tests.test_pipe_autorouting -v
```

## MD18 - Large-Model Benchmarks And Performance Budgets

**Goal:** Establish measurable performance gates for future work.

**Tasks:**

- Add benchmark model generator:
  - pipe grid
  - rack grid
  - supports
  - ports
  - relationships
  - external IDs
- Add benchmark command/module.
- Capture timings:
  - load
  - serialize
  - index rebuild
  - relationship query
  - physical properties pass
  - broadphase query
  - scene build
  - IFC export smoke
- Add JSON benchmark report.
- Add non-flaky smoke thresholds for CI.

**Acceptance Criteria:**

- Benchmarks run locally with repeatable output.
- CI-safe smoke benchmark avoids excessive runtime.
- Performance regressions can be compared across commits.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_benchmarks -v
.\.venv\Scripts\python.exe -m tuba.benchmarks multidomain --size smoke
```

## MD19 - Migration Tools And Docs

**Goal:** Help existing models move to the new structure without manual repair.

**Tasks:**

- Add migration docs:
  - groups to assemblies
  - supports to support components
  - ad hoc attributes to typed specs
  - IFC GUID persistence
- Add CLI or script for migration preview.
- Add migration diagnostics:
  - missing support attachments
  - rack groups without attachment points
  - duplicate names
  - unresolved refs
- Add dry-run mode.

**Acceptance Criteria:**

- Existing sample models migrate without behavior changes.
- Migration preview reports changes before writing.
- Docs show old and new examples.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_migrations -v
```

## MD20 - Release Readiness And Examples

**Goal:** Ship a coherent developer-facing and user-facing model update.

**Tasks:**

- Update `docs/future_ready_architecture.md`.
- Add example scripts:
  - pipe plus insulation
  - pipe plus rack
  - support component with load path
  - IFC export with rack/support property sets
  - route alternative comparing detour versus structure
- Update README snippets if needed.
- Run full test suite and viewer tests.
- Produce final implementation report.

**Acceptance Criteria:**

- Examples execute.
- Docs describe the new model clearly.
- Full test suite passes.
- Viewer tests pass.
- IFC export smoke passes where IfcOpenShell is installed.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm --prefix viewer test
npm --prefix viewer run build
```

## Performance Design Checklist

Use this checklist before marking MD16-MD18 complete:

- [ ] No hot path scans all elements when an index can answer by ID.
- [ ] No hot path scans all relationships for a single entity query.
- [ ] No route candidate loop exports IFC.
- [ ] No clash broadphase uses all-pairs for large model fixtures.
- [ ] Physical properties cache is invalidated by model revision.
- [ ] Geometry assets are keyed by reusable section/material/envelope descriptors.
- [ ] IFC GUID registry lookup is O(1) after index build.
- [ ] Serialization avoids embedding duplicate large derived data.
- [ ] Benchmarks include model sizes above normal unit-test scale.
- [ ] Optional acceleration backends have pure-Python fallbacks.

## Final Verification Gate

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm --prefix viewer test
npm --prefix viewer run build
```

Expected result:

- Python suite passes.
- Viewer suite passes.
- Viewer build succeeds.
- Benchmark smoke report generated.
- Existing IFC tests remain green.

## MD21 - Code_Aster Analysis Study And Mesh Provenance

**Goal:** Make Code_Aster input generation traceable back to native Tuba entities.

**Why this matters:** Code_Aster uses an analysis mesh, not only the native model graph. Pipe bends are already discretized into intermediate nodes and segment elements. Those generated mesh nodes must be retained if we want accurate deformed visualization and deformed clash detection.

**Tasks:**

- Add `AnalysisStudy` dataclass.
- Add `AnalysisMesh` dataclass.
- Update `CodeAsterSolver.export_study()` to optionally return or write an analysis study manifest.
- Update `_write_mail()` to record:
  - generated mesh node IDs
  - generated mesh element IDs
  - native `EntityRef` source for every mesh element
  - parametric position for intermediate bend nodes
  - Code_Aster group membership
- Persist study manifest beside `.mail`, `.comm`, and `.export`.
- Add tests using export-only mode, not requiring Code_Aster execution.

**Acceptance Criteria:**

- Every generated Code_Aster mesh node has a source record.
- Every generated Code_Aster mesh element maps to a native element.
- Bend intermediate nodes are not lost after export.
- Existing solver export tests remain compatible.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study tests.test_routing_solver_loop -v
```

## MD22 - Serializable Result States

**Goal:** Convert in-memory `FEAResults` into a traceable, serializable result state.

**Tasks:**

- Add `ResultState` dataclass.
- Add converter:
  - `result_state_from_fea_results(model, study, results)`
  - `fea_results_from_result_state(model, result_state)`
- Include:
  - load case
  - model revision
  - solver name
  - result file refs
  - native node results
  - generated mesh node results where available
  - element forces/stresses
  - reactions
- Update Code_Aster parser to preserve generated solver mesh node displacements when CSV/MED provides them.
- Add JSON roundtrip tests.

**Acceptance Criteria:**

- `FEAResults` can be converted to `ResultState` without losing native node results.
- Generated bend node displacements can be preserved when available.
- Result state refuses to apply to the wrong model revision unless explicitly overridden.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_result_state tests.test_visualization_results -v
```

## MD23 - Physical Geometry States And Deformed Envelopes

**Goal:** Turn solver displacement into reusable physical geometry for clash, routing, visualization, and review.

**Tasks:**

- Add `GeometryState` dataclass.
- Add deformed point projection:
  - native endpoints
  - generated bend mesh nodes
  - interpolation fallback
- Add `DeformedEnvelope` builder for:
  - bare pipe
  - insulation
  - clearance
  - maintenance
  - wind
  - rack/support members where solved
- Add cache keys based on:
  - model revision
  - result state ID
  - load case
  - envelope type
  - safety factor
- Enforce separate controls:
  - visual deformation scale
  - physical clash deformation scale
  - safety factor

**Acceptance Criteria:**

- Physical deformed geometry uses scale `1.0` by default.
- Visual scene can still use large deformation scales.
- Deformed envelope bounds include insulation and clearance.
- Bends use generated solver mesh nodes where present.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_geometry_states tests.test_visualization_results tests.test_visualization_envelopes -v
```

## MD24 - Operating/Deformed Clash Integration

**Goal:** Detect clashes that exist only after thermal expansion, pressure, gravity, support movement, or nonlinear contact.

**Tasks:**

- Update structured `TrimeshClashEngine` to accept:
  - cold geometry state
  - operating/deformed geometry state
  - result state
  - envelope type
- Return `ClashResult` metadata:
  - geometry state
  - load case
  - displacement source
  - cold distance
  - operating distance
  - newly created by deformation flag
- Update routing `ClashObjective` to use the structured engine instead of the older `PipingCollisionChecker`.
- Add thermal expansion fixture:
  - cold geometry has no clash
  - hot/deformed geometry clashes with obstacle or rack/support member
- Add viewer issue overlay for operating-only clashes.

**Acceptance Criteria:**

- A hot load case can produce an operating clash absent from cold state.
- Clash report distinguishes cold clash from operating/deformed clash.
- Route optimizer can penalize operating clashes.
- Viewer can filter by load case and geometry state.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deformed_clash tests.test_clash_engine tests.test_routing_objectives tests.test_visualization_issues -v
npm --prefix viewer test
```
