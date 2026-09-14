# Tuba v4 Agent Instructions

## Core Product Contract

Tuba v4 is a Code_Aster-backed piping engineering workflow:

The whole point of Tuba v4 is to define piping structure, evaluate it with Code_Aster, and display processed results.

1. Define the piping structure in Tuba.
2. Evaluate the model with Code_Aster.
3. Display, review, and report the processed Code_Aster results.

Code_Aster is not optional for production stress, displacement,
reaction, thermal-expansion, operating-state clash, compliance, or result
visualization workflows. Export-only paths are development and diagnostic
surfaces only.

## Code_Aster Rules

- Do not present fabricated, mock, hand-built, or proxy values as solver
  results.
- Do not treat `.comm`, `.mail`, or `.export` generation as a completed Tuba
  evaluation workflow.
- If Code_Aster is unavailable, fail loudly with the runtime/setup blocker and
  stop before displaying or reporting solver results.
- Unit tests may use export-only studies or deterministic fixtures so CI stays
  portable, but integration/developer validation must run the real Code_Aster
  backend.
- Prefer a Python-managed Code_Aster runtime/bridge when implementing execution
  paths. Shell runners, Docker, and legacy `as_run` should be fallbacks, not the
  product definition.
- Solver integration must remain native Tuba code with external-process
  Code_Aster execution.

## Documentation Rules

- README, notebooks, examples, and architecture docs must preserve the core
  workflow: Tuba model -> Code_Aster solve -> processed result display.
- Any export-only example must be labeled as incomplete for engineering
  evaluation until the exported study has been solved by Code_Aster and result
  artifacts have been imported.
- Any UI or notebook that displays stress, displacement, reaction, compliance,
  or operating-state results must use Code_Aster-backed artifacts or stop with a
  clear runtime requirement.

## Visualization Surfaces

There are two result-display paths. Keep them distinct; do not add a third.

- `tuba/plotting/` (PyVista) is the **quick-look & export** path. It is wired
  to `FEAResults.plot_*()` (see `tuba/solver/base.py`) and reads real `.rmed`
  artifacts; use it for interactive/notebook views and PLY/glTF/Blender export.
- `tuba/visualization/` + `viewer/` is the **reviewable web-scene** path.
  `build_visualization_scene` / `write_scene_bundle` emit a JSON scene contract
  that the `viewer/` Three.js app renders. Use it for shareable review bundles.

Prefer one path per notebook/example rather than mixing both.
