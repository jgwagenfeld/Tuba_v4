# Mixed 1D/3D Code_Aster coupling research

Date: 2026-08-31  
Scope: local Tuba v2 evidence, current Tuba v4 seams, and official Code_Aster
coupling semantics. This is a research note, not solver validation.

## Decision

Use one mixed Code_Aster study and one persisted `AnalysisMesh`/`ResultState` as
the display authority. Replace the selected tee/bend/pipe span with a real 3D
solid mesh; retain the surrounding native 1D pipe elements; and couple each
regular straight solid cut face to its corresponding 1D endpoint with
`AFFE_CHAR_MECA/LIAISON_ELEM`.

For Tuba v4 pipes, which are modeled as `TUYAU_3M`, the normal coupling is
`OPTION='3D_TUYAU'`, with `CARA_ELEM` and `AXE_POUTRE`. Use `3D_POU` only when
the actual adjoining 1D modelization is an Euler/Timoshenko beam such as
`POU_D_T`. Do not use a coincident center node as the solid-to-line coupling.

This differs from Tuba v2: v2 generated a genuine mixed solve, but always wrote
`OPTION='3D_POU'` for its volume-to-line interfaces, including interfaces next
to `TUYAU_3M`. That transfers the six beam rigid-section degrees of freedom but
not the extra TUYAU bulging/ovalization modes. It is evidence for the workflow,
not the correct v4 operator choice.

## What Tuba v2 actually did

The inspected sibling checkout is `D:\Gitprojects\TUBA_V2` at commit
`fe4dbe0ebcd91e059fb69644683dcb4546a618c0`. Its tracked source files used below
were present; the worktree had unrelated deletions of tracked `__pycache__`
files.

1. The DSL deliberately alternated 1D and 3D members. The example creates a 1D
   straight, a `V_3D` straight, another 1D straight, a `Bent_3D`, a 1D straight,
   a `TShape_3D`, and two more 3D straights
   (`D:\Gitprojects\TUBA_V2\tutorials\000_Testing\x_008_TUYAU_3d\008_TUYAU_3D_K_M_F.py:20-33`).

2. It constructed actual hollow solids and hexahedral meshes in Salome. A
   straight 3D pipe was partitioned to permit hexa meshing, classified into
   `StartFace`, `EndFace`, `InnerFace`, and `OuterFace`, and meshed with
   segments, quadrangles, and hexahedra
   (`D:\Gitprojects\TUBA_V2\tuba\write_Salome_file.py:328-404`). The tee used
   Salome's `MakePipeTShape`, created start/incident/end and inner/outer face
   groups, and selected a hexahedral algorithm
   (`D:\Gitprojects\TUBA_V2\tuba\write_Salome_file.py:783-880`).

3. It concatenated the separate point, line, and volume meshes and merged
   coincident nodes/equal elements
   (`D:\Gitprojects\TUBA_V2\tuba\write_Salome_file.py:1137-1146`). That merge
   was mesh cleanup, not the solid-to-line mechanical connection: the annular
   solid cut face has no centerline node through which bending moment and
   rotation could be transferred.

4. Its generated `.comm` converted `G_3D` to quadratic elements with
   `CREA_MAILLAGE/LINE_QUAD`, assigned `G_TUYAU` to `TUYAU_3M`, and assigned
   each solid and its face groups to `3D`
   (`D:\Gitprojects\TUBA_V2\tutorials\000_Testing\x_008_TUYAU_3d\008_TUYAU_3D_K_M_F_aster.comm:90-170`).

5. The physical connection was `LIAISON_ELEM`, face to one 1D centerline node.
   The generator writes two `3D_POU` links for a 3D straight and three for a 3D
   tee (`D:\Gitprojects\TUBA_V2\tuba\write_Aster_file.py:1202-1276`). The
   generated example contains those links for straight, bend, and tee faces
   (`D:\Gitprojects\TUBA_V2\tutorials\000_Testing\x_008_TUYAU_3d\008_TUYAU_3D_K_M_F_aster.comm:249-305`).
   No generated `OPTION='3D_TUYAU'` use was found in the v2 source; only dormant
   template placeholders exist. Therefore v2 did **not** couple the 3D faces to
   all TUYAU kinematic modes even though its remaining pipe group was
   `TUYAU_3M`.

6. It solved the mixed model with `MECA_STATIQUE`, calculated reactions/forces,
   TUYAU equivalent stress, and 3D tensor/equivalent stress, then wrote the
   results to one MED result file and displacement/reaction/force tables
   (`D:\Gitprojects\TUBA_V2\tutorials\000_Testing\x_008_TUYAU_3d\008_TUYAU_3D_K_M_F_aster.comm:509-640`; generator:
   `D:\Gitprojects\TUBA_V2\tuba\write_Aster_file.py:1391-1482`). ParaVis read
   that `.rmed`, exposed 3D `SIEQ_ELNO/VMIS`, and optionally overlaid a
   translucent geometry compound
   (`D:\Gitprojects\TUBA_V2\tuba\write_ParaPost_file.py:25-62,67-105,344-367`).

## Code_Aster coupling choices

| Technique | What it does | Appropriate use here |
| --- | --- | --- |
| Shared node | Gives compatible 1D modelizations the same centerline translations/rotations. It does not distribute a force or moment over an annular solid face. | Acceptable for compatible 1D-to-1D transitions, with the TUYAU-to-beam transition far enough from a disturbance for ovalization to decay. Not a solid-to-line coupling. |
| `LIAISON_ELEM`, `3D_POU` | Builds six linear relations between a quadratic 3D cut face and one beam node, transferring the three translations and three rotations. The beam axis must be normal to the face and meet its centroid. | Use when the adjacent line element is a beam (`POU_D_*`). It does not transfer the extra TUYAU modes. |
| `LIAISON_ELEM`, `3D_TUYAU` | Connects a 3D cut face to one TUYAU endpoint and transfers the six beam modes plus TUYAU bulging and Fourier ovalization modes. It requires the pipe `CARA_ELEM` and `AXE_POUTRE`. | Preferred for v4 `TUYAU_3M` pipe-to-solid interfaces. |
| `MASSIF_POUTRE` | Not a current `AFFE_CHAR_MECA` keyword or `LIAISON_ELEM` option found in the official syntax. “Raccord massif-poutre” is the conceptual name of the connection. | Do not emit it. The concrete operator is `LIAISON_ELEM/3D_POU` (or `3D_TUYAU` for TUYAU). |
| Submodel/zoom projection | Solves a global model first, projects its displacement field to the boundary of a separate local model, then imposes it with `AFFE_CHAR_CINE/EVOL_IMPO`. It is one-way: the local 3D stiffness does not feed back into the global solve. | Useful later for local stress refinement. It is not the requested single, simultaneously coupled 1D/3D model. |

The official `AFFE_CHAR_MECA` manual defines `LIAISON_ELEM`, its `3D_POU` and
`3D_TUYAU` operands, group requirements, `CARA_ELEM`, and `AXE_POUTRE`. It also
warns that the connection should be away from strong curvature, corners,
holes, material discontinuities, or sharp load/temperature changes, and that
the linear relations are defined in the initial geometry rather than updated
for large displacement: [U4.44.01, Dirichlet mechanical loads, `LIAISON_ELEM`](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.44.01/Chargements_de_type_Dirichlet_.html#mot-cle-liaison-elem).

The official TUYAU command guide explicitly describes `3D_TUYAU`, identifies
validation case `SSLX102F` as a `3D`/`TUYAU` connection using `HEXA20` and
`METUSEG3`, recommends 3D or shell modeling for tees, and places the connection
in a regular straight section: [U2.02.02, TUYAU command description](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u2/u2.02.02/Description_du_jeux_de_commandes.html).

Code_Aster's reference derivation explains why a single coincident point is not
the correct solid-to-beam link: a solid point has no rotational degree of
freedom and concentrating force/couple transfer there creates an ill-defined,
singular local connection. It also explains why simply forcing a whole face to
rigid beam kinematics creates parasitic stresses: [R3.03.03, beam-to-solid
connection](https://code-aster.org/doc/v14/fr/man_r/r3/r3.03.03.pdf).

For the separate submodel alternative, Code_Aster documents structural zoom
under `AFFE_CHAR_CINE/EVOL_IMPO`: the coarse/global result is projected to the
local model boundary and imposed as an evolving kinematic field:
[U4.44.03, `AFFE_CHAR_CINE`](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.44.03/Op_randes.html).

## Minimal v4 architecture

The current checkout was inspected at
`8c07d5c7d1efb1078565874e5112276099d2f603`.

### 1. Extend the existing native mesh authority

The native volume mesher already creates `G_SOLID_region_0`, tee ownership, the
inner/outer skins, and `G_END_<node>` cut-face groups
([pipe_volume.py](../../tuba/meshing/pipe_volume.py#L84),
[straight end groups](../../tuba/meshing/pipe_volume.py#L227),
[tee end groups](../../tuba/meshing/pipe_volume.py#L365)). It also reads the
volume nodes/elements/groups back into an `AnalysisMesh` and stores a display
surface skin ([pipe_volume.py](../../tuba/meshing/pipe_volume.py#L500)).

For a mixed region:

- keep that solid mesh and its cut-face groups;
- omit the centerline elements replaced by the solid from the line mesh, model,
  material, and load groups, avoiding duplicate stiffness/mass/load;
- mesh the remaining pipe members as native quadratic line elements in the same
  MED mesh;
- create one single-node `GROUP_NO` at the centroid of each solid cut face;
- store both solid and line nodes/elements, both modelizations, and all solver
  groups in the same `AnalysisMesh`;
- derive `AFFE_MODELE`, `LIAISON_ELEM`, result parsing, and scene geometry from
  that same mesh/name map.

Do not make the visible geometry and the analysis mesh independent authorities.
The review scene should be a projection of this combined solved mesh plus its
matching result state. The solid surface skin and line elements are sufficient
for display; volume-cell connectivity remains available for solver provenance.

### 2. Select coupling from the adjoining modelization

v4 already has one modelization authority: pipes map to `TUYAU_3M`, while true
beam elements map to `POU_D_T`
([modelisation.py](../../tuba/solver/modelisation.py#L41)). Emit:

```text
3D face <-> TUYAU_3M node: LIAISON_ELEM OPTION='3D_TUYAU',
                           CARA_ELEM=CARA, AXE_POUTRE=(...)
3D face <-> POU_D_T node:  LIAISON_ELEM OPTION='3D_POU'
```

The selected 3D tee region should include straight stubs. Each branch then has
its own cut face and its own outward 1D continuation node. Do not couple all
three tee faces to one junction node. Put each interface far enough from the
tee crotch/bend that the section is regular and local ovalization/stress
perturbations can decay.

### 3. Compile one load/material/solve command

One `.comm` should contain:

1. `AFFE_MODELE`: solid group as `3D`; remaining pipe group as `TUYAU_3M`.
2. `AFFE_CARA_ELEM`: the remaining pipe section/orientation data.
3. `AFFE_MATERIAU`: material on both regions.
4. `AFFE_CHAR_MECA`: supports/loads plus one `LIAISON_ELEM` per cut face.
5. Internal pressure exactly once: `PRES_REP` on the 3D inner skin and the
   established TUYAU pressure load on remaining 1D pipes. End-cap/effective
   thrust must be checked by global equilibrium so it is neither lost nor
   doubled at the interfaces.
6. `MECA_STATIQUE`, `CALC_CHAMP`, and one MED result output.

The existing volume study already provides the material, 3D pressure/gravity,
solve, derived fields, MED, and CSV table structure
([aster_volume.py](../../tuba/solver/aster_volume.py#L190)). The main 1D compiler
already provides `CARA_ELEM`, TUYAU fields, MED output, and parseable tables
([aster_comm.py](../../tuba/solver/aster_comm.py#L750)). Reuse those writers or
factor their common pieces. Do not promote the current experimental mixed
exporter as-is: it explicitly declares itself export-only
([mixed_study.py](../../tuba/solver/mixed_study.py#L18)), records only line
connectivity while leaving solid/face groups empty
([mixed_study.py](../../tuba/solver/mixed_study.py#L219)), and writes only
`AFFE_MODELE` plus incomplete `LIAISON_ELEM` entries before `FIN()`
([mixed_study.py](../../tuba/solver/mixed_study.py#L279)). Runtime correctly
refuses to present that handoff as solved results
([aster.py](../../tuba/solver/aster.py#L432)).

### 4. Save and display the evaluated result

Persist one attested run with:

- the combined `AnalysisMesh` and solver input identity;
- one `.rmed` containing at least `DEPL`, 3D `SIGM_ELNO`/`SIEQ_ELNO`, TUYAU
  generalized forces/stress fields, and `FORC_NODA`/`REAC_NODA` as required;
- parseable displacement, force/reaction, solid stress, and TUYAU result tables;
- one `ResultState` tied to the same `mesh_id`, with file references and solve
  attestation. `ResultState` already persists displacements, reactions, element
  results, files, metadata, and solver identity
  ([results.py](../../tuba/analysis/results.py#L25)).

The parser should partition fields by modelization rather than fabricate one
uniform result shape: volume nodes/surface VMIS belong to the solid surface;
native node results and TUYAU subpoint/element results stay on the line region.
The existing volume parser already maps volume displacements, supported-node
forces, and surface VMIS into the result model
([aster_volume_results.py](../../tuba/solver/aster_volume_results.py#L17)).

The web scene should then show, from that one run:

- the solid's actual exterior mesh skin, optionally deformed and colored by 3D
  VMIS;
- the remaining 1D analysis mesh/deformed pipe/result diagrams;
- optional diagnostic markers for coupling faces/nodes, hidden by default;
- a clear field label: 3D FE VMIS is not ASME B31.3 piping-code stress.

This is already the shape of the trusted volume-review path: it imports an
attested artifact, stages its evidence, and builds the scene and engineering
review from the same analysis run
([code_aster_tee_volume_review.py](../../examples/code_aster_tee_volume_review.py#L52)).
The real-solver test also checks identical solver identities and asserts that
the scene contains a `volume_stress_field`
([test_code_aster_tee_volume_reference.py](../../tests/test_code_aster_tee_volume_reference.py#L19)).
Official MED field output semantics are documented under
[`IMPR_RESU/RESU`](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u7/u7.05.21/Mot-cl__facteur_RESU.html).

## Required real-solver proof

Before removing the export-only blocker, add a small real Code_Aster integration
matrix:

1. A straight `TUYAU_3M` - `HEXA20` solid - `TUYAU_3M` specimen under axial,
   bending, torsion, and pressure cases. Check displacement continuity and force
   plus moment equilibrium across both interfaces.
2. Mesh refinement of the solid and interface cut-face mesh. Check stable global
   resultants/energy and document that local interface stress is excluded from
   engineering hotspot interpretation.
3. A tee solid with three straight stubs and three separate `3D_TUYAU`
   interfaces. Compare global resultants with a whole-line model and local fields
   with an all-3D reference where practicable.
4. A beam-specific specimen proving `3D_POU`, separately from the pipe specimen.
5. Real runtime attestation and import into the same scene/review path; generated
   `.med`/`.comm`/`.export` files alone are not proof.

The official `SSLX102F` case is the closest operator-level validation pattern
for the first specimen; it is not a substitute for Tuba's own naming, loading,
result-import, and display tests.

## Blockers and risks

- The current mixed exporter is not solve-ready and its `AnalysisMesh` is not a
  representation of the actual solid mesh.
- `3D_TUYAU` needs correct `CARA_ELEM`, a normalized `AXE_POUTRE`, one-node
  endpoint groups, compatible cut-face orientation, and consistent centroid/axis
  geometry. These must be derived and validated, not user-entered free text.
- The native volume exporter currently allows only anchor supports on selected
  terminals and rejects nodal and thermal loads
  ([aster_volume.py](../../tuba/solver/aster_volume.py#L131)). A mixed compiler
  must reconcile the mature 1D load/support path with 3D face loads.
- Pressure end effects are the highest load-transfer risk: 1D TUYAU pressure and
  3D surface pressure can under- or over-count axial thrust without explicit
  resultant checks.
- Coupling too close to a tee, bend, diameter change, or load discontinuity can
  contaminate the local solid stress. Straight stubs and exclusion zones must be
  part of model generation and review metadata.
- `LIAISON_ELEM` is based on initial geometry and is not a general large-rotation
  remeshing/contact connection.
- A shared-node-only implementation cannot transfer a solid-face bending moment
  correctly; global coincident-node merging must not be mistaken for coupling.
- Full volume result payloads can be large. Persist the authoritative solver
  artifact and mesh, but send the viewer only the exterior surface plus selected
  fields; do not build a second independently tessellated geometry authority.
- 3D VMIS is an FE stress visualization. It must remain clearly distinct from
  piping-code stress/compliance evaluation.

## Primary official sources

- [Code_Aster U4.44.01: Dirichlet mechanical loads and `LIAISON_ELEM`](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.44.01/Chargements_de_type_Dirichlet_.html#mot-cle-liaison-elem)
- [Code_Aster U2.02.02: TUYAU command/modeling guidance](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u2/u2.02.02/Description_du_jeux_de_commandes.html)
- [Code_Aster R3.03.03: 3D solid-to-beam connection derivation](https://code-aster.org/doc/v14/fr/man_r/r3/r3.03.03.pdf)
- [Code_Aster U4.44.03: `AFFE_CHAR_CINE`, including structural zoom](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.44.03/Op_randes.html)
- [Code_Aster U7.05.21: fields emitted by `IMPR_RESU/RESU`](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u7/u7.05.21/Mot-cl__facteur_RESU.html)
