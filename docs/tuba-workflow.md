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
