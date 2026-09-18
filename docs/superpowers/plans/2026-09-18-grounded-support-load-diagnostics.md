# Grounded-support load diagnostics

**Follows:** `2026-09-17-architecture-deepening.md` ("Not in this plan": load-path diagnostics for grounded supports)

## Context

`analyze_load_paths` (rebuilt in `04d2ad5`) sums rack loads from the reactions at
attached nodes, per the support-attachment rule: a grounded support standing on a
rack node is not a rack load. But the report then drops grounded supports on the
floor:

- Every grounded support emits the diagnostic `Support 'X' is not associated with
  a rack.` — the same message an attached support on a non-rack node gets. The
  bridge demo's review carries twelve such "warnings", one per rack-foot anchor,
  so a real misattachment drowns in noise.
- A grounded support's reaction (its load to foundation) appears nowhere in the
  report or the review scene, even though `result_state.node_reactions` carries
  it at the support's own node. The bridge demo's twelve anchors carry real load
  (≈3.1 kN vertical at the end bents) that the load-path review does not show.

## Decision

One report, two destinations, honest forces:

1. **`GroundedSupportLoad` record** in `tuba/load_path.py`: `support`, `node`,
   and `force_n` — the reaction at the support's node, `None` until a result
   state or `node_reactions` supplies it. `None`, not zeros: zeros would
   masquerade as a solved result (AGENTS.md evidence rule).
2. **`LoadPathReport.grounded_loads`** lists every grounded support, solved or
   not, so the pre-solve picture is complete.
3. **Diagnostics are for problems only.** Grounded supports are by design and
   produce none. An attached support whose `attached_to` node belongs to no rack
   is the one real problem, and its message says so:
   `Support 'X' is attached to node 'N5', which belongs to no rack.`
4. **The scene projects the same record** (`_build_load_path_scene`): one
   `load_path_vector` per grounded support with a known force (`target: "ground"`
   in metadata, kind unchanged so the viewer renders it untouched), overlay data
   gains `grounded_loads`, and the vector scale reference includes grounded
   magnitudes so all vectors scale together. Issues still come from diagnostics
   only.

## Tasks

### Task 1: Report carries grounded loads

**Files:** `tuba/load_path.py`, `tests/test_load_path.py`

- [ ] Failing tests:
  - A grounded support produces no association and no diagnostic; it appears in
    `grounded_loads` with its node and `force_n is None` (replaces the
    "not associated" assertion in `test_grounded_support_on_a_rack_node_is_not_a_rack_load`).
  - `node_reactions` at the support's node become its `force_n`.
  - An attached support on a non-rack node produces one diagnostic naming the
    support and the node ("belongs to no rack"), and no grounded entry.
  - Bridge evidence (`RackRowExampleEvidence`): `diagnostics == []`; the twelve
    grounded anchors all appear in `grounded_loads` with known forces; the four
    bay rollups are unchanged.
- [ ] Implement `GroundedSupportLoad`, `LoadPathReport.grounded_loads` (with
  `to_dict`), and the diagnostics split in `analyze_load_paths`.
- [ ] Run `pytest tests/test_load_path.py -q`.

### Task 2: Scene projects grounded loads

**Files:** `tuba/visualization/builders/_review.py`, `tuba/visualization/builders/_helpers.py`, `tests/test_visualization_racks.py`

- [ ] Failing tests:
  - A grounded support with a known reaction draws one `load_path_vector` with
    `metadata["target"] == "ground"` and the reaction; the overlay carries
    `grounded_loads`; no `load_path` issue exists.
  - Without reactions it draws no vector and the overlay entry has
    `force_n is None`.
  - `test_unassociated_support_becomes_review_issue` becomes
    `test_misattached_support_becomes_review_issue`: the issue comes from a
    support attached to a stray node; the grounded support in the same model
    produces none.
- [ ] Implement `_build_grounded_load_vector`, extend `_load_path_reference`
  with grounded magnitudes, and add `grounded_loads` to the overlay data,
  object ids and entity refs.
- [ ] Run `pytest tests/test_visualization_racks.py -q`.

### Task 3: Glossary

**Files:** `CONTEXT.md`

- [ ] Add **Grounded support** next to **Attached support**: its restraint acts
  against a point fixed in space; its load goes to foundation and the load-path
  report lists it under grounded loads, not rack loads.

## Verification

- [ ] `pytest tests/test_load_path.py tests/test_visualization_racks.py tests/test_support_attachment.py tests/test_future_ready_integration.py tests/test_operating_state_fixtures.py -q`
- [ ] Full suite: `python -m pytest -q`.
- [ ] No solver input identity changes: `git status --short examples/*/evidence` is clean.
- [ ] No viewer change, fixture regeneration or bundle rebuild: the new vectors
  reuse the `load_path_vector` kind the viewer already renders.

## Not in this plan

- Attributing a rack's summed reaction to individual supports when several share
  one attached node (`_reaction_for_association` returns zeros there today).
- Displaying `grounded_loads` in the viewer's overlay panel (the scene carries
  the data; the panel is viewer work).
- The group-metadata fingerprint projection and the Element/Support record
  fan-out (the identity batch), the mixed study, and the viewer god modules.
