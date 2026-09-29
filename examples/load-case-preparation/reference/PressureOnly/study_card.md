# Study card: PressureOnly

Source folder: `evidence/PressureOnly`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:PressureOnly |
| Load case | PressureOnly |
| Project | Load-case preparation |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:PressureOnly |
| Mesh size | 142 nodes, 70 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-26T20:58:44.379073Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 5 |
| `AFFE_MATERIAU` | 1 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
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
| `study.comm` | 4.9 kB | `d02016fb408e3aa1…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 18.5 kB | `31349d81b9352e30…` |
| `study.mess` | 35.9 kB | `ca47dba47763a7bb…` |
| `study.rmed` | 4.40 MB | `0e134d62c5125969…` |
| `study_depl.csv` | 45.9 kB | `688ac2a568812822…` |
| `study_effo.csv` | 74.9 kB | `d71b0211ab148a98…` |
| `study_manifest.json` | 159.6 kB | `88cc79aab04a3cc6…` |
| `study_reac.csv` | 45.9 kB | `40e234ebfa8a213e…` |
| `study_sieq.csv` | 10.83 MB | `cebc1fd3117e851b…` |
| `study_tuba_fem.json` | 13.2 kB | `356e787a5c9426b4…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
