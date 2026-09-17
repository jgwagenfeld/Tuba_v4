# Examples

The examples below show piping geometry and Code_Aster analyses. Each entry
states whether it contains solver results or model geometry only.

[Example gallery](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

Piping-code evaluations, clearance checks, and project-specific design rules
are included only where stated.

## Thermal expansion

[![Thermal expansion review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop)

A 180 C line routed around equipment with an automatically selected expansion loop. The review shows thermal displacement and clearance violations around a cable tray.

The reported gap decreases from 150.0 mm cold to 131.3 mm in the operating
state. The clearance check reports a 13.2 mm violation of the configured 100 mm
clearance band, flagged `introduced_by_deformation`. The tray and clearance
band are model inputs; displacement comes from imported Code_Aster results.
The router's reserved corridor also includes the declared insulation.

Piping-standard checks are the responsibility of the user.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop) &middot; Evidence: **Results**

## Pipe bends

[![Pipe bends review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

A pressurised line with two anchors and two bends. The review shows displacement, pipe-wall stress, and anchor reactions from one Code_Aster run.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review) &middot; Evidence: **Results**

## Elements and supports

[![Elements and supports review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/elements-supports-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=elements-supports-review)

Pipe, beam, bar, cable and rectangular members in one model, with spring, rest, anchor and partly released supports. The review shows the element and support definitions alongside the imported Code_Aster results.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=elements-supports-review) &middot; Evidence: **Results**

## Cable

[![Cable review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/guyed-mast-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review)

A 12 m tubular mast held by three pretensioned guy cables under a 3 kN side load. The leeward cable goes slack and the two windward ones carry it, which is the redistribution a tension-only member exists to show.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review) &middot; Evidence: **Results**

## Imported components

[![Imported components model review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/imported_component_mixed_demo.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo)

A STEP/STL component placed beside Tuba pipework, showing connection ports, local frames and coupling. This example contains geometry only, with no solver results.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo) &middot; Evidence: **Model only - no results**

## 3D solid

[![3D solid review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review)

A 3D solid quadratic hexahedral tee coupled to 1D TUYAU_3M pipe beam extensions. The review shows kinematic shell-to-solid coupling and stress transition across the junction.

FE von Mises is not piping-code stress. The design tubes, analysis skin,
displacement, terminal resultants and stress field stay separately inspectable.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review) &middot; Evidence: **Results**

## Load transfer

[![Load transfer review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review)

A DN100 line centered in an I-beam rack under distributed line loading, internal pressure and thermal expansion. The review shows ground and element rest shoe reactions, steel deflection, and support spacing.

An engineer-authored 3.5 m support-spacing rule flags the 4 m rack span.
This project rule annotates the solver evidence; it does not establish
compliance with a piping or structural standard.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review) &middot; Evidence: **Results**

## Nonlinear friction

[![Nonlinear friction review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review)

Two disconnected, identical pipes share one nonlinear Code_Aster run and load history. The review compares friction coefficients of 0 and 0.3 through heating, cooling, lift-off and reseating.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review) &middot; Evidence: **Results**

See the [native friction example](examples/native-friction.md) for the contact law, load stages and validation.

## Beam orientation

[![Beam orientation review in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review)

Three identical I-section cantilevers at 0, 45 and 90 degrees in one model. The review compares global and local loading, deformed profiles, and section rotations relative to the original local axes.

[Open this review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review) &middot; Evidence: **Results**

See the [profile-orientation example](examples/profile-orientation.md) for the two load cases, local-axis convention and numerical reference checks.

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

Committed Code_Aster evidence is never a cleanup target: each solved gallery
project keeps its own under `examples/<project>/evidence/<operation>/`, and the
notebooks keep theirs under `notebooks/code_aster_results/`.

| Example | Evidence status | Purpose |
| --- | --- | --- |
| `demo.py` | **MODEL JSON + STUDY HANDOFF** | Writes `piping_model.json` and Code_Aster input files, then stops before results |
| `autorouting_basic.py` | **ROUTE REPORT** | Applies a selected single-pipe candidate in memory and writes route report files; no study export |
| `autoroute_single_pipe.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a route report and exports candidate Code_Aster studies without running them |
| `autoroute_expansion_loop.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a hot-line U-loop report and exports candidate studies without running them |
| `operating_state_clash.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises until real result artifacts are available |
| `future_ready_semantic_workflow.py` | **BOM + BENCHMARK; COMPUTED MODEL CHECKS** | Writes a BOM CSV and benchmark summary, then prints quantity, route-cost, load-path, and rule results; no solver study or results |
| `imported_component_mixed_system.py` | **MODEL REVIEW SCENE; OPTIONAL STEP HANDOFF** | Writes a model JSON and geometry-only scene; STEP/STP input can also export an unsolved mixed study |
| `realtime_visualization_review.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises before writing any result-review scene |
| `code_aster_artifact_review.py` | **SOLVED ARTIFACT IMPORT + REVIEW BUNDLE** | Imports existing Code_Aster artifacts and writes engineering review and web-scene files; `clash_clearance_m` adds the operating-state clash check. The gallery studies below share it |

No script in this table launches Code_Aster. Rows labelled **STUDY HANDOFF** write `.comm`, `.mail`, and `.export` inputs only; those files remain incomplete for engineering evaluation until Code_Aster runs and Tuba imports the result artifacts. Report-only and model-review rows do not claim to produce solver handoff or result evidence.

## Gallery projects

Each published review is a folder under `examples/` holding `model.py`, which builds the model at module level, and `study.py`, which says how it is solved and reviewed: `autorouted-expansion-loop`, `code-aster-review`, `elements-supports-review`, `guyed-mast-review`, `imported_component_mixed_demo`, `native-friction-review`, `pipe-tee-volume-review` (whose `mesh_study.py` also produces the unsolved Gmsh mesh review), `profile-orientation-review` and `support-rack-review`. The gallery build, the solver refresh and the studio all load these same files, so there is no second copy of any model.

```powershell
python -m tuba.cli_studio examples/code-aster-review
python -m tuba.project examples/code-aster-review --output .build/code-aster-review --artifact-dir examples/code-aster-review/evidence/Operating
```

`tuba.project` imports the attested evidence given with `--artifact-dir`, such as the project's own `evidence/<operation>/` folder. Without it, it first solves the study's operations into that folder, reusing evidence that still matches the model and study (`--force` solves again), and builds the review from there.

## Autorouting example outputs

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
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
