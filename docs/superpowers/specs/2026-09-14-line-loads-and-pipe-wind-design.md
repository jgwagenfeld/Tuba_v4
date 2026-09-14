# Line Loads and Pipe Wind by Modelization — Design

**Status:** proposed 2026-09-14
**Scope:** 1D Code_Aster studies (`TUYAU_3M`, `POU_D_T`). 3D surface loads are the next slice.

## Problem

An engineer authors a load by what it is — wind pressure from a direction, a force per metre — and picks the pipe
modelization as a study choice. Tuba does not work that way today:

- Wind is accepted only on `beam` elements. The architecture review reasoned that `TUYAU_3M` has no documented
  distributed-load command, so pipe wind is refused.
- There is no line load at all.
- An uncommitted generalized-fields change let wind reach pipes only by forcing `POU_D_T`, which refuses internal
  pressure and tees, and it validated a `force` quantity that no writer applied.

## Measured facts

Real Code_Aster solves, WSL Ubuntu runtime, 2026-09-14. Tuba exports were patched by hand to swap gravity for the
load under test. The pipe was OD 0.1 m and WT 0.01 m, anchored at both ends, and each result is the sum of the
support reactions.

| # | Study | Result |
|---|---|---|
| 1 | `TUYAU_3M`, 4 m straight, plain `FORCE_POUTRE` FY = −1000 N/m | Solves: reactions 4000.0 N. Midspan deflection 1.172 mm (fixed–fixed beam theory: 1.150 mm plus shear) |
| 2 | `TUYAU_3M`, same pipe, `FORCE_POUTRE(TYPE_CHARGE='VENT')` | Refused: `<EXCEPTION> <PIPE1_44>` "Le chargement de type vent n'est pas utilisable pour les éléments tuyaux" |
| 3 | `POU_D_T`, 4 m straight, `VENT` 1000 N/m at 30° to the axis | Reactions (0, −1000, 0). Only the wind across the axis acts, scaled once more by sin θ: magnitude \|f\|·sin²θ |
| 4 | `TUYAU_3M`, 90° elbow R = 0.5 m, plain `FORCE_POUTRE` FZ = −1000 N/m | 785.08 N: the load times the length of the 16 chord segments |
| 5 | `POU_D_T`, same elbow, `VENT` in-plane (0, −1000, 0) | Reactions (−166.7, +333.3, 0), the sin² rule again |
| 6 | `TUYAU_3M`, same elbow, plain `FORCE_POUTRE` whose `FORMULE`s of X, Y, Z apply the sin² rule | Reactions (−166.6, +333.2, 0): matches #5 within 0.06% |
| 7 | `TUYAU_3M`, two `FORCE_POUTRE` occurrences on one group in one `AFFE_CHAR_MECA` (FY −1000, then −500) | Reactions 2000 N: the last occurrence wins; the two do not add |

Two other projection rules solved in #6's setup gave their own exact integrals: plain vector projection
(−249.9, +392.5) and projected area along the wind (0, +499.8). So Code_Aster does evaluate the formulas along
the TUYAU segments, and the sin² rule is the one that reproduces `VENT`.

## Decisions

1. **Loads stay physical and modelization-free.**
   - `wind` keeps its meaning: dynamic pressure in Pa plus a direction. Its head-on line load is q · D_wind, and
     D_wind includes insulation.
   - The new `line_load` is a force per metre along a direction, applied in full.
   - The pipe modelization stays a study choice. It is already part of the model fingerprint's compiler inputs.
2. **One place maps each load to its Code_Aster form**, per element modelization (table below). Every cell is
   either proven by a real reference solve or refused with an error that names the gap. No load is dropped
   silently.
3. **Wind form depends on the modelization.**
   - Beam-modelled elements keep `VENT`, and their existing command output stays byte-identical.
   - `TUYAU_3M` pipes get the rule `VENT` applies, computed by Tuba: F = (|f⊥| / |f|) · f⊥ with
     f⊥ = f − (f·t̂) t̂.
   - On straight pipes that is a constant. On bends it is a `FORMULE` of X, Y, Z, with tangent
     axis × (P − center) from the stored bend geometry.
4. **Each kind of load is its own load concept:** `WIND` (`VENT`), `WIND_TUY` (Tuba's rule) and `LINELOAD`, so
   they add up in `EXCIT`. Within a concept, each element appears in at most one `FORCE_POUTRE` row (fact 7).
5. **Overlapping line loads that disagree fail validation**, through the existing overlap rule, so the engineer
   authors one combined field. Summing per element can come later if needed.
6. **No compiler-id bump.** Models valid before this change export byte-identical studies, so committed evidence
   stays current.
7. **Cables and bars take neither load** until a solve backs them.

## Load forms in this slice

| Authored load | `POU_D_T` (beams always, pipes when chosen) | `TUYAU_3M` pipes | Pipe-volume / mixed study | Native contact path |
|---|---|---|---|---|
| Wind | `FORCE_POUTRE(TYPE_CHARGE='VENT')` (existing) | plain `FORCE_POUTRE`, Tuba applies the sin² rule | refused (existing) | refused (existing: no fields) |
| Line load | plain `FORCE_POUTRE` | plain `FORCE_POUTRE` | refused (new) | refused (existing: no fields) |

## Out of scope

- **3D surface loads** (`FORCE_FACE` on the meshed outer skin `G_OUTER_*`). Next plan, checked against the 1D
  total reaction.
- **The STEP mixed exporter** (`tuba/solver/mixed_study.py`). It writes no loads at all today (only
  `AFFE_MODELE` and `LIAISON_ELEM`, execution disabled). This is a known gap, not changed here.
- **Other items:** line loads in the load-case overlay, cables and bars, additive overlapping line loads, and
  time-varying loads.
- **The uncommitted generalized-fields change** in the main working tree. This work starts from committed `main`.

## Verification

- **Export tests** pin the command text for every cell and every refusal.
- **Pure tests** pin the wind rule. They evaluate the exact `FORMULE` text Tuba writes and compare it with the
  point rule along a tilted bend, and with the solved `VENT` elbow (fact 5).
- **Opt-in real Code_Aster references** (`TUBA_RUN_CODE_ASTER_INTEGRATION=1`):
  - line-load reactions equal load × length on both modelizations;
  - `TUYAU_3M` wind equals `POU_D_T` `VENT` on an oblique straight and on an elbow;
  - wind and a line load on one elbow add up.
