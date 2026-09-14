# User-Facing Piping DSL and Agent Operations

Status: roadmap draft; examples in this document are target API, not current
shipped behavior unless explicitly noted.

## Purpose

Tuba v4 should keep the structured model architecture while recovering the
intuitive parts of the older authoring experience.

The core design is two-layered:

1. A fluent Python DSL for engineers and notebooks.
2. A strict structured operation model for agents, patches, validation, and
   transaction workflows.

Both layers compile into the same `TubaModel`.

## Design Goals

- Preserve v4 internals: explicit `TubaModel`, nodes, elements, supports,
  serialization, validation, solver export, and future patch operations.
- Recover the older user clarity: geometry commands move a cursor, point-property
  commands apply to the current point, and all DOFs are explicit.
- Keep normal Python control flow usable inside `with model.pipe(...) as b:`.
- Avoid hidden global mutable state outside the active builder.
- Avoid ambiguous scalar support definitions where the constrained DOF is not
  visible.
- Give agents a low-ambiguity operation format with discriminated operation
  names instead of heavily overloaded Python methods.
- Treat operating conditions such as pressure and temperature as named
  operations/load cases, not as implicit global state.

## Non-Goals

- Do not recreate v2's global `current_tubapoint` architecture.
- Do not make magical APIs such as `b.block.x.y.rz` the main interface.
- Do not overload `Block(y=-1000)` to mean imposed displacement.
- Do not silently assume spring direction or bend plane.
- Do not require agents to infer intent from permissive Python syntax.
- Do not include a compatibility layer for v2 command names. This is a new v4
  authoring interface, not a source-compatible port.

## Core Mental Model

The user-facing builder owns a current point and current local frame.

```python
with model.pipe(section="DN100", material="Steel") as b:
    b.start([0, 0, 0]).anchor()
    b.run(2.0).guide(axis="x")
    b.run(2.0).spring(y=1.5e6)
```

Each geometry method updates the cursor and `last_node_id`.

Each point-property method applies to `last_node_id`.

Normal Python loops should work naturally:

```python
with model.pipe(section="DN100", material="Steel") as b:
    b.start([0, 0, 0]).anchor()

    for i in range(4):
        b.run(1.0)
        b.block(z=True)

    b.bend_to(radius=0.3, direction=[0, 1, 0])
    b.run(2.0).anchor()
```

## DOF Convention

All support and point-property APIs use the same six DOF names:

```text
x, y, z, rx, ry, rz
```

Meaning depends on the method:

```python
b.block(x=True, y=True, rz=True)
b.spring(y=1.5e6)
b.displace(y=-0.001)
b.force(y=-1000.0)
b.moment(rz=250.0)
```

Boolean convention:

```text
True  = active or blocked
False = inactive or free
None  = unspecified
```

The canonical v4 API should use booleans and explicit numeric component values.
It should not use sentinel strings such as `"x"` for free DOFs.

## Human DSL

### Geometry

Canonical methods:

```python
b.start([0, 0, 0])
b.run(2.0)
b.set_direction([0, 1, 0])
b.end()
```

Bends should use explicit intent methods instead of one overloaded method:

```python
b.bend_to(radius=0.3, direction=[0, 1, 0], mode="intersect")
b.bend_by_orientation(radius=0.3, angle=90.0, orientation=45.0, mode="intersect")
b.bend_in_plane(radius=0.3, angle=90.0, normal=[0, 0, 1], mode="intersect")
```

### Bend Semantics

`bend_to` defines the new pipe direction directly.

```python
b.bend_to(radius=0.3, direction=[0, 1, 0])
```

`bend_by_orientation` follows the v2 mental model:

- The current pipe direction is local X.
- A maintained local reference direction defines orientation zero.
- `angle` is the bend angle away from the current pipe axis.
- `orientation` is the dihedral angle around the current pipe axis.

```python
b.bend_by_orientation(radius=0.3, angle=90.0, orientation=30.0)
```

`bend_in_plane` defines the bend plane by its normal.

```python
b.bend_in_plane(radius=0.3, angle=90.0, normal=[0, 0, 1])
```

`mode` controls whether the previous straight run is adjusted:

```text
intersect = shorten/adjust the previous straight run to the bend tangent point
add       = start the bend at the current point without adjusting previous geometry
```

### Point Properties

Canonical support and point-property methods:

```python
b.anchor()
b.guide(axis="x")
b.rest(y=True)
b.block(x=True, y=True, rz=True)
b.spring(x=0.0, y=1.5e6, z=0.0, rx=0.0, ry=0.0, rz=0.0)
b.hanger(y=1.5e6)
b.mass(50.0)
b.friction(mu=0.3)
b.displace(y=-0.001)
b.force(x=1000.0, y=-500.0)
b.moment(rz=250.0)
```

All methods return `self` so users can chain methods and use loops.

Example:

```python
with model.pipe(section="DN100", material="Steel") as b:
    b.start([0, 0, 0]).anchor()
    b.run(2.0).guide(axis="x")
    b.run(2.0).rest(y=True, friction=0.3)
    b.run(2.0).spring(y=1.5e6)
    b.bend_to(radius=0.3, direction=[0, 1, 0])
    b.run(2.0).block(x=True, y=True, rz=True)
    b.run(2.0).mass(50.0)
    b.end().anchor()
```

### Imposed Displacement

v2 used `Block(y=-1000)` for imposed displacement. v4 should separate these
concepts.

```python
b.block(y=True)
b.displace(y=-0.001)
```

This avoids mixing support state and imposed movement in one argument.

### Reference Frames

Point-property methods may accept a reference:

```python
b.block(y=True, reference="global")
b.spring(y=1.5e6, reference="global")
b.force(y=-1000.0, reference="local")
```

Unsupported references must fail loudly:

```text
ValueError: local spring reference is not implemented
```

Silent fallback to global coordinates is not acceptable.

## Local Physical Properties

Physical properties are part of the model, not part of an operation.
They include section, material, insulation, corrosion allowance, fluid metadata,
groups, tags, support hardware, and local model attributes.

The builder should support local scoping without reintroducing global mutable
state:

```python
with model.pipe(section="DN100", material="Steel", route="main") as b:
    b.start([0, 0, 0]).anchor()

    b.run(2.0).group("inlet")

    with b.section("DN80"):
        b.run(1.5).group("reducer_zone")

    with b.insulation("mineral_wool_50mm"):
        b.run(4.0).group("hot_leg")
```

Direct assignment on the next or last element should also be available:

```python
b.run(2.0, group="inlet")
b.run(4.0).group("heater").tag("critical")
b.last_element().insulation("mineral_wool_50mm")
```

The physical scoping API should be explicit:

```python
with b.section("DN80"):
    ...

with b.material("P265GH"):
    ...

with b.insulation("mineral_wool_50mm"):
    ...

with b.corrosion_allowance(0.001):
    ...
```

Each generated element should store enough placement metadata for later local
assignments:

```text
route
station_start
station_end
groups
tags
section
material
insulation
```

This is what makes local operation fields deterministic. A temperature profile
can target `route="main", start=2.0, end=6.0` because elements know their
station range.

## Operating Scenarios

Temperature, pressure, gravity, wind, and other operating conditions should be
defined as named operations. An operation is an operating state applied to the
same physical model.

Basic operation definition:

```python
model.operation(
    "cold",
    temperature=20.0,
    reference_temperature=20.0,
    pressure=0.0,
    gravity=True,
)

model.operation(
    "hot_operating",
    temperature=180.0,
    reference_temperature=20.0,
    pressure=1.6e6,
    gravity=True,
)
```

The physical pipe route stays the same. Each operation changes the state used
for solver export and compliance evaluation.

Temperature sweeps should be first-class:

```python
model.temperature_sweep(
    name="startup_ramp",
    temperatures=[20.0, 60.0, 100.0, 140.0, 180.0],
    reference_temperature=20.0,
    pressure=1.6e6,
    gravity=True,
)
```

For time-dependent operating states:

```python
model.transient_operation(
    "thermal_cycle",
    steps=[
        {"time": 0.0, "temperature": 20.0, "pressure": 0.0},
        {"time": 600.0, "temperature": 120.0, "pressure": 1.0e6},
        {"time": 1200.0, "temperature": 180.0, "pressure": 1.6e6},
        {"time": 2400.0, "temperature": 80.0, "pressure": 0.8e6},
    ],
    reference_temperature=20.0,
    gravity=True,
)
```

The initial implementation may compile sweeps and transient operations into
multiple static load cases. A later solver backend can treat them as true
transient inputs if supported.

### Local Operating Fields

Most examples can use one operation temperature for the whole model. Real
systems need temperature, pressure, fluid density, wind, and other state fields
to vary by group, station range, or profile.

Use groups for that:

```python
with model.pipe(section="DN100", material="Steel") as b:
    b.start([0, 0, 0]).anchor()
    b.run(4.0).group("supply")
    b.bend_to(radius=0.3, direction=[0, 1, 0])
    b.run(4.0).group("return")

model.operation(
    "mixed_temperature",
    temperature={
        "supply": 180.0,
        "return": 95.0,
    },
    reference_temperature=20.0,
    pressure=1.6e6,
)
```

Use station ranges for gradients along a route:

```python
op = model.operation("startup", reference_temperature=20.0, gravity=True)

op.temperature.range(route="main", start=0.0, end=2.0, value=60.0)
op.temperature.range(route="main", start=2.0, end=6.0, value=180.0)
op.pressure.uniform(1.6e6)
```

Use standard profile types for changing fields:

```python
op.temperature.linear(route="main", start=0.0, end=8.0, v0=20.0, v1=180.0)

op.temperature.piecewise(
    route="main",
    points=[
        (0.0, 20.0),
        (2.0, 80.0),
        (6.0, 180.0),
        (8.0, 140.0),
    ],
)
```

Raw Python functions may be useful in notebooks, but they should compile into a
sampled or piecewise field before serialization/export:

```python
op.temperature.profile(
    route="main",
    start=0.0,
    end=8.0,
    value=lambda station: 20.0 + 160.0 * station / 8.0,
    samples=17,
)
```

The serializable/canonical forms are:

```python
uniform(value)
group_values({...})
range(route, start, end, value)
linear(route, start, end, v0, v1)
piecewise(route, points=[...])
sampled(route, points=[...])
```

For agents, this should be explicit structured data:

```json
{
  "op": "model.operation",
  "name": "mixed_temperature",
  "temperature": {
    "supply": 180.0,
    "return": 95.0
  },
  "reference_temperature": 20.0,
  "pressure": 1600000.0,
  "gravity": true
}
```

```json
{
  "op": "operation.temperature.piecewise",
  "operation": "startup",
  "route": "main",
  "points": [
    [0.0, 20.0],
    [2.0, 80.0],
    [6.0, 180.0],
    [8.0, 140.0]
  ]
}
```

### Thermal Cases

Common derived cases should be easy to express:

```python
model.thermal_cases(
    reference_temperature=20.0,
    cases={
        "cold": 20.0,
        "startup": 80.0,
        "operating": 180.0,
        "shutdown": 60.0,
    },
    pressure=1.6e6,
)
```

This expands to named operations and makes batch solving natural:

```python
results = model.solve_operations(["cold", "startup", "operating", "shutdown"])
```

The domain term should be `operation` for named real-world operating states.

## Structured Agent Operations

Agents should prefer a strict operation model over the permissive Python DSL.

Each operation has a discriminated `op` value and explicit fields.

### Geometry Ops

```json
{
  "op": "pipe.start",
  "point": [0.0, 0.0, 0.0]
}
```

```json
{
  "op": "pipe.run",
  "length": 2.0
}
```

```json
{
  "op": "pipe.bend_to",
  "radius": 0.3,
  "direction": [0.0, 1.0, 0.0],
  "mode": "intersect"
}
```

```json
{
  "op": "pipe.bend_by_orientation",
  "radius": 0.3,
  "angle": 90.0,
  "orientation": 45.0,
  "mode": "intersect"
}
```

```json
{
  "op": "pipe.bend_in_plane",
  "radius": 0.3,
  "angle": 90.0,
  "normal": [0.0, 0.0, 1.0],
  "mode": "intersect"
}
```

### Point Property Ops

```json
{
  "op": "point.anchor"
}
```

```json
{
  "op": "point.block",
  "dof": {
    "x": true,
    "y": true,
    "z": false,
    "rx": false,
    "ry": false,
    "rz": true
  }
}
```

```json
{
  "op": "point.spring",
  "stiffness": {
    "x": 0.0,
    "y": 1500000.0,
    "z": 0.0,
    "rx": 0.0,
    "ry": 0.0,
    "rz": 0.0
  },
  "reference": "global"
}
```

```json
{
  "op": "point.displace",
  "displacement": {
    "y": -0.001
  }
}
```

```json
{
  "op": "point.force",
  "force": {
    "y": -1000.0
  },
  "reference": "global"
}
```

This structured form should be the basis for:

- agent-generated edits
- transactions
- patch application
- validation
- future UI forms
- deterministic replay

### Scenario Ops

```json
{
  "op": "model.operation",
  "name": "hot_operating",
  "temperature": 180.0,
  "reference_temperature": 20.0,
  "pressure": 1600000.0,
  "gravity": true
}
```

```json
{
  "op": "model.temperature_sweep",
  "name": "startup_ramp",
  "temperatures": [20.0, 60.0, 100.0, 140.0, 180.0],
  "reference_temperature": 20.0,
  "pressure": 1600000.0,
  "gravity": true
}
```

### Local Property Ops

```json
{
  "op": "element.assign_group",
  "selector": {
    "route": "main",
    "start": 2.0,
    "end": 6.0
  },
  "group": "heater"
}
```

```json
{
  "op": "element.assign_physical_property",
  "selector": {
    "group": "hot_leg"
  },
  "property": "insulation",
  "value": "mineral_wool_50mm"
}
```

## Model Storage Requirements

The structured v4 model should store enough information to reproduce and
export the geometry accurately.

For bends, `Element` should eventually preserve:

```python
bend_radius
bend_angle
bend_center
bend_normal
bend_mode
start_tangent
end_tangent
```

Current v4 stores `bend_radius` and `bend_angle`, but not enough bend plane and
center information. That is weaker than v2's `TubaBent` representation and
should be improved.

For springs, the canonical storage should be:

```python
Support(
    node="N3",
    type="spring",
    stiffness_matrix=[0.0, 1.5e6, 0.0, 0.0, 0.0, 0.0],
)
```

Scalar spring stiffness without an explicit direction is not part of the
canonical authoring model. Solver export must not infer a default direction.

For operations, canonical storage should separate the physical model from the
operating states:

```python
Scenario(
    name="hot_operating",
    temperature=180.0,
    reference_temperature=20.0,
    pressure=1.6e6,
    gravity=True,
)
```

For local operating fields, canonical storage should preserve selectors and
profile type:

```python
OperationField(
    name="temperature",
    profile="piecewise",
    selector={"route": "main"},
    points=[(0.0, 20.0), (2.0, 80.0), (6.0, 180.0), (8.0, 140.0)],
)
```

Solver export should resolve operation fields onto elements or nodes as needed
by the backend.

Segment-specific values should reference explicit groups:

```python
Scenario(
    name="mixed_temperature",
    temperature={"supply": 180.0, "return": 95.0},
    reference_temperature=20.0,
    pressure=1.6e6,
)
```

## Validation Rules

`model.validate()` should catch at least:

- support node does not exist
- spring has scalar stiffness without explicit direction
- `stiffness_matrix` length is not 6
- local reference requested for a feature that only supports global reference
- block and displacement conflict on the same DOF
- duplicate incompatible supports on the same node
- bend direction is colinear with current direction for a single-plane bend
- 180 degree `bend_to` without an explicit bend plane or orientation
- zero or negative bend radius
- impossible bend geometry due to insufficient previous straight length in
  `mode="intersect"`
- operation references a group that does not exist
- operation temperature is missing for a group that requires one
- thermal sweep contains no steps
- transient operation times are not strictly increasing
- operation field selector matches no elements
- station range falls outside the route length
- piecewise profile stations are not strictly increasing
- overlapping range assignments conflict without an explicit precedence rule

Validation should run before solver export and should also be available as a
user-facing diagnostic.

## Implementation Phases

### Phase 1: Point Property DSL

- Add canonical builder methods: `anchor`, `guide`, `rest`, `block`, `spring`,
  `mass`, `friction`, `displace`, `force`, and `moment`.
- Keep all methods returning `self`.
- Update notebooks to use canonical lowercase methods.
- Keep `model.add_support(...)` as the low-level structured API.

### Phase 2: Scenario API

- Add `model.operation`.
- Add `model.temperature_sweep`.
- Add `model.transient_operation` as a static-case expansion first.
- Add segment/group-specific temperature assignment.
- Add `model.solve_operations`.

### Phase 3: Local Property and Field API

- Add route and station metadata to generated elements.
- Add `b.group`, `b.tag`, and element selector support.
- Add scoped physical property contexts such as `b.section(...)` and
  `b.insulation(...)`.
- Add operation field profiles: uniform, group values, range, linear,
  piecewise, and sampled.
- Resolve operation fields to solver-specific element inputs.

### Phase 4: Bend API

- Add `bend_to`, `bend_by_orientation`, and `bend_in_plane`.
- Add local frame maintenance to the builder.
- Store bend normal and center information in the model.
- Update visualization and solver export to use stored bend geometry.

### Phase 5: Structured Agent Ops

- Define operation dataclasses or pydantic models.
- Compile operation lists into builder calls.
- Use discriminated operation names instead of overloaded parameter sets.
- Route LLM/agent edits through validation before mutating `TubaModel`.

### Phase 6: Validation Hardening

- Add `model.validate()`.
- Reject scalar spring stiffness without direction at authoring and export
  boundaries.
- Reject unsupported local references at authoring and export boundaries.

## Detailed Implementation Plan

This plan is ordered so every phase leaves the repo in a usable state. The
early phases add authoring clarity without requiring solver or visualization
rewrites. Later phases add richer local fields and bend geometry.

### Milestone 1: Canonical Support and Point Property DSL

Goal: make the builder pleasant and unambiguous for point-level properties.

Files:

- `tuba/builder.py`
- `tuba/model.py`
- `tuba/solver/aster.py`
- `tuba/schema.py`
- `tests/test_tuba_core.py`
- support notebooks under `notebooks/`

Tasks:

- Add `PipingBuilder.anchor()`.
- Add `PipingBuilder.guide(axis="x" | "y" | "z" | list[float])`.
- Add `PipingBuilder.rest(x=False, y=True, z=False, friction=0.0)`.
- Add `PipingBuilder.block(x=False, y=False, z=False, rx=False, ry=False, rz=False)`.
- Keep `PipingBuilder.spring(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)` as the canonical spring API.
- Add `PipingBuilder.mass(value)`.
- Add `PipingBuilder.friction(mu)`, either by updating the current support when
  meaningful or by adding a point-level contact/friction record if support
  semantics require it.
- Add `PipingBuilder.displace(...)`, `force(...)`, and `moment(...)` only if the
  current model has storage for them; otherwise add storage first.
- Ensure every builder method returns `self`.
- Reject scalar spring stiffness without explicit direction in all authoring
  paths.
- Update notebooks to use lowercase canonical methods.

Acceptance criteria:

- Existing support examples can be written without `model.add_support(...)`.
- A Y spring is visibly authored as `b.spring(y=1.5e6)`.
- Code_Aster export never silently chooses a spring direction.
- `python -m pytest tests\test_tuba_core.py -q` passes.

### Milestone 2: Route, Station, Group, and Tag Metadata

Goal: every generated element knows where it lives along a route, so local
properties and operation fields can target deterministic ranges.

Files:

- `tuba/model.py`
- `tuba/builder.py`
- `tuba/schema.py`
- `tuba/fragments.py`
- `tuba/patches.py`
- tests for model serialization and builder behavior

Data model changes:

```python
Element(
    ...,
    route: str | None = None,
    station_start: float | None = None,
    station_end: float | None = None,
    groups: list[str] = field(default_factory=list),
    tags: list[str] = field(default_factory=list),
)
```

Builder state:

```python
current_route: str
current_station: float
current_groups: set[str]
current_tags: set[str]
```

Tasks:

- Add `route` parameter to `model.pipe(..., route="main")`.
- Track route station length through `run`, bend tangent arcs, and element
  creation.
- Store `station_start` and `station_end` on every generated element.
- Add `b.group(name)` to assign a group to the last element.
- Add `b.tag(name)` to assign a tag to the last element.
- Add `b.run(length, group=None, tags=None)` convenience parameters.
- Add selectors for `route`, station range, group, tag, and element id.
- Serialize and deserialize metadata in `to_dict` and `from_dict`.

Acceptance criteria:

- A straight route built with three `run(...)` calls has monotonically
  increasing station ranges.
- Groups survive JSON roundtrip.
- A selector can find elements by route range and by group.
- Existing models without metadata still load.

### Milestone 3: Local Physical Property Scopes

Goal: make local physical changes explicit and scoped without global mutable
state.

Files:

- `tuba/builder.py`
- `tuba/model.py`
- `tuba/schema.py`
- tests for builder scoping and serialization

Data model options:

Use existing element fields where possible:

```python
Element.section
Element.material
```

Add attributes for physical metadata that are not core fields:

```python
AttributeAssignment(target="element:pipe_str_1", key="insulation", value="mineral_wool_50mm")
```

Tasks:

- Add scoped builder context managers:

```python
with b.section("DN80"):
    ...

with b.material("P265GH"):
    ...

with b.insulation("mineral_wool_50mm"):
    ...

with b.corrosion_allowance(0.001):
    ...
```

- Add direct last-element helpers:

```python
b.last_element().insulation("mineral_wool_50mm")
b.last_element().attribute("paint_system", "C5")
```

- Decide whether insulation/corrosion should become first-class fields or stay
  generic attributes. Use first-class fields only when solver/export needs them.
- Ensure scoped properties unwind correctly after `with` blocks.

Acceptance criteria:

- Physical property scopes affect only elements created inside the scope.
- Nested scopes restore previous values correctly.
- Local attributes survive JSON roundtrip.
- Solver export either uses supported attributes or clearly ignores unsupported
  attributes with validation/warnings.

### Milestone 4: Operation Model

Goal: separate physical geometry from operating states such as temperature,
pressure, gravity, and wind.

Files:

- `tuba/model.py`
- `tuba/schema.py`
- `tuba/solver/aster.py`
- tests for operation creation and serialization

New data types:

```python
@dataclass
class Operation:
    name: str
    reference_temperature: float = 20.0
    gravity: bool = True
    fields: dict[str, OperationField] = field(default_factory=dict)

@dataclass
class OperationField:
    name: str
    profile: str
    selector: dict[str, Any]
    value: Any = None
    points: list[tuple[float, float]] | None = None
```

Tasks:

- Add `model.operation(name, temperature=None, reference_temperature=20.0, pressure=0.0, gravity=True)`.
- Preserve existing `LoadCase` behavior during transition by compiling simple
  operations into load cases.
- Add `model.solve_operations([...])`.
- Add `model.temperature_sweep(...)` as operation generation.
- Add `model.transient_operation(...)` as static operation expansion first.
- Serialize and deserialize operations.
- Keep `LoadCase` as the low-level solver concept.

Acceptance criteria:

- A simple operation can reproduce the current single load-case export.
- Multiple operations serialize and roundtrip.
- Operation names are unique.
- Existing `define_load_case` users still work until replaced.

### Milestone 5: Local Operation Fields

Goal: allow temperature, pressure, and other state fields to vary locally by
route, station range, group, tag, or profile.

Files:

- `tuba/model.py`
- `tuba/solver/aster.py`
- validation code
- tests for field resolution

Field API:

```python
op = model.operation("startup", reference_temperature=20.0)

op.temperature.uniform(180.0)
op.temperature.group_values({"supply": 180.0, "return": 95.0})
op.temperature.range(route="main", start=0.0, end=2.0, value=60.0)
op.temperature.linear(route="main", start=0.0, end=8.0, v0=20.0, v1=180.0)
op.temperature.piecewise(route="main", points=[(0.0, 20.0), (8.0, 180.0)])
op.pressure.uniform(1.6e6)
```

Tasks:

- Add operation field builder objects for `temperature`, `pressure`, and later
  `fluid_density`, `wind`, and other fields.
- Implement field resolution from selectors to elements.
- Resolve uniform values globally.
- Resolve group values by element groups.
- Resolve range, linear, and piecewise values by station midpoint first.
- Preserve enough data to support better interpolation later.
- Add conflict rules for overlapping assignments:
  - exact element assignment wins over group
  - station range wins over uniform
  - later assignment either errors or requires `override=True`
- Add sampled profiles for Python notebook functions:

```python
op.temperature.profile(route="main", start=0.0, end=8.0, value=lambda s: ..., samples=17)
```

Acceptance criteria:

- A route temperature gradient resolves to per-element temperatures.
- Group-specific pressure resolves to grouped elements.
- Overlapping fields without explicit override fail validation.
- Field resolution is deterministic and serializable.

### Milestone 6: Solver Export Integration

Goal: map operations and local fields into backend-specific load cases.

Files:

- `tuba/solver/aster.py`
- any solver base interfaces
- tests for exported `.comm` and `.mail` content

Tasks:

- Add an operation-to-load-case compiler.
- For simple uniform operation fields, export as current load case behavior.
- For per-element temperature/pressure, group elements by resolved value or
  generate backend groups as needed.
- Preserve operation name in output artifacts.
- Add result metadata that records the operation/load case source.
- Keep algebraic combinations separate from operations:

```python
model.combination("EXP_hot_cold", expression="hot_operating - cold")
```

Acceptance criteria:

- Uniform temperature operation exports exactly like the old simple load case.
- Two different element groups can export different temperatures.
- Exported study names and result metadata identify the operation.
- Unsupported operation fields fail clearly before export.

### Milestone 7: Bend API and Bend Geometry Storage

Goal: replace simple plane-based bends with robust 3D bend authoring and
storage.

Files:

- `tuba/builder.py`
- `tuba/model.py`
- `tuba/plotting/*`
- `tuba/solver/aster.py`
- tests for bend geometry

Data model changes:

```python
Element(
    ...,
    bend_radius: float | None,
    bend_angle: float | None,
    bend_center: list[float] | None,
    bend_normal: list[float] | None,
    bend_mode: str | None,
    start_tangent: list[float] | None,
    end_tangent: list[float] | None,
)
```

Tasks:

- Add `b.bend_to(radius, direction, mode="intersect")`.
- Add `b.bend_by_orientation(radius, angle, orientation, mode="intersect")`.
- Add `b.bend_in_plane(radius, angle, normal, mode="intersect")`.
- Maintain local frame on the builder:
  - local X = current pipe direction
  - local reference direction for orientation zero
  - update reference direction after non-colinear segments
- Compute bend center, normal, start tangent, and end tangent.
- Support `mode="add"` and `mode="intersect"`.
- Validate 180 degree bends require orientation or explicit normal.
- Update visualization to render stored bend arc geometry.
- Update solver export to use stored bend geometry where relevant.

Acceptance criteria:

- `bend_to` can route between arbitrary non-colinear 3D directions.
- `bend_by_orientation` matches the older intuitive dihedral model.
- 180 degree bends are rejected unless plane/orientation is explicit.
- Bend geometry survives JSON roundtrip.
- Visualization uses stored bend center/normal instead of reconstructing from a
  weak plane enum.

### Milestone 8: Structured Agent Operations

Goal: give agents a strict edit surface that maps to the same builder/model
operations without relying on permissive Python syntax.

Files:

- new `tuba/operations.py` or `tuba/ops.py`
- `tuba/patches.py`
- schema/tests for operation validation

Tasks:

- Define discriminated operation schemas:
  - `pipe.start`
  - `pipe.run`
  - `pipe.bend_to`
  - `point.spring`
  - `point.block`
  - `model.operation`
  - `operation.temperature.piecewise`
  - `element.assign_group`
  - `element.assign_physical_property`
- Add parser/validator for operation lists.
- Add compiler from operation list to builder/model mutations.
- Add dry-run mode that returns proposed changes and validation diagnostics.
- Require all agent operations to pass validation before mutating the model.

Acceptance criteria:

- Agent operation JSON can reproduce the canonical example model.
- Invalid mixed bend parameters are rejected by schema, not by solver export.
- Operation replay is deterministic.
- Dry-run diagnostics show selected elements for local field/profile operations.

### Milestone 9: Validation Layer

Goal: make invalid engineering input fail early with messages that point to the
authoring mistake.

Files:

- new `tuba/validation.py`
- `tuba/model.py`
- solver export entry points
- tests for validation failures

Tasks:

- Add `model.validate()`.
- Add validation severities: `error`, `warning`, `info`.
- Validate support definitions.
- Validate route/station metadata.
- Validate operation field selectors and profile monotonicity.
- Validate bend geometry.
- Validate solver backend compatibility.
- Run validation automatically before solver export.

Acceptance criteria:

- Errors block export.
- Warnings can be reported without blocking.
- Validation messages include the affected node, element, route, operation, or
  support id.
- Core examples pass validation cleanly.

### Milestone 10: Notebook and Documentation Refresh

Goal: make examples teach the new model consistently.

Files:

- `notebooks/01_building_piping_systems.ipynb`
- `notebooks/02_supports_and_loading.ipynb`
- visualization notebooks
- architecture docs

Tasks:

- Update support examples to use point-property DSL.
- Add a thermal operation notebook:
  - uniform operation
  - group-specific operation
  - piecewise temperature profile
  - operation sweep
- Add a 3D bend notebook:
  - `bend_to`
  - `bend_by_orientation`
  - `bend_in_plane`
- Add an agent operations example using structured JSON.

Acceptance criteria:

- Notebooks avoid low-level `model.add_support(...)` except in advanced API
  sections.
- Temperature examples use `model.operation(...)`.
- No notebook demonstrates scalar spring stiffness without explicit DOF.

### Recommended Build Order

1. Support DSL.
2. Route/station metadata.
3. Local physical property scopes.
4. Operation model with uniform fields.
5. Local operation fields.
6. Solver export for operations.
7. Bend API and bend storage.
8. Structured agent operations.
9. Validation hardening.
10. Notebook refresh.

This order keeps each step useful. The first two milestones already improve
authoring. The operation API becomes useful before the full bend rewrite. The
agent operation model lands after the human API and data model have stabilized.

## Recommended Canonical Example

```python
model = Model(project_name="SupportExample")
model.add_material("Steel", E=2.1e11, nu=0.3)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)

with model.pipe(section="DN100", material="Steel") as b:
    b.start([0, 0, 0]).anchor()

    for i in range(3):
        b.run(2.0)
        b.rest(y=True)

    b.bend_to(radius=0.3, direction=[0, 1, 0])
    b.run(2.0).spring(y=1.5e6)
    b.run(2.0).block(x=True, y=True, rz=True)
    b.end().anchor()

model.operation("cold", temperature=20.0, reference_temperature=20.0)
model.operation(
    "hot_operating",
    temperature=180.0,
    reference_temperature=20.0,
    pressure=1.6e6,
)

model.validate()
```

Example with local operation fields:

```python
model = Model(project_name="ThermalProfileExample")
model.add_material("Steel", E=2.1e11, nu=0.3)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)

with model.pipe(section="DN100", material="Steel", route="main") as b:
    b.start([0, 0, 0]).anchor()
    b.run(2.0).group("inlet")
    b.run(4.0).group("heater")
    b.run(2.0).group("outlet")
    b.end().anchor()

startup = model.operation("startup", reference_temperature=20.0, gravity=True)
startup.temperature.piecewise(
    route="main",
    points=[
        (0.0, 20.0),
        (2.0, 80.0),
        (6.0, 180.0),
        (8.0, 140.0),
    ],
)
startup.pressure.uniform(1.6e6)

model.validate()
```

## Summary

The older version had a clearer authoring model for engineers. v4 has the better internal
architecture. The target design should combine them:

- point-property clarity for users
- v4 structured model as the source of truth
- explicit six-DOF support APIs
- richer 3D bend APIs based on target direction, orientation, or plane normal
- explicit operation APIs for temperatures, pressure, sweeps, and thermal cycles
- route/station metadata for local physical and operating assignments
- strict structured operations for agents
- validation before solver export
