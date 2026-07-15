# Tuba v4 Notes

Tuba v4 is an open-source Python project around piping models and
Code_Aster-backed result review.

```text
Tuba model -> Code_Aster solve -> imported artifacts -> result review
```

## Current Scope

- model definitions for piping geometry, sections, materials, supports, loads,
  and operating cases
- Code_Aster study handoff and result artifact import
- renderer-independent engineering review packages through `tuba.reporting`
- notebook quick-look views through `tuba/plotting/`
- browser review bundles through `tuba/visualization/` and `viewer/`

## Where To Start

- `notebooks/00_welcome_and_setup.ipynb`
- `notebooks/10_interactive_postprocessor.ipynb`
- `viewer/?bundle=code-aster-review`
- `docs/code_aster_installation.md`

## Result Examples

Examples that display stresses, displacements, reactions, meshes, or deformed
states should use Code_Aster runs or imported Code_Aster artifacts. Exported
`.comm`, `.mail`, and `.export` files are useful for inspection, but they are
only the handoff to the solver.

## Engineering Review Packages

Build the authoritative review from the model plus imported Code_Aster study
and result records, then write it independently of any visualization:

```python
from tuba.reporting import build_engineering_review, write_engineering_review

review = build_engineering_review(
    model,
    studies=[artifact.study],
    result_states=[artifact.result_state],
)
output = write_engineering_review(review, "runs/demo_hot/review")
```

`build_engineering_review(...)` and `write_engineering_review(...)` do not run
Code_Aster. They validate and package records already supplied by the caller.
The FE stress table is labeled `FE Von Mises (not piping-code stress)`.
Piping-code compliance is available only when an explicit compliance report is
supplied; FE stress or scene utilization must not be presented as compliance.

To retain the established web-scene layout in the same output directory:

```python
from tuba.visualization import write_engineering_review_with_scene

output = write_engineering_review_with_scene(
    review,
    "runs/demo_hot/review_scene",
    scene=scene,
)
```

This adapter combines reporting with the existing web-review display path; it
does not create a third visualization path. Existing scene bundles without
`review.json` remain valid. The legacy `write_static_report(scene, ...)` API
also remains callable, but its output is explicitly labeled scene-derived and
states that code compliance is unavailable.
