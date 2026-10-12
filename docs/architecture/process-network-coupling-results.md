# Serial process-network coupling qualification

Validated locally on 2026-10-12. This qualifies the bounded example in the
[process-network guide](../content/process-networks.md), not arbitrary equipment,
networks or piping-code compliance.

The initial sections retain the OpenModelica qualification. The final section
records the fresh pandapipes qualification for the new default backend.

## Three retained layouts

Each layout delivers 10 kg/s of the selected constant-property water medium.
The operating temperature is 60 °C, mechanical reference 20 °C, sink pressure
300 kPa absolute, and external pressure 101.325 kPa. Endpoints, connectivity,
four bends and two anchors remain fixed; bore and offset length vary.

The declared limits are 3 m/s velocity, 600 kPa maximum source pressure,
300 kPa minimum sink pressure, 10 kg/s minimum delivery, 20 kN support force,
50 mm displacement at authored nodes and 10 mm bare-pipe clearance.

| Candidate | Bore | Length | Velocity | Total pressure drop | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Small bore, 1 m offset | 52.48 mm | 9.885 m | 4.643 m/s | 103.286 kPa | Rejected: velocity exceeds 3 m/s; Code_Aster not invoked |
| Larger bore, 1 m offset | 77.92 mm | 9.885 m | 2.106 m/s | 18.305 kPa | All declared checks pass; retained |
| Larger bore, 3 m offset | 77.92 mm | 13.885 m | 2.106 m/s | 20.529 kPa | Rejected: authored-node displacement reaches 100.206 mm, above 50 mm |

Both larger-bore cases were actually evaluated with Code_Aster TUYAU_3M.

| Code_Aster measurement | 1 m offset | 3 m offset |
| --- | ---: | ---: |
| Maximum displayed displacement, including solver nodes | 17.456 mm | 100.905 mm |
| Maximum support force magnitude | 801.383 N | 1,092.856 N |
| Maximum support moment magnitude | 1,243.562 N m | 2,491.743 N m |
| Peak FE von Mises stress from TUYAU subpoints | 95.107 MPa | 102.901 MPa |

These FE stresses are results for the specified idealization, not a
piping-standard stress check. The longer offset increases self-weight and span
flexibility in this two-anchor arrangement; greater route length does not by
itself improve the combined design.

Each scene includes measured fluid velocity, endpoint-derived mean absolute
pressure and pressure drop, and bulk temperature. The solved scenes also carry
both supports' force/moment vectors, six internal-force components, displacement
and FE stress. Rejected layouts and their raw evidence remain available.

## Independent numerical checks

The three hydraulic pressure drops agree with an independent Darcy-Weisbach /
iterated Colebrook calculation plus the declared local losses within **0.008%**.
This checks the implemented constant-property correlations and dimensions;
it does not qualify the illustrative bend/restriction coefficients as equipment
data. A separate 3 m straight-pipe probe agrees in distributed friction within
0.014%, and its K=5 local-loss term matches to floating-point precision.

The real integration test
[`test_code_aster_process_coupling.py`](../../tests/test_code_aster_process_coupling.py)
uses real Modelica measurements on a 3 m cantilever and three real Code_Aster
operations. It checks the mapped case against a separately authored native
pressure/temperature/density operation and independent references:

| Quantity | Reference | Code_Aster |
| --- | ---: | ---: |
| Vertical support reaction from steel plus liquid weight | 800.487558281 N | 800.487558277 N |
| Support bending moment | −1,200.731337422 N m | −1,200.731337416 N m |
| Free thermal expansion, (αΔTL) | 1.440000000 mm | 1.440000014 mm |

All reported original-node displacement/reaction components agree with the
native operation within the test's declared tolerances. The thermal reference
isolates thermal expansion; the mapped/native comparison includes pressure,
temperature and gravity together. Pressure uses the evaluated element-end
arithmetic mean minus external pressure; no separate fluid-momentum forces are
added.

Portable tests cover graph/association validation, geometry freshness, raw
artifact changes, compiler failures, conservation and mapping contracts.
Search tests cover fluid rejection before FEA, failure retention, immutable
candidate IDs, concurrent geometry edits, and self-contained fluid evidence in
reviews. Viewer tests cover selecting the correct hydraulic attempt/field and
keeping its provenance separate from structural results.

## Retained evidence

Local evidence root:
`D:/tuba-runs/Tuba_v4/process-coupling-20261012/`.

- `campaign-1/`: native immutable candidate history, raw Modelica and Code_Aster
  studies, source snapshot, mapping records and measured checks.
- `validation.json`: verified archive inventories, independent friction/loss
  references and values summarized above.
- `replay/`: review bundles with their fluid and structural artifacts.
- `film-readable/index.html` and `film-readable/film.webm`: 24-second iteration
  film at 1600 x 900, with one eight-second view per candidate.
- `film-readable/film.json`: captured viewer identity, selected fields, support
  glyph components, frame/movie hashes and browser diagnostics.
- `qualification-tests/completed/`: successful real integration test inputs,
  results, `qualification.json` and mapping receipt.

All three captured frames were visually inspected. The first displays measured
velocity and nine pipe-local failure markers, with structural results explicitly
unevaluated. The solved frames display FE stress, force arrows and moment arcs
at both supports; the longer-offset frame also marks its four displacement
failures. Browser capture completed without page errors. All 80 focused viewer
tests passed on the final source.

Runtime: OpenModelica `v1.27.0-dev-574-g5a19131b33`, MSL 4.1.0; Code_Aster through
the existing Ubuntu WSL runtime. Exact solver identities and versions remain in
the execution records. No remote deployment or controlled LLM-provider
benchmark is implied by this local qualification.

## DEXPI 2.0.1 import qualification

The next local qualification on 2026-10-12 imports the unmodified official
reference P&ID from DEXPI release commit
`eef0f0c6e8edfe84582e7a45d109c396bdc544f8`. The pinned fixture passed its pinned
official XSD. Attribution, source URLs and byte hashes are in the
[fixture record](../../examples/process_network/dexpi_reference/README.md).

Selected line `47122` / `PipingNetworkSegment2` contains `Pipe2`, from pump
`P4711` at `Nozzle2` / `PipingNode3` to heat exchanger `H1007` at `Nozzle3` /
`PipingNode4`. The adapter preserves these identities and records the other
292 identified objects as outside the selected model. Physical layout and
operating data are separately authored; the demo substitutes water for the
uninterpreted `MNb` fluid code and does not simulate pump or heat-exchanger
behavior. Both layouts keep the source DN80 and both anchor endpoints fixed.

Two new OpenModelica and Code_Aster evaluations produced:

| Measurement | 1 m offset | 3 m offset |
| --- | ---: | ---: |
| Actual centerline length | 9.885 m | 13.885 m |
| Fluid velocity | 2.106 m/s | 2.106 m/s |
| Pressure drop across the imported pipe span | 7.262 kPa | 9.486 kPa |
| Peak displayed displacement, including solver nodes | 17.457 mm | 100.905 mm |
| Maximum support force magnitude | 801.393 N | 1,092.856 N |
| Maximum support moment magnitude | 1,243.565 N m | 2,491.743 N m |
| Peak FE von Mises stress | 95.109 MPa | 102.903 MPa |
| Declared-check outcome | Retained | Rejected: four authored nodes exceed 50 mm |

The imported span contains no external restriction. Its pressure drop therefore
excludes the illustrative K=5 restriction in the earlier authored circuit.
Independent Darcy-Weisbach/Colebrook plus declared bend-loss references agree
within **0.012%**. Source topology/associations remain identical across the route
edit; the measured length and bound-result fingerprints change.

Validation verified every sealed attempt inventory, rechecked the final importer
against both retained sources, and checked the detached review's source bytes,
assumptions, attribution and structural fields. Final importer/example tests
passed 61 cases, including contradictory nominal-size metadata; 32 native
workflow/export/replay tests and the additional attribution check also passed.
These are focused checks, not a full repository test run.

Evidence is retained at `D:/tuba-runs/Tuba_v4/dexpi-import-20261012/`:
`campaign-1/`, its `replay/`, `validation.json`, the pinned schema-validation
receipt under `reference/`, and the iteration film under `film/`. The prior
viewer build is reused because viewer source did not change in this milestone.

The 16-second, 1600 x 900 film contains one eight-second view per layout. Both
frames were visually inspected: FE stress colours use a shared legend, both
supports show force arrows and moment arcs with measured labels, and the
rejected layout marks its four displacement failures in red. Browser capture
completed without page errors; the frame and movie hashes match `film.json`.

## Pandapipes default-backend qualification

On 2026-10-12, pandapipes 0.15.0 evaluated the same three authored layouts and
transferred their verified loads into real Code_Aster TUYAU_3M operations. The
default command ran with `TUBA_OMC` deliberately pointing to a nonexistent
compiler. OpenModelica was neither required nor invoked.

| Candidate | Velocity | Total pressure drop | Outcome |
| --- | ---: | ---: | --- |
| Small bore, 1 m offset | 4.643 m/s | 103.273 kPa | Rejected before FEA: velocity exceeds 3 m/s |
| Larger bore, 1 m offset | 2.106 m/s | 18.304 kPa | All declared checks pass; retained |
| Larger bore, 3 m offset | 2.106 m/s | 20.527 kPa | Rejected: four authored nodes exceed 50 mm displacement |

The two solved layouts retain maximum displayed displacements of 17.456 and
100.905 mm, support-force magnitudes of 801.383 and 1,092.856 N, support-moment
magnitudes of 1,243.562 and 2,491.743 N m, and peak FE von Mises stresses of
95.107 and 102.901 MPa, respectively. Their scenes contain all six internal-force
components and force/moment vectors at both supports. These are measured FE
results for the declared model; they do not establish piping-code compliance.

Independent Colebrook/Darcy-Weisbach calculations, with each declared K loss
counted once, reproduce the campaign pressure drops. Additional rising and
falling routes at different absolute elevations pass independent segment-level
friction, bend/restriction loss and hydrostatic checks at tolerances of
`rel=1e-6, abs=1e-4 Pa`. These tests include the conversion between Tuba's
absolute Pa and pandapipes' gauge bar and height-dependent atmospheric pressure.

Comparison with the earlier **archived** OpenModelica qualification gives less
than 0.013% difference in pressure drop and unchanged rounded velocities and
outcomes. This was not a fresh OpenModelica run. The solvers use slightly
different Colebrook correlations and gravity constants, recorded in provenance;
bit-for-bit equality is not expected.

The real cantilever qualification passed three Code_Aster operations: mapped
hydraulic loads, a separately authored native reference and isolated thermal
expansion. It measured 800.487558277 N vertical reaction,
-1,200.731337416 N m bending moment and 1.440000014 mm free thermal expansion,
matching the independent references above. All original-node displacement and
reaction components matched the native operation within the test tolerances.

The adapter is restricted to forward, steady, isothermal, fully filled serial
water with pipe Reynolds number at least 4,000. Density 995.586 kg/m³ and
viscosity 0.001 Pa s remain explicit constant assumptions. Bulk temperature is
prescribed; no heat-transport, transient, pump-curve or branched-network model
is qualified here. Optional Python dependencies replace the separate hydraulic
compiler installation, while Code_Aster remains required for structural results.

Retained evidence: `D:/tuba-runs/Tuba_v4/pandapipes-20261012/`:

- `campaign-1/` and its `replay/`: three sealed attempts, raw pandapipes inputs,
  output tables, dependency hashes, convergence logs and actual Code_Aster artifacts.
- `validation.json`: verified inventory hashes, independent hydraulic references,
  structural field coverage and the hashed archived OpenModelica comparison.
- `qualification/real-tests-2/`: the successful real integration cases and their
  `qualification.json` receipts; `qualification/pytest-real-2.txt` reports three passed.
- `film/`: the iteration capture, its player and frame/movie provenance.
- Focused checks: 76 backend/workflow/film Python tests, 57 network/example Python
  tests and 75 viewer tests passed. The full repository suite was not run.

The 24-second, 1600 x 900 film contains three visually inspected frames: nine
velocity-failure markers on the first layout, force/moment glyphs at both
supports on each solved layout, and four displacement-failure markers on the
last. Browser capture has no page errors. Frame/movie hashes match, and decoded
seeks at 1, 9, 17 and 23 seconds reproduce the corresponding captured views.

The additional installed distributions occupied about 208 MB in the reused
Python environment, excluding the shared download cache. Structural-only users
do not require the optional `process` extra. No push, deployment or controlled
LLM-provider benchmark is implied.

## Tagged process schematic review

On 2026-10-12, the shared process graph was projected into a tagged SVG in the
existing web review. The diagram preserves component/port IDs, connections,
measured pipe route associations and explicit hydraulic check IDs. It displays
recorded pandapipes flow, absolute pressure and velocity. The SVG download is
editable as a vector drawing; edits do not update the engineering model.

A fresh two-candidate run used pandapipes with `TUBA_OMC` pointing to a
nonexistent compiler. The small bore was rejected at **4.643 m/s** against the
3 m/s limit before structural evaluation. Both its routed pipe and external
restriction display their own failure. The larger bore measured **2.106 m/s**,
passed the declared checks and completed a real Code_Aster operation. This
checks the linked drawing against current solver artifacts; the earlier
three-layout qualification remains the broader numerical reference above.

Browser checks verified selection of the pipe's nine actual mechanical
elements, empty structural selection for source/sink/external restriction,
measured component pressure endpoints, keyboard activation and focus,
candidate switching without inherited selection, reverse route selection, and a real SVG download with
parseable identity metadata. Both the linked review and the failed drawing
were visually inspected. Legacy scenes hide the new panel and mismatched bound
fingerprints refuse the drawing/download. No browser page errors occurred.
Standalone checks observed only existing optional Studio API probes returning
404 from the static review server.

Focused validation passed 27 backend/workflow tests, 99 viewer tests and six
documentation tests. Three generated-site checks were skipped because the site
was not rebuilt. These are scoped checks, not a full repository suite.
Re-export enriches the derived scene while retaining the sealed attempts and
raw hydraulic review bytes.

Evidence is retained under
`D:/tuba-runs/Tuba_v4/process-schematic-20261012/`: `campaign-1/`,
`replay-final/`, the inventory validation receipt, `browser-validation.json`,
`water-circuit.svg`, `rejected-circuit.svg` and their screenshots. The active
vision and next stages are in the [process review roadmap](process-model-review-study.md).

This milestone supports the existing serial graph. It does not add instrument
or control semantics, graphical model editing, DEXPI export or piping-code
certification.

## Instrumented P&ID review

On 2026-10-12 the shared network gained explicit equipment, instrument taps and
electrical signal declarations. The authored water example declares supply and
receiving tanks, a control valve at the existing illustrative fixed-K operating
point, PT-101 at the pipe inlet, FT-101 at its outlet and the FT-101 -> FIC-101 ->
FCV-101 control intent. Equipment remains represented by boundary/fixed-loss
hydraulic approximations and stays outside the mechanical pipe model. No tank
level, valve motion, controller output or feedback response is simulated.

A fresh pandapipes run, with OpenModelica deliberately unavailable, rejected the
small bore at **4.643 m/s** against the 3 m/s limit. Its P&ID marks the pipe and
valve failures while retaining PT-101's calculated **403.273 kPa absolute** and
FT-101's **10 kg/s**. The larger bore measured **2.106 m/s** and passed the declared
checks; PT-101 displays **318.304 kPa absolute**, its exact inlet endpoint value.
The larger candidate completed real Code_Aster evaluation and retains stress,
all internal-force components, displacement, support forces/moments and TUYAU
fields. The hydraulically rejected candidate has no structural result fields.

The P&ID is rendered from the same verified graph inside the existing review.
**Open P&ID** provides a full-size drawing; **Download SVG** exports its symbols,
connections, tags, calculated values and identity metadata. Pipe and transmitter
selection links to nine real mechanical elements. Tank/valve/controller selection
has no fabricated structural association. Controllers display their declared
signal path and explicitly have no calculated output.

Validation passed 121 backend/network/workflow tests, 14 viewer tests and 14
example/documentation checks. Real-browser checks cover exact-port values,
linked and reverse selection, keyboard activation/focus, dialog dismissal,
candidate reset and downloaded SVG parsing. Accepted and rejected drawings
were visually inspected after correcting tap-line label clearance. Browser-only
response checks preserve the old schematic without P&ID declarations and refuse
missing transmitter taps, duplicate ports and explicit null definitions. No
browser page or console errors occurred. Sealed inventories and native
Code_Aster publication identities verify. Two old bound networks round-trip
unchanged, and absent P&ID definitions retain old fingerprints. These are focused
checks; the full repository suite and published documentation site were not run.

Evidence: `D:/tuba-runs/Tuba_v4/process-pid-20261012/`, including `campaign-1/`
and its replay, `validation.json`, browser receipts, accepted/rejected P&ID SVGs
and screenshots. The [implementation plan](process-pid-implementation-plan.md)
records the interface, limits and next work. No new solver capability or
standards-compliance qualification is implied by the equipment symbols.
