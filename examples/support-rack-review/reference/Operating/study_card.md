# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | SupportRackReview |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 92 nodes, 87 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-20T06:43:51.927222Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 14 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 10 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 4 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 4 |
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
| `study.comm` | 13.5 kB | `847d6028e4bd33b9…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 13.3 kB | `47495ee9121a2f89…` |
| `study.mess` | 94.8 kB | `2951033e8872972a…` |
| `study.rmed` | 370.6 kB | `3297dd4db99b3d36…` |
| `study_contact.json` | 499 B | `009c5bfaec9d2715…` |
| `study_depl.csv` | 29.8 kB | `e6f850c847e082b1…` |
| `study_effo.csv` | 63.5 kB | `9c59c4af7e64b980…` |
| `study_manifest.json` | 68.9 kB | `d1a97dd7d98a6fd7…` |
| `study_reac.csv` | 29.8 kB | `391365f6c2573cd8…` |
| `study_sieq.csv` | 633.7 kB | `7bbc8c99c21518a0…` |
| `study_tuba_fem.json` | 10.7 kB | `2d17d3451351dd35…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
