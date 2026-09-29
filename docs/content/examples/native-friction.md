# Native piping friction comparison

This example builds two disconnected, translated copies of the same horizontal L-shaped pipe and solves them together in one nonlinear Code_Aster `DIS_CHOC` evolution. One copy has frictionless shoes; the other has Coulomb friction with mu = 0.3. Geometry, material, supports, load cases, solver increments and the `Cold -> Hot -> Cold -> Lift -> Cold` path are otherwise identical.

The pipes have 4 m and 3 m straight legs joined by a 0.3 m radius elbow. Each copy has its own anchor and two upward-normal shoes. Gravity acts in global -Z. A 10 kN downward nodal load seats each shoe; during Lift, S2 instead receives 600 N upward. Pressure is zero. The pipe uses `POU_D_T`, OD 114.3 mm, wall 6 mm, E = 200 GPa, density 7850 kg/m3 and thermal expansion 12e-6/K.

The model is `examples/native-friction-review/model.py`; the load path, solver settings and review checks are in `study.py` beside it. Open it in the studio from the repository root:

```powershell
python -m tuba.cli_studio examples/native-friction-review
```

Build shows `model.py` beside the scene. Solve reuses the committed evidence while it still matches the model, and runs Code_Aster once an edit changes the solver input. In Review, use Controls and Results to step through the shared converged history. The scene labels identify **Without friction - mu = 0** and **With friction - mu = 0.3**.

A load path is a sequence, so the review reads as one. **Load path** offers the stages - `Reference`, `Cold`, `Hot`, `Cold`, `Lift`, `Cold` - and each jumps to the converged increment that stage ended on, with a chip marking the stages where a shoe moved. The contact panel opens with a sentence per event in load-path order (which shoe slid, from which stage through which; which lifted clear and by how much; which reversed; which reseated), then the per-shoe table, where a column per stage lets a shoe's whole cycle be read across one row. Selecting a shoe plots its force against travel with the Coulomb envelope.

Contact rows expose true gap, vector slip, force and utilization. Frictionless utilization remains unavailable and tangential force must remain zero; a mu = 0 shoe is reported as having no cone rather than as an indeterminate failure. The friction copy must demonstrate sticking, sliding, opening, cooling reversal and final reseating.

The output contains one solver attestation, the review package, and one scene with both pipe copies. `reports/contacts.csv` holds every shoe at every converged increment in solved order and `reports/contact_findings.csv` the derived sequence; both are listed in `report_manifest.json`. To rebuild the review from the canonical attested artifacts:

```powershell
python -m tuba.project examples/native-friction-review --output .build/native-friction-import --artifact-dir examples/native-friction-review/evidence/Reseat
```

Leave out `--artifact-dir` to solve into the project's `evidence/Reseat/` instead; evidence that still matches is reused unless you add `--force`. The folder is named after the load path's final stage, which is what a load path's study is filed under: a five-stage cycle solved as one run is called after the state it ends in, so the evidence says `Reseat` rather than repeating the first stage's `Cold`.

Changing either copy, the coefficient, stiffness, load path or solver inputs invalidates the shared solver identity and stops artifact import. Penalty stiffnesses are numerical controls. This example qualifies the demonstrated small-displacement beam and fixed-frame shoe behavior; it does not establish piping-code compliance or numerical equivalence with another pipe-stress product.
