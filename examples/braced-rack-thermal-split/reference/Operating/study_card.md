# Study card: Operating

Source folder: `evidence/Operating`

## What was solved

| Field | Value |
| --- | --- |
| Study | analysis_study:Operating |
| Load case | Operating |
| Project | BracedRackThermalSplit |
| Model revision | 0 |
| Analysis mesh | analysis_mesh:Operating |
| Mesh size | 647 nodes, 678 elements |
| Solver | Code_Aster 18.0.12 |
| Execution | wsl |
| Solved at | 2026-09-29T12:50:50.382506Z |
| Evidence | **verified** — the attestation is intact and the run was verified. |

## Code_Aster commands in the generated .comm

| Command | Calls |
| --- | --- |
| `AFFE_CARA_ELEM` | 1 |
| `AFFE_CHAR_MECA` | 28 |
| `AFFE_MATERIAU` | 2 |
| `AFFE_MODELE` | 1 |
| `CALC_CHAMP` | 1 |
| `CREA_CHAMP` | 2 |
| `CREA_RESU` | 1 |
| `CREA_TABLE` | 16 |
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
| `study.comm` | 31.0 kB | `370e49df76c97923…` |
| `study.export` | 377 B | `49d368425faa339a…` |
| `study.mail` | 93.8 kB | `24a00342a8a94964…` |
| `study.mess` | 166.8 kB | `c15301e2f5d6127a…` |
| `study.rmed` | 981.2 kB | `5d38cb82d66c8d74…` |
| `study_contact.json` | 1.0 kB | `4a611e7a90289ca1…` |
| `study_depl.csv` | 208.1 kB | `bc8718b7029c01d4…` |
| `study_effo.csv` | 485.1 kB | `5e17455b2ebdac85…` |
| `study_manifest.json` | 504.2 kB | `f731b9cbd7a7cf41…` |
| `study_reac.csv` | 208.1 kB | `aeef59ceda1ab4f7…` |
| `study_sieq.csv` | 1.24 MB | `a45ff42fc322489e…` |
| `study_tuba_fem.json` | 75.1 kB | `7492893242a63f52…` |

These hashes are what the solve attested. The evidence verdict above is taken by re-checking them against the files on disk.

## What this card is not

Every value above is read from solver artifacts and describes what Code_Aster was given and returned. No number here is a code check, a utilization or an acceptance verdict: Tuba performs no standards evaluation, and the stresses in this study are finite-element output.
