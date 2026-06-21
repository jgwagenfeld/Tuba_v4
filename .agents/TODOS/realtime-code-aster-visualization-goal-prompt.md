# Goal Prompt - Realtime Code_Aster Visualization

Use this as the Codex `/goal` prompt when ready to implement the visualization roadmap.

```text
Your /goal is to fully implement the realtime Code_Aster visualization workflow for Tuba, package by package, using the specification and workplan already written in:

- .agents/SPECS/realtime-code-aster-visualization.md
- .agents/TODOS/realtime-code-aster-visualization-implementation-plan.md
- .agents/TODOS/realtime-code-aster-visualization.md
- .agents/DECISIONS/realtime-code-aster-visualization.md
- .agents/SPECS/visualization-engine.md
- .agents/TODOS/visualization-engine-workpackages.md
- docs/visualization_engine_vision.md

Implement the packages RV01 through RV19 sequentially. RV00 is already complete as the planning baseline.

For each package:

1. Read the relevant spec/workplan section.
2. Add focused tests before or alongside the implementation.
3. Implement only the current package scope.
4. Run the package verification command from the workplan.
5. Fix failures before moving to the next package.
6. Update the package status in .agents/TODOS/realtime-code-aster-visualization-implementation-plan.md.
7. Record new architectural decisions in .agents/DECISIONS/realtime-code-aster-visualization.md.
8. Preserve compatibility with the existing Tuba workflow, Code_Aster solver integration, VisualizationScene contract, PyVista paths, and viewer tests.

Core constraints:

- VisualizationScene remains the canonical viewer contract.
- The web viewer is the primary interactive review engine.
- Use Vite + TypeScript + Three.js for the first real viewer renderer.
- Keep PyVista/trame for notebooks, screenshots, and engineering debug plots.
- IFC is exchange/context, not the internal visualization state.
- Code_Aster must not be executed automatically on every preview save.
- Unit tests must not require a local Code_Aster installation.
- Browser/e2e tests must be deterministic and must verify a nonblank canvas for the viewer smoke fixture.
- Visual deformation scale must never change engineering clash results.
- Realtime preview starts with full scene reload before SceneDiff optimization.
- Python live preview only runs trusted local scripts in a subprocess with timeout.
- JSON ModelPatch preview must dry-run through ModelTransaction and must not mutate the committed model.
- Keep implementation incremental, tested, and compatible with existing tests.

Start with RV01. Continue through RV19 until the complete visualization workflow is implemented, tested, documented, and the final verification gate passes.
```
