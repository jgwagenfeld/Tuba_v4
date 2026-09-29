# Study card: OperatingHot

Source folder: `evidence/OperatingHot`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:OperatingHot |
| Load case | OperatingHot |
| Project | Load-case preparation |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:OperatingHot |
| Mesh size | 142 nodes, 70 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-26T20:58:17.023009Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 6 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 1 |
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
| `study.comm` | 13.8 kB | `fd7bd977fc4ddd98…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 18.5 kB | `31349d81b9352e30…` |
| `study.mess` | 49.8 kB | `7d8926f172736c3b…` |
| `study.rmed` | 4.40 MB | `9598b418d5b39f72…` |
| `study_depl.csv` | 45.9 kB | `72408de946987b3d…` |
| `study_effo.csv` | 74.9 kB | `211895f4de4b2982…` |
| `study_manifest.json` | 159.6 kB | `b1a5b1c7f99bd7a3…` |
| `study_reac.csv` | 45.9 kB | `831a41075a67a738…` |
| `study_sieq.csv` | 10.83 MB | `c00f739ef71ac541…` |
| `study_tuba_fem.json` | 13.2 kB | `e4aabc16ae88c895…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
