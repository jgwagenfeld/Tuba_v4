# Examples

Every review below is a piping model that was analysed and kept together with
its evidence. Open one to inspect the geometry, the deformed shape, the
stresses and the support loads.

**[Browse them all in the gallery](https://jgwagenfeld.github.io/Tuba_v4/viewer/)** - no install required.

What a review is backed by is stated on each entry. Anything calculated on top
of that evidence - a piping-code evaluation, a clearance check, a design rule -
is an optional layer a review may or may not carry. None of them is the
reference the review is measured against, and a review without them is not a
lesser review.

## Where does a hot line move, and what does it reach?

**Hot line expansion loop.** A 180 C line routed around equipment, with the expansion loop chosen automatically. Shows how far it grows when hot and where it infringes the clearance it was given around a cable tray.

The line clears the tray cold and reaches it hot: the gap is 150.0 mm cold and
137.6 mm once it expands. What it infringes is the authored 100 mm clearance
band around it, by 6.8 mm, so the markers are warnings flagged
`introduced_by_deformation` - an infringement that exists only in the operating
state. The tray and the band are authored design inputs; the displacement that
closes the gap is imported solver evidence. The band is not the router's
reserved corridor, which additionally reserves the declared insulation.

It also carries an optional ASME B31.3 evaluation.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop) &middot; Evidence: **Results**

## What happens to a pressurised line held at both ends?

**Anchored line with two bends.** The starting point for reading a Tuba review. One line, two anchors, two bends: deflection, wall stress through the pipe section, and the loads arriving at each anchor, all from the same run.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review) &middot; Evidence: **Results**

## Do bars, cables and spring supports survive the trip to the solver?

**Mixed elements and supports.** Pipe, beam, bar, cable and rectangular members in one model, held by spring, rest, anchor and partly-released supports. Evidence that each element and support type is translated and analysed as authored.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=elements-supports-review) &middot; Evidence: **Results**

## What does the analysis actually discretise at a branch?

**Tee junction mesh.** The conformal tetrahedral wall mesh generated for a header and its branch, before anything is solved. Useful for judging mesh quality at the junction where a beam idealisation stops being enough.

The viewer opens on the analysis mesh; the authored pipe tubes remain available
as a layer but start hidden so they cannot obscure the junction.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=gmsh-tee-mesh-review) &middot; Evidence: **Mesh only - no results**

## How does a supplied component join an authored line?

**Imported equipment connection.** A STEP/STL component brought in beside Tuba-authored pipework, with its connection ports, local frames and coupling shown. Geometry review only - nothing here has been analysed.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo) &middot; Evidence: **Model only - no results**

## Does stress concentrate where the branch meets the header?

**Tee junction wall stress.** The same tee, meshed as a solid wall and analysed in 3D. Shows the stress pattern around the junction that a centreline beam model cannot resolve.

FE von Mises is not ASME piping-code stress. The design tubes, analysis skin,
displacement, terminal resultants and stress field stay separately inspectable.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review) &middot; Evidence: **Results**

## What do the supports and the steel underneath actually carry?

**Pipe on a support rack.** A line resting on a framed rack, analysed together. Traces the load from the pipe through each support into the rack members, and flags a span that exceeds the project support-spacing limit.

Two optional layers sit on top of the evidence. Its Compliance tab carries an
ASME B31.3 evaluation, which covers the pipe elements only - B31.3 does not
govern the rack steel, and the evaluator is one code implementation, not the
standard the solver results are judged by. It also carries an engineer-authored
3.5 m support-spacing rule that the 4 m rack span exceeds. Neither layer is a
solver result; both are annotations beside the evidence, not instead of it.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review) &middot; Evidence: **Results**

## Local examples

Run an example with:

```powershell
.\.venv\Scripts\python.exe examples\<name>.py
```

Tuba-owned benchmark and review outputs default to `.build/`. When no Tuba
command is running, remove all ignored Tuba build output with:

```powershell
git clean -fdX -- .build
```

Canonical Code_Aster artifacts under `notebooks/code_aster_results/` are
committed engineering evidence and are not cleanup targets.

| Example | Evidence status | Purpose |
| --- | --- | --- |
| `demo.py` | **MODEL JSON + STUDY HANDOFF** | Writes `piping_model.json` and Code_Aster input files, then stops before results |
| `autorouting_basic.py` | **ROUTE REPORT** | Applies a selected single-pipe candidate in memory and writes route report files; no study export |
| `autoroute_single_pipe.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a route report and exports candidate Code_Aster studies without running them |
| `autoroute_network.py` | **NETWORK ROUTE REPORT** | Writes prioritized multi-pipe routing and conflict reports; no study export |
| `autoroute_expansion_loop.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a hot-line U-loop report and exports candidate studies without running them |
| `operating_state_clash.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises until real result artifacts are available |
| `future_ready_semantic_workflow.py` | **BOM + BENCHMARK; COMPUTED MODEL CHECKS** | Writes a BOM CSV and benchmark summary, then prints quantity, route-cost, load-path, and rule results; no solver study or results |
| `imported_component_mixed_system.py` | **MODEL REVIEW SCENE; OPTIONAL STEP HANDOFF** | Writes a model JSON and geometry-only scene; STEP/STP input can also export an unsolved mixed study |
| `realtime_visualization_review.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises before writing any result-review scene |
| `gmsh_tee_mesh_review.py` | **GMSH MESH REVIEW; UNSOLVED** | Generates a native 3D tee MED mesh and a web scene with optional design geometry and no solver results |
| `code_aster_artifact_review.py` | **SOLVED ARTIFACT IMPORT + REVIEW BUNDLE** | Imports existing Code_Aster artifacts and writes engineering review and web-scene files; `include_compliance` adds the ASME B31.3 table and `clash_clearance_m` adds the operating-state clash check |
| `elements_supports_review.py` | **SOLVED ARTIFACT IMPORT + REVIEW BUNDLE** | Rebuilds the mixed bar/cable/spring model and imports its committed Code_Aster artifacts |
| `code_aster_tee_volume_review.py` | **SOLVED 3D ARTIFACT IMPORT + REVIEW BUNDLE** | Imports the attested native Gmsh/Code_Aster tee study and writes its volume-result review |

No script in this table launches Code_Aster. Rows labelled **STUDY HANDOFF** write `.comm`, `.mail`, and `.export` inputs only; those files remain incomplete for engineering evaluation until Code_Aster runs and Tuba imports the result artifacts. Report-only and model-review rows do not claim to produce solver handoff or result evidence.

## Autorouting example outputs

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
.\.venv\Scripts\python.exe examples\autoroute_network.py
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Default outputs under `.build/routing_reports/` can include `route_report.md`, `route_result.json`, and candidate `study.*` files. Reports explain candidate geometry and scoring. Study handoff files alone are not solver evidence.

See [Autorouting](autorouting.md) for the request fields, grid behavior, solver-loop options, U-loop limit, and acceptance boundary.

## Local postprocessing

After [Setup](setup.md) succeeds, open:

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\10_interactive_postprocessor.ipynb
```

Examples that display stress, reaction, displacement, compliance, or operating-state results must either execute Code_Aster or load real preserved Code_Aster artifacts.
