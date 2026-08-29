# Browser model authoring

Date: 2026-08-29
Status: unblocked, not started

## What changed

Authoring a piping model and writing its complete Code_Aster handoff no longer
requires a compiled mesher.

`_compute_bend_nodes_gmsh` used Gmsh's OCC kernel to place the interior nodes
along a bend. It asked for a transfinite curve on a circular arc, which is a
uniform subdivision of the swept angle — the start radius rotated about the
bend axis in equal steps. `tuba/solver/aster_mesh.py` now does that rotation
directly.

Measured against the previous Gmsh output across every bend in the committed
gallery models, the worst deviation was **9.155e-16 m**, and the generated
`study.mail` is **byte-identical** to the committed artifact for
`viz_gallery_operating`, `support_rack_operating`, `elements_supports_loadcase1`
and `autorouted_expansion_hot`. The solver input did not change.

With `gmsh`, `pyvista`, `h5py`, `meshio` and `ifcopenshell` all made
unimportable — raising `ImportError`, not merely unused — a model *containing a
bend* now completes:

- authoring through `model.pipe(...)` and `model.validate()`
- `build_visualization_scene(...)` and `write_scene_bundle(...)`
- `export_analysis_study(...)`, producing `study.comm`, `study.mail`,
  `study.export`, the manifest and the sidecar

`tests/test_code_aster_study.py::TestOneDimensionalHandoffNeedsNoMesher` guards
this. Without it a stray import quietly closes the door again.

## Why this matters

The product's front door is now the browser, and the gallery shows models
someone else authored. The natural next step is a reader authoring their own —
and the whole authoring half of Tuba is pure Python over numpy and jsonschema,
both of which Pyodide ships.

The resulting shape is honest about where the solver lives:

    author in the browser  ->  download the study handoff
    solve where Code_Aster is  ->  import the artifacts back
    review in the browser

That is the existing export boundary, not a new one. `AGENTS.md` already
requires an exported study to be labelled incomplete until solved, so the
vocabulary for "you authored and meshed this here, now go solve it" exists.

## Scope when this is picked up

In: authoring API, validation, scene building, bundle writing, 1D study export,
rendering the produced scene in the existing viewer with no new renderer.

Out: solving; 3D volume meshing, which still needs Gmsh
(`tuba/meshing/pipe_volume.py`); IFC exchange; RMED reading.

## Known unknowns

- **Pyodide packaging.** Tuba must build as a pure-Python wheel and import
  under Pyodide. The import chain is already clear: `tuba`,
  `tuba.visualization` and `tuba.solver.aster` all import and run with Gmsh
  raising `ImportError`, so only numpy and jsonschema are actually required.
  Gmsh remains a declared dependency in `pyproject.toml` and is still needed
  for 3D volume meshing; whether it becomes an optional `mesh3d` extra is a
  packaging decision about install size, no longer a technical blocker.
- **Payload size.** Pyodide plus numpy is on the order of ten megabytes before
  Tuba. Acceptable for an authoring tool, not for the gallery, so the gallery
  must not pay for it: the editor loads on demand.
- **What the editor actually is.** A code editor over the Python API is the
  cheapest honest thing and matches the audience, who are Python-capable
  engineers by definition. A form or direct-manipulation UI is a much larger
  project and should not be assumed.

## Not a blocker any more

The earlier finding that bend node positions feed the solver-input fingerprint
was about the bend's *endpoint* nodes, which the builder computes and stores in
the model. The interior nodes are generated at mesh time and are not part of
the fingerprint. The byte-identical `study.mail` results confirm it.
