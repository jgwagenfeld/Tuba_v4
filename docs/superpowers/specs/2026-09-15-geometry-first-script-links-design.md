# Geometry-first script links and vector-style generated model scripts

Date: 2026-09-15
Status: proposed

Terms follow `CONTEXT.md` (Model script, Generated and Authored model script,
Authoring session, Model fingerprint). This spec adds **Pipe run**: the records
that one `with model.pipe(...)` block, or one `build_pipe_run` call, creates
from a sequence of builder steps with one section and one material. It respects
ADR 0001 (beta API may break without shims) and ADR 0003 (tools rewrite only
generated model scripts), and amends decision 9 of
`2026-09-13-project-authoring-session-design.md`.

## Problem

In Build mode the inspector's "Defined by model.py:N" link
(`tuba/model.py::_script_lines`, `viewer/src/app.js::renderScriptLink`) points
at the line that created the selected record. For a builder pipe that is its
geometry (`builder.run(3.0)`), but not elsewhere:

- A support links to its `add_support(...)` line, a property statement, not to
  the line that created the point it sits on.
- A generated model script has no geometry lines at all.
  `tuba/mcp/server.py::build_pipe_run` receives vector steps (start, run, bend,
  end: the vocabulary of Tuba v2's `P`, `Vc` and `Bent`), but
  `tuba/project/script.py::generate_model_script` writes the finished records
  as `model.add_node(...)` and `model.add_element(id=..., n1=..., n2=...,
  section=..., material=..., route_id=..., station_start=...,
  station_end=...)`. Every pipe of an MCP-built project links to a line made
  mostly of properties.
- Profile, Attributes and Restraint have no link to where they are defined, and
  load arrows have no link at all.

Tuba v2 kept the two apart: vectors defined geometry, and `SectionTube`,
`Material`, `Temperature` and `Pressure` applied to the vectors that followed.
Code_Aster works the same way. `study.mail` carries the geometry with named
groups (one per element, `SEC_<section>`, `MAT_<material>`, `GN_<node>`), and
`study.comm` assigns properties to those groups (`tuba/solver/aster_mesh.py`,
`tuba/solver/aster_comm.py`). A model script's layout never reaches the solver.

## Objective

"Defined by" points at the geometry line, each property links to the line that
defines it, and a generated model script writes each pipe run as the vector
steps it was built from.

## Decisions

### Pipe runs

1. A `with model.pipe(...)` block and a `PipeRunRecipe.build(model)` call each
   remember one pipe run on `model.pipe_runs`: its recipe (section, material,
   route, up vector, steps), the lengths of the node, element and support
   sequences when its first step executed, and the ids of the records its own
   steps created. The builder collects those ids from its own model calls, so a
   model call typed inside the block is not part of the run. A block whose steps
   create no records remembers nothing.
2. `pipe_runs` lives only in memory, like source lines. It is never part of
   `to_dict()`, model.json, `same_model` or the model fingerprint.
   `copy.deepcopy` keeps it, so it survives the MCP's copy-per-edit (`_edit`)
   and `ModelTransaction.apply` (deep copy, then `__dict__` swap). Running a
   model script rebuilds it, so an MCP reload
   (`init_session(load_existing=True)`) has it too. `TubaModel.from_dict`
   starts without runs.

### Generated model scripts

3. The generator writes geometry in creation order instead of all nodes, then
   all elements, then all supports. Where a remembered run begins, it writes the
   run as a block:

   ```python
   with model.pipe(section='DN100_SCH40', material='P265GH') as builder:
       builder.start([0.0, 0.0, 0.0], support='anchor')
       builder.run(5.0)
       builder.bend(radius=0.1524, angle=90.0, plane='XY')
       builder.run(3.0)
       builder.end(support='anchor')
   model.add_node([9.0, 0.0, 0.0])
   model.add_element(id='pipe_str_2', type='pipe_straight', n1='N3', n2='N4', ...)
   ```

   Materials and sections stay before the geometry. Load cases, operations,
   tees, obstacles, groups, placements, specs, attributes and mixed records stay
   after it, as today. A section or material change starts a new block.
4. Steps are written as recorded. The main argument is positional (`start([...])`,
   `run(5.0)`, `set_direction([...])`, `bend_to([...], ...)`), the rest are
   keywords, and an argument is left out only when it is identical to the
   method's default (same type and value), so replay cannot change.
   `run_element` steps recorded by `beam`, `bar` and `cable` are written under
   those names (`builder.beam(1.5)`). A recipe's route is passed as
   `model.pipe(..., route=...)`.
5. A remembered run is written as a block only when:
   - its records fill exactly the positions that follow the sequence lengths
     recorded at its first step, in each of the three sequences;
   - it does not overlap or interleave with another remembered run in any
     sequence;
   - its up vector is the builder default.

   Otherwise its records are written as single calls, exactly as today. A model
   without remembered runs generates today's text.
6. The exact-rebuild proof stays whole-script (`write_model_script`). If the
   script with blocks fails it, the single-call script is proved and written
   instead; only when that fails too does the save raise, as today. The
   ceiling, to be noted in the code: one run that replays inexactly flattens
   the whole script; a per-run proof is the upgrade if that ever matters.
7. Decision 9 of the authoring-session spec is amended: pipe runs are written
   as their builder steps; every other node, element and support stays one
   public call.

### Links

8. `add_node`, `add_material`, every `add_*_section`, `define_load_case`,
   `define_operation`, `LoadCase.add_nodal_force`, `Operation.add_nodal_force`
   and `assign_attribute` (and so `assign_insulation` and patch-applied
   attributes) record `source_line` and `source_call_line` through
   `_script_lines()`, as `add_element` and `add_support` already do. The fields
   are never serialized and are declared `compare=False`. `AttributeAssignment`
   is frozen, so its lines are passed at construction. `InsulationSpec`,
   `PlacementFrame`, `PlacementAssignment` and the mixed records get no line
   fields, because `_record_keywords` writes them field by field.
9. "Defined by" shows the geometry line:

   | Selection | Line |
   |---|---|
   | Element | its own creation line: the block step (`builder.run(5.0)`, `builder.bend(...)`) or `model.add_element(...)` |
   | Support | the line that created its node; the support's own line when the node has none |
   | Load arrow | its `add_nodal_force(...)` line |

10. Property links:

    | Inspector | Line |
    |---|---|
    | Profile | the element's section definition |
    | Attributes: section, material | the section or material definition |
    | Attributes: an assigned value | the assignment that supplied the value shown, by the `get_attributes` rule: group assignments first, then direct ones, the last one wins |
    | Restraint | the support's own line |
    | Load: load case | the `define_load_case(...)` or `define_operation(...)` line |

11. Scene metadata (`tuba/visualization/builders`):
    - Elements keep `source_line`/`source_call_line` and gain
      `property_lines: {"section", "material", "attributes": {key: line}}`.
    - A support's `source_line`/`source_call_line` become its node's, and it
      gains `property_lines: {"restraint"}`.
    - Load arrows gain `source_line`/`source_call_line` and
      `property_lines: {"load_case"}`.

    Keys without a line are left out.

### Viewer

12. Links stay in Build mode only. "Defined by" (`renderScriptLink`) keeps its
    look and is also shown for `applied_load` objects, whose entity ref is a
    node. The code pane marks the "Defined by" line, so selecting a support
    marks its point's line.
13. Each property with a line gets a small `:N` chip: on the Profile heading, on
    each Attributes row, on the Restraint heading, and on the Load case row of a
    new "Load" section for load arrows. A chip's title shows the line's code;
    clicking it does what "Defined by" does (switch to the model.py tab, reveal
    and mark the line). Chips are hidden while the script's lines have moved
    since the last run.
14. `getPropertySections` and `getSelectionSummary` carry `sourceLine` on
    sections and rows (not `lines`, which a summary section already uses for
    its rows). `renderEvidenceSection` and `renderRestraintStrip` draw the chips
    through one `scriptLineChip(line)` beside `scriptLineButton`, sharing its
    click behaviour.

## Interface

```python
# tuba/builder.py
@dataclass(frozen=True)
class BuiltRun:
    node_ids: List[str]
    element_ids: List[str]
    support_ids: List[str]              # new
    recipe: PipeRunRecipe               # new
    offsets: Tuple[int, int, int]       # new: node, element, support counts at the first step

# tuba/model.py
model.pipe_runs: List[BuiltRun]         # runtime only (decision 2)

# tuba/project/script.py
generate_model_script(model, *, pipe_runs: bool = True) -> str   # False: today's single-call layout
write_model_script(path, model, *, last_text) -> str             # unchanged; falls back per decision 6
```

```json
{"source_line": 12, "property_lines": {"section": 8, "material": 7, "attributes": {"paint": 31}}}
```

## Testing

Python, written to fail first:

- `tests/test_model_script.py`
  - A `with model.pipe()` block and a `PipeRunRecipe.build` each come out as a
    block with their steps (`run(5.0)` positional, `beam(1.5)` by name) and
    rebuild the same model.
  - Patch records between two runs stay single calls, in creation order.
  - A `model.add_support` inside a block stays outside the run, and the script
    still rebuilds (the guyed-mast pattern).
  - A run whose records do not fill consecutive positions, and a run with a
    non-default up vector, are written as single calls.
  - Fallback: when the script with blocks does not rebuild the model,
    `write_model_script` writes the single-call script.
  - `test_each_element_and_support_links_to_its_own_line` asserts that
    elements link to their block step and supports to their node's line.
  - The nine example projects still rebuild (the parametrized round trip, now
    with blocks).
- `tests/test_studio_server.py`: the guide support links to `builder.bend(`;
  scene metadata carries `property_lines` for a section, a material, an
  assigned attribute and a restraint, and a load arrow carries its
  `source_line` and load case; the blank-line fingerprint test also checks that
  node and material lines move without changing the fingerprint.
- `tests/test_mcp_server.py`: after `build_pipe_run`, model.py holds the run's
  block, and it still does after `init_session(load_existing=True)` and a
  patch.

Viewer (`npm test`): `viewer/test/selection.test.js` and
`viewer/test/supports.test.js` cover `sourceLine` on Profile, Attributes rows,
Restraint and the Load section. `viewer/test/code-link.test.js` is unchanged:
the Length editor already reads `builder.run(5.0)`.

Before finishing: the full Python suite, `npm test`, and `npm run build` for the
committed viewer bundle.

## Rollout

- Work in the worktree `D:/tmp/tuba-script-links` on branch
  `script-links/geometry-first`, created from `main` at `2dacd52`, which
  already has Build mode's generated `.comm` tabs. Never commit in
  `D:/Gitprojects/Tuba_v4`: other sessions work there.
- Order: Python (line recording, pipe runs, generator, scene metadata), then
  the viewer (chips, the Load section, "Defined by" for load arrows), then one
  `npm run build`.
- A fresh worktree has no `viewer/node_modules`: run `npm ci` in its `viewer/`
  first. Run pytest from the worktree root with the main checkout's `.venv`
  interpreter.
- Docs: `CONTEXT.md` gains **Pipe run**; decision 9 of the authoring-session
  spec gets a pointer to this spec.
- Run the Linux Pages check before pushing: the viewer bundle and the gallery
  scenes' metadata change what Pages builds.

## Out of scope

- Rewriting authored model scripts (ADR 0003).
- v2-style property steps inside a run (`builder.section(...)`); a section or
  material change starts a new block.
- A single-call `V(dx, dy, dz)`, and the Length editor for `beam`, `bar` and
  `cable` lines.
- Lines for records built by `from_dict`, inside the MCP process, or written as
  literals (generated I-beam sections, groups, specs).
- A per-run exact-rebuild proof (decision 6).
