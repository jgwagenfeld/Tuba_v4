# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | VizGalleryDemo |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 72 nodes, 36 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-21T07:53:19.606591Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 7 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 6 |
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

A unit the command file writes but the export omits is silently lost with the run directory; the two lists above are the check on that.

## Attested artifacts

| File | Size | SHA-256 |
| --- | --- | --- |
| `study.comm` | 7.4 kB | `896d147f570cf6eb…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 8.3 kB | `5c171267d0d6d85d…` |
| `study.mess` | 96.7 kB | `819511dc22cef574…` |
| `study.rmed` | 2.21 MB | `775571b25eb724a8…` |
| `study_contact.json` | 137 B | `b1d43e75b8523e6f…` |
| `study_depl.csv` | 23.4 kB | `2fba75e21a1d9a69…` |
| `study_effo.csv` | 38.3 kB | `92860ecb003d2c04…` |
| `study_manifest.json` | 78.9 kB | `201a30ea26ab731e…` |
| `study_reac.csv` | 23.4 kB | `14f0e55312d8a590…` |
| `study_sieq.csv` | 5.41 MB | `a370b76b353dc365…` |
| `study_tuba_fem.json` | 5.7 kB | `514ec0f0b2c858a5…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
