# STEP Mixed Code_Aster Studies

Tuba can import STEP geometry for mixed Code_Aster studies only after the imported
geometry has explicit analysis regions, confirmed ports, material assignments,
mesh groups, and coupling specs.

Exported `.med`, `.comm`, `.export`, `study_manifest.json`, and
`study_tuba_fem.json` files are solver handoff artifacts. They are not completed
engineering results.

Production stress, displacement, reaction, compliance, operating-state clash, and
result visualization workflows must use artifacts produced by a real Code_Aster
run. If Code_Aster is unavailable, Tuba may export the study for inspection but
must stop before displaying solver results.

First supported slice:

```text
native Tuba pipe endpoint
  -> confirmed imported solid port
  -> LIAISON_ELEM OPTION='3D_TUYAU'
  -> MED-backed Code_Aster study
```
