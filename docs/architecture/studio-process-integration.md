# Studio process integration

**Updated:** 2026-10-12. **Scope:** the supported serial-water process network
inside normal Studio Build, Solve and Review. The core hydraulic-to-Code_Aster
workflow has fresh native qualification. Final visible stale/P&ID, restart and
failure lifecycle checks remain pending; the earlier campaign qualifications
remain separate evidence.

## Authored project contract

`model.py` exposes `model: TubaModel` and optional
`process: BoundProcessNetwork`. The declaration must verify against the actual
model geometry. A project without `process` follows the existing structural
workflow. A malformed or mismatched declaration reports its error explicitly.

The [water project](../../examples/process_network/model.py) keeps its
procedural route, explicit sections, graph, equipment and instruments together
in one authored source. Its `PIPE_SIZE` and `OFFSET_M` parameters also serve
the retained-candidate campaign's existing `build_model` / `process_inputs`
interface. It can be copied with its
[study](../../examples/process_network/study.py) and opened with installed Tuba;
it imports no other checkout example.

`study.py` declares exactly one `LOAD_CASES` operation matching the scenario ID,
`SOLVER_OPTIONS = {"pipe_modelization": "TUYAU_3M"}`, and an explicit
`WALL_TEMPERATURE_MODEL = "bulk-fluid-equals-wall-steady"`. The cold authored
model contains no operating fluid case. After current hydraulic evidence
passes all declared requirements, Studio maps verified pressure, fluid contents
and wall temperature onto a copy. The same copy supplies Code_Aster Solve,
result identity and the existing `build_study_review` path. Mapping preserves
the authored model and source.

## One shared drawing and result contract

The typed process graph supplies the existing SVG schematic and associations
to mechanical elements. Before hydraulics, the scene carries
`tuba.process.declaration.v1`, with `status`, `bound_fingerprint`,
`geometry_fingerprint`, `scenario_id`, `operation` and `schematic`. It carries
no numerical result segments or fluid overlays. Declared boundary inputs and
route dimensions remain distinguishable from measurements. Missing measured
values read **Not evaluated**.

An evaluated scene uses the existing `tuba.process.review.v1` projection with
native verified hydraulic measurements, solver provenance and requirement
checks. A rejected hydraulic run remains inspectable; it cannot create
structural evidence. Code_Aster fields require completed, verified and imported
Code_Aster artifacts. A drawing or export file never establishes a solve.

Build and Review expose **P&ID** through the existing full-size SVG dialog.
Selection keeps its current component/port-to-route association. **Run
hydraulics** sits beside **Solve** in the existing Studio flow. The existing
`tuba/visualization` scene contract and `viewer/` renderer own these views;
there is no additional application or graphical engineering source.

## Jobs, evidence and freshness

`GET /api/project` exposes `process` with `available`, `status`, `can_run`,
`error` and `bound_fingerprint`. Its lifecycle is `not_evaluated`, `running`,
`passed`, `rejected`, `failed` or `stale`. `POST /api/process/run` accepts an
empty JSON object and starts an asynchronous pandapipes job. Studio emits
`process_started`, `process_finished` or `process_failed` and publishes the
current scene. The action uses existing request authorization, job exclusion
and source-revision rules.

Hydraulic evidence is reusable only while its solve-issued artifacts verify
for the current bound inputs. Geometry, section/bore, graph, P&ID declaration,
scenario or requirements changes invalidate that match. Relevant study edits
invalidate structural readiness and previously mapped structural results.
Unsaved editor text remains pending until **Run model.py** executes it. A job
finishing after its input revision changed cannot attach to the replacement
model. Failures and restarts cannot silently adopt evidence from different
inputs; restart requires a fresh hydraulic run.

The mapped model is the structural freshness authority. A matching cold
geometry preview alone is insufficient to reuse an operating Code_Aster result.
Native process diagnostics and structural artifacts retain their solver
identity. Generate task diagnostics outside tracked source and preserve small
logs and manifests with required failure evidence.

## Implementation and acceptance plan

| Step | Work | Acceptance evidence |
| --- | --- | --- |
| 1 | Expose optional authored process declarations in Build | The normal project loader yields valid `model` and `process`; an unsolved SVG includes equipment, exact-port taps and signals, with no invented measurements or solver fields. Malformed declarations fail; structural-only projects and legacy reviews still open. |
| 2 | Add asynchronous hydraulic execution and its scene projection | Real pandapipes input/results and dependency identities are retained. Passing and rejected requirement checks display actual values; runtime failures remain explicit. Authorization and concurrent-job exclusion use existing Studio rules. |
| 3 | Gate mapped structural Solve and Review | A small-bore hydraulic rejection prevents Code_Aster execution. A current passing run enables real `WaterOperating` Code_Aster evaluation. Source/model remain unchanged, and Review contains the corresponding hydraulic and imported structural evidence. |
| 4 | Verify edits, stale inputs and interruption | Geometry/bore, graph, scenario, requirement and study changes block mismatched evidence. Late jobs cannot publish to newer inputs; failures and restart do not silently restore structural readiness. |
| 5 | Verify the existing Studio interaction | P&ID is reachable in Build and Review; component and transmitter selection links to the route. Full-size view, keyboard/focus behavior and SVG download pass; pending editor text remains visibly distinct from executed source. |
| 6 | Qualify the authored project end to end | Source-only project launch, smaller-bore rejection, larger-bore hydraulic pass, real Code_Aster Solve, Review and a requirements-only edit pass in a fresh browser workflow. The requirements edit must invalidate dependent evidence while preserving mechanical identity; backend checks cover geometry and section edits. Record exact commands, dependency/runtime identities, artifact hashes, numerical outcomes and browser receipts. |

Focused source, declaration, lifecycle and viewer tests are implementation
checks. Step 6 also requires real pandapipes and Code_Aster execution plus live
browser receipts. The user guide lives in
[Process networks](../content/process-networks.md#open-the-authored-project-in-studio).
Local qualification evidence is retained under
`D:\tuba-runs\Tuba_v4\studio-process-20261012`; this path is an evidence
location, not a portable dependency.

## Qualification record

The fresh Studio run used pandapipes 0.15.0 and the existing WSL Code_Aster
runtime. The retained scene projections establish these hydraulic outcomes for
the authored 10 kg/s scenario:

| Case | Measured outcome | Receipt |
| --- | --- | --- |
| Smaller bore | Rejected: maximum velocity 4.643 m/s exceeds the declared 3 m/s limit. | `rejected-scene.json` |
| Larger bore | Passed: maximum velocity 2.106 m/s, inlet absolute pressure 318.304 kPa and mass flow 10 kg/s; all declared hydraulic checks pass. | `accepted-fluid-scene.json` |
| Mapped `WaterOperating` | Real Code_Aster evaluation through Studio completed and native structural artifacts verified; the authored model still has no fluid operating case. | `native-validation.json` |

`structural-scene.json` contains the matching passed hydraulic projection and
imported Code_Aster displacement, reaction force, reaction moment, internal
section forces, FE VMIS stress and TUYAU subpoint stress fields. The native
receipt records `review_stale: false` for this completed revision. FE VMIS is
labeled as FE stress, not piping-code stress; these results do not establish
piping-code compliance or broader equipment/circuit qualification.

Validation scope at this checkpoint:

- Focused backend Studio process controls: **24 passed**. Portable fixtures
  cover stale inputs, malformed native evidence, mapped copies, authorization,
  job cleanup, late publication, restart and watcher survival.
- UI checks: **123 passed**, plus a later targeted batch of **33 passed**.
  The shared-CSS P&ID dialog fixture passed at 1680 x 1100, 1200 x 800 and
  900 x 650; Close and Download remain reachable while the body scrolls.
  These layout fixtures are distinct from live Studio solver/browser checks.
- Source example, process-network, P&ID and documentation checks: **103
  distinct checks passed across the initial run and retry**. The initial
  sandbox-restricted run had three temporary-directory setup errors; the
  authorized rerun passed all four new example checks.
- The older Studio/project/mesh selection reported **48 passed and four
  failures**. All four failures reproduced against unchanged `c8b077c` source:
  the unverified-result trust expectation, the invalid-study error expectation
  and two shell-worker import-count expectations. They remain recorded
  baseline failures in `backend-validation.md`.
- **The full test suite was not run.** Final live visible stale/P&ID behavior
  after the requirements-only edit, restart and error workflow remain pending
  receipt. Passing portable lifecycle tests do not complete those browser
  acceptance checks.

## Supported boundaries

This integration uses the already qualified steady serial-water hydraulic
subset and its explicit operating assumptions. The illustrative control valve
is an external fixed loss; tank levels, valve curves, actuator response,
feedback-control dynamics and equipment structural bodies are not simulated.
The declared wall-temperature approximation supplies steady thermal loads,
not heat transfer or flow-induced vibration. Broader circuits, new equipment
models, a graphical editing canvas, DEXPI export and piping-code compliance
claims require separate work and qualification.
