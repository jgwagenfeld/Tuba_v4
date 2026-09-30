# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | MultipipeRack |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 340 nodes, 328 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-29T21:56:46.510070Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 39 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 28 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 13 |
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
| `study.comm` | 36.4 kB | `e4d6bbed5927bd7b…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 48.8 kB | `7e8464e0ecc17f1e…` |
| `study.mess` | 206.7 kB | `06c06fca931f3de9…` |
| `study.rmed` | 1.03 MB | `5fb256179bd7d8e5…` |
| `study_contact.json` | 2.4 kB | `b381841c7f10b347…` |
| `study_depl.csv` | 109.5 kB | `e441686f96c57dec…` |
| `study_effo.csv` | 237.7 kB | `4145fa766461fcde…` |
| `study_manifest.json` | 249.0 kB | `e488fd80bfba32b4…` |
| `study_reac.csv` | 109.5 kB | `d6e0bc430aedc739…` |
| `study_sieq.csv` | 1.86 MB | `682e220b14880672…` |
| `study_tuba_fem.json` | 37.2 kB | `d370cee1cd313ceb…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
