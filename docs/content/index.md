# Tuba v4

Tuba v4 defines piping structures, evaluates them with Code_Aster, and displays the processed results for engineering review.

Code_Aster is required for production stress, displacement, reaction, thermal-expansion, operating-state clash, compliance, and result-visualization workflows. Exported study files are only a handoff until Code_Aster has solved the model and Tuba has imported the result artifacts.

Start with [Setup](https://jgwagenfeld.github.io/Tuba_v4/setup.html), then [build and solve the tutorial model](https://jgwagenfeld.github.io/Tuba_v4/tutorial.html). You can also open the [live Code_Aster review viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).

Tuba has two visualization paths:

- `tuba/plotting/` provides PyVista quick-look and export views from real `.rmed` results.
- `tuba/visualization/` and `viewer/` produce reviewable web-scene bundles from real solver artifacts.

Use one path per notebook or example.
