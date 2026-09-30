# Tuba v4 library architecture and capability scope

Reviewed 2026-09-30 on the cleanup branch based on `ac00d69`. This page replaces the July
inventory, which described several APIs and standards helpers that have since
been retired. The public manual owns current usage; the links below lead there.

## Production workflow

1. Author a procedural Python model and its study configuration.
2. Validate the model and the selected solver inputs.
3. Export the study and run Code_Aster as an external process.
4. Import and validate the solver artifacts and their lineage.
5. Review or report those processed results through an existing display path.

Exported input files alone are an incomplete handoff. Stress, displacement,
reactions and operating-state results require imported Code_Aster evidence.
Missing runtime or evidence must remain an explicit blocker.

## Current references and owners

| Topic | Current reference | Implementation |
| --- | --- | --- |
| Architecture and ownership | [Current architecture](../content/architecture/index.md) | `tuba/model.py`, `tuba/builder.py` |
| Authoring inputs and limits | [Modeling](../content/modeling.md) | `tuba/validation.py`, `tuba/verify.py` |
| Solve, import and review | [Workflow](../content/workflow.md) | `tuba/solver/`, `tuba/project/`, `tuba/analysis/` |
| Public Python API | [Public API](../content/reference/public-api.md) | The owning Python modules |
| Reports and display contracts | [Visualization](../content/architecture/visualization.md) | `tuba/reporting/`, `tuba/plotting/`, `tuba/visualization/`, `viewer/` |
| Native friction evidence | [Qualification and limits](../content/engineering/native-friction-qualification.md) | `tuba/solver/aster_contact.py`, `tuba/solver/contact_results.py` |
| Planned engineering packages | [Reliability and V2 parity](../superpowers/plans/2026-09-26-library-reliability-and-v2-parity.md) | Packages B-J remain separately scoped |
| Standards policy | [Piping standards checks: retired](b31j-compliance-migration.md) | No built-in B31 evaluator |

Python remains the engineering authoring language. Studio and MCP inspect,
verify and solve the authored project; authored scripts retain their procedural
structure. Construction units support reusable composition.

Keep both result-display paths: PyVista quick-look/export in `tuba/plotting/`,
and reviewable web scenes in `tuba/visualization/` plus `viewer/`. Notebook
HTML and Blender exporters have live callers and remain supported. A second
frontend implementation or a generic solver framework would add maintenance
without closing the engineering gaps below.

## Supported slices and explicit limits

- Linear 1D piping supports operation-specific contents, with separate metal,
  insulation and contents mass. Pressure uses `TUYAU_3M`; `POU_D_T` pressure
  and tee/branch flexibility remain unsupported.
- Native point-shoe contact histories support the qualified uniform-temperature,
  gravity and nodal-force slice. Pressure, contents and operation fields remain
  blocked on that history path.
- Native straight/bend/tee volume studies have mechanical reference cases.
  Thermal loading, wind, line loads, insulation and contents are rejected by
  the volume exporter.
- Imported STEP components support geometry, mesh and diagnostic mixed export.
  Their exported study remains explicitly blocked from production execution.
- The web viewer already provides attributable result-step envelopes within a
  load case. Signed governing component results across compatible cases remain
  planned.
- Built-in ASME B31 evaluators and B31J/Appendix D factor helpers are retired.
  Users own the applicable standards, checks and acceptance criteria.

## Cleanup completed in this review

Repository searches covered tracked Python, viewer source, tests, notebooks,
examples, documentation, public exports and subprocess entry points.

- Removed the superseded single-sample friction classifier; the active
  classifier reads the complete contact history.
- Removed three unused viewer exports and unused local-axis/route-HTML helpers.
- Removed unused imports and the plotting-only I-beam dimension wrapper.
  IFC now reads the same section dimensions from `tuba.geometry.profiles`.
- Replaced this obsolete feature inventory and corrected the routing scope
  record. Historical implementation plans remain as qualification history.
- Retained CLI/subprocess solver helpers, artifact parsing, notebook exports,
  both visualization paths and tolerant bundle readers.

These changes do not implement new solver physics or qualify new formulations.
Undocumented deep imports of removed helpers are outside the retained facade.

## Findings to address before expanding features

The two high-priority correctness findings have been fixed. Routing acceptance
requires a true evaluator verdict and finite, present enforced evidence; missing
support reactions cannot hide behind another valid reaction. Plotting preserves
unavailable result fields as `NaN`; exports that require complete fields reject
incomplete evidence before writing. Raw RMED plots retain annotated helper-node
stress gaps. Genuine solver zero values remain available. PLY exports now write
their computed stress colors into the file.

| Priority | Finding | Evidence and next action |
| --- | --- | --- |
| Medium | Several routing inputs are exposed without enforcement. | Nozzle, displacement and operating-clearance acceptance limits; slope, waypoints and named zones; some cost weights and thermal preferences are not consumed. Reject unsupported requests or explicitly report the checked scope. |
| Medium | Resolved local temperatures do not reach every result consumer. | The PyVista surface mapper publishes case-default `TEMP`; web reference ratios explicitly refuse spatial temperature fields. Carry the resolved engineering field into the existing review contract. |
| Medium | Study eligibility is not fully inspectable before export. | Some volume restrictions are checked after creating the output directory. Move those checks into the existing pure study-input/compiler owner. |

The remaining findings are recorded for follow-up. Synthetic regression cases
establish acceptance and availability behavior; numerical qualification requires
real Code_Aster evidence.

## Next engineering features

These are already tracked in the reliability plan, rather than newly discovered
requirements. Prioritize completing the existing workflow:

1. Temperature-dependent material stiffness and expansion (Package B).
2. Filled, pressurized friction histories and heated native solids (F and E).
3. Qualified imported STEP solves, artifact import and result display (G).
4. Signed cross-case governing results with operation/increment lineage (H).
5. Concentric reducers, automated convergence studies and traceable catalogs
   (C, I and J).

Each package needs independent references and real Code_Aster
solve/import/review evidence. Operation-specific contents and required numerical
qualification gates are already shipped.

Modal/seismic analysis, fatigue, bellows, specialized valve/flange models,
eccentric reducers and partially filled contents remain separate product
decisions. Their absence does not authorize expansion of a cleanup change.

## Cleanup verification

The cleanup branch incorporates the subsequent onboarding and bridge fix
`ac00d69`. Validation covered:

- 97 focused Python tests passed, with 16 subtests passed and two opt-in skips.
- 47 plotting, IFC, documentation and browser-runtime tests passed in a separate
  environment synchronized to `uv.lock`. Three generated-HTML checks skipped
  because a strict documentation-site build was not part of this change.
- The complete viewer unit suite and production build passed.
- Release checks rebuilt identical viewer assets from a clean Git snapshot and
  verified that an installed wheel serves its exact packaged assets.
- Two real WSL Code_Aster tests passed without skips: a loaded pipe smoke and an
  independent cantilever displacement/reaction reference. Their JUnit evidence
  is retained locally at `.build/cleanup/real-code-aster.xml`.

The full Python suite and full solver-reference qualification were not rerun.
The shared developer environment lost dependency files during validation; the
affected checks passed in the isolated environment. Its cause was not established,
and this cleanup did not repair the shared environment.

The follow-up correctness checks used the same isolated locked environment:

- Routing regressions passed, including failed verdicts, invalid limits,
  non-finite values, partial support coverage, genuine zeros and rescoring.
- Plotting availability, scenes, reactions, RMED and notebook-backend checks
  covered missing fields, unknown spans, member-local stress, annotated RMED
  gaps and PLY color readback.
- 22 documentation checks passed; three generated-HTML checks skipped.
- Three browser-runtime/package checks passed, including the production build.
  After the final PLY fix, the shipped browser ZIP was refreshed and compared
  byte-for-byte with the runtime generated from the final Python source.
- Both real WSL Code_Aster smoke/reference tests passed without skips; evidence
  is retained at `.build/correctness/real-code-aster.xml`.
- A separate attested loaded-pipe solve verified line, surface and RMED mapping,
  rendered stress and deformed-stress PNGs, and exported Blender/PLY results.
  Removing records from a copy preserved missing-data masks and blocked
  incomplete exports. Its raw artifacts and readback evidence remain under
  `.build/correctness/`.
