# Retained hot-line search

This example builds an authored piping model, solves its **Sustained** and **Hot**
operations with real Code_Aster, checks the imported results, and retains every
trial. It requires a working Code_Aster runtime. Exported input files alone do
not establish an engineering result.

The endpoint span is 8 m at elevation 3 m. The DN80 steel line carries hot oil
at 1.2 MPa, with an 800 kg/m³ contents density and 50 mm mineral-wool insulation.
The reference temperature is 20 °C; the hot operation is 180 °C. A procedural U
loop varies in width and depth; an optional middle guide varies its restraint.
The grid has 12 proposals and a maximum of 24 fresh operation calls.

Both equipment nozzles are fixed. Shoes at X=1.5 and X=6.5 m sit on the declared
rigid rack crossbeams. The rack is an ideal ground boundary; its elastic response
is omitted. Ideal shoes hold lateral and vertical translation bilaterally and
allow axial translation, so lift-off and friction are omitted. The optional
midpoint guide uses a matching rigid bracket.
These supports appear in the authored model, solve and displayed review.

The requirements are fixed in `study.py` before qualification:

| Requirement | Scope | Limit |
| --- | --- | --- |
| Structural/cold-model gate | Complete model | Native verification must pass |
| Cold clearance | Insulated model, all declared obstacles | 0.03 m |
| Operating clearance | Sustained and Hot, physical deformation scale 1 | 0.03 m around the insulation |
| Pump and tie-in force magnitude | Translational nozzle reactions, both operations | 10,000 N each |
| Loop midpoint displacement magnitude | Translation, both operations | 0.10 m |
| Native evidence gate | Each required operation | Verified, intact Code_Aster attestation |

The force limits are illustrative equipment requirements, not manufacturer
allowables. This example has **no piping-standard compliance evaluator**. Its
feasibility statement covers the listed checks and modelling assumptions only.
A production study requiring standard compliance must declare a
`user_evaluator` check and supply `evaluate_search(context)`; missing output
remains unknown and prevents selection.

From the repository checkout, using its existing Python environment:

```powershell
python -m tuba.solver.code_aster_doctor --check
python -m tuba.search run examples/piping-search --run-dir D:/tuba-runs/Tuba_v4/my-search
python -m tuba.search inspect --run-dir D:/tuba-runs/Tuba_v4/my-search
python -m tuba.search inspect --run-dir D:/tuba-runs/Tuba_v4/my-search --candidate C0005
python -m tuba.search export --run-dir D:/tuba-runs/Tuba_v4/my-search --output D:/tuba-runs/Tuba_v4/my-search/exports/replay
python -m tuba.search review --run-dir D:/tuba-runs/Tuba_v4/my-search --candidate C0005 --output D:/tuba-runs/Tuba_v4/my-search/exports/candidate-C0005
python -m tuba.visualization.viewer D:/tuba-runs/Tuba_v4/my-search/exports/candidate-C0005 --open
```

Use the candidate IDs actually shown by inspection. A review contains native
solver artifacts, result fields, recorded constraint issues and a constraint
table in `report.html`. A rejected candidate's check names its operation, state,
target, measurement/limit or collision, and evidence file. Unsolved candidates
can have a geometry preview, with no solver result fields.

The archive owns `history.sqlite3`, frozen source, candidate parameters/geometry,
permanent solver attempts and their SHA-256 inventories. Rejected, failed and
interrupted evidence is retained. The original project source, its `evidence/`
and its staging directory are not changed by search. Put histories outside
tracked source and preserve them as engineering data.

`run ... --resume` requires the exact frozen source/configuration. For a changed
study, start a new directory with `--parent-run <old-run>`; only verified evidence
for identical solver inputs can be reused, and checks are always recomputed.
Within a run, reuse references the original output. Between separately owned
runs, attested evidence is copied once into shared assets per solver identity.

The replay JSON and JSONL preserve proposal/event order, ancestry, all decisions,
failed/unexecuted checks, scoped result IDs and artifact availability. A replay
manifest references its retained archive; moving the manifest alone is not a
self-contained handoff. Candidate review bundles follow the existing complete
web-bundle contract. Interactive history playback and film export are later
roadmap milestones.

Real qualification is opt-in and never substitutes recorded fixtures:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = '1'
$env:TUBA_SEARCH_QUALIFICATION_DIR = 'D:/tuba-runs/Tuba_v4/fresh-qualification'
python -m pytest tests/integration/test_piping_search_code_aster.py -q
```

See [the search guide](../../docs/content/piping-search.md) for configuration,
failure behavior and the qualified example's measured results.
