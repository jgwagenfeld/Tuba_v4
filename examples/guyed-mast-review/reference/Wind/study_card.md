# Study card: Wind

Source folder: `evidence/Wind`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Wind |
| Load case | Wind |
| Project | Guyed_Mast_Review |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Wind |
| Mesh size | 41 nodes, 40 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T11:08:06.894242Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 6 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_TABLE` | 3 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 3 |
| `LIRE_MAILLAGE` | 1 |
| `STAT_NON_LINE` | 1 |

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

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 4.7 kB | `56b00c81084ee4f8…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 5.7 kB | `731e6c332cec93d7…` |
| `study.mess` | 45.0 kB | `ccb8a450cb9dccca…` |
| `study.rmed` | 54.8 kB | `5eef88c03f91fd03…` |
| `study_depl.csv` | 13.4 kB | `9ce9fa99b946ad73…` |
| `study_effo.csv` | 28.7 kB | `1a31ae377dec226d…` |
| `study_manifest.json` | 28.8 kB | `c1f4e0f8487bc0a7…` |
| `study_reac.csv` | 13.4 kB | `4bb51086493fa42f…` |
| `study_tuba_fem.json` | 4.4 kB | `28657e6f40a25347…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
