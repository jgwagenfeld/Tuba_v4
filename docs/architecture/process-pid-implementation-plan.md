# Instrumented P&ID implementation plan

**Status:** implemented and qualified on 2026-10-12 for the existing serial-water
subset. The [qualification record](process-network-coupling-results.md#instrumented-pid-review)
records the fresh pandapipes and Code_Aster results and retained evidence.

## Objective and scope

Generate a readable instrumented P&ID from the same process graph used by
pandapipes, and link its components and exact-port values to the existing 3D
review. Reuse the current SVG renderer and review viewer. Procedural Python
remains the editable engineering source; SVG is a one-way drawing export.

The change reaches network serialization, public process exports, review
projection, the authored water example, existing viewer, related tests and
documentation. Numerical backends and structural load mapping are unchanged.
No dependency or separate diagram application was added.

## Declared interface

`ProcessNetwork.pid` optionally holds a `PidDefinition`. Its schema is
`tuba.process-pid.v1`, with immutable records and strict JSON validation:

| Record | Meaning and validation |
| --- | --- |
| `EquipmentDefinition(tag, component_id, kind, description)` | Explicit symbol attached to an existing component. Tanks, pumps and heat exchangers annotate source/sink boundaries; manual/control valves annotate external fixed losses. Symbols add no equipment physics. |
| `Instrument(tag, kind, port_id, description)` | PT/FT require an exact declared port and display calculated absolute pressure/mass flow. PIC/FIC have no process tap or calculated controller output. Tags identify the declared kind. |
| `SignalConnection(source_tag, target_tag)` | Electrical design intent: PT to PIC or FT to FIC, then controller to a control valve. Each controller requires one compatible input and one valve output; each valve permits at most one controller. |
| `PidDefinition(equipment, instruments, signals)` | Globally unique tags, one annotation per component, valid references and no ambiguous component-ID shadowing. Duplicate, dangling or incompatible signals fail before execution. |

Absent declarations preserve legacy JSON and fingerprints. Present declarations
round-trip with archived networks and participate in the bound fingerprint;
changing them requires a new evaluation. Geometry fingerprints and measured
pipe segments remain unchanged. Imported graphs receive no invented tags.

## Completed implementation and acceptance

- [x] Add validated declarations, optional network serialization and public exports.
      Verify strict inputs, immutable records and unchanged legacy fingerprints.
- [x] Declare the authored water example and project its definitions into the
      existing review. Verify exact associations and archive/export round-trips.
- [x] Render equipment, instrument bubbles, a panel controller, solid process/tap
      lines and dashed electrical signals with a legend, full-size view and SVG download.
- [x] Link equipment to graph components and transmitters to exact-port values
      and actual pipe elements. Preserve keyboard focus, failure display,
      reverse selection and candidate reset. Controllers have no invented output.
- [x] Run a fresh small-bore hydraulic rejection and accepted larger-bore
      pandapipes/Code_Aster campaign. Verify sealed inventories and native results.
- [x] Check the built viewer in Chromium, download and parse both SVGs, inspect
      final images, and verify legacy fallback and malformed-declaration refusal.

Focused validation passed 121 backend/network/workflow tests, 14 viewer tests
and 14 example/documentation checks. Browser checks and artifact receipts are
retained in `D:/tuba-runs/Tuba_v4/process-pid-20261012/`. Follow-up documentation
checks validate local links, completed status and Markdown fences. The full
repository suite and published documentation site were not run.

## Example and limits

The water circuit declares TK-101 and TK-102 boundary tanks, FCV-101 on the
existing illustrative `K=5` loss, PT-101 at `L-101.in`, FT-101 at `L-101.out`, and
the FT-101 -> FIC-101 -> FCV-101 signal path. The source still prescribes 10 kg/s.
There are no simulated tank levels, valve characteristics, actuator response
or dynamic controls. Equipment symbols are outside the mechanical pipe model.

The P&ID uses a documented symbol subset with explicit scope. It does not claim
standards compliance, complete plant design, DEXPI export, graphical model
editing or SVG-to-model round-trip. Branching circuits and qualified pump/valve
models require their own hydraulic qualification. The
[review roadmap](process-model-review-study.md#roadmap-and-acceptance) sequences
assumption/candidate comparison, qualified equipment and exchange/agent work.

## Design decisions and references

Keep typed declarations on the authoritative graph instead of maintaining a
second editable topology or independent drawing metadata. Reuse the existing
renderer for the supported serial layout. A full DEXPI authoring stack is
outside this milestone; existing import behavior remains unchanged.

Primary references checked on 2026-10-12:

- [ISA5.1 instrumentation symbols and identification](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa5-1).
- [DEXPI 2.0 instrumentation model](https://dexpi.org/specification/2.0/html/models/Plant/Instrumentation/package-index.html).
