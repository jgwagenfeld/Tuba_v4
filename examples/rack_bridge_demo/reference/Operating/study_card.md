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
| Execution | wsl |
| Solved at | 2026-10-04T17:07:51.134598Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 24 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 2 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 15 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 7 |
| `FIN` | 1 |
| `IMPR_RESU` | 1 |
| `IMPR_TABLE` | 5 |
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
| `study.comm` | 21.7 kB | `fa4c786585453ff8…` |
| `study.export` | 404 B | `85dc46238025a16f…` |
| `study.mail` | 48.7 kB | `d48486632ed5501e…` |
| `study.mess` | 156.1 kB | `b6fd920f4e100467…` |
| `study.rmed` | 4.63 MB | `1c19e950f23728e2…` |
| `study_contact.json` | 841 B | `a5d6552dbe28b84e…` |
| `study_depl.csv` | 119.4 kB | `032aa89ae1d896c6…` |
| `study_effo.csv` | 239.8 kB | `cfafcfc2ab7c2c60…` |
| `study_manifest.json` | 341.6 kB | `e6c5778efb4c613f…` |
| `study_reac.csv` | 119.4 kB | `5267897944412ca4…` |
| `study_sieq.csv` | 11.14 MB | `55ff2e030848de3e…` |
| `study_sipo.csv` | 125.4 kB | `78c7b74f75a28a5b…` |
| `study_tuba_fem.json` | 40.6 kB | `abbdafd8338d969b…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
