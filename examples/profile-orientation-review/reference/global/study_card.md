# Study card: global

Source folder: `evidence/global`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:global |
| Load case | global |
| Project | I-section orientation: the same tip force at 0, 45 and 90 degrees |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:global |
| Mesh size | 291 nodes, 288 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T14:34:53.003617Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 4 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_TABLE` | 3 |
| `DEBUT` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 3 |
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
| `study.comm` | 8.0 kB | `b7e47b3c613832cb…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 40.5 kB | `a9175456698e7d7f…` |
| `study.mess` | 36.9 kB | `adb0bb6910dd555e…` |
| `study.rmed` | 135.0 kB | `07795b31fa7aefd4…` |
| `study_depl.csv` | 93.7 kB | `135f2b6f32c73339…` |
| `study_effo.csv` | 205.0 kB | `4bfe9ca7755cf65e…` |
| `study_manifest.json` | 201.8 kB | `7f3bf62a1f41070b…` |
| `study_reac.csv` | 93.7 kB | `312709846dc91bd7…` |
| `study_tuba_fem.json` | 28.6 kB | `4b71f17cfc6ecf66…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
