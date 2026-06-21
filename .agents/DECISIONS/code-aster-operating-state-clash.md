# Code_Aster Operating-State Clash Decisions

## Purpose

Record architectural decisions for the Code_Aster result-state, deformed geometry, and operating-state clash workflow.

## Decisions

### D01 - Code_Aster Remains The Core Solver

Tuba will not introduce a competing finite-element solver path for production stress, displacement, reaction, or thermal-expansion results.

**Implication:** New architecture layers must wrap and preserve Code_Aster inputs/outputs rather than bypassing them.

### D02 - IFC Is A Coordination Adapter, Not The Internal Clash Engine

Operating clash detection should run on Tuba model semantics, result states, and deformed envelopes. IFC/BCF export consumes the resulting issues.

**Implication:** IFC export quality matters, but route optimization and clash scoring must not depend on exporting/importing IFC in the inner loop.

### D03 - Analysis Mesh Provenance Is Mandatory

Code_Aster analysis mesh nodes and elements must map back to native `EntityRef` values, including generated bend nodes and bend segment elements.

**Implication:** Accurate deformed bend clash detection cannot rely only on native endpoint interpolation when solver mesh data exists.

### D04 - Keep `FEAResults` As The In-Memory Convenience Type

Existing `FEAResults` remains the short-lived object for current solver and visualizer paths. `ResultState` becomes the persistent, traceable representation.

**Implication:** Implementation should be additive and avoid breaking current visualizer/result users.

### D05 - Do Not Mutate `TubaModel` For Deformed Geometry

Cold geometry remains the authoritative model. Operating/deformed geometry is derived from `ResultState` and `GeometryState`.

**Implication:** Deformed envelopes can be cached, serialized as artifacts, and visualized, but they are not written back as native model nodes/elements.

### D06 - Physical Clash Uses Scale `1.0`

Engineering clash checks use physical displacement, normally `displacement_scale=1.0`. Visual deformation scale is separate and may be exaggerated.

**Implication:** A visual state with scale `50.0` must not silently drive engineering clash detection. Conservative checks use explicit safety factors.

### D07 - Initial Deformed Clash Uses Translational Centerline Projection

The first implementation will apply translational node displacement to centerline/envelope geometry. Rotational swept-section updates are deferred.

**Implication:** This is accurate enough for circular pipe envelopes and most early clash checks, but large rotations or non-circular support components may need later refinement.

### D08 - Unit Tests Must Not Require Code_Aster Installation

Core tests use export-only solver paths, manifests, and mock `FEAResults`/`ResultState` fixtures.

**Implication:** Actual Code_Aster execution belongs in optional integration tests or developer-local validation.

### D09 - Deformed Envelopes Are Derived Cache Artifacts

`DeformedEnvelope` objects are generated from model, result state, geometry state, and envelope policy. They can be cached but invalidated aggressively.

**Implication:** Cache keys must include model revision, result-state ID, geometry-state ID, envelope type, clearance policy, and safety factor.

### D10 - Cold And Operating Clash Results Must Be Compared

Operating clash reports should include both cold and operating distances where possible.

**Implication:** The system can classify whether a clash was pre-existing, introduced by deformation, worsened by deformation, or resolved in operation.

### D11 - Support Structure Can Be Cold First, Coupled Later

The first implementation may check deformed pipes against cold rack/support geometry if support structure was not included in the Code_Aster study.

**Implication:** The report must include diagnostics such as `target_structure_not_solved`. Coupled pipe-plus-rack solving is a later package, not a prerequisite.

### D12 - Route Optimization Is Two-Stage

Routing uses cheap proxy checks for broad search and Code_Aster/result-state checks only for shortlisted candidates.

**Implication:** Solver execution and full operating clash should not happen during every low-level route expansion step.

### D13 - BCF Is Preferred For Operating Clash Coordination

Operating-only clashes should be exported as BCF topics with load case, geometry state, cold distance, operating distance, and involved IFC GUIDs where available.

**Implication:** IFC remains the design/coordination geometry exchange. BCF carries issue workflow semantics.

### D14 - Deformed IFC Geometry Is Optional Review Output

As-designed IFC geometry remains the default export. Deformed geometry may be exported only as explicitly marked review geometry.

**Implication:** External coordination should not confuse installed/as-designed geometry with thermal/deformed review geometry.

### D15 - Code_Aster Manifest Export Is Additive

`CodeAsterSolver.export_study()` remains backward compatible and returns the output directory. The manifest workflow uses the new `export_analysis_study()` API, which writes `study_manifest.json` and returns an `AnalysisStudy`.

**Implication:** Existing solver callers keep their current behavior while result-state and operating-clash packages can depend on traceable `AnalysisStudy` and `AnalysisMesh` artifacts.

### D16 - Generated Mesh Node Results Stay Separate From Native Node Results

`FEAResults.node_results` remains native-model-node-only. Generated Code_Aster mesh node displacements are stored in `FEAResults.analysis_node_results`.

**Implication:** Existing result consumers remain compatible, while deformed bend projection can use generated mesh-node results when available.

### D17 - ResultState Stores Solver Node Displacements In One Lookup

`ResultState.node_displacements` stores both native node and generated analysis mesh node displacements. Conversion back to `FEAResults` separates native nodes from generated analysis nodes by checking membership in `model.nodes`.

**Implication:** The persistent state remains compact and solver-oriented, while in-memory consumers keep their native/generated result separation.

### D18 - Operating Clash Results Extend ClashResult Metadata

Operating-state clash checks reuse `ClashResult` and store load-case, geometry-state, cold-distance, operating-distance, envelope, and deformation-introduction data in `metadata`.

**Implication:** Existing clash serializers and visualization paths can continue consuming `ClashResult`, while operating-state consumers can inspect richer metadata.

### D19 - Routing Objectives Accept Optional Analysis Context

Routing objectives keep the existing `evaluate(model, results=None)` shape, but now accept keyword context such as `result_state`, `geometry_state`, `cold_state`, `analysis_mesh`, and `envelope_type`.

**Implication:** Existing FEA-based scoring remains compatible, and shortlisted route candidates can be scored against operating-state clashes without invoking Code_Aster inside route expansion.

### D20 - Load Path Reactions Resolve Through Support Nodes

`analyze_load_paths()` accepts `ResultState` and maps `node_reactions` to supports by matching each support's node ID.

**Implication:** Code_Aster `FORC_NODA` results can roll up to rack loads without changing the existing explicit `support_reactions` API.

### D21 - Operating-State Exchange Uses BCF Metadata And IFC Property Sets

BCF exports carry operating clash metadata in topic descriptions and viewpoint payloads. IFC exports can attach `Pset_TubaOperatingState` to involved elements when a `ResultState` or operating clash list is supplied.

**Implication:** Cold/as-designed IFC geometry remains unchanged, while operating-state review data is available to coordination tools as metadata.

### D22 - Operating Clash Broadphase Uses Pure-Python AABB Indexes

Operating-state clash checks prune envelope/obstacle candidate pairs with the reusable `SpatialIndex` AABB helper before exact segment-distance checks.

**Implication:** The CA14 smoke benchmark can run without optional acceleration dependencies, while future larger models can replace or extend the index behind the same candidate-pair API.

### D23 - Developer Examples Use Export-Only Studies And Mock Results

Portable examples should call `CodeAsterSolver.export_analysis_study()` and then construct a deterministic mock `ResultState` instead of requiring a local Code_Aster execution.

**Implication:** Documentation and agent smoke checks can validate the full downstream operating-state workflow on any development machine, while real solver execution remains an integration step.

## Open Decisions

1. Should large `ResultState` fields remain JSON dictionaries initially, or should array-backed compressed artifacts be introduced immediately for large models?
2. Should nonlinear/contact analyses create one `GeometryState` per increment/time step?
3. Which support components should be part of the first coupled Code_Aster pipe-plus-rack study?
4. What minimum operating clash severity should block route acceptance versus only creating a review issue?
