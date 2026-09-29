# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | pipe_volume_study:Operating |
| Load case | Operating |
| Project | PipeTeeVolumeReview |
| Model revision | 0 |
| Analysis mesh | pipe-volume-48b0c29066b4416982c783c72314e060 |
| Mesh size | 56141 nodes, 11336 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T15:22:43.999003Z |
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
| `study.comm` | 4.6 kB | `db55c1215cf4c861…` |
| `study.export` | 308 B | `a3d19b6667499571…` |
| `study.med` | 2.91 MB | `623853175a1f93d5…` |
| `study.mess` | 40.1 kB | `a92ba856cfe6cf70…` |
| `study.rmed` | 61.64 MB | `70384d6b049285bf…` |
| `study_depl.csv` | 9.96 MB | `f282694b605d2532…` |
| `study_effo.csv` | 51.4 kB | `8e5180722524be72…` |
| `study_manifest.json` | 34.76 MB | `087ecaf9bb85e78b…` |
| `study_reac.csv` | 9.96 MB | `bfbd2ee864a5a40d…` |
| `study_sieq.csv` | 38.63 MB | `43e60383bb45b9e8…` |
| `study_tuba_fem.json` | 1.3 kB | `8bb1f7b2f7a1284b…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
