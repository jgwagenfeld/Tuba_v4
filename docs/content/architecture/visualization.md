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

### Bodies: the composited result view

Categories answer where content came from. The pinned display strip answers a
different question - which of the overlaid things on screen you are looking at -
and groups the scene into four **bodies**: geometry, analysis mesh, sub-points,
and the deformed shape. The split is not a re-cut of the categories: sub-points
and the deformed shape are both results, but a reviewer dims them separately.

Each body carries visibility and, except the deformed shape, an opacity that
lets the reviewer see the mesh and its sub-points through the authored surface.
Deformed is a transform of the mesh drawn over the undeformed geometry, not a
fourth solid, so it has nothing behind it to see through to. Per-body opacity is
a ceiling rather than a multiplier, so dimming geometry never compounds with the
ghosting an undeformed reference already carries.

Content no category-to-body rule claims - result vectors and every annotation -
stays reachable through the full layer tree. A body the scene does not populate
is omitted rather than shown empty.

### Mesh identity and the discretisation check

`SceneLayer.extra["mesh_identity"]` describes the mesh rather than drawing it:
its modelisations, topological dimension, node and element counts, and the
element families the connectivity actually has (`SEG2`, `SEG3`), which
`MODELISATION` alone cannot state.

When the mesh was built from bends it also carries a **bend-chord discretisation
check** (`tuba/analysis/mesh_quality.py`): how many elements span each arc, and
how far the straight chord falls inside it. That verdict is **geometric, not a
code check** - it is reported against a declared fraction of the bend radius, and
the criterion is displayed next to the verdict so a bare "OK" is never read as a
code acceptance. A mesh with no bends omits the check entirely rather than
reporting a pass it did not earn.

### TUYAU sub-points

`TUYAU_3M` is a 1D mesh whose stress recovery lives at sub-points around and
through the wall. `tuba/analysis/tuyau.py` is the single home for that indexing
convention - `NSEC` circumferential divisions give `2·NSEC+1` angular stations,
`NCOU` layers give `2·NCOU+1` radial stations, and sub-points run angle-fastest.
Both the solver reader, which places the display glyphs, and the scene builder,
which decodes where a peak sits in the wall, read it from there.

The sub-point overlay therefore carries a `section_profile` (the grid on one
element node) and a `peak` decoded into a wall position. Only the two radial
extremes are named - bore and outer surface - because calling a sector
"intrados" would need an orientation the scene does not carry.

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

The channel is owned by one control: the bar above the viewport. The results panel owns thresholds, vector scales, and hotspots, and deliberately does not repeat the case, field, or component selectors - two controls for one selection is how they drift out of sync. The legend and its compliance caveat are pinned in the viewport rather than the results panel, because that panel detaches under the Review, Model, and Issues tasks while the scene stays colour-mapped. The legend ramp is sampled from the same function that tints the scene, so it cannot drift from the pixels it explains.

Deformation has two truthful meanings:

- **Physical deformation** is the engineering geometry state at 1× displacement. Its scale is not a display control.
- **Visual deformation** is explicitly display-only and may use an exaggerated scale to make small movement visible.

Only the matching geometry assets render for the active physical or visual deformation state. Untagged reference context remains available for orientation.

## Display units

The scene stores SI base throughout - metres, pascals, newtons - and the unit
chip in the coloring bar never changes that. It is a presentation layer
(`viewer/src/units.js`): values convert on the way to the screen and back on the
way in from an input, so a threshold typed in MPa reaches state in pascals and
is compared against pascals. Two systems ship today, engineering
(`mm · MPa · kN`) and SI base (`m · Pa · N`), and engineering is the default
because that is how a piping review reads.

One chip governs every readout together - legend, ticks, hotspots, body metrics,
the sub-point peak, the bend-chord deviation - so they cannot disagree with each
other. Two rules keep it honest:

- **Only known units convert.** A unit the table does not recognise passes
  through with its stored label. Rescaling on a guess would invent a reading,
  and a temperature or a ratio has no second one to offer.
- **Raw scene data is shown as stored.** The inspector prints object metadata
  verbatim, where a key like `radius_m` names its own unit. Converting there
  would make the property panel disagree with the bundle it came from.

An absent value renders empty rather than as `0`: `Number(null)` is zero, and a
missing measurement displayed as a measurement of zero is the failure this
layer's `numeric()` guard exists to prevent.

## True clipping

The section box performs true clipping with six renderer clipping planes. A pipe crossing the box remains in the scene and only its interior fragment is drawn. The controls do not approximate sectioning by hiding whole objects whose bounds fall outside the box. Camera and section helpers remain visible so the cut can be understood and reset.

[Open the published Code_Aster review viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).
