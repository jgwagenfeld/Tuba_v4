# Realtime Code_Aster Visualization Decisions

## D01 - Use The Web Viewer As The Primary Interactive Engine

The main review UI will be a browser viewer, not a notebook, Blender scene, or PyVista window.

Reasoning:

- The required workflow needs object trees, properties, issue lists, route comparison, patch approval, saved views, and live updates.
- Browser UI is the most practical platform for those controls.
- The same viewer can run locally, embed in notebooks, and export static review bundles.

## D02 - Keep PyVista For Engineering Plots And Notebooks

PyVista remains useful for solver/result debugging, screenshots, and notebook workflows.

Reasoning:

- PyVista is strong for scientific mesh/result plotting.
- PyVista/trame can provide interactive notebook/browser previews.
- It should consume the same model/result data, but it should not own the review workflow.

## D03 - Use Three.js First

The first real viewer renderer should use Three.js.

Reasoning:

- Tuba's first viewer assets are procedural tubes, polylines, boxes, vectors, envelopes, markers, and simple meshes.
- Three.js is flexible, broadly adopted, and not tied to IFC.
- BIM-scale renderers can be added later behind the scene contract.

Rejected:

- Make xeokit, Fragments, vtk.js, Blender, or IFC the phase-one core renderer.

## D04 - Keep VisualizationScene As The Contract

The viewer receives `VisualizationScene` plus geometry assets. It does not parse raw Code_Aster outputs as its primary API.

Reasoning:

- Python already understands Tuba semantics, Code_Aster manifests, result states, physical properties, and clashes.
- The viewer should display validated engineering data, not infer engineering meaning from raw files.

## D05 - Realtime Preview Uses Trusted Python And JSON Patches

Realtime preview will watch trusted local Python scripts and JSON `ModelPatch` files.

Reasoning:

- Python is the real authoring language for procedural pipe/rack generation.
- JSON patches are safer and easier for agents, tests, review, and transport.
- YAML/Mermaid-like authoring is deferred until a narrow non-programmer use case is proven.

## D06 - Full Scene Reload Before SceneDiff Optimization

The first live preview should rebuild and reload the whole scene bundle. Incremental `SceneDiff` updates come after stable identity and invalidation rules are proven.

Reasoning:

- Full reload is simpler and reliable.
- SceneDiff is valuable for responsiveness, but premature partial updates can hide stale geometry/results.

## D07 - Visual Scale Is Display-Only

The viewer may expose visual deformation scale controls, but engineering clash results remain tied to physical `GeometryState` scale `1.0` and explicit safety factors.

Reasoning:

- A visual scale slider must not silently change clash classification, route scoring, or issue severity.

## D08 - Code_Aster Is Never Run On Every Save By Default

Live preview does not automatically execute Code_Aster whenever a script changes.

Reasoning:

- Solver runs are too expensive and environment-dependent.
- Preview should use existing result files, imported `ResultState`, or mock states unless the user explicitly triggers a solve.

## D09 - BIM And Scientific Adapters Are Secondary

That Open Fragments, xeokit/XKT, vtk.js, APS, and iTwin are reference patterns or later adapters.

Reasoning:

- They solve important large-model/scientific cases.
- Tuba first needs its own local semantic review loop.
- The scene contract keeps these adapters replaceable.

## D10 - Realtime Baseline Fixtures Are Test-Owned Bundles

RV01 baseline regression fixtures live in test support and generate deterministic `VisualizationScene` bundles, Code_Aster study manifests, mock `ResultState` records, geometry states, and operating-state clash snapshots without running Code_Aster.

Reasoning:

- Later packages need stable object, asset, overlay, issue, and view counts before renderer migration.
- The fixture should exercise existing production builders and solver export paths while staying independent of local solver availability.
- Keeping it in test support avoids expanding the public Tuba API before the realtime workflow stabilizes.

## D11 - AnalysisMesh Projects To Selectable Scene Assets

`AnalysisMesh` is projected into `VisualizationScene` as selectable mesh-node and mesh-element objects with point/polyline assets, source `EntityRef` metadata, Code_Aster group membership, and missing-provenance diagnostics.

Reasoning:

- The web viewer should inspect the actual solver mesh submitted to Code_Aster, not infer it from cold pipe geometry.
- Native and generated mesh entities need stable object IDs for selection, layer toggles, result overlays, and later warped mesh views.
- Missing source mappings should be visible diagnostics instead of silently dropping mesh records.

## D12 - ResultState Emits Semantic Solver Overlays

Persistent `ResultState` records emit semantic `solver_result` overlays for stress/utilization, displacement vectors, reaction vectors, and parser diagnostics.

Reasoning:

- The web viewer consumes imported/parsed solver state instead of reading raw Code_Aster files.
- Scalar overlays need stable object IDs, legend metadata, thresholds, and hotspot summaries for later browser UI.
- Vector overlays carry node-linked displacement and reaction data without requiring solver execution or renderer-specific objects.

## D13 - Deformed Geometry Is A Scene Projection

Physical and visual deformed geometry is projected into scene layers from `ResultState`, `GeometryState`, and optional `AnalysisMesh` inputs without mutating `TubaModel`.

Reasoning:

- Physical operating states use engineering scale `1.0`; exaggerated visual states are display-only.
- Deformed centerlines, envelopes, and warped mesh assets carry `geometry_state_id`, `result_state_id`, load case, and visual scale metadata.
- Clash review remains tied to the engineering geometry state rather than the visual deformation scale.

## D14 - Clash Review Uses A Normalized Payload

Clash markers, overlays, issues, and BCF exports include a normalized review payload in addition to the raw `ClashResult`.

Reasoning:

- The viewer needs top-level fields for filtering by load case, geometry state, result state, severity, envelope type, and object pair.
- Operating-state clash review must expose cold and operating distances without requiring UI code to know the internal `ClashResult.metadata` shape.
- BCF export keeps the raw clash payload but also carries review metadata for coordination workflows.

## D15 - Canonical Review Bundle Exercises The Full Local Loop

The realtime review example writes a Code_Aster-free scene bundle containing cold geometry, analysis mesh, mock result overlays, physical and visual deformed geometry, and an operating-only clash issue.

Reasoning:

- Later viewer packages need one stable smoke fixture that exercises all core visualization layers together.
- The example uses export-only Code_Aster manifest generation plus mock results so it remains deterministic without a solver installation.
- Bundle metadata records expected counts for regression tests and loader smoke checks.

## D16 - Vite Owns Viewer Build Without Breaking JS Loader APIs

The viewer scaffold uses Vite, TypeScript config, and a TypeScript entrypoint while preserving existing JavaScript modules and Node unit tests.

Reasoning:

- RV07 should modernize the app shell without forcing a risky renderer or loader rewrite before RV08 and RV09.
- `loadSceneBundleFromUrl` remains browser-first, while Node bundle loading keeps its existing API for tests and fixtures.
- Node-only imports are hidden from the browser bundle so the Vite build stays warning-free and CI-friendly.

## D17 - Three.js Renders Viewer-Generated Geometry Directly

RV08 renders `VisualizationScene` geometry assets with Three.js primitives generated in the browser, not with IFC, GLB, or solver-file parsing.

Reasoning:

- The first interactive renderer only needs lightweight tubes, polylines, points, vectors, markers, AABBs/cuboids, and simple meshes.
- Rendered Three.js objects carry stable scene object IDs in `userData` so later selection and property inspection can use the canonical viewer contract.
- Browser smoke coverage reads WebGL pixels from a deterministic fixture to prove the canvas is nonblank and includes cold geometry plus clash markers.

## D18 - Viewer State Separates Object Layers From Overlay Layers

RV09 derives client-side layers from object `layer_ids` and overlay kinds, then recomputes visible object IDs without mutating the loaded `VisualizationScene`.

Reasoning:

- Cold geometry, deformed geometry, result states, and clash review need independently controllable visibility.
- Overlay-kind layers hide only overlay-owned marker/envelope objects where appropriate, so hiding a clash overlay does not hide the underlying pipe.
- Full-scene reload can preserve camera, selection, and shared layer visibility by stable object/layer IDs before SceneDiff optimization exists.

## D19 - Viewer Inspection Uses Canonical Scene Metadata

RV10 keeps the property panel and object tree driven by `VisualizationScene` object, asset, overlay, issue, and provenance metadata rather than renderer-specific state.

Reasoning:

- Raycast/hover helpers return stable scene object IDs, so selection remains independent of Three.js mesh internals.
- Engineering inspection needs insulation, effective radius, clash distances, IFC refs, result values, and analysis mesh provenance in one normalized panel.
- Copy, fit, hide, and isolate actions operate on canonical object IDs so they remain valid across reloads and later SceneDiff updates.

## D20 - Result Review Controls Are Display-State Only

RV11 stores load case, result state, geometry state, vector scales, thresholds, and visual deformation scale in viewer state while keeping engineering issue metadata immutable.

Reasoning:

- Code_Aster remains upstream of result values; the browser reviews projected `ResultState` overlays rather than recalculating solver output.
- Displacement/reaction vector scale and visual deformation scale are rendering controls, not engineering scale factors.
- Clash issue distances remain the physical values exported by the operating-state workflow, so UI exaggeration cannot silently change engineering review results.

## D21 - Clash Review Is Local UI State Over Immutable Engineering Data

RV12 stores review status and comments in viewer state, while cold distance, operating distance, penetration, envelope, load case, BCF, and clash-review metadata remain exported scene issue data.

Reasoning:

- Operating-state clash distances come from the physical Code_Aster/Tuba workflow and must not be recalculated or mutated by the browser.
- Grouping, filtering, and BCF readiness derive from issue and marker metadata so they remain compatible with generated scene bundles.
- Hide, isolate, focus, and restore actions operate on selected scene object IDs without changing the underlying `VisualizationScene`.

## D22 - Live Preview Uses Trusted Subprocesses And Full Scene Reloads First

RV13 runs trusted local preview scripts in a subprocess with timeout, writes a normal `VisualizationScene` bundle, and notifies the browser through websocket `scene_reloaded` events.

Reasoning:

- The preview server never executes Python from scene bundles and does not invoke Code_Aster automatically; scripts must be explicitly watched local files.
- Full bundle reload preserves the canonical viewer contract while avoiding premature `SceneDiff` complexity.
- Diagnostics are sent as websocket events and appended to viewer state so invalid scripts are visible without refreshing the browser.
- `scene.json` is written last because live viewers treat it as the reload trigger for a complete bundle.

## D23 - JSON Patch Preview Reuses Agent Proposal Dry Runs

RV14 previews JSON `ModelPatch` files by loading a committed model snapshot, validating the patch, and building a proposal scene through the existing dry-run `ModelTransaction` path on a copied `TubaModel`.

Reasoning:

- Agent/tool patch proposals should use the same schema validation and rollback semantics as normal `ModelPatch` application.
- The committed model file is read-only during preview; accepted changes require a separate commit/apply action outside the viewer loop.
- Patch preview still emits full `scene_reloaded` events in RV14 so the browser path remains compatible with RV13 until RV15 adds conservative `SceneDiff` delivery.
- Invalid patches write diagnostic scenes and websocket diagnostics so reviewers see failures without mutating model state.

## D24 - SceneDiff Applies Only Compatible Semantic Scene Changes

RV15 applies incremental `SceneDiff` updates only when the viewer's current `scene_id` matches the diff `base_scene_id` and core scene identity remains compatible.

Reasoning:

- Small preview changes should avoid full bundle reloads, but stale engineering data is worse than a slower reload.
- Geometry assets are treated as upserts through `added_geometry_assets` because the current `SceneDiff` contract has no separate updated-asset field.
- Removed objects prune geometry assets that no longer reference surviving objects, preventing renderer and validation references to deleted scene objects.
- Mismatched scene bases or incompatible scene identity produce fallback diagnostics and use a full reload when a bundle URL is available.

## D25 - Static Reports Are Bundle-Based And Notebook-Friendly

RV16 static reports wrap the canonical scene bundle with a self-contained HTML summary, issue summary, and notebook iframe helper instead of introducing a separate notebook-first viewer.

Reasoning:

- `VisualizationScene` and `write_scene_bundle()` remain the source of truth for report data and geometry metadata.
- A local `index.html` with embedded scene/report JSON can open without a dev server, while the full web viewer remains the primary interactive review path.
- Notebook integration should embed or link the same report/viewer artifacts rather than creating a parallel notebook UI contract.
- Screenshot export is optional and diagnostic-only because local Playwright/browser availability varies by workstation.

## D26 - Performance Benchmarks Start As Deterministic Smoke Metrics

RV17 measures scene build time, bundle size, viewer-smoke load parsing, selection lookup, overlay-toggle simulation, and stable geometry asset hashes before adding large-model renderer adapters.

Reasoning:

- Local benchmark smoke tests should be deterministic and cheap enough to run without browser or solver dependencies.
- Geometry payload hashes make cache reuse measurable and provide a stable basis for later renderer asset caching.
- The benchmark CLI writes `.benchmarks/viewer_smoke_latest.json` so future package gates can compare local runs without changing core viewer behavior.
- Performance diagnostics are threshold-driven warnings, not hard failures, until realistic project-specific limits are chosen.

## D27 - Optional Renderers Stay Behind Metadata-Only Boundaries

RV18 registers vtk.js, That Open Fragments, and xeokit/XKT as optional adapter boundaries through a metadata/status registry instead of importing their packages in core visualization code.

Reasoning:

- The Three.js web viewer and `VisualizationScene` remain the primary interactive review engine and canonical contract.
- BIM/scientific engines can be added later as dedicated adapter packages without making unit tests, PyVista paths, or scene builders depend on browser-side libraries.
- Missing adapters return structured diagnostics, so future UI and CLI paths can explain unavailable renderers without crashing on imports.
- IFC/fragments/XKT artifacts are context or exchange assets; they do not become the internal visualization state.

## D28 - Scene Lookup Uses Maintained Model Indexes Where Available

RV19 adds a maintained element ID index to `TubaModel` and routes visualization element lookup through that index before falling back to legacy scans.

Reasoning:

- Scene builders still iterate entities when constructing a complete scene, but referenced element lookups should not rescan the full element list when the model already owns an index.
- The index is rebuilt through normal `Model.from_dict()` loading because elements are restored through `add_element()`.
- The fallback scan preserves compatibility with older model-like objects that do not expose indexed lookup.
- This keeps the final release gate's performance checklist grounded in code, not just benchmark timing.

## References

- PyVista trame notebook/browser rendering: https://docs.pyvista.org/user-guide/jupyter/trame.html
- VTK.js: https://kitware.github.io/vtk-js/docs/
- Three.js: https://threejs.org/docs/
- xeokit SDK: https://xeokit.github.io/xeokit-sdk/
- That Open docs: https://docs.thatopen.com/
- Autodesk Platform Services Viewer: https://aps.autodesk.com/apis-and-services/viewer
- Bentley iTwin.js: https://www.itwinjs.org/
