# Native Pipe Volume Meshing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate grouped quadratic Gmsh MED meshes for selected straight hollow pipes and explicit tees, then solve verified 3D Code_Aster reference cases through Tuba's existing result pipeline.

**Architecture:** `tuba.meshing.pipe_volume` directly uses the already-installed Gmsh OCC API; there is no backend abstraction or SALOME requirement. Geometry is built as outer unions minus bore unions, classified by coordinates/radii/adjacency rather than face tag order, and returned with an `AnalysisMesh` plus a surface skin. `CodeAsterSolver` calls a small `aster_volume` compiler only for an explicit typed solid choice; `TUYAU_3M` remains the default.

**Tech Stack:** Python 3.10+, Gmsh >=4.11, meshio, NumPy, Code_Aster 18, existing analysis/result/viewer contracts

**Spec:** `docs/superpowers/specs/2026-08-27-native-section-and-pipe-volume-meshing-design.md`

## Global Constraints

- Gmsh is the primary and only implemented backend; do not require SALOME-Meca and do not add a one-implementation mesher interface.
- Accept only selected `pipe_straight` elements and explicit equal/reducing tees with circular `PipeSection` records.
- Reject bends, generic reducers, valves, flanges, shells, contacts, and pad solids before writing MED.
- Require `element_order=2` and an engineer-supplied positive `max_element_size` no larger than half the thinnest selected wall.
- Create non-empty stable groups `G_SOLID_<region>`, `G_INNER_<region>`, `G_OUTER_<region>`, `G_END_<node>`, and `G_TEE_<node>` through the existing Code_Aster name mapper.
- A mesh is analysis input only. Do not display stress/displacement/reaction until real Code_Aster artifacts were solved, attested, and imported.
- Preserve caller-owned Gmsh sessions; remove only the model created by Tuba and finalize only when Tuba initialized Gmsh.

---

### Task 1: Straight hollow pipe OCC mesh and readback

**Files:**
- Create: `tuba/meshing/__init__.py`
- Create: `tuba/meshing/pipe_volume.py`
- Test: `tests/test_pipe_volume_mesh.py`

**Interfaces:**
- Consumes: `build_pipe_volume_mesh(model, output_path, element_ids, max_element_size, element_order=2)`.
- Produces: `GeneratedPipeVolumeMesh(analysis_mesh, groups, surface_vertices, surface_faces, gmsh_version, settings, med_path)`.

- [ ] **Step 1: Write failing validation and straight-pipe integration tests**

```python
generated = build_pipe_volume_mesh(
    straight_pipe_model(), tmp_path / "straight.med",
    element_ids=["pipe_0"], max_element_size=0.004, element_order=2,
)
assert generated.med_path.is_file()
assert generated.analysis_mesh.modelisations == {"G_SOLID_region_0": "3D"}
for name in ("G_SOLID_region_0", "G_INNER_region_0", "G_OUTER_region_0", "G_END_N0", "G_END_N1"):
    assert generated.groups[name]
mesh = meshio.read(generated.med_path)
assert any(block.type == "tetra10" for block in mesh.cells)
```

Also assert `element_order=1`, coarse wall resolution, non-straight selections, and missing Gmsh fail before a non-empty MED file exists.

- [ ] **Step 2: Verify the tests fail because the meshing package is absent**

Run: `uv run pytest tests/test_pipe_volume_mesh.py -q`

Expected: FAIL importing `tuba.meshing`.

- [ ] **Step 3: Implement the minimal public result and preflight**

```python
@dataclass(frozen=True)
class GeneratedPipeVolumeMesh:
    analysis_mesh: AnalysisMesh
    groups: dict[str, tuple[str, ...]]
    surface_vertices: tuple[tuple[float, float, float], ...]
    surface_faces: tuple[tuple[int, int, int], ...]
    gmsh_version: str
    settings: dict[str, Any]
    med_path: Path

def build_pipe_volume_mesh(model, output_path, *, element_ids, max_element_size, element_order=2):
    if element_order != 2:
        raise ValueError("Native pipe volume meshes require element_order=2.")
    # Resolve exact elements, validate sections/material/connectivity, and reject
    # max_element_size > min(section.WT) / 2 before initializing Gmsh.
```

- [ ] **Step 4: Build one OCC hollow cylinder and classify its surfaces geometrically**

```python
outer = gmsh.model.occ.addCylinder(*start, *direction, section.OD / 2.0)
inner = gmsh.model.occ.addCylinder(*start, *direction, section.ID / 2.0)
cut, _ = gmsh.model.occ.cut([(3, outer)], [(3, inner)], removeObject=True, removeTool=True)
gmsh.model.occ.synchronize()
```

Classify the two planar end faces by center-of-mass distance to the selected endpoint planes. Classify cylindrical faces by radius/adjacency using OCC mass and bounding boxes; require non-empty disjoint inner/outer sets.

- [ ] **Step 5: Add stable physical groups, mesh settings, MED write, and readback**

```python
gmsh.model.addPhysicalGroup(3, volume_tags, name=solver_name("G_SOLID_region_0"))
gmsh.option.setNumber("Mesh.MeshSizeMax", max_element_size)
gmsh.option.setNumber("Mesh.ElementOrder", 2)
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 20)
gmsh.model.mesh.generate(3)
gmsh.model.mesh.setOrder(2)
gmsh.write(str(med_path))
```

Use Gmsh node/element queries to populate `AnalysisMesh`; source every cell to `EntityRef("element", "pipe_0")`, and extract the visible skin from the classified boundary triangles.

- [ ] **Step 6: Verify MED content, groups, skin, and lifecycle**

Run: `uv run pytest tests/test_pipe_volume_mesh.py -q`

Expected: PASS with a non-empty `tetra10` block, finite skin, required groups, and caller-owned Gmsh still initialized.

- [ ] **Step 7: Commit the straight-pipe mesher**

```bash
git add tuba/meshing/__init__.py tuba/meshing/pipe_volume.py tests/test_pipe_volume_mesh.py
git commit -m "feat: mesh straight pipe solids with gmsh"
```

### Task 2: Equal/reducing tee boolean geometry and conformal connection

**Files:**
- Modify: `tuba/meshing/pipe_volume.py`
- Test: `tests/test_pipe_volume_mesh.py`

**Interfaces:**
- Consumes: `classify_tee_junction(...)` from the tee/section plan and explicit `model.tees[node_id]`.
- Produces: the same `GeneratedPipeVolumeMesh`, now with `G_TEE_<node>` and one conformal solid region across three selected runs.

- [ ] **Step 1: Write failing equal-tee and reducing-tee tests**

```python
@pytest.mark.parametrize("branch_od", [0.1, 0.06])
def test_meshes_conformal_explicit_tee(tmp_path, branch_od):
    model = tee_model(branch_od=branch_od)
    generated = build_pipe_volume_mesh(model, tmp_path / "tee.med",
        element_ids=["left", "right", "branch"], max_element_size=0.004)
    assert generated.groups["G_TEE_N0"]
    assert generated.groups["G_SOLID_region_0"]
    assert {"G_END_N1", "G_END_N2", "G_END_N3"} <= generated.groups.keys()
    assert connected_tetra_component_count(generated.analysis_mesh) == 1
```

- [ ] **Step 2: Verify the tests fail because only isolated straight selections work**

Run: `uv run pytest tests/test_pipe_volume_mesh.py -k tee -q`

Expected: FAIL with unsupported three-way selection.

- [ ] **Step 3: Fuse outer cylinders, fuse bores, then cut once**

```python
outer_union, _ = gmsh.model.occ.fuse([outer_dims[0]], outer_dims[1:], removeObject=True, removeTool=True)
bore_union, _ = gmsh.model.occ.fuse([bore_dims[0]], bore_dims[1:], removeObject=True, removeTool=True)
wall, lineage = gmsh.model.occ.cut(outer_union, bore_union, removeObject=True, removeTool=True)
gmsh.model.occ.synchronize()
```

Use the shared classifier to reject ambiguous topology and reject any three-way node without `model.tees[node_id]`.

- [ ] **Step 4: Classify tee provenance and terminal groups after booleans**

Use terminal planes for `G_END_*`, bore-distance samples for `G_INNER_*`, remaining boundary surfaces for `G_OUTER_*`, and the post-boolean volume(s) adjacent to the junction for `G_TEE_*`. Require one connected tetrahedral component.

- [ ] **Step 5: Verify equal/reducing tees and invalid fitting failures**

Run: `uv run pytest tests/test_pipe_volume_mesh.py -q`

Expected: PASS for both tees and explicit preflight failures for bends, absent tee records, non-pipe sections, and mixed materials.

- [ ] **Step 6: Commit the tee mesher**

```bash
git add tuba/meshing/pipe_volume.py tests/test_pipe_volume_mesh.py
git commit -m "feat: mesh native pipe tee solids"
```

### Task 3: Expose the authoritative volume-mesh skin in the web scene

**Files:**
- Modify: `tuba/visualization/builders/_core.py`
- Modify: `tuba/visualization/builders/_states.py`
- Modify: `tuba/analysis/mesh.py`
- Test: `tests/test_visualization_analysis_mesh.py`

**Interfaces:**
- Consumes: `GeneratedPipeVolumeMesh.analysis_mesh.surface_mesh`.
- Produces: existing analysis-mesh `SceneObject`/`GeometryAsset(format="mesh")`, separate from procedural design tubes and solver-result overlays.

- [ ] **Step 1: Write a failing analysis-mesh skin test**

```python
scene = build_visualization_scene(model, analysis_meshes=[generated.analysis_mesh])
asset = next(a for a in scene.geometry_assets if a.id == "geometry:analysis_mesh:volume:region_0")
assert asset.format == "mesh"
assert asset.generation_config["vertices"]
assert asset.generation_config["faces"]
assert not any("solver_result" in layer for layer in scene.objects_by_asset(asset.id).layer_ids)
```

- [ ] **Step 2: Verify it fails on the current line/tetra projection**

Run: `uv run pytest tests/test_visualization_analysis_mesh.py -q`

Expected: FAIL finding the volume skin asset.

- [ ] **Step 3: Adapt volume boundary faces to the existing mesh format**

Add an optional, serialized `surface_mesh` field to `AnalysisMesh`. The native
mesher sets it; existing analysis meshes default to `None` and keep their current
line/sub-point projection.

```python
surface_mesh: dict[str, Any] | None = None

GeometryAsset(id=asset_id, format="mesh", bounds=bounds, object_ids=[object_id],
              generation_config={"source": "tuba.analysis_mesh.volume_skin",
                                 "vertices": analysis_mesh.surface_mesh["vertices"],
                                 "faces": analysis_mesh.surface_mesh["faces"]})
```

- [ ] **Step 4: Verify scene serialization and viewer rendering**

Run: `uv run pytest tests/test_visualization_analysis_mesh.py tests/test_visualization_web_export.py -q`

Run: `npm.cmd test -- --runInBand renderer.test.js` from `viewer/`.

Expected: PASS.

- [ ] **Step 5: Commit the analysis-skin slice**

```bash
git add tuba/analysis/mesh.py tuba/visualization/builders/_core.py tuba/visualization/builders/_states.py tests/test_visualization_analysis_mesh.py
git commit -m "feat: review native pipe volume meshes"
```

### Task 4: Typed modelization and volume-specific Code_Aster study

**Files:**
- Modify: `tuba/solver/modelisation.py`
- Create: `tuba/solver/aster_volume.py`
- Modify: `tuba/solver/aster.py`
- Modify: `tuba/model.py`
- Modify: `tuba/analysis/provenance.py`
- Test: `tests/test_code_aster_volume_study.py`

**Interfaces:**
- Produces: `PipeModelization(Enum)` with `TUYAU_3M` and `SOLID_3D`; explicit `CodeAsterSolver.export_volume_study(...)` until reference validation permits wiring `model.solve(...)`.
- Consumes: generated MED/groups plus the existing material, operation, name-map, sidecar, `AnalysisStudy`, runtime, and import machinery.

- [ ] **Step 1: Write the failing compiler-contract test**

```python
study = CodeAsterSolver(work_dir=tmp_path).export_volume_study(
    model, "Operating", tmp_path,
    element_ids=["pipe_0"], max_element_size=0.004,
)
comm = Path(study.input_files["comm"]).read_text()
assert "MODELISATION='3D'" in comm
assert "GROUP_MA='G_SOLID" in comm
assert "PRES_REP=_F(GROUP_MA='G_INNER" in comm
assert study.metadata["result_status"] == "export_only"
```

- [ ] **Step 2: Verify the test fails on the missing API**

Run: `uv run pytest tests/test_code_aster_volume_study.py -q`

Expected: FAIL with missing `export_volume_study`.

- [ ] **Step 3: Add the typed choice without changing defaults**

```python
class PipeModelization(str, Enum):
    TUYAU_3M = "TUYAU_3M"
    SOLID_3D = "3D"
```

Keep `modelisation_assignments(model)` unchanged for existing calls.

- [ ] **Step 4: Compile the minimum 3D Code_Aster command blocks**

`aster_volume.py` must emit `LIRE_MAILLAGE(FORMAT='MED')`, `AFFE_MODELE(...MODELISATION='3D')`, `DEFI_MATERIAU`, `AFFE_MATERIAU`, endpoint constraints, `AFFE_CHAR_MECA(PRES_REP=...)`, `MECA_STATIQUE`, `CALC_CHAMP`, `.rmed` output, displacement/reaction/stress tables, and `FIN()` using the existing line-writer/name-map helpers.

```python
PRESSURE = AFFE_CHAR_MECA(
    MODELE=MODELE,
    PRES_REP=_F(GROUP_MA='G_INNER_region_0', PRES=pressure),
)
```

- [ ] **Step 5: Verify export contract and unchanged TUYAU studies**

Run: `uv run pytest tests/test_code_aster_volume_study.py tests/test_code_aster_study.py -q`

Expected: PASS; existing studies still assign `TUYAU_3M`.

- [ ] **Step 6: Commit the explicit volume-study exporter**

```bash
git add tuba/solver/modelisation.py tuba/solver/aster_volume.py tuba/solver/aster.py tuba/analysis/provenance.py tests/test_code_aster_volume_study.py
git commit -m "feat: export code aster pipe volume studies"
```

### Task 5: Real straight-pipe Lame reference solve

**Files:**
- Create: `tests/integration/test_code_aster_pipe_volume_reference.py`
- Modify: `tuba/solver/aster.py` only if real-result import exposes a concrete 3D parsing gap

**Interfaces:**
- Consumes: `CodeAsterSolver.export_volume_study`, existing runtime doctor/runner, and existing artifact import.
- Produces: a verified `AnalysisRun`/`ResultState` from a real Code_Aster solve at two mesh sizes.

- [ ] **Step 1: Write the integration reference with independent Lame values**

```python
def lame_hoop_stress(p, ri, ro, r):
    a = p * ri**2 / (ro**2 - ri**2)
    b = p * ri**2 * ro**2 / (ro**2 - ri**2)
    return a + b / r**2

@pytest.mark.integration
@pytest.mark.parametrize("max_size", [0.004, 0.003])
def test_real_pressurized_pipe_matches_lame_away_from_ends(max_size, tmp_path):
    run = solve_real_volume_pipe(tmp_path, max_size=max_size)
    assert run.result_state.metadata["solve_attestation"]
    assert run.result_state.solver_input_identity == run.study.solver_input_identity
    assert relative_error(run.midspan_inner_hoop_stress, expected_lame) < 0.10
```

- [ ] **Step 2: Verify the test either fails on a real integration gap or blocks loudly on runtime setup**

Run: `uv run python -m tuba.solver.code_aster_doctor --check`

Run: `uv run pytest tests/integration/test_code_aster_pipe_volume_reference.py -q`

Expected: Code_Aster runs; no export-only fallback is accepted.

- [ ] **Step 3: Repair only observed 3D result import gaps**

If Code_Aster's 3D table shape differs from TUYAU output, add a volume-specific parser keyed by the study's compiler id. Preserve CSV-authoritative parsing and keep `.rmed` loading explicit.

- [ ] **Step 4: Re-run both meshes and the existing real smoke**

Run: `uv run pytest tests/integration/test_code_aster_pipe_volume_reference.py tests/integration/test_code_aster_real_smoke.py -q`

Expected: both mesh sizes meet the stated error bound, carry attestations/identities, and existing TUYAU smoke remains green.

- [ ] **Step 5: Enable the explicit public solve choice only after reference success**

```python
model.solve(operation="Operating", pipe_modelization=PipeModelization.SOLID_3D,
            volume_element_ids=["pipe_0"], max_element_size=0.004)
```

Unknown or incomplete solid selections must fail before export.

- [ ] **Step 6: Commit the verified reference path**

```bash
git add tests/integration/test_code_aster_pipe_volume_reference.py tuba/solver/aster.py tuba/model.py
git commit -m "feat: solve verified pipe volume studies"
```

### Task 6: Real tee result bundle and publication gate

**Files:**
- Create: `examples/code_aster_tee_volume_review.py`
- Create: `tests/integration/test_code_aster_tee_volume_reference.py`
- Modify: `scripts/refresh_code_aster_gallery.py`
- Modify: official gallery catalog inputs selected by the refresh script
- Test: `tests/test_examples.py`
- Test: `tests/test_official_viewer_publication.py`
- Test: browser E2E files used by the assembled Pages gate

**Interfaces:**
- Consumes: real volume solve/import, analysis-mesh skin, and existing `write_engineering_review_with_scene`.
- Produces: a solved, attested tee review bundle whose FE VMIS is explicitly not piping-code stress/compliance.

- [ ] **Step 1: Write the failing example/publication assertions**

```python
assert summary["result_status"] == "solved"
assert summary["stress_label"] == "FE VMIS (not code stress)"
assert summary["analysis_mesh_kind"] == "native_pipe_volume"
assert Path(summary["bundle_root"], "scene.json").is_file()
```

- [ ] **Step 2: Verify no current official tee volume bundle satisfies them**

Run: `uv run pytest tests/test_examples.py tests/test_official_viewer_publication.py -q`

Expected: FAIL on the absent tee example/catalog entry.

- [ ] **Step 3: Build the example only from real imported solver artifacts**

Use the same artifact-evidence staging and solver-input identity checks as `examples/code_aster_artifact_review.py`. If artifacts are absent or stale, raise the Code_Aster/setup blocker before scene/result creation.

- [ ] **Step 4: Add the trusted refresh path and solve at two tee mesh sizes**

The refresh must run Code_Aster, require stable reactions and stress-location convergence, record the chosen mesh/quality settings, then write the canonical bundle. It must never accept `.comm`, `.med`, or `.export` generation as completion.

- [ ] **Step 5: Verify Python, viewer, real solver, Pages, and browser gates**

Run: `uv run pytest -q`

Run: `npm.cmd test` from `viewer/`.

Run: `uv run pytest tests/integration/test_code_aster_pipe_volume_reference.py tests/integration/test_code_aster_tee_volume_reference.py -q`.

Run: `uv run python scripts/build_pages.py pages --output .build/pages-volume-review` followed by the repository's Pages E2E test.

Expected: all pass; the browser distinguishes design tube, analysis volume skin, applied pressure input, and real solver result overlays.

- [ ] **Step 6: Commit the solved tee gallery and release proof**

```bash
git add examples/code_aster_tee_volume_review.py scripts/refresh_code_aster_gallery.py tests <trusted refreshed artifact and catalog paths>
git commit -m "feat: publish solved pipe tee volume review"
```
