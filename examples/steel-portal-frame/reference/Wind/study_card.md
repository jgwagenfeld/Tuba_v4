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
| Solved at | 2026-09-29T09:25:46.178153Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 15 |
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
| `study.comm` | 69.9 kB | `dac4a5e0fc1152da…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 65.7 kB | `11d9e74c267305cd…` |
| `study.mess` | 127.0 kB | `e2a3dc6c96f621a6…` |
| `study.rmed` | 679.4 kB | `546b47670c069cec…` |
| `study_depl.csv` | 67.7 kB | `0dcde3f09b51ab2d…` |
| `study_effo.csv` | 397.7 kB | `22190620a8c5ae0a…` |
| `study_manifest.json` | 274.4 kB | `36e78707e34b2936…` |
| `study_reac.csv` | 67.7 kB | `4e1cc6aa2e301827…` |
| `study_tuba_fem.json` | 47.0 kB | `52e0c0972b02719b…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
