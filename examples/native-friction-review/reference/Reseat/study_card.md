# Study card: Reseat

Source folder: `evidence/Reseat`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Reseat |
| Load case | Reseat |
| Project | Native piping friction comparison |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Reseat |
| Mesh size | 134 nodes, 132 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-29T06:04:33.083937Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 11 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 11 |
| `DEBUT` | 1 |
| `DEFI_FONCTION` | 5 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 5 |
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
| `study.comm` | 12.2 kB | `9f02c39318dfb09a…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 19.7 kB | `48055fef5f2f5eae…` |
| `study.mess` | 210.4 kB | `72fe6abf22e678f0…` |
| `study.rmed` | 1.59 MB | `32491088454bff81…` |
| `study_contact.json` | 33.2 kB | `ecad9cff4430adc1…` |
| `study_depl.csv` | 2.14 MB | `6fc1e074bc311d90…` |
| `study_effo.csv` | 4.67 MB | `f3af08ca9fd304af…` |
| `study_manifest.json` | 171.2 kB | `48e0774d2fd085b7…` |
| `study_reac.csv` | 2.14 MB | `9f8079584d411a27…` |
| `study_tuba_fem.json` | 13.6 kB | `442b9c331d9bde05…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
