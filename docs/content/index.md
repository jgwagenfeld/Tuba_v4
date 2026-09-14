# Tuba v4

Tuba is an open-source Python library for modeling piping systems, running Code_Aster analyses, and displaying the results.

[![A solved Tuba review showing pipe geometry, the analysis mesh, wall stress, deformation and support reactions together.](assets/figures/code_aster_review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

## Gallery

Every review opens in your browser, no install needed. All except *Imported components* show imported Code_Aster results. [Browse the full gallery](https://jgwagenfeld.github.io/Tuba_v4/viewer/), or read what each one demonstrates on [Examples](examples.md).

<div class="grid cards" markdown>

-   [![Thermal expansion review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop)

    **Thermal expansion** — Where does a hot line move, and what does it reach?

-   [![Load transfer review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review)

    **Load transfer** — What do the supports and the steel underneath actually carry?

-   [![Beam orientation review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review)

    **Beam orientation** — How do section orientation and local axes change bending?

-   [![Pipe bends review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

    **Pipe bends** — What happens to a pressurised line held at both ends?

-   [![Cable review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/guyed-mast-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review)

    **Cable** — Which guys hold a mast in the wind, and which one goes slack?

-   [![Nonlinear friction review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review)

    **Nonlinear friction** — How does friction change the same pipe and load path?

-   [![3D solid review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review)

    **3D solid** — Does stress concentrate where the branch meets the header?

-   [![Elements and supports review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/elements-supports-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=elements-supports-review)

    **Elements and supports** — Do bars, cables and spring supports survive the trip to the solver?

-   [![Imported components model review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/imported_component_mixed_demo.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo)

    **Imported components** — How does a supplied component join an authored line?

</div>

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
