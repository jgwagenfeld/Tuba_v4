# Imported geometry in Studio

This is known reference geometry, not a reconstruction of the missing historical header disks. `model.py` defines reusable functions for imported solids, panels, frame members, pipe/beam continuations and released joints. Its `assemble` calls record their parameters for agent inspection. It builds the model only; `study.py` runs and checks real Code_Aster results.

From the repository root:

```powershell
python -m tuba.cli_studio examples/imported-geometry-studio
```

In Build, inspect the gray STL enclosure, its dimensions/axes and surface diagnostics; select the solid ports and connection overlays, then follow Defined by and Called at into the Python functions. Use Import geometry to preview an STL/STEP/STP, declare its scale/placement and store it in this project. The resulting Python call is explicit source for `model.py`; importing a file does not rewrite authored functions.

Select a body to see Meshing and Structural integration. Show surface triangles draws the imported STL triangles or STEP display tessellation; these are separate from the structural FE mesh. STEP analysis bodies show their material, element order and requested mesh size. Inspect connections follows their authored ports, patches, members and supports, and Highlight connections marks those relationships in the scene. An STL reference explicitly reports no structural stiffness or connections. View solved FE mesh in Review opens the current native solver mesh when verified evidence is available.

The STL cube's coordinates are millimetres, converted once with scale .001. It is reference geometry for inspection and clearance, without stiffness. The supplied STEP is the same deliberately scaled test spool used by the native connection references: its source-local coordinates are .2 long and .05 outside radius, and explicit scale 1.0 makes them model metres. For ordinary millimetre CAD use scale .001, with selectors in normalized source-local millimetres.

The authored panel and native frame share a restrained base. Its spool mount holds DX, DY, DRX, DRY and DRZ against the frame and releases DZ, following the selected V3 convention. Separate confirmed ports connect a native pipe with `3D_TUYAU` and a native beam with `3D_POU`.

Save changes to Python or a source geometry file to refresh Build. Solve runs the existing Gmsh/Code_Aster path and checks actual support force/moment balance before Review displays processed results. An unavailable runtime or invalid interface stops evaluation clearly. Inspection geometry alone is not a completed engineering evaluation.
