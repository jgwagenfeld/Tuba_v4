# Visualization Engine Decisions

## Decision 1 - Build A Semantic Scene Contract First

Tuba will introduce a `VisualizationScene` manifest before building more interactive features.

Reasoning:

- Routing, clash, cost, rules, solver results, and agent proposals need one shared visualization contract.
- Directly adding controls to the existing PyVista functions would not solve metadata, selection, issue, or route-review needs.
- A manifest lets multiple renderers consume the same engineering state.

Rejected option:

- Extend each plot/export function independently.

## Decision 2 - Use A Hybrid Renderer Strategy

Tuba will keep PyVista for scientific and engineering plots while adding a web-first viewer for interactive review.

Reasoning:

- PyVista is useful for FEA-like visualizations, screenshots, and Python workflows.
- Web viewers are better for product UX: property panels, issue lists, filtering, saved views, route comparison, BCF, and agent proposal review.
- Keeping both avoids rewriting all existing visualization logic at once.

Rejected option:

- Replace PyVista immediately.

## Decision 3 - Treat IFC As Exchange, Not Internal State

IFC will be used for import/export, property-set mapping, external coordination, and BCF issue exchange. It will not become the internal visualization/routing/clash model.

Reasoning:

- Internal route candidates and agent proposals often exist before final model mutation.
- IFC roundtrips would be too slow and lossy for optimization loops.
- Tuba already has richer domain-specific state than IFC can conveniently represent without custom property sets.

Rejected option:

- Export every route candidate to IFC before visualization or clash review.

## Decision 4 - Use glTF/GLB Plus Metadata Sidecar First

The first scene bundle should use GLB geometry plus JSON metadata.

Reasoning:

- GLB is widely supported and efficient for runtime rendering.
- Metadata sidecars keep object identity and engineering data explicit.
- This can later be adapted to xeokit XKT, That Open Fragments, 3D Tiles, or USD without changing the internal scene contract.

Rejected option:

- Store all engineering metadata directly inside renderer-specific mesh formats.

## Decision 5 - Make BCF-Compatible Issues Internal From The Start

The internal `Issue` model should be compatible with BCF topic/viewpoint concepts even before complete BCF export/import exists.

Reasoning:

- Clash and rule review need issue lifecycle, viewpoints, comments, and involved objects.
- BCF compatibility prevents rework when external coordination becomes important.

Rejected option:

- Store clashes only as report rows or screenshots.

## Decision 6 - Agentic Workflows Must Be Patch-First

Agents can create `AgentProposal` objects with `ModelPatch` payloads. They cannot silently mutate the model through the viewer.

Reasoning:

- Generated geometry must be inspectable and reversible.
- Users need cost, clash, and rule deltas before applying changes.
- This matches the existing future-ready architecture direction.

Rejected option:

- Let viewer buttons directly call arbitrary model mutations.

## Decision 7 - Make Physical Envelopes Toggleable Visual Objects

Bare geometry, insulation, cladding, clearance, maintenance, and wind envelopes should be separate overlays where practical.

Reasoning:

- Many future optimization decisions depend on non-visible attributes.
- Users must see why insulation changes clash, wind load, cost, and route feasibility.

Rejected option:

- Only inflate mesh radius and hide the source of the envelope.

## Decision 8 - Renderer Adapters Must Be Replaceable

The viewer architecture must not depend on one rendering library.

Reasoning:

- Plain Three.js may be best for the first MVP.
- xeokit or Fragments may be better for large IFC/BIM models.
- vtk.js may be useful for solver/scientific overlays.

Rejected option:

- Encode all viewer semantics directly into one web rendering library.

## Decision 9 - Performance Requirements Belong In The Contract

Scene build time, bundle size, load time, selection latency, and overlay-toggle latency must be benchmarked.

Reasoning:

- Visualization performance cannot be repaired only at the UI layer.
- Stable IDs, batching, caching, and LOD need to be designed early.

Rejected option:

- Wait until the viewer is slow, then optimize ad hoc.

## Decision 10 - First Viewer Should Be Review-First, Not CAD-Authoring-First

The first interactive viewer should focus on review, comparison, inspection, issue management, and patch approval.

Reasoning:

- Tuba's differentiator is programmable generation and optimization, not manual CAD drafting.
- Review-first reduces scope while still enabling high-value workflows.

Rejected option:

- Build a full browser CAD editor first.

## Decision 11 - Do Not Add YAML As A First-Class Authoring Format Yet

Tuba will use Python scripts for expressive human authoring and JSON `ModelPatch` / `VisualizationScene` / `SceneDiff` payloads for agents, APIs, review, tests, and realtime transport.

Reasoning:

- Piping and rack generation need variables, loops, reusable modules, catalogs, conditionals, units, and validation. Python already provides those without inventing a weak DSL.
- Agents are more reliable when producing schema-valid JSON patches than loosely structured YAML.
- JSON patches are easier to validate, diff, review, and apply through `ModelTransaction`.
- A Mermaid-like YAML layer would add maintenance weight before we have proven the core realtime preview loop.

Rejected option:

- Make YAML or a Mermaid-style text DSL part of the core model authoring path now.

Future option:

- Add a small YAML/template layer later only for narrow non-programmer use cases, compiling immediately into typed JSON patches.

## Decision 12 - Realtime Preview Uses Python Watch Mode And JSON Scene Diffs

Realtime preview will be implemented as trusted local Python script watching plus JSON patch watching. The viewer receives full scene bundle reloads first, then `SceneDiff` updates when incremental recomputation is safe.

Reasoning:

- Python gives power users and agents a direct way to use the real Tuba API.
- JSON patch preview keeps agent output reviewable and schema-valid.
- `SceneDiff` keeps the viewer responsive without making the renderer own model logic.
- Full rebuild fallback avoids unsafe partial updates early.

Rejected option:

- Execute arbitrary code from the browser or scene bundle.

## Decision 13 - Adopt The SpatialClaw Pattern, Not The SpatialClaw Dependency

Tuba will add an agentic Python workspace inspired by SpatialClaw's persistent-code action interface: an agent reasons through small Python cells, receives feedback, and revises before producing a final answer. For Tuba, the final answer must be a validated JSON `ModelPatch`, `RoutePlan`, or `AgentProposal`.

Reasoning:

- Spatial/routing problems often need flexible computation: vector math, nearest-neighbor search, geometry probes, route scoring, clash checks, and visual inspection.
- Fixed tool calls are too rigid for exploratory engineering tasks.
- One-shot generated Python scripts are too brittle because the agent cannot inspect intermediate results before committing.
- A persistent Python workspace lets the agent compute, inspect, visualize, and revise.
- JSON patches preserve reviewability, schema validation, rollback, and human approval.

Rejected options:

- Vendor SpatialClaw as a direct runtime dependency.
- Let agent Python directly mutate the committed model.
- Require agents to solve spatial routing only through fixed JSON tool calls.

Implementation consequences:

- The workspace needs sandboxing, execution limits, audit logs, and cancellation.
- The workspace should preload Tuba-specific helpers instead of perception-heavy SpatialClaw modules.
- Intermediate snapshots are analysis artifacts; committed changes still go through `ModelPatch` and `ModelTransaction`.

Reference:

- SpatialClaw project: https://spatialclaw.github.io/
