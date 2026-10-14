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
        - validate
        - verify
        - add_support
        - define_load_case
        - define_operation
        - import_step
        - import_stl
        - mesh
        - set_mesh_size
        - set_mesh_size_factor
        - add_mesh_refinement
        - remove_mesh_refinement
        - connect_pipe_to_port
        - connect_beam_to_port
        - add_shell_panel
        - add_reference_point
        - add_rigid_patch
        - solve
        - to_dict
        - to_json
        - from_dict
        - from_json

The pipe context returns the current fluent builder.

`model.verify()` is the cold-model gate used by the project solve surfaces.
It combines structural validation, join-aware clashes and rules; check its
`passed`, `errors` and `warnings` fields. `model.validate()` checks structural
invariants only. See [Modeling](../modeling.md#verify-before-solving).

Reusable frames, piping routes and imported fittings belong in parameterized
construction units in `model.py` or `units/`. Apply them with
`assemble(model, "units.frame:build", ...)`; the model records their parameters
and created groups for inspection. Give groups named `attachment_points` so
other units can connect to `lug_left` or `level_1_mid_left` rather than repeat
coordinates. Keep geometry, connection assumptions and operating loads explicit.
Agents edit authored Python and use `inspect_model` and `check_clashes` to verify
it. Generated-script editing tools preserve authored files and cannot rewrite
their unit calls; edit those calls in the source and reload the model.

For a V3-style node connection, use the existing attached support:

```python
model.add_support(
    lug_reference, "custom", attached_to=frame_node,
    blocked_dof=[1, 1, 0, 1, 1, 1],
    attachment_mode="dof_equality", id="lug_left_slide",
)
```

This equates global DX, DY, DRX, DRY and DRZ between the two nodes and leaves DZ
free, using Code_Aster `LIAISON_DDL`. It preserves the V3 equations even when
the nodes are separated. The default `attachment_mode="rigid_offset"` includes
the rotation lever arm. Direct DOF equality at separated points is an explicit
model assumption; it does not have the rigid-motion behaviour of an offset arm.
Both nodes need an actual structural or discrete modelization. A solid lug also
needs its physical face patch tied to the reference node; creating this support
alone does not attach STEP geometry. Use `add_reference_point` and
`add_rigid_patch` for that attachment. See the
[mixed structure authoring contract](https://github.com/jgwagenfeld/Tuba_v4/blob/main/docs/architecture/step-mixed-code-aster.md)
for explicit shell outlines, patch selectors and construction units.

::: tuba.builder.PipingBuilder
    options:
      show_source: false
      members_order: source

## Solver and artifact workflow

The [STEP and mesh guide](../step-meshing.md) gives a complete authoring example,
unit/selection conventions, diagnostic CLI/MCP jobs and Code_Aster convergence.

`model.import_step(path, id="tee", material="Steel", mesh_size="auto", ...)`
imports real CAD and records named engineering interfaces. CAD coordinates and
interface selectors are normalized to millimetres; the default scale converts
them to model metres. Placement uses global metres and a unit quaternion.
`model.mesh("tee.med")` generates quadratic tetrahedra, validates their quality,
connectivity and complete boundary, and records settings in `tee.mesh.json`.
It requires no load case and produces no solver results.

Solid and shell regions select the mixed compiler automatically in model and
project/Studio solving. The native mesh combines quadratic STEP solids,
straight `TUYAU_3M` pipes, `POU_D_T` frame members, planar `DKT` panels and
massless `DIS_TR` reference carriers. Materials and line sections can differ.
Rigid patches, support DOF masks, held prescribed translations, uniform region
temperatures and pipe contents fields retain their authored meaning. Unsupported
contact, buckling, curved shells and temperature-dependent elastic laws fail
explicitly. The supported mixed path solves without a developer opt-in using an
available Code_Aster runtime. Code_Aster 18.0.12 passed eleven reference checks
covering seventeen solves, including STEP response, combined stiffness and
equilibrium, released DOFs, rigid patches, shell refinement and outer-layer
stress, imposed translation, fluid weight and uniform thermal expansion.
Reference-carrier studies use `MULT_FRONT` with `NPREC=8` and
`STOP_SINGULIER='OUI'`, retaining zero-stiffness, massless `DIS_TR` carriers.
This scope covers straight collinear pipe chains, planar DKT panels and scalar
elastic materials; unsupported requests retain their validation errors.
`TUBA_RUN_CODE_ASTER_INTEGRATION=1` selects native reference tests and is not
required by normal `Model.solve()` calls.

`Model.solve()` runs the Code_Aster-backed solve path and returns an `AnalysisRun`. Use the artifact importer when Code_Aster has already produced the study result directory; it returns the same type.

::: tuba.project.mesh.run_project_mesh
    options:
      show_source: false

::: tuba.analysis.mesh_convergence.run_mesh_convergence
    options:
      show_source: false

::: tuba.analysis.mesh_convergence.reopen_mesh_convergence
    options:
      show_source: false

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

## Portable editable projects

Studio, CLI and MCP share the same ZIP/TGZ package implementation. See
[Share and open a project](../project-sharing.md) for user commands and limits.

::: tuba.project.package
    options:
      show_source: false
      members:
        - plan_project_package
        - export_project_package
        - inspect_project_package
        - unpack_project_package

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

Pass a `SceneRequest` containing the model and verified `analysis_runs` to build
one semantic scene, write a portable bundle, and optionally place that scene
alongside an engineering review package. A request with only a model produces a
geometry preview.

::: tuba.visualization.SceneRequest
    options:
      show_source: false
      members_order: source

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
