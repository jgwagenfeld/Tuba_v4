# Tuba Piping Engineering

Tuba is a Python-first, pipe-native engineering context for piping and stress engineers who define piping systems, evaluate them with Code_Aster, and review traceable results.

## Language

**Authoring engineer**:
The primary Tuba user: a Python-capable piping or stress engineer with access to a Code_Aster runtime.
_Avoid_: General FEA user, non-technical reviewer

**Core Tuba workflow**:
The complete path from a validated piping model through Code_Aster evaluation to traceable engineering review.
_Avoid_: Export workflow, visualization workflow

**Engineering review**:
Inspection of solver-backed, traceable analysis evidence to support an engineering decision; it is not formal approval or certification.
_Avoid_: Engineering signoff, compliance approval, certification

**Review consumer**:
A secondary user who inspects a shared Tuba review without authoring or solving the model.
_Avoid_: Authoring engineer

**Operation**:
A named real-world operating state authored by an engineer and compiled into a solver-ready analysis case.
_Avoid_: Public load case, scenario

**Analysis run**:
The provenance-bearing record of one Code_Aster evaluation, linking its study, analysis mesh, persistent result state, and numerical results.
_Avoid_: Bare results, solve output

**Result state**:
The persistent authority for imported solver results and their identity, provenance, and diagnostics.
_Avoid_: Plot data, transient results

**Verified result**:
A result whose Code_Aster execution and artifact lineage are attested and suitable for engineering review.
_Avoid_: Any parsed result, fixture result

**Unverified result**:
A historical or compatibility result without complete execution attestation; it may be inspected only with its trust limitation visible.
_Avoid_: Verified result

**Review surface**:
The shareable semantic view used by a review consumer to inspect geometry, solver evidence, diagnostics, and results together.
_Avoid_: Quick-look view

**Official gallery**:
A centrally registered, validated publication record that owns its bundle producer, audience, profile, and solver-backed refresh metadata when applicable.
_Avoid_: Parallel gallery lists, unregistered publication bundle

**Quick-look view**:
A local interactive inspection or export used by an authoring engineer while working with results.
_Avoid_: Review surface

**FE equivalent stress**:
A Code_Aster von Mises field used to inspect finite-element response; it is not piping-code stress and does not establish compliance.
_Avoid_: Code stress, compliance utilization

**Piping-code stress**:
A code-defined stress quantity calculated from the required solver evidence and code-specific factors within an explicit compliance evaluation.
_Avoid_: FE equivalent stress, raw von Mises stress

**Pipe-wall sub-point result**:
A TUYAU result recovered at section sub-points whose wall position is tied to the solver's pipe orientation.
_Avoid_: Reconstructed surface stress

**Unavailable result**:
A quantity that is absent, incomplete, malformed, or non-finite and therefore has no engineering value to display.
_Avoid_: Zero result

**Reaction force**:
The translational force components returned at a restrained degree of freedom.
_Avoid_: Reaction moment, reactions

**Reaction moment**:
The rotational moment components returned at a restrained degree of freedom.
_Avoid_: Reaction force, reactions

**Pipe modelization**:
The engineer-selected structural idealization of a pipe, limited to validated choices such as beam or `TUYAU_3M` and retained with the analysis evidence.
_Avoid_: Arbitrary solver modelization string

**Reference validation case**:
A piping case with an independently established expected response used to validate Tuba's complete engineering translation and result path.
_Avoid_: Runtime smoke test

**Applied input**:
An authored load, pressure, temperature, or boundary condition shown during postprocessing to explain the analysis setup.
_Avoid_: Solver result

**Solver result**:
A quantity returned by a verified Code_Aster analysis and retained with its result provenance.
_Avoid_: Applied input, derived compliance quantity

**Derived compliance quantity**:
A value calculated from verified solver evidence under an explicit piping-code method.
_Avoid_: Solver result, FE equivalent stress

**Model fingerprint**:
The content-derived identity used to decide whether analysis evidence belongs to the exact engineering model that produced it.
_Avoid_: Model revision
