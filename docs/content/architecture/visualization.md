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
- **Annotations:** issues, clashes, rules, route candidates, proposals, review markers, and world-anchored text labels.

A volume-meshed element is drawn once. Its mesh skin is the discretisation of
the `VolumeGeometry` the element was meshed from, so the scene carries the skin
alone and no second display sweep that could drift from it. Build therefore
keeps the analysis mesh visible, because a volume review has no procedural
design geometry to fall back on, and drops only the result and annotation
overlays. Every preset, Build included, follows `default_visible`, so a layer a
bundle declared hidden is never revived by a preset.

### Bodies: the composited result view

The display strip groups the scene into four **bodies**: geometry, analysis
mesh, sub-points, and deformed shape. These groups have separate display
controls. Sub-points and deformed shape both belong to the Results category.

Each body has a visibility control. Geometry, analysis mesh, and sub-points
also have opacity controls. Deformed shape applies a transform to the mesh.
Body opacity caps the layer opacity rather than multiplying it, preserving
the transparency of the undeformed reference.

Result vectors and annotations remain accessible through the layer tree.
Empty bodies are omitted from the display strip.

### Mesh identity and the discretisation check

`SceneLayer.extra["mesh_identity"]` describes the mesh rather than drawing it:
its modelisations, topological dimension, node and element counts, and the
element families the connectivity actually has (`SEG2`, `SEG3`), which
`MODELISATION` alone cannot state.

When the mesh was built from bends it also carries a **bend-chord discretisation
check** (`tuba/analysis/mesh_quality.py`): the number of elements per arc and
the deviation of each straight chord from the arc. The criterion is a declared
fraction of the bend radius, displayed beside the result. This is a geometric
check, not a piping-code check. It is omitted for meshes without bends.

### TUYAU sub-points

`TUYAU_3M` is a 1D mesh whose stress recovery lives at sub-points around and
through the wall. `tuba/analysis/tuyau.py` is the single home for that indexing
convention - `NSEC` circumferential divisions give `2·NSEC+1` angular stations,
`NCOU` layers give `2·NCOU+1` radial stations, and sub-points run angle-fastest.
Both the solver reader, which places the display glyphs, and the scene builder,
which decodes where a peak sits in the wall, read it from there.

### 3D scene labels

`add_scene_label(scene, text, position, *, label_id, height=0.18)` adds world-anchored, camera-facing text badges to the scene:

- **Metric height:** The `height` argument defines the badge height in world metres (e.g. `0.18` = 180 mm).
- **Automatic aspect ratio:** Width scales dynamically with text length to preserve character proportions without distortion.
- **Camera billboarding:** Labels render as `THREE.Sprite` instances that face the camera during orbit, pan, and tilt.
- **Layering & occlusion:** Labels render without depth clipping over geometry and belong to the `annotations:labels` layer, toggleable in the viewer's Overlays panel.

The sub-point overlay therefore carries a `section_profile` (the grid on one
element node) and a `peak` decoded into a wall position. Only the two radial
extremes are named - bore and outer surface - because calling a sector
"intrados" would need an orientation the scene does not carry.

## Review rail and evidence

The rail is one scrollable column of sections, not a set of tabs. Nothing swaps, so nothing is hidden to make room: layer visibility is owned by the pinned display strip, the colouring channel by the pinned **Colour by** control, and the issue list sits with the scene so a clash row and a result field are read together.

| Section | Holds |
| --- | --- |
| Colour by | The colouring channel: a model property or a solver field |
| Result refinements | Case, component, deformation, thresholds, vectors and hotspots |
| Bodies / Overlays / All layers | What is drawn |
| Issues | Diagnostics and issue-focused geometry |

The review's tables live in the generated report that the header links to.

## Result and deformation selection

The coloring channel is load case × result field × component. The pinned **Colour by** control chooses which channel tints the scene: a model property (role, section, material, group, insulation) or a solver field. Because it is pinned above the layer list, the choice does not depend on where you are reading. A scalar field exposes only `magnitude`; vector fields expose their available components plus `magnitude`. Selecting a load case keeps the result field and geometry state coherent with that case. Field selection changes coloring and its legend, not layer ownership.

The result refinements control the chosen field: load case, component, thresholds, vector scales and hotspots. The legend and compliance caveat remain visible in the viewport whenever the results channel owns the colours. The legend and scene use the same color function.

There are two deformation settings:

- **Physical deformation** is the engineering geometry state at 1× displacement. Its scale is not a display control.
- **Visual deformation** is explicitly display-only and may use an exaggerated scale to make small movement visible.

Only the matching geometry assets render for the active physical or visual deformation state. Untagged reference context remains available for orientation.

## Display units

The scene stores values in SI base units: metres, pascals, and newtons.
`viewer/src/units.js` converts displayed values and user inputs. For example,
a threshold entered in MPa is stored and compared in pascals. The unit selector
offers engineering units (`mm · MPa · kN`, the default) and SI base units
(`m · Pa · N`).

The selection applies to the legend, ticks, hotspots, body metrics, sub-point
peak, and bend-chord deviation. Conversion follows two rules:

- **Only known units convert.** Unrecognised units retain their stored values
  and labels. Temperatures and ratios are unchanged.
- **Raw scene data is shown as stored.** The inspector prints object metadata
  verbatim, where a key like `radius_m` names its own unit. Converting there
  would make the property panel disagree with the bundle it came from.
- **Derived readouts convert.** The evidence panel's own sections - the
  restraint strip, Definition, Reactions and Contact - are not metadata rows.
  They are computed for the reader, name no stored key, and follow the unit
  chip like every other readout, so a reaction reads `3.989 kN` rather than
  `3988.7852930479976`. The distinction is the presence of a key: a row
  labelled with a scene key is verbatim, a row labelled in words is derived.

The `numeric()` guard displays missing values as empty, preventing JavaScript's
`Number(null)` conversion from displaying them as zero.

## True clipping

The section box performs true clipping with six renderer clipping planes. A pipe crossing the box remains in the scene and only its interior fragment is drawn. The controls do not approximate sectioning by hiding whole objects whose bounds fall outside the box. Camera and section helpers remain visible so the cut can be understood and reset.

[Open the published Code_Aster review viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).
