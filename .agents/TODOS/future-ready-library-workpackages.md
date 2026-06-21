# Future-Ready Tuba Library Workpackages

## Purpose

This roadmap turns the architecture review into executable workpackages. It covers more than clash detection: typed attributes, patch-first generation, route planning, costs, rack modules, physical properties, IFC/BOM export, load paths, rules, and performance.

The direction is to deepen the existing architecture, not replace it. `TubaModel` remains the compact solver graph. New modules add semantic intent, adapters, and optimization interfaces around it.

## Execution Strategy

- Build foundation modules first: entity refs, typed attributes, schema roundtrip, and model indexes.
- Keep generated model changes behind `ModelPatch` / `ModelTransaction`.
- Let adapters project semantic data into geometry, clash, solver loads, IFC, BOM, and visualization.
- Keep every workpackage independently testable.
- Avoid coupling routing and optimization to IFC export/import.

## Milestones

| Milestone | Outcome | Workpackages |
| --- | --- | --- |
| M0 | Planning baseline | WP00 |
| M1 | Semantic model foundation | WP01, WP02, WP03 |
| M2 | Physical envelope and clash foundation | WP04, WP05 |
| M3 | Route planning and cost optimization | WP06, WP07, WP08 |
| M4 | Modular rack construction | WP09, WP10 |
| M5 | Quantities, exports, and load paths | WP11, WP12, WP13 |
| M6 | Rules engine and scale readiness | WP14, WP15 |

## Dependency Graph

```text
WP00
  -> WP01 Entity refs and IDs
      -> WP02 Typed attributes and specs
          -> WP04 Physical properties and envelopes
              -> WP05 Clash interface
              -> WP11 Quantity, cost, weight, wind
          -> WP09 Rack assemblies
      -> WP03 Patch-first generation
          -> WP06 RoutePlan
          -> WP09 Rack assemblies
  -> WP15 Model indexes

WP06 RoutePlan
  -> WP07 RouteCostModel
      -> WP08 Planner seam and network optimization

WP09 Rack assemblies
  -> WP10 Geometry/profile adapter
      -> WP12 IFC/BOM export
      -> WP13 Load-path analysis

WP05, WP07, WP11, WP13
  -> WP14 Rules/compliance engine
```

## WP00 - Architecture Baseline And Vocabulary

**Goal:** Make the architecture decisions durable so future agents do not re-litigate the same questions.

**Inputs:**

- `.agents/SPECS/pipe-autorouting.md`
- `.agents/DECISIONS/pipe-autorouting.md`
- `.agents/SPECS/clash-detection-ifc.md`
- `.agents/DECISIONS/clash-detection-ifc.md`
- Architecture review report in OS temp directory

**Deliverables:**

- Consolidated architecture overview in `docs/architecture.md` or `.agents/SPECS/future-ready-library-architecture.md`.
- Domain vocabulary for: entity ref, attribute, assembly, route plan, rack module, physical envelope, quantity, clash, load path.
- Coordinate convention decision, especially vertical axis and IFC mapping.

**Acceptance Criteria:**

- New terms are defined once and reused by later specs.
- The doc states that IFC is an adapter, not the internal clash or routing interface.
- The doc states that `TubaModel` remains the solver graph.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## WP01 - Entity References And Stable IDs

**Goal:** Introduce stable references so results and attributes can target elements, obstacles, supports, groups, routes, and assemblies.

**Dependencies:** WP00.

**Deliverables:**

- `EntityRef` type.
- Stable ID strategy for supports and future assemblies.
- Ref parsing and formatting.
- Model lookup helpers.
- Tests for valid and invalid refs.

**Relevant Current Files:**

- `tuba/model.py`
- `tuba/patches.py`
- `tuba/fragments.py`
- `tuba/schema.py`

**Acceptance Criteria:**

- Refs can identify `element:pipe_str_0`, `obstacle:equipment_box`, `support:<id>`, `group:rack_A`, `route:P-100`, and `assembly:rack_bay_01`.
- Refs roundtrip through JSON.
- Existing public model APIs keep working.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_entity_refs -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## WP02 - Typed Attributes And Specs

**Goal:** Give non-geometry facts a typed home instead of spreading them across metadata dicts.

**Dependencies:** WP01.

**Deliverables:**

- `AttributeDefinition`.
- `AttributeAssignment`.
- Attribute store on or beside `TubaModel`.
- Typed specs for insulation, cladding, cost codes, system/line identity, route intent, rack zone, and provenance.
- Schema and roundtrip support.
- Inheritance rules for group -> route -> element, with explicit override behavior.

**Example Specs:**

- `InsulationSpec`
- `CladdingSpec`
- `CostRateSpec`
- `RouteIntentSpec`
- `RackZoneSpec`

**Acceptance Criteria:**

- `insulation.spec` can be assigned to a line group and resolved for every pipe element in that group.
- Unknown but schema-valid attributes survive `to_dict()` / `from_dict()`.
- Invalid units or target kinds produce clear validation errors.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_attributes tests.test_schema -v
```

## WP03 - Patch-First Generated Changes

**Goal:** Make `ModelPatch` / `ModelTransaction` the canonical generated-change interface.

**Dependencies:** WP01.

**Deliverables:**

- Patch operations for catalog entries, attributes, groups/assemblies, and route application.
- Builder adapter that can produce a patch before mutation.
- Fragment placement that is fully represented by a patch.
- Dry-run and diff-friendly patch serialization.
- Transaction diagnostics and rollback tests.

**Relevant Current Files:**

- `tuba/builder.py`
- `tuba/patches.py`
- `tuba/fragments.py`
- `tuba/routing/adapter.py`

**Acceptance Criteria:**

- Generated scripts can create a model change without mutating the model first.
- Patch validation catches bad node refs, bad section refs, and invalid attributes.
- Existing builder usage remains supported.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patches tests.test_fragments tests.test_tuba_core -v
```

## WP04 - Physical Properties And Envelopes

**Goal:** Compute physical derived properties from geometry and typed attributes in one module.

**Dependencies:** WP02.

**Deliverables:**

- Effective OD/radius for clash and routing.
- Mass per meter including pipe, fluid placeholder, insulation, and cladding.
- Projected wind diameter.
- Surface area and volume quantities.
- Cost basis hooks.
- Tests for bare pipe, insulated pipe, cladded pipe, and overridden specs.

**Acceptance Criteria:**

- Insulation thickness affects clash/routing envelope.
- Insulation density affects mass per meter.
- Cladding affects wind diameter and mass per meter.
- One implementation is reused by routing, clash, solver load generation, and quantity/cost modules.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_physical_properties -v
```

## WP05 - Clash Detection Interface And IFC Adapter

**Goal:** Add the clash module defined in `.agents/SPECS/clash-detection-ifc.md`.

**Dependencies:** WP01, WP04.

**Deliverables:**

- `tuba.clash.types`
- `tuba.clash.envelopes`
- `TrimeshClashEngine`
- Compatibility wrapper for `PipingCollisionChecker`
- Optional IFC review export adapter
- JSON/Markdown clash report serialization

**Acceptance Criteria:**

- Structured clash results include left/right refs, severity, distance/penetration when available, and diagnostics.
- Insulated pipe envelope can turn a bare-pipe clear case into a clash.
- IFC remains an exchange adapter, not the internal routing check.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_collision tests.test_clash_engine tests.test_ifc -v
```

## WP06 - RoutePlan Module

**Goal:** Introduce a route plan between route candidate geometry and model mutation.

**Dependencies:** WP03, WP04.

**Deliverables:**

- `RoutePlan` type with centerline, bends, supports, rack attachments, added structure placeholders, and provenance.
- Conversion from existing `PipeRouteCandidate` to `RoutePlan`.
- Conversion from `RoutePlan` to `ModelPatch`.
- Route plan JSON serialization.

**Relevant Current Files:**

- `tuba/routing/types.py`
- `tuba/routing/adapter.py`
- `tuba/routing/astar.py`

**Acceptance Criteria:**

- A route can be evaluated, costed, reported, and compared without mutating `TubaModel`.
- Applying a route plan produces the same model elements as the current route adapter for simple cases.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_route_plan tests.test_routing_adapter -v
```

## WP07 - RouteCostModel

**Goal:** Centralize route economics and engineering scoring before model mutation.

**Dependencies:** WP04, WP06.

**Deliverables:**

- `RouteCostModel` interface.
- Cost terms for length, bends, vertical travel, support count/type, rack attachment, added structure, insulation, cladding, and clash penalties.
- Cost breakdown with units and source refs.
- Adapters for cheap routing score and solver-loop score.

**Acceptance Criteria:**

- Detour versus new support/rack structure can be represented in one cost breakdown.
- Insulation cost/weight can affect route selection.
- Existing `RoutingCostWeights` maps into the new cost model for compatibility.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_route_cost_model tests.test_routing_solver_loop -v
```

## WP08 - Planner Seam And Network Optimization

**Goal:** Make route search replaceable and improve multi-pipe optimization beyond greedy order.

**Dependencies:** WP06, WP07, WP15.

**Deliverables:**

- Planner interface for single-pipe and network routing.
- Current A* as the first adapter.
- Search state that includes cell, incoming direction, straight-run length, and optional lane/support state.
- Network conflict repair or backtracking adapter.
- Benchmark cases for multiple pipes.

**Acceptance Criteria:**

- Existing `GridRouter` behavior remains available.
- `NetworkRouteRequest.max_reroute_attempts` is either implemented or removed from the public promise.
- Multi-pipe conflicts can trigger replan attempts.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_astar tests.test_routing_network -v
```

## WP09 - Rack Assemblies And Construction Modules

**Goal:** Promote flattened groups into first-class construction assemblies.

**Dependencies:** WP01, WP02, WP03.

**Deliverables:**

- `AssemblyInstance` or strengthened group interface.
- `RackModule`, `RackBay`, `RackGrid`, and rack level concepts.
- Attachment points for pipe supports and routing lanes.
- Rack construction templates producing `ModelPatch`.
- Rack attributes for zone, capacity, level, cost code, and revision.

**Acceptance Criteria:**

- A rack bay can be generated as a reusable module.
- Rack identity survives model serialization.
- Generated pipe supports can reference rack attachment points.
- Existing solver export still sees ordinary nodes/elements.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rack_assemblies tests.test_fragments -v
```

## WP10 - Geometry/Profile Adapter

**Goal:** Stop each downstream module from re-implementing section shape and geometry logic.

**Dependencies:** WP04, WP09.

**Deliverables:**

- Geometry/profile adapter seam for visual mesh, collision envelope, IFC profile, quantity shape, and section area.
- Adapters for pipe, bend approximation, I-beam, rectangular, bar, cable.
- Explicit limitations for bends and mesh accuracy.

**Relevant Current Files:**

- `tuba/visualizer/pipeline.py`
- `tuba/external/ifc.py`
- `tuba/geometry/collision.py`
- `tuba/sections/catalog.py`

**Acceptance Criteria:**

- Adding a new construction shape does not require separate edits across visualizer, IFC, collision, and quantity code.
- Existing visualizer and IFC tests still pass.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualizer_scenes tests.test_ifc tests.test_collision -v
```

## WP11 - Quantity, Cost, Weight, And Wind Loads

**Goal:** Turn physical properties and attributes into engineering/economic quantities.

**Dependencies:** WP02, WP04, WP07, WP10.

**Deliverables:**

- Quantity takeoff module.
- Cost adapter using rates for pipe, insulation, cladding, supports, steel, coatings, clamps, bolts, and waste factors.
- Weight report by system, route, assembly, and element.
- Wind load adapter using projected diameter and load case data.
- JSON/CSV report output.

**Acceptance Criteria:**

- Insulation thickness/material produces mass, cost, and wind projected diameter.
- Route cost can include insulation and structure costs.
- BOM output can group by route, rack assembly, and material.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_quantities tests.test_route_cost_model -v
```

## WP12 - IFC And BOM Export Upgrade

**Goal:** Preserve Tuba semantics in downstream exchange files.

**Dependencies:** WP02, WP09, WP10, WP11.

**Deliverables:**

- IFC property sets for route IDs, assembly IDs, insulation specs, cost codes, quantities, and clash report refs.
- IFC assembly/group export for rack modules.
- BOM CSV/JSON export.
- Diagnostics for geometry export failures.
- Optional BCF issue export for clashes.

**Acceptance Criteria:**

- IFC export no longer silently drops geometry errors.
- Route, rack, insulation, and quantity metadata can be inspected after export.
- Existing IFC roundtrip tests still pass.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ifc tests.test_quantities -v
```

## WP13 - Load-Path Analysis For Pipe Supports And Racks

**Goal:** Connect pipe support reactions to rack beams, columns, and baseplates.

**Dependencies:** WP09, WP11, solver-loop outputs.

**Deliverables:**

- Support-to-rack association model.
- Reaction transfer from pipe supports to rack elements.
- Rack utilization checks.
- Baseplate/foundation load placeholders.
- Reports for governing rack members and support reactions.

**Acceptance Criteria:**

- A pipe support attached to a rack member can transfer a vertical/lateral load.
- Rack member utilization can be reported from solver or proxy load cases.
- Missing support-to-rack associations are diagnostics, not silent assumptions.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_load_path tests.test_rack_assemblies -v
```

## WP14 - Rules And Compliance Engine

**Goal:** Centralize engineering rules that are not just solver stress calculations.

**Dependencies:** WP05, WP07, WP11, WP13.

**Deliverables:**

- Rule interface for checks and diagnostics.
- Rules for support spacing, sag proxy, clearance, constructability, slope, rack occupancy, route bend limits, clash, and code-specific pipe checks.
- Existing ASME B31.3 evaluator adapter.
- Rule report JSON/Markdown.

**Acceptance Criteria:**

- Rules can run without Code_Aster when only proxy data is needed.
- Solver-backed rules can attach compliance ratios when results are available.
- Route reports and model reports can include rule diagnostics.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rules tests.test_validation tests.test_routing_report -v
```

## WP15 - Model Indexes And Performance Benchmarks

**Goal:** Make optimization loops performant without changing public interfaces.

**Dependencies:** Can start after WP01; supports all later workpackages.

**Deliverables:**

- Spatial node index behind `find_node_by_point`.
- Fast element ID allocation without rebuilding sets per element.
- EntityRef lookup indexes.
- Optional broad-phase spatial index for clash candidates.
- Benchmarks for routing grids, patch application, clash checks, and network routing.

**Acceptance Criteria:**

- Existing tests pass without public interface changes.
- Moderate generated models apply patches faster than current full-snapshot workflow or have documented limits.
- Benchmark outputs are saved under `.benchmarks/`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_indexes tests.test_patches -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## Suggested First Implementation Slice

Start with a small vertical slice that proves the architecture:

1. WP01: `EntityRef` for elements and obstacles.
2. WP02: minimal `InsulationSpec` and assignment.
3. WP04: effective pipe envelope calculation.
4. WP05: structured clash result using the effective envelope.
5. WP06: route candidate to route plan for one pipe.
6. WP07: cost breakdown includes length and insulation cost.

This slice proves that one semantic attribute can feed routing, clash, cost, and reports without hardcoding the same concept in four places.

## Parallelization Plan

Independent tracks after WP01/WP02:

- Track A: WP03 patch-first generation.
- Track B: WP04/WP05 physical envelope and clash.
- Track C: WP15 indexes and benchmarks.

Independent tracks after WP09/WP10:

- Track D: WP11 quantity/cost/wind.
- Track E: WP12 IFC/BOM export.
- Track F: WP13 load-path analysis.

## Final Verification Gate

Before considering the architecture expansion complete:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Required manual demos:

- Build a rack assembly.
- Assign insulated pipe routes.
- Route around obstacles using insulation envelope.
- Compare route alternatives by cost.
- Export IFC and BOM with route/rack/insulation metadata.
- Produce clash and rule reports.

