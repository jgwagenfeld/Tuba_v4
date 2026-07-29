# Examples

Examples are labelled by evidence status so geometry, handoff files, and solved engineering results cannot be confused.

## Code_Aster review scene — solved engineering review

**Status: SOLVED / IMPORTED.** The published bundle contains an attested Code_Aster run, imported result tables, analysis mesh, result fields, review records, and scene geometry.

[Open the Code_Aster review scene](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).

The browser performs no engineering calculation. It displays the preserved Python-produced review and scene contracts.

## Imported-component scene — model review

**Status: MODEL REVIEW / NO SOLVER RESULTS.** This bundle demonstrates imported-component geometry, local frames, object selection, and model provenance.

[Open the imported-component model review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo).

## Local examples

Run an example with:

```powershell
.\.venv\Scripts\python.exe examples\<name>.py
```

| Example | Evidence status | Purpose |
| --- | --- | --- |
| `demo.py` | **EXPORT ONLY** | Expansion-loop and end-to-end handoff workflow |
| `autorouting_basic.py` | **EXPORT ONLY** | Basic single-pipe route and review files |
| `autoroute_single_pipe.py` | **EXPORT ONLY** | Candidate route, study export, and report |
| `autoroute_network.py` | **EXPORT ONLY** | Prioritized multi-pipe routing and conflicts |
| `autoroute_expansion_loop.py` | **EXPORT ONLY** | Hot-line U-loop candidates and solver-loop export configuration |
| `operating_state_clash.py` | **MODEL REVIEW** | Operating-state geometry and clash metadata; no solver result claim |
| `future_ready_semantic_workflow.py` | **MODEL / REPORT** | Semantic model, quantities, BOM, rules, and benchmarks |
| `imported_component_mixed_system.py` | **MODEL REVIEW** | Programmatic pipe connected to STEP/STL geometry |
| `realtime_visualization_review.py` | **PRESERVED RESULT INPUT** | Browser scene generation from a preserved result state |
| `code_aster_artifact_review.py` | **SOLVED ARTIFACT IMPORT** | Imports existing Code_Aster artifacts into result and review surfaces |

The export-only examples do not launch Code_Aster. Their `.comm`, `.mail`, and `.export` files are incomplete for engineering evaluation until Code_Aster runs and Tuba imports the result artifacts.

## Autorouting example outputs

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
.\.venv\Scripts\python.exe examples\autoroute_network.py
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Outputs under `routing_reports/` can include `route_report.md`, `route_result.json`, and candidate `study.*` files. Reports explain candidate geometry and scoring. Study handoff files alone are not solver evidence.

See [Autorouting](autorouting.md) for the request fields, grid behavior, solver-loop options, U-loop limit, and acceptance boundary.

## Local postprocessing

After [Setup](setup.md) succeeds, open:

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\10_interactive_postprocessor.ipynb
```

Examples that display stress, reaction, displacement, compliance, or operating-state results must either execute Code_Aster or load real preserved Code_Aster artifacts.
