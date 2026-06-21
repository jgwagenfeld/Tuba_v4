# Multidomain IFC-Aware Data Model Decisions

## Context

Tuba is evolving from scripted piping geometry into a multidomain engineering system for piping, support structures, rack assemblies, load paths, route optimization, clash detection, cost optimization, visualization, agent patches, and IFC/BCF coordination.

The earlier architecture established that IFC is an exchange adapter, not the internal routing or clash model. The new question is how this changes when Tuba models support structure in addition to piping.

## Decision 1 - Tuba Becomes Multidomain, Not Pipe-Only With Support Metadata

Support structure must be first-class. Racks, beams, columns, braces, support components, and load transfers cannot be hidden as attributes on pipes.

### Consequences

- Pipe systems and support/rack systems get equal modeling status.
- Optimization can compare pipe detours against added support steel.
- Clash checks can consider pipe, insulation, supports, rack members, and maintenance envelopes.
- Cost and quantity takeoff can separate pipe, insulation, support hardware, and structural members.

## Decision 2 - IFC-Aware Native Model, Not IFC-Native Internal Model

Tuba will adopt IFC-inspired patterns:

- stable global identity
- occurrence/type split
- property-set mapping
- ports/connectivity
- assemblies/decomposition
- material associations
- structural analysis separation

Tuba will not store or mutate an IFC graph as the primary model.

### Rationale

IFC is excellent for exchange and coordination, but too broad and too slow for live routing, clash broadphase, agent patch preview, and cost optimization loops.

### Consequences

- Internal algorithms work on `TubaModel`, `EntityRef`, ports, relationships, indexes, envelopes, routes, costs, and patches.
- IFC export/import uses a mapping registry.
- IFC roundtrip is not required for internal review or optimization.

## Decision 3 - Relationships Become First-Class

Containment, decomposition, support, attachment, load transfer, connectivity, issue links, and provenance will be represented as `ModelRelationship` records.

### Rationale

The current model stores some important semantics in group metadata or implicit node matching. That does not scale for agents, IFC export, load paths, or cost decisions.

### Consequences

- Querying "what supports this pipe" or "which rack member receives this load" becomes direct.
- BCF and visualization can trace issues to involved entities.
- IFC export can map native relationships to IFC relationships or property sets.

## Decision 4 - Ports Are Required For Future Routing

Native `Port` objects will represent connection points for pipes, equipment nozzles, fittings, support attachment points, and structural joints.

### Rationale

Node coordinates alone are not enough to express connection compatibility, flow direction, system membership, nominal size, or attachment intent.

### Consequences

- Autorouting can target ports rather than only coordinates.
- Agents can reason about valid connections.
- IFC `IfcDistributionPort` mapping becomes straightforward for distribution systems.

## Decision 5 - Keep Solver Supports Separate From Physical Support Components

The existing `Support` object remains the boundary condition used by solvers. A new `SupportComponent` represents physical hardware such as shoes, clamps, anchors, brackets, guides, or spring hangers.

### Rationale

One physical support may imply one or more solver constraints, and one solver support is not always enough to describe constructible hardware.

### Consequences

- Existing solver paths remain stable.
- Physical supports can be costed, clashed, visualized, exported, and attached to rack members.
- Load transfer can link solver reactions to physical hardware and structure.

## Decision 6 - Assemblies Supersede Groups Gradually

`Assembly` becomes the first-class model for rack bays, frames, modules, and skids. `groups` remain as compatibility views.

### Rationale

Groups are useful but underspecified. Assemblies need type, membership, ports, parent/child nesting, relationships, and IFC mapping.

### Consequences

- `RackBay.to_patch()` should eventually create both `Assembly` and compatibility `Group`.
- Legacy rack groups can be read as virtual assemblies.
- IFC export maps assemblies to `IfcElementAssembly` where appropriate.

## Decision 7 - IFC Export Uses A Mapping Registry

IFC entity, property, and relationship mappings will live in a central `IfcMappingRegistry`.

### Rationale

Scattered export decisions make it hard to prove what semantics are preserved. A registry provides testable coverage and diagnostics.

### Consequences

- Export profiles define how much data to emit.
- Missing mappings become diagnostics.
- Tests can assert every first-class native concept has an IFC policy.

## Decision 8 - Performance Indexes Are Part Of The Model Update

The model update must include indexes and cache invalidation, not only new dataclasses.

### Rationale

Adding relationships, ports, assemblies, and external identities can make naive scans expensive. Routing and clash checks will multiply that cost.

### Required Indexes

- entity by ID
- relationships by source, target, and type
- ports by owner
- assemblies by member
- groups by member
- supports by node
- elements by node
- external identities by target and external ID
- spatial AABB indexes for envelopes and obstacles

### Consequences

- `ModelTransaction` increments model revision.
- Derived caches check revision before reuse.
- Benchmarks become required acceptance gates.

## Rejected Option - Store Everything As Generic Attributes

This would be quick but would fail for routing, load transfer, IFC mapping, validation, and performance.

## Rejected Option - Convert To IFC Internally Before Every Operation

This would make exchange easier in the short term but would slow optimization loops, complicate agent patches, and introduce IFC implementation-specific behavior into core algorithms.

## Rejected Option - Replace The Whole Model In One Migration

This is too risky. The current test suite and working APIs are valuable. The migration must be additive, package-based, and compatibility-first.

## Decision Status

Accepted as implementation direction for `.agents/SPECS/multidomain-ifc-aware-data-model.md` and `.agents/TODOS/multidomain-ifc-aware-data-model.md`.
