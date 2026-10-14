# Agent model workflow

Work in the same authored project folder as Studio and the CLI. For a received
project, extract it with all referenced Python helpers, CAD and data. See
[Share and open a project](content/project-sharing.md).

## Procedural authoring first

Write readable, parametric `model.py` using engineering constants, functions,
loops and `with model.pipe(...) as pipe:`. Use `study.py` for operations,
solver settings and review configuration. Avoid hand-authored flat node/element
dumps or long sequences of geometry RPC calls. Authored Python is executed as-is;
Studio and generated-script tools preserve it.

Construction units belong in the leading definitions of `model.py`, before
the model assignment, or in `units/<name>.py`. Each unit builds one structure,
takes `model` first, and exposes varying dimensions, sections, materials and
other choices as JSON-serializable parameters. Document and validate inputs.
Compose rack, pipe and load units rather than copying bodies.

Prefer existing reusable geometry such as `tuba.assemblies.RackRow`.
Project-specific geometry belongs in project units. MCP's `save_unit`
validates unit code and `apply_unit` retains its invocation. General library
changes need the corresponding tests.

## Inspection, verification and solving

Start the MCP stdio server with the project environment's Python:

```bash
python -m tuba.mcp.server
```

1. Bind the intended folder explicitly with
   `init_session(file_path="/path/to/project/model.py", load_existing=True)`.
2. Edit authored Python, then reload the session. Use `inspect_model` to
   inspect routes, groups and assembly calls.
3. Run `verify_model` / `model.verify()` and `check_clashes` as needed.
   The shared verification gate includes structural validation, join-aware
   cold-model clashes and rules. `model.validate()` alone is a subset.
4. Resolve a clash by changing the originating unit's parameters or code.
   Inspect again and clear blocking findings before solving.
5. Use `solve_model` or the project CLI to evaluate the study with real
   Code_Aster. Process projects also require passing, current hydraulic evidence.
6. Review imported results and their lineage in Studio or an exported review
   bundle. Exported `.comm`, `.mail` and `.export` inputs are an incomplete
   handoff until Code_Aster runs and result artifacts are imported.

Inspection refreshes changed source, helpers and CAD but does not authorize
overwriting externally edited files. Rebind before applying a mutation.
Generated-script edit tools cannot rewrite an authored unit call; edit its
Python source.

MCP and CLI use the same `study.py`, verification gate and evidence.
`solve_model(load_case=...)` validates the named operation and evaluates the
study's operations together. Matching attested evidence may be reused;
`force=True` requests a fresh solve and does not bypass blocking verification.
A blocked runtime or missing result artifacts stop evaluation without fabricated
stress, displacement or reactions.

See the [CLI and MCP guide](content/workflow.md#projects-in-studio-the-cli-and-agents).
For retained candidate campaigns, use [piping search](content/piping-search.md);
for graph/P&ID and hydraulic-to-structural coupling, use
[process networks](content/process-networks.md).

## Fragments, placements and transactional edits

`ModelFragment` and `CoordinateSystem` remain useful for reusable model
records and explicit local-to-global placement. Construction units retain the
authored recipe; fragments contain the compiled records.

Placed fragment nodes are stored in model-global Cartesian coordinates.
A retained `PlacementFrame` supports source provenance and local editing;
it does not make stored node coordinates local.
`model.to_global_point(point, frame="placement_frame:rack_A")` converts an
explicit local point.

For generated record edits, use `ModelPatch` and `ModelTransaction` so
validation and rollback run consistently. Validate patch payloads with
`validate_patch_dict()` and full model payloads with `validate_model_dict()`.

- Placement names are unique; an existing name raises `ValueError` and rolls
  back the placement.
- Fragment material and section names must be new or match the parent's
  definitions exactly.
- Group metadata retains placed nodes, elements, supports, fragment identity
  and placement for inspection.
- `AddNode` reuses coincident nodes by default. Use `reuse_existing=False`
  only when a distinct node at the same location is intended.

These APIs support record editing. Procedural Python remains the preferred
definition for complex piping and supporting structures.
