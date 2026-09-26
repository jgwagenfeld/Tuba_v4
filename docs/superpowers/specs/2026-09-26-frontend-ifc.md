# Shared Studio/Gallery workspace and IFC exchange

The approved direction is the preceding frontend review: one viewer for Studio and published Gallery reviews, an engineering object tree, readable results, discoverable inspection tools, reproducible downloads, IFC export, reference IFC import, and validated engineering conversion.

## Product behavior

- Preserve Build/Review, Python-first authored projects, Code_Aster evidence, colour/visibility independence, and both existing visualization paths.
- The default object browser groups physical engineering objects. Derived representations belong under their source object where a source is known. Unmapped analysis objects remain accessible under an explicit analysis group. Existing search and alternate grouping stay available.
- Render human labels for result fields and geometry states, with identifiers still available in details. Keep FE stress versus code-stress warnings.
- Put fit/hide/isolate/section controls together and provide a two-point distance measurement with explicit units and coordinates; no claim of nearest-surface clearance.
- Studio and Gallery use the same renderer, controls, and source inspection; only server-backed actions differ. Add viewer build identity and downloadable Gallery project/IFC artifacts when actually available.
- IFC reference import previews contents, unit scale and placement; adding it persists a reference without altering authored model.py or the solver model. Tessellated geometry uses the existing scene mesh format; IFC identity/property sets appear in selection details. Unsupported geometry is reported, never silently passed as complete.
- IFC conversion is deliberately bounded to supported straight pipe axes, explicit material/section assignments, unit and placement normalization, and selected IFC GUIDs. Unsupported fittings/geometry and unresolved values block conversion. Produce a new portable unsolved project (procedural loader plus original IFC), not a rewritten existing script or a coordinate dump. Boundary conditions and loads require authoring before solving.
- IFC export uses the existing exporter. Geometry export is available for supported native geometry when the optional IFC extra is installed; unsupported geometry is explicitly rejected instead of silently omitted. Engineering properties require fresh verified Code_Aster evidence; do not derive results from viewport colours or amplified deformation. If an evidence-backed export cannot be provided safely, expose geometry-only clearly and document the remaining limitation.
- No browser IFC engine dependency: static Gallery supports published IFC downloads and preprocessed references; arbitrary IFC uploads require Studio. Missing IfcOpenShell gives an actionable setup message.

## Validation

Meaningful focused Python and Node tests, real IfcOpenShell reference/conversion/export checks, HTTP boundary checks, Studio/static browser parity checks, and a review using existing attested Code_Aster artifacts. No fabricated numerical results. No new solve engine is being implemented.
