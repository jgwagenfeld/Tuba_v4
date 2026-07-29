# Visualization architecture

Tuba has exactly two visualization paths. Both can display processed Code_Aster results, but they serve different review needs. Do not add a third path or mix both paths in one example.

## Two supported paths

| Path | Use it for | Result boundary |
| --- | --- | --- |
| `tuba/plotting/` | PyVista quick-look in notebooks, interactive inspection, screenshots, PLY, glTF, and Blender export | `FEAResults.plot_*()` reads real parsed Code_Aster/RMED artifacts |
| `tuba/visualization/` + `viewer/` | A reviewable web scene that can be published, shared, embedded, and paired with engineering-review records | `build_visualization_scene()` creates the semantic contract; `write_scene_bundle()` writes the browser bundle |

A geometry-only scene may be used for model review when it is visibly labelled as having no solver results. Stress, displacement, reaction, compliance, or operating-state claims require imported Code_Aster artifacts.

## Web-scene contract

`VisualizationScene` is the renderer-independent boundary. It carries scene objects, geometry assets, explicit layers, result fields, overlays, issues, review records, diagnostics, and saved view state. The bundle writer serializes the manifest and deterministic geometry payloads; the Three.js viewer renders that contract rather than reconstructing engineering meaning from filenames.

The four layer categories answer what is drawn:

- **Design:** authored pipes, fittings, supports, loads, envelopes, imported components, and context.
- **Analysis mesh:** the nodes, elements, groups, and Code_Aster modelisations handed to the solver.
- **Results:** deformed geometry and solver-returned field or vector geometry.
- **Annotations:** issues, clashes, rules, route candidates, proposals, and review markers.

## Review tasks and evidence

Task mode and evidence destination are independent state. Choosing a task changes the review emphasis and display preset; it does not silently move the evidence dock.

| Task mode | Purpose |
| --- | --- |
| Review | Governing status and overall context |
| Model | Authored geometry and model records |
| Results | Solver-backed fields and result geometry |
| Issues | Diagnostics and issue-focused geometry |

| Evidence destination | Purpose |
| --- | --- |
| Summary | Review status and governing values |
| Diagnostics | Parser, provenance, scene, and issue diagnostics |
| Compliance | Supplied code checks or an explicit unavailable state |
| Reports | Downloadable review artifacts |

These are four independent evidence destinations, not aliases for the four task modes.

## Result and deformation selection

The coloring channel is load case × result field × component. A scalar field exposes only `magnitude`; vector fields expose their available components plus `magnitude`. Selecting a load case keeps the result field and geometry state coherent with that case. Field selection changes coloring and its legend, not layer ownership.

Deformation has two truthful meanings:

- **Physical deformation** is the engineering geometry state at 1× displacement. Its scale is not a display control.
- **Visual deformation** is explicitly display-only and may use an exaggerated scale to make small movement visible.

Only the matching geometry assets render for the active physical or visual deformation state. Untagged reference context remains available for orientation.

## True clipping

The section box performs true clipping with six renderer clipping planes. A pipe crossing the box remains in the scene and only its interior fragment is drawn. The controls do not approximate sectioning by hiding whole objects whose bounds fall outside the box. Camera and section helpers remain visible so the cut can be understood and reset.

[Open the published Code_Aster review viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).
