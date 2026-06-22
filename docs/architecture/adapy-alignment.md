# Adapy Alignment Policy

## Decision

Tuba may learn from `krande/adapy` architecture and may provide a default-off optional bridge, but Tuba must not vendor or copy `adapy` implementation code.

## License Boundary

`ada-py` is licensed GPL-3.0-or-later. Do not vendor adapy code into Tuba unless the project explicitly accepts GPL-compatible obligations. Any adapter must import `ada` at runtime behind an optional dependency and must keep Tuba's core package usable without `ada-py`.

## Product Boundary

Tuba remains pipe-native. `TubaModel`, routing, supports, Code_Aster pipe stress export, result states, deformed envelopes, and clash checks remain authoritative. IFC and `adapy` are exchange and interoperability surfaces, not internal optimization requirements.

## Allowed Transfers

- IFC pipe-system semantics.
- IFC round-trip test shape.
- Solver sidecar and name-map concepts.
- RMED artifact manifest concepts.
- Optional bridge APIs that are disabled when `ada` is not installed.

## Disallowed Transfers

- Direct source copying from `adapy`.
- Mandatory `ada-py` dependency in the core package.
- Replacing `CodeAsterSolver` with a generic FEM exporter.
- Requiring IFC import/export for routing or clash checks.
