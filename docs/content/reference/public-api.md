# Public API

These are the stable entry points for the supported workflow. Signatures below are generated from the importable Python objects; the surrounding guidance is maintained here.

## Model authoring

`tuba.Model` is the public alias for `TubaModel`.

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

The reporting builder consumes authoritative model, study, mesh, result, and compliance records. It does not invoke Code_Aster.

::: tuba.reporting.build_engineering_review
    options:
      show_source: false
      members_order: source

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
