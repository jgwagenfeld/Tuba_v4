# Tee and Section Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give compliance, meshing, PyVista, and the web viewer one tee-topology decision and one dependency-light source of true structural section geometry.

**Architecture:** `tuba.geometry.junctions` classifies a three-pipe node without importing compliance or Gmsh. `tuba.geometry.section_mesh` produces plain vertices and triangular faces; PyVista adapts them locally and the existing web scene emits them as its already-supported `format="mesh"` assets. `RackBay` selects sections by member role while retaining its current `section` default.

**Tech Stack:** Python 3.10+, NumPy, PyVista adapter, existing Three.js mesh renderer, unittest/pytest

**Spec:** `docs/superpowers/specs/2026-08-27-native-section-and-pipe-volume-meshing-design.md`

## Global Constraints

- Keep `tuba/plotting/` as the PyVista quick-look path and `tuba/visualization/` plus `viewer/` as the web-review path; add no third renderer.
- Keep procedural tubes for normal pipe design geometry; use mesh assets for non-pipe structural profiles and later for native volume-mesh skins.
- Do not label geometry-only output as solved, deformed, stress, displacement, reaction, or compliance output.
- Preserve current `RackBay(section=...)` callers; role-specific sections are optional overrides.
- Reuse NumPy and existing section records; add no dependency.

---

### Task 1: Neutral tee-junction classification

**Files:**
- Create: `tuba/geometry/junctions.py`
- Modify: `tuba/compliance/sif.py`
- Test: `tests/test_pipe_junctions.py`
- Test: `tests/test_compliance_b31j.py`

**Interfaces:**
- Consumes: `TubaModel.nodes`, `TubaModel.elements`, and optional selected element ids.
- Produces: `TeeJunction(header_element_ids: tuple[str, str], branch_element_id: str, directions: dict[str, tuple[float, float, float]])` and `classify_tee_junction(model, node_id, *, element_ids=None) -> TeeJunction`.

- [ ] **Step 1: Write the failing topology tests**

```python
def test_classifies_opposite_pair_as_header():
    model = tee_model((-1, 0, 0), (1, 0, 0), (0, 1, 0))
    junction = classify_tee_junction(model, "N0")
    assert set(junction.header_element_ids) == {"left", "right"}
    assert junction.branch_element_id == "branch"

def test_rejects_symmetric_wye_as_ambiguous():
    model = tee_model((1, 0, 0), (-0.5, 0.8660254, 0), (-0.5, -0.8660254, 0))
    with pytest.raises(ValueError, match="ambiguous header"):
        classify_tee_junction(model, "N0")
```

- [ ] **Step 2: Verify the tests fail because the module is absent**

Run: `uv run pytest tests/test_pipe_junctions.py -q`

Expected: FAIL importing `tuba.geometry.junctions`.

- [ ] **Step 3: Implement the classifier with a stable result record**

```python
@dataclass(frozen=True)
class TeeJunction:
    node_id: str
    header_element_ids: tuple[str, str]
    branch_element_id: str
    directions: dict[str, tuple[float, float, float]]

def classify_tee_junction(model, node_id: str, *, element_ids=None) -> TeeJunction:
    selected = None if element_ids is None else set(element_ids)
    connected = [
        element for element in model.elements
        if (element.n1 == node_id or element.n2 == node_id)
        and element.type.startswith("pipe")
        and (selected is None or element.id in selected)
    ]
    if len(connected) != 3:
        raise ValueError(f"Tee node {node_id!r} requires exactly three connected pipe elements.")
    # Normalize the three outward directions, rank the three dot products,
    # and reject a tie between the best and second-best header candidates.
```

- [ ] **Step 4: Verify topology and compliance tests pass**

Run: `uv run pytest tests/test_pipe_junctions.py tests/test_compliance_b31j.py -q`

Expected: PASS.

- [ ] **Step 5: Make compliance consume the shared header pair**

```python
junction = classify_tee_junction(model, node_id)
header_el = model.get_element(junction.header_element_ids[0])
header_section = model.sections[header_el.section]
```

Delete the duplicate direction/dot-product block and its direct NumPy dependency from `tuba/compliance/sif.py`.

- [ ] **Step 6: Commit the independently testable topology slice**

```bash
git add tuba/geometry/junctions.py tuba/compliance/sif.py tests/test_pipe_junctions.py tests/test_compliance_b31j.py
git commit -m "refactor: share tee junction classification"
```

### Task 2: Dependency-light straight section surface meshes

**Files:**
- Create: `tuba/geometry/section_mesh.py`
- Modify: `tuba/plotting/pipeline.py`
- Test: `tests/test_section_mesh.py`
- Test: `tests/test_tuba_core.py`

**Interfaces:**
- Consumes: existing `PipeSection`, `BarSection`, `CableSection`, `RectangularSection`, and `IBeamSection` records.
- Produces: `SurfaceMesh(vertices: tuple[tuple[float, float, float], ...], faces: tuple[tuple[int, int, int], ...])`, `section_loops(section, *, n_sides=16)`, and `straight_section_surface_mesh(section, start, end, *, twist_angle_deg=0.0, n_sides=16)`.

- [ ] **Step 1: Write failing profile and extrusion tests**

```python
@pytest.mark.parametrize("section", [pipe(), bar(), cable(), rhs(), ipe()])
def test_straight_section_surface_mesh_is_finite_and_indexed(section):
    mesh = straight_section_surface_mesh(section, (0, 0, 0), (2, 0, 0))
    assert len(mesh.vertices) >= 8
    assert len(mesh.faces) >= 8
    assert np.isfinite(np.asarray(mesh.vertices)).all()
    assert max(index for face in mesh.faces for index in face) < len(mesh.vertices)

def test_hollow_profiles_keep_open_voids_in_each_end_cap():
    mesh = straight_section_surface_mesh(rhs(), (0, 0, 0), (1, 0, 0))
    assert all(len(face) == 3 for face in mesh.faces)
    assert not any(point == (0.0, 0.0, 0.0) for point in mesh.vertices)
```

- [ ] **Step 2: Verify the tests fail because the module is absent**

Run: `uv run pytest tests/test_section_mesh.py -q`

Expected: FAIL importing `tuba.geometry.section_mesh`.

- [ ] **Step 3: Move the existing loop, frame, wall, and end-cap logic into the pure module**

```python
@dataclass(frozen=True)
class SurfaceMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]

def straight_section_surface_mesh(section, start, end, *, twist_angle_deg=0.0, n_sides=16):
    axis = np.asarray(end, dtype=float) - np.asarray(start, dtype=float)
    if not np.isfinite(axis).all() or np.linalg.norm(axis) <= 1.0e-12:
        raise ValueError("Section extrusion requires two distinct finite endpoints.")
    loops = section_loops(section, n_sides=n_sides)
    # Build the same local axes currently used by plotting, triangulate every
    # side quad, and triangulate solid or annular end caps.
    return SurfaceMesh(vertices=tuple(vertices), faces=tuple(faces))
```

- [ ] **Step 4: Adapt PyVista instead of duplicating straight extrusion**

```python
surface = straight_section_surface_mesh(
    sec,
    model.nodes[elem.n1].coords,
    model.nodes[elem.n2].coords,
    twist_angle_deg=getattr(elem, "twist_angle", 0.0),
)
cells = np.asarray([[3, *face] for face in surface.faces], dtype=np.int32).ravel()
mesh = pv.PolyData(np.asarray(surface.vertices), faces=cells)
```

Keep the existing sampled-bend transport path for pipe bends; do not invent bent IPE/RHS members.

- [ ] **Step 5: Verify pure geometry and existing PyVista tests**

Run: `uv run pytest tests/test_section_mesh.py tests/test_tuba_core.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the shared surface-mesh slice**

```bash
git add tuba/geometry/section_mesh.py tuba/plotting/pipeline.py tests/test_section_mesh.py tests/test_tuba_core.py
git commit -m "refactor: share section surface geometry"
```

### Task 3: Render structural members as true web meshes

**Files:**
- Modify: `tuba/visualization/builders/_objects.py`
- Test: `tests/test_visualization_builders.py`
- Test: `viewer/test/renderer.test.js`

**Interfaces:**
- Consumes: `straight_section_surface_mesh(...)` from Task 2.
- Produces: existing `GeometryAsset(format="mesh")` with `generation_config.vertices` and `generation_config.faces`; no scene-schema or renderer change.

- [ ] **Step 1: Write the failing scene-builder test**

```python
def test_structural_sections_emit_true_mesh_assets(self):
    model = structural_profile_model()
    scene = build_visualization_scene(model)
    assets = {asset.id: asset for asset in scene.geometry_assets}
    for element in model.elements:
        asset = assets[f"geometry:element:{element.id}"]
        assert asset.format == "mesh"
        assert asset.generation_config["vertices"]
        assert asset.generation_config["faces"]
```

- [ ] **Step 2: Verify it fails because beams are still `line` assets**

Run: `uv run pytest tests/test_visualization_builders.py::TestVisualizationBuilders::test_structural_sections_emit_true_mesh_assets -q`

Expected: FAIL with `line != mesh`.

- [ ] **Step 3: Emit the existing mesh contract for non-pipe straight members**

```python
if elem.type.startswith("pipe"):
    asset_format = "tube"
else:
    surface = straight_section_surface_mesh(
        model.sections[elem.section], points[0], points[-1],
        twist_angle_deg=float(getattr(elem, "twist_angle", 0.0)),
    )
    asset_format = "mesh"
    generation_config.update(
        vertices=[list(vertex) for vertex in surface.vertices],
        faces=[list(face) for face in surface.faces],
    )
```

- [ ] **Step 4: Verify Python and existing viewer mesh behavior**

Run: `uv run pytest tests/test_visualization_builders.py tests/test_visualization_web_export.py -q`

Run: `npm.cmd test -- --runInBand renderer.test.js` from `viewer/`.

Expected: both PASS; the viewer already accepts indexed `mesh` assets.

- [ ] **Step 5: Commit the web-scene slice**

```bash
git add tuba/visualization/builders/_objects.py tests/test_visualization_builders.py viewer/test/renderer.test.js
git commit -m "feat: render structural section meshes"
```

### Task 4: Role-specific RackBay sections and solved gallery refresh

**Files:**
- Modify: `tuba/assemblies.py`
- Modify: `examples/code_aster_artifact_review.py`
- Test: `tests/test_rack_assemblies.py`
- Test: `tests/test_visualization_racks.py`
- Generated by trusted solver refresh: official `support-rack-review` artifacts selected by `scripts/refresh_code_aster_gallery.py`

**Interfaces:**
- Consumes: `RackBay.section` fallback.
- Produces: optional `column_section`, `longitudinal_section`, and `transverse_section`, each defaulting to `section`.

- [ ] **Step 1: Write the failing role-assignment test**

```python
rack = RackBay(..., section="Fallback", column_section="IPEColumn",
               longitudinal_section="RHSLong", transverse_section="RHSCross")
ModelTransaction(model).apply(rack.to_patch())
by_id = {element.id: element.section for element in model.elements}
assert {value for key, value in by_id.items() if "_col_" in key} == {"IPEColumn"}
assert {value for key, value in by_id.items() if "_long_" in key} == {"RHSLong"}
assert {value for key, value in by_id.items() if "_cross_" in key} == {"RHSCross"}
```

- [ ] **Step 2: Verify the test fails on the missing keyword arguments**

Run: `uv run pytest tests/test_rack_assemblies.py -q`

Expected: FAIL with unexpected `column_section`.

- [ ] **Step 3: Add only the three optional fields and select them at creation**

```python
column_section: str | None = None
longitudinal_section: str | None = None
transverse_section: str | None = None

def add_beam(local_id, n1, n2, section):
    operations.append(AddElement(..., section=section or self.section, ...))
```

- [ ] **Step 4: Update the canonical rack model with visibly distinct sections**

```python
model.add_ibeam_section("RackColumnIPE", "IPE160")
model.add_rectangular_section("RackLongRHS", height_y=0.14, height_z=0.08,
                              thickness_y=0.008, thickness_z=0.008)
model.add_rectangular_section("RackCrossRHS", height_y=0.10, height_z=0.06,
                              thickness_y=0.006, thickness_z=0.006)
RackBay(..., section="RackLongRHS", column_section="RackColumnIPE",
        longitudinal_section="RackLongRHS", transverse_section="RackCrossRHS")
```

- [ ] **Step 5: Verify model/example tests before touching solved artifacts**

Run: `uv run pytest tests/test_rack_assemblies.py tests/test_visualization_racks.py tests/test_examples.py -q`

Expected: PASS.

- [ ] **Step 6: Refresh the support-rack artifacts with real Code_Aster**

Run: `uv run python scripts/refresh_code_aster_gallery.py --help` and select the documented support-rack-only option if available; otherwise run the script's documented full official refresh.

Expected: the refresh invokes real Code_Aster, records a solve attestation, and replaces no artifact with export-only data.

- [ ] **Step 7: Verify assembled Pages and browser-visible section variation**

Run: `uv run python scripts/build_pages.py pages --output .build/pages-section-review`

Run the repository's Pages E2E test against `.build/pages-section-review` and inspect an IPE column, both RHS roles, and the circular process pipe.

Expected: all four authored profiles are distinct and the selected-object metadata contains their section names/dimensions.

- [ ] **Step 8: Commit model, tests, and genuinely refreshed artifacts**

```bash
git add tuba/assemblies.py examples/code_aster_artifact_review.py tests/test_rack_assemblies.py tests/test_visualization_racks.py <paths printed by the trusted refresh>
git commit -m "feat: vary support rack sections"
```
