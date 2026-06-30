# STEP Mixed-Dimension Code_Aster Design

Status: draft
Date: 2026-06-30

## Purpose

Tuba v4 should be able to import a STEP component, classify the useful
engineering parts of that component, connect those parts to the native Tuba
piping structure, and solve the combined model with Code_Aster.

The first implementation slice is deliberately narrow:

```text
one STEP solid component
  -> one engineer-confirmed connection port
  -> one native Tuba pipe endpoint
  -> one MED-backed mixed Code_Aster study
  -> Code_Aster solve
  -> provenance-safe result import and review
```

This slice establishes the architecture for later 1D-to-2D, 2D-to-3D,
1D-to-3D, and non-conformal mesh couplings without pretending that every STEP
file can be analyzed automatically.

## Product Boundary

Code_Aster remains the production solver boundary.

Exporting a STEP-derived mesh, `.comm`, `.export`, or MED file is not a completed
engineering evaluation. Stress, displacement, reaction, compliance, clash, and
result visualization workflows must use Code_Aster-backed artifacts or fail with
a clear runtime/setup blocker.

The imported STEP file is not itself an engineering model. It becomes part of a
Tuba analysis only after Tuba records explicit:

- analysis regions,
- material assignments,
- mesh groups,
- ports,
- coupling rules,
- solver provenance.

## Current Tuba Baseline

The current repo already has useful pieces, but they target a mostly 1D pipe
workflow.

- `tuba/model.py` keeps `TubaModel` compact: materials, sections, nodes,
  elements, supports, load cases, groups, and obstacles.
- `tuba/geometry/importer.py` imports STEP with Gmsh/OpenCASCADE and converts it
  into a surface `trimesh` for collision/context use. It detects circular
  geometry hints, but it does not create analysis regions or Code_Aster
  couplings.
- `tuba/solver/aster.py` writes ASTER-format 1D studies with pipe, beam, bar,
  cable, and support groups. It already emits `study_tuba_fem.json` sidecar
  provenance and parses Code_Aster artifacts.
- `tuba/analysis/mesh.py` provides `AnalysisMesh`, `MeshNodeSource`, and
  `MeshElementSource`, which are the right pattern for imported/generated mesh
  provenance.
- `tuba/refs.py` and `tuba/schema.py` currently do not have first-class refs or
  schema entries for CAD assets, imported components, ports, analysis regions,
  mesh groups, or couplings.
- `docs/future_ready_architecture.md` already points toward ports,
  relationships, external identities, and traceable Code_Aster studies.

TUBA_V2 contains the closest precedent:

- SALOME-created MED meshes.
- `LIRE_MAILLAGE(FORMAT='MED')`.
- `AFFE_MODELE` using both `TUYAU_3M` and `3D`.
- `AFFE_CHAR_MECA` with `LIAISON_ELEM` and `LIAISON_MAIL`.

The new design should recover that mixed-model capability while preserving v4's
explicit model, sidecar, and result-provenance boundaries.

## External Interface Findings

Code_Aster owns the mixed-dimensional mechanics in `AFFE_CHAR_MECA`.

The relevant coupling families are:

- `LIAISON_ELEM` for explicit dimensional transitions:
  - `OPTION='3D_POU'`: 3D solid to beam.
  - `OPTION='3D_TUYAU'`: 3D solid to pipe.
  - `OPTION='COQ_POU'`: shell edge to beam.
  - `OPTION='COQ_TUYAU'`: shell edge to pipe.
- `LIAISON_MAIL` for projection/tie couplings across non-conformal meshes:
  - `TYPE_RACCORD='MASSIF'`.
  - `TYPE_RACCORD='HULL'`.
  - `TYPE_RACCORD='COQUE_MASSIF'`.
  - `TYPE_RACCORD='MASSIF_COQUE'`.
- `LIAISON_SOLIDE` for rigid node sets, useful for fixtures and rigid hardware
  only when the extra stiffness is intentional.

The normal CAD-to-Code_Aster production workflow is:

```text
STEP/BREP
  -> SALOME-MECA or Gmsh/OpenCASCADE geometry import
  -> topology/mesh groups
  -> MED mesh
  -> LIRE_MAILLAGE(FORMAT='MED')
  -> AFFE_MODELE by group
  -> AFFE_CHAR_MECA couplings and loads
  -> Code_Aster result artifacts
```

SALOME-MECA is the most proven manual workflow. Gmsh/OpenCASCADE is the best fit
for a Python-first Tuba implementation because the repo already depends on
`gmsh`, `meshio`, and `trimesh`.

## Design Decision

Add a mixed-analysis layer beside the native pipe model. Do not replace
`TubaModel.elements` with imported finite elements.

Native Tuba pipe elements remain the source of truth for piping authoring,
routing, sections, supports, load cases, compliance, and reports. Imported STEP
content becomes analysis-side structure with stable references back to the Tuba
model.

The first implementation uses:

- Gmsh/OpenCASCADE for automated STEP import and initial mesh generation.
- MED as the mixed-study mesh handoff format.
- Code_Aster `LIRE_MAILLAGE(FORMAT='MED')` for mixed studies.
- Code_Aster `LIAISON_ELEM` for the first pipe-to-solid port coupling.
- `study_tuba_fem.json` as the canonical sidecar for native refs, solver names,
  imported mesh lineage, and coupling provenance.

SALOME-MECA remains a compatibility/reference path. Tuba should be able to
consume or compare against SALOME-generated MED studies later, but SALOME is not
a required Python dependency for the first slice.

## New Concepts

### CAD Asset

A CAD asset records the imported source file and import settings.

```json
{
  "id": "cad_asset_0",
  "source_path": "equipment.step",
  "source_format": "STEP",
  "unit_scale_to_m": 0.001,
  "placement": {
    "origin": [0.0, 0.0, 0.0],
    "rotation": [1.0, 0.0, 0.0, 0.0]
  },
  "content_digest": "sha256:...",
  "importer": "gmsh-occ"
}
```

### Imported Component

An imported component is the model-level owner for analysis regions and ports.

```json
{
  "id": "component_pump_body",
  "asset": "cad_asset:cad_asset_0",
  "name": "Pump body",
  "role": "equipment",
  "status": "reviewed"
}
```

### Analysis Region

An analysis region maps selected CAD/mesh topology to solver modelization.

```json
{
  "id": "region_pump_solid",
  "owner": "component:component_pump_body",
  "role": "solid_3d",
  "code_aster_modelisation": "3D",
  "material": "Steel",
  "mesh_group": "G_PUMP_SOLID",
  "element_order": 2,
  "status": "reviewed"
}
```

Supported roles for the first architecture:

- `context_only`: collision/visualization only, excluded from solver coupling.
- `solid_3d`: 3D Code_Aster analysis region.
- `shell_2d`: shell analysis region, deferred for the first implementation.
- `line_1d`: imported line/beam/pipe idealization, deferred for the first
  implementation.

### Port

A port is a confirmed connection target. It is not just a detected circle.

```json
{
  "id": "port_pump_nozzle_a",
  "owner": "component:component_pump_body",
  "kind": "circular_face",
  "position": [2.0, 0.0, 0.5],
  "axis": [1.0, 0.0, 0.0],
  "radius": 0.05715,
  "face_group": "G_PORT_NOZZLE_A_FACE",
  "edge_group": "G_PORT_NOZZLE_A_EDGE",
  "status": "confirmed"
}
```

Port status values:

- `detected`: importer found a candidate.
- `confirmed`: engineer or deterministic fixture accepted it.
- `rejected`: candidate is preserved for review history but unused.

Solver export only uses `confirmed` ports.

### Coupling Spec

A coupling spec records the engineering connection intent.

```json
{
  "id": "coupling_pipe_to_pump_a",
  "kind": "pipe_to_solid_port",
  "source": "element:pipe_0",
  "source_node": "node:N1",
  "target": "port:port_pump_nozzle_a",
  "code_aster_keyword": "LIAISON_ELEM",
  "code_aster_option": "3D_TUYAU",
  "status": "reviewed"
}
```

The coupling spec is the only place where Tuba should decide between
`3D_TUYAU`, `3D_POU`, `COQ_TUYAU`, `COQ_POU`, `LIAISON_MAIL`, or
`LIAISON_SOLIDE`.

## EntityRef Extensions

Add these `EntityRef` kinds:

- `cad_asset`
- `component`
- `analysis_region`
- `port`
- `mesh_group`
- `coupling`

These refs allow imported analysis objects to participate in attributes,
diagnostics, visualization scene selection, BCF/export metadata, and solver
sidecars without forcing them into `TubaModel.elements`.

## First Workflow

### 1. Import STEP As Reviewable CAD

Add a new importer separate from the current collision importer:

```text
tuba/geometry/step_analysis_importer.py
```

Responsibilities:

- open STEP through Gmsh/OpenCASCADE;
- apply unit scale and placement;
- enumerate solids, faces, edges, and names when available;
- propose circular-face and circular-edge port candidates;
- produce a `CadAsset`, one or more `ImportedComponent` records, and detected
  `Port` records;
- keep a lightweight visual/collision mesh for review.

The existing `StepGeometryImporter` can remain collision-focused.

### 2. Confirm Analysis Intent

The MVP can use Python calls or deterministic fixtures instead of a UI:

```python
component = model.import_step_component(
    "equipment.step",
    id="component_pump_body",
    role="equipment",
    unit_scale_to_m=0.001,
)

component.region(
    "region_pump_solid",
    role="solid_3d",
    material="Steel",
    mesh_group="G_PUMP_SOLID",
)

component.confirm_port(
    "port_pump_nozzle_a",
    face_group="G_PORT_NOZZLE_A_FACE",
    axis=[1, 0, 0],
    radius=0.05715,
)
```

Automatic candidates are useful, but confirmed solver input must be explicit.

### 3. Connect Native Pipe To Port

Use a structured connection call:

```python
model.connect_pipe_to_port(
    pipe="element:pipe_0",
    node="node:N1",
    port="port:port_pump_nozzle_a",
    method="3D_TUYAU",
)
```

The method should validate:

- source element exists and is a pipe;
- source node is one endpoint of that element;
- target port exists and is confirmed;
- target port belongs to a `solid_3d` region for `3D_TUYAU`;
- pipe section diameter and port radius are compatible within tolerance;
- pipe tangent and port axis are aligned within tolerance;
- required mesh groups exist before solver export.

### 4. Generate MED Mixed Mesh

Add a mixed-study exporter beside the existing ASTER-format writer:

```text
tuba/solver/mixed_study.py
```

Responsibilities:

- build native 1D pipe/beam elements and imported 3D mesh into one mesh model;
- preserve physical groups for native pipes, imported solids, ports, and
  coupling faces;
- write MED through `meshio` or Gmsh depending on which preserves group names
  correctly for the case;
- emit a sidecar mapping every solver group to stable `EntityRef` values.

For the first `3D_TUYAU` slice, the 3D side should use second-order tetrahedral
elements unless a Code_Aster validation case proves a lower-order mesh is valid
for the selected option. If the mesher cannot provide a valid element order, the
export fails before Code_Aster execution.

### 5. Generate Code_Aster Commands

The mixed `.comm` path reads MED instead of ASTER mesh:

```python
MAIL0 = LIRE_MAILLAGE(FORMAT='MED', UNITE=20)
```

Then it assigns modelizations by group:

```python
MODELE = AFFE_MODELE(
    MAILLAGE=MAIL0,
    AFFE=(
        _F(GROUP_MA=('G_TUBE',), PHENOMENE='MECANIQUE', MODELISATION='TUYAU_3M'),
        _F(GROUP_MA=('G_PUMP_SOLID',), PHENOMENE='MECANIQUE', MODELISATION='3D'),
    ),
)
```

Then it applies the coupling:

```python
CHAR = AFFE_CHAR_MECA(
    MODELE=MODELE,
    LIAISON_ELEM=(
        _F(
            OPTION='3D_TUYAU',
            GROUP_MA_1='G_PORT_NOZZLE_A_FACE',
            GROUP_NO_2='N_PIPE_PORT_A',
        ),
    ),
)
```

The exact group/node arguments must be generated from the validated coupling
spec and checked against the active Code_Aster manual/test case before
implementation. The design requires command generation to be structured, not
string-spliced from user input.

### 6. Run Code_Aster Or Fail Loudly

The existing runtime boundary should be reused:

- `CodeAsterSolver.export_analysis_study(...)` style API for deterministic
  handoff;
- `solve_exported_study(...)` for real execution;
- `import_code_aster_artifacts(...)` for parser-backed review.

If Code_Aster is unavailable, the mixed workflow may export a study for
inspection, but it must not display or report solver results.

### 7. Import Results With Provenance

The sidecar should extend the existing provenance shape:

```json
{
  "cad_assets": {...},
  "components": {...},
  "analysis_regions": {...},
  "ports": {...},
  "couplings": {...},
  "mesh_groups": {
    "G_PUMP_SOLID": ["analysis_region:region_pump_solid"],
    "G_PORT_NOZZLE_A_FACE": ["port:port_pump_nozzle_a"],
    "G_TUBE": ["group:G_TUBE"]
  }
}
```

Imported 3D mesh nodes/elements should map to `analysis_region` or `port` refs
at minimum. Native 1D mesh nodes/elements keep their existing node/element refs.

Visualization can then distinguish:

- native pipe results;
- imported component results;
- port/coupling diagnostics;
- solver mesh groups with missing provenance.

## Coupling Selection Rules

Initial mapping:

| Source | Target | Default Code_Aster coupling |
| --- | --- | --- |
| Tuba pipe endpoint | 3D solid port face | `LIAISON_ELEM OPTION='3D_TUYAU'` |
| Tuba beam endpoint | 3D solid face | `LIAISON_ELEM OPTION='3D_POU'` |
| Tuba pipe endpoint | shell edge | `LIAISON_ELEM OPTION='COQ_TUYAU'` |
| Tuba beam endpoint | shell edge | `LIAISON_ELEM OPTION='COQ_POU'` |
| non-conformal solid face | solid face | `LIAISON_MAIL TYPE_RACCORD='MASSIF'` |
| shell face/edge | solid face | `LIAISON_MAIL TYPE_RACCORD='COQUE_MASSIF'` or `MASSIF_COQUE` |
| rigid support hardware | selected nodes | `LIAISON_SOLIDE` only when intentionally rigid |

`3D_POU_ARLEQUIN` and broader Arlequin methods are deferred. They are useful for
overlap transitions and stiffness smoothing, but they add validation and
modeling complexity that is not needed for the first port connection.

## Validation Rules

Mixed-study export must fail before writing a solver study when:

- a STEP asset is missing or has an unsupported unit/placement transform;
- a candidate port is not confirmed;
- a confirmed port has no face or edge group;
- a solver region has no material;
- a region role does not map to a supported Code_Aster modelization;
- a coupling references missing refs;
- a pipe-to-solid coupling targets a non-solid region;
- a pipe axis and port axis differ beyond the configured tolerance;
- a pipe outside diameter and port diameter differ beyond tolerance;
- a required MED group name is missing or too long for the chosen writer;
- Gmsh/MED export drops a physical group;
- the selected coupling requires element order or topology that the mesh does
  not satisfy;
- result import, display, or engineering-result claims are requested while
  Code_Aster runtime or solved artifacts are unavailable.

Warnings should be emitted, not hidden, when:

- automatic port detection found multiple plausible faces;
- the imported STEP has unnamed topology;
- a coupling uses `LIAISON_SOLIDE`;
- a mesh size is inferred from geometry instead of explicitly set;
- imported result artifacts have solver data but incomplete sidecar provenance.

## Testing Strategy

### Portable Unit Tests

These do not require Code_Aster:

- STEP import fixture creates stable `CadAsset`, `ImportedComponent`, and
  detected `Port` records.
- Confirmation of a port changes status from `detected` to `confirmed`.
- Invalid couplings fail validation with specific diagnostics.
- Mixed study export writes a `.comm` containing `LIRE_MAILLAGE(FORMAT='MED')`,
  `AFFE_MODELE`, and the expected coupling keyword.
- Sidecar records `EntityRef` lineage for native pipe groups, imported regions,
  ports, and couplings.
- Export-only examples are labeled as incomplete for engineering evaluation.

### Optional Gmsh/MED Tests

These run when Gmsh/MED support is available:

- generated MED preserves physical group names for the pipe group, solid group,
  and port face group;
- `meshio` can re-read the generated MED mesh and expose the expected cells and
  groups;
- failed group preservation blocks export.

### Code_Aster Integration Tests

These run only when a real Code_Aster runtime is configured:

- solve a minimal pipe-to-solid fixture;
- import `DEPL`, `REAC`, `EFFO`, stress tables, and optional RMED;
- verify no result is displayed unless it came from the real Code_Aster run;
- compare the first slice against a small committed reference or a generated
  TUBA_V2-style MED/command fixture.

## Implementation Milestones

### Milestone 1: Data Containers And Refs

Files:

- `tuba/refs.py`
- `tuba/model.py`
- `tuba/schema.py`
- `tuba/analysis/mesh.py`
- tests for serialization and ref resolution

Add CAD asset, component, analysis region, port, mesh group, and coupling data
records. Keep them optional so existing models load unchanged.

Acceptance:

- existing tests continue to load old models;
- new records roundtrip through `to_dict` and `from_dict`;
- `EntityRef` resolves the new kinds.

### Milestone 2: STEP Analysis Importer

Files:

- new `tuba/geometry/step_analysis_importer.py`
- existing `tuba/geometry/importer.py` only if shared helpers are needed
- tests with a tiny STEP fixture or generated OCC geometry

Add analysis-oriented STEP import while preserving the current collision
importer.

Acceptance:

- importer can create reviewable component records;
- detected ports are not solver-active until confirmed;
- missing Gmsh fails with a clear optional dependency message.

### Milestone 3: Coupling Validation API

Files:

- `tuba/model.py`
- `tuba/validation.py`
- tests for invalid and valid coupling specs

Add `connect_pipe_to_port(...)` or equivalent low-level model API.

Acceptance:

- invalid refs, geometry mismatches, and unconfirmed ports fail before export;
- valid coupling produces a structured `CouplingSpec`.

### Milestone 4: MED Mixed Study Export

Files:

- new `tuba/solver/mixed_study.py`
- `tuba/solver/aster_sidecar.py`
- tests that inspect generated files

Generate MED and sidecar for the native pipe plus imported solid region.

Acceptance:

- MED contains native 1D and imported 3D groups;
- sidecar maps all solver-visible groups to refs;
- group name normalization is deterministic.

### Milestone 5: Mixed Code_Aster Command Writer

Files:

- `tuba/solver/mixed_study.py`
- `tuba/solver/aster.py` only for shared runtime integration
- command-file tests

Generate `.comm` for `LIRE_MAILLAGE(FORMAT='MED')`, mixed `AFFE_MODELE`, and the
first `LIAISON_ELEM OPTION='3D_TUYAU'` coupling.

Acceptance:

- pure 1D export path remains unchanged;
- mixed path emits the expected MED reader and modelization blocks;
- unsupported couplings fail with a precise diagnostic.

### Milestone 6: Real Code_Aster Integration

Files:

- runtime tests under `tests/integration/`
- artifact parser updates only if needed

Run the first mixed fixture with Code_Aster when configured.

Acceptance:

- real Code_Aster execution succeeds for the fixture;
- result import includes provenance for native and imported regions;
- no notebook/viewer path displays fabricated values.

### Milestone 7: Review And Visualization Surface

Files:

- `tuba/visualization/builders.py`
- optional viewer scene updates
- tests for scene object refs and diagnostics

Expose imported component, port, and coupling diagnostics in the scene model.

Acceptance:

- users can see which imported face/port is connected;
- missing provenance is visible as a diagnostic;
- stress/displacement display still requires Code_Aster-backed artifacts.

## Non-Goals For The First Slice

- automatic engineering interpretation of arbitrary STEP files;
- shell midsurface extraction;
- imported 1D centerline extraction;
- Arlequin coupling;
- nonlinear contact;
- pressure/nozzle flexibility code checks;
- generic FEM backend replacement;
- mandatory SALOME dependency;
- adapy as a required dependency;
- UI-based port review.

## Default Tolerances

Initial validation defaults:

- pipe axis to port axis angular tolerance: 5 degrees;
- pipe outer radius to port radius tolerance: 2 percent or 1 mm, whichever is
  larger;
- port face centroid to pipe endpoint tolerance: 5 mm after placement transform;
- MED group-name maximum: use the stricter active writer/Code_Aster limit and
  record original-to-solver names in the sidecar.

These defaults are conservative starting points and should be configurable per
project or per coupling once real fixtures reveal better domain limits.

## References

- Code_Aster `AFFE_CHAR_MECA` manual, `LIAISON_ELEM`, `LIAISON_MAIL`,
  `LIAISON_SOLIDE`: https://code-aster.org/doc/default/en/man_u/u4/u4.44.01.pdf
- Code_Aster `AFFE_MODELE` manual: https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.41.01.html
- Code_Aster `LIRE_MAILLAGE` manual: https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.21.01.html
- Gmsh/OpenCASCADE and physical groups: https://gmsh.info/doc/texinfo/
- SALOME GEOM import/export: https://docs.salome-platform.org/latest/gui/GEOM/import_export_geom_obj_page.html
- SALOME SMESH import/export and MED: https://docs.salome-platform.org/latest/gui/SMESH/importing_exporting_meshes.html
- Existing v4 architecture: `docs/future_ready_architecture.md`
- Existing adapy boundary: `docs/architecture/adapy-alignment.md`
- Implementation architecture summary: `docs/architecture/step-mixed-code-aster.md`
- TUBA_V2 mixed reference:
  `TUBA_V2/tutorials/000_Testing/x_008_TUYAU_3d/008_TUYAU_3D_K_M_F_aster.comm`
