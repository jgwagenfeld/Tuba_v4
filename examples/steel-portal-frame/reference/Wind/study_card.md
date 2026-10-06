# Study card: Wind

Source folder: `evidence/Wind`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Wind |
| Load case | Wind |
| Project | Steel_Portal_Frame_Hall |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Wind |
| Mesh size | 210 nodes, 559 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-04T17:24:04.068369Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 15 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 2 |
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
| sipo | `study_sipo.csv` | R | 43 | frame member normal stress (SIPO_ELNO) |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 70.4 kB | `4eed27f562079c45…` |
| `study.export` | 404 B | `85dc46238025a16f…` |
| `study.mail` | 65.7 kB | `11d9e74c267305cd…` |
| `study.mess` | 132.7 kB | `9e57a00529f66bb8…` |
| `study.rmed` | 679.4 kB | `debc4449d8d92910…` |
| `study_depl.csv` | 67.7 kB | `228d6faaecc68d23…` |
| `study_effo.csv` | 397.7 kB | `40f2c30461b29251…` |
| `study_manifest.json` | 274.5 kB | `e5bae48f4d20a98e…` |
| `study_reac.csv` | 67.7 kB | `3fd06c46322d07b4…` |
| `study_sipo.csv` | 312.5 kB | `681979f48595e8c9…` |
| `study_tuba_fem.json` | 47.0 kB | `97e946fdea1fc784…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
