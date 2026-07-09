# Adapy Alignment Policy

## Decision

Tuba may learn from `krande/adapy` architecture as reference-only interoperability input, but Tuba must not vendor or copy `adapy` implementation code. No runtime ada-py bridge ships in Tuba core.

## License Boundary

`ada-py` is licensed GPL-3.0-or-later. Do not vendor adapy code into Tuba unless the project explicitly accepts GPL-compatible obligations. Any future adapter requires an explicit project and license decision before implementation, and must keep Tuba's core package usable without `ada-py`.

## Product Boundary

Tuba remains pipe-native. `TubaModel`, routing, supports, Code_Aster pipe stress export, result states, deformed envelopes, and clash checks remain authoritative. IFC and `adapy` are exchange and interoperability surfaces, not internal optimization requirements.

## Allowed Transfers

- IFC pipe-system semantics.
- IFC round-trip test shape.
- Solver sidecar and name-map concepts.
- RMED artifact manifest concepts.
- Adapter design notes that preserve Tuba's Code_Aster-backed workflow and license boundary.

## Disallowed Transfers

- Direct source copying from `adapy`.
- Mandatory `ada-py` dependency in the core package.
- Runtime `ada-py` bridge code without an explicit project and license decision.
- Replacing `CodeAsterSolver` with a generic FEM exporter.
- Requiring IFC import/export for routing or clash checks.
