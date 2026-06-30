# Future-Ready Tuba Architecture

This document summarizes the architecture added for semantic geometry generation, rack assemblies, routing, clash checks, quantities, costs, and rules.

## Core Direction

`TubaModel` remains the compact solver graph: materials, sections, nodes, elements, supports, load cases, obstacles, and groups. Future-facing behavior is layered around that graph through typed refs, attributes, patches, plans, and adapters.

IFC is an exchange adapter, not the internal clash or routing interface. Internal algorithms work against `TubaModel`, `EntityRef`, physical envelopes, route plans, and structured result types. IFC/BOM export consumes those semantics after model data is ready.

Coordinate handling follows IFC placement semantics without making IFC the internal model. Native nodes remain in the model-global Cartesian frame; optional placement frames preserve site, assembly, product, and imported local placements for authoring and exchange.

The next architecture step is to make Tuba explicitly multidomain. Piping and support structure should both be first-class. A rack, support frame, beam, column, clamp, shoe, support reaction, and load-transfer path cannot remain only metadata on a pipe if route optimization is expected to compare detours against added structure.

## Main Layers

1. **Identity:** `EntityRef` provides stable references such as `element:pipe_0`, `support:support_0`, `group:rack_A`, `route:P-100`, and `obstacle:box`.
2. **Semantics:** `InsulationSpec` and `AttributeAssignment` attach non-geometry facts to entities. These facts can influence routing, clash checks, costs, wind loads, and reports without directly changing centerline geometry.
3. **Generated Changes:** `ModelPatch` and `ModelTransaction` are the mutation boundary for generated geometry, semantic specs, groups, and attributes. Transactions rollback on validation failure.
4. **Derived Physics:** `tuba.physical` computes effective diameters, mass per meter, insulation volume, wind diameter, and element quantities from the model and semantic attributes.
5. **Geometry Profiles:** `tuba.geometry.profiles` normalizes section geometry for visualizer, collision, IFC, and quantity consumers.
6. **Clash:** `TrimeshClashEngine` returns structured `ClashResult` objects with entity refs and penetration/distance data. The legacy collision checker now uses the same physical envelope.
7. **Routing:** `RoutePlan` preserves route intent before mutation. `RouteCostModel` evaluates alternatives before applying patches. `PipePlanner` / `AStarPipePlanner` keep search replaceable.
8. **Assemblies:** `RackBay` generates rack construction patches while preserving rack identity, zone attributes, and attachment points in model groups.
9. **Takeoff And Export:** `quantity_takeoff`, `wind_loads`, and BOM export reuse the physical layer and group semantics.
10. **Load Path And Rules:** `analyze_load_paths` maps supports to rack attachment points. `RuleEngine` runs proxy checks such as support spacing and clash-free validation.
11. **Scale:** model-side node and element indexes support faster lookup and ID allocation. Benchmark summaries can be written with `write_model_benchmark_summary`.

## Multidomain Data Model Direction

The IFC-informed native model should add these concepts without replacing the current API in one migration:

1. **Entity Records:** optional common metadata for any `EntityRef`: name, description, tags, status, and provenance.
2. **External Identities:** stable mappings from Tuba refs to IFC GUIDs, BCF topic IDs, and other external system IDs.
3. **Relationships:** first-class `ModelRelationship` records for containment, decomposition, connectivity, support, attachment, load transfer, issue links, classification, and provenance.
4. **Ports:** native connection points for pipe endpoints, equipment nozzles, fittings, rack attachment points, and structural joints.
5. **Assemblies:** rack bays, frames, skids, pipe modules, and support frames as first-class assemblies. Existing `groups` remain compatibility views.
6. **Support Components:** physical support hardware such as shoes, clamps, anchors, brackets, guides, and spring hangers. Existing `Support` remains the solver boundary condition.
7. **Load Transfers:** explicit pipe/support-to-rack/member load paths with load case, force, moment, and degree-of-freedom metadata.
8. **IFC Mapping Registry:** a central mapping layer for IFC entities, property sets, relationships, export profiles, diagnostics, and stable GUID reuse.

This keeps Tuba fast and agent-friendly while making IFC export deliberate and testable.

## Support Structure Implications

Support structure changes the model from:

```text
Pipe -> geometry + material + insulation + route
```

to:

```text
Pipe system
Support and rack system
Connection and attachment graph
Load-transfer graph
Clash and clearance envelopes
Cost and quantity graph
IFC and BCF exchange mapping
```

That distinction matters for future optimization. A route candidate may be cheaper because it avoids a rack extension. Another may be cheaper because it adds a simple support instead of a long detour. The model has to carry both choices as native, queryable, costable objects before geometry is exported.

## Performance Requirements

The multidomain model must include performance work as part of the implementation, not as cleanup later.

Required indexes:

- entity lookup by ID for nodes, elements, supports, support components, ports, and assemblies.
- relationships by source, target, and type.
- ports by owner.
- assemblies and groups by member.
- supports by node and elements by node.
- external identities by native ref and external ID.
- spatial AABB indexes for bare geometry, insulation, clearance, support components, rack members, obstacles, and external context geometry.

Required cache behavior:

- model mutations increment a revision counter.
- indexes rebuild lazily when stale.
- derived physical properties, envelopes, quantities, and geometry assets cache against model revision.
- route optimization never requires IFC export or import in the inner loop.
- IFC export uses deterministic GUID lookup and a model visitor over indexed objects.

The detailed package roadmap is in `.agents/TODOS/multidomain-ifc-aware-data-model.md`; the data-model spec is in `.agents/SPECS/multidomain-ifc-aware-data-model.md`; architecture decisions are recorded in `.agents/DECISIONS/multidomain-ifc-aware-data-model.md`.

## Code_Aster And Deformed Clash Workflow

Code_Aster remains the core solver. The data-model expansion should not replace it; it should make solver input and output traceable enough for optimization, visualization, and clash checks.

### Expansion Aware Autorouting

Hot-line routing needs explicit expansion-loop space, not only clash-free
shortest paths. Tuba treats these routes as candidate generation reviewed
through routing spaces, generated U-loop candidates, reserved envelopes, and
`SolverAcceptanceCriteria` evidence. Today the scorer enforces expansion ratio,
sustained ratio, and anchor reaction; nozzle, displacement, and clearance limits
remain typed review/future fields. Solver execution may be export-only or run
locally; neither path replaces engineer review. See
[Expansion Aware Autorouting](architecture/expansion-aware-autorouting.md).

Recommended lifecycle:

```text
TubaModel cold design
  -> AnalysisStudy and AnalysisMesh for Code_Aster
  -> Code_Aster solve
  -> FEAResults in memory
  -> ResultState for traceable persistence
  -> GeometryState for cold / operating / deformed views
  -> DeformedEnvelope for clash, route scoring, and visualization
```

The distinction between visual and physical deformation is critical:

- visual review may exaggerate displacement with a large scale factor.
- clash detection must use physical displacement, normally scale `1.0`.
- conservative clash checks should use an explicit safety factor, not the visualization scale.

This fits the current solver adapter. `CodeAsterSolver` already generates `.mail`, `.comm`, and `.export`, handles pipe and beam-like elements, applies thermal expansion through temperature/reference-temperature load cases, writes `DEPL`, `SIEQ_ELNO`, `EFFO_ELNO`, and `FORC_NODA`, and parses displacements, reactions, forces, and stresses into `FEAResults`.

Real Code_Aster connection has two levels:

1. **Study export / solve handoff:** `CodeAsterSolver.export_analysis_study()` writes `.mail`, `.comm`, `.export`, and `study_manifest.json`. This is the deterministic handoff to Code_Aster and does not require the solver to be installed.
2. **Artifact import / review:** `import_code_aster_artifacts()` reads an existing Code_Aster output directory and turns `study_depl.csv`, `study_effo.csv`, `study_reac.csv`, `study_sieq.csv`, optional `study.rmed`, and `study_manifest.json` into `FEAResults`, `ResultState`, and `AnalysisMesh` context for visualization and downstream checks.

Code_Aster exports also include `study_tuba_fem.json`, a Tuba-owned sidecar
that records solver name mapping and native lineage. This sidecar is the bridge
between Code_Aster solver names and stable `EntityRef` values. It is required
for robust result projection when solver group names must be shortened or when
generated analysis mesh entities do not exist in the native model.

The missing architectural layer is traceability. Code_Aster analysis meshes can contain generated nodes and elements that do not exist in the native model, especially bend intermediate nodes. Those generated mesh entities need source mapping back to native `EntityRef` values. Without that, deformed clash checks for bends and complex supports degrade to endpoint interpolation.

Operating-state clash detection should therefore use:

1. a cold geometry state for installed/as-modeled geometry.
2. a solver result state for the active load case.
3. deformed envelopes derived from solver displacements.
4. structured clash results that report cold distance, operating distance, load case, and whether the clash was introduced by deformation.

This allows detection of cases where the pipe is clash-free when installed but clashes after thermal expansion, pressure, gravity sag, support movement, or nonlinear contact.

The dedicated implementation specification is in `.agents/SPECS/code-aster-operating-state-clash.md`; the checkpoint workplan is in `.agents/TODOS/code-aster-operating-state-clash.md`; the decision log is in `.agents/DECISIONS/code-aster-operating-state-clash.md`.

Implemented operating-state APIs:

- `CodeAsterSolver.export_analysis_study()` writes `.mail`, `.comm`, `.export`, and `study_manifest.json` without executing Code_Aster.
- `import_code_aster_artifacts()` imports existing parser-readable Code_Aster result artifacts into `FEAResults`, `ResultState`, and optional `AnalysisMesh` provenance without executing Code_Aster.
- `ResultState` persists native and generated analysis-node displacement, reaction, force, stress, file, and parser-diagnostic data.
- `GeometryState` separates cold, physical operating, and visual deformed states. Engineering states require displacement scale `1.0`.
- `build_deformed_envelopes()` creates bare, insulation, clearance, maintenance, and wind envelopes from solver displacement and physical attributes.
- `TrimeshClashEngine.check_operating_state()` reports cold distance, operating distance, load case, geometry state, envelope type, and operating-only classification.
- `build_visualization_scene()` can carry result states, geometry states, and operating clash issues together.
- `export_bcf_topics()` exports operating clash metadata for coordination review.
- `python -m tuba.benchmarks deformed-clash --size smoke` checks broadphase pruning and envelope cache reuse.

The runnable developer examples are:

- `examples/operating_state_clash.py`, which uses export-only Code_Aster study generation plus a mock `ResultState`.
- `examples/code_aster_artifact_review.py`, which writes a portable set of solver-style result tables, imports them through the real artifact path, and emits a visualization scene bundle.

Both examples can run on machines without a Code_Aster installation. A developer-local integration run can replace the sample CSV tables with files produced by the real solver.

Troubleshooting notes:

- If generated bend mesh-node results are missing, bend projection falls back to endpoint interpolation and emits `bend_displacement_interpolated`.
- If `study_manifest.json` is missing during artifact import, Tuba can still parse native-node result tables but reports incomplete analysis-mesh provenance.
- If a visual deformed state is passed into engineering clash detection, the check fails instead of silently using visual scale.
- If an exported manifest has no generated bend nodes, inspect whether the model actually contains `pipe_bend` elements and whether the export path was created by `export_analysis_study()`.
- If IFC GUIDs are missing during BCF/IFC coordination export, the internal clash result is still valid; only external element identity is incomplete.

## Insulation Data Flow

Insulation starts as semantic data:

```python
model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
model.assign_insulation("group:line_A", "mw_50")
```

That assignment is then resolved by:

- `physical_properties_for_element()` for effective OD, mass, and wind diameter.
- `TrimeshClashEngine` for collision envelope.
- `RouteCostModel` for insulation cost and weight terms.
- `quantity_takeoff()` and `bom_to_dict()` for reports.

## Extension Points

- Add new semantic specs in `tuba.attributes` and persist them under `model.specs`.
- Add new generated operations in `tuba.patches` so agents can propose changes without mutating first.
- Add new section shapes behind `profile_for_section()`.
- Add new routing algorithms by implementing `PipePlanner`.
- Add engineering checks by implementing the `ModelRule` protocol and registering them in `RuleEngine`.
