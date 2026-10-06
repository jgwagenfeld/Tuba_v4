# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | LineLoadStudioProject |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 57 nodes, 36 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-04T17:04:42.455329Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 9 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 2 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 7 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 2 |
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
| `study.comm` | 9.5 kB | `80c970f998616e36…` |
| `study.export` | 404 B | `85dc46238025a16f…` |
| `study.mail` | 7.2 kB | `733835882f248f56…` |
| `study.mess` | 84.5 kB | `e4c0980da72553ba…` |
| `study.rmed` | 1.24 MB | `e165c552e0adc954…` |
| `study_contact.json` | 205 B | `9efd5c90ffda2cd4…` |
| `study_depl.csv` | 18.6 kB | `dcd13a3789f22bc7…` |
| `study_effo.csv` | 32.6 kB | `769d724b5cfa1c0b…` |
| `study_manifest.json` | 52.6 kB | `32f49736a9d597db…` |
| `study_reac.csv` | 18.6 kB | `3cd27acb2b3696c3…` |
| `study_sieq.csv` | 2.94 MB | `d69a2d98eef60458…` |
| `study_sipo.csv` | 9.2 kB | `eab5e84624dc7332…` |
| `study_tuba_fem.json` | 5.0 kB | `e9d6b57b5ae1a3e9…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
