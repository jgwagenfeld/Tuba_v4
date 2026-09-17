---
name: tuba-modeling
description: Author, verify, solve and review piping/structural models with the Tuba Python library. Use when a project contains model.py / study.py, when the user mentions Tuba, pipe routing, RackRow racks, supports, clash checks, or Code_Aster-backed stress and displacement results.
---

# Tuba modeling

Tuba is a Code_Aster-backed piping engineering workflow. Its contract never changes:

1. Define the structure in Python (`model.py`).
2. Evaluate it with Code_Aster (`study.py`).
3. Display the processed Code_Aster results (web review scene or PyVista).

A `.comm`, `.mail`, or `.export` file is solver input, not a result. Never present
export-only output, hand-derived numbers, or proxy values as solver results. If
Code_Aster is unavailable, stop with the runtime blocker instead of substituting
anything.

## Author Python, not node dumps

`model.py` is engineering code. Write procedural, parametric Python: constants,
loops, construction units (`units/<name>.py` applied with `assemble(...)`), and
the fluent builder. Do not emit flat `add_node` / `add_element` coordinate dumps.

```python
from tuba import Model
from tuba.assemblies import RackRow

model = Model("Plant", standard="ASME B31.3")
model.add_material("SS316L", E=1.95e11, nu=0.3, rho=8000.0, alpha=1.6e-5)
model.add_pipe_section("DN80_SCH80", OD=0.0889, WT=0.00762)

with model.pipe(section="DN80_SCH80", material="SS316L", route="HP_H2") as p:
    p.start([14.0, -6.5, 1.5], support="anchor")
    p.run(4.0)
    p.bend(radius=0.4, angle=90.0, plane="XZ")
    p.end(support="anchor")

model.define_load_case("Operating", pressure=3.0e6, temperature=65.0, gravity=True)
model.validate()
```

The reference layout is `examples/hydrogen-plant-layout/`: obstacles, a `RackRow`
bridge, shoe supports at beam midpoints, and two routed process lines.

## Verify before you solve

`model.verify()` is the one cold-model gate; every surface that solves runs it
and refuses on a blocking error. Run it after every routing change:

```python
report = model.verify()               # validation + clashes + rules
assert report.passed, report.errors   # blocking: bad refs, hard clashes, error rules
print(report.warnings)                # clearance clashes and warnings, non-blocking
```

Under it, `ClashEngine().check_all(model)` is the full cold-model triple —
obstacles, self, and duplicate nodes. `check_model(model)` covers obstacles
only. `check_self(model)` covers element vs element without a topological
connection (shared node, support link, shared coupling target). A route that
doubles back onto itself passes obstacle checks and fails `check_self`. Never
treat a green obstacle-only test as "clash free".

## Prove every route by its endpoints

A fluent route can look right in a screenshot and still end in the wrong place.
Assert the final coordinates against the equipment the line feeds:

```python
end = model.nodes[model.elements[-1].n2].coords
assert [round(float(value), 3) for value in end] == [33.0, -3.25, 1.5]
```

Compare against the obstacle bounds (`model.obstacles`). Stop about 1 m short of
an obstacle face: the end anchor is a nozzle stub, and touching the face is an
obstacle clash.

### Bend sign semantics (the classic bug)

`bend(radius, angle, plane)` picks its rotation axis from the **current
heading**:

- `plane="XY"`: axis is +Z; the sign is stable for any heading.
- `plane="XZ"`: axis is `cross(direction, up)`, with a fallback to +Y for
  headings along ±Z. A `+90` "up" bend from +X becomes a "backwards" bend from
  +Z. The plane is not fixed, so a loop written as `+90, -90, -90, +90` folds
  back over itself instead of continuing forward.

For loops and risers, say the axis explicitly:

```python
p.bend_by_orientation(radius=0.4, angle=90.0, axis=[0.0, -1.0, 0.0])   # +X -> +Z
p.bend_by_orientation(radius=0.4, angle=90.0, axis=[0.0, 1.0, 0.0])    # +Z -> +X
```

The builder resolves `bend(plane=...)` against the heading when you call it and
records that absolute axis, so a saved recipe replays the same turn even if an
earlier step changes. While authoring, `bend_by_orientation` still states your
intent most clearly.

A 90° bend consumes `r * tan(45°)` of straight leg on each side, so runs that
must land on a target need to account for the tangent length.

## Name the context in the 3D scene

Analytical obstacles (buildings, vessels) render as plain boxes. Label them from
the study with `scene_modifier`, so reviewers read the plant, not the boxes:

```python
def _add_obstacle_labels(scene, model):
    for obstacle in model.obstacles:
        low, high = obstacle["min_point"], obstacle["max_point"]
        add_scene_label(
            scene,
            OBSTACLE_LABELS[obstacle["id"]],
            [(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, high[2] + 1.0],
            label_id=obstacle["id"],
            height=0.9,   # metres; scale to the model, 0.18 is for bench-scale models
        )
```

Sandbox-scale studies pass `scene_modifier=_add_labels` to
`run_example(...)`; see `examples/support-rack-review/study.py`.

## Solve and review

- `study.py` declares `LOAD_CASES`, `SOLVER_OPTIONS`, `VOLUME_EXPORT`, and
  `build_review(namespace, output, ...)`; it delegates to
  `examples/code_aster_artifact_review.py`. Keep that structure.
- `python -m tuba.cli_studio <project-folder>` opens the live studio;
  `python -m tuba.project <project-folder> --output <dir>` builds the review.
- `python -m tuba.mcp.server` exposes inspection, `check_clashes`, units, and
  `solve_model` to agents. Use it to inspect and verify, not to unroll geometry.
- Two display paths, never mixed in one study: `tuba.plotting` (PyVista quick
  look / export) and `tuba.visualization` + `viewer/` (reviewable web scene).

## Report what was verified

State the checks you ran and what they returned: `check_all` clash count, route
endpoint assertions, and whether the review came from a fresh Code_Aster solve or
imported committed evidence. Committed evidence is only valid for the model it
was solved from; changing `model.py` invalidates it.
