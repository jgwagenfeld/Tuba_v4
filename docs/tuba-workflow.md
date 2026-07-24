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
`review.json` remain valid.

## Viewer Review Workflow

The Three.js viewer is the interactive consumer of the engineering review
package. It reads the exported `review.json`, CSV tables, scene metadata, and
geometry assets. It performs no engineering calculations in JavaScript.
Code_Aster must solve the study and Tuba must import the result artifacts before
stress, displacement, reaction, or operating-state results can be displayed.

The full review package opens on **Summary** and provides seven workflows:

1. **Summary** — analysis status, provenance, model counts, governing results,
   and warnings.
2. **Model** — nodes, line list, sections, materials, and supports.
3. **Load Cases** — load definitions, linked studies, and solve lineage.
4. **Results** — active load/result state, displacements, reactions, element
   forces, and FE stress. FE stress remains labeled
   `FE Von Mises (not piping-code stress)`.
5. **Compliance** — code and edition, sustained and expansion checks, or an
   explicit unavailable state when no `ComplianceReport` was supplied.
6. **3D** — the reviewable scene, overlays, selection, issue focus, and
   display-only deformation/vector scales. A table row can select its mapped
   scene object without changing the active load case or result state.
7. **Diagnostics** — review, scene, parser, issue, and artifact-provenance
   diagnostics.

Legacy scene-only bundles open on **3D** without treating a missing
`review.json` as an error. `embed=1` also opens the compact 3D surface and hides
the full workflow chrome.

## Visualization Paths

Tuba has two result-display paths:

- `tuba/plotting/` is the PyVista **quick-look and export** path used by
  `FEAResults.plot_*()`. It reads real `.rmed` artifacts and supports notebook,
  PLY, glTF, and Blender output.
- `tuba/visualization/` plus `viewer/` is the Three.js **reviewable web-scene**
  path. Python writes the scene and engineering review package; the browser
  displays those contracts for shareable review.

Reporting packages feed these existing consumers; they are not a third
visualization path. Exported `.comm`, `.mail`, or `.export` files alone are not
a completed engineering evaluation, and neither viewer path makes Code_Aster
optional.
