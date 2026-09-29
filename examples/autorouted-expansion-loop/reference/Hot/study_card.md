# Study card: Hot

Source folder: `evidence/Hot`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Hot |
| Load case | Hot |
| Project | HotLineExpansionLoop |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Hot |
| Mesh size | 145 nodes, 73 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-19T11:02:32.625875Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 8 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 8 |
| `DEBUT` | 1 |
| `DEFI_LIST_INST` | 1 |
| `DEFI_LIST_REEL` | 1 |
| `DEFI_MATERIAU` | 3 |
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
| `study.comm` | 9.1 kB | `3340f74a71079723…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 16.3 kB | `0273085f81c307fb…` |
| `study.mess` | 103.7 kB | `fdd2cc82a0932119…` |
| `study.rmed` | 4.42 MB | `8f62cc6c0ec4c659…` |
| `study_contact.json` | 274 B | `661db79bd4a30e7e…` |
| `study_depl.csv` | 46.8 kB | `33630f9d4fc172ca…` |
| `study_effo.csv` | 77.4 kB | `a333abb18e72cde8…` |
| `study_manifest.json` | 152.8 kB | `1864cb5f11903c72…` |
| `study_reac.csv` | 46.8 kB | `1455a47517458e1e…` |
| `study_sieq.csv` | 10.98 MB | `91e87c9a455eb4ae…` |
| `study_tuba_fem.json` | 10.9 kB | `f80aa49bd902aa3b…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
