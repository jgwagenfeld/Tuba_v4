# Piping review isometry export

Generate dimensioned A3 SVG sheets, a printable HTML set, and CSV/JSON schedules
from an authored Tuba piping model:

```sh
python -m tuba.reporting.isometry path/to/project --output .build/isometry-review
```

The project must contain `model.py`. It executes through Tuba's existing project
loader. The exporter does not modify the model, create `study.py`, launch MCP or
run Code_Aster. No additional drawing dependencies are required.

```python
from tuba.reporting.isometry import write_isometry

manifest = write_isometry(model, "drawings", units="mm", precision=1,
                          elements_per_sheet=8, orientation=0, revision="A")
```

Open `index.html` locally or through an HTTP server. The HTML embeds the vector
sheets, links to individual SVGs and schedules, and supports browser printing at
A3 landscape. Native PDF/DXF generation is not implemented.

Optional CLI arguments:

- `--route NAME` (repeatable): select authored routes; unassigned elements use
  `unrouted`. Connections to omitted elements remain explicit.
- `--units mm|m|in` and `--precision 0..6`: displayed dimensions and coordinates.
  Machine-readable values in the manifest/CSV retain explicitly named SI units.
- `--elements-per-sheet 1..8`: detail-sheet density, grouped by route and native
  element order. Reduce it if labels cannot fit.
- `--orientation DEGREES`: rotation about global Z before isometric projection;
  use it to avoid an end-on view. Geometry is never moved in the model.
- `--revision TEXT`: user-supplied revision label; approval stays unissued.

Output must be a new or empty directory. Geometry validation and SVG layout run
before files are written. Repeated exports of an unchanged model/configuration
produce identical bytes. Output names are generated sheet IDs, never model text.

## Content and interpretation

Each sheet uses monochrome linework, a large drawing field, a compact right-hand
segment schedule and a bottom-right title block. Long straight runs use parallel
offset dimension lines with extension lines and arrows. Short or congested runs
use leader callouts; bends show radius/angle and tabulate true arc length.

Sheets include a coordinate reference, point/native-node mapping, true
centerline dimensions, pipe OD/wall, bend radius/angle, elevation changes,
support/tee references, sheet continuations and a model fingerprint. `P1` etc.
are local drawing points; the schedule maps them to native node IDs. Reference
coordinates for the first/last authored endpoints are printed on the sheet.
All node coordinates are available in each HTML sheet's expandable table and
in the manifest. HTML route links jump to the first sheet of each route.
Dots identify native nodes; a crossing without a dot is not a connection.
`S` means a native restraint, `A` a source support annotation, `T` an explicit tee.
An asterisk marks an element carrying a geometry caveat or placeholder note.

`manifest.json` carries full topology, 3D points, attributes, sections, materials,
native support settings and all node-level `drawing_support` assignments, even
multiple callouts at one node. CSVs contain segment properties, native restraints
and source support annotations separately. Spreadsheet formula-like source strings
are prefixed with an apostrophe in CSV; JSON preserves exact strings.

Support states are ordered X/Y/Z/RX/RY/RZ. Counts do not verify source-to-restraint
reconciliation. Defaults in a native support are exported as model values; the
exporter cannot establish whether a source drawing specified them.

This is an **UNSOLVED REVIEW**, with no standards-compliance or fabrication claim.
Only native straight pipes and canonical pipe bends are currently supported;
other selected element types fail explicitly. Tee records are annotated at nodes;
they do not establish manufacturer's fitting envelopes. Diameter changes preserve
each segment's section and are not promoted into explicit reducer components.

The segment schedule is not a manufacturing BOM: it does not count mesh segments
as stock parts or derive cut lengths, welds, fitting takeouts or support hardware.
Straight lengths are node-to-node distances; bend lengths are arc lengths, not
chords. Page scaling does not change dimensions. Dense sheets may require fewer
elements or another orientation; long side notes indicate overflow and refer to
the full manifest. Sheet splitting is deterministic, not spool optimization.

The layout was informed by Autodesk's published
[isometric drawing workflow](https://help.autodesk.com/cloudhelp/2022/ENU/Plant3D-UserGuide/files/GUID-3A114B81-47AF-4E0C-B314-BA4969D9217A.htm)
and [dimension configuration](https://help.autodesk.com/cloudhelp/2022/ENU/Plant3D-UserGuide/files/iso_style_tb_dims_configure_to.htm):
separate drawing/table areas, dimension offsets and explicit dimension anchors.
These are design references, not evidence of ISO conformance. This version keeps
the existing eight-element detail-sheet limit; automatic spool boundaries,
schematic shortening and project-specific fitting/support symbols are not implemented.

Rendering checks do not resolve source revision conflicts, open ties, clashes or
incomplete engineering inputs. Engineering evaluation still requires the native
Tuba -> real Code_Aster -> processed-result workflow.

Run the focused checks with `python -m pytest tests/test_isometry_export.py -q`.
