# Assemblies as Retained Recipes — Design

**Status:** proposed 2026-09-17.
**Scope:** `RackBay`, `RackRow`, `RackCorner` in `tuba/assemblies.py`, and the two examples that apply them.

## Problem

An assembly is a parametrized structure — a row of rack bays with sections, levels, zones and shoes. Today the examples apply one as a one-shot patch:

```python
rack = RackRow(name_prefix="main_rack", bays=4, ...)
ModelTransaction(model).apply(rack.to_patch(), validate=True)
```

That bypasses `assemble`, so the model records no invocation. The parametric identity (bays, bay length, sections, zone, shoes) exists only in the example's local variables, and a generated model script must unroll the rack's ~30 nodes and elements as `add_node` / `add_element` singles — the dump the model-script lint forbids and the opposite of the retained-recipe property the pipe builder already has. Editing the rack means editing records, not a parameter.

## Measured facts

- `tuba/model.py:551-557`: `assembly_calls` is runtime-only, "never serialized, so a generated model script can write it back as one `assemble()` call without changing model.json or the fingerprint."
- `tuba/assemblies.py:90-135`: `assemble(model, ref, **params)` already resolves a `"module:func"` ref, records the invocation (ref, JSON params, record span), and stamps source lines. `tuba/project/script.py` replays each invocation as one `assemble(...)` line; `tests/test_assembly_replay.py` covers replay, nesting, line stamping and fallback unrolling.
- `tuba/patches.py:235-277`: patch node references resolve through the transaction's local-id map with a literal fallback, so a shoe `AddSupport(node=<pipe node>, attached_to=<local mid node>)` passes the pipe node through and remaps the rack node.
- Applying the same patch the same way assigns the same node and element ids whether it goes through `assemble` or `ModelTransaction` directly; the only difference is the (unserialized) `assembly_calls` entry and source lines. So routing an example through `assemble` leaves its model JSON and fingerprint unchanged.

## Decisions

1. **Add three library-level construction units** to `tuba/assemblies.py`: `rack_bay(model, **params)`, `rack_row(model, **params)`, `rack_corner(model, first, **params)`. Each builds its dataclass and applies `to_patch()` through `ModelTransaction(model).apply(..., validate=True)`, and returns the `PatchResult`. `assemble`, `patches.py` and `project/script.py` are unchanged.
2. **`rack_corner` takes its first row as a JSON params dict** (`first={...}`), because `RackCorner.first` is a `RackRow` dataclass and `assemble` params must be JSON-serializable literals. The unit constructs `RackRow(**first)`.
3. **The examples apply racks with `assemble`.** `examples/hydrogen-plant-layout` and `examples/support-rack-review` call `assemble(model, "tuba.assemblies:rack_row"|":rack_bay", **params)`. Their model JSON is unchanged, so `support-rack-review`'s committed evidence stays fresh; only `assembly_calls` (runtime) and any generated script differ.
4. **The dataclasses stay.** `RackBay` / `RackRow` / `RackCorner` remain the patch builders and are used directly by tests; the unit functions are the authored path.
5. **Shoes stay real node ids.** `shoes=[[<node id>, <station>], ...]` is passed as a JSON list; the ids resolve because the pipe run that created them replays first, in creation order, exactly as it does today.

## Delivery order

1. The three unit functions and their import of `ModelTransaction`.
2. Tests: direct patch and `assemble` produce the same model JSON for each assembly; a generated script carries one `assemble` call and replays to the same model; the invocation ref is recorded.
3. The two examples.
4. Note the follow-on in ADR 0004's plan as delivered for assemblies.

## Out of scope

- Changing `RackBay` / `RackRow` / `RackCorner` geometry, parameters or patch contents.
- `patches.py`, `project/script.py`, and the `assemble` contract.
- A general assembly registry; the `"module:func"` ref is enough.
- Re-solving `support-rack-review`'s evidence (the model is unchanged, so it is not owed).

## Verification

- `tests/test_assembly_units.py`: model-JSON equality between the direct patch and the `assemble` path for `RackBay`, `RackRow` and `RackCorner`; generated-script replay equality; the recorded `assembly_calls` ref.
- Existing `tests/test_rack_assemblies.py`, `tests/test_assembly_replay.py`, `tests/test_model_script.py` stay green.
- `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_examples.py tests/test_official_gallery_models.py -q` and `git status --short examples/*/evidence` shows no evidence change.
