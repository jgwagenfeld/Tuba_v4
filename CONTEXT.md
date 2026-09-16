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
The provenance-bearing record of one Code_Aster evaluation, linking its solver study, analysis mesh, persistent result state, and numerical results.
_Avoid_: Bare results, solve output

**Solver study**:
The Code_Aster input compiled from a model for one operation, together with the identity of the model it was compiled from.
_Avoid_: Study, export deck

**Evidence**:
The attested artifacts an analysis run leaves behind, kept in the project it belongs to; reviews are built from copies of it.
_Avoid_: Results folder, artifact directory, fixture results

**Analysis mesh**:
The solver-facing discretization retained with stable groups and source-entity lineage as part of an analysis run.
_Avoid_: Display mesh, design geometry

**Result state**:
The persistent authority for imported solver results and their identity, provenance, and diagnostics.
_Avoid_: Plot data, transient results

**Verified result**:
A result whose Code_Aster execution and artifact lineage are attested and suitable for engineering review.
_Avoid_: Any parsed result, fixture result

**Unverified result**:
A result without complete, qualified execution attestation, such as a historical artifact or a run on a fallback runtime; it may be inspected only with its trust limitation visible.
_Avoid_: Verified result

**Review surface**:
The shareable semantic view used by a review consumer to inspect geometry, solver evidence, diagnostics, and results together.
_Avoid_: Quick-look view

**Official gallery**:
A centrally registered publication record: its card, its audience and its publication profile, pointing at the project and study whose review it publishes.
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

**Line load**:
A force per metre of pipe or beam along one fixed global direction, carried in full whatever the element's orientation.
_Avoid_: Distributed wind, nodal force

**Wind load**:
Wind pressure on a pipe's exposed diameter; only the part crossing the pipe's axis loads it, reduced once more by the sine of the angle between wind and axis.
_Avoid_: Line load

**Node temperature**:
An operation temperature given to one model node; each element touching the node varies linearly between its end values, at every solver node.
_Avoid_: Element temperature, nodal field

**Solver result**:
A quantity returned by a verified Code_Aster analysis and retained with its result provenance.
_Avoid_: Applied input, derived compliance quantity

**Derived compliance quantity**:
A value calculated from verified solver evidence under an explicit piping-code method.
_Avoid_: Solver result, FE equivalent stress

**Model fingerprint**:
The content-derived identity, per operation, of everything the solver receives: the model's solver-relevant content and the study's solver choices. It decides whether analysis evidence belongs to the exact engineering model that produced it. Changes the solver never sees, such as the project name or the script's layout, leave it unchanged.
_Avoid_: Model revision, model hash

**Project**:
The unit of Tuba work: one model script together with the study that solves and reviews it and the evidence produced for it.
_Avoid_: Example module, workspace

**Study**:
A project's declaration of which operations are solved, with which solver choices, what must hold for a solve to count as evidence, and how the review is built.
_Avoid_: Solver study, review producer

**Standard review**:
The review a project gets when its study does not build one of its own.
_Avoid_: Example review, default bundle

**Model script**:
The Python script that builds a project's model; it is the only source of that model.
_Avoid_: Model JSON, scene script

**Generated model script**:
A model script written and owned by an authoring session, which may rewrite it after each change.
_Avoid_: Exported script

**Authored model script**:
A model script written by an engineer; tools read it and may propose changes, but never rewrite it.
_Avoid_: Hand-edited generated script

**Pipe run**:
The nodes, elements and supports that one `model.pipe(...)` block, or one replayed pipe-run recipe, builds from builder steps with one section and one material; a generated model script writes it back as those steps.
_Avoid_: Route, piping run

**Authoring session**:
A live working copy of one project's model, shared by agents and engineers through the project's model script, that knows whether the project's review is still current.
_Avoid_: MCP session, studio session, preview session

**Stale review**:
A review whose evidence no longer matches the model, because the model fingerprint of at least one of its operations has changed since it was solved.
_Avoid_: Outdated results, dirty review

**Attached support**:
A support whose restraint acts between its node and another model node instead of a point fixed in space.
_Avoid_: Linked support, connector

**Shoe**:
The one-way contact every rest compiles to: it carries compression, slides with its friction coefficient and lifts off.
_Avoid_: Unilateral zone

**Solver choices**:
A study's declared choices for compiling its operations: the pipe modelization, the solver segments, a load path and its step, and which elements become 3D solids. They are part of the model fingerprint, and they never say how Code_Aster runs.
_Avoid_: Solver options dict, runtime settings

**Code_Aster runtime**:
How Code_Aster runs on this machine: execution method, distribution or image, bridge, command and timeout. Never a study's choice; it is the production adapter behind the solver port.
_Avoid_: Solver choices, solver configuration

**Staged run**:
An analysis run's evidence copied into a review bundle, one folder per operation, with every file the bundle names covered by that run's attestation.
_Avoid_: Artifact directory, bundle assets

**Publication profile**:
What a review bundle of one kind must hold, run by run, to be published: the result families each run shows, and the files its attestation must cover.
_Avoid_: Bundle type string, gallery badge
