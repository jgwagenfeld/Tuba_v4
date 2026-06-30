# Expansion Aware Autorouting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Tuba autorouting from shortest clash-free centerlines to corridor-aware, expansion-loop-aware routing that can reserve physical space and rank candidates with thermal stress, nozzle reaction, support, and operating-clearance evidence.

**Architecture:** Keep the existing `GridRouter`, `NetworkRouter`, `AutoroutingAgent`, and `SolverLoopScorer` as compatibility surfaces. Add structured routing-space types, explicit thermal route requirements, expansion-loop candidate generation, and solver acceptance criteria around them. The low-level grid remains a deterministic candidate source; hot-line routing becomes a hybrid search over direct routes, corridor-guided routes, and generated expansion-loop route families.

**Tech Stack:** Python dataclasses, existing `unittest` style, `numpy`, existing `TubaModel`, existing `CodeAsterSolver`, existing ASME B31.3 evaluator, existing visualization scene bundle format.

---

## Scope Check

This is one feature area, but it has independently shippable layers:

1. Structured routing spaces and corridor penalties.
2. Thermal route requirements and expansion-loop geometry generation.
3. Hybrid candidate generation that combines grid routes and loop templates.
4. Solver-driven acceptance and re-ranking.
5. Multi-pipe coordination with reserved loop envelopes.
6. Reports, examples, and documentation.

Do not implement this as one commit. Each task below should pass focused tests before moving to the next task.

## Non-Goals

- Do not remove `GridRouter`; it remains the deterministic baseline.
- Do not require Code_Aster to be installed for basic route generation.
- Do not claim stress signoff from geometry heuristics alone.
- Do not model nonlinear friction/contact in the first implementation.
- Do not make IFC import/export part of the inner routing loop.
- Do not use LLM-generated routes as authoritative geometry without typed validation.

## Existing Source Anchors

- `tuba/routing/types.py` defines route requests, constraints, and cost weights.
- `tuba/routing/grid.py` builds occupancy and penalty grids.
- `tuba/routing/astar.py` owns the current deterministic A* route generation.
- `tuba/routing/network.py` routes multiple pipes in priority order and repairs conflicts.
- `tuba/routing/solver_loop.py` exports or runs solver studies and attaches compliance, reactions, and displacements.
- `tuba/routing/report.py` writes route review Markdown and JSON.
- `docs/future_ready_architecture.md` documents operating-state clash and solver artifact context.

## Files To Create Or Modify

- Create `tuba/routing/spaces.py`  
  Owns `RoutingZone`, `RoutingSpace`, zone validation, and point/segment classification.

- Modify `tuba/routing/types.py`  
  Add optional `routing_space`, `thermal_requirements`, and `solver_acceptance` fields while preserving existing defaults and JSON conversion behavior.

- Modify `tuba/routing/grid.py`  
  Apply forbidden zones as blocked cells, preferred/corridor zones as penalties, and required corridor policies as neighbor filters.

- Create `tests/test_routing_spaces.py`  
  Covers structured zone validation, point classification, and grid blocking/penalty behavior.

- Create `tuba/routing/thermal.py`  
  Owns `ThermalRouteRequirement`, `ExpansionLoopSpec`, free-expansion estimates, loop-size heuristics, and solver acceptance criteria.

- Create `tests/test_routing_thermal.py`  
  Covers thermal expansion estimates, loop spec validation, and acceptance criteria defaults.

- Create `tuba/routing/expansion.py`  
  Owns `ExpansionLoopGenerator`, route-family generation, loop envelope reservation, and candidate metadata.

- Create `tests/test_routing_expansion.py`  
  Covers U-loop and Z-loop candidate generation, envelope metadata, and corridor fit rejection.

- Create `tuba/routing/hybrid.py`  
  Owns `ExpansionAwareRouter`, which combines `GridRouter` results with expansion-loop candidates and delegates final ranking.

- Modify `tuba/routing/__init__.py`  
  Export new public routing-space, thermal, expansion, and hybrid-router interfaces.

- Modify `tuba/routing/solver_loop.py`  
  Add solver acceptance evaluation and route candidate re-ranking by compliance, reactions, displacement, and operating clearance.

- Modify `tuba/routing/network.py`  
  Reserve accepted expansion-loop envelopes before routing later pipes and report corridor capacity conflicts.

- Modify `tuba/routing/report.py`  
  Report routing-space use, expansion-loop geometry, thermal assumptions, solver acceptance, reactions, displacements, and known open review items.

- Create `examples/autoroute_expansion_loop.py`  
  Demonstrates a hot line that requires an expansion loop and exports candidate studies.

- Modify `README.md` and `docs/future_ready_architecture.md`  
  Document corridor-aware and expansion-aware autorouting scope, required review workflow, and limitations.

Use this command for the full Python test baseline after every implementation task:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected result:

```text
OK
```

---

### Task 1: Structured Routing Spaces

**Files:**
- Create: `tuba/routing/spaces.py`
- Modify: `tuba/routing/types.py`
- Modify: `tuba/routing/__init__.py`
- Test: `tests/test_routing_spaces.py`

- [ ] **Step 1: Write failing tests for zone validation and point classification**

Add this test file:

```python
import unittest

from tuba.routing.spaces import RoutingSpace, RoutingZone


class TestRoutingSpaces(unittest.TestCase):
    def test_point_classification_prefers_most_specific_zone(self):
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    id="rack_volume",
                    kind="allowed",
                    min_point=(0.0, 0.0, 0.0),
                    max_point=(10.0, 2.0, 2.0),
                ),
                RoutingZone(
                    id="maintenance_gap",
                    kind="forbidden",
                    min_point=(4.0, 0.0, 0.0),
                    max_point=(5.0, 2.0, 2.0),
                ),
            ),
            policy="require_allowed",
        )

        self.assertEqual(space.classify_point((1.0, 1.0, 1.0)).kind, "allowed")
        self.assertEqual(space.classify_point((4.5, 1.0, 1.0)).kind, "forbidden")
        self.assertIsNone(space.classify_point((12.0, 1.0, 1.0)))

    def test_invalid_zone_bounds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_point must be greater"):
            RoutingZone(
                id="bad",
                kind="allowed",
                min_point=(1.0, 0.0, 0.0),
                max_point=(1.0, 2.0, 2.0),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_spaces -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tuba.routing.spaces'`.

- [ ] **Step 3: Add routing-space dataclasses**

Create `tuba/routing/spaces.py` with this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from tuba.routing.types import Point3D


ZoneKind = Literal["allowed", "preferred", "forbidden", "reserved"]
RoutingSpacePolicy = Literal["unrestricted", "prefer_allowed", "require_allowed"]


@dataclass(frozen=True)
class RoutingZone:
    id: str
    kind: ZoneKind
    min_point: Point3D
    max_point: Point3D
    penalty: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        lo = np.asarray(self.min_point, dtype=float)
        hi = np.asarray(self.max_point, dtype=float)
        if lo.shape != (3,) or hi.shape != (3,):
            raise ValueError("RoutingZone points must be 3D.")
        if np.any(hi <= lo):
            raise ValueError("RoutingZone max_point must be greater than min_point on all axes.")

    def contains_point(self, point: Point3D) -> bool:
        p = np.asarray(point, dtype=float)
        lo = np.asarray(self.min_point, dtype=float)
        hi = np.asarray(self.max_point, dtype=float)
        return bool(np.all(p >= lo - 1e-9) and np.all(p <= hi + 1e-9))

    @property
    def volume(self) -> float:
        span = np.asarray(self.max_point, dtype=float) - np.asarray(self.min_point, dtype=float)
        return float(np.prod(span))


@dataclass(frozen=True)
class RoutingSpace:
    id: str
    zones: tuple[RoutingZone, ...] = ()
    policy: RoutingSpacePolicy = "unrestricted"
    metadata: dict[str, Any] = field(default_factory=dict)

    def classify_point(self, point: Point3D) -> RoutingZone | None:
        matches = [zone for zone in self.zones if zone.contains_point(point)]
        if not matches:
            return None
        priority = {"forbidden": 0, "reserved": 1, "preferred": 2, "allowed": 3}
        return sorted(matches, key=lambda zone: (priority[zone.kind], zone.volume))[0]

    def point_allowed(self, point: Point3D) -> bool:
        zone = self.classify_point(point)
        if zone is not None and zone.kind in ("forbidden", "reserved"):
            return False
        if self.policy == "require_allowed":
            return zone is not None and zone.kind in ("allowed", "preferred")
        return True
```

Modify `tuba/routing/types.py` only after `PipeRouteRequest.preferred_zones`:

```python
    routing_space: Any | None = None
```

This uses `Any` to avoid a circular import between `types.py` and `spaces.py`.

Modify `tuba/routing/__init__.py` to export:

```python
from tuba.routing.spaces import RoutingSpace, RoutingZone
```

- [ ] **Step 4: Run focused tests and full routing type tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_spaces tests.test_routing_types -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/spaces.py tuba/routing/types.py tuba/routing/__init__.py tests/test_routing_spaces.py
git commit -m "feat: add structured routing spaces"
```

---

### Task 2: Corridor Blocking And Penalties In The Grid

**Files:**
- Modify: `tuba/routing/grid.py`
- Test: `tests/test_routing_spaces.py`
- Test: `tests/test_routing_grid.py`

- [ ] **Step 1: Add failing grid tests for forbidden and preferred zones**

Append these tests to `tests/test_routing_spaces.py`:

```python
from tuba import Model
from tuba.routing.grid import RoutingGrid
from tuba.routing.spaces import RoutingSpace, RoutingZone
from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingGridSpec


def _zone_model():
    model = Model("Zones")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    return model


class TestRoutingGridZones(unittest.TestCase):
    def test_forbidden_zone_blocks_grid_cells(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(RoutingZone("forbidden_gap", "forbidden", (1.0, -1.0, -1.0), (2.0, 1.0, 1.0)),),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertTrue(grid.is_blocked(grid.world_to_index((1.5, 0.0, 0.0))))

    def test_preferred_zone_reduces_grid_penalty(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(RoutingZone("rack_lane", "preferred", (0.0, -0.5, -0.5), (3.0, 0.5, 0.5), penalty=-2.0),),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertLess(grid.penalty(grid.world_to_index((1.0, 0.0, 0.0))), 0.0)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_spaces -v
```

Expected: FAIL because `RoutingGrid.from_model()` does not apply `request.routing_space`.

- [ ] **Step 3: Apply routing-space masks in `RoutingGrid.from_model()`**

Add this call after obstacle and existing-pipe marking, before endpoint unblocking:

```python
        if request.routing_space is not None:
            grid._apply_routing_space(request.routing_space)
```

Add this method to `RoutingGrid`:

```python
    def _apply_routing_space(self, space) -> None:
        for ix in range(self.shape[0]):
            for iy in range(self.shape[1]):
                for iz in range(self.shape[2]):
                    idx = (ix, iy, iz)
                    point = self.index_to_world(idx)
                    zone = space.classify_point(point)
                    if zone is None:
                        if space.policy == "require_allowed":
                            self.occupancy[idx] = True
                        continue
                    if zone.kind in ("forbidden", "reserved"):
                        self.occupancy[idx] = True
                    elif zone.kind == "preferred":
                        self.penalties[idx] += float(zone.penalty)
                    elif zone.kind == "allowed" and space.policy == "prefer_allowed":
                        self.penalties[idx] += float(zone.penalty)
```

- [ ] **Step 4: Run routing-space and routing-grid tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_spaces tests.test_routing_grid -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/grid.py tests/test_routing_spaces.py
git commit -m "feat: apply corridor zones to routing grid"
```

---

### Task 3: Thermal Route Requirement Types

**Files:**
- Create: `tuba/routing/thermal.py`
- Modify: `tuba/routing/types.py`
- Modify: `tuba/routing/__init__.py`
- Test: `tests/test_routing_thermal.py`

- [ ] **Step 1: Write failing tests for thermal expansion and acceptance defaults**

Create `tests/test_routing_thermal.py`:

```python
import unittest

from tuba.routing.thermal import SolverAcceptanceCriteria, ThermalRouteRequirement, estimate_free_expansion


class TestRoutingThermal(unittest.TestCase):
    def test_free_expansion_uses_alpha_delta_t_and_length(self):
        requirement = ThermalRouteRequirement(
            design_temperature_c=180.0,
            reference_temperature_c=20.0,
            line_length_m=25.0,
            thermal_expansion_coefficient=12e-6,
        )

        self.assertAlmostEqual(estimate_free_expansion(requirement), 0.048)

    def test_solver_acceptance_has_strict_hot_line_defaults(self):
        criteria = SolverAcceptanceCriteria.hot_line_defaults()

        self.assertEqual(criteria.max_expansion_ratio, 1.0)
        self.assertGreater(criteria.max_anchor_reaction_n, 0.0)
        self.assertGreater(criteria.max_operating_clearance_violation_m, -1e-12)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_thermal -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tuba.routing.thermal'`.

- [ ] **Step 3: Add thermal dataclasses and helpers**

Create `tuba/routing/thermal.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


LoopFamily = Literal["u_loop", "z_loop", "offset_loop"]


@dataclass(frozen=True)
class ThermalRouteRequirement:
    design_temperature_c: float
    reference_temperature_c: float
    line_length_m: float
    thermal_expansion_coefficient: float
    requires_expansion_loop: bool = True
    preferred_loop_families: tuple[LoopFamily, ...] = ("u_loop", "z_loop")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def delta_t_c(self) -> float:
        return float(self.design_temperature_c - self.reference_temperature_c)


@dataclass(frozen=True)
class ExpansionLoopSpec:
    family: LoopFamily
    width_m: float
    depth_m: float
    plane: Literal["xy", "xz", "yz"] = "xy"
    min_clearance_m: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width_m <= 0.0 or self.depth_m <= 0.0:
            raise ValueError("Expansion loop width_m and depth_m must be positive.")


@dataclass(frozen=True)
class SolverAcceptanceCriteria:
    max_expansion_ratio: float = 1.0
    max_sustained_ratio: float = 1.0
    max_anchor_reaction_n: float = 50_000.0
    max_nozzle_reaction_n: float = 10_000.0
    max_operating_displacement_m: float = 0.25
    max_operating_clearance_violation_m: float = 0.0

    @classmethod
    def hot_line_defaults(cls) -> "SolverAcceptanceCriteria":
        return cls()


def estimate_free_expansion(requirement: ThermalRouteRequirement) -> float:
    return (
        float(requirement.thermal_expansion_coefficient)
        * float(requirement.delta_t_c)
        * float(requirement.line_length_m)
    )
```

Modify `PipeRouteRequest` in `tuba/routing/types.py` after `routing_space`:

```python
    thermal_requirements: Any | None = None
    solver_acceptance: Any | None = None
```

Modify `tuba/routing/__init__.py` to export:

```python
from tuba.routing.thermal import (
    ExpansionLoopSpec,
    SolverAcceptanceCriteria,
    ThermalRouteRequirement,
    estimate_free_expansion,
)
```

- [ ] **Step 4: Run thermal and type tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_thermal tests.test_routing_types -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/thermal.py tuba/routing/types.py tuba/routing/__init__.py tests/test_routing_thermal.py
git commit -m "feat: add thermal route requirements"
```

---

### Task 4: Expansion Loop Candidate Generation

**Files:**
- Create: `tuba/routing/expansion.py`
- Test: `tests/test_routing_expansion.py`

- [ ] **Step 1: Write failing tests for U-loop generation**

Create `tests/test_routing_expansion.py`:

```python
import unittest

from tuba import Model
from tuba.routing.expansion import ExpansionLoopGenerator
from tuba.routing.thermal import ExpansionLoopSpec, ThermalRouteRequirement
from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingConstraints


def _model():
    model = Model("Expansion")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    return model


class TestRoutingExpansion(unittest.TestCase):
    def test_u_loop_candidate_has_reserved_envelope_metadata(self):
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        candidates = ExpansionLoopGenerator(
            loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0, plane="xy"),)
        ).generate(_model(), request)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].metadata["route_family"], "u_loop")
        self.assertIn("reserved_envelope", candidates[0].metadata)
        self.assertGreater(len(candidates[0].points), 4)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_expansion -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tuba.routing.expansion'`.

- [ ] **Step 3: Add deterministic U-loop generation**

Create `tuba/routing/expansion.py` with this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tuba.model import TubaModel
from tuba.routing.postprocess import build_segments, validate_bend_geometry
from tuba.routing.thermal import ExpansionLoopSpec
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, Point3D


@dataclass(frozen=True)
class ExpansionLoopGenerator:
    loop_specs: tuple[ExpansionLoopSpec, ...]

    def generate(self, model: TubaModel, request: PipeRouteRequest) -> list[PipeRouteCandidate]:
        if request.thermal_requirements is None:
            return []
        candidates: list[PipeRouteCandidate] = []
        for spec in self.loop_specs:
            if spec.family == "u_loop":
                candidates.append(self._u_loop_candidate(model, request, spec))
        return candidates

    def _u_loop_candidate(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        spec: ExpansionLoopSpec,
    ) -> PipeRouteCandidate:
        start = np.asarray(request.start.point, dtype=float)
        goal = np.asarray(request.goal.point, dtype=float)
        axis = goal - start
        if np.linalg.norm(axis) <= 1e-12:
            raise ValueError("Expansion loop endpoints must be distinct.")
        mid = start + 0.5 * axis
        half_width = spec.width_m / 2.0
        if spec.plane == "xy":
            p1 = mid + np.array([-half_width, 0.0, 0.0])
            p2 = p1 + np.array([0.0, spec.depth_m, 0.0])
            p3 = mid + np.array([half_width, spec.depth_m, 0.0])
            p4 = mid + np.array([half_width, 0.0, 0.0])
        elif spec.plane == "xz":
            p1 = mid + np.array([-half_width, 0.0, 0.0])
            p2 = p1 + np.array([0.0, 0.0, spec.depth_m])
            p3 = mid + np.array([half_width, 0.0, spec.depth_m])
            p4 = mid + np.array([half_width, 0.0, 0.0])
        else:
            p1 = mid + np.array([0.0, -half_width, 0.0])
            p2 = p1 + np.array([spec.depth_m, 0.0, 0.0])
            p3 = mid + np.array([spec.depth_m, half_width, 0.0])
            p4 = mid + np.array([0.0, half_width, 0.0])
        points = [_tuple(start), _tuple(p1), _tuple(p2), _tuple(p3), _tuple(p4), _tuple(goal)]
        diagnostics = validate_bend_geometry(points, request.constraints)
        candidate = PipeRouteCandidate(
            request_id=request.id,
            points=points,
            segments=build_segments(points, request.constraints),
            cost=0.0,
            cost_breakdown={},
            diagnostics=diagnostics,
            is_valid=not diagnostics,
            metadata={
                "route_family": spec.family,
                "expansion_loop": {
                    "width_m": spec.width_m,
                    "depth_m": spec.depth_m,
                    "plane": spec.plane,
                },
                "reserved_envelope": _bounds(points, request.constraints.clearance),
            },
        )
        return candidate


def _tuple(point: np.ndarray) -> Point3D:
    return (float(point[0]), float(point[1]), float(point[2]))


def _bounds(points: list[Point3D], clearance: float) -> dict[str, Point3D]:
    arr = np.asarray(points, dtype=float)
    lo = arr.min(axis=0) - float(clearance)
    hi = arr.max(axis=0) + float(clearance)
    return {"min_point": _tuple(lo), "max_point": _tuple(hi)}
```

- [ ] **Step 4: Run expansion tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_expansion -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/expansion.py tests/test_routing_expansion.py
git commit -m "feat: generate expansion loop route candidates"
```

---

### Task 5: Expansion-Aware Hybrid Router

**Files:**
- Create: `tuba/routing/hybrid.py`
- Modify: `tuba/routing/__init__.py`
- Test: `tests/test_routing_expansion.py`

- [ ] **Step 1: Write failing test for hybrid candidate composition**

Append this test:

```python
from tuba.routing.astar import GridRouter
from tuba.routing.hybrid import ExpansionAwareRouter
from tuba.routing.types import RoutingGridSpec


class TestExpansionAwareRouter(unittest.TestCase):
    def test_hybrid_router_returns_grid_and_loop_candidates(self):
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (10.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
            thermal_requirements=ThermalRouteRequirement(180.0, 20.0, 10.0, 12e-6),
        )

        result = ExpansionAwareRouter(
            base_router=GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0), candidate_count=1),
            loop_generator=ExpansionLoopGenerator(
                loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0),)
            ),
        ).route(_model(), request)

        families = {candidate.metadata.get("route_family") for candidate in result.candidates}
        self.assertIn("grid", families)
        self.assertIn("u_loop", families)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_expansion.TestExpansionAwareRouter -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tuba.routing.hybrid'`.

- [ ] **Step 3: Add `ExpansionAwareRouter`**

Create `tuba/routing/hybrid.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from tuba.model import TubaModel
from tuba.routing.astar import GridRouter
from tuba.routing.cost import score_candidate
from tuba.routing.expansion import ExpansionLoopGenerator
from tuba.routing.types import PipeRouteRequest, PipeRouteResult


@dataclass
class ExpansionAwareRouter:
    base_router: GridRouter
    loop_generator: ExpansionLoopGenerator

    def route(self, model: TubaModel, request: PipeRouteRequest) -> PipeRouteResult:
        base = self.base_router.route(model, request)
        candidates = list(base.candidates)
        for candidate in candidates:
            candidate.metadata.setdefault("route_family", "grid")
        loop_candidates = self.loop_generator.generate(model, request)
        for candidate in loop_candidates:
            score_candidate(candidate, model, request)
        candidates.extend(loop_candidates)
        selected_index = _best_valid_candidate_index(candidates)
        return PipeRouteResult(
            request=request,
            candidates=candidates,
            selected_index=selected_index,
            diagnostics=list(base.diagnostics),
        )


def _best_valid_candidate_index(candidates):
    valid = [(idx, candidate.cost) for idx, candidate in enumerate(candidates) if candidate.is_valid]
    if not valid:
        return None
    return min(valid, key=lambda item: (item[1], item[0]))[0]
```

Modify `tuba/routing/__init__.py`:

```python
from tuba.routing.hybrid import ExpansionAwareRouter
```

- [ ] **Step 4: Run expansion tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_expansion -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/hybrid.py tuba/routing/__init__.py tests/test_routing_expansion.py
git commit -m "feat: add expansion aware hybrid router"
```

---

### Task 6: Solver Acceptance Criteria And Re-Ranking

**Files:**
- Modify: `tuba/routing/solver_loop.py`
- Test: `tests/test_routing_solver_loop.py`

- [ ] **Step 1: Write failing test for acceptance metadata**

Add this test to `tests/test_routing_solver_loop.py`:

```python
from dataclasses import replace

from tuba.routing.thermal import SolverAcceptanceCriteria


class RejectingComplianceReport:
    overall_pass = False
    worst_sustained_ratio = 0.1
    worst_expansion_ratio = 0.75
    results = []


class RejectingComplianceEvaluator:
    def evaluate(self, model, results):
        return RejectingComplianceReport()


def test_solver_loop_marks_candidate_rejected_by_expansion_ratio(self):
    model, request, candidate = _solver_loop_fixture()
    request = replace(
        request,
        solver_acceptance=SolverAcceptanceCriteria(max_expansion_ratio=0.5),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        ranked = SolverLoopScorer(
            solver_factory=PassingSolver,
            compliance_evaluator=RejectingComplianceEvaluator(),
        ).score_candidates(
            model,
            request,
            [candidate],
            SolverLoopConfig(
                run_solver=True,
                export_study=True,
                max_solver_candidates=1,
                work_root=tmpdir,
                load_case="Hot",
            ),
        )

    self.assertFalse(ranked[0].metadata["solver_acceptance"]["accepted"])
    self.assertIn("expansion_ratio", ranked[0].metadata["solver_acceptance"]["failed_checks"])
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop -v
```

Expected: FAIL because solver acceptance metadata is not attached.

- [ ] **Step 3: Add acceptance evaluation**

Pass `request.solver_acceptance` into `_attach_solver_result_metadata()` by changing the call:

```python
                    _attach_solver_result_metadata(
                        candidate,
                        temp_model,
                        results,
                        self.compliance_evaluator,
                        request.solver_acceptance,
                    )
```

Change the helper signature:

```python
def _attach_solver_result_metadata(
    candidate: PipeRouteCandidate,
    model: TubaModel,
    results: FEAResults,
    evaluator: ASMEB313Evaluator,
    criteria=None,
) -> None:
```

Add this helper:

```python
def _attach_solver_acceptance(candidate, criteria) -> None:
    if criteria is None:
        return
    compliance = candidate.metadata.get("compliance", {})
    failed: list[str] = []
    if compliance.get("worst_expansion_ratio", 0.0) > criteria.max_expansion_ratio:
        failed.append("expansion_ratio")
    if compliance.get("worst_sustained_ratio", 0.0) > criteria.max_sustained_ratio:
        failed.append("sustained_ratio")
    max_reaction = 0.0
    for vector in candidate.metadata.get("reactions", {}).values():
        force = vector[:3]
        max_reaction = max(max_reaction, float(sum(component * component for component in force) ** 0.5))
    if max_reaction > criteria.max_anchor_reaction_n:
        failed.append("anchor_reaction")
    candidate.metadata["solver_acceptance"] = {
        "accepted": not failed,
        "failed_checks": failed,
        "max_reaction_n": max_reaction,
    }
    if failed:
        candidate.is_valid = False
        candidate.diagnostics.append("Solver acceptance failed: " + ", ".join(failed))
```

Call `_attach_solver_acceptance(candidate, criteria)` at the end of `_attach_solver_result_metadata()`.

- [ ] **Step 4: Run solver-loop tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/solver_loop.py tests/test_routing_solver_loop.py
git commit -m "feat: score route candidates with solver acceptance"
```

---

### Task 7: Reserved Loop Envelopes In Network Routing

**Files:**
- Modify: `tuba/routing/network.py`
- Test: `tests/test_routing_network.py`

- [ ] **Step 1: Write failing test for reserved envelope conflicts**

Add this test to `tests/test_routing_network.py`:

```python
def test_network_reports_reserved_expansion_envelope_conflict(self):
    first = PipeRouteCandidate(
        request_id="HOT-100",
        points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
        segments=[],
        cost=1.0,
        cost_breakdown={},
        metadata={
            "route_family": "u_loop",
            "reserved_envelope": {"min_point": (1.0, -1.0, -1.0), "max_point": (3.0, 1.0, 1.0)},
        },
    )
    second = PipeRouteCandidate(
        request_id="COLD-200",
        points=[(2.0, -2.0, 0.0), (2.0, 2.0, 0.0)],
        segments=[],
        cost=1.0,
        cost_breakdown={},
    )

    conflicts = detect_candidate_conflicts({"HOT-100": first, "COLD-200": second}, clearance=0.0)

    self.assertEqual(conflicts[0]["type"], "reserved_envelope")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_network -v
```

Expected: FAIL because `detect_candidate_conflicts()` only checks centerline segment distances.

- [ ] **Step 3: Add reserved-envelope conflict detection**

In `detect_candidate_conflicts()`, before segment-distance checks for a pair, add:

```python
            envelope_conflict = _reserved_envelope_conflict(id_a, cand_a, id_b, cand_b)
            if envelope_conflict is not None:
                conflicts.append(envelope_conflict)
                continue
```

Add helpers:

```python
def _reserved_envelope_conflict(id_a, cand_a, id_b, cand_b):
    for owner_id, owner, other_id, other in ((id_a, cand_a, id_b, cand_b), (id_b, cand_b, id_a, cand_a)):
        envelope = owner.metadata.get("reserved_envelope")
        if not envelope:
            continue
        lo = np.asarray(envelope["min_point"], dtype=float)
        hi = np.asarray(envelope["max_point"], dtype=float)
        for seg_idx, (p0, p1) in enumerate(zip(other.points, other.points[1:])):
            if _segment_intersects_box(np.asarray(p0, dtype=float), np.asarray(p1, dtype=float), lo, hi):
                return {
                    "type": "reserved_envelope",
                    "pipes": (owner_id, other_id),
                    "segments": (None, seg_idx),
                    "distance": 0.0,
                    "required_clearance": 0.0,
                    "envelope": envelope,
                }
    return None


def _segment_intersects_box(p0, p1, lo, hi) -> bool:
    direction = p1 - p0
    t_min = 0.0
    t_max = 1.0
    for axis in range(3):
        if abs(direction[axis]) <= 1e-12:
            if p0[axis] < lo[axis] or p0[axis] > hi[axis]:
                return False
            continue
        inv = 1.0 / direction[axis]
        t1 = (lo[axis] - p0[axis]) * inv
        t2 = (hi[axis] - p0[axis]) * inv
        t_min = max(t_min, min(t1, t2))
        t_max = min(t_max, max(t1, t2))
        if t_min > t_max:
            return False
    return True
```

- [ ] **Step 4: Run network tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_network -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/network.py tests/test_routing_network.py
git commit -m "feat: reserve expansion loop envelopes in network routing"
```

---

### Task 8: Route Reports For Expansion Review

**Files:**
- Modify: `tuba/routing/report.py`
- Test: `tests/test_routing_report.py`

- [ ] **Step 1: Write failing report test**

Add this test to `tests/test_routing_report.py`:

```python
def test_writes_expansion_loop_and_solver_acceptance(self):
    request = PipeRouteRequest(
        id="HOT-100",
        start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
        goal=RouteEndpoint(id="B", point=(4.0, 0.0, 0.0)),
        section="PipeSec",
        material="Steel",
        constraints=RoutingConstraints(clearance=0.1),
    )
    candidate = PipeRouteCandidate(
        request_id="HOT-100",
        points=[(0.0, 0.0, 0.0), (2.0, 1.0, 0.0), (4.0, 0.0, 0.0)],
        segments=[
            RouteSegment(start=(0.0, 0.0, 0.0), end=(2.0, 1.0, 0.0), kind="straight"),
            RouteSegment(start=(2.0, 1.0, 0.0), end=(4.0, 0.0, 0.0), kind="straight"),
        ],
        cost=6.0,
        cost_breakdown={"length": 4.5, "bends": 2},
        metadata={
            "route_family": "u_loop",
            "expansion_loop": {"width_m": 2.0, "depth_m": 1.0, "plane": "xy"},
            "solver_acceptance": {"accepted": False, "failed_checks": ["expansion_ratio"]},
        },
    )
    result = PipeRouteResult(request=request, candidates=[candidate], selected_index=0, diagnostics=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = write_route_report(result, tmpdir)
        markdown = report_path.read_text(encoding="utf-8")

    self.assertIn("Route family: `u_loop`", markdown)
    self.assertIn("Expansion loop", markdown)
    self.assertIn("Solver acceptance: `False`", markdown)
    self.assertIn("expansion_ratio", markdown)
```

- [ ] **Step 2: Run the report tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_report -v
```

Expected: FAIL because route-family and solver-acceptance text is missing.

- [ ] **Step 3: Add expansion-report sections**

In the selected-candidate section of `_single_route_markdown()`, add:

```python
        route_family = selected.metadata.get("route_family")
        if route_family:
            lines.append(f"- Route family: `{route_family}`")
        expansion_loop = selected.metadata.get("expansion_loop")
        if expansion_loop:
            lines.append("- Expansion loop:")
            lines.append(f"  - Width m: `{expansion_loop.get('width_m')}`")
            lines.append(f"  - Depth m: `{expansion_loop.get('depth_m')}`")
            lines.append(f"  - Plane: `{expansion_loop.get('plane')}`")
        solver_acceptance = selected.metadata.get("solver_acceptance")
        if solver_acceptance:
            lines.append(f"- Solver acceptance: `{solver_acceptance.get('accepted')}`")
            lines.append(f"- Failed solver checks: `{solver_acceptance.get('failed_checks', [])}`")
```

- [ ] **Step 4: Run report tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_report -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tuba/routing/report.py tests/test_routing_report.py
git commit -m "feat: report expansion routing review data"
```

---

### Task 9: Example Hot Line With Expansion Loop

**Files:**
- Create: `examples/autoroute_expansion_loop.py`
- Modify: `tests/test_examples.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing example test**

Add `examples/autoroute_expansion_loop.py` to the example allowlist or smoke list in `tests/test_examples.py` using the same pattern as `autoroute_single_pipe.py`.

Expected command in the test:

```powershell
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

- [ ] **Step 2: Run the example test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_examples -v
```

Expected: FAIL because the new example file does not exist.

- [ ] **Step 3: Add the expansion-loop example**

Create `examples/autoroute_expansion_loop.py`:

```python
from __future__ import annotations

from tuba import Model
from tuba.routing import (
    AutoroutingAgent,
    ExpansionAwareRouter,
    ExpansionLoopGenerator,
    ExpansionLoopSpec,
    GridRouter,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
    SolverAcceptanceCriteria,
    ThermalRouteRequirement,
)
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.routing.types import PipeRouteRequest


def build_model() -> Model:
    model = Model("ExpansionLoopDemo")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6, allowable_stress={20.0: 140e6, 180.0: 125e6})
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.add_obstacle(
        id="equipment_keepout",
        type="cuboid",
        min_point=(4.0, -0.4, -0.4),
        max_point=(5.0, 0.4, 0.8),
    )
    return model


def main() -> None:
    model = build_model()
    request = PipeRouteRequest(
        id="HOT-100",
        start=RouteEndpoint("equipment_nozzle", (0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0), min_straight=0.5),
        goal=RouteEndpoint("rack_tie_in", (10.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0), min_straight=0.5),
        section="DN100",
        material="steel",
        constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.3),
        thermal_requirements=ThermalRouteRequirement(
            design_temperature_c=180.0,
            reference_temperature_c=20.0,
            line_length_m=10.0,
            thermal_expansion_coefficient=12e-6,
        ),
        solver_acceptance=SolverAcceptanceCriteria.hot_line_defaults(),
    )
    router = ExpansionAwareRouter(
        base_router=GridRouter(RoutingGridSpec(cell_size=0.5, margin=2.0), candidate_count=2),
        loop_generator=ExpansionLoopGenerator(
            loop_specs=(ExpansionLoopSpec("u_loop", width_m=2.0, depth_m=1.0, plane="xy"),)
        ),
    )
    run = AutoroutingAgent(
        router=router,
        solver_config=SolverLoopConfig(run_solver=False, export_study=True),
        output_root="routing_reports",
    ).route_pipe(model, request, apply=False)
    print(run.report_dir)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the example**

Run:

```powershell
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Expected: prints a path below `routing_reports`.

- [ ] **Step 5: Update README**

Add this command below the other autorouting examples:

```powershell
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Add one paragraph:

```markdown
For hot lines, use `ExpansionAwareRouter` with explicit `ThermalRouteRequirement`
and `SolverAcceptanceCriteria`. The router generates direct and expansion-loop
families, exports reviewable solver studies, and reports whether the selected
candidate still needs stress or reaction review.
```

- [ ] **Step 6: Run example tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_examples -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add examples/autoroute_expansion_loop.py tests/test_examples.py README.md
git commit -m "docs: add expansion loop autorouting example"
```

---

### Task 10: Architecture Documentation And Review Checklist

**Files:**
- Modify: `docs/future_ready_architecture.md`
- Create: `docs/architecture/expansion-aware-autorouting.md`
- Test: no automated test

- [ ] **Step 1: Create architecture note**

Create `docs/architecture/expansion-aware-autorouting.md` with this structure:

```markdown
# Expansion Aware Autorouting

## Decision

Tuba treats hot-line routing as a solver-reviewed candidate-generation problem,
not as shortest-path search. The grid router remains the deterministic baseline,
but expansion-aware routing adds explicit routing spaces, loop route families,
reserved loop envelopes, and solver acceptance criteria.

## Required Inputs

- Endpoints with optional approach directions and minimum straight lengths.
- Pipe section, material, insulation, and clearance.
- Routing space with allowed, preferred, forbidden, and reserved zones.
- Thermal route requirement with design temperature, reference temperature,
  effective line length, and expansion coefficient.
- Solver acceptance criteria for expansion stress ratio, sustained stress ratio,
  anchor reactions, nozzle reactions, displacement, and operating clearance.

## Review Outputs

- Candidate route family and centerline points.
- Expansion-loop dimensions and reserved envelope.
- Corridor and keepout conflicts.
- Code_Aster study path for each reviewed candidate.
- ASME sustained and expansion ratios when solver results are available.
- Reaction and displacement summaries when solver results are available.
- Open engineering review items.

## Limitations

- First implementation uses linear envelope reservation.
- Solver execution remains optional.
- Nonlinear friction, support gaps, and lift-off require later solver and support-model upgrades.
- Final construction routing still requires engineer review.
```

- [ ] **Step 2: Link from future-ready architecture**

Add a short section to `docs/future_ready_architecture.md` near the routing and solver architecture discussion:

```markdown
### Expansion Aware Autorouting

Hot-line routing needs explicit expansion-loop space, not only clash-free
shortest paths. The implementation plan is to combine routing spaces, generated
loop route families, reserved envelopes, and solver acceptance criteria. See
`docs/architecture/expansion-aware-autorouting.md`.
```

- [ ] **Step 3: Run a documentation sanity check**

Run:

```powershell
rg -n "Expansion Aware Autorouting|expansion-aware-autorouting|SolverAcceptanceCriteria" docs README.md
```

Expected: prints matches from the new architecture note and linked docs.

- [ ] **Step 4: Commit**

```powershell
git add docs/architecture/expansion-aware-autorouting.md docs/future_ready_architecture.md
git commit -m "docs: document expansion aware autorouting architecture"
```

---

## Verification Before Completion

Run these commands after all tasks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
.\.venv\Scripts\python.exe examples\autoroute_network.py
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
rg -n "ExpansionAwareRouter|ThermalRouteRequirement|RoutingSpace|SolverAcceptanceCriteria" tuba tests examples docs README.md
```

Expected results:

```text
All unit tests pass.
All three examples write reports below routing_reports/.
The search command finds the public APIs, tests, example, and docs.
```

## Self-Review

- Spec coverage: corridors, forbidden/preferred/reserved zones, expansion loops, thermal requirements, solver scoring, network reservation, reports, and examples are each covered by a task.
- Placeholder scan: no step relies on unspecified behavior; each code-changing step names the file and expected API.
- Type consistency: `RoutingSpace`, `RoutingZone`, `ThermalRouteRequirement`, `ExpansionLoopSpec`, `SolverAcceptanceCriteria`, `ExpansionLoopGenerator`, and `ExpansionAwareRouter` are introduced before later tasks use them.
