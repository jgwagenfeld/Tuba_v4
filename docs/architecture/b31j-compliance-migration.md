# ASME B31J / B31.3-2020 Compliance — Migration Brief

**Status:** the *safe, source-verified* subset is implemented. The remaining
items are blocked on either a **licensed ASME B31J-2023 copy** or **solver +
model feature work**, and must **not** be coded from memory — wrong stress
numbers ship non-conservative results.

This brief was produced from a research + adversarial-verification pass
(cross-checking every formula against independent sources) plus direct reading
of the current code. Formula citations are in the appendix.

---

## Background

ASME B31.3-2020 **deleted Appendix D** and made **ASME B31J-2017/2023
mandatory** for stress-intensification (i) and flexibility (k) factors. B31J is
a *directional* index system: separate in-plane / out-of-plane / torsional /
axial indices and direction-specific flexibility, plus distinct **sustained**
stress indices (≈0.75·i) vs **displacement** SIFs. The sustained and occasional
stress equations also moved to **B31.3 §320** (from §302.3.5).

## Done (implemented, tested, backward-compatible)

- **Bend/elbow SIFs are already B31J-correct** — B31J and Appendix D are
  numerically identical for elbows (`h=tR/r_m²`, `i_i=0.9/h^(2/3)`,
  `i_o=0.75/h^(2/3)`, `k=1.65/h`), verified against the pveng.com CAESAR II
  sample report. Regression test: `tests/test_compliance_b31j.py`.
- **B31J 3-index structure** — [`SIFSet`](../../tuba/compliance/sif.py) +
  `compute_sif_set` (`i_i, i_o, i_t=1, i_a=1, k_i, k_o, h, basis`).
  `compute_sifs` kept as a 4-tuple backward-compat wrapper. Tees are flagged
  `basis="appendix_d_fallback"` (see item 1).
- **Edition-gated f-factor** — `stress_range_reduction_factor(N, edition)`:
  `6·N^-0.2` (2020), `20·N^-1/3` (2022), cap 1.2, floor 0.15.
- **Liberal allowable** — `ASMEB313Evaluator(use_liberal_allowable=True)`
  → `SA = f[1.25(Sc+Sh) − SL]`. The evaluator uses `compute_sif_set` and
  applies `i_t` to the expansion torsion term.

---

## Remaining work

### 1. B31J tee/branch i-factors — BLOCKED: licensed ASME B31J-2023

**Why blocked:** the exact Table 1-1 branch/run coefficients (the `C, a, b, c`
in `i = C·γ^a·β^b·τ^c` and the k analogues) are behind the ASME paywall. Both
the research and the adversarial verifier flagged this; do **not** guess them.

**Current state:** [`sif.py:_get_tee_sifs`](../../tuba/compliance/sif.py)
implements the pre-2020 Markl model — a single `h`, `i_i=i_o=0.9/h^(2/3)`,
`k=1` (rigid), evaluated on the **run** section only, no branch/run split, no
torsional index. `compute_sif_set` returns these with `basis="appendix_d_fallback"`.

**Target (verified structure):** B31J gives **six** i-factors
(`i_ib,i_ob,i_tb` on the branch; `i_ir,i_or,i_tr` on the run) and six k-factors,
each a closed form in `β=r/R`, `γ=R/T`, `τ=t/T` (+ pad ratio `t_r/T`). Stress =
`i·M/Z` using **the section modulus of the leg the factor belongs to** (branch
factors → branch Z, run factors → run Z); B31J drops B31.3's "effective section
modulus". Validity: standard straight tees, `D/T < 100`.

**Touchpoints:**
- `sif.py`: extend `SIFSet` (or add a `BranchSIFSet`) to carry branch vs run
  indices; `_get_tee_sifs` returns them from a transcribed Table 1-1 lookup.
- `asme_b313.py`: wire branch factors to branch Z and run factors to run Z
  (currently applies one SIF to the run section regardless).

**Acceptance:** transcribe B31J-2023 Table 1-1 for welding tee (B16.9),
unreinforced fabricated tee, reinforced (pad) fabricated tee, and weldolet;
validate against a CAESAR II / AutoPIPE tee verification example. The public
**WRC-329** formulas (appendix) are the documented *basis* and a useful
cross-check, but are **not** the exact B31J numbers.

**Effort:** medium once the standard is in hand (transcription + wiring + tests).

### 2. Full sustained-stress rewrite (§320.2) — needs model additions

**Current state:** `asme_b313.py` uses `SL = P·Do/4t + √((i_i·Mi)²+(i_o·Mo)²)/Z`
with the displacement SIFs, allowable `Sh`.

**Target (§320.2, verified):**
`SL = √((Sa+Sb)² + (2·St)²)`, allowable `W·Sh`, with
`Sb = √((Ii·Mi)²+(Io·Mo)²)/Z`, `St = It·Mt/(2Z)`, `Sa = Ia·Fa/Ap`,
using **sustained** indices `Ii,Io,It,Ia ≈ 0.75·i (≥1.0)` (B31J-sourced),
**not** the displacement SIFs.

**Blockers (model additions):**
- `Ap` — metal wall cross-section area → add to `PipeSection`.
- `W` — weld joint strength reduction factor → add to element/section.
- Sustained axial force `Fa` from the solver.
- Sustained indices (`0.75·i` default; B31J values where available).

**Touchpoints:** `sif.py` (sustained-index accessor), `asme_b313.py`
(`_evaluate_node` sustained block), `model.py` (`PipeSection.Ap`, `W`).

**Effort:** medium.

### 3. In/out-of-plane moment decomposition — needs solver output

**Current state:** `_evaluate_node` sets `M_o = 0` and lumps all bending into
`M_i` (its own comment admits this). This is **conservative** (it applies the
larger in-plane SIF to the full resultant), so it is safe but imprecise — and it
means B31J's whole directional-index point is not yet exercised.

**Target:** resolve the solver's local-axis moments (`My, Mz`) into in-plane vs
out-of-plane relative to each element's orientation (for a bend, its plane).

**Blocker:** requires per-element orientation and the solver's local-axis moment
output threaded into compliance.

**Priority:** low for *safety* (currently conservative), high for *accuracy* and
to make B31J directional indices meaningful.

### 4. Occasional loads (§320.3) — END-TO-END feature

**Target (verified):** `SL_sustained + SL_occasional ≤ k·Sh`, **k = 1.33** for
B31.3 (do **not** import the B31.1 1.15/1.20 graduated-duration table).
Occasional loads: wind, earthquake (not combined with each other), relief-valve
discharge, water/steam hammer.

**Blockers (end-to-end):**
- `LoadCase` currently has only `gravity`, `pressure`, `temperature`,
  `ref_temperature` — **no lateral / wind / seismic field**. Add one
  (e.g. a horizontal acceleration or a distributed lateral load).
- `aster.py:_write_comm` must apply that load in Code_Aster.
- A new evaluator path combining a solved sustained case with a solved
  occasional case: `evaluate_occasional(model, sustained_results,
  occasional_results, k=1.33)`.

**Touchpoints:** `model.py` (`LoadCase`), `tuba/solver/aster_comm.py`,
`asme_b313.py`.

**Effort:** large (spans model, solver, compliance).

---

## Verified formula reference (safe to trust)

Cross-verified against independent authoritative sources.

**Bends/elbows (unchanged from Appendix D; add the B31J extras):**
- `h = t·R / r_m²`; `i_i = max(0.9/h^(2/3), 1)`; `i_o = max(0.75/h^(2/3), 1)`;
  `k_i = k_o = 1.65/h`; `i_t = 1`; `i_a = 1`.
- Pressure corrections (large-D/thin-wall only, not yet applied):
  `k /= 1 + 6(P/Ec)(r2/T)^(7/3)(R1/r2)^(1/3)`;
  `i /= 1 + 3.25(P/Ec)(r2/T)^(5/2)(R1/r2)^(2/3)`. (Confirm `Ec` = cold modulus.)

**Stress equations (B31.3-2020/2022):**
- Sustained `SL = √((Sa+Sb)²+(2St)²) ≤ W·Sh` (§320.2) — see item 2.
- Occasional `SL_sus + SL_occ ≤ 1.33·Sh` (§320.3).
- Displacement range `SE = √(Sb²+(2St)²) ≤ SA` (§319.4.4); with `i_t=1` this
  equals the classic `√((i_iMi)²+(i_oMo)²+Mt²)/Z`.
- `SA = f(1.25·Sc + 0.25·Sh)` (Eq. 1a) or liberal `f[1.25(Sc+Sh) − SL]` (Eq. 1b).
- `f`: `6·N^-0.2` (2020) / `20·N^-1/3` (2022), cap 1.2, floor 0.15.

**WRC-329 branch/run SIFs** (public OSTI basis for B31J tees — a cross-check,
**not** the exact B31J numbers):
- Unreinforced, `r_m/R_m ≤ 0.9`: branch `i_b = 1.5(R_m/T_r)^(2/3)(r_m/R_m)^(1/2)(T_b'/T_r)(r_m/r_p)`;
  run `i_r = 0.4(R_m/T_r)^(2/3)(r_m/R_m) ≥ 1.5`.
- Fillet/partial-pen (weldolet-class): branch `i_b = 4.5(...)^(2/3)(...)^(1/2)(T_b'/T_r)(r_m/r_p) ≥ 3.0`;
  run `i_r = 0.8(...)^(2/3)(r_m/R_m) ≥ 2.1`.
- Reinforced fabricated tee (Markl, App. D): `i = 0.9/h^(2/3) ≥ **2.1**` — note
  Tuba's current fallback uses a floor of 1.0, so it under-applies this.

## Reference validation case

**pveng.com "ASME B31.3 Piping Stress Analysis Sample Report"** (File
16579psa-1 R0, B31.3-2018, CAESAR II). NPS 4″ SCH 80 long-radius elbow gives the
exact solver-free SIF/section values already asserted in
`tests/test_compliance_b31j.py`. Its full end-to-end stresses (SUS 8186 psi,
SUS+OCC 8396 psi, EXP 5933 psi) require the full model + a Code_Aster solve and
are only an approximate integration target.

## Sources

- ASME B31J-2017 / **B31J-2023** Table 1-1 (i/k/h per component) — primary,
  proprietary.
- ASME B31.3-2020 / -2022 §319.4.4, §320.2 (sustained), §320.3 (occasional),
  §302.3.5(d) Eqs. 1a/1b/1c.
- Becht, "ASME B31.3 Substantive Changes in the 2020 Edition" (App. D removal,
  B31J mandate) and "Changes to f Factor in the 2022 Edition".
- Paulin Research Group — f-factor 2020→2022 curve change.
- OSTI/DOE Report 841246 (Wais/Rodabaugh), "Background of SIFs and Stress
  Indices" — verbatim WRC-329 branch/run equations.
- whatispiping.com — "SIF / Flexibility Factor: ASME B31.3 vs ASME B31J".
- pveng.com — B31.3 sample report (reference case).
