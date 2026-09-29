# Study card: Sustained

Source folder: `evidence/Sustained`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Sustained |
| Load case | Sustained |
| Project | Load-case preparation |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Sustained |
| Mesh size | 142 nodes, 70 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-26T20:57:54.964694Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 6 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_TABLE` | 4 |
| `DEBUT` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 4 |
| `LIRE_MAILLAGE` | 1 |
| `MECA_STATIQUE` | 1 |

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
| `study.comm` | 5.1 kB | `89f4985e0985a34e…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 18.5 kB | `31349d81b9352e30…` |
| `study.mess` | 37.0 kB | `c39aec777c34d404…` |
| `study.rmed` | 4.40 MB | `12e7fc269cf9be7c…` |
| `study_depl.csv` | 45.9 kB | `cdf161389c5634c2…` |
| `study_effo.csv` | 74.9 kB | `8ac80589105e650d…` |
| `study_manifest.json` | 159.5 kB | `3afb7dfa454f78fc…` |
| `study_reac.csv` | 45.9 kB | `346c2429def22f89…` |
| `study_sieq.csv` | 10.83 MB | `44f914bf202582d8…` |
| `study_tuba_fem.json` | 13.2 kB | `d0b3db613463df03…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
