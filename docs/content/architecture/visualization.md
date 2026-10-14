# Visualization architecture

Tuba has exactly two visualization paths. Both display processed Code_Aster
results, with different uses. Choose one path per notebook or example.

## Two supported paths

| Path | Use it for | Result boundary |
| --- | --- | --- |
| `tuba/plotting/` | PyVista notebook inspection, quick-look, screenshots, PLY, glTF and Blender export | `FEAResults.plot_*()` reads parsed Code_Aster/RMED artifacts |
| `tuba/visualization/` + `viewer/` | Shareable browser reviews paired with engineering records | `build_visualization_scene()` creates the scene contract; `write_scene_bundle()` writes the bundle |

A geometry-only scene is labelled as unsolved. Stress, displacement, reaction
and operating-state claims require imported Code_Aster artifacts. FE stress
does not establish piping-code compliance.

## Shared Gallery and Studio workspace

Gallery and local Studio use the same Three.js viewer, with **Build** and
**Review** stages. Studio saves and executes authored `model.py` locally.
Gallery runs geometry previews in browser Python and offers script downloads.
Review retains the published or locally imported Code_Aster evidence;
changed inputs mark dependent results outdated.

The **Profiles** dialog is opened with **Tools & files → Section profiles**.
Its catalogue comes from Python's `SectionCatalog`, exported by
`scripts/build_profile_catalog.py` into packaged `profiles.json`. Browsing
requires no Studio API. In Build, insertion adds a section definition to the
Python editor.

Every scene carries a complete `sections` snapshot, including definitions
with no assigned members. Build uses the latest native run or browser preview;
Review uses its displayed Code_Aster scene. Source links apply only while the
editor matches the snapshot. An external Studio reload closes the dialog so
reopened links use refreshed definitions.

Projects with a bound process network also use the existing viewer's **P&ID**
dialog. **Run hydraulics** evaluates the current graph and route; passing,
current hydraulic evidence gates structural **Solve**. Declared instruments
and signals are drawing/model records, not simulated controls. See
[Process networks](../process-networks.md).

## Web-scene contract

`VisualizationScene` carries objects, geometry assets, layers, fields,
overlays, issues, review records, diagnostics and saved view state. Ordinary
geometry is embedded in the manifest; dense stress glyphs use separate
payloads. Hashes cover geometry in either form, and older bundles with
individual payload files remain readable. The viewer renders this contract
without reconstructing engineering meaning from filenames.

| Layer category | Contains |
| --- | --- |
| Design | Authored pipes, fittings, supports, loads, envelopes and imported context |
| Analysis mesh | Nodes, elements, groups and Code_Aster modelisations |
| Results | Deformed geometry and solver-returned fields or vectors |
| Annotations | Clashes, rules, route candidates, review markers and scene labels |

A volume-meshed element is drawn once, as its mesh skin. Build keeps that
analysis mesh visible because there is no separate procedural design sweep
for the volume. Presets respect `default_visible`; a bundle's hidden layer
is not revived by a preset.

### Bodies and layer visibility

**Display** over the viewport groups geometry, analysis mesh, sub-points and
deformed shape. Sub-points and deformed shape belong to Results. Geometry,
mesh and sub-points have opacity controls; deformed shape transforms the mesh.
Body opacity caps layer opacity rather than multiplying it, preserving the
undeformed reference's transparency.

Supports, loads and vectors have their own controls; **All layers** exposes
individual layers. Empty bodies are omitted.

### Mesh identity and TUYAU sub-points

`SceneLayer.extra["mesh_identity"]` records modelisations, topological
dimension, node/element counts and actual connectivity families such as
`SEG2` and `SEG3`. For bends, `tuba.analysis.mesh_quality` records chord
counts and chord-to-arc deviation against a declared fraction of bend radius.
This is a geometric discretization check.

`TUYAU_3M` uses a 1D mesh with stress recovery around and through the wall.
`tuba.analysis.tuyau` owns the indexing: `NSEC` gives `2·NSEC+1` angular
stations; `NCOU` gives `2·NCOU+1` radial stations; angle runs fastest.
The section overlay carries the grid and a peak decoded into a wall position.
Only bore and outer surface are named; intrados/extrados labels would require
an orientation that this scene record does not carry.

### Scene labels

`add_scene_label(scene, text, position, *, label_id, height=0.18)` creates
world-anchored, camera-facing labels. Height is in metres, width follows text
length, and sprites face the camera during navigation. Labels are in
`annotations:labels`; visibility follows the layer controls. They render over
geometry without depth clipping.

## Review controls and evidence

The left rail contains result and object controls. Visibility, findings and
file actions are in the following places:

| Location | Controls or information |
| --- | --- |
| Colour by | Model property or solver field used to colour the scene |
| Result refinements | Case, component, deformation, filters, legend scale and field details |
| Objects | Search and selection by object, material or route |
| Display, over the viewport | Bodies, supports, loads, vectors, all layers and Cut view |
| Tables & issues, below the viewport | Support reactions, run diagrams, hotspots, issues, Diagnostics & provenance |
| Selection inspector | Definition, source link and available result evidence for the selection |
| Report | Printable engineering tables |
| Status strip | Evidence state, solver identity, analysis information and displayed units |
| Tools & files | Profiles, geometry import, files/export and technical details |
| Help | Workflow guidance and keyboard shortcuts |

The camera controls and orientation gizmo are on the viewport. `B` and `R`
switch Build and Review. Selecting a component can reveal its defining source
call when matching source metadata is available. The [Tutorial](../tutorial.md#review-controls)
provides the user walkthrough.

## Result and deformation selection

The colouring channel is load case × field × component. **Colour by** selects
a model property (role, section, material, group or insulation) or a solver
field. Scalar fields expose magnitude; vector fields expose their components
and magnitude. Selecting a case keeps the field and geometry state coherent.
Field selection changes colours and the legend, while visibility remains with
Display.

The viewport legend and field details retain the result basis and compliance
caveat. Two deformation settings are distinct:

- **Physical deformation** is the engineering state at 1× displacement.
- **Visual deformation** uses an explicitly display-only scale to make small
  movements visible.

Only geometry matching the selected state is drawn. Untagged reference
context remains available for orientation.

## Display units and colour scales

Scene values use SI: metres, pascals and newtons. `viewer/src/units.js`
converts known displayed values and inputs. The unit selector offers
`mm · MPa · kN` (default) and `m · Pa · N`. Unknown units remain as stored;
temperatures and ratios are unchanged.

Legends, ticks, hotspots, reaction/contact readouts, sub-point peaks and
bend-chord deviations follow the selection. Raw metadata remains verbatim:
a key such as `radius_m` retains its stored unit. Missing values stay empty;
they are never coerced to zero.

Colour ranges default to the active field's range. **Filters & vectors**
allows band count and explicit bounds. The band count persists between fields;
bounds do not. Bands use rounded steps and extend the top edge to cover the
range. The scene, swatches and legend use the same ramp; overridden bounds are
labelled as set by the reviewer.

## Result basis and load consistency

Field details state the measured population. Cell FE stress is an element-end
maximum; a sub-point field describes its measured wall points and interpolation.

The viewer's reaction/load consistency disclosure compares imported reactions
with authored nodal loads only, including their moment arms about the origin.
It lists gravity, pressure, line loads and authored fields as excluded.
This limited viewer disclosure is separate from the report's broader
[solver-backed equilibrium checks](../workflow.md#engineering-review-records).
Read each check's coverage before interpreting its residual.

## Findings, envelopes and reference stress

`n` and `N` step through scalar-field findings, worst first, selecting and
framing each location. The shortcuts respect typing and modifier guards.
**Select n findings** turns the current filter into a selection for review
tables.

An envelope field appears when a case publishes multiple result steps. It
spans those steps within that case, records the winning state for each object,
and is labelled as derived arithmetic over solver results. Ties use the
earlier step. It never combines load cases. If only one step carries the
quantity, the field states that no maximum across steps was taken.

Reference stress uses a nearest-rank percentile of the measured TUYAU
sub-point population without interpolating new values. It is available only
for that field. A truncated payload states the available and declared counts.
The percentile supports review and filtering; it is not an adequacy criterion.

## Station diagrams

**Plot this run** in the inspector, or `d`, opens the selected run's diagram
in **Tables & issues**. Stations follow the published centerline, including
bend arcs. Ordinates use the imported element-end section forces, in
Code_Aster's `EFGE_ELNO` component order.

A run needs at least two members. Unsupported geometry is excluded and absent
end forces remain gaps. A component is offered only with coverage at both
ends of the relevant members. Signed value axes include zero.

## Review records

Issues support `open`, `reviewing`, `resolved`, `accepted` and `waived`
dispositions. A waiver requires a nonblank justification. Changes retain the
self-declared reviewer name, timestamp and transition history; the export
identifies attribution as self-declared, without authentication.

An untouched issue is untriaged, not a recorded open disposition. Tallies
distinguish touched issues. CSV exports current dispositions; JSON also carries
transition history. A disposition changes the review record, not the solver
evidence or clash result.

## User reference ratio

The user reference ratio divides an element's FE von Mises stress by the
user-entered material stress schedule. The denominator is published per
element so the ratio can be inspected. See
[ADR 0007](https://github.com/jgwagenfeld/Tuba_v4/blob/main/docs/adr/0007-user-reference-ratio-is-not-a-code-check.md).

A missing schedule, temperature outside its range, spatial temperature field
or volume run leaves the ratio unavailable. Values are not extrapolated or
filled with zero. The field carries its disclaimer into the legend, status
strip and field details. This is a user reference, not a piping-code check.

## True clipping

**Display → Cut view** offers *Off*, *Around selection* and *Custom*, also
reachable through **Cut view around selection** in the right-click menu.
Six renderer planes perform true clipping: a pipe crossing the box shows only
its interior fragment; objects wholly outside it are hidden. Labels and badges
are hidden whole when their anchor is outside. An outline marks the box.

[Open the published Code_Aster review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).
