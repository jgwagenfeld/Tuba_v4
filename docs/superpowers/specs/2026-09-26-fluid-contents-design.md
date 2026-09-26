# Operation-specific fluid contents

**Status:** Approved by the user, 2026-09-26. Implemented on `codex/fluid-contents`; see the implementation plan for qualification evidence and limitations.
**Basis:** Package A of `docs/superpowers/plans/2026-09-26-library-reliability-and-v2-parity.md`.
**Branch:** `codex/fluid-contents`, based on completed reliability milestone `ca17624`.

## Outcome and boundaries

An engineer can define empty, operating-fluid and water-filled hydrotest states
of the same pipe model, solve supported states with Code_Aster, and review the
separate metal, insulation and contents masses alongside imported reactions.
Existing models remain empty by default. Density and pressure are independent.

This package supports fully filled 1D straight pipes and bends in `TUYAU_3M` and
`POU_D_T`. It does not add partial filling, free surfaces, fluid dynamics, pressure
head, material curves, reducers, native solids or nonlinear contact histories.
Existing formulation restrictions remain: `POU_D_T` rejects internal pressure;
pressurized hydrotest evidence therefore uses `TUYAU_3M`. Both formulations get
empty/operating-density/water-density gravity references, clearly described as
weight-only cases where pressure is zero.

## Design choice

Reuse `OperationField` with a new quantity, `fluid_density`, in kg/m3. This keeps
the existing scope, overlap, serialization and solver-identity mechanisms.
Reuse the compiler's existing insulation mass adjustment for additional contents
mass. No new fluid object hierarchy, material catalog, dependency or solver is needed.

Two alternatives were considered: a separate contents-assignment subsystem would
duplicate selectors and provenance; a scalar density on every pipe would prevent
one model from expressing different operations. Neither is needed for this package.

## Authoring and admission

```python
empty = model.define_operation('Empty', gravity=True)
operating = model.define_operation('Operating', gravity=True, pressure=1e6)
operating.add_field('fluid_density', 800.0, route_id='P-100')
hydrotest = model.define_operation('Hydrotest', gravity=True, pressure=1.5e6)
hydrotest.add_field('fluid_density', 1000.0, route_id='P-100')
```

- No field means empty; density zero explicitly means empty. Positive density
  means the bore is completely filled. Values must be finite real numbers >= 0;
  strings, booleans, complex values and `None` are rejected without coercion.
- Accept uniform fields over all pipes, a group, a route, complete route station
  spans, or named elements. Default `all` means all pipe elements; structural
  beams/bars/cables do not acquire fluid mass. Explicit groups/routes/elements
  containing non-pipe elements are rejected rather than partially applied.
- Each selected pipe must use a `PipeSection`. Empty selections and missing
  explicit element IDs fail. Station spans must cover whole elements, using the
  existing line-load endpoint tolerance of 1e-9 m. No automatic element splitting.
- Conflicting overlaps fail even when gravity is disabled. Identical overlapping
  densities agree and apply once; they never add. Reject multiple competing
  selectors in a fluid field rather than choosing one by precedence.
- Reject node scope, direction vectors, linear/piecewise profiles, and irrelevant
  station selectors outside route scope. Validation names the case, field and
  offending selection/value. Mutation after construction cannot bypass validation.
- Keep the shared validation owner in `tuba/validation.py`. Admission, quantities
  and export consume that owner; no separate competing physics validator.

## Persistence and compatibility

`OperationField.to_dict()` remains the canonical field encoding. Extend the schema
quantity enum; operations keep their existing payload shape and default behavior.

Current `LoadCase.fields` are dropped by `to_dict`, `from_dict` and generated
scripts, although resolved operations carry fields through this type. Close that
gap as part of this package:

- Add trailing optional `fields=None` to `Model.define_load_case`, accepting the
  same field records/dictionaries as `define_operation`. Reuse one private field
  construction path; do not introduce a base-class hierarchy or duplicate rules.
- Emit `load_cases[name]['fields']` only when nonempty, deserialize it, validate
  fields on both named load cases and operations, and replay nonempty fields in
  generated scripts. Old empty load-case JSON and generated calls stay unchanged.
- Check canonical JSON, generated-script replay, and authored-project reload for
  empty, operating and hydrotest cases. Authored Python must never be rewritten.
- Existing solver identities already include resolved `fields`. Density, scope,
  selected group members, bore dimensions and selected case changes must stale
  previous evidence. No compiler/schema identity bump is needed if old admitted
  models retain identical canonical inputs and compiler output; prove that with
  representative existing fixtures before deciding otherwise.

## Physical quantities and public API

Extend existing functions with keyword-only `operation: str | None = None`:

```python
physical_properties_for_element(model, element, *, operation=None)
element_quantities(model, element, *, operation=None)
quantity_takeoff(model, *, operation=None)
```

An explicit name resolves through the existing operation/load-case namespace.
An unknown name raises. `None` retains the current dry metal-plus-insulation
quantity meaning; it never silently chooses the first operation.

For a selected density rho and nominal bore `ID = OD - 2*WT`:

```
bore_area = pi * ID**2 / 4
fluid_mass_per_length = rho * bore_area
total_mass_per_length = pipe_mass_per_length + insulation_mass_per_length + fluid_mass_per_length
fluid_mass = fluid_mass_per_length * element_length
```

Bends use the existing true arc length. Corrosion allowance does not enlarge the
nominal bore in this package, matching the existing section-property convention.
Do not change stiffness, external geometry, wind diameter or insulation quantities.

Add `fluid_density_kg_m3`, `bore_area_m2`, and `fluid_mass_kg_per_m` to physical
properties; add `fluid_mass_kg` to element quantities. Add `pipe_mass_kg` and
`fluid_mass_kg` to takeoff records/totals/groups so all three masses can be checked
independently. New dataclass fields are appended with defaults to preserve existing
constructor calls. A takeoff records its explicit operation name; omit that label
from old dry serialized takeoffs. Added mass columns are additive API output.

Resolve density assignments once per takeoff/compilation, using private helpers
in `tuba/physical.py`; do not add global caches or another public configuration API.
Derived masses must also be finite; finite inputs that overflow a derived quantity
fail before solver writes. Quantity calls refuse malformed fluid assignments.

## Code_Aster compilation and unsupported combinations

For supported 1D studies reuse the insulation material override, with effective
`RHO = total_mass_per_length / metal_area`. Preserve original E, nu, alpha and
section properties; do not mutate the source material or add gravity twice.
The operation's gravity flag controls whether weight is applied. Gravity-disabled
cases still retain their authored contents and reported mass.

Extend preflight before directory creation, meshing or replacing existing files:

- Any fluid field in a selected solid-volume or mixed/CAD study is rejected,
  including an explicit zero-density field. Other unselected operations do not
  block an otherwise supported empty study.
- Fluid fields are not qualified for native friction/contact or load-path studies.
  Inspect every selected history case, not merely the final endpoint. Preserve
  current pressure, thermal and formulation guards.
- Apply these guards to diagnostic `export_study`, full export, direct volume/mixed
  exporters, `Model.solve` and project solves. Existing artifact directories must
  remain unchanged on rejection, including forced project solves.

Likely owners are `aster.py`, `compiler_contract.py`, `aster_volume.py`,
`mixed_study.py`, `aster_contact.py`, and project preflight where required by a
failing boundary test. Do not build the broader Package D preflight framework.

## Reports and example

Add an input table `operation_quantities`, built through the existing model-table
registry, with one row per named case: case name, gravity flag, pipe mass,
insulation mass, fluid mass and total mass. It is explicitly calculated input
data, not a solver result. Empty models produce an empty table. Group and element
breakdowns remain available through the takeoff API.

Add one procedural `examples/fluid_contents.py` example: a supported insulated
pipe route, empty/operating/hydrotest operations, TUYAU solves, imported reactions
and displacements, and an engineering review using the existing web-scene path.
Missing Code_Aster fails loudly before result publication. Do not use generated
or hand-entered values as solver output.

## Numerical acceptance, fixed before implementation

Independent expectations must be calculated in tests from geometry and density,
not from the new physical-property functions. The following 2 m straight example
uses OD 0.1 m, WT 0.01 m, steel density 7850 kg/m3, insulation thickness 0.02 m,
insulation density 100 kg/m3, and g = 9.81 m/s2:

| Contents density kg/m3 | Fluid mass kg | Total mass kg | Vertical reaction N |
| --- | --- | --- | --- |
| 0 | 0 | 45.8986686689 | 450.265939642 |
| 800 | 8.04247719319 | 53.9411458621 | 529.162640908 |
| 1000 | 10.0530964915 | 55.9517651604 | 548.886816224 |

- Pure mass/volume calculations: `rel=1e-12`, `abs=1e-12`.
- Straight gravity force and moment reactions: `rel=1e-5`, `abs=1e-6`.
- Bent-route total force and moment: `rel=5e-3`, `abs=1e-6`, compared to independent
  arc integrals, allowing the existing line-mesh chord approximation.
- Reference bent route: 2 m along +X, quarter-circle radius 0.5 m in XY, then 1 m
  along +Y. Length is `3 + pi/4`; `integral(x ds) = 4.75 + pi/2` and
  `integral(y ds) = 0.75 + pi/8`. With downward uniform q, base reactions are
  `Fz=q*L`, `Mx=q*integral(y ds)`, `My=-q*integral(x ds)`.
- Straight cantilever deflection: compare with independent distributed-load beam
  theory within 3%; also verify filled/empty displacement ratio follows total
  mass ratio within 0.1% for the same linear model and gravity-only loading.
- Matrix: straight/bent x bare/insulated x TUYAU/beam, each with densities
  0/800/1000. Add a TUYAU pressurized hydrotest and pressure-with-zero-contents
  case to prove pressure and density are independent. Preserve beam pressure
  rejection. Add a gravity-disabled case with a known nodal force to detect any
  change in stiffness or accidentally applied contents weight.
- Invalid input, conflicting/identical overlaps, station cuts, serialization,
  replay, stale artifact refusal and unsupported-boundary side effects require
  targeted regression tests. Include two elements sharing a material but carrying
  different densities, so an override cannot contaminate adjacent pipes.
- Add `tests/test_code_aster_fluid_contents.py` to the existing mandatory gate.
  Portable tests belong in `tests/test_fluid_contents.py` and existing owning
  suites. Required real references must pass with zero skips; never relax these
  tolerances solely to accommodate an observed failure.

## Delivery and review

After written-spec approval, write the implementation plan in three testable
tasks: (1) admission/persistence/quantities, (2) compilation/preflight/provenance,
(3) reports/example/real qualification. Execute on this isolated branch, then
perform one fresh read-only review. Milestone 1 remains independently reviewable;
no merge, push or publication is part of this package.

Self-review: every Package A requirement is covered above. The pressure limitation
is explicit, old defaults remain dry, additional mass has one physical owner,
legacy field persistence is included, and unsupported cases fail before side
effects. This document specifies the approved design; it is not evidence that fluid contents already work.
