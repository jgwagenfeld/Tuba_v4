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
| Execution | python_bridge |
| Solved at | 2026-09-30T13:32:33.081160Z |
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
| `study.comm` | 24.0 kB | `d5cb319d7a8772be…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 75.1 kB | `05143368cd59ff3a…` |
| `study.mess` | 155.7 kB | `2c51f22e8ec432f2…` |
| `study.rmed` | 12.00 MB | `893214d7196b1385…` |
| `study_contact.json` | 910 B | `81de8ce1a5a9b19f…` |
| `study_depl.csv` | 196.9 kB | `3461a92e4191a5cd…` |
| `study_effo.csv` | 367.8 kB | `6b6cfa7a1bd83814…` |
| `study_manifest.json` | 599.4 kB | `c2a748b04fc223de…` |
| `study_reac.csv` | 196.9 kB | `26503efed1a41d81…` |
| `study_sieq.csv` | 29.69 MB | `40c26a57eb7993cc…` |
| `study_tuba_fem.json` | 56.6 kB | `57e49c5fb9e4b65b…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
