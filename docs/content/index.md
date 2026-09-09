# Tuba v4

Tuba is an open-source Python library for modeling piping systems, running Code_Aster analyses, and displaying the results.

[![A solved Tuba review showing pipe geometry, the analysis mesh, wall stress, deformation and support reactions together.](assets/figures/code_aster_review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

[Example gallery](https://jgwagenfeld.github.io/Tuba_v4/viewer/): browser views of piping models, analysis meshes, and Code_Aster results. Each entry states whether it contains results or geometry only.

## Start here

- **[Setup](setup.md)** — install Tuba, and the solver when you want to compute your own results.
- **[Tutorial](tutorial.md)** — build a model, run Code_Aster, and display the results.
- **[Examples](examples.md)** — what each published review demonstrates.
- **[Modeling](modeling.md)** — sections, supports, placements, fragments and interop.

## Where results come from

Analysis requires [Code_Aster](https://code-aster.org), installed separately. Modeling, geometric routing, and viewing existing results do not require a local solver installation. Stress, displacement, reaction, and operating-state clearance calculations require Code_Aster result files.

Exporting `.comm`, `.mail`, and `.export` input files does not run an analysis. Results are available after Code_Aster has run and Tuba has imported its output.

## Result visualization

- `tuba/plotting/` gives PyVista quick-look and export views while you work.
- `tuba/visualization/` and `viewer/` produce the shareable web review bundles behind the gallery.

Use one path per notebook or example.
