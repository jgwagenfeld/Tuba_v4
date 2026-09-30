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
| Mesh size | 94 nodes, 88 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | python_bridge |
| Solved at | 2026-09-30T13:40:25.140284Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 15 |
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
| `study.comm` | 14.2 kB | `ac98ca23188db3a3…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 13.6 kB | `c46068a044c73381…` |
| `study.mess` | 96.8 kB | `8c1889c6e09eac21…` |
| `study.rmed` | 434.3 kB | `488df85ca93663bf…` |
| `study_contact.json` | 396 B | `3a7a90523cc86c2b…` |
| `study_depl.csv` | 30.4 kB | `3a388d3e7f4fe17a…` |
| `study_effo.csv` | 64.6 kB | `ded5441c5e496a44…` |
| `study_manifest.json` | 70.0 kB | `60729cf46789c1da…` |
| `study_reac.csv` | 30.4 kB | `0f6c16887c257c90…` |
| `study_sieq.csv` | 792.1 kB | `18aaa878165eb5cb…` |
| `study_tuba_fem.json` | 10.8 kB | `8f60b09d945a4e01…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
