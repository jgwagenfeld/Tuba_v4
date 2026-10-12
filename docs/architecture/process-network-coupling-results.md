# Serial process-network coupling qualification

Validated locally on 2026-10-12. This qualifies the bounded example in the
[process-network guide](../content/process-networks.md), not arbitrary equipment,
networks or piping-code compliance.

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
