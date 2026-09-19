# Tuba v4 Agent Instructions

## Core Product Contract

Tuba v4 is a Code_Aster-backed piping engineering workflow:

The whole point of Tuba v4 is to define piping structure, evaluate it with Code_Aster, and display processed results.

1. Define the piping structure in Tuba.
2. Evaluate the model with Code_Aster.
3. Display, review, and report the processed Code_Aster results.

Code_Aster is not optional for production stress, displacement,
reaction, thermal-expansion, operating-state clash, compliance, or result
visualization workflows. Export-only paths are development and diagnostic
surfaces only.

## Code_Aster Rules

- Do not present fabricated, mock, hand-built, or proxy values as solver
  results.
- Do not treat `.comm`, `.mail`, or `.export` generation as a completed Tuba
  evaluation workflow.
- If Code_Aster is unavailable, fail loudly with the runtime/setup blocker and
  stop before displaying or reporting solver results.
- Unit tests may use export-only studies or deterministic fixtures so CI stays
  portable, but integration/developer validation must run the real Code_Aster
  backend.
- Prefer a Python-managed Code_Aster runtime/bridge when implementing execution
  paths. Shell runners, Docker, and legacy `as_run` should be fallbacks, not the
  product definition.
- Solver integration must remain native Tuba code with external-process
  Code_Aster execution.

## Documentation Rules

- README, notebooks, examples, and architecture docs must preserve the core
  workflow: Tuba model -> Code_Aster solve -> processed result display.
- Any export-only example must be labeled as incomplete for engineering
  evaluation until the exported study has been solved by Code_Aster and result
  artifacts have been imported.
- Any UI or notebook that displays stress, displacement, reaction, compliance,
  or operating-state results must use Code_Aster-backed artifacts or stop with a
  clear runtime requirement.

## Model Authoring Philosophy (Python-First vs. Decompiled Dumps)

Tuba treats Python as a first-class engineering authoring language, exactly like
Blender treats `bpy`:

- **Write clean, procedural Python**: When defining models, author clean,
  readable, parametric code in `model.py`. Use engineering constants
  (`CLEARANCE_HEIGHT = 5.5`, `ROAD_WIDTH = 8.0`), fluent routing
  (`with model.pipe(...) as b:`), and loops.
- **Never author flat node dumps**: Do not write hundreds of raw `model.add_node()`
  and `model.add_element()` lines by hand, and do not use MCP tools to unroll
  geometry into flat coordinate dumps. Flat coordinates are compiled FEM state,
  not human- or agent-maintainable engineering code.
- **Authored vs. Generated Scripts**:
  - Scripts authored with procedural Python (without the generated MCP header)
    are **Authored Model Scripts** (see ADR 0003). Tuba Studio and solvers execute
    them as-is and **never overwrite or destroy them**.
  - Generated scripts (from MCP sessions) replay builder steps or unrolled records
    for round-tripping, but authored Python is the preferred medium for complex
    piping systems.
- **Role of the MCP Server**:
  - The MCP server is an **Inspection, Verification, and Solving Engine**, not a
    micro-RPC substitute for Python code.
  - Use MCP tools for structural queries (`inspect_model`), join-aware clash
    detection (`check_clashes`), unit validation (`save_unit`, `apply_unit`),
    and Code_Aster evaluation (`solve_model`).
  - Do not treat the MCP server as a micro-tool treadmill to reconstruct raw
    geometry line by line.

## Construction Units Style

Construction units (`def` in `model.py`, or `units/<name>.py` applied with
`assemble(model, "<ref>", ...)`) are project code, not snippets: they replay on
every studio load and every MCP save. `save_unit` enforces this and refuses
anything else; write units that pass it the first time.

- One unit, one structure: `def rack_row(model, ...)` builds a rack row, not a
  rack row plus its pipe plus its load case. Compose calls; do not copy bodies.
- Everything that varies is a parameter: sections, materials, dimensions,
  counts, friction, zones. No project literals inside the body. Params must stay
  JSON-serializable literals so invocations replay byte-identically.
- `model` is always the first parameter; document what the unit builds and what
  each parameter means in the docstring.
- Place unit defs in the leading run of `model.py` (docstring, imports, defs,
  before `model = ...`): the script writer carries only that run, so a def below
  the first assignment is invisible to generated round-trips.
- Validate inputs and fail loudly (`ValueError` with the expected value), like
  the shoe-midpoint alignment check. Never `print`, never bare `except`.
- Prefer the library (`tuba.assemblies.RackRow`, patch ops, `ModelTransaction`)
  over reimplementing geometry. New reusable geometry belongs in `tuba/`
  with tests; project-specific composition belongs in units.
- **Do not bloat core libraries**: Do not add one-off structural classes (e.g.
  bespoke tees, doglegs, cantilever brackets) to `tuba/assemblies.py`. Keep the
  core minimal (topological integrity, node-sharing, midpoint shoe splits).
- **Create on-the-fly units**: For non-standard configurations or clash fixes,
  synthesize a construction unit on the fly and register it via `save_unit`
  (`where="units"` or `where="model"`).
- **Clash resolution loop**: When `check_clashes` reports an overlap:
  1. Inspect `groups` and `assembly_calls` via `inspect_model` to identify the
     originating unit calls and element spans.
  2. Either adjust the recorded parameters or author an on-the-fly unit with
     `save_unit` that routes or frames clear of the collision.
  3. Apply with `apply_unit` and verify zero clashes remain before solving.

## Visualization Surfaces

There are two result-display paths. Keep them distinct; do not add a third.

- `tuba/plotting/` (PyVista) is the **quick-look & export** path. It is wired
  to `FEAResults.plot_*()` (see `tuba/solver/base.py`) and reads real `.rmed`
  artifacts; use it for interactive/notebook views and PLY/glTF/Blender export.
- `tuba/visualization/` + `viewer/` is the **reviewable web-scene** path.
  `build_visualization_scene` / `write_scene_bundle` emit a JSON scene contract
  that the `viewer/` Three.js app renders. Use it for shareable review bundles.

Prefer one path per notebook/example rather than mixing both.
