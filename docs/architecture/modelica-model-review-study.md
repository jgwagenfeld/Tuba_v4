# Modelica model review: study, vision and roadmap

**Date:** 2026-10-12.
**Status:** Proposed review workflow and roadmap; no new runtime or UI is
implemented by this document.
**Code inspected:** `6e2c975`, including the existing process-network adapter,
coupled evaluator, review exporter and user documentation.

## Vision

Let an engineer inspect the process connections, hydraulic assumptions,
physical pipe layout and measured solver results together. The engineer should
be able to understand a candidate in the browser, inspect its exact Modelica
source in OpenModelica, and trace the operating loads into Code_Aster.

The workflow remains Tuba model -> real Code_Aster evaluation -> processed
structural result review. OpenModelica supplies the supported hydraulic
evaluation; a successful fluid calculation alone does not establish structural
acceptance or piping-code compliance.

## What already exists

The [process-network guide](../content/process-networks.md) documents the
implemented, bounded serial-water workflow. The
[coupling results](process-network-coupling-results.md) record earlier real-run
evidence; this study does not claim a fresh solver run.

| Existing boundary | Review material already available |
| --- | --- |
| `tuba/process/network.py` | Typed components, ports, scenarios, hydraulic requirements and associations to measured Tuba routes and elements. |
| `tuba/process/modelica.py` | Generated `TubaLiquidCircuit.mo`, `run.mos`, bound `network.json`, compiler logs, raw result CSV and an execution manifest. |
| `HydraulicResults.verify_for` | Checks solve-issued evidence against the current bound network, geometry, scenario, source, library and raw measurements. |
| `tuba/process/structural.py` | Verified operating-load mapping with declared pressure reference, contents density and wall-temperature assumption. |
| `tuba/process/workflow.py` and `tuba/search/export.py` | Retained candidates and rejected attempts, hydraulic checks, structural evidence and detached reviews. |
| Existing web viewer | Hydraulic fields labeled OpenModelica; Code_Aster fields for evaluated structural cases; imported DEXPI source IDs and study assumptions. |

The hydraulic subset uses Modelica Standard Library 4.1.0 and constant-property
liquid water in a steady, forward, fully filled serial circuit. The current
adapter invokes an installed `omc` as an external process. A new Python bridge
dependency, Docker service or hosted compiler is unnecessary for this review
study's first milestone.

The narrow DEXPI XML 2.0.1 import supplies topology and source identity for one
selected pipe connection. It does not supply a complete plant model, equipment
behavior, operating conditions or physical dimensions without declared study
inputs. Preserve those limits in the review.

## The missing review surface

Retaining artifacts and displaying colored results does not yet give the user
a dedicated explanation of the Modelica model. The useful next surface is a
read-only inspector in the existing review, covering:

- Component classes and connections, with stable process IDs and corresponding
  Tuba route/element IDs.
- Boundary conditions, medium, units, bore, measured length, elevation change,
  roughness and loss coefficients, including their sources or assumptions.
- The exact generated source and run settings used for this candidate.
- Compiler/library identity, evaluation status, measured checks and limitations.
- The mapping from absolute fluid pressure, temperature and density to the
  structural operating case, with its wall-temperature approximation visible.

Derived tables and diagrams should come from the retained typed network and
generator-owned associations. Do not infer engineering meaning by parsing
display text or maintain another editable model beside the authored inputs.

## Where OpenModelica fits

OpenModelica already fits Tuba's external-process architecture. OMEdit is its
desktop Qt editor, with source, library browsing, simulation and plotting.
Provide a reproducible download that engineers open locally; keep the browser
review available without an OpenModelica installation.
Source: [official OMEdit guide](https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/omedit.html).

There is a practical diagram gap: the current generator emits components and
`connect` equations without graphical placement annotations. Opening the file
in OMEdit enables source inspection, but a useful laid-out circuit diagram
must be provided separately or generated through standard annotations.
The physical 3D layout and the process connection diagram describe different
things; both should use the same declared identities.

For the supported generated subset, create a simple process diagram from the
typed graph. If OMEdit diagram review becomes necessary, add deterministic
placement annotations to the same generator and verify that the equations and
results remain unchanged. A general Modelica diagram renderer or browser IDE
would be substantially broader work.

## Reproducible review download

Extend the existing detached review/evidence export. A download should contain
the exact generated `.mo`, `.mos`, bound network, relevant logs, raw CSV,
execution metadata, source hashes and associated load-mapping records. Preserve
the authored Tuba inputs and imported DEXPI source when they are part of the
candidate. Use the existing archive and evidence inventory owners.

Include a short opening/reproduction guide with the qualified compiler version,
MSL version and source identity, medium, model name and simulation settings.
Bundle necessary custom library sources where distribution is permitted, or
declare the exact required dependency and refuse to claim reproduction until
it is available. Do not include the installed compiler, temporary build output,
caches or unrelated historical studies.

Keep the measured source and results immutable. Run any local reproduction in
a new directory outside the checkout and review bundle. A local OMEdit edit
creates a separate proposed model; it must not overwrite the recorded candidate
or become verified hydraulic evidence merely by producing a CSV. The current
generated-source workflow requires declared input changes and reevaluation
through the existing adapter. General user-authored Modelica import is separate
scope and needs an explicit ownership/mapping contract.

`saveTotalModel` can help export a model and its dependencies for expert
reproduction, subject to dependency distribution rights. It does not replace
the original source/evidence identity.
Source: [OpenModelica saveTotalModel](https://build.openmodelica.org/Documentation/OpenModelica.Scripting.saveTotalModel.html).

## Reviews, checks and evidence identity

A review assessment should identify the candidate and attempt, exact process
inputs and geometry, scenario, Modelica source and library hashes, hydraulic
execution, load mapping and any completed Code_Aster execution. Retain reviewer
scope, rationale and unresolved assumptions with the existing review material.
This is a proposed assessment surface, not a new approval service or database.

Different observations must remain distinguishable:

| Observation | What it establishes |
| --- | --- |
| Modelica source loads/checks | The compiler accepted the particular model; it does not validate engineering assumptions. |
| Hydraulic execution and reference checks pass | Evidence for the recorded supported circuit and scenario. |
| Code_Aster evaluation completes | Structural result evidence for its recorded geometry and operating loads. |
| Human engineering review | An assessment of the stated scope and assumptions, with its own unresolved issues. |

OpenModelica's `checkModel` reports a model check and variable/equation counts.
Numerical/reference checks and engineering review still require their own
evidence. Source: [official checkModel contract](https://build.openmodelica.org/Documentation/OpenModelica.Scripting.checkModel.html).

Changing the route, bore, topology, losses, scenario, medium or relevant library
requires a new evaluation. An earlier assessment remains attached to its earlier
revision. Hydraulic rejection retains its measured fields while structural
checks remain unevaluated; runtime failure remains unresolved. Reference plots
must identify whether they show retained results or a new reproduction.

## Implementation roadmap

| Order | Work package | Completion evidence |
| --- | --- | --- |
| 1 | Modelica source and assumption inspection in the existing review | A user can inspect the exact `.mo`, declared parameters, units, boundaries and process-to-route associations for a candidate, including a hydraulically rejected candidate. No runtime installation is needed to read them. |
| 2 | Reproducible download for OMEdit | A second machine can inspect the source and, with the declared runtime/libraries, reproduce the reference case in a fresh directory. Hashes, settings and differences are recorded. No build/cache payloads enter source control. |
| 3 | Linked process diagram and 3D selection | Selecting a process component identifies its actual route/element association and measured results. Generate a diagram from the typed graph; add OMEdit placement annotations only if required and qualified. |
| 4 | Candidate comparison and scoped assessment | An offset/bore edit shows changed hydraulic inputs and results, mapped mechanical loads and completed Code_Aster findings. The original revision and rejected candidates remain reviewable; stale evidence is visibly unavailable. |
| 5 | User and agent completion | CLI/MCP users and coding agents locate the same retained inputs, checks and review artifacts. Demonstrate inspect -> propose a declared edit -> reevaluate -> compare -> export without inventing solver results or changing requirements. |

Reuse the current process adapter, search archive, coupled evaluator and
`tuba/visualization` + `viewer/` scene path. Keep source inspection read-only;
author edits in the existing Python/process input workflow. Full Modelica
authoring, arbitrary external packages, FMU interchange, transient controls and
broader network/equipment support retain their separate qualification needs
in the [coupled process roadmap](process-network-modelica-and-code-aster-roadmap.md).

## Acceptance and validation limits

The decisive review walkthrough is the existing small serial-water example:
inspect the declared process connections and assumptions, open its exact source
in OMEdit, reproduce the hydraulic case, change the offset or bore through the
authored workflow, and compare the new hydraulic and Code_Aster evidence. Also
exercise a hydraulic rejection, unavailable compiler/library, changed source or
CSV, missing dependency, and a detached review opened outside the author machine.

Use existing process contract tests for source/evidence identity and focused
viewer tests for selection, labels, stale results and unavailable states. Real
reproduction must run OpenModelica; structural acceptance evidence requires
real Code_Aster. Document compiler versions, reference values and tolerances
before comparing results. This document itself introduces no fresh solver,
browser or engineering qualification evidence.
