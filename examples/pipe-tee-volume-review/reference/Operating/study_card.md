# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | pipe_volume_study:Operating |
| Load case | Operating |
| Project | PipeTeeVolumeReview |
| Model revision | 0 |
| Analysis mesh | pipe-volume-a3d45eca22bb43b2b7c58af6cedb13c7 |
| Mesh size | 56141 nodes, 17318 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-10-06T15:24:49.060319Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 4 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_TABLE` | 4 |
| `DEBUT` | 1 |
| `DEFI_GROUP` | 1 |
| `DEFI_MATERIAU` | 1 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 4 |
| `LIRE_MAILLAGE` | 1 |
| `MECA_STATIQUE` | 1 |
| `MODI_MAILLAGE` | 1 |

## Unit map in the generated .export

| Logical | File | Dir | Unit | Carries |
| --- | --- | --- | --- | --- |
| comm | `study.comm` | D | 1 | command file |
| mmed | `study.med` | D | 20 | mesh |
| mess | `study.mess` | R | 6 | message log |
| rmed | `study.rmed` | R | 80 | result MED |
| depl | `study_depl.csv` | R | 39 | displacements (DEPL) |
| reac | `study_reac.csv` | R | 40 | node reactions (REAC_NODA) |
| sieq | `study_sieq.csv` | R | 41 | stress invariants (SIEQ_ELNO) |
| effo | `study_effo.csv` | R | 38 | element end forces (EFGE_ELNO) |

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 4.6 kB | `2ef9b61ef9cd1d93…` |
| `study.export` | 308 B | `a3d19b6667499571…` |
| `study.med` | 2.91 MB | `691304e0da8b7416…` |
| `study.mess` | 42.4 kB | `517923397eee826e…` |
| `study.rmed` | 61.64 MB | `006b7a4b44f24f72…` |
| `study_depl.csv` | 9.96 MB | `f3f1dcc8a36b3cd4…` |
| `study_effo.csv` | 51.4 kB | `46f81c03c53617cb…` |
| `study_manifest.json` | 38.00 MB | `eaf6c871ffcbc22b…` |
| `study_reac.csv` | 9.96 MB | `11ba756f89edfc1e…` |
| `study_sieq.csv` | 38.63 MB | `7d0f32aca05771ee…` |
| `study_tuba_fem.json` | 1.3 kB | `b9a3b9a2dfa4b1aa…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
