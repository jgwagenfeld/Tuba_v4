# Imported component: a demo that actually couples

Date: 2026-09-09
Status: accepted

## Problem

The gallery entry `imported_component_mixed_demo` leads with the question
"How does a supplied component join an authored line?" and answers it with
geometry that joins nothing.

The asset is `examples/assets/imported_component_demo.stl`: a 591-byte,
four-facet tetrahedron. On screen it is a grey pyramid beside a blue pipe, and
it reads as a bug. Three separate gaps produce that.

**1. STL never reaches the mesh.** `_write_med` branches on
`_has_existing_step_assets` (`tuba/solver/mixed_study.py:106`), which requires
`source_format` in `{STEP, STP}`, the matching suffix, and the file on disk.
STEP takes `_write_med_with_gmsh`: `occ.importShapes`, a physical group on the
solid volume, `mesh.generate(3)` — a real tet mesh. STL falls to
`_write_med_with_meshio`, which writes the pipe centreline as `line` cells and
the solid region and port face groups as *empty arrays*:

```python
cell_sets[name_map[region.mesh_group]] = [np.array([], dtype=int)]   # :210
cell_sets[name_map[port.face_group]]   = [np.array([], dtype=int)]   # :212
```

The `.comm` still emits `LIAISON_ELEM(GROUP_MA_1=<port face group>)` against a
group that exists by name and holds zero cells. The component has no presence
in the MED at all — no volume, no faces, no contact, no mass. It is not meshed
and it is not an obstacle. It exists only in `scene.json` as
`mesh_vertices_local`/`mesh_faces`, for the viewer to draw. It is a picture.

**2. Nothing anchors the port to the asset.** `_validate_ports`
(`tuba/validation.py:377`) checks that the owner resolves and that a confirmed
port carries a `face_group` string. `connect_pipe_to_port`
(`tuba/model.py:715`) checks pipe `OD/2` against port radius within
`max(1 mm, 2%)` — the only geometric check anywhere in the path. Nothing checks
that the port position lies on, or anywhere near, the asset that owns it. Port
position is user-asserted metadata against a placement nobody cross-checks.

And the detector that would otherwise supply it is not trustworthy either:
`_detect_port_candidates` proposes a candidate for *every* boundary face,
derives radius from a bounding box, and hardcodes `axis = [1.0, 0.0, 0.0]`
(`step_analysis_importer.py:150,161`). On a cylinder lateral that radius is half
the face length. This is why the demo hand-writes the whole port and labels the
importer `manual-port-metadata` — the automatic path cannot be relied on, so the
example quietly stopped using it.

**3. The viewer names none of it.** The builder emits four layer families —
`imported_components`, `mixed_ports`, `mixed_couplings`,
`local_coordinate_axes` (`tuba/visualization/builders/_imported.py:96,140,171,216`).
None appears in `BODY_SPECS` or `OVERLAY_SPECS` (`viewer/src/bodies.js:29,74`).
They are drawn, and named nowhere in the UI. The viewport key
(`viewer/src/app.js:1267`) exists for exactly this job — "what is that mark" —
and covers only bodies, load case, and force/reaction vectors. The gallery
card's `question` and `summary` are shown on the picker and then discarded on
entry to the scene.

## Objective

The entry either demonstrates a real coupling or leaves the gallery. It stays,
as STEP.

`AGENTS.md` governs what "real" may claim here: export-only paths are
diagnostic surfaces, and any export-only example stays labeled incomplete until
Code_Aster has solved it and results are imported. **This design does not
change that.** `MixedCodeAsterStudyExporter.RESULT_STATUS` stays `export_only`,
`RUNTIME_BLOCKER` stands, and the scene keeps its
`publication.model_review.no_solver_results` diagnostic.

What changes is that the coupling becomes *structurally* real: a meshed volume,
a genuine port face carrying a gmsh face tag, and a `LIAISON_ELEM` whose
`GROUP_MA_1` names a non-empty group.

## Decisions

1. **The demo asset ships as STEP.** Only STEP reaches gmsh. An STL that looks
   more like real equipment makes the demo *more* misleading, not less — the
   better the connection looks, the more it implies a coupling that contributes
   nothing.
2. **The connection face is a bored nozzle stub end, not a flange.** A flange
   breaks the OD check: `_detect_port_candidates` derives radius from a bounding
   box (`max(dx,dy,dz)/2`, `tuba/geometry/step_analysis_importer.py:150`), which
   on a Ø0.20 flange face is 0.10 against a required 0.05, and
   `connect_pipe_to_port` raises. A stub of OD 0.10 / bore 0.084 has an annular
   end face 0.10 across, giving a detected radius of exactly pipe `OD/2`. The
   check passes on genuinely detected metadata rather than a hand-asserted
   number.
3. **Detection derives port geometry instead of asserting it.** The axis stops
   being hardcoded and comes from the face normal, and candidates are filtered
   to planar faces — without that filter the bbox radius on a cylinder lateral
   is half a face length, not a radius. A detector that reports a confident
   wrong number is worse than one that reports nothing.
4. **Display tessellation belongs in the library.** `mesh_vertices_local` is a
   library seam (`_imported.py:222`) that only an example fills today, so every
   STEP component in every scene renders as a featureless box from
   `local_bounds`. Fixing it in the example would leave every other caller
   broken.
5. **The port gains a geometric anchor in validation.** This is a trust
   boundary: a port that does not touch its asset is silently wrong geometry,
   the same failure class the OD check already guards. It breaks existing
   models, and that is accepted.
6. **The viewport key gains the scene's own question, and a row for every layer
   it draws.** No new popup. The surface already exists and is under-fed.
7. **The STL tetrahedron is deleted, not kept as a fixture.** Its only consumer
   is the gallery; the tests write their own via `_write_tiny_stl`
   (`tests/test_imported_component_mixed_example.py:11`).

## Design

### 1. The demo asset — `examples/assets/imported_component_demo.step`

A vessel with a bored nozzle stub, authored in local coordinates with the
connection face on the local origin plane and the body extending to `+x`:

| part        | shape                 | local x     |
|-------------|-----------------------|-------------|
| nozzle stub | OD 0.10, bore 0.084   | 0.00 → 0.16 |
| vessel body | Ø0.30 cylinder        | 0.16 → 0.40 |

Bore 0.084 is DN100 `OD 0.1 − 2 × WT 0.008`, so the stub is the same tube the
pipe is. The stub end face is an annulus 0.10 across; its bounding box gives a
detected radius of 0.05, matching pipe `OD/2` exactly, inside the
`max(1 mm, 2%)` tolerance.

Placement is unchanged: origin `[1.2, 0.45, 0]`, identity rotation. The pipe
runs `[0, 0.45, 0]` → `[1.2, 0.45, 0]` and terminates on the stub face.

Generated once with gmsh OCC primitives and committed. No generator script is
kept; a header comment in the example records how it was made.

### 2. STEP display tessellation — `tuba/geometry/step_analysis_importer.py`

`import_component` already opens a gmsh model with the shapes imported. While
it is open, add a coarse surface tessellation and write it into the asset
metadata that the visualization seam already reads:

- `gmsh.model.mesh.generate(2)`, then `getNodes()` and the 3-node triangle
  element type, in **local** STEP coordinates — placement is applied downstream
  by `_transform_asset_points` (`_imported.py:258`).
- Store `mesh_vertices_local` and `mesh_faces` on the cad asset metadata.
- Derive and store `local_bounds` from the node coordinates, replacing the
  example's hand-written `DEFAULT_LOCAL_BOUNDS`. This also gives section 4 real
  bounds to validate against.
- Cap at 5000 vertices, matching the existing STL cap. Set
  `Mesh.MeshSizeFactor` coarse up front and tessellate once; if the result is
  still over the cap, store `local_bounds` only and let the existing box
  fallback stand. One attempt, no retry loop — this is a display mesh.

Consequence beyond this demo: every imported STEP component renders as itself.

### 3. Placement on import — `import_component`

`import_component` has no `placement` parameter, so it cannot both auto-detect
port faces and place the asset; the demo currently calls
`record_component_from_metadata` directly and hand-writes everything. It also
passes no `metadata`, so section 2's tessellation has nowhere to go. Both are
keyword arguments to add, passed through to `record_component_from_metadata`,
which already accepts them.

The example then imports for real, but **detection returns one candidate per
boundary face** — a fused stub-and-vessel solid has cylinder laterals, end caps
and the annulus, so `_detect_port_candidates` yields a handful of
`port_candidate_N` entries with `G_PORT_CANDIDATE_N` face groups and
`status="detected"`. Confirming is therefore a real step, not a relabel. The
example must:

1. Select the candidate whose radius matches pipe `OD/2` and whose position is
   the local origin — the stub end annulus.
2. Rename it to `port_equipment_nozzle_a` with face group `G_EQUIP_PORT_A`, the
   names the analysis region and coupling already use.
3. Promote `status` to `confirmed`.

Step 1 is the part worth getting right: selection by matched radius and
position is the demonstrable rule, and if no candidate matches, the example
must fail loudly rather than fall back to a hand-written port. The remaining
candidates are discarded, not recorded.

Position, radius and axis all come from detection — see section 4. The example
asserts nothing geometric.

### 4. Port axis and face detection — `_detect_port_candidates`

Detection today walks every boundary face, derives radius from a bounding box,
and hardcodes `axis = [1.0, 0.0, 0.0]` (`step_analysis_importer.py:161`). Both
are wrong on curved faces. Probed against the section 1 geometry:

```
tag= 10 type=Plane     r=0.0500  ctr=(0.000,0.000,0.000)  n=[-1.0, 0.0, 0.0]
tag=  8 type=Plane     r=0.1500  ctr=(0.160,0.000,0.000)  n=[-1.0, 0.0, 0.0]
tag=  7 type=Plane     r=0.1500  ctr=(0.400,0.000,0.000)  n=[ 1.0, 0.0, 0.0]
tag=  5 type=Plane     r=0.0420  ctr=(0.170,0.000,0.000)  n=[ 1.0, 0.0, 0.0]
tag=  9 type=Cylinder  r=0.0800  ctr=(0.080,0.000,0.000)  n=[ 0.0, 0.0,-1.0]
tag=  6 type=Cylinder  r=0.1500  ctr=(0.280,0.000,0.000)  n=[ 0.0, 0.0,-1.0]
tag= 11 type=Cylinder  r=0.0850  ctr=(0.085,0.000,0.000)  n=[ 0.0, 0.0, 1.0]
```

On the cylinder laterals the bbox radius is not a radius at all — tag 9's
`0.0800` is half the face *length* — and the normal sampled at the parametric
midpoint is an arbitrary point on the surface. A pipe cannot land on a cylinder
lateral, so these are not port candidates in the first place.

Two changes:

- **Filter to planar faces.** `gmsh.model.getType(2, tag) == "Plane"`. This is
  what makes the bbox radius meaningful: on a disc or annulus, max extent / 2
  *is* the radius (tag 10 gives 0.0500 against a required 0.05).
- **Derive the axis from the face normal.** Take the parametric midpoint from
  `gmsh.model.getParametrizationBounds(2, tag)` and call
  `gmsh.model.getNormal(tag, [u, v])`. Orient it outward: flip if it points
  toward the solid's `occ.getCenterOfMass(3, volume)`, so a port axis always
  points away from the equipment and back down the pipe, independent of how OCC
  happened to orient the face.

With both, detection on the demo asset yields a fully correct port — radius,
position and axis — and the example confirms status only. Candidate count drops
from 7 to 4.

### 5. Port-on-asset validation — `tuba/validation.py`

`_validate_ports` gains: resolve the port's owning component to its cad asset;
if that asset carries `local_bounds`, transform the eight corners by the
placement, take the AABB, and require the port position inside it within
tolerance `max(1 mm, 1% of the largest span of that AABB)`. Skipped when bounds
are unknown — the check cannot assert what it does not know.

The AABB of a rotated box is looser than the box, so this is deliberately a
coarse check. It catches the failure that matters: a port nowhere near the
asset it claims to belong to.

**This is a breaking change, and that is accepted.** Models that validate today
with off-asset ports will now fail. Backward compatibility is explicitly not a
constraint here: a port that does not touch its asset is wrong, and keeping it
loadable preserves nothing worth preserving. Any fixture the suite exposes is
assessed as a real defect and its geometry corrected — not the check loosened
to admit it.

### 6. Viewport key — `viewer/src/app.js`

In `renderViewportLegend()`:

- Prepend the active catalog entry's `question` and `summary`. The catalog is
  already loaded at `app.js:174` and handed to `initBundlePicker` at `:204`;
  stash the entry matching `currentBundleUrl` alongside it.
- Add rows, gated on the corresponding layer being populated: imported
  component (STEP, meshed as a 3D solid), connection port, coupling, local
  frame — plus a support-glyph row off the existing `support` overlay.
- `bodyLegendOpen` (`app.js:1877`) defaults to `true`; a close persists in
  `localStorage` so it stays shut once dismissed.
- Embed mode keeps hiding the key, unchanged, so the docs iframes stay clean.

### 7. Republication

`viewer/public/<bundle>/` and `viewer/dist/` are gitignored (`.gitignore:44,52`)
— they are local build artifacts, regenerated on demand and never committed.
The committed output is the packaged viewer under `tuba/visualization/_viewer/`,
which CI keeps in sync with `npm run build` followed by `git diff --exit-code`.

So republication is: rebuild the bundle locally to look at it, rebuild the
packaged viewer, and commit only the latter. On Windows the page build needs
`UV_NO_SYNC=1` — a nested `uv run` swaps numpy while its DLL is loaded.

Docs to update: `docs/content/examples.md` (the row) and
`docs/content/modeling.md` (the iframe copy currently reads "geometry and model
provenance only"). Both must keep saying there are no solver results, because
there are none.

## Testing

- **Asset**: the shipped STEP parses; the detected port radius equals pipe
  `OD/2` within tolerance; `gmsh_face_tag` is an int.
- **Candidate selection**: detection yields more than one candidate, and the
  example picks the stub end annulus by matched radius and position. A STEP
  whose faces match nothing must raise rather than silently hand-write a port.
- **Detection geometry**: on the shipped asset, the selected candidate carries
  radius `0.05`, position `[0, 0, 0]` and axis `[-1, 0, 0]`, all from gmsh; no
  cylinder lateral is proposed; the outward-orientation guard survives a face
  whose OCC normal points inward.
- **Coupling**: `run_demo(..., export_study=True)` writes a study whose `.comm`
  names the port face group in `GROUP_MA_1`, and whose MED carries a
  **non-empty** group for it. This is the assertion the whole design exists to
  make true.
- **Tessellation**: a STEP import populates `mesh_vertices_local`, `mesh_faces`
  and `local_bounds`, under the vertex cap.
- **Validation**: a port moved off its asset raises; a port on it passes; an
  asset without bounds is skipped.
- **Viewer**: node tests for the new key rows, the question/summary block, and
  default-open.
- The full suite (586) must stay green.

## Out of scope

- **Making the mixed study solve-ready.** `RUNTIME_BLOCKER` stands; this design
  does not claim a solve.
- **Non-planar port faces.** Detection filters to planes. A port on a conical or
  spherical seat is real geometry this will not propose, and is a later change.
- **An overlay toggle for the imported layers.** The key names them; a toggle is
  a different request.
