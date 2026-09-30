# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | Street Rack Bridge |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 371 nodes, 301 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | python_bridge |
| Solved at | 2026-09-30T13:36:06.129588Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 24 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 14 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 7 |
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
| `study.comm` | 21.3 kB | `1779109b849c2deb…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 48.7 kB | `d48486632ed5501e…` |
| `study.mess` | 147.3 kB | `62dbabdad44251da…` |
| `study.rmed` | 4.63 MB | `04bc2a53f5662331…` |
| `study_contact.json` | 841 B | `a5d6552dbe28b84e…` |
| `study_depl.csv` | 119.4 kB | `029140ddc12d3733…` |
| `study_effo.csv` | 239.8 kB | `e9c51fb67399672a…` |
| `study_manifest.json` | 341.6 kB | `61ce6ea4cdbf90c1…` |
| `study_reac.csv` | 119.4 kB | `95b668d41be172e1…` |
| `study_sieq.csv` | 11.14 MB | `7df117d99227ad77…` |
| `study_tuba_fem.json` | 40.6 kB | `b0ba3e99813aa530…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
