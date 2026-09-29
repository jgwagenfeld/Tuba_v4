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
| Solved at | 2026-09-29T09:25:39.107039Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 15 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `ASSE_MATRICE` | 2 |
| `CALC_CHAMP` | 1 |
| `CALC_MATR_ELEM` | 2 |
| `CALC_MODES` | 1 |
| `CREA_CHAMP` | 1 |
| `CREA_TABLE` | 4 |
| `DEBUT` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 4 |
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
| modes | `study_buckling_modes.csv` | R | 43 | unmapped unit |
| crit | `study_buckling.json` | R | 44 | unmapped unit |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 70.7 kB | `1c7058ca84a5d75d…` |
| `study.export` | 447 B | `7035cda4075cef53…` |
| `study.mail` | 65.7 kB | `11d9e74c267305cd…` |
| `study.mess` | 142.3 kB | `bcd080bdcaca5cc5…` |
| `study.rmed` | 679.4 kB | `fddecc05a6277e56…` |
| `study_buckling.json` | 729 B | `2ef194c151f0c614…` |
| `study_buckling_modes.csv` | 497.3 kB | `765eca5df296c0bc…` |
| `study_depl.csv` | 67.7 kB | `9e75992b621e5349…` |
| `study_effo.csv` | 397.7 kB | `bbc7b773149f2093…` |
| `study_manifest.json` | 274.7 kB | `2b5682775d0c837b…` |
| `study_reac.csv` | 67.7 kB | `f43f8de8295d061c…` |
| `study_tuba_fem.json` | 47.0 kB | `a86705d313300998…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
