# Visualization Layer Structure

**Date:** 2026-07-23
**Status:** Approved design, ready for implementation planning

## Problem

The viewer has no explicit structure. Four things that are conceptually distinct
are all flattened into one "layers" list, and the list itself is reconstructed in
JavaScript by guessing at layer-ID string prefixes.

Concretely, as of `6a7324b`:

1. **Design intent is incomplete.** Pipes and supports render. Applied loads do
   not — `LoadCase` and `NodalForce` (`tuba/model.py:340-395`) have no scene
   builder anywhere in `tuba/visualization/builders/`. A load case reaches the
   viewer only as a string on a result overlay's `data.load_case`.
2. **The mesh cannot describe itself.** `AnalysisMesh`
   (`tuba/analysis/mesh.py:100`) carries nodes, elements and groups but no
   element family and no dimension. The `MODELISATION` choice is made at
   `.comm`-write time (`tuba/solver/aster_comm.py:174-199`) and discarded. The
   question "is this a 1D mesh, a 2D mesh, or TUYAU?" is unanswerable from the
   scene contract.
3. **Result toggles are a flat pile.** 35+ overlay `kind` values are sorted into
   six categories by prefix matching (`viewer/src/sceneLoader.js:312-322`).
   Anything unrecognised lands in a generic "Overlays" bin.
4. **Result selection has no axes.** Three loosely coupled dropdowns (load case,
   result state, deformed state) are reconciled by a heuristic
   (`viewer/src/resultReview.js:30-58`), and the scalar field actually drawn is
   picked by a hard-coded priority chain (`resultReview.js:108-115`):
   `tuyau_subpoints ?? stress ?? first-overlay-with-numeric-values`.

## Prior art

The structure being asked for is Salome-Meca's module split, and that split is
load-bearing rather than cosmetic:

- **GEOM** — CAD plus groups. Fields defined here carry *components* and *steps*.
- **SMESH** — the mesh built on the geometry, reported by entity dimension
  (nodes / edges / faces / volumes). `GROUP_MA` / `GROUP_NO` are the anchor that
  boundary conditions attach to.
- **PARAVIS (ParaView)** — the decisive idea: *what is drawn* (pipeline source
  plus representation — surface, wireframe, points, opacity) is orthogonal to
  *what colours it* (array plus component-or-magnitude plus colour map), which is
  orthogonal to *which step*. ParaView deliberately refuses to let one array name
  have two transfer functions, because that misleads readers.
- **MED field model** — a field is (support: node | cell | Gauss point) ×
  (components) × (steps). That triple is the vocabulary that survives thousands
  of results.

For Code_Aster specifically: `TUYAU_3M` is topologically a **1D** mesh (SEG3 /
SEG4) whose stress recovery lives at circumferential sub-points × thickness
layers. It is a 1D mesh with 2.5D result support. Tuba already emits a
`tuyau_subpoints` overlay, but the UI never explains why it exists.

Sources:
- https://docs.salome-platform.org/latest/gui/GEOM/geom_field_page.html
- https://code-aster-windows.com/2018/02/16/beginning-with-post-processing-paravis-module-in-salome-meca/
- https://docs.paraview.org/en/latest/ReferenceManual/colorMapping.html
- https://biba1632.gitlab.io/code-aster-manuals/docs/user/u3.11.01.html
- https://www.kitware.com/salome-an-open-source-simulation-platform-integrating-paraview/

## Shape of the solution

Four **layer categories** (things that are drawn and can be toggled) plus one
**coloring channel** (which is a selector, not a layer). Load case selection
belongs to the coloring channel, not to the layer tree.

### 1. Layers become data

`tuba/visualization/scene.py` gains a first-class entity:

```python
@dataclass(frozen=True)
class SceneLayer:
    id: str                  # "design:supports"
    category: str            # design | analysis_mesh | results | annotations
    label: str
    parent_id: str | None = None
    default_visible: bool = True
```

`VisualizationScene.layers` is emitted by the builders. The viewer consumes it
directly instead of inferring category from the ID prefix. `schema_version` takes
a minor bump.

Category definitions — each is a rule, not a bucket:

| Category | Rule | Members today |
|---|---|---|
| `design` | What the engineer authored | pipes, fittings, supports, applied loads, physical envelopes, imported components, reference context, point clouds, obstacles |
| `analysis_mesh` | What was handed to the solver | mesh nodes, mesh elements, `GROUP_MA` / `GROUP_NO` groups |
| `results` | What the solver returned | deformed shape, deformed mesh, field-coloured geometry, displacement vectors, reaction vectors, TUYAU sub-point field |
| `annotations` | What comments on the model | clash markers, rule markers, rule violations, issues, route candidates, route alternatives, agent proposals, BCF topics, load-path vectors, cost heatmaps, field notes |

### 2. The mesh states its own identity

`MODELISATION` is currently chosen inside `_write_comm`. Both `aster_mesh.py` and
`aster_comm.py` derive the same group names (`AllPipes`, `G_TUBE`, `G_BAR`,
`G_CABLE`, `DIS_<node>`) from the same element-type partition of `TubaModel`, so
the assignment moves to one shared function that both call.

New module `tuba/solver/modelisation.py`:

```python
def modelisation_assignments(model: TubaModel) -> dict[str, str]:
    """GROUP_MA name -> Code_Aster MODELISATION, one source of truth for
    AFFE_MODELE emission and AnalysisMesh metadata."""
```

Pure lookup data lives in `tuba/analysis/mesh.py`, which must not import
`TubaModel`:

```python
MODELISATION_INFO = {           # modelisation -> (topological_dim, result_support)
    "TUYAU_3M": (1, "subpoint"),   # 1D mesh, 2.5D stress recovery
    "POU_D_T":  (1, "cell"),
    "POU_D_E":  (1, "cell"),
    "BARRE":    (1, "cell"),
    "CABLE":    (1, "cell"),
    "DIS_TR":   (0, "node"),
    "DKT":      (2, "cell"),
    "COQUE_3D": (2, "cell"),
    "3D":       (3, "gauss"),
}

@dataclass(frozen=True)
class AnalysisMesh:
    ...
    modelisations: dict[str, str] = field(default_factory=dict)  # group_ma -> modelisation
```

This mirrors `AFFE_MODELE` one-to-one, so a mixed model (TUYAU pipes + POU_D_T
steel + DIS_TR spring supports) describes itself correctly rather than collapsing
to a single label.

`aster_comm.py` reads the shared function instead of re-deriving the assignment.
`aster_mesh.py:434` and `mixed_study.py:266` populate `modelisations` when
constructing the `AnalysisMesh`.

The viewer renders this as a badge on the Analysis mesh group, e.g.
`1D · TUYAU_3M · sub-point recovery`. When a mesh carries more than one
modelisation, the badge lists them by descending element count.

### 3. Load cases and applied loads enter the scene

New builder `tuba/visualization/builders/_loads.py`:

- Each `NodalForce` becomes a `SceneObject(kind="applied_load",
  layer_ids=["design:loads"])` drawn as an arrow glyph, reusing the glyph
  construction already used for reaction vectors in `_results.py`. Every such
  object is tagged with its owning `load_case`.
- Each `LoadCase` becomes an `Overlay(kind="load_case")` carrying `gravity`,
  `internal_pressure`, `temperature` and `ref_temperature`, so the case is
  inspectable in the property panel rather than merely selectable.

Switching load case then switches the *inputs* on screen, not only the outputs.

Moment components on a `NodalForce` render as a distinct double-headed glyph so
they are not mistaken for forces.

### 4. Coloring: one field, one scale

A new scene entity decouples "which fields exist" from "which overlay happens to
hold the values":

```python
@dataclass(frozen=True)
class ResultField:
    id: str
    label: str
    unit: str
    load_case: str
    result_state_id: str
    support: str                      # node | cell | subpoint | gauss
    components: tuple[str, ...]       # ("DX","DY","DZ","magnitude") or ("magnitude",)
    range: tuple[float, float]
    overlay_id: str
    compliance_role: str | None       # e.g. visualization_only_not_asme_code_stress
```

Viewer coloring state collapses to `{loadCase, fieldId, component}`, replacing
`activeLoadCase` / `activeResultStateId` / `activeScalarOverlay` and deleting the
priority chain at `resultReview.js:108-115`. One field yields one legend yields
one colour map, per the ParaView rule.

**Where `components` comes from.** Today `Overlay.data.values` is a flat
`{object_id: scalar}` mapping, so scalar fields (stress, TUYAU sub-point,
temperature, utilisation) declare `components = ("magnitude",)` and the component
selector is disabled for them. Only overlays that already store vectors —
`displacement_vector` and `reaction_vector`, which carry per-node
`[dx, dy, dz]` — declare `("DX", "DY", "DZ", "magnitude")`. No new component data
is synthesised: a field advertises exactly what its overlay holds. Splitting
stress tensors into components is a later change that requires Code_Aster to emit
`SIEF_ELGA` components into the overlay in the first place.

**Axes are case × field × component.** A step/time axis is deliberately excluded:
current Code_Aster runs are static per load case, so a step control would be a
one-entry dropdown. `ResultField` gains a `step` field when transient analysis
lands; that is an additive change.

**Compliance caveat.** The TUYAU sub-point field carries
`visualization_only_not_asme_code_stress`. Explicit field selection makes it
*easier* to mislabel a screenshot, so `compliance_role` renders as a persistent
badge adjacent to the legend — not a tooltip, not a hover, and not suppressible
by any visibility preset.

### 5. Viewer layout

Layer visibility and coloring are separated, matching the ParaView split.

```
Results panel          Load case [Operating v]  Field [SIEQ VMIS (sub-point) v]
                       Component [magnitude v]  0 ════════ 187 MPa
                       ⚠ FE stress — not ASME code stress
                       Hotspots …

Display strip          [x] Design         >   pipes · supports · loads · envelopes
(pinned)               [ ] Analysis mesh  >   1D · TUYAU_3M · sub-point
                       [x] Results        >   deformed ×20 · vectors
                       [x] Annotations    >   clashes · rules · proposals
```

The pinned display strip answers "what is drawn". The Results panel answers "what
does it mean". Task visibility presets (`viewer/src/workflowState.js:30-35`)
remap from their current five keys (`geometry`, `analysis_mesh`, `results`,
`overlays`, `envelopes`) to the four categories.

## Backwards compatibility

Bundles written before this change have no `scene.layers` and no
`scene.result_fields`. The viewer keeps the existing prefix-derivation
(`categoryForLayerId`) as an explicit fallback path, remapped onto the four new
categories:

| Legacy category | New category |
|---|---|
| `geometry` | `design` |
| `envelopes` | `design` |
| `analysis_mesh` | `analysis_mesh` |
| `results` | `results` |
| `overlays` | `annotations` |
| `other` | `annotations` |

Legacy bundles show no applied-load arrows and no mesh badge, because that data
is genuinely absent — the fallback degrades honestly rather than fabricating it.

`AnalysisMesh.modelisations` and the new `SceneLayer` / `ResultField` collections
all default to empty, so deserialising an older payload does not raise.

## Testing

Python:
- `modelisation_assignments` returns the same group→modelisation mapping that
  `_write_comm` emits into `AFFE_MODELE`, for a mixed pipe + beam + bar + spring
  model. This is the regression that keeps the two callers from drifting.
- `AnalysisMesh` round-trips `modelisations` through `to_dict` / `from_dict`, and
  an older dict without the key deserialises to an empty mapping.
- `_loads.py` emits one `applied_load` object per `NodalForce` per load case,
  with correct `load_case` tagging, and one `load_case` overlay per case.
- The emitted `ResultField` catalogue agrees with the overlays it points at:
  every `overlay_id` resolves, and every declared `range` matches the values.

Viewer:
- Categorisation from an explicit `scene.layers` payload.
- Categorisation of a legacy fixture through the fallback table above.
- Coloring reducer keeps `{loadCase, fieldId, component}` coherent across a live
  reload, including when the selected field disappears from the new scene.
- `compliance_role` badge renders whenever the selected field declares one, under
  every task preset.
- One end-to-end test for the split panel: layer groups in the strip, coloring
  controls in the Results panel.

## Out of scope

- Time/step axis for transient results (additive later; see §4).
- Any change to `tuba/plotting/` — the PyVista quick-look path stays as-is, per
  the two-surfaces rule in `AGENTS.md`.
- Per-object colour overrides and custom colour-map editing.
- Reworking the evidence dock, saved views, or the selection/inspector panels.
