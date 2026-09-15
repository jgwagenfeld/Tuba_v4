# Supports Attached to Other Nodes — Design

**Status:** proposed 2026-09-15
**Scope:** 1D Code_Aster studies (`TUYAU_3M`, `POU_D_T`). Pipe-volume and mixed studies keep their anchor-only
ground supports.

## Problem

An engineer states what a support does and what it sits on: a shoe resting on a rack beam, a spring hanger
hanging from steel. Tuba can only express the first half, and gets parts of that wrong:

- **Every support is fixed in space.** `add_support` has no second node. The support-rack example puts the pipe
  "on" the rack by routing it through the rack's corner nodes, which welds pipe and rack in all six DOFs, and then
  adds global rests on those nodes. The rack association in `tuba/load_path.py` is post-solve bookkeeping that the
  solver never sees.
- **Rests on `TUYAU_3M` hold the pipe down instead of up** (fact 1). The `LIAISON_UNIL` zone is written with
  `COEF_MULT=+1`, which Code_Aster enforces as `DZ <= 0`.
- **Rests behave differently per formulation.** On `POU_D_T` they become native `DIS_CHOC` shoes with friction,
  but that path refuses internal pressure and operation fields (fact 9) and still pins the shoe to a fixed point.
- **Ground springs and support masses land on the wrong node** (fact 8).
- **The support type string is interpreted in about a dozen places:** the `aster_comm` boundary-condition branch,
  `aster_contact`, `modelisation`, `aster.py`, plots, fragments, IFC import, the builder and volume results.
  `hanger` and unknown types, such as the `sliding` documented by the MCP edit tool, fall into a branch that fixes
  DX, DY and DZ. A guide with a skewed direction blocks every global axis that direction touches.

## Measured facts

Real Code_Aster 18.0.12 solves on the WSL Ubuntu runtime, 2026-09-15. Unless a row says "unedited", Tuba exports were
edited by hand to add the form under test. "Rack model" is `examples/support-rack-review` with the pipe given its
own nodes 0.25 m above the two rack attachment nodes, the whole model at 180 °C.

| # | Study | Result |
|---|---|---|
| 1 | Committed evidence of `elements-supports-review`, `code-aster-review`, `autorouted-expansion-loop` and `support-rack-review` (unedited) | Rest nodes sink 20.7, 5.0 and 3.5 mm with zero reaction. The rack example holds its heated column tops down with −809 kN, which is E·A·α·ΔT of the IPE160. The zone enforces `DZ <= 0` |
| 2 | 6 m DN100 cantilever, rest at the tip, gravity only, `COEF_MULT` +1 against −1 | +1: tip −40.5 mm, reaction 0. −1: tip 0 mm, reaction +353.75 N, which is 3/8 qL |
| 3 | Rack model on `TUYAU_3M` with 1.5 MPa pressure, `MECA_STATIQUE`, `LIAISON_DDL` DZ(rack) − DZ(pipe) = 0 per shoe | Pipe-side rack column 3.52 kN (shipped example: 810 kN). Link force 2.73 kN, seen as equal and opposite `REAC_NODA` on the two nodes. The pipe slides 3.84 mm along the rack |
| 4 | Rack model on `POU_D_T` without pressure, native friction shoes (μ 0.3) whose `SEG2` is re-pointed from the ground node to the rack node, ground `DDL_IMPO` removed, `DIST_1` set to the 0.25 m element length | N −2.72 kN, friction/normal 0.300 while sliding, slip 3.83 mm |
| 5 | Rack model on `TUYAU_3M` with pressure, `STAT_NON_LINE` with 10 increments, `SEG2` `DIS_T` + `DIS_CHOC` between rack node and pipe node (μ 0.3) | N −2.73 kN, friction/normal 0.3000, V4 = 1 (sliding), slip 3.8 mm, no solver errors |
| 6 | As 4, but keeping Tuba's shoe geometry (helper node 1 m below the pipe node) with the helper tied to the rack node by `LIAISON_DDL` on DX, DY, DZ | Identical to 4: N −2723.2 N, friction 817.0 N. The helper follows the rack node exactly |
| 7 | Rack model on `TUYAU_3M` with pressure, `MECA_STATIQUE`: helper node tied to the rack node in all six DOFs, `SEG2` `DIS_TR` from helper to pipe node with global `K_TR_D_L` (0, 0, 1e7, 0, 0, 0) | First attempt refused with `<DISCRETS_67>` "La dilatation n'est pas prise en compte sur les éléments discrets en linéaire" on element type `MECA_DIS_TR_L`. With `AFFE_VARC` restricted to `('AllPipes', 'G_TUBE')`: spring N −2629 N, relative DZ 0.263 mm = N/k, free in X and Y. `REAC_NODA` at each helper node is +2629.4 N, the spring force |
| 8 | Cantilever with anchor N0 and a ground spring `stiffness_matrix=[0, 0, 1e5, 0, 0, 0]` at tip N1, gravity + 120 °C (unedited export, `MECA_STATIQUE`) | Solves, but the `POI1` made by `CREA_POI1=_F(..., NOEUD='N1')` sits at (0, 0, 0) with zero force, and the tip sags 40.531 mm as if unsupported. Removing or reordering the zero `M_TR_D_N` occurrence changes nothing. With `GROUP_NO='GN_N1'` the element sits at (6, 0, 0): tip −3.253 mm, spring VZ −325.35 N, matching hand theory (3.25 mm, 325 N). `NOEUD='N2'` gives the same correct result although no node is named N2: the operand takes node numbers in mesh order, so Tuba's `'N1'` meant the first node |
| 9 | `support-rack-review` exported with `pipe_modelization='POU_D_T'` (unedited) | Refused: "Native contact load paths currently support uniform temperature, gravity and nodal forces only." |
| 10 | `elements-supports-review` with `COEF_MULT` −1 | `NO_CONVERGENCE` after about four minutes. Its committed solve already needed time-step cuts down to level 3 |

The documentation agrees:

- `LIAISON_DDL` writes `sum(alpha_i * U_i) = beta` over ordered nodes and DOFs, so one relation can span several
  nodes. `LIAISON_GROUP` applies one relation to node pairs from two groups (U4.44.01).
- `LIAISON_UNIL` writes `sum(alpha_i * p_i) <= r` for each node of `GROUP_NO` separately, and a negative
  `alpha_i` reverses it (U4.44.11). It cannot relate two nodes.
- `DIS_CHOC` models contact with Coulomb friction "entre deux structures". On a `SEG2` the normal distance is
  `dN = ((X2 + u2) - (X1 + u1)) - DIST_1 - DIST_2`, with contact when `dN <= 0` (R5.03.17 §7.1).
- CAESAR II connects a restraint to a rigid point in space unless a connecting node (CNode) is given, in which case
  the restraint stiffness acts between the two nodes.

## Decisions

1. **A support can name the node it is attached to.**
   - New field `Support.attached_to: str | None`. Absent means ground, as today.
   - It flows through `TubaModel.add_support`, the builder's `add_support`, both JSON schemas, `to_dict` and
     `from_dict`, generated model scripts, `AddSupport` patches with their local node-id remapping, fragments,
     the MCP edit tool and the supports report table.
   - Validation: the node exists and is not the support's own node. That also catches a pipe built through the
     structure node, because the builder snaps to existing nodes.
2. **Support types form a closed list, each with one meaning.**

   | Type | Holds |
   |---|---|
   | `anchor` | all six DOFs, both ways |
   | `guide` | with `direction`: that one direction, both ways. Without: DX, DY and DZ, both ways. That is today's meaning, used by examples, tests and the tutorial |
   | `rest` | pushes along `direction` (default +Z), slides with optional friction, lifts off; optional gap and contact stiffnesses |
   | `spring` | `stiffness_matrix`, or `stiffness` along `direction`, in the global frame |
   | `custom` | the `blocked_dof` mask, both ways |
   | `hanger` | DZ, both ways. Today it fixes DX, DY and DZ through the fallback branch. No example or test uses it; IFC import can create it |

   - Any other type is refused in `add_support` with the list of valid types.
   - The MCP edit tool documents `rest` instead of `sliding`.
   - Friction, gap and contact stiffnesses stay rest-only.
   - `imposed_displacement` is refused on attached supports.
3. **An attachment acts between matching global DOFs of the two nodes.** No lever arm between the node positions
   is modelled. When the offset moment matters, for example an anchor on a beam below the pipe, the engineer
   models the stanchion as an element.
4. **One module turns supports into solver forms.**
   - A new `tuba/solver/support_plan.py`, following the `modelisation.py` pattern, returns each support's form
     with everything the writers need: helper nodes, `SEG2` and `POI1` elements, groups, `DDL_IMPO` rows,
     `LIAISON_DDL` rows, contact parameters and whether the solve must be nonlinear.
   - The mesh writer, command writer, `modelisation_assignments`, contact tables, the `load_path` history writer
     and the load-path review consume it.
   - Nothing else branches on support type to decide solving. Plots, glyphs and IFC keep the type name for
     display only.
   - `aster_contact.shoes` is absorbed into the planner, and the `LIAISON_UNIL` branch is deleted.
5. **Forms.** P is the support node, A the attached node, n the unit `direction`.

   | Type | Ground | Attached to A |
   |---|---|---|
   | `anchor`, `custom`, `hanger` | `DDL_IMPO` on the held DOFs, with today's text for anchor and custom | `LIAISON_DDL` `u(P) - u(A) = 0` per held DOF |
   | `guide` without direction or axis-aligned | `DDL_IMPO` on the held DOFs (today's text) | `LIAISON_DDL` per held DOF |
   | `guide` with a skewed direction | one `LIAISON_DDL` `sum(n_i * u_i(P)) = 0` | one `LIAISON_DDL` `sum(n_i * (u_i(P) - u_i(A))) = 0` |
   | `rest` | shoe: helper H at `P - (1 + gap) * n`, `SEG2` from H to P, `DIS_T` with `DIS_CHOC` and `DIST_1 = 1`, H fixed by `DDL_IMPO` | the same shoe, H tied to A by `LIAISON_DDL` on DX, DY, DZ |
   | `spring` | `POI1` `DIS_TR` `K_TR_D_N` | helper H at `P - 1 m * ez`, `SEG2` `DIS_TR` from H to P with global `K_TR_D_L`, H tied to A on all six DOFs |

   - Support masses stay `POI1` `M_TR_D_N` at P.
   - The shoe does not depend on where A is, so A may coincide with P's position or sit anywhere else.
   - Supports on `TUYAU_3M` nodes keep their warping restraint.
6. **Every rest is a shoe, on every formulation.** The `LIAISON_UNIL` zones, the `UNIL_*` constants and
   `DEFI_CONTACT` go away, and fact 1's sign bug with them. Shoes keep today's contact defaults (`RIGI_NOR` 1e10,
   `RIGI_TAN` 1e8) and the `contact_law='DIS_CHOC'` compiler input, so every shoe exports attested contact rows.
7. **The solve type follows the plan.**
   - Any shoe or cable makes the solve `STAT_NON_LINE`. A single-operation nonlinear solve uses the standard
     writer, with every load it already writes and `load_step` increments.
   - `load_path` histories keep `write_contact_solve` and its load limits, fed by the same plan.
   - A study with a two-node spring assigns the temperature variable to its pipe, beam, bar and cable groups only
     (fact 7). Every other study keeps `TOUT='OUI'`, which facts 4 to 6 show works for shoes.
8. **Discrete supports are created from node groups.** `CREA_POI1` uses `GROUP_NO='GN_<node>'` instead of `NOEUD`
   (fact 8), which fixes every ground spring and support mass. The runtime stays on Code_Aster 18: `NOEUD` takes
   node numbers, so the fault is Tuba passing a node name.
9. **Each support's result comes from where its force is.**
   - Fixed and tied supports: `REAC_NODA` at P, the force on the pipe (fact 3). The structure receives the
     opposite force.
   - Shoes: contact rows with N, VY, VZ, slips and status, whether grounded or attached.
   - Attached springs: `REAC_NODA` at the helper node, where the tie carries the spring force.
10. **Rack loads come from attachments.** The load-path review associates a support with every `rack_bay` group
    that contains its `attached_to` node, and reports the force on the structure. Matching on
    `attachment_points` is removed. `attachment_points` stays, as named nodes to attach to.
11. **The review scene shows attachments.** Support scene objects carry `attached_to` and the chosen form, and the
    viewer draws a line from P to A in `viewer/src/supports.js`.
12. **Unaffected studies stay byte-identical.**
    - A model without rests, springs, support masses, hangers, skewed guides or attachments exports the same
      command and mesh text, so its committed evidence stays current.
    - Evidence is re-solved for `elements-supports-review`, `code-aster-review` and `autorouted-expansion-loop`,
      whose routing adds rests. `native-friction-review` is re-solved only if its study text changes.
    - `support-rack-review` is rebuilt with the pipe on attached friction shoes above the beam.
13. **Language.** `CONTEXT.md` gains two terms:
    - **Attached support**: a support whose restraint acts between its node and another model node instead of a
      point fixed in space.
    - **Shoe**: the one-way contact form every rest compiles to.

## Delivery order

1. **Planner for grounded supports.** Closed types, rests as shoes on every formulation, springs and masses
   created from node groups, skewed guides as one equation and the hanger meaning. Re-solve the evidence this
   changes.
2. **Attachments end to end.** The `attached_to` field through the model, schemas, scripts, patches, fragments
   and the MCP tool; the attached forms; results and rack loads.
3. **Review and example.** Scene metadata, the viewer line, the `CONTEXT.md` terms and the rebuilt
   `support-rack-review`.

## Out of scope

- **Attaching to a point along a member.** The engineer places a node on the member first.
- **Lever arms between P and A.** Also out: one-way or constant-load hangers and local-frame springs.
- **Attached supports outside 1D studies:** pipe-volume and mixed studies, and IFC export or import.
- **Load limits of `load_path` histories** in `write_contact_solve`.
- **Force reporting for ground springs** in the review.
- **Attachment lines in the matplotlib plots** of `tuba/plotting/plots.py`.

## Verification

- **Planner unit tests** without a solver:
  - every type, grounded and attached, maps to its form;
  - refusals: unknown type, self-attachment, missing node, imposed movement on an attached support, friction on a
    non-rest;
  - helper node positions, the nonlinear flag and the temperature group rule.
- **Round trips:** `to_dict` and `from_dict`, generated model scripts, patches with remapped node ids, and both
  schemas.
- **Export tests** pin the command text of every form and assert byte-identical studies for a model without
  affected supports.
- **Opt-in real Code_Aster references** (`TUBA_RUN_CODE_ASTER_INTEGRATION=1`):
  - a cantilever rest carries 3/8 qL on `TUYAU_3M` and on `POU_D_T`, and an uplift case opens the shoe;
  - a ground spring at the cantilever tip gives 325 N and 3.25 mm (fact 8);
  - the rack shoe with pressure and friction slides with friction/normal equal to μ (facts 5 and 6);
  - a tied support's force on the pipe equals `REAC_NODA` at P, and its opposite appears at A (fact 3);
  - an attached anchor between coincident nodes reproduces the shared-node model;
  - an attached skewed guide holds only its direction;
  - an attached spring's relative movement equals force over stiffness, and its force equals `REAC_NODA` at the
    helper node (fact 7);
  - `elements-supports-review` converges with its rest as a shoe beside springs, a mass, a bar and a cable.
