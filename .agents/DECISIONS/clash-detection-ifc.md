# Clash Detection And IFC Decisions

## Decision

Tuba should own a clash detection interface and at least one internal clash engine. IFC should be an adapter for exchange, review, and optional external coordination workflows, not the only clash detection mechanism.

## Recommendation

Use a hybrid architecture:

1. `tuba.clash` owns the public clash interface, result model, and filtering rules.
2. The first internal adapter uses the existing `trimesh` / `python-fcl` path from `tuba.geometry.collision`.
3. The routing grid keeps its lightweight occupancy checks for path search.
4. IFC import/export remains an external adapter for model exchange and optional external clash checks.
5. Later adapters can call IfcOpenShell geometry, BlenderBIM, Navisworks/Solibri/BIMCollab/BCF workflows, or a CAD-kernel engine without changing routing and optimization code.

## Why Not IFC-Only

IFC is a file exchange and coordination format. It is valuable, but using it as the only clash mechanism creates several risks:

- Slow feedback for routing. Every candidate would require export, geometry reconstruction, and external interpretation.
- Lossy semantics. Current IFC export maps Tuba elements by `elem.type`, while insulation, cost, rack identity, and route intent are not preserved as durable model data yet.
- Weak locality. A routing algorithm should ask one local module whether a candidate is clear. It should not know how to export IFC, find external products, and map results back.
- Test fragility. Unit tests and CI should validate clash behavior without depending on external BIM tools.
- Roundtrip uncertainty. IFC import currently simplifies product geometry and obstacles; it is useful for exchange, not a complete source of truth.

## Why Keep Internal Clash Detection

Internal clash detection gives Tuba the speed and control needed for scripted generation and optimization:

- Routing needs thousands of cheap envelope checks.
- Optimization needs repeatable scoring for many candidates.
- Insulation and clearance need deterministic effective envelopes.
- Deformed-state checks need direct access to solver displacement results.
- Tests can define exact fixtures and expected clashes.

The internal engine does not need to become a full BIM coordination product. It should answer engineering questions that Tuba must own:

- Does this pipe route violate clearance?
- Does insulation or cladding clash with obstacles?
- Does the hot/deformed state clash?
- Which element, obstacle, and distance drove the result?
- Is the clash hard, soft, or filtered by rule?

## Current Evidence In The Codebase

- `tuba.geometry.collision.PipingCollisionChecker` already builds pipe cylinders and checks them against model obstacles using `trimesh.collision.CollisionManager`.
- `tuba.routing.grid.RoutingGrid` already inflates obstacles and existing pipes with pipe OD, insulation, and clearance for route search.
- `tuba.external.ifc.IfcExporter` and `IfcImporter` already provide exchange adapters, but export geometry errors are currently swallowed in some paths.
- `tests/test_collision.py` already covers primitive cuboid and STEP-mesh collision.
- `tests/test_ifc.py` already covers IFC export/import roundtrip for pipes, supports, beams, and obstacles.

## Rejected Option: Only Use IFC

Rejected because it would put routing, cost optimization, solver checks, and CI on top of an exchange adapter. That makes the clash module shallow: the caller would still need to understand model export, external geometry limitations, result mapping, and filtering.

## Rejected Option: Build A Full CAD/BIM Clash Engine Now

Rejected because the near-term need is not a Navisworks replacement. Tuba needs a deterministic internal interface for routing, insulation envelopes, deformed-state checks, and optimization. External BIM tools can remain review adapters.

## Revisit When

Revisit this decision if:

- A production customer requires certified BIM coordination as the source of truth.
- IFC product geometry import becomes robust enough to preserve all required semantics.
- Benchmarks show the internal engine cannot scale even with spatial indexes and broad-phase filtering.
- A third-party clash engine has a stable Python adapter and maps results back to Tuba entity refs reliably.

