# Native Section Geometry and Pipe Volume Meshing Design

**Date:** 2026-08-27

**Status:** Approved for implementation

**Scope:** Profile-aware structural examples, native straight-pipe, isolated-bend, and tee solid meshing, Code_Aster volume-study preparation, and review geometry

## Decision Summary

Tuba will use the existing Gmsh Python dependency and its OpenCASCADE kernel to
generate native pipe and tee geometry. SALOME-Meca will not become a required
installation.

The implementation will port the useful behavior of Tuba v2 rather than copy
its generated Python 2 scripts:

- create hollow straight-pipe and tee solids;
- create stable volume, inner-wall, outer-wall, and end-face groups;
- write a MED mesh suitable for Code_Aster `MODELISATION='3D'`;
- derive review geometry from the same generated topology; and
- retain traceability from mesh entities to Tuba elements and tee junctions.

The normal Tuba solve remains `TUYAU_3M`. Solid 3D is an explicit engineer
choice and is not silently enabled for every pipe. A generated mesh is an
analysis input, not a solver result. Stress, displacement, reaction, or
compliance views remain unavailable until a real Code_Aster run has produced
and Tuba has imported the corresponding artifacts.

## Why Gmsh, Not a Required SALOME-Meca Installation

Tuba v2 implemented `TShape3D` by generating a SALOME script. The script called
`geompy.MakePipeTShape`, selected faces, created quadrilateral and hexahedral
hypotheses, and exported named mesh groups. Its Code_Aster writer then assigned
`MODELISATION='3D'` and connected the three terminal faces to line elements
through `LIAISON_ELEM(OPTION='3D_POU')`.

That implementation proves the intended workflow, but it is not an appropriate
runtime boundary for v4:

- it requires a separate SALOME-Meca installation and compatible embedded
  Python runtime;
- it generates a script that must run inside SALOME rather than using Tuba's
  normal Python process;
- it identifies inner and outer faces through hard-coded OpenCASCADE face
  indices, which are sensitive to geometry-kernel changes; and
- it duplicates geometry, mesh, and solver orchestration already present in
  v4.

Gmsh is already a core dependency in `pyproject.toml`. V4 already uses its OCC
kernel for bend geometry, STEP import, three-dimensional mesh generation, MED
output, and physical groups. The native implementation can therefore run under
the supported Python environment and on the existing CI and self-hosted
Code_Aster runner.

The first production mesh will use second-order tetrahedra. It will not claim
structured-hexahedral parity with the old SALOME mesh. A SALOME adapter should
be considered only if a documented engineering case requires structured
hexahedra or boundary-layer control and the Gmsh mesh fails the defined quality
or reference-validation gates. No generic mesher interface will be added before
a second backend is actually required.

Primary references:

- [Tuba v2 `TShape3D` API](https://tuba-v2.readthedocs.io/en/new_dev/Commands.html#tuba.define_geometry.TShape3D)
- [Tuba v2 SALOME tee generator](https://github.com/jgwagenfeld/TUBA_V2/blob/SM2019/tuba/write_Salome_file.py#L783-L884)
- [Tuba v2 Code_Aster 3D tee coupling](https://github.com/jgwagenfeld/TUBA_V2/blob/SM2019/tuba/write_Aster_file.py#L1242-L1276)
- [Gmsh Python/OpenCASCADE API](https://gmsh.info/doc/texinfo/gmsh.html#Gmsh-application-programming-interface)

## Product Requirements

### Structural cross-sections

The solved support-rack example will use visibly different structural sections:

- IPE sections for columns;
- rectangular hollow sections for longitudinal members;
- a second rectangular or IPE size for transverse members; and
- circular pipe sections for the supported process pipe.

The web-review scene will render the actual I, rectangular hollow, and circular
profiles. Non-pipe beams will no longer be displayed as identical lines when
their model sections are different. The section schedule and selected-object
metadata will retain the section name, kind, and dimensions.

### Native pipe solids

The native volume mesher will accept a connected selection of
`pipe_straight` elements and explicit `model.tees` junctions. The first
supported slice is:

- straight hollow pipes;
- one isolated circular bend with an explicit `BendGeometry` record;
- equal and reducing three-way tees whose header and branch sections are
  circular `PipeSection` records;
- one material per connected solid region; and
- open terminal faces at the selected run boundaries.

Connected straight-bend-tee selections, reducers other than a tee branch,
flanges, valves, shells, contacts, and reinforcement-pad geometry fail before
geometry generation until their own validated slices exist. `pad_thickness`
remains compliance metadata; it does not fabricate a reinforcing-pad solid.

### Solver and result semantics

The generated MED file must contain the groups needed by Code_Aster:

| Group | Dimension | Purpose |
|---|---:|---|
| `G_SOLID_<region>` | 3 | `AFFE_MODELE` and material assignment |
| `G_INNER_<region>` | 2 | Internal pressure application |
| `G_OUTER_<region>` | 2 | Inspection and future external loads |
| `G_END_<node>` | 2 | Boundary conditions or 1D/3D coupling |
| `G_TEE_<node>` | 3 | Tee provenance and result selection |

Names pass through the existing Code_Aster name mapper. Raw OCC entity tags are
never part of the public contract.

The first volume solve uses Code_Aster `MODELISATION='3D'`, assigns the model's
material, applies pressure to `G_INNER_*`, applies endpoint conditions to
`G_END_*`, runs the real solver, writes `.rmed`, and imports the result through
the existing `AnalysisRun`/`ResultState` path. FE equivalent stress remains an
FE result and does not become piping-code stress or B31.3 compliance.

## Architecture

```text
TubaModel
  |-- sections ----------------------> section profile mesh
  |                                      |-- PyVista quick-look
  |                                      `-- Three.js review mesh
  |
  `-- selected pipes + explicit tees -> pipe topology classification
                                         |
                                         v
                                    Gmsh OCC solids
                                         |
                          +--------------+--------------+
                          |                             |
                    surface skin                    MED volume mesh
                          |                             |
                  existing web scene             Code_Aster 3D solve
                                                        |
                                                 AnalysisRun/ResultState
                                                        |
                                             existing review/quick-look paths
```

No third visualization path is introduced. `tuba/plotting/` remains the local
quick-look/export path, and `tuba/visualization/` plus `viewer/` remains the
shareable review path.

## Module Boundaries

### `tuba/geometry/junctions.py`

Owns neutral pipe-junction classification. It identifies the header pair and
branch at a three-way node from element directions and returns explicit source
element references. The current equivalent logic in `tuba/compliance/sif.py`
will use this shared helper so meshing and compliance cannot disagree about tee
topology.

It rejects:

- fewer or more than three connected pipe elements;
- zero-length directions;
- ambiguous header selection;
- non-circular sections; and
- tee records whose node is not the selected junction.

### `tuba/geometry/section_mesh.py`

Owns dependency-light section polygons and straight-element surface extrusion.
The existing pipe, bar, cable, rectangular, hollow-rectangular, and I-section
logic moves out of `tuba/plotting/pipeline.py` into this module. It returns plain
vertices and triangular faces. PyVista and the web-scene builder adapt that one
geometry record to their existing formats.

This module does not generate a Code_Aster volume mesh.

### `tuba/meshing/pipe_volume.py`

Owns the Gmsh OCC construction and MED export for native pipe solids. Its public
entry point is deliberately small:

```python
from tuba.meshing import build_pipe_volume_mesh

generated = build_pipe_volume_mesh(
    model,
    output_path="study.med",
    element_ids=["header_left", "header_right", "branch"],
    max_element_size=0.025,
    element_order=2,
)
```

`max_element_size` is required because wall thickness, diameter, and local tee
geometry determine a meaningful mesh scale. `element_order` initially accepts
only `2`; lower-order tetrahedra are not a production stress default. The
return value contains the `AnalysisMesh`, group inventory, surface-skin
vertices/faces, Gmsh version, mesh settings, and MED path.

The module owns and releases Gmsh only when it initialized the process, matching
the existing import/export lifecycle. It does not hide Gmsh behind a backend
factory.

### `tuba/solver/aster_volume.py`

Compiles the generated native volume mesh into the existing Code_Aster study
and result pipeline. `CodeAsterSolver` remains the public solver. The new module
contains only the volume-specific command blocks and is called from the solver
when the engineer explicitly chooses solid 3D modelization.

`tuba/solver/modelisation.py` will expose a typed `PipeModelization` choice;
raw arbitrary modelization strings remain internal. Solid 3D is not exposed
through `model.solve()` until the straight-pipe reference case passes. Once
enabled, the intended public call is:

```python
from tuba.solver.modelisation import PipeModelization

run = model.solve(
    operation="Operating",
    pipe_modelization=PipeModelization.SOLID_3D,
    volume_element_ids=["header_left", "header_right", "branch"],
    max_element_size=0.025,
)
```

The existing call without `pipe_modelization` continues to select
`PipeModelization.TUYAU_3M`. Unknown or partially supported solid selections
fail before export.

### Existing visualization modules

`tuba/visualization/builders/_objects.py` will emit `format="mesh"` assets for
profile-aware structural members and generated pipe-solid skins. The viewer
already renders indexed mesh assets, so no new renderer or scene contract is
needed.

The normal lightweight pipe view may continue using procedural tubes. When a
native volume analysis mesh is supplied, its surface skin is authoritative for
the analysis-mesh layer and the tube remains design geometry.

### Structural assembly and example

`RackBay` will accept optional `column_section`, `longitudinal_section`, and
`transverse_section` names, each defaulting to the existing `section` value.
This preserves the current simple API while allowing the official support-rack
example to demonstrate real section variation without rewriting the assembly
by hand.

The committed support-rack Code_Aster artifacts must be refreshed after its
section assignments change. Until that real refresh completes, the existing
solved gallery remains authoritative and no regenerated scene may claim the old
results belong to the changed model.

## Geometry and Grouping Algorithm

### Straight pipe

For each selected straight element:

1. Create an outer OCC cylinder from its start point and direction.
2. Create a coaxial inner cylinder from `PipeSection.ID`.
3. Cut the inner cylinder from the outer cylinder.
4. Retain source-element lineage on the resulting volume.

Adjacent collinear elements with compatible sections may be fused inside one
selected solid region. Different sections remain separate until a reducer
implementation exists.

### Tee

For an explicit tee node:

1. Use the shared junction classifier to select the two most opposite element
   directions as the header and the remaining direction as the branch.
2. Create outer cylinders extending from the junction into all three selected
   elements.
3. Fuse the outer cylinders.
4. Create and fuse the corresponding inner-bore cylinders.
5. Cut the fused inner bore from the fused outer body.
6. Fragment/fuse the tee body with adjacent selected straight-pipe bodies so
   the final region is conformal.

This reproduces the physical intent of v2's `MakePipeTShape` without depending
on SALOME's specialized constructor.

### Isolated bend

For one selected `pipe_bend`, create an annular cross-section at the recorded
start point and revolve it around `BendGeometry.center` and
`BendGeometry.normal` through the recorded angle. The start tangent orients the
cross-section. The generated torus segment must end at the element's second
node; its bore, outer wall, and two terminal annuli use the same stable groups
as a straight pipe. Connected mixed selections remain a later conformal-boolean
slice.

### Surface classification

Surface groups are derived from geometry, not face order:

- terminal planes identify `G_END_<node>`;
- cylindrical radius and adjacency to the inner bore identify `G_INNER_*`;
- remaining external cylindrical surfaces identify `G_OUTER_*`; and
- volume ancestry identifies `G_TEE_<node>` and source-element lineage.

Generation fails unless every open terminal has exactly one end-face group,
the inner and outer groups are non-empty and disjoint, and every volume belongs
to one solid group.

## Mesh Generation and Quality Gates

The first mesh is quadratic tetrahedral:

- three-dimensional Gmsh mesh generation;
- element order 2;
- maximum element size supplied by the engineer;
- curvature refinement enabled around the bore and tee crotch; and
- at least two elements through the thinnest selected wall as a preflight
  requirement.

The mesher records node and element lineage in `AnalysisMesh`, plus the Gmsh
version and mesh settings in study metadata. It rejects:

- empty physical groups;
- non-finite coordinates;
- inverted or zero-volume cells;
- a disconnected solid region;
- missing end, inner, or outer surfaces; and
- a requested mesh size too coarse for the selected wall thickness.

The exact quality threshold beyond positive cell orientation will be set from
the reference meshes rather than copied from the old SALOME defaults.

## Pressure Profiles

Linear pressure by route/station remains the next small solver slice. It should
land before the 3D volume solve so both `TUYAU_3M` and solid studies resolve the
same authored pressure at each selected element.

For the solid study, resolved element pressures are compiled to the
corresponding `G_INNER_*` surfaces. A pressure discontinuity is allowed only at
a retained region boundary; it is not averaged across a fused surface without
an explicit rule. Applied pressure is displayed as an input overlay, never as a
solver result.

Piecewise pressure remains unsupported because the current `OperationField`
does not contain knot values. It will not be invented as part of meshing.

## Failure Behavior

- Missing Gmsh is a setup error before geometry generation.
- Missing Code_Aster allows mesh inspection but blocks result display.
- Unsupported fittings or ambiguous tee topology fail before writing MED.
- A stale result fingerprint blocks review after section or mesh settings
  change.
- A geometry-only surface is labelled design or analysis-mesh geometry; it is
  never labelled deformed or solver-backed.
- A failed boolean operation reports the selected element and tee ids and
  preserves no partial authoritative mesh.

## Verification Contract

### Unit and geometry tests

- Classify a three-way tee consistently with compliance SIF logic.
- Reject ambiguous and invalid junctions.
- Generate closed straight-pipe and tee wall skins with finite vertices and
  consistently oriented faces.
- Verify IPE, rectangular hollow, circular pipe, bar, and cable scene meshes.
- Verify every generated group is non-empty, disjoint where required, and
  mapped to stable source refs.
- Verify Gmsh lifecycle handling preserves a caller-owned session.

### Gmsh integration tests

- Generate a second-order straight hollow pipe MED mesh.
- Generate equal and reducing tee MED meshes.
- Confirm non-empty 3D cells and all required physical groups.
- Confirm the minimum wall-resolution preflight and cell-orientation gate.
- Read the generated MED back and rebuild a matching `AnalysisMesh`.

### Code_Aster reference cases

1. **Straight pressurized pipe:** compare radial and hoop stress away from end
   effects against the thick-cylinder Lamé solution at more than one mesh size.
2. **Tee:** run a real pressurized or mechanically loaded equal tee, require
   stable reactions and stress-location convergence under refinement, and keep
   the result explicitly FE stress rather than code compliance.
3. **Isolated bend:** run a real pressurized 90-degree bend, require the anchor
   reaction to balance the independently derived pressure resultant, and build
   the existing result and analysis-skin scene.

All cases must create a verified `AnalysisRun`, matching solver-input
identities, `.rmed`, imported displacement/stress/reaction data, and a review
bundle. Export-only success is insufficient.

### Structural gallery and browser proof

- Re-solve the support-rack gallery after assigning its different sections.
- Assert that model metadata names each section and that mesh assets contain
  visibly different profile geometries.
- Build the assembled Pages tree.
- In the browser, inspect an IPE column, a rectangular member, a circular pipe,
  and the tee analysis mesh.
- Verify the tee/pipe analysis mesh is separate from result overlays and that
  solver results appear only for the real solved reference bundle.

## Implementation Sequence

1. Add shared tee topology classification and make compliance use it.
2. Extract dependency-light section meshing and render true structural
   cross-sections in the existing web scene.
3. Extend `RackBay` section roles and update the unsolved model/example tests.
4. Implement and verify the linear-pressure writer slice.
5. Implement straight-pipe OCC solids, group classification, MED export, and
   mesh readback.
6. Implement tee outer-union/inner-cut geometry and conformal connection to
   selected straight pipes.
7. Add the volume-specific Code_Aster compiler and straight-pipe Lamé reference
   case.
8. Add the real tee solve, import, and review bundle.
9. Refresh the affected official solver-backed gallery and run assembled Pages
   browser verification.
10. Add the isolated `BendGeometry` torus-segment mesh and real pressure-result
    reference without enabling connected mixed selections.

Each step leaves one independently runnable check. Unsupported geometry remains
an explicit error until its own step is verified.

## Acceptance Criteria

The design is complete when:

- SALOME-Meca is not required for the supported native meshes;
- structural examples visibly distinguish their authored sections;
- straight pipes, isolated circular bends, and explicit tees produce valid,
  grouped, second-order Gmsh MED meshes;
- the same geometry can be inspected in the existing web-review path;
- a real Code_Aster straight-pipe reference solve agrees with the Lamé basis;
- a real tee solve imports and displays traceable FE results;
- no export-only or geometry-only artifact is presented as a solver result; and
- full Python, viewer, publication, and self-hosted Code_Aster gates pass.
