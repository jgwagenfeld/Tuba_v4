# Visualization Optional Adapters

Tuba's canonical viewer contract remains `VisualizationScene`. Optional adapter
packages may add specialized renderers or exchange formats, but they must stay
behind isolated interfaces and must not become required dependencies of the core
web viewer, PyVista debug paths, scene builders, or tests.

## Capability Matrix

| Adapter | Primary use | Optional dependencies | Artifact boundary | Contract rule |
| --- | --- | --- | --- | --- |
| vtk.js dense mesh/scalar | Dense finite-element mesh, scalar, vector, and time/state result review | `vtk.js` | VTK.js scene or VTU/VTP-derived JSON referenced from a scene bundle | Consumes `VisualizationScene` result references and external mesh artifacts; it does not replace scene metadata or engineering result values. |
| That Open Fragments IFC context | IFC context, fragment streaming, large BIM coordination context | `@thatopen/fragments`, `@thatopen/components` | IFC or fragment artifacts attached as external context | IFC/fragments are exchange and context only; Tuba model, clash, route, and result state remain authoritative. |
| xeokit XKT context | Metadata-heavy BIM context and large XKT coordination models | `@xeokit/xeokit-sdk`, `xeokit-gltf-to-xkt` | XKT or glTF-to-XKT context assets | External BIM IDs map into scene context metadata without mutating committed Tuba visualization state. |

## Adapter Boundary Notes

- The core web viewer continues to use Vite, TypeScript, Three.js, and the scene
  bundle contract.
- Optional adapter status checks return diagnostics when an adapter is not wired;
  they do not import renderer packages.
- Adapter packages may generate or reference additional artifacts, but object
  selection, overlays, issues, route reviews, and agent proposals still flow
  through `VisualizationScene`.
- Visual deformation or renderer-specific exaggeration must never change
  engineering clash, route, or Code_Aster result values.
- Unit tests for Tuba must pass without installing any optional adapter package.
