# Examples

Follow the piping workflow: author Python, solve with Code_Aster, then inspect the processed results. The first eight examples form a learning path; the later studies cover specialized applications.

[Example gallery](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

To try changes, choose **Build**, edit `model.py`, and click **Update geometry**. That preview is unsolved; engineering results require a new Code_Aster solve. See [browser editing](setup.md#try-a-model-in-the-browser).

## Start here

### Pipe bends

[![Pipe bends in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

A pressurised line with two anchors and two bends. The review shows displacement, pipe-wall stress, and anchor reactions from one Code_Aster run.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review) - **Code_Aster results, 1 load case(s)**

### Load-case preparation

[![Load-case preparation in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/load-case-preparation.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=load-case-preparation)

Two restrained pipe lines solved in four states: Sustained, OperatingHot, Occasional and PressureOnly. Compare Code_Aster results and export signed expansion differences for user-owned checks; no standard or utilization verdict is assigned.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=load-case-preparation) - **Code_Aster results, 4 load case(s)**

### Load transfer

[![Load transfer in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review)

A DN100 line on one I-beam rack bay carries distributed pipe and crossbeam loads, a point force and moment, pressure and thermal expansion. The review follows the loads through the attached frictionless sliding shoes and steel to the ground reactions, with deflection and support spacing beside them.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review) - **Code_Aster results, 1 load case(s)**

### Thermal expansion

[![Thermal expansion in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop)

A 180 C line routed around equipment with an automatically selected expansion loop. The review shows thermal displacement and clearance violations around a cable tray.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop) - **Code_Aster results, 1 load case(s)**

### Nonlinear friction

[![Nonlinear friction in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review)

Two disconnected, identical pipes share one nonlinear Code_Aster run and load history. The review compares friction coefficients of 0 and 0.3 through heating, cooling, lift-off and reseating.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review) - **Code_Aster results, 1 load case(s)**

### Multipipe rack

[![Multipipe rack in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/multipipe-rack.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=multipipe-rack)

Three DN100, DN150 and DN200 lines share a four-bay steel rack. Each has a mid-run fixed shoe and sliding friction shoes, with temperatures of 100, 200 and 300 C and pressures of 1, 2 and 3 MPa. Code_Aster results show pipe-wall stress, displacement and the combined support load path.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=multipipe-rack) - **Code_Aster results, 1 load case(s)**

### Beam orientation

[![Beam orientation in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review)

Three identical I-section cantilevers at 0, 45 and 90 degrees in one model, each loaded by the same 500 N tip force in global -Z. The review compares deformed profiles and section rotations relative to the original local axes, so the difference on screen is the section orientation alone.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review) - **Code_Aster results, 1 load case(s)**

### 3D solid

[![3D solid in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review)

A 3D solid quadratic hexahedral tee coupled to 1D TUYAU_3M pipe beam extensions. Under internal pressure, gravity and a 4 kN out-of-plane load at the free branch end, the review shows 1D pipe-to-3D solid coupling (3D_TUYAU), the stress hot spot where the branch meets the junction, and the branch deflection. FE von Mises is not piping-code stress.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review) - **Code_Aster results, 1 load case(s)**

Line loads and Load transfer share one public lesson: distributed pipe and crossbeam loads, a concentrated force and moment, and the complete load path to ground. The original `examples/line-load-studio` project remains a developer reference.

The thermal-expansion example selects a route geometrically, then reviews its solved operating clearance; it does not rank competing routes by solver results.

## Advanced solved studies

### Braced rack split

[![Braced rack split in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/braced-rack-thermal-split.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=braced-rack-thermal-split)

A DN250 line on a four-bay braced steel rack, anchored once at mid-run. One pipe at 400 C grows at four times the rate of the steel beneath it, so the shoes slide and the end bays take the whole expansion. The review shows displacement, wall stress, the support reactions and the load path the sliding shoes actually carry.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=braced-rack-thermal-split) - **Code_Aster results, 1 load case(s)**

### Cable

[![Cable in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/guyed-mast-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review)

A 12 m tubular mast held by three pretensioned guy cables under a 3 kN side load. The leeward cable unloads and sags while retaining positive tension, and the two windward cables carry most of the load. The review shows nonlinear cable-force redistribution.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review) - **Code_Aster results, 1 load case(s)**

### Plant layout

[![Plant layout in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/hydrogen-plant-layout.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout)

A green-hydrogen facility in plan: an electrolyzer hall, a compressor station, storage bullets and a four-bay pipe rack. Two process lines share the illustrative 3 MPa, 65 C operating state. The review shows displacement, pipe-wall stress and friction shoe reactions from Code_Aster; it does not establish hydrogen-service suitability.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout) - **Code_Aster results, 1 load case(s)**

### Portal frame stability

[![Portal frame stability in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/steel-portal-frame-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=steel-portal-frame-review)

A steel industrial hall with seven portal frames and six bays, solved for gravity and wind in Code_Aster, with the linear buckling eigenvalue analysis of the gravity case. The review shows displacements, reactions, member-end section forces, and the linear buckling factors for the ideal frame under gravity. First-order, imperfection-free reference factors are not a design safety margin or member-adequacy verdict. Von Mises is absent by design: a pipe-free frame has no equivalent-stress field.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=steel-portal-frame-review) - **Code_Aster results, 2 load case(s)**

## Geometry and authoring

### Imported components

[![Imported components in the Tuba viewer](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/imported_component_mixed_demo.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo)

An STL component placed beside Tuba pipework, showing connection ports, local frames and coupling. This example contains geometry only, with no solver results.

[Open this example](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo) - **Model only - no solver results**

## Developer references

- `examples/elements-supports-review`: mixed-element and support translation coverage.
- `examples/line-load-studio`: the original distributed and concentrated load example.
- `examples/rack_bridge_demo`: an elevated rack with regular 3 m bays; it does not establish an 8 m clear roadway.
- `examples/pipe-tee-volume-review/mesh_study.py`: an unsolved mesh diagnostic.

These projects and their solver evidence remain available locally.

## Local examples

After [Setup](setup.md), run a listed script from the checkout root in the
activated environment, replacing `<name>` with its filename without `.py`:

```bash
python -m examples.<name>
```

Tuba-owned benchmark and review outputs default to `.build/`. When no Tuba
command is running, remove all ignored Tuba build output with:

```powershell
git clean -fdX -- .build
```

Committed Code_Aster evidence is never a cleanup target: each solved gallery
project keeps its own under `examples/<project>/evidence/<operation>/`. One
private run remains under `notebooks/code_aster_results/bim_operating`, for the
IFC round-trip notebook; the other four went with the notebooks that read them.

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

Each review or developer reference is a folder under `examples/` holding `model.py`, which builds the model at module level, and `study.py`, which says how it is solved and reviewed: `autorouted-expansion-loop`, `code-aster-review`, `elements-supports-review`, `guyed-mast-review`, `imported_component_mixed_demo`, `native-friction-review`, `pipe-tee-volume-review` (whose `mesh_study.py` also produces the unsolved Gmsh mesh review), `profile-orientation-review`, `steel-portal-frame`, `support-rack-review`, `braced-rack-thermal-split`, `hydrogen-plant-layout`, `line-load-studio`, `load-case-preparation` and `rack_bridge_demo`. The gallery build, the solver refresh and the studio all load these same files, so there is no second copy of any model.

Gallery cards offer a project ZIP when one was built. Extract it and run Studio from the archive root; the ZIP includes the example's shared Python helpers and local assets. It does not contain solver evidence. Some cards also offer a geometry-only IFC file when the exporter can represent the whole native model geometry. Imported CAD, volume meshes and unsupported elements have no IFC link. A downloaded IFC contains no stress or operating-state results.

In Studio, **Exchange** previews an IFC's units, bounds, products and warnings before attaching it as a reference. Attaching or removing a reference changes the displayed scene, not `model.py` or the solver model. Select supported straight pipes and supply explicit material and section values to download a separate, unsolved conversion project; fittings and unresolved geometry cannot be converted. Add loads and supports before a Code_Aster solve. IFC imports require a local Studio session and the optional `tuba[ifc]` installation. In the public gallery, **Exchange** provides downloads; browser geometry editing is available separately in **Build**.

Contributors can run `uv run python scripts/ifc_exchange_browser_smoke.py` after installing the IFC extra, viewer dependencies and Playwright Chromium. This opt-in check uses a temporary Studio project to upload, preview, attach, convert, export and remove a real IFC; it executes the downloaded conversion project and checks that authored source remains unchanged.

```powershell
python -m tuba.cli_studio examples/code-aster-review
python -m tuba.project examples/code-aster-review --output .build/code-aster-review --artifact-dir examples/code-aster-review/evidence/Operating
```

`tuba.project` imports the attested evidence given with `--artifact-dir`, such as the project's own `evidence/<operation>/` folder. Without it, it first solves the study's operations into that folder, reusing evidence that still matches the model and study (`--force` solves again), and builds the review from there.

## Study cards and reference figures

Solved evidence is a pile of artifacts, and the generated `study.comm` and `study.export` are text only Code_Aster reads. Each project therefore also carries a **study card** under `reference/<operation>/`: a page that states what was solved, lists the Code_Aster commands the generated command file actually calls, shows the export unit map, and records the artifact hashes and the evidence verdict, all read back out of the evidence.

```powershell
python scripts/build_study_cards.py                # write the cards and figures
python scripts/build_study_cards.py --check        # fail when a committed card is stale
```

Cards live in `reference/` rather than beside the evidence because evidence promotion removes every file a solve did not attest — a card kept inside `evidence/` would be deleted by the next solve. `--check` is the CI form and is exercised by the test suite.

A project can also commit **reference figures**: a `reference_series.py` next to `model.py` exposes `reference_figures(project_root, evidence_folder)` and returns the solved series beside an analytical one, drawn as a deterministic SVG with no plotting dependency. `examples/profile-orientation-review` is the worked case — its two figures put the Code_Aster beam solution against closed-form cantilever beam theory along all 97 mesh stations and across all three section rolls, agreeing to 2.5e-12 m.

Both are finite-element comparisons. A card and a figure describe what the solver was given and returned; neither is a code check, a utilization or an acceptance verdict, and Tuba evaluates no standard.

## Load-case preparation

`examples/load-case-preparation` solves **Sustained**, **OperatingHot**,
**Occasional** and **PressureOnly** with Code_Aster. Its review includes all four
states and a CSV of signed element-end forces, including the hot-minus-sustained
expansion difference. No standard or utilization verdict is assigned; pressure
design remains a separate user calculation. See the project's `README.md` for
load assumptions, component conventions and check inputs.

```powershell
python -m tuba.cli_studio examples/load-case-preparation
python -m tuba.project examples/load-case-preparation --output .build/load-case-preparation
```

## Fluid contents

`examples/fluid_contents.py` solves one insulated cantilever in Empty, Operating
(800 kg/m3 at 1.0 MPa) and Hydrotest (1000 kg/m3 at 1.5 MPa) states using
Code_Aster `TUYAU_3M`. The review separates input masses and imported results for
all three cases. No review is written if any solve fails.

```powershell
python -m examples.fluid_contents
python -m tuba.visualization.viewer .build/fluid-contents/review --open
```

The example requires a configured Code_Aster runtime and runs locally; it is
not a prebuilt gallery card. See [fluid contents by operation](modeling.md#fluid-contents-by-operation)
for selectors, units and unsupported combinations.

## Autorouting example outputs

```bash
python -m examples.autoroute_single_pipe
python -m examples.autoroute_expansion_loop
```

Default outputs under `.build/routing_reports/` can include `route_report.md`, `route_result.json`, and candidate `study.*` files. Reports explain candidate geometry and scoring. Study handoff files alone are not solver evidence.

See [Autorouting](autorouting.md) for the request fields, grid behavior, solver-loop options, U-loop limit, and acceptance boundary.

## Local postprocessing

After [Setup](setup.md) succeeds, open:

```bash
jupyter lab notebooks/04_visualization_gallery.ipynb
```

Examples that display stress, reaction, displacement, compliance, or operating-state results must either execute Code_Aster or load real preserved Code_Aster artifacts.
