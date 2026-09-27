# Public API

These are the stable entry points for the supported workflow. Signatures below are generated from the importable Python objects; the surrounding guidance is maintained here.

## Model authoring

`tuba.Model` is the public alias for `TubaModel`.

`model.validate()` checks numerical inputs as well as references. Materials require
finite `E > 0`, `-1 < nu < 0.5`, `rho >= 0`, and finite `alpha`. Zero density is
valid for a massless idealization; zero or negative thermal expansion coefficients
are allowed. Temperatures and reference temperatures must be finite (negative
Celsius values are allowed). Uniform internal pressure must be finite and
nonnegative; this input does not represent external pressure or vacuum.

Pipe dimensions require finite `OD > 0`, `0 < WT < OD/2`, and
`0 <= corrosion_allowance < WT`. Bar wall thickness is nonnegative; the existing
`WT == 0` or `WT >= OD/2` solid-bar convention is preserved. Cable radius must be
positive, pretension nonnegative, and compression modulus ratio in `[0, 1]`.
Rectangular sections have positive heights and either two zero wall thicknesses
(solid) or two positive thicknesses smaller than their respective half-heights
(hollow). I-beam properties must be finite, with positive area, principal inertias,
torsion constant (`A`, `IY`, `IZ`, `JX`), and supplied profile dimensions
(`H`, `B`, `Tw`, `Tf`); signed offsets and higher moments retain catalog conventions.
These scalar inputs reject numeric strings, booleans, NaN, and infinity.
Errors identify the record and property. Validation runs again at study
export/solve, so mutation after construction does not bypass these checks.

::: tuba.model.TubaModel
    options:
      show_source: false
      members_order: source
      members:
        - pipe
        - define_load_case
        - define_operation
        - solve
        - to_dict
        - to_json
        - from_dict
        - from_json

The pipe context returns the current fluent builder.

::: tuba.builder.PipingBuilder
    options:
      show_source: false
      members_order: source

## Solver and artifact workflow

`Model.solve()` runs the Code_Aster-backed solve path and returns an `AnalysisRun`. Use the artifact importer when Code_Aster has already produced the study result directory; it returns the same type.

Rest friction works in single-operation studies on `TUYAU_3M` and `POU_D_T`; only load-path histories, such as `load_path=["Cold", "Hot", "Cold"]` with existing absolute load cases, require `pipe_modelization="POU_D_T"`. `run.result_states` retains every converged increment; `run.result_state` and `run.results` refer to the final state. A stage index and pseudo-time distinguish repeated case names.

Rest supports accept `friction_coefficient`, `gap` in metres, `normal_stiffness` and `tangential_stiffness` in N/m. `direction` is the outward shoe normal (default +Z). The selected `DIS_CHOC` stiffnesses are numerical penalty controls: defaults are 1e10/1e8 N/m, and model-specific sensitivity still matters. Contact records contain forces **on the pipe**, true gap, total relative displacement, native slip and the status source. See the [solved example](../examples/native-friction.md) and [qualification](../engineering/native-friction-qualification.md) for supported scope and the native-status caveats.

::: tuba.analysis.run.AnalysisRun
    options:
      show_source: false
      members_order: source

::: tuba.analysis.code_aster_artifacts.import_code_aster_artifacts
    options:
      show_source: false
      members_order: source

Import validates the study/artifact lineage and returns the study, analysis mesh, persistent `ResultState`, and transient `FEAResults` as one run. Merely producing `.comm`, `.mail`, or `.export` files is not a completed engineering evaluation.

## Reporting

The reporting builder consumes authoritative model, study, mesh, and result records. It does not invoke Code_Aster.

::: tuba.reporting.build_engineering_review
    options:
      show_source: false
      members_order: source

## Operation quantities

`operation.add_field("fluid_density", density_kg_m3, ...)` assigns a full-bore
contents density with the existing pipe selectors. See [fluid contents by
operation](../modeling.md#fluid-contents-by-operation) for validation rules and
solver limitations. Pressure and contents density are independent inputs.

::: tuba.quantities.quantity_takeoff
    options:
      show_source: false

The default is dry metal plus insulation; `operation="Operating"` includes the
named case's contents. Totals expose `pipe_mass_kg`, `insulation_mass_kg`,
`fluid_mass_kg` and `total_mass_kg`. These are model-derived quantities, not
imported solver reactions.

## Autorouting

Autorouting produces candidates for review. Engineering acceptance still requires a real Code_Aster evaluation and the configured acceptance criteria.

::: tuba.routing.AutoroutingAgent
    options:
      show_source: false
      members_order: source

::: tuba.routing.PipeRouteRequest
    options:
      show_source: false
      members_order: source

::: tuba.routing.PipeRouteResult
    options:
      show_source: false
      members_order: source

::: tuba.routing.SolverAcceptanceCriteria
    options:
      show_source: false
      members_order: source

## PyVista quick-look and export

`Model.solve()` and the artifact-import path produce `AnalysisRun`; use `run.results` for the `FEAResults` quick-look helpers. Its `plot_*()` and export helpers are the supported `tuba/plotting/` boundary and operate on real parsed Code_Aster results.

::: tuba.solver.base.FEAResults
    options:
      show_source: false
      members_order: source
      members:
        - plot_deformed
        - plot_stress
        - plot_displacement_vectors
        - plot_reactions
        - plot_temperature
        - plot_deformed_stress
        - export_ply
        - export_gltf

## Reviewable web scene

Build one semantic scene, write a portable bundle, and optionally place that scene alongside an engineering review package.

::: tuba.visualization.build_visualization_scene
    options:
      show_source: false
      members_order: source

::: tuba.visualization.write_scene_bundle
    options:
      show_source: false
      members_order: source

::: tuba.visualization.write_engineering_review_with_scene
    options:
      show_source: false
      members_order: source

::: tuba.visualization.add_scene_label
    options:
      show_source: false
      members_order: source

## User-owned standards checks

Tuba does not implement piping-standard calculations or choose an applicable code.
Use the processed Code_Aster forces, displacements, reactions, and stresses as
inputs to independently verified engineering checks.

For an existing external evaluator, `SolverLoopScorer(compliance_evaluator=...)`
accepts an object with `evaluate(model, results)`. No evaluator runs by default.
If routing acceptance criteria require stress ratios and no evaluator supplies
them, the candidate is rejected with `compliance_unavailable`.

The former `tuba.compliance` evaluators, SIF helpers, detailed formula reports,
and the example option `include_compliance` have been removed.

IFC exports now carry `MaxVonMisesStress_Pa` from the solver results. The former
`MaxStress_Pa`, sustained/expansion ratios, and compliance verdict properties
are no longer generated.
