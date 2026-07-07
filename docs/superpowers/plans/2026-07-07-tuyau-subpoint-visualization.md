# TUYAU Sub-Point Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve and visualize real Code_Aster TUYAU sub-point stress rows in Tuba's existing reviewable web-scene path.

**Architecture:** Use SALOME/ParaVis behavior as the reference: Code_Aster writes integration/sub-point fields, Tuba preserves those rows, and the viewer renders them as selectable point assets. Display positions use Code_Aster's validated TUYAU fibre formula from `zzzz296a`.

**Tech Stack:** Code_Aster `.comm` generation, CSV artifact parsing, `ResultState`, `tuba.visualization` scene JSON, existing Three.js `point` renderer.

## Global Constraints

- Production result values must come from Code_Aster artifacts only.
- Mark display positions as `code_aster_tuyau_subpoint_formula`; keep raw centerline coordinates separately.
- Keep the two existing visualization surfaces only: `tuba/plotting/` and `tuba/visualization/` plus `viewer/`.
- Do not add `medcoupling` or another dependency unless `meshio` and CSV artifacts cannot expose the required data.
- Preserve the existing `max_von_mises` element summary behavior.

---

### Task 1: Export Code_Aster Integration-Point Stress

**Files:**
- Modify: `tuba/solver/aster_comm.py`
- Test: `tests/test_code_aster_study.py`

**Interfaces:**
- Consumes: existing `has_pipe_stress` guard.
- Produces: `.comm` output with `SIEQ_ELGA` in `CALC_CHAMP` and `IMPR_RESU` for pipe studies.

- [ ] Add `SIEQ_ELGA` to `CRITERES` for pipe stress studies.
- [ ] Add `SIEQ_ELGA` to MED `NOM_CHAM` for pipe stress studies.
- [ ] Keep non-pipe studies free of `SIEQ_*` stress criteria.
- [ ] Add/update tests that assert pipe studies export `SIEQ_ELGA` and non-pipe studies do not.

### Task 2: Preserve TUYAU Sub-Point Rows

**Files:**
- Modify: `tuba/solver/base.py`
- Modify: `tuba/solver/aster.py`
- Test: `tests/test_code_aster_tuyau_subpoints.py`

**Interfaces:**
- Produces: `FEAResults.tuyau_subpoints: list[dict[str, Any]]`.
- Consumes: existing `_parse_csv_table()` and solver label maps.

- [ ] Add `tuyau_subpoints` to `FEAResults`.
- [ ] While parsing `study_sieq.csv`, append rows that include `SOUS_POINT`.
- [ ] Include mapped `element_id`, raw Code_Aster labels, `subpoint_index`, `VMIS`, and centerline coordinates when present.
- [ ] Keep `ElementResult.max_von_mises` unchanged.

### Task 3: Persist Sub-Point Metadata

**Files:**
- Modify: `tuba/analysis/results.py`
- Modify: `tuba/analysis/code_aster_artifacts.py`
- Test: `tests/test_result_state.py`

**Interfaces:**
- Consumes: `FEAResults.tuyau_subpoints`.
- Produces: `ResultState.metadata["tuyau_subpoints"]`.

- [ ] Store a compact list of sub-point rows in result-state metadata.
- [ ] Store artifact file references for `study_sieq.csv` as the raw source.
- [ ] Rehydrate `FEAResults.tuyau_subpoints` from result-state metadata.

### Task 4: Render Sub-Points In The Web Scene

**Files:**
- Modify: `tuba/visualization/builders.py`
- Test: `tests/test_visualization_result_overlays.py`

**Interfaces:**
- Consumes: `ResultState.metadata["tuyau_subpoints"]`.
- Produces: scene objects of kind `tuyau_subpoint` and geometry assets with format `point`.

- [ ] Add a result-state sub-point scene builder.
- [ ] Render a capped set of point assets using Code_Aster's TUYAU fibre formula.
- [ ] Add metadata fields `position_source`, `subpoint_index`, `field`, `value`, and raw solver labels.
- [ ] Add an overlay with count, cap, value range, and source field.

### Task 5: Verification

**Files:**
- Run focused tests only.

- [ ] `python -m pytest tests/test_code_aster_study.py tests/test_code_aster_tuyau_subpoints.py tests/test_result_state.py tests/test_visualization_result_overlays.py`
- [ ] Confirm no Code_Aster solve is claimed unless a real runtime is available.
