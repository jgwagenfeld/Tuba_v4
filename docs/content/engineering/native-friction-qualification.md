# Native contact diagnostic qualification

Measured 2026-09-08 with Code_Aster 18.00.12; real WSL Ubuntu external execution. SI units. Selected law: DIS_CHOC (penalty contact).
POU_D_T circular pipe OD114.3mm, WT6mm, L2m, E200GPa; beam base tangential travel imposed, pipe tangential displacement solved. Normal displacement fixes a measured 10 kN preload. This is not a force-controlled opening qualification.

Acceptance: force/reference within 1%; reaction-force equilibrium below 10 N (0.1%); penetration <=1e-5m; Coulomb excess <=10N; endpoint step sensitivity <=30N.

| kn N/m | kt N/m | step | penetration m | stick N | slide N | reverse unload N | reverse slide N | equilibrium N |
|---|---|---|---|---|---|---|---|---|
| 1e+09 | 1e+07 | 0.1 | 1e-05 | -1000 | -3000 | -2904.67 | 3000 | 0.03882 |
| 1e+09 | 1e+07 | 0.05 | 1e-05 | -1000 | -3000 | -2904.67 | 3000 | 0.03882 |
| 1e+10 | 1e+08 | 0.1 | 1e-06 | -1000 | -3000 | -2328.8 | 3000 | 0.023882 |
| 1e+10 | 1e+08 | 0.05 | 1e-06 | -1000 | -3000 | -2328.8 | 3000 | 0.023882 |
| 1e+11 | 1e+09 | 0.1 | 1e-07 | -1000 | -3000 | -1304.68 | 3000 | 0.0223882 |
| 1e+11 | 1e+09 | 0.05 | 1e-07 | -1000 | -3000 | -1304.68 | 3000 | 0.0223882 |

DIS_CHOC native V4 labels stick=0, slide=1, detached=2; V5/V6 are tangential slip. The tests check native status against known phases and slip increments against friction work. DIS_CONTACT uses V3/V4 for slip instead; the two mappings must not be mixed.
At the baseline stiffness, the closed elastic-driver reference is keq=kbeam*kt/(kbeam+kt); breakaway travel=3000/keq. Tests check 1000 N stick, 3000 N forward/reverse slide, and incremental unloading.

DIS_CONTACT also passed the prescribed-normal driver sweep (driver-qualification.json), but failed the force-loaded public opening pilot at both baseline and 0.1 stiffness, including CORDE. DIS_CHOC solved the public force-loaded cycle; this prescribed-normal diagnostic does not substitute for that independent production test.

[Native variable mapping, R5.03.17 section 7.6](https://codeaster.gitlab.io/doc/docaster/manuals/man_r/r5/r5.03.17/Modelisation_des_chocs_et_du_frottement_DIS_CHOC.html). Installed Code_Aster18 catalog confirms ten internal variables.

## Beam references

A real 4 m straight pipe solve combined axial and transverse 1000 N loads with a 100 K temperature increase. Axial displacement was 0.0048098 m versus 0.0048097972 m; transverse displacement was 0.0355812 m versus the Euler reference 0.0355304952 m (0.143%, including transverse shear).

A 0.3 m radius, 90-degree elbow under a 100 Nm end moment was checked against independent curvature integration using the existing elbow flexibility factor. At 32 segments, maximum displacement/rotation error was below 0.005%; refinement to 64 segments changed results by less than 0.004%. Anchor moment equilibrium was checked within 0.1 Nm.

`COEF_FLEX` receives the flexibility factor itself: Code_Aster divides bending inertia by that factor. Stress intensification remains in compliance postprocessing. See [POUTRE/COUDE, section 9.4.6](https://codeaster.gitlab.io/doc/docaster/manuals/man_u/u4/u4.42.01/Mot_cle_POUTRE.html).

## Reproduce and limitations

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = '1'
python -m unittest discover -s tests/integration -p test_code_aster_friction.py -v
python -m unittest discover -s tests -p test_code_aster_beam_pipes.py -v
```

Raw tables and measured JSON summaries are under `.build/friction-reference/`; beam artifacts are under `.build/beam-qualification/`. The configured WSL Ubuntu Code_Aster runtime must be available. Skipped integration tests are not qualification passes.

The selected baseline is kn=1e10 N/m, kt=1e8 N/m. Maximum equilibrium residual across the six DIS_CHOC driver runs was 0.03882 N, maximum vector Coulomb excess was zero to output precision, and maximum endpoint-force difference after halving the step was 2.23e-13 N. Native statuses and tangential slip work passed the known cycle checks.

Evidence covers small-displacement, fixed-frame point shoes with isotropic Coulomb friction. It does not establish ROHR2/CAESAR numerical equivalence, full fitting qualification, pressure stiffening, dynamic friction, or a piping compliance verdict. Beam pressure and tee/branch flexibility remain explicitly unsupported. Beam section forces are not TUYAU fibre stresses. Independent formulas are validation references, never replacement result values.


## Public piping and history checks

The public compiler/importer was run with horizontal and inclined shoes through seating, heating, cooling, force-controlled opening and reseating. Each run archived 51 increments. True anchor reactions use `REAC_NODA`; shoe forces are isolated from contact element forces rather than assembled nodal internal forces.

A rigid nonaxis rotation of the complete force/geometry/contact model with a 1 mm initial gap reproduced all 51 increments: maximum global-force transformation difference 1.85e-6 N; displacement difference 8.22e-12 m. The unloaded positive-gap reference is classified as open from its gap and zero force because native internal variables initially contain zeros.

The L-shaped two-shoe example and its independent frictionless comparison passed force and moment equilibrium at every increment. Maximum residuals were respectively 0.008136 N / 0.03436 Nm (mu=0.3), and 0.007439 N / 0.03408 Nm (mu=0). These are measured residuals, not engineering accuracy estimates. Uplift of 600 N opens S2 by 3.75251 mm while S1 retains 10513.29 N normal force.

Code_Aster 18.0.12 can retain a stale open flag after frictionless reseating in its [symmetric local contact branch](https://gitlab.com/codeaster/src/-/blob/18.0.12/bibfor/elements/dis_choc_frot_syme.F90#L282). For mu=0, Tuba derives normal opening from solved force/gap, leaves closed stick/slip behavior indeterminate, and preserves the raw native flag and classification basis. Positive-friction loaded states use native labels.

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = '1'
python -m unittest discover -s tests -p test_native_contact_import.py -v
python -m unittest discover -s tests -p test_code_aster_friction_example.py -v
```
