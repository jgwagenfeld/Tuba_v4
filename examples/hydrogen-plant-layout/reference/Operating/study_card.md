# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | Hydrogen Plant Layout |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 612 nodes, 421 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T11:09:38.835906Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 26 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 14 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 8 |
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
| `study.comm` | 23.6 kB | `81f5eccc89db70ce…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 75.1 kB | `05143368cd59ff3a…` |
| `study.mess` | 156.5 kB | `616481f3a0592f82…` |
| `study.rmed` | 12.00 MB | `1a9b68e81c32f22b…` |
| `study_contact.json` | 997 B | `b94ce9d911efb051…` |
| `study_depl.csv` | 196.9 kB | `555d9d458ec49f47…` |
| `study_effo.csv` | 367.8 kB | `6a5932f586484aac…` |
| `study_manifest.json` | 599.3 kB | `45592e5f6b2bcabf…` |
| `study_reac.csv` | 196.9 kB | `d398d481582089b5…` |
| `study_sieq.csv` | 29.69 MB | `a62a1d7b90dc342d…` |
| `study_tuba_fem.json` | 56.6 kB | `4303dc6e6012c45e…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
