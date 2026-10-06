# Study card: Wind

Source folder: `evidence/Wind`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Wind |
| Load case | Wind |
| Project | Guyed_Mast_Review |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Wind |
| Mesh size | 41 nodes, 40 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-04T17:22:56.955737Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 6 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 2 |
| `CREA_TABLE` | 4 |
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
| sipo | `study_sipo.csv` | R | 43 | frame member normal stress (SIPO_ELNO) |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 5.4 kB | `d6a1aa25776e419f…` |
| `study.export` | 404 B | `85dc46238025a16f…` |
| `study.mail` | 5.7 kB | `731e6c332cec93d7…` |
| `study.mess` | 51.4 kB | `b4788c629b1f089e…` |
| `study.rmed` | 54.8 kB | `4c1fbdfcd72e1fa3…` |
| `study_depl.csv` | 13.4 kB | `5f21fdeb1781b03c…` |
| `study_effo.csv` | 28.7 kB | `a6b1aab46d2ef8ad…` |
| `study_manifest.json` | 28.9 kB | `5443a6211ca47d6d…` |
| `study_reac.csv` | 13.4 kB | `d562dfa3b1aec4ed…` |
| `study_sipo.csv` | 9.2 kB | `761ba08bf011a6ac…` |
| `study_tuba_fem.json` | 4.4 kB | `84a8f26ddf871dd3…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
