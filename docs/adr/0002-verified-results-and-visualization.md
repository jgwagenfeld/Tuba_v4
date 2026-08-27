---
status: accepted
---

# Require verified results and preserve visualization semantics

Production engineering review and compliance consume an attested `ResultState`; historical artifacts without complete execution attestation remain inspectable only as visibly unverified evidence. Postprocessing may show applied loads, pressure, temperature, and boundary conditions, but it keeps authored inputs, solver-returned results, and derived compliance quantities in distinct semantic channels. Missing or non-finite quantities are unavailable rather than zero, generic FE von Mises stress never implies piping-code utilization, and reaction forces and moments remain distinct results.

The Three.js scene remains the shareable review surface and PyVista remains the local quick-look/export path; they share the same validated result meaning without promising feature parity. Pipe-wall stress claims are reserved for solver-oriented TUYAU sub-point results, reconstructed fields are labelled as element/nodal FE overviews, and stronger production claims require reference validation cases rather than runtime smoke alone.
