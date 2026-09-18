# Solver identity and the Element/Support record fan-out

**Follows:** `2026-09-17-architecture-deepening.md` ("Not in this plan": the group-metadata
fingerprint projection, and the `Element`/`Support` record fan-out)

## Context

Both items change the solver-input identity, so they land as one batch behind one
Code_Aster evidence refresh.

- **Group metadata moved the fingerprint.** W1 found it: adding rack attachment
  points staled the bridge evidence, although the solver never reads group
  metadata. `build_solver_input_identity` hashed `model.to_dict()["groups"]`
  whole, metadata included.
- **Element and Support still fan out.** W3 gave `OperationField` one encoding
  and one rule table; `Support.restraint()` (W7) gave supports one restraint
  record. `Element` and `Support` still carry their fields as loose dataclass
  attributes projected separately into the JSON schema, patch dicts and script
  codegen. (Task 2, not yet specified.)

## Task 1: Group projection (landed)

**Files:** `tuba/analysis/provenance.py`, `tests/test_solver_input_provenance.py`

- [x] Failing tests: adding group metadata leaves the identity untouched; changing
  a group's members or name moves it.
- [x] `_solver_groups_projection`: hash group names plus their member lists
  (`nodes`, `elements`, `supports`); drop `metadata`. The solver reads group
  names (reserved compiler names) and member elements (operation-field scopes);
  metadata is rack/inspection annotation.
- [x] All 34 provenance tests pass.

### Evidence refresh (landed)

The projection is identity-only: no compiled text changes. Three committed studies
carry group metadata and were re-solved on the real runtime and re-promoted:

- `examples/support-rack-review` (rack groups carry attachment points),
- `examples/rack_bridge_demo` (same),
- `examples/hydrogen-plant-layout` (four plant racks).

`study.comm`, `study.mail` and `study.export` are byte-identical in the diff; only
the solved artifacts and the identity attestation moved. The other examples'
evidence already matched (their projection is unchanged) and imports cleanly.

## Task 2: Element/Support record fan-out (landed)

**Files:** `tuba/model.py`, `tuba/schema.py`, `tuba/patches.py`, `tests/test_record_fanout.py`

- [x] `Element.to_dict()` and `Support.to_dict()` are the canonical encodings;
  `TubaModel.to_dict` projects them. Script codegen already projected the model
  payload (`_element_line`, `add_support` lines), so it needed no change.
- [x] `schema.py` holds one property table per record (`_ELEMENT_PROPERTIES`,
  `_SUPPORT_PROPERTIES`); the model schema uses them whole, the patch schema drops
  the model-assigned `id` and adds `op`/`local_id`/`id_prefix`.
- [x] `_apply_add_element`/`_apply_add_support` project the patch record's own
  fields (`asdict`) instead of restating them.
- [x] `tests/test_record_fanout.py` pins the fan-out to the dataclasses: the model
  schema, both patch schema entries and the `AddElement`/`AddSupport` field sets
  must agree with the record fields, so a new field cannot land on one surface
  alone.
- [x] Behavior-preserving: the fingerprint did not move (freshness and evidence
  tests pass on the existing committed attestations; no re-solve needed).

## Verification

- [x] `pytest tests/test_solver_input_provenance.py tests/test_project_freshness.py tests/test_project_evidence.py tests/test_code_aster_study.py tests/test_contact_results.py tests/test_load_path.py tests/test_support_attachment.py tests/test_future_ready_integration.py tests/test_visualization_racks.py tests/test_operating_state_fixtures.py -q` — 116 passed.
- [ ] Full suite: `python -m pytest -q`.
- [x] Every committed evidence folder imports against its current model.

## Not in this plan

- The mixed study becoming solve-ready, the viewer god modules, and the
  duplicated bundle validation (unchanged follow-ups).
- **`imposed_displacement` is not encoded.** The record carries it and reporting
  and contact code read it, but `Support.to_dict()` has never emitted it, so a
  model.json round-trip drops it. Task 2 pins the current behavior instead of
  changing it; deciding whether the encoding should carry the field is its own
  change (it moves fingerprints for any model that uses it).
