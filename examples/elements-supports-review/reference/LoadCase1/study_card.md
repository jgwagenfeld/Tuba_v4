# Study card: LoadCase1

Source folder: `evidence/LoadCase1`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:LoadCase1 |
| Load case | LoadCase1 |
| Project | Tuba_v4_Demo_Study |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:LoadCase1 |
| Mesh size | 63 nodes, 44 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T11:07:48.827698Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 6 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_MAILLAGE` | 1 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 6 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 2 |
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
| `study.comm` | 10.4 kB | `298ffac1dcf2fb31…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 8.1 kB | `fdc31db2bf2f6e47…` |
| `study.mess` | 154.9 kB | `86bd8eef8e15477a…` |
| `study.rmed` | 1.18 MB | `849b63b5398dec62…` |
| `study_contact.json` | 137 B | `6d83658041a09daf…` |
| `study_depl.csv` | 20.5 kB | `1d975cdac58170ab…` |
| `study_effo.csv` | 39.0 kB | `f8a5855d2060fe6a…` |
| `study_manifest.json` | 57.4 kB | `000f3f31a25ed01e…` |
| `study_reac.csv` | 20.5 kB | `58eab0963c90d8b1…` |
| `study_sieq.csv` | 2.78 MB | `52dabf515a64e345…` |
| `study_tuba_fem.json` | 5.8 kB | `3675f90365985d38…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
