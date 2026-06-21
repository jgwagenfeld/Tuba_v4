# Future Visualization Engine Vision

This document summarizes the planned visualization architecture for Tuba. The detailed implementation spec is in `.agents/SPECS/visualization-engine.md`; the executable package checklist is in `.agents/TODOS/visualization-engine-workpackages.md`.

## Direction

Tuba should become more than a geometry renderer. The visualization engine should become an engineering review workspace for scripted piping, modular rack construction, route optimization, clash and rule diagnostics, cost tradeoffs, load paths, IFC/BCF coordination, and agent-generated proposals.

The current PyVista visualizer remains valuable for solver plots, screenshots, notebooks, and quick engineering inspection. The future interactive viewer should be web-first and should consume a semantic scene manifest shared with PyVista and export adapters.

Realtime authoring should use trusted Python scripts and JSON patches. YAML or a Mermaid-style DSL is intentionally deferred because piping and rack generation need real programming constructs, typed validation, and patch review. Agents should emit schema-valid JSON patches; humans should use Python for procedural generation.

For agents, Tuba should also adopt a SpatialClaw-like pattern: a persistent sandboxed Python workspace where the agent runs small code cells, inspects stdout/errors/variables/scene snapshots, revises, and only then emits a schema-valid patch or proposal. SpatialClaw is a useful reference pattern, not a planned direct dependency.

The concrete implementation addendum for cold geometry, Code_Aster results, warped/deformed views, clash review, and live preview is `.agents/SPECS/realtime-code-aster-visualization.md`. The matching package checklist is `.agents/TODOS/realtime-code-aster-visualization.md`.

Recommended technology baseline:

- Web viewer: `viewer/` evolved to Vite, TypeScript, and Three.js.
- Python side: `VisualizationScene`, scene bundles, preview server, file watcher, and websocket reload.
- Notebook side: embed the same web scene or use PyVista/trame for quick scientific plots.
- Solver side: parse Code_Aster outputs into `ResultState`; viewer consumes validated scene overlays, not raw solver files.
- BIM/IFC side: keep IFC as exchange; add Fragments/xeokit-style adapters later if large IFC context requires it.

## Core Architecture

```text
TubaModel
  + attributes/specs
  + physical properties
  + route plans/candidates
  + clash reports
  + rule reports
  + quantity/cost data
  + solver results
  + model patches / agent proposals
        |
        v
VisualizationScene
        |
        +-- PyVista adapter
        +-- Web viewer
        +-- glTF/GLB + metadata export
        +-- IFC adapter
        +-- BCF issue exchange
```

The important architectural decision is that the viewer receives semantic engineering objects, not just meshes. A pipe object should know its `EntityRef`, section, material, route, insulation, effective diameter, mass, cost, clash envelope, support associations, IFC GUID, and issue links.

## Major Feature Areas

| Area | Required Features |
| --- | --- |
| Navigation | orbit, pan, zoom, fit selection, standard views, saved viewpoints, section box |
| Object inspection | picking, hover, property panel, copy entity ref, isolate/hide, reveal in tree |
| Model organization | tree by route/system/rack/group/kind, search, filters, layer controls |
| Measurement | point distance, object clearance, clipping, sectioning, transparent ghost mode |
| Route review | candidate comparison, ghost routes, cost table, invalid reasons, patch preview |
| Clash review | issue list, severity/status, focus viewpoint, involved objects, BCF compatibility |
| Rule review | support spacing, slope, rack occupancy, code/proxy diagnostics |
| Physical envelopes | bare pipe, insulation, cladding, clearance, maintenance, wind envelope toggles |
| Cost/quantity | route cost, insulation cost, support/structure cost, heatmaps, grouped takeoff |
| Rack/load path | rack levels/lanes, attachment points, support reactions, load-path overlays |
| Solver results | stress, displacement, reactions, temperature, deformed shape overlays |
| Patch review | added/removed/modified geometry, semantic changes, before/after metrics |
| Agent workflows | proposal rationale, route alternatives, risks, approval state, audit trail |
| IFC/BCF | IFC GUID mapping, property sets, BCF topics/viewpoints/comments |
| Federation | Tuba model plus external IFC/equipment/scan context in one scene |
| Operations | asset state, inspection status, sensor placeholders, time/state overlays |
| Realtime preview | trusted Python watch mode, JSON patch watch mode, scene diffs, hot reload |
| Agentic workspace | sandboxed persistent Python cells, scene feedback, final JSON patch proposal |

## Package Roadmap

| Package | Outcome |
| --- | --- |
| VE01 Scene manifest | Canonical `VisualizationScene` data contract |
| VE02 Scene builders | Convert model/routes/clashes/rules/costs/results into scene data |
| VE03 Geometry bundle export | GLB plus metadata sidecar for browser loading |
| VE04 Web viewer shell | Local interactive viewer that loads scene bundles |
| VE05 Selection/property panel | Inspect model objects and engineering metadata |
| VE06 Tree/filter/sectioning | Review controls expected from serious model viewers |
| VE07 Route alternatives | Compare route candidates and cost/rule/clash tradeoffs |
| VE08 Clash issues | Focus, group, comment, and export clash issues |
| VE09 Rule review | Visualize compliance and constructability diagnostics |
| VE10 Physical envelopes | Toggle insulation, cladding, clearance, wind, maintenance envelopes |
| VE11 Cost/quantity overlays | Heatmaps and grouped economic/quantity summaries |
| VE12 Rack/load-path overlays | Rack lanes, support attachments, reactions, utilization |
| VE13 Solver overlays | Web-level stress/displacement/reaction/temperature context |
| VE14 Agent proposal review | Patch diffs, rationale, approval, before/after metrics |
| VE15 IFC mapping | Stable object mapping and property-set exchange |
| VE16 BCF exchange | External issue coordination |
| VE17 Performance | batching, caching, LOD, benchmarks, progressive loading |
| VE18 Federation | external model sources and transforms |
| VE19 Point cloud context | retrofit/field review foundation |
| VE20 Digital twin state | operational state overlays |
| VE21 Realtime preview | live Python script preview, JSON patch preview, scene diffs |
| VE22 Agentic Python workspace | SpatialClaw-like iterative code workspace for agents |

## First Vertical Slice

The first useful implementation should prove the full semantic loop with limited scope:

1. Define `VisualizationScene`.
2. Build a scene from a small Tuba model with pipes, obstacles, insulation, and route candidates.
3. Export GLB geometry and metadata sidecar.
4. Load the scene in a web viewer.
5. Select a pipe and inspect insulation/effective OD/cost data.
6. Toggle route alternatives.
7. Focus a clash issue.
8. Toggle insulation and clearance envelopes.
9. Preview a JSON patch update without mutating the committed model.
10. Run an agent workspace session that emits a validated patch proposal.

This creates a foundation for all later visualization packages without overcommitting to one renderer or external exchange format.

## Realtime Preview Loop

The first realtime loop should behave like this:

```text
save trusted Python generation script
  -> preview subprocess executes script
  -> Tuba validates model, patch, result state, or scene
  -> scene bundle is rebuilt
  -> websocket event tells viewer to reload
  -> viewer preserves camera/selection when possible
```

After that is stable, add JSON `ModelPatch` watch mode and then incremental `SceneDiff` updates. This gives a Mermaid-like feedback loop without inventing a weak YAML DSL for piping/rack generation.

## Key Decisions

- Use a semantic scene manifest before adding more UI controls.
- Keep PyVista for engineering plots.
- Build a web-first viewer for review workflows.
- Use glTF/GLB plus metadata sidecar first.
- Keep IFC as an exchange adapter, not the internal routing/clash model.
- Make BCF-compatible issues internal from the start.
- Require agent proposals to be patch-first and reviewable.
- Do not add YAML as a first-class authoring format yet.
- Use Python scripts for expressive authoring and JSON patches/scene diffs for agents and realtime transport.
- Adopt the SpatialClaw-style persistent Python workspace pattern for agent reasoning, but keep final changes patch-first and reviewable.
- Make physical envelopes explicit visual overlays.
- Benchmark scene build, bundle size, load time, selection latency, and overlay toggling.
