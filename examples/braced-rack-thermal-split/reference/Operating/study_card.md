# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | BracedRackThermalSplit |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 647 nodes, 678 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-04T16:59:20.389186Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 28 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 2 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 17 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 7 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 5 |
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
| sipo | `study_sipo.csv` | R | 43 | frame member normal stress (SIPO_ELNO) |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 31.8 kB | `1fb02e805e15bbdd…` |
| `study.export` | 404 B | `85dc46238025a16f…` |
| `study.mail` | 93.8 kB | `24a00342a8a94964…` |
| `study.mess` | 177.6 kB | `ddd61e7cecd88a9b…` |
| `study.rmed` | 981.2 kB | `cfcb08932820777f…` |
| `study_contact.json` | 1.1 kB | `55b4b48fa23134d0…` |
| `study_depl.csv` | 208.1 kB | `5f367cb6cd2d5d63…` |
| `study_effo.csv` | 485.1 kB | `8bb2a394e4fb6208…` |
| `study_manifest.json` | 504.3 kB | `f31849b65c701dd6…` |
| `study_reac.csv` | 208.1 kB | `998c3751069d386f…` |
| `study_sieq.csv` | 1.24 MB | `8d8c589b28c278d7…` |
| `study_sipo.csv` | 371.2 kB | `63084cbc9204e009…` |
| `study_tuba_fem.json` | 75.1 kB | `45a26f4a8c227463…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
