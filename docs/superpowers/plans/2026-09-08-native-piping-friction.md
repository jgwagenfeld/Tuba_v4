# Native piping friction and beam demonstration implementation plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Steps use checkboxes for tracking. No parallel agent execution is required.

**Goal:** Demonstrate native Code_Aster frictional pipe supports on a qualified beam-based piping model, with traceable load history and an interactive review of solved contact behavior.

**Architecture:** Retain Tuba's model -> external-process Code_Aster -> processed result workflow. Use `POU_D_T` for the first qualification and demonstration, and discrete native contact elements for support behavior. Extend existing result states and the existing Three.js review bundle; do not introduce another solver or visualization path.

**Tech stack:** Existing Python/NumPy, Code_Aster, existing unittest tests, JSON scene bundles, Three.js, native SVG for the small history chart, existing Node/Playwright tests.

**Spec:** The user requested a workplan for replacing the V2 custom friction iteration with official Code_Aster behavior, challenged automatic use of TUYAU in favor of beams, and requested an example and considered result visualization. The scope and acceptance criteria below are the implementation specification; `AGENTS.md` supplies the product constraints.

**Status:** Planning only, 2026-09-08. No native friction benchmark has been run and no equivalence has been established. Inspection baseline: `a26646036dff52bb3b308d4fb167a127a3c48418`, with pre-existing dirty viewer, scene-builder, gallery and generated-asset files. Reinspect at execution time and preserve that work; use an isolated implementation worktree.

## Global constraints and decisions

- Production results must come from real Code_Aster artifacts. Missing runtime, unsupported behavior, or failed convergence stops result publication; generating input files is not an engineering evaluation.
- Prefer the existing Python-managed runtime/bridge with external-process execution. WSL, command runners and Docker remain fallbacks. Use `code_aster_doctor` to discover the actual environment.
- Friction contact does not require TUYAU. Qualify contact with beams first; keep pipe entities as pipes in the domain model even when their solver idealization is a beam.
- Add explicit `POU_D_T` selection through the existing `pipe_modelization` API. Preserve the current default during qualification. A repository-wide default migration is outside this plan and needs its own regression evidence.
- Beam elbows require validated flexibility corrections. Code stress intensification is a separate postprocessing operation; never apply a flexibility factor as an SIF or amplify stresses twice.
- Start with small-displacement, fixed-support-frame, unilateral point contact with isotropic Coulomb friction. Static and sliding coefficients are the same scalar initially. No arbitrary rolling friction, clamp-preload model, surface contact search, or dynamic friction model.
- First production support scope: resting shoes, including inclined planes. Reject positive friction on other support types until their normal-force/preload semantics are explicitly implemented. Guides/stops must not silently inherit shoe behavior.
- Use one display path for the example: `tuba/visualization/` + `viewer/`. Leave `tuba/plotting/` as the existing quick-look/export path; no second implementation of this example in PyVista.
- Independent calculations are validation references, never substitute solver results or fabricated demo states.

## Evidence and current gaps

| Location | Observed behavior | Consequence |
|---|---|---|
| V2 `tuba/write_Aster_friction.py` | `DIS_TR` springs; repeated `MECA_STATIQUE`; `k = mu * norm(R) / norm(u)`; four loop passes, no active convergence stop | Historical approximation, not an acceptance oracle for reversal, sticking or opening |
| `tuba/solver/modelisation.py` | `AllPipes` is assigned `TUYAU_3M`; ordinary beams use `POU_D_T`; enum has TUYAU and solid choices | Reuse this common assignment owner when adding beam pipe idealization |
| `tuba/model.py`, `TubaModel.solve` | Existing `pipe_modelization` selection | Extend this entry point instead of adding a competing solve API |
| `tuba/solver/aster_comm.py` | Positive friction selects nonlinear analysis; `LIAISON_UNIL` generation only addresses rests; coefficient is not emitted into a friction law | Unsupported friction must fail explicitly until the native path is qualified |
| `tuba/solver/aster_mesh.py`, `aster_comm.py`, `aster.py` | Pipe mesh, cross-section DOFs, loads and stress recovery contain TUYAU assumptions | Changing only `AFFE_MODELE` is insufficient |
| `tuba/solver/base.py`, `tuba/analysis/results.py` | `FEAResults` and persistent `ResultState` have no dedicated contact results | Add one shared typed contact record and preserve it through conversion/import |
| `tuba/analysis/run.py` | One final result state and publication/provenance checks | Extend for converged history without weakening existing checks |
| `tuba/visualization/builders/_core.py`, `viewer/src/resultReview.js` | Existing result-state selection and overlays | Reuse selection, result IDs, units, inspector and overlay infrastructure |

Primary references, consulted during the discussion:

- [Code_Aster R5.03.17, DIS_CONTACT](https://codeaster.gitlab.io/doc/docaster/manuals/man_r/r5/r5.03.17/Modelisation_des_chocs_et_du_frottement_DIS_CONTACT.html): Coulomb limit in the tangent plane, slip history, loading/unloading, and the distinction between physical stiffness (`DIS_CONTACT`) and penalty stiffness (`DIS_CHOC`).
- [Code_Aster nonlinear discrete behaviors](https://codeaster.gitlab.io/doc/docaster/manuals/man_r/r5/r5.03.17/index.html): supported nonlinear solution context. Verify exact catalogs and validation cases against the installed version; material keyword `DIS_CONTACT` is not itself a choice of behavior relation.
- [Code_Aster POUTRE/COUDE](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.42.01/Mot_cle_POUTRE.html): beam section and elbow correction definitions.
- [Code_Aster SSLX102](https://code-aster.org/doc/v17/manuals/man_v/v3/v3.05.102/index.html): TUYAU ovalisation and elbow/straight interaction; richer section kinematics do not establish that TUYAU is necessary for friction.
- [CAESAR II friction implementation](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/Version-14/335613): finite sticking stiffness and Coulomb-limited sliding force. This supports comparison of physical idealizations, not identical numerical algorithms.
- [V2 implementation](https://github.com/jgwagenfeld/TUBA_V2/blob/SM2019/tuba/write_Aster_friction.py). ROHR2's public feature list confirms friction capability but does not establish an equivalent internal algorithm.

## Task 1 — Qualify the native law and stop silent friction omission

**Files:** Modify `tuba/solver/aster.py`; create `tests/test_code_aster_friction.py`, `tests/integration/test_code_aster_friction.py` and `tests/integration/code_aster/friction_reference.comm`. Use the existing runtime and attestation helpers, not a new runner.

**Interface:** Existing solve/export entry points initially reject positive friction with an actionable unsupported-feature error. The reference `.comm` is an isolated diagnostic model, not a second production generator.

- [ ] Add a regression showing that requesting friction cannot successfully export a study that lacks a friction law. Put the guard at the common compilation boundary; trace solve, export, volume and mixed-study callers. Include negative, nonfinite coefficients in boundary validation.
- [ ] Run `python -m unittest discover -s tests -p test_code_aster_friction.py -v`; demonstrate the missing-law regression, then implement the guard and rerun.
- [ ] Run `python -m tuba.solver.code_aster_doctor --check --json`; record the actual executable/version and readiness outcome. Stop the solve phase if no runtime works.
- [ ] Read the installed behavior catalogs and an official validation case. Exercise `DIS_CHOC` for a stiff penalty support and `DIS_CONTACT` for finite physical stiffness. Do not interpret local constitutive integration terminology as requiring a globally explicit dynamic solve.
- [ ] Build the smallest contact fixture with a known normal preload and a tangential elastic driver. Run it in `STAT_NON_LINE`, with no damping, through preload, sticking, sliding, reversal, opening and recontact. Then attach the same contact to a `POU_D_T` pipe-section beam.
- [ ] Identify actual element-force, displacement and internal-variable outputs, their local axes, signs, units and meaning. Confirm whether status is explicit or must be classified from solved quantities. Never assume `FORC_NODA` at a shared node isolates one support's reaction.

Reference mechanics for a fixed normal force and a scalar elastic driver:

```python
# Independent reference only; never used to fill result artifacts.
limit = mu * normal_force
k_eq = beam_axial_stiffness * tangential_stiffness / (beam_axial_stiffness + tangential_stiffness)
force_before_slip = k_eq * imposed_driver_displacement
breakaway_driver_displacement = limit / k_eq
```

Use `N=10_000 N`, `mu=0.3` as a fixture target, so the sliding limit is `3_000 N`. Establish the preload independently; do not assume the total nodal reaction equals its normal component. For reversal use the incremental slip law, not the monotonic formula above.

**Acceptance gate:** Real converged output demonstrates Coulomb bounds, breakaway, opposing friction during slip, zero contact force after opening, and finite history on reversal. Repeat at half load-step size and at penalty stiffness multipliers 0.1, 1 and 10. Require force/displacement reference agreement within 1% where a closed form applies, force equilibrium residual below 0.1% of characteristic applied load, and documented penetration/stick-compliance bounds. For the chosen penalty value target penetration below `1e-5 m`; adjust based on measured error, not arbitrary large stiffness. Record tolerances before assessing results. A skipped integration test is not a pass.

**Deliverable:** A short measured qualification table added to this plan, with runtime version, behavior chosen, parameters, artifact paths and checks. Select one native behavior for the production shoe; do not expose two algorithms in the public API unless the evidence requires it. If neither qualifies, retain the explicit blocker and report it without restoring the old approximation as a hidden fallback.

## Task 2 — Add a deliberate beam idealization for pipe systems

**Files:** Modify `tuba/solver/modelisation.py`, `tuba/model.py`, `tuba/solver/aster.py`, `aster_mesh.py`, `aster_comm.py`, `aster_loads.py`; inspect/reuse `tuba/compliance/sif.py`, `tuba/compliance/asme_b313.py`, `tuba/analysis/provenance.py`. Create `tests/test_code_aster_beam_pipes.py`; extend the real friction integration test with beam reference cases.

**Interface:** Add `PipeModelization.POU_D_T = 'POU_D_T'`; consume it through the existing `model.solve(pipe_modelization=...)` and study compiler. Serialize the selection in compiler inputs and all artifact fingerprints. Keep `pipe_straight` and `pipe_bend` entity types and IDs.

- [ ] Add export checks for explicit beam selection, ordinary pipe sections, SEG2 beam connectivity, correct local orientation, and no TUYAU-only DOFs or subpoint requests. Add a provenance mismatch check when the selected formulation changes.
- [ ] Implement the selected mapping once in `modelisation_assignments` and thread the selection into mesh and command generation. Preserve source-to-analysis IDs for bend segments and contact helper elements.
- [ ] Implement `POUTRE/COUDE` flexibility on the proper bend groups using the existing `SIFSet.k_i/k_o` source where applicable. Verify the Code_Aster coefficient convention with the installed documentation. Do not silently use unity for unsupported fittings.
- [ ] Trace temperature, gravity, internal pressure and section-force recovery for beam pipes. Explicitly account for applicable pressure end thrust and pressure stress; fail unsupported combinations rather than dropping a load. Avoid adding full advanced pressure-stiffening support merely for this demonstration.
- [ ] Keep code stress calculation in the existing compliance evaluator. Do not label ordinary beam stress as a TUYAU fibre field or a shell-resolved stress. Where a field is unavailable, publish it as unavailable.
- [ ] Run `python -m unittest discover -s tests -p test_code_aster_beam_pipes.py -v` and the existing modelization, study, result and compliance checks affected by the change.

**Acceptance gate:** Real straight-beam axial and bending reference agreement within 1%; elbow response validated against an independent flexibility reference with mesh refinement changing key displacement/reaction by less than 1%. Existing TUYAU and solid selections remain valid. The friction example may use zero pressure, but public beam selection must either support or explicitly reject each requested load/fitting combination.

## Task 3 — Compile native shoe contacts and a continuous load path

**Files:** Modify `tuba/model.py`, `tuba/builder.py`, `tuba/schema.py`, `tuba/patches.py`, `tuba/fragments.py`, `tuba/solver/aster.py`, `aster_mesh.py`, `aster_comm.py`, `aster_loads.py`, `aster_sidecar.py`, `tuba/analysis/provenance.py`. Extend the two friction test files. Keep contact-generation code local to the existing compiler unless its size warrants one focused helper.

**Proposed interfaces:** Extend existing `Support` and `add_support` with `gap: float = 0.0`, `normal_stiffness: float | None = None`, `tangential_stiffness: float | None = None`. Retain `friction_coefficient` and define `direction` for rests as the outward unit normal (default global +Y, consistent with gravity -Y). Missing numerical stiffness uses the documented, qualified selection rule from Task 1; do not bury constants in templates.

Add `load_path: Sequence[str] | None = None` to `TubaModel.solve`, forwarded explicitly to the compiler, mutually exclusive with `load_case`. Each name refers to an existing load case containing absolute endpoint loads. Repeated names are allowed for return to cold. Store the complete ordered path, step controls and stage labels in compiler inputs. Use the final named case as the existing final `load_case` compatibility field; identify history stages separately by index and pseudo-time.

- [ ] Test model/schema/patch/fragment round trips, nonfinite or negative coefficients, zero normal vectors, negative gaps, nonpositive stiffness, duplicate IDs and overlapping normal constraints. Multiple shoes at one pipe node must have distinct support IDs and helper groups.
- [ ] Generate one discrete connector per shoe, with a local orthonormal frame and a fixed support node. Apply the selected native law only to these groups and `ELAS` to beams. Do not also impose the shoe's normal DOF or add `LIAISON_UNIL` on the same contact.
- [ ] Match connector geometric length, initial gap and material distances explicitly; test a rotated support and a model rigidly rotated in space. Do not use the first nonzero component of a normal vector as an axis approximation.
- [ ] Replace the Task 1 guard only for the now-qualified support/formulation combination. Keep explicit rejection for unsupported friction on anchors, guides, springs, clamps, mixed/volume studies and unqualified TUYAU combinations.
- [ ] Compile the ordered path into one continuous nonlinear evolution with endpoint interpolation and automatic substepping. Gravity is established first and retained through heating/cooling. Temperature starts at the declared reference temperature. Preserve contact internal variables across stages; separate independent solves or algebraic load combinations are not a cycle.
- [ ] Archive every converged increment, including stage endpoints and reversals. Validate missing case names, incompatible endpoint load definitions, finite values and monotonic pseudo-times. Reject unsupported path loads explicitly.
- [ ] Include normals, gaps, stiffnesses, formulation, complete load path, solver controls and coefficient basis in solver input identity and sidecar mapping.

**Acceptance gate:** The public API reproduces Task 1 behavior through real Code_Aster. Two tangential directions share the vector bound `sqrt(Ft1**2 + Ft2**2) <= mu*N`; they must not each receive an independent full Coulomb limit. Two supports redistribute load while satisfying global equilibrium. Changes to support/path inputs invalidate stale artifacts.

## Task 4 — Preserve contact results and history through import

**Files:** Modify `tuba/solver/base.py`, `tuba/solver/aster.py`, `aster_comm.py`, `aster_sidecar.py`, `code_aster_runtime.py`, `tuba/analysis/results.py`, `run.py`, `code_aster_artifacts.py`. Extend `tests/test_result_state.py`, `tests/test_code_aster_artifact_import.py`; add contact parser cases to `tests/test_code_aster_friction.py`.

**Interface:** Define one `ContactResult` record in `tuba/solver/base.py`. Add `contact_results: dict[str, ContactResult]` to `FEAResults` and `ResultState`, keyed by support ID. Add `result_states: tuple[ResultState, ...] = ()` to `AnalysisRun`; preserve `results` and `result_state` as final-state accessors. Reuse the existing result-state converters and publication validation for every history entry.

Each contact record contains `support_id`, `node_id`, `status` (`open`, `sticking`, `sliding`, `indeterminate`), global `normal`, compressive `normal_force`, global `tangential_force`, `gap`, global `relative_displacement`, global accumulated `slip`, `friction_limit`, nullable `utilization`, and `status_source` (`solver` or `derived`). Forces are on the pipe; SI units are explicit. Carry native variable mapping and classification tolerances in result metadata. A state has stage index, stage label and solver pseudo-time, not an invented physical duration.

- [ ] Export/import contact element forces and internal variables for every converged increment. Map by persistent support/element ID and `INST`, never by table row order. Distinguish element contact forces from summed nodal forces.
- [ ] Preserve force/displacement/internal-state data together at the same increment. Missing required fields create diagnostics and block verified contact publication; never interpret missing data as zero or open.
- [ ] Derive status only where native outputs require it: use contact opening and slip increments with declared tolerances. `|Ft| == mu*N` alone does not prove sliding. Sticking permits finite elastic tangential displacement; slider animation is not slip.
- [ ] Use `utilization = |Ft|/(mu*N)` only for a positive meaningful denominator. For open or zero-friction supports it is null, displayed as not applicable. Never hide an excess over the limit by clamping the reported value.
- [ ] Update all explicit `ResultState` reconstructions and artifact-copy paths to retain contact fields and history. Attest contact tables and history files in the existing artifact chain. Old bundles without these fields remain readable with no contact claims.
- [ ] Check round-trip preservation, shuffled table rows, malformed/nonfinite values, missing increments and mismatched artifact hashes. Validate every published history state against the same solved study identity.

**Runnable physical assertions in the integration test:**

```python
assert contact.normal_force >= -force_tol
assert np.linalg.norm(contact.tangential_force) <= contact.friction_limit + force_tol
if contact.status == 'open':
    assert abs(contact.normal_force) <= force_tol
    assert np.linalg.norm(contact.tangential_force) <= force_tol
if contact.status == 'sliding':
    assert np.dot(contact.tangential_force, slip_increment) <= work_tol
```

Use `force_tol = max(1.0, 0.001 * characteristic_force)` in N for the benchmark and `work_tol = force_tol * slip_tolerance` in J. Define `slip_increment` from consecutive converged native slip states, never total pipe displacement. Check complementarity/penetration according to the chosen compliant or penalty law rather than imposing exact rigid-contact equations on finite-stiffness results.

## Task 5 — Deliver a reproducible piping example

**Files:** Create `examples/code_aster_friction_review.py`, `tests/test_code_aster_friction_example.py`, `docs/content/examples/native-friction.md`. Reuse `examples/code_aster_artifact_review.py`, `tuba/analysis/code_aster_artifacts.py` and `write_scene_bundle`; register in the existing documentation navigation when verified.

**Interface:** `build_friction_model() -> Model`; `run_example(output_dir, *, artifact_dir=None) -> dict`. Expose `python -m examples.code_aster_friction_review --output-dir .build/friction-review`; optional `--artifact-dir` imports matching attested evidence. With no artifacts, run real Code_Aster through the existing runtime. No silent export-only fallback.

- [ ] Use steel `E=200 GPa`, `nu=0.3`, `rho=7850 kg/m3`, `alpha=12e-6/K`; pipe OD `114.3 mm`, wall `6 mm`. Author a horizontal L in global XZ with 4 m and 3 m straight legs joined by a 0.3 m radius 90-degree bend. Anchor the first end and place shoes on straight portions of both legs. Select `POU_D_T` explicitly, with qualified elbow flexibility and `mu=0.3`.
- [ ] Define absolute stages: ambient/reference 20 C with no gravity; gravity seating at 20 C; heating to 120 C; cooling to 20 C; controlled uplift at one shoe; release/reseating. Use zero pressure in this first example to make friction behavior legible. Explain that uplift is an intentional separate support check, not a claim that heating necessarily causes lift-off.
- [ ] Select shoe positions and uplift force using real pilot solves. Freeze final values in `build_friction_model` once the example shows a resolved stick interval, sliding, reversal, and opening/recontact without mechanisms. Do not alter friction or state thresholds to manufacture the desired labels. Retain the simpler Task 1 benchmark as the quantitative oracle.
- [ ] Solve a separately identified `mu=0` comparison with the same geometry and path. Explain that it is an independent run; do not splice its states into the friction history or claim friction always increases every force/stress.
- [ ] Save raw `.rmed`, contact/section-force/displacement tables, solve attestation, model/compiler identity, converged history and scene bundle. Export a contact summary CSV and a static history SVG from these same solved records.
- [ ] Document the single run command, runtime requirement, geometry/load stages, units, contact idealization, numerical stiffness and limitations. Explain the difference between contact slip, total displacement and residual displacement after cooling.

**Acceptance gate:** A fresh run produces verified artifacts and the same behavioral sequence; import-only regeneration succeeds on matching evidence and fails after changing mu, stiffness or load path. No stress compliance verdict is inferred from the contact demonstration. If a stress field is shown, its beam/code basis is explicit.

## Task 6 — Review contact behavior in the existing web viewer

**Files:** Modify `tuba/visualization/builders/_results.py`, `_core.py`, `_states.py`, `tuba/visualization/scene.py`; extend `viewer/src/resultReview.js`, `controls.js`, `selection.js`, `reviewTables.js`, `renderer.js`, `styles.css` as needed. Add `viewer/test/contact-review.test.js`, `viewer/e2e/friction-review.spec.js`; extend `tests/test_visualization_result_overlays.py`. Reconcile existing dirty changes before editing these files.

**Interface:** One contact-result overlay per `ResultState`, linked to support IDs and result-state ID. `AnalysisRun.result_states` feeds the existing scene result-state list; do not additionally insert its final state twice. Contact history is the ordered series of these records, not a separate anonymous frontend dataset.

### Review layout and interactions

```text
Stage: [Gravity | Heating | Cooling | Uplift | Reseated]  Step [<  12 / 40  >]
3D pipe and supports                     Selected shoe S2
  neutral pipe + undeformed outline      State: Sliding (solver/derived)
  support state marker                   N: ... kN   |Ft|: ... kN
  normal and tangential arrows           Limit: ... kN   Usage: ... % / n/a
  deformed centerline                    Gap: ... mm   Slip: ... mm
                                         Force vs signed tangential travel
                                         [history curve and current point]
```

- [ ] Default to contact review with neutral pipe coloring. Use labeled, shape-distinct markers: open/hollow, sticking/square, sliding/arrow, indeterminate/question. Color supplements labels and shape; reserve red for failures or limit violations, not ordinary sliding.
- [ ] Add separate toggles for normal-force and tangential-force arrows on the pipe. Reuse existing units/selection. Define arrows as forces on the pipe and use one consistent scale per quantity across steps and comparison runs. In-plane direction is the actual solved vector.
- [ ] Reuse the result-state selector with named stage endpoints and previous/next converged-step controls. Keep camera and selected support on step changes. Playback, if included, advances actual converged states without fabricating intermediate contact states. Pseudo-time is not physical time.
- [ ] Keep the existing deformation-scale control independent from the load-stage control. Show a persistent deformation exaggeration label. Gap and slip values always use true results; show the support at its real location. Do not imply contact opening solely because exaggerated pipe geometry separates from the shoe.
- [ ] Add a selected-support inspector and a compact table for all shoes: state, N, |Ft|, mu*N, utilization, gap and slip. Keyboard selection of a table row selects the same 3D support and chart. Open/zero-friction usage is n/a.
- [ ] Draw the small force-versus-travel history in native SVG with a current-step marker, stage labels and changing +/-mu*N envelope. Use signed local t1 travel and its force component; provide t2 selection for two-directional motion. Also expose normal load versus stage. Explain that a projected component plot is not the full vector friction cone.
- [ ] Show residual displacement at the cooled state and comparison-run selection using existing result selection. Preserve separate run identities. Keep stress/displacement overlays available as secondary views without mixing their legends with contact states.
- [ ] Display artifact source, runtime version, formulation and convergence status in the existing provenance/review details. Unknown contact data is visibly unavailable. An unsolved model may show support definitions but never solved state markers.

**Acceptance gate:** Browser interaction against the actually served new bundle proves selection, stage changes, force arrows, chart cursor, units, zero-friction/open state, residual cooled displacement, deformation-scale independence and missing-data behavior. Check a narrow viewport and keyboard navigation. Compare displayed values to archived contact CSV for at least one sticking, sliding and open state. Record bundle hash/URL and screenshots; generated assets alone do not prove the user sees the changes.

## Execution and completion checks

Run focused checks when their task lands. Commands below are execution instructions, not checks already performed:

```powershell
python -m tuba.solver.code_aster_doctor --check --json
python -m unittest discover -s tests -p test_code_aster_friction.py -v
python -m unittest discover -s tests -p test_code_aster_beam_pipes.py -v
python -m unittest discover -s tests -p test_code_aster_friction_example.py -v
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = '1'
python -m unittest discover -s tests/integration -p test_code_aster_friction.py -v
python -m examples.code_aster_friction_review --output-dir .build/friction-review
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
```

Run the new browser test from `viewer/` with `npx.cmd playwright test e2e/friction-review.spec.js`, using the repository's existing Playwright server/bundle setup. Extend that setup only as needed to serve the generated friction example. Run affected existing provenance, mesh mapping, schema, result round-trip, compliance and viewer checks; do not call a focused run the full suite.

- [ ] Tasks 1–4 qualify the solver/data path before the example can claim solved behavior.
- [ ] Task 5 produces the real artifacts consumed by Task 6; UI fixtures remain explicitly test-only.
- [ ] Final delivery includes the example source/run command, runnable reference checks, native-law qualification table, verified portable bundle, contact CSV/history figure, and browser evidence.
- [ ] Record any unsupported support/formulation/load combinations explicitly. Do not claim ROHR2/CAESAR numerical equivalence without actual comparison cases.
- [ ] Keep the current pipe default until a separate migration decision. No custom friction solver, new chart dependency, generic load-history framework or third visualization path is required.

## Plan verification performed

Repository interfaces and current gaps were inspected read-only. This document is the only intended change for the planning task. Implementation, Code_Aster execution, numerical qualification, example generation and browser verification remain unchecked work above.
