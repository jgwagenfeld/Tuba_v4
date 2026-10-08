# STEP Mixed Code_Aster Studies

For a procedural STEP spool/pipe example with saved local refinement, diagnostic
regeneration, and authentic Code_Aster convergence, see
[mesh-refinement-review](../../examples/mesh-refinement-review/README.md).
Global/region sizes and local entity/CAD/spatial rules resolve into one effective
policy. CAD refinements use finite face distances scoped to their component;
legacy `interface_mesh_sizes` remains supported. Each convergence level scales
requested sizes while retaining geometry, target extents, quadratic families,
physical groups, materials, orientation, and line-to-solid coupling. Independent
attestation, actual topology, and per-level identities gate result reuse. Quality
metrics describe geometry; unlike stress supports remain separate, unavailable
quantities and near-zero changes have no relative verdict, and mesh comparison
does not certify accuracy or compliance.

Tuba can import STEP geometry for mixed Code_Aster studies only after the imported
geometry has explicit analysis regions, confirmed ports, material assignments,
mesh groups, and coupling specs.

Exported `.med`, `.comm`, `.export`, `study_manifest.json`, and
`study_tuba_fem.json` files are solver handoff artifacts. They are not completed
engineering results.

Production stress, displacement, reaction, compliance, operating-state clash, and
result visualization workflows must use artifacts produced by a real Code_Aster
run. If Code_Aster is unavailable, Tuba may export the study for inspection but
must stop before displaying solver results.

Author mixed structures in procedural Python. Native straight pipes use
`TUYAU_3M`, frame members use `POU_D_T`, imported STEP volumes use `3D`,
and authored planar panels use `DKT`. Each physical region and line member
retains its own material and section. Gmsh generates the FEM nodes and cells;
the authoring script defines engineering geometry and named interfaces.
Connected TUYAU members currently require an open, consistently oriented,
collinear chain. Each chain receives one endpoint orientation seed; branch
junctions use explicit imported solids. Bent or closed pipe chains are rejected.

Two connections serve different purposes:

- `connect_pipe_to_port` / `connect_beam_to_port` join a continuation endpoint
  to a confirmed solid cut face using `3D_TUYAU` / `3D_POU`.
- `add_rigid_patch` joins explicitly selected CAD faces, panel vertices/edges,
  or native nodes to a massless `DIS_TR` reference point with `LIAISON_SOLIDE`.
  A support attached to a frame node then controls the released DOFs.

For the selected V3 convention, hold global DX, DY, DRX, DRY, DRZ and release DZ:

This convention reproduces an ideal guide with no vertical sliding resistance.
For the distinction between this rigid mapping and a proposed frictional joint,
see the [tee lug contact modeling review](tee-lug-contact-modeling-review.md).
Mixed surface contact remains unsupported; the review describes design and
qualification requirements.

```python
lug = model.add_reference_point("left_lug", position=lug_position_m)
model.add_rigid_patch(
    "left_lug_patch", reference=lug, component="component:tee",
    faces=[lug_face_selector],  # stable geometry in source-local CAD units
)
model.add_support(
    lug, "custom", attached_to=frame_node,
    blocked_dof=[1, 1, 0, 1, 1, 1], attachment_mode="dof_equality",
)
```

`dof_equality` reproduces V3's equal selected DOFs even when reference nodes
are separated. It does not add lever-arm terms. Use the default `rigid_offset`
when the intended connection includes the physical offset. Neither choice
defines the geometry of an absent plate.

Panels need an explicit outline, thickness and material:

```python
model.add_shell_panel(
    "plate", polygon=outline_m, thickness=0.012,
    material="Steel", mesh_size=0.025,
)
model.add_rigid_patch(
    "plate_edge", reference=plate_reference, shell="group:plate", edges=[0],
)
```

Polygon coordinates, thickness and mesh size are in metres. `edges` select
all mesh nodes along the named polygon edges; `vertices` select only the
specified corner nodes. CAD face selectors are resolved again on each mesh;
Gmsh entity tags are never authored interface identities.

In Studio Build, select the component, port, pipe, shell or attached support and
enable **Show interface mapping** in its inspector. Amber marks the reference
point; cyan marks the selected face, edge or nodes. The inspector distinguishes
the structural connection (for example, 1D pipe to 3D solid) from its boundary
mapping (0D endpoint to 2D cut face), and lists the actual operator and releases.
Before meshing it shows the authored footprint. A current, attested Review mesh
supplies the exact boundary cells and nodes in Build; stale evidence is not used.
Generated solid tee borders use the study's explicit `VOLUME_EXPORT` selection.
STL reference geometry carries no structural mapping unless one is defined.

Use parameterized project construction units for repeated connections and
structures. Keep each unit responsible for one structure, and pass dimensions,
sections, materials and connector masks as parameters. Existing JSON records,
inspection and generated round trips carry these analysis regions and couplings.

Uniform operating temperatures can target a native frame/pipe group, or a
solid/shell region by its region id, owner id or mesh group. Contents density
uses existing pipe `fluid_density` fields. Ground supports may prescribe held
translations and rotations. Relative prescribed movement across a node attachment
is rejected. Reference carriers require a physical solid or shell region in the
same mixed study. Contact, buckling, curved shells and temperature-dependent
elastic material laws require their own qualified capabilities; unsupported
requests fail before solving.

The complete evaluation remains:

```text
authored Tuba structure and named connections
  -> Gmsh MED mesh and checked groups
  -> real Code_Aster solve
  -> verified imported result state
  -> processed web-scene review
```

Mesh quality checks and a successful reference solve establish different
facts. The reference example uses known test geometry.

`examples/code_aster_mixed_connections_review.py` composes a known shell strip,
frame, STEP spool, pipe and released V3 joint. It runs `model.solve`, imports
verified Code_Aster artifacts and writes the existing web-scene review. Its
`shell_strip(model, ...)` function is parameterized project code that users and
agents can reuse; the panel outline stays in authored Python.

The supported mixed path solves automatically through `model.solve`; it requires
an available Code_Aster runtime and no developer opt-in. Code_Aster 18.0.12 passed
eleven reference checks covering seventeen real solves: five STEP checks and six
mixed-connection checks. These cover STEP axial, bending, torsion and pressure
response, pipe/frame continuity, combined stiffness and equilibrium, rigid-patch
kinematics, physical-corner anchoring and shared-reference fanout, released DOFs,
DKT bending/refinement and outer-layer stress,
prescribed translation, fluid weight and uniform thermal expansion.

Reference-carrier studies use `MULT_FRONT`, `NPREC=8` and
`STOP_SINGULIER='OUI'`. The `DIS_TR` carriers retain zero stiffness and mass;
the solver policy is recorded in the solver-input identity. Qualification covers
the supported straight collinear pipe chains, planar DKT panels and scalar
elastic materials described above. It does not qualify unsupported contact,
buckling, curved shells, insulation loads or temperature-dependent material laws.
The mandatory release reference selection includes both suites.
`TUBA_RUN_CODE_ASTER_INTEGRATION=1` selects their native integration tests;
normal mixed solving does not require that flag.

Studio's import workflow previews actual STL/STEP triangles with an explicit unit
scale and placement, then stores immutable source files under the project
`geometry/` directory. It returns an explicit Python import call without rewriting
authored functions. `Model.import_stl` creates reference geometry for inspection
and clearance; it creates no stiffness or analysis region. STEP ports must still
be confirmed, assigned a material and connected before structural evaluation.

`examples/imported-geometry-studio/` shows leading parametric functions and recorded
`assemble` calls for two solid instances, pipe/beam ports, shell patches and a
released V3 joint. Definitions and invocations are linked in the inspector.
Project helpers and referenced geometry refresh on change; failed reloads retain
the last valid view, mark its review stale and block solving until repaired.

STL clearance coverage checks native straight pipe/frame circular envelopes and
solver-derived operating polylines against the placed triangles. Closed manifold
surfaces also detect enclosed centerlines. Open surfaces have surface-distance
coverage only. Shell/STEP bodies and reference-to-reference clearance are outside
this check's coverage; cold bends fail explicitly when STL references are present.
