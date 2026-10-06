# Study card: Gravity

Source folder: `evidence/Gravity`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Gravity |
| Load case | Gravity |
| Project | Steel_Portal_Frame_Hall |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Gravity |
| Mesh size | 210 nodes, 559 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-04T17:23:47.818165Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 15 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `ASSE_MATRICE` | 2 |
| `CALC_CHAMP` | 2 |
| `CALC_MATR_ELEM` | 2 |
| `CALC_MODES` | 1 |
| `CREA_CHAMP` | 1 |
| `CREA_TABLE` | 5 |
| `DEBUT` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 5 |
| `LIRE_MAILLAGE` | 1 |
| `MECA_STATIQUE` | 1 |
| `NUME_DDL` | 1 |

## Unit map in the generated .export

| Logical | File | Dir | Unit | Carries |
| --- | --- | --- | --- | --- |
| comm | `study.comm` | D | 1 | command file |
| mail | `study.mail` | D | 20 | mesh |
| mess | `study.mess` | R | 6 | message log |
| resu | `study.resu` | R | 8 | result database |
| rmed | `study.rmed` | R | 80 | result MED |
| effo | `study_effo.csv` | R | 38 | element end forces (EFGE_ELNO) |
| depl | `study_depl.csv` | R | 39 | displacements (DEPL) |
| reac | `study_reac.csv` | R | 40 | node reactions (REAC_NODA) |
| sieq | `study_sieq.csv` | R | 41 | stress invariants (SIEQ_ELNO) |
| libr | `study_contact.json` | R | 42 | contact history |
| sipo | `study_sipo.csv` | R | 43 | frame member normal stress (SIPO_ELNO) |
| modes | `study_buckling_modes.csv` | R | 45 | buckling mode shapes |
| crit | `study_buckling.json` | R | 44 | buckling critical factors |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 71.1 kB | `7c73808e45929eba…` |
| `study.export` | 474 B | `8c7cdde12b04fe44…` |
| `study.mail` | 65.7 kB | `11d9e74c267305cd…` |
| `study.mess` | 148.9 kB | `33d7e5f918bcec75…` |
| `study.rmed` | 679.4 kB | `c1bdd7e5d38f5837…` |
| `study_buckling.json` | 729 B | `2ef194c151f0c614…` |
| `study_buckling_modes.csv` | 497.3 kB | `3f99f550d4c0401f…` |
| `study_depl.csv` | 67.7 kB | `6c50a65ad6ffebfe…` |
| `study_effo.csv` | 397.7 kB | `9622b6a20a4abe79…` |
| `study_manifest.json` | 274.7 kB | `adfae789b1483c48…` |
| `study_reac.csv` | 67.7 kB | `afcc459479f3fc7d…` |
| `study_sipo.csv` | 312.5 kB | `a42e6835143cf313…` |
| `study_tuba_fem.json` | 47.0 kB | `125fd7ec7102db09…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
