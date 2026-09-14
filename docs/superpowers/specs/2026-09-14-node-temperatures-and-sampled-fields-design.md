# Node Temperatures and Sampled Fields — Design

**Status:** approved in brainstorming 2026-09-14, awaiting spec review
**Scope:** 1D Code_Aster studies (`TUYAU_3M`, `POU_D_T`). This brings over the sound parts of the stashed
generalized-fields work (stash message "generalized-fields WIP set aside for the line-loads merge (2026-09-14)").

## Problem

Engineers want to put CFD results, formulas and tables onto a piping model as temperatures, pressures, wind and line
loads.

The stashed generalized-fields work tried to do this by storing each field's *source* on the operation field: a formula
string run with `eval`, a point array, or a MED file path. Reviewing it found several problems:
- the model fingerprint ignored the point values;
- whole clouds were stored in the saved model;
- `eval` ran on model data;
- `force` and `acceleration` fields were accepted but never written;
- a default `value=0` could silently zero the pressure;
- route scopes were ignored.

Designing this slice uncovered one more. Code_Aster's temperature field (`NOEU_TEMP_R`) has one value per **node**, and
the solver mesh contains nodes the model does not have: bend segment nodes, POU_D_T subdivision nodes and TUYAU midside
nodes. The stash wrote temperatures only on model nodes, which left those generated nodes at the base temperature. That
makes the thermal expansion wrong along every element it touched.

Today a temperature can only be given per element: `element_ids`, a route (optionally with a station range and a
linear profile), a group, or all elements. A linear profile becomes a staircase of per-element values. A node shared by
two elements with different values takes whichever element's group was written last.

## Decisions

1. **Store only what the solver receives.** Helpers evaluate profiles in Python and write ordinary operation fields.
   The model keeps numbers only — no clouds, formula strings or file references — so fingerprints, saved models and
   reports stay exact and small.
2. **Node temperatures are a new `nodes` scope on ordinary operation fields:**
   `operation.add_field("temperature", value, node_ids=[...])`.
3. **The compiler writes a true nodal temperature field.** It writes every solver node of every element that touches
   a node temperature, and interpolates generated nodes along their element.
4. **Node temperatures and element temperature fields must not meet at a node.** Such an overlap is refused, naming
   the nodes.
5. **A cloud value is the mean within a capture radius.** A target with no cloud point inside the radius is refused.
6. **Element fields stay as they are.** `element_ids`, route, group and all keep working. Studies of models without
   node temperatures stay byte-identical, and `CODE_ASTER_COMPILER_ID` does not change.

## Authoring and validation

- **API.**
  - `Operation.add_field("temperature", value, node_ids=[...])` sets scope `"nodes"`, as `element_ids` sets
    `"elements"`.
  - `OperationField` gains `node_ids: List[str]`, empty by default.
  - Saved models load through `define_operation(fields=[...])` → `add_field(**field)`, so `node_ids` round-trips.
- **Validation of a node-scoped field.** `_validate_operation_fields` handles node scope before element selection.
  - The quantity is `temperature`, the profile is `uniform`, and `node_ids` is not empty. The field carries no `group`,
    `route_id`, `element_ids`, station range or direction.
  - Every node exists and belongs to at least one pipe element (`pipe_straight` or `pipe_bend`).
  - Two node fields that give the same node different values are refused. Identical duplicates are allowed; these are
    the same state semantics today's temperature fields have.
  - A node that has a node temperature and also belongs to an element selected by any element temperature field (any
    scope, any profile) is refused. The message names the nodes and the field indices.
  - A field of any other scope that carries `node_ids` is refused.
- **Serialization.** `_operation_field_to_dict` writes `node_ids` only when it is non-empty. The schema's
  `operationField` gains `"nodes"` in the scope enum and a `node_ids` string array.
- **Identity and reports.** `_operation_field_payload` (`tuba/analysis/provenance.py`) and `_operation_field_dict`
  (`tuba/reporting/tables.py`) add `node_ids` only when it is non-empty. Every existing fingerprint and the exact-dict
  report test therefore stay unchanged.
- **Unchanged refusals:**
  - Pipe-volume studies refuse every temperature field and any temperature change (`aster_volume.py`).
  - Native-contact paths refuse every operation field (`aster_contact.py`).
  - `resolve_operation_field_elements` stays element-only. For a node-scoped field it keeps raising "Unsupported
    operation field scope", so the pressure, wind and line-load resolvers refuse a misplaced node scope.
  - The STEP mixed exporter writes no loads at all, a known gap outside this slice.

## Compiler (1D Code_Aster)

- **Node temperatures per load case.**
  - A node-temperature resolver in `tuba/solver/aster_loads.py` returns the node temperatures of the solved load case.
  - It repeats the validation refusals (unknown nodes, disagreeing values, overlap with element temperature fields).
    `LoadCase.fields` skip validation; the line-load resolver already does the same for this reason.
  - `resolve_operation_field_groups` ignores node-scoped fields.
- **Touched elements and written nodes.** An element is *touched* when either of its end nodes has a node temperature
  in the solved load case. Every element type counts: pipe, beam, bar and cable. For each touched element the compiler
  writes:
  - its two end nodes;
  - its generated interior nodes `{element id}_n{i}`: on bends, and on beams, cables and POU_D_T pipe straights when
    they are subdivided;
  - its TUYAU SEG3 midside nodes: `{element id}_mid` on a TUYAU straight, and `{element id}_s{k}_mid` for each segment
    of a TUYAU bend. Both are named by `_generated_midpoint_node_id`, which hashes long names.
- **Values.**
  - An end node with a node temperature takes that value.
  - Any other end node takes the value Code_Aster would give it anyway. That is the value of the last row of
    `resolve_operation_field_groups(model, load_case, "temperature")` whose element ids include an element at that
    node; with no such row, `load_case.temperature`.
  - A generated node takes the linear interpolation between its element's two end values, at its fraction `t` along
    the element. These fractions equal the `parametric_t` values `AnalysisMesh.node_sources` already records:
    - interior node `i` of `N` segments: `t = i/N` (bend nodes sit at equal angle steps, so this is also the arc-length
      fraction);
    - midside node of bend segment `k`: `t = (k + 0.5)/N`;
    - midside node of a TUYAU straight: `t = 0.5`.
- **Mesh.**
  - The `.mail` GROUP_NO block and `AnalysisMesh.groups` get one `GN_<node>` group for every node that any load case
    or operation writes. These sit next to today's support and nodal-force groups, collected the way
    `_nodal_force_node_ids` does it.
  - The solver name map is built from `AnalysisMesh.groups`, so long group names are hashed automatically.
  - The mesh is shared across studies. A model where only one operation has node temperatures therefore carries these
    groups in every study's mesh. That changes the mesh text of those studies, not their results.
- **Command file.**
  - `_write_temperature_field` keeps the `TOUT` entry and today's `GROUP_MA` rows.
  - After them it appends one `_F(GROUP_NO='GN_<node>', NOM_CMP='TEMP', VALE=...)` per node written for the solved load
    case, each node once. The order is stable: touched elements in model order, then each element's nodes by `t` (n1,
    generated nodes, n2).
  - `TEMP_FIELD` (linear path) and `TEMP_HOT_FIELD` (nonlinear path) both get these entries. `TEMP_REF_FIELD` stays
    uniform at `ref_temperature`.
  - The `MODELE=MODELE` form with an `AFFE` tuple is used whenever element rows or node entries exist. Otherwise
    today's `MAILLAGE=MAIL` form is written.
- **Temperature load.** `has_temperature_load` also returns true when any written node value differs from
  `ref_temperature`.
- **Byte identity.** A model with no node temperatures writes no extra nodes and no extra groups, so its `.mail` and
  `.comm` stay byte-identical.

## Sampling helpers (`tuba/sampling.py`)

### Common behaviour

- **Quantity.** One of `temperature`, `pressure`, `wind`, `line_load`. `direction` is required for `wind` and
  `line_load`, and refused for the others.
- **Scope keywords.** `group`, `route_id`, `station_start`, `station_end` and `element_ids` pick the scope exactly as
  they do in `add_field`.
- **Selection.** Elements come from `model.resolve_operation_field_elements` on a probe `OperationField` built from the
  same keywords. The helpers therefore follow the field rules exactly:
  - with no scope keyword, the helper selects what scope `all` selects;
  - bars and cables are refused for wind and line loads;
  - partial station ranges are refused for wind and line loads.
- **Targets.**
  - `temperature`: the distinct end nodes of the selected elements, in element order.
  - The other quantities: the selected elements.
- **Positions.**
  - A node is at its coordinates.
  - A straight element (pipe or beam) is at the mean of its end nodes.
  - A bend is at its arc midpoint, `sample_bend_geometry(n1 coords, bend_geometry, n_segments=2)[1]`. A bend without
    stored `bend_geometry` is refused, as the viewer and plotting already do.
- **Stations** (route tables only).
  - An element's station is the midpoint of its `station_start` and `station_end`.
  - A node's station is the `station_start` of a selected element whose `n1` it is, or the `station_end` of one whose
    `n2` it is.
  - A target without station metadata is refused.
- **All or nothing.** A helper computes every value before writing, so a refused call leaves the operation unchanged.
- **Writes.**
  - `temperature`: one `operation.add_field("temperature", value, node_ids=[node])` per node.
  - The other quantities: one `operation.add_field(quantity, value, element_ids=[element], direction=direction)` per
    element.
- **Return value.** The list of `OperationField` records written, in target order.
- **Units.**
  - Coordinates, points and the capture radius are in model units (metres).
  - Values are in the field's units: °C for temperature, Pa for pressure, Pa of dynamic pressure for wind, N/m for
    line loads.

### `field_from_cloud(model, operation, quantity, points, values, *, capture_radius=None, direction=None, group=None, route_id=None, station_start=None, station_end=None, element_ids=None)`

- **Inputs.** `points` has shape (N, 3) and `values` shape (N,), all finite, with N ≥ 1.
- **Value.** A target takes the mean of `values` over the points within distance `r` of its position.
  - `r` is `capture_radius` when given, and it must be finite and > 0.
  - Otherwise `r` is 1.25 × the largest `physical_properties_for_element(model, element).bare_radius_m` among the
    selected elements at that target.
  - A ring of wall points around a centreline node therefore gives the circumferential mean.
- **Refusal.** If any target has no point within `r`, a `ValueError` lists up to 10 such targets with their
  nearest-point distance and `r`. It hints to check units (mm vs m), the coordinate frame and the cloud's coverage.
- **Cost.** Distances are computed with NumPy one target at a time, so memory stays O(points). A `ponytail:` comment
  names the O(targets × points) time ceiling and the upgrade path (a KD-tree).

### `field_from_function(model, operation, quantity, function, *, direction=None, group=None, route_id=None, station_start=None, station_end=None, element_ids=None)`

- **Value.** A target takes `float(function(x, y, z))` at its position. Only plain Python callables are accepted: no
  formula strings and no `eval`.
- **Refusal.** A non-finite result raises `ValueError` naming the target.

### `field_from_route_table(model, operation, quantity, route_id, table, *, direction=None, station_start=None, station_end=None)`

- **Table.** `table` is a sequence of `(station, value)` rows: at least 2, all finite, with strictly increasing
  stations.
- **Value.** A target takes the linear interpolation of the table at its station.
- **Refusal.** A target whose station lies outside `[first station, last station]` raises `ValueError` naming the target
  and its station; the table is not extrapolated. A station range limits the helper to the part of the route the table
  covers.

## Verification

### Default-suite tests

- **Authoring and validation:**
  - the node-scope rules, including which keywords a node-scoped field may not carry;
  - the refusal of disagreeing node values and of overlaps with element temperature fields;
  - `node_ids` in `to_dict`, schema, fingerprint payload and report only when present;
  - a round trip through `to_dict` and `from_dict`.
- **Compiler:**
  - `GN_` groups for generated nodes in the `.mail` and in `AnalysisMesh.groups`;
  - interpolated `VALE`s on a POU_D_T subdivided straight and on a TUYAU bend with midside nodes, checked against the
    mesh's `parametric_t`;
  - an uncovered end taking an adjacent element field's value;
  - both the linear and the nonlinear path;
  - the resolver's refusals for load-case fields.
- **Byte identity.** Take a straight-pipe model with uniform and linear element temperature fields. Its exact
  temperature `CREA_CHAMP` blocks, on both paths, and its exact `GROUP_NO NOM=` lines are captured from `main` before
  the change and must not move. Today's tests only check that `TEMP_FIELD = CREA_CHAMP(` is present.
- **Helpers:**
  - the capture-radius mean, including a ring of points giving the circumferential mean, and the default radius;
  - the refusal message with nearest distances, and that nothing is written after a refusal;
  - function values at nodes and at a bend's arc midpoint;
  - route-table interpolation, the out-of-range refusal and a station range;
  - `direction` required for wind and line loads;
  - the bar/cable and partial-station refusals inherited from selection.

### Real Code_Aster references (opt-in, `TUBA_RUN_CODE_ASTER_INTEGRATION=1`)

- **Model.**
  - A cantilever anchored at one end: a 4 m straight, then a 90° bend of R 0.5 m.
  - OD 0.1 m, WT 0.01 m, α = 1.2e-5 /K, `ref_temperature` 20 °C.
  - The operation has gravity off and no pressure.
  - Node temperatures come from `field_from_function`, rising along the route, with a different value at each of the
    three model nodes.
- **Check.**
  - The free end is unrestrained, so it moves by α ∫ (T(s) − T_ref) t(s) ds along the centreline. Here t(s) is the unit
    tangent, and T is linear in arc length on each element between its end values.
  - The solved tip displacement must be within 1% of that vector's magnitude, on both `TUYAU_3M` and `POU_D_T`.
- **Why it matters.** The check fails if generated nodes keep the base temperature, which was the stash's bug.

### Docs

- **`docs/content/modeling.md`:** a section on element versus node temperatures and the three helpers, with a
  CFD-cloud example.
- **`CONTEXT.md`:** a "Node temperature" entry.
- **`docs/architecture/library-architecture-review.md`:** the command-map row and the feature inventory.

## Out of scope

- Storing field sources in the model: formula strings, clouds, tables, MED references and MED projection.
- The stash's `force` and `acceleration` quantities, and its `impose_field` / `map_cfd_field` APIs.
- Node-scoped pressure, wind or line loads.
- Through-wall or circumferential temperature variation in TUYAU (`TEMP_INF` / `TEMP_SUP`).
- Node temperatures in pipe-volume or mixed studies, and time-varying temperatures.
- Changing today's per-element temperature writer. Element fields keep the staircase and the shared-node rule.
- KD-tree acceleration of cloud sampling.
- 3D surface loads, which get their own plan next.

## Execution

- **Branch.** A new branch in a `D:\tmp` worktree from current `main`. This spec and the plan are committed there
  first.
- **Execution.** Subagent-driven, with opus implementers and reviewers.
- **Tests.** The full suite runs once at the end.
- **Merge.** Merging waits for the user's OK.
