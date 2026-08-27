---
status: accepted
---

# Keep one Python package with a small stable engineering core

Tuba is for Python-capable piping and stress engineers who author a pipe-native model, evaluate it with Code_Aster, and review the resulting evidence. Keep one `tuba` distribution: model authoring, validation, solver integration, analysis provenance, and reporting form the stable core; the two display modules support that workflow; routing, compliance, IFC, optimization, clash, and agent capabilities remain explicit extensions rather than equal top-level promises.

The public facade will be reduced deliberately. `Operation` is the sole public operating-state concept and compiles to an internal analysis case; `model.solve()` returns a provenance-bearing `AnalysisRun`, with `ResultState` as persistent result authority and `FEAResults` as its transient numerical carrier. Pipe modelization is a typed engineer choice, model fingerprints establish result freshness, and invalid engineering inputs fail closed. Because the library has no production users, this cleanup may break the current beta API directly instead of retaining compatibility shims.
