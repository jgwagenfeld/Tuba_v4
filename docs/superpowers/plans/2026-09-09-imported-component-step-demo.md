# Imported Component STEP Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `imported_component_mixed_demo` gallery entry demonstrate a real pipe-to-solid coupling — a meshed STEP volume with a detected port face — instead of an STL tetrahedron that contributes nothing to the analysis.

**Architecture:** Six library and example changes plus one viewer change. The STEP importer stops hardcoding port axes and starts deriving them from planar face normals; it gains a display tessellation so imported components render as themselves; validation gains a geometric anchor tying a port to its asset; the example imports its asset for real instead of hand-writing metadata; and the viewer's existing `i` key learns to name the imported-component marks it already draws.

**Tech Stack:** Python 3.12, gmsh (OCC kernel), numpy, pytest; Three.js viewer with `node --test`; uv for Python execution.

**Spec:** `docs/superpowers/specs/2026-09-09-imported-component-step-demo-design.md`

## Global Constraints

- **The mixed study stays export-only.** `MixedCodeAsterStudyExporter.RESULT_STATUS` remains `"export_only"`, `RUNTIME_BLOCKER` is unchanged, and the scene keeps its `publication.model_review.no_solver_results` diagnostic. No task may claim a solve. (`AGENTS.md`: export-only paths are development and diagnostic surfaces only.)
- **No fabricated values presented as solver results.** (`AGENTS.md`)
- **Backward compatibility is not a constraint.** Task 4 breaks models with off-asset ports by design. When a fixture fails, correct the fixture's geometry — never loosen the check to admit it.
- **Nothing hardcodes a gmsh face tag.** Tags renumber across a STEP write/read round trip (verified: the port face is tag 10 when generated, tag 5 when re-imported). Selection is by radius and position only.
- **Display-mesh vertex cap:** 5000, matching the existing STL cap.
- **Windows:** `uv run` invocations of the page build need `UV_NO_SYNC=1` — a nested `uv run` swaps numpy while its DLL is loaded.
- **gmsh needs native paths.** Pass `str(Path(...))`, never an MSYS `/c/...` path; gmsh is a native binary and fails to create the file.
- **Commit attribution:** every commit message ends with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`

---

### Task 1: Planar port-face detection with a normal-derived axis

Detection today proposes a candidate for *every* boundary face, derives radius from a bounding box, and hardcodes `axis = [1.0, 0.0, 0.0]`. On a cylinder lateral the "radius" is half the face length and the sampled normal is an arbitrary surface point. Filter to planar faces, and take the axis from the face normal oriented outward.

**Files:**
- Modify: `tuba/geometry/step_analysis_importer.py:118-167` (`_detect_port_candidates`)
- Test: `tests/test_step_analysis_importer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_detect_port_candidates(imported)` returns candidates whose `axis` is the outward unit face normal and which are restricted to planar faces. Candidate dict shape is unchanged: `{"id": str, "kind": "circular_face", "position": [float, float, float], "axis": [float, float, float], "radius": float, "face_group": str, "metadata": {"gmsh_face_tag": int}}`. New static helper `StepAnalysisImporter._outward_face_axis(face_tag: int, face_center: list[float], solid_center: Any) -> list[float]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_step_analysis_importer.py`. This builds the real demo solid so the test exercises OCC geometry rather than a mock:

```python
import gmsh as gmsh_module

from tuba.meshing._gmsh import gmsh_model


def _write_nozzle_step(path: Path) -> Path:
    """A vessel with a bored nozzle stub; the stub end face is the port."""
    with gmsh_model(gmsh_module, "test_nozzle"):
        outer = gmsh_module.model.occ.addCylinder(0, 0, 0, 0.16, 0, 0, 0.05)
        bore = gmsh_module.model.occ.addCylinder(-0.01, 0, 0, 0.18, 0, 0, 0.042)
        vessel = gmsh_module.model.occ.addCylinder(0.16, 0, 0, 0.24, 0, 0, 0.15)
        fused, _ = gmsh_module.model.occ.fuse([(3, outer)], [(3, vessel)])
        gmsh_module.model.occ.cut(fused, [(3, bore)])
        gmsh_module.model.occ.synchronize()
        gmsh_module.write(str(path))
    return path


def test_detection_proposes_only_planar_faces_with_outward_axes(tmp_path: Path):
    step_path = _write_nozzle_step(tmp_path / "nozzle.step")
    model = Model(project_name="Nozzle detection")

    StepAnalysisImporter().import_component(
        model,
        step_path,
        id="component_nozzle",
        asset_id="cad_asset_nozzle",
    )

    # Seven faces, four of them planar. The three cylinder laterals must not be
    # proposed: a pipe cannot land on one, and their bbox "radius" is half a
    # face length.
    assert len(model.ports) == 4

    ports = list(model.ports.values())
    stub_end = [port for port in ports if abs(port.radius - 0.05) < 1e-6]
    assert len(stub_end) == 1, "the stub end annulus is the only 0.05 m face"

    port = stub_end[0]
    assert port.position == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    # Outward from a solid that lies at +x, so the axis points back down the pipe.
    assert port.axis == pytest.approx((-1.0, 0.0, 0.0), abs=1e-9)
    assert isinstance(port.metadata["gmsh_face_tag"], int)

    # Every axis is a unit vector, and none is the old hardcoded default on a
    # face whose true normal is -x.
    for candidate in ports:
        assert sum(value * value for value in candidate.axis) == pytest.approx(1.0, abs=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_step_analysis_importer.py::test_detection_proposes_only_planar_faces_with_outward_axes -v`

Expected: FAIL — 7 ports instead of 4 (laterals are proposed), and the stub-end axis is `(1.0, 0.0, 0.0)` from the hardcoded default rather than `(-1.0, 0.0, 0.0)`.

- [ ] **Step 3: Write the implementation**

Replace `_detect_port_candidates` in `tuba/geometry/step_analysis_importer.py` with:

```python
    def _detect_port_candidates(self, imported: list[tuple[int, int]] | None) -> list[dict[str, Any]]:
        if gmsh is None:
            return []
        if not imported:
            return []

        candidates: list[dict[str, Any]] = []
        seen_face_tags: set[int] = set()

        for entity in imported:
            try:
                dim, tag = entity
            except (TypeError, ValueError):
                continue
            if dim != 3:
                continue
            try:
                faces = gmsh.model.getBoundary([(dim, tag)], oriented=False, recursive=False)
            except Exception:
                continue
            try:
                solid_center = gmsh.model.occ.getCenterOfMass(dim, tag)
            except Exception:
                solid_center = None

            for boundary_dim, raw_face_tag in faces:
                face_tag = abs(int(raw_face_tag))
                if boundary_dim != 2 or face_tag in seen_face_tags:
                    continue
                # A pipe lands on a flat face. On a curved one the bounding box
                # is not a radius - on a cylinder lateral it is half the face
                # length - and a normal sampled at the parametric midpoint is an
                # arbitrary point on the surface. A confident wrong number is
                # worse than no candidate.
                try:
                    if gmsh.model.getType(boundary_dim, face_tag) != "Plane":
                        continue
                except Exception:
                    continue
                try:
                    x_min, y_min, z_min, x_max, y_max, z_max = gmsh.model.getBoundingBox(
                        boundary_dim,
                        face_tag,
                    )
                except Exception:
                    continue

                seen_face_tags.add(face_tag)
                radius = max(x_max - x_min, y_max - y_min, z_max - z_min) / 2.0
                if radius <= 0.0:
                    radius = 1e-6
                position = [
                    (x_min + x_max) / 2.0,
                    (y_min + y_max) / 2.0,
                    (z_min + z_max) / 2.0,
                ]

                index = len(candidates)
                candidates.append(
                    {
                        "id": f"port_candidate_{index}",
                        "kind": "circular_face",
                        "position": position,
                        "axis": self._outward_face_axis(face_tag, position, solid_center),
                        "radius": float(radius),
                        "face_group": f"G_PORT_CANDIDATE_{index}",
                        "metadata": {"gmsh_face_tag": face_tag},
                    }
                )

        return candidates

    @staticmethod
    def _outward_face_axis(
        face_tag: int,
        face_center: list[float],
        solid_center: Any,
    ) -> list[float]:
        """The face normal, flipped to point away from the solid it bounds.

        OCC orients a face however the modelling history left it, so the raw
        normal's sign says nothing about which side the material is on. A port
        axis has to point away from the equipment and back down the pipe.
        """
        default = [1.0, 0.0, 0.0]
        if gmsh is None:
            return default
        try:
            parametric_min, parametric_max = gmsh.model.getParametrizationBounds(2, face_tag)
            u = (float(parametric_min[0]) + float(parametric_max[0])) / 2.0
            v = (float(parametric_min[1]) + float(parametric_max[1])) / 2.0
            normal = [float(value) for value in gmsh.model.getNormal(face_tag, [u, v])]
        except Exception:
            return default
        length = sum(value * value for value in normal) ** 0.5
        if length <= 1e-12:
            return default
        normal = [value / length for value in normal]
        if solid_center is None:
            return normal
        # ponytail: centroid heuristic; use a ray cast if a concave solid ever
        # puts its centre of mass on the wrong side of one of its own faces.
        outward = [float(face_center[index]) - float(solid_center[index]) for index in range(3)]
        if sum(a * b for a, b in zip(normal, outward)) < 0.0:
            normal = [-value for value in normal]
        return normal
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_step_analysis_importer.py -v`
Expected: PASS, including the three pre-existing tests in that file.

- [ ] **Step 5: Commit**

```bash
git add tuba/geometry/step_analysis_importer.py tests/test_step_analysis_importer.py
git commit -m "feat(step): derive port axes from planar face normals

Detection proposed a candidate per boundary face with a hardcoded [1,0,0] axis.
On a cylinder lateral the bbox radius is half the face length and the sampled
normal is an arbitrary surface point, so the automatic path produced confident
wrong numbers and callers hand-wrote their ports instead.

Filter to planar faces and take the axis from the face normal, flipped outward
against the solid centroid.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `import_component` accepts placement and metadata

`import_component` cannot place an asset or carry metadata, so a caller that needs either must abandon auto-detection and call `record_component_from_metadata` by hand. Task 3 needs `metadata` to store its tessellation; Task 5 needs `placement`.

**Files:**
- Modify: `tuba/geometry/step_analysis_importer.py:25-57` (`import_component`)
- Test: `tests/test_step_analysis_importer.py`

**Interfaces:**
- Consumes: `_write_nozzle_step(path)` from Task 1's test module.
- Produces: `import_component(model, file_path, *, id, asset_id="cad_asset_0", role="equipment", unit_scale_to_m=1.0, placement: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None)`. `placement` and `metadata` pass straight through to `record_component_from_metadata`, which already accepts both.

- [ ] **Step 1: Write the failing test**

```python
def test_import_component_records_placement_and_metadata(tmp_path: Path):
    step_path = _write_nozzle_step(tmp_path / "nozzle.step")
    model = Model(project_name="Placed nozzle")
    placement = {"origin": [1.2, 0.45, 0.0], "rotation": [1.0, 0.0, 0.0, 0.0]}

    StepAnalysisImporter().import_component(
        model,
        step_path,
        id="component_placed",
        asset_id="cad_asset_placed",
        placement=placement,
        metadata={"source_format": "STEP"},
    )

    asset = model.cad_assets["cad_asset_placed"]
    assert asset.placement == placement
    assert asset.metadata["source_format"] == "STEP"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_step_analysis_importer.py::test_import_component_records_placement_and_metadata -v`
Expected: FAIL with `TypeError: import_component() got an unexpected keyword argument 'placement'`

- [ ] **Step 3: Write the implementation**

In `tuba/geometry/step_analysis_importer.py`, change the signature and the pass-through:

```python
    def import_component(
        self,
        model: TubaModel,
        file_path: str | Path,
        *,
        id: str,
        asset_id: str = "cad_asset_0",
        role: str = "equipment",
        unit_scale_to_m: float = 1.0,
        placement: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"STEP file not found: {path}")

        if gmsh is None:
            raise StepImportError("gmsh is required to import STEP files for mixed analysis.")

        with gmsh_model(gmsh, f"tuba_step_{id}"):
            imported = gmsh.model.occ.importShapes(str(path))
            gmsh.model.occ.synchronize()

            ports = self._detect_port_candidates(imported)
            digest = self._compute_digest(path)
            return self.record_component_from_metadata(
                model,
                source_path=path,
                component_id=id,
                asset_id=asset_id,
                role=role,
                unit_scale_to_m=unit_scale_to_m,
                placement=placement,
                content_digest=digest,
                metadata=dict(metadata or {}),
                ports=ports,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_step_analysis_importer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tuba/geometry/step_analysis_importer.py tests/test_step_analysis_importer.py
git commit -m "feat(step): let import_component place and annotate the asset

Without these a caller needing a placement had to abandon auto-detection and
hand-write the whole component.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: STEP display tessellation and derived local bounds

`tuba/visualization/builders/_imported.py:222` reads `mesh_vertices_local`/`mesh_faces` from asset metadata and otherwise draws a box from `local_bounds`. Only an example fills that seam today, and only for STL — so every imported STEP component in every scene renders as a featureless block.

**Files:**
- Modify: `tuba/geometry/step_analysis_importer.py` (`import_component`, plus a new static helper)
- Test: `tests/test_step_analysis_importer.py`

**Interfaces:**
- Consumes: `import_component(..., metadata=...)` from Task 2; `_write_nozzle_step(path)` from Task 1's test module.
- Produces: `StepAnalysisImporter._display_mesh_metadata() -> dict[str, Any]`, returning `{}` or a dict with keys `mesh_vertices_local: list[list[float]]`, `mesh_faces: list[list[int]]`, `local_bounds: list[float]` (6 values, `[x_min, y_min, z_min, x_max, y_max, z_max]`). Called inside an open gmsh model, **after** port detection. Class constants `DISPLAY_MESH_VERTEX_CAP = 5000` and `DISPLAY_MESH_SIZE_FACTOR = 4.0`.

- [ ] **Step 1: Write the failing test**

```python
def test_step_import_stores_a_display_mesh_and_local_bounds(tmp_path: Path):
    step_path = _write_nozzle_step(tmp_path / "nozzle.step")
    model = Model(project_name="Display mesh")

    StepAnalysisImporter().import_component(
        model,
        step_path,
        id="component_display",
        asset_id="cad_asset_display",
    )

    metadata = model.cad_assets["cad_asset_display"].metadata
    vertices = metadata["mesh_vertices_local"]
    faces = metadata["mesh_faces"]

    assert 3 <= len(vertices) <= 5000
    assert all(len(vertex) == 3 for vertex in vertices)
    assert faces and all(len(face) == 3 for face in faces)
    assert all(0 <= index < len(vertices) for face in faces for index in face)

    # The nozzle spans x 0 -> 0.40, and the vessel radius is 0.15.
    bounds = metadata["local_bounds"]
    assert len(bounds) == 6
    assert bounds[0] == pytest.approx(0.0, abs=1e-3)
    assert bounds[3] == pytest.approx(0.40, abs=1e-3)
    assert bounds[4] == pytest.approx(0.15, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_step_analysis_importer.py::test_step_import_stores_a_display_mesh_and_local_bounds -v`
Expected: FAIL with `KeyError: 'mesh_vertices_local'`

- [ ] **Step 3: Write the implementation**

Add the constants to the class body of `StepAnalysisImporter`, directly under the docstring:

```python
    #: The scene builder falls back to a box past this, which is the honest
    #: outcome - a review viewer does not need a million-triangle asset.
    DISPLAY_MESH_VERTEX_CAP = 5000
    DISPLAY_MESH_SIZE_FACTOR = 4.0
```

Add the helper as a static method on the class:

```python
    @staticmethod
    def _display_mesh_metadata() -> dict[str, Any]:
        """A coarse surface tessellation for the review viewer, in local coords.

        Placement is applied downstream by the scene builder, so these stay in
        the STEP's own frame. Without them every imported STEP component renders
        as a featureless box.
        """
        if gmsh is None:
            return {}
        try:
            gmsh.option.setNumber(
                "Mesh.MeshSizeFactor",
                StepAnalysisImporter.DISPLAY_MESH_SIZE_FACTOR,
            )
            gmsh.model.mesh.generate(2)
            node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
            element_types, _, nodes_by_type = gmsh.model.mesh.getElements(2)
        except Exception:
            return {}

        vertices = [
            [
                float(coordinates[index * 3]),
                float(coordinates[index * 3 + 1]),
                float(coordinates[index * 3 + 2]),
            ]
            for index in range(len(node_tags))
        ]
        if len(vertices) < 3:
            return {}

        bounds = [
            min(vertex[0] for vertex in vertices),
            min(vertex[1] for vertex in vertices),
            min(vertex[2] for vertex in vertices),
            max(vertex[0] for vertex in vertices),
            max(vertex[1] for vertex in vertices),
            max(vertex[2] for vertex in vertices),
        ]
        # One coarsening pass, no retry loop - this is a display mesh.
        if len(vertices) > StepAnalysisImporter.DISPLAY_MESH_VERTEX_CAP:
            return {"local_bounds": bounds}

        index_by_tag = {int(tag): index for index, tag in enumerate(node_tags)}
        faces: list[list[int]] = []
        for element_type, tags in zip(element_types, nodes_by_type):
            if int(element_type) != 2:  # 2 == 3-node triangle
                continue
            for start in range(0, len(tags), 3):
                triangle = [index_by_tag.get(int(tags[start + offset])) for offset in range(3)]
                if any(index is None for index in triangle):
                    continue
                faces.append([int(index) for index in triangle])
        if not faces:
            return {"local_bounds": bounds}
        return {
            "mesh_vertices_local": vertices,
            "mesh_faces": faces,
            "local_bounds": bounds,
        }
```

In `import_component`, tessellate after detection and merge into the caller's metadata. Replace the body inside the `with gmsh_model(...)` block:

```python
        with gmsh_model(gmsh, f"tuba_step_{id}"):
            imported = gmsh.model.occ.importShapes(str(path))
            gmsh.model.occ.synchronize()

            # Detection reads geometry, so it runs before anything is meshed.
            ports = self._detect_port_candidates(imported)
            display = self._display_mesh_metadata()
            digest = self._compute_digest(path)
            return self.record_component_from_metadata(
                model,
                source_path=path,
                component_id=id,
                asset_id=asset_id,
                role=role,
                unit_scale_to_m=unit_scale_to_m,
                placement=placement,
                content_digest=digest,
                metadata={**dict(metadata or {}), **display},
                ports=ports,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_step_analysis_importer.py -v`
Expected: PASS. The nozzle tessellates to roughly 107 vertices / 210 triangles.

- [ ] **Step 5: Commit**

```bash
git add tuba/geometry/step_analysis_importer.py tests/test_step_analysis_importer.py
git commit -m "feat(step): tessellate imported STEP for the review viewer

The scene builder has always read mesh_vertices_local/mesh_faces and otherwise
drawn a box, but only an example ever filled that seam, and only for STL. Every
imported STEP component rendered as a featureless block.

Also derives local_bounds from the tessellation, which gives port validation
real bounds to check against.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Port-on-asset validation

Nothing checks that a port lies on the asset that owns it. Port position is user-asserted metadata against a placement nobody cross-checks. This task also removes the third copy of the placement quaternion maths by promoting one shared helper.

**Files:**
- Modify: `tuba/mixed.py` (new public `placement_transform`)
- Modify: `tuba/visualization/builders/_imported.py:267-283` (delegate to it)
- Modify: `tuba/validation.py:379-387` (`_validate_ports`)
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: `local_bounds` written by Task 3.
- Produces: `tuba.mixed.placement_transform(placement: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]` returning `(origin, rotation)` — a 3-vector and a 3x3 rotation matrix, with an identity rotation for a degenerate quaternion. `tuba/validation.py` gains `_validate_port_on_asset(model, port_id, port, errors) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_validation.py`:

```python
def _model_with_placed_asset(port_position):
    model = Model(project_name="Port anchoring")
    model.add_cad_asset(
        id="cad_asset_equipment",
        source_path="equipment.step",
        source_format="STEP",
        placement={"origin": [1.2, 0.45, 0.0], "rotation": [1.0, 0.0, 0.0, 0.0]},
        metadata={"local_bounds": [0.0, -0.15, -0.15, 0.40, 0.15, 0.15]},
    )
    model.add_imported_component(
        id="component_equipment",
        asset="cad_asset:cad_asset_equipment",
        name="component_equipment",
        role="equipment",
        status="review",
    )
    model.add_port(
        id="port_a",
        owner="component:component_equipment",
        kind="circular_face",
        position=port_position,
        axis=[-1.0, 0.0, 0.0],
        radius=0.05,
        face_group="G_EQUIP_PORT_A",
        status="confirmed",
    )
    return model


def test_port_on_its_asset_validates():
    # Local origin under the placement above.
    model = _model_with_placed_asset([1.2, 0.45, 0.0])
    model.validate()


def test_port_off_its_asset_is_rejected():
    model = _model_with_placed_asset([5.0, 0.45, 0.0])
    with pytest.raises(ValueError, match="lies outside its asset"):
        model.validate()


def test_port_is_not_checked_when_asset_bounds_are_unknown():
    model = _model_with_placed_asset([5.0, 0.45, 0.0])
    asset = model.cad_assets["cad_asset_equipment"]
    model.cad_assets["cad_asset_equipment"] = replace(asset, metadata={})
    model.validate()
```

Add `from dataclasses import replace` and `import pytest` to that module's imports if absent.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validation.py -k port -v`
Expected: `test_port_off_its_asset_is_rejected` FAILS — `model.validate()` raises nothing.

- [ ] **Step 3: Write the implementation**

Add to `tuba/mixed.py`, importing numpy at the top of the module:

```python
def placement_transform(placement: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """An asset placement as ``(origin, rotation)``.

    One copy, because three drifting copies of quaternion-to-matrix is how a
    review viewer and a validator end up disagreeing about where a part is.
    """
    origin = np.asarray(placement.get("origin", [0.0, 0.0, 0.0]), dtype=float)
    qw, qx, qy, qz = [float(value) for value in placement.get("rotation", [1.0, 0.0, 0.0, 0.0])]
    norm = float(np.linalg.norm([qw, qx, qy, qz]))
    if norm <= 1e-12:
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
    else:
        qw, qx, qy, qz = [value / norm for value in (qw, qx, qy, qz)]
    rotation = np.array(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=float,
    )
    return origin, rotation
```

Replace the body of `_asset_placement_transform` in `tuba/visualization/builders/_imported.py` so the maths lives in one place:

```python
def _asset_placement_transform(placement: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    return placement_transform(placement)
```

with `from tuba.mixed import placement_transform` added to that module's imports.

In `tuba/validation.py`, add `import numpy as np` and `from tuba.mixed import placement_transform` if absent, then rewrite `_validate_ports` and add the helper:

```python
def _validate_ports(model: TubaModel, errors: list[str]) -> None:
    for port_id, port in model.ports.items():
        if port.owner.kind != "component":
            errors.append(f"Port {port_id!r} owner must be a component, got {port.owner.kind!r}.")
        elif port.owner.id not in model.imported_components:
            errors.append(f"Port {port_id!r} references missing owner {port.owner!r}.")
        else:
            _validate_port_on_asset(model, port_id, port, errors)

        if port.status == "confirmed" and not port.face_group:
            errors.append(f"Port {port_id!r} is confirmed but missing face_group.")


def _validate_port_on_asset(model: TubaModel, port_id: str, port: Any, errors: list[str]) -> None:
    """A port that does not touch its asset is silently wrong geometry.

    The AABB of a rotated box is looser than the box, so this is deliberately
    coarse. It catches the failure that matters: a port nowhere near the asset
    it claims to belong to.
    """
    component = model.imported_components[port.owner.id]
    asset = model.cad_assets.get(component.asset.id)
    if asset is None:
        return
    bounds = asset.metadata.get("local_bounds")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 6:
        return
    values = [float(value) for value in bounds]
    if not all(np.isfinite(values)):
        return

    x_min, y_min, z_min, x_max, y_max, z_max = values
    corners = [
        [x, y, z]
        for x in (x_min, x_max)
        for y in (y_min, y_max)
        for z in (z_min, z_max)
    ]
    origin, rotation = placement_transform(asset.placement)
    scale = float(getattr(asset, "unit_scale_to_m", 1.0))
    world = np.array(
        [origin + rotation @ (np.asarray(corner, dtype=float) * scale) for corner in corners]
    )
    low = world.min(axis=0)
    high = world.max(axis=0)
    tolerance = max(0.001, float(np.max(high - low)) * 0.01)
    position = np.asarray(port.position, dtype=float)
    if np.any(position < low - tolerance) or np.any(position > high + tolerance):
        errors.append(
            f"Port {port_id!r} at {[float(value) for value in port.position]} lies outside "
            f"its asset {asset.id!r} bounds {low.tolist()} to {high.tolist()} "
            f"(tolerance {tolerance:.4g} m)."
        )
```

- [ ] **Step 4: Run the targeted tests, then the full suite**

Run: `uv run pytest tests/test_validation.py -k port -v`
Expected: PASS

Run: `uv run pytest`
Expected: PASS. If a fixture now fails, its port genuinely does not sit on its asset — **correct the fixture's geometry, do not loosen the check.** Record what you changed and why in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tuba/mixed.py tuba/validation.py tuba/visualization/builders/_imported.py tests/test_validation.py
git commit -m "feat(validation): anchor a port to the asset that owns it

Port position was user-asserted metadata against a placement nobody
cross-checked, so a port could sit anywhere and still validate. Requires the
position inside the AABB of the placement-transformed asset bounds, skipped when
bounds are unknown.

Breaking by design: a model whose port does not touch its asset now fails.
Also promotes one placement_transform, deleting a second copy of the quaternion
maths.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The demo STEP asset and the example that imports it

Generate the asset, rewrite the STEP branch of `build_model` to import and confirm rather than hand-write, and delete the tetrahedron. The STL branch is untouched: STL has no BREP faces to detect, so hand-written metadata is genuinely the only option there, and the example documents it as review geometry only.

**Files:**
- Create: `examples/assets/imported_component_demo.step`
- Delete: `examples/assets/imported_component_demo.stl`
- Modify: `examples/imported_component_mixed_system.py`
- Modify: `scripts/official_gallery.py:172`
- Test: `tests/test_imported_component_mixed_example.py`

**Interfaces:**
- Consumes: `import_component(..., placement=, metadata=)` (Task 2), the display mesh and `local_bounds` (Task 3), planar detection with outward axes (Task 1), port-on-asset validation (Task 4).
- Produces: `_confirm_nozzle_port(model, *, component_id, pipe_radius) -> Port` in the example — selects the detected candidate matching `pipe_radius`, renames it to `port_equipment_nozzle_a` / `G_EQUIP_PORT_A`, promotes status to `confirmed`, discards the rest, and raises `ValueError` when nothing matches.

- [ ] **Step 1: Generate and commit the asset**

Run this once from the repo root:

```bash
UV_NO_SYNC=1 uv run python -c "
import gmsh
from pathlib import Path
gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('imported_component_demo')
outer = gmsh.model.occ.addCylinder(0, 0, 0, 0.16, 0, 0, 0.05)
bore = gmsh.model.occ.addCylinder(-0.01, 0, 0, 0.18, 0, 0, 0.042)
vessel = gmsh.model.occ.addCylinder(0.16, 0, 0, 0.24, 0, 0, 0.15)
fused, _ = gmsh.model.occ.fuse([(3, outer)], [(3, vessel)])
gmsh.model.occ.cut(fused, [(3, bore)])
gmsh.model.occ.synchronize()
gmsh.write(str(Path('examples/assets/imported_component_demo.step').resolve()))
gmsh.finalize()
"
git rm examples/assets/imported_component_demo.stl
```

Expected: roughly a 13 KB STEP file, one volume, seven faces, four of them planar.

- [ ] **Step 2: Write the failing test**

Replace `test_step_component_can_be_modeled_without_forcing_export` in `tests/test_imported_component_mixed_example.py` — it currently passes a stub `ISO-10303-21;` file that `build_model` never opens, which no longer works once the example imports for real:

```python
DEMO_STEP = Path(__file__).resolve().parents[1] / "examples" / "assets" / "imported_component_demo.step"


def test_step_component_is_detected_not_asserted(tmp_path: Path):
    model = build_model(DEMO_STEP)

    asset = model.cad_assets["cad_asset_custom_equipment"]
    assert asset.source_format == "STEP"
    assert asset.importer == "gmsh-occ"
    assert asset.metadata["mesh_vertices_local"], "the viewer must draw the real shape"

    # One confirmed port; the other detected candidates are discarded.
    assert list(model.ports) == ["port_equipment_nozzle_a"]
    port = model.ports["port_equipment_nozzle_a"]
    assert port.status == "confirmed"
    assert port.face_group == "G_EQUIP_PORT_A"
    assert port.radius == pytest.approx(0.05, abs=1e-6)
    # Detected, not asserted: outward from the vessel, back down the pipe.
    assert port.axis == pytest.approx((-1.0, 0.0, 0.0), abs=1e-6)
    assert isinstance(port.metadata["gmsh_face_tag"], int)

    # The pipe terminates on the detected face.
    assert list(model.nodes["N1"].coords) == pytest.approx(list(port.position), abs=1e-9)
    assert "coupling_pipe_to_equipment_a" in model.couplings


def test_step_demo_exports_a_coupling_against_a_non_empty_group(tmp_path: Path):
    summary = run_demo(DEMO_STEP, output_root=tmp_path / "out", export_study=True)

    assert summary["result_status"] == "export_only"
    comm = Path(summary["study_dir"], "study.comm").read_text(encoding="utf-8")
    assert "LIAISON_ELEM" in comm
    assert "GROUP_MA_1" in comm

    import meshio

    mesh = meshio.read(Path(summary["study_dir"], "study.med"))
    port_cells = [
        name for name, value in mesh.cell_sets.items()
        if "PORT" in name.upper() and any(len(block) for block in value)
    ]
    assert port_cells, "the port face group must carry cells, not be an empty placeholder"


def test_step_source_matches_a_face_or_fails_loudly(tmp_path: Path):
    """A STEP whose faces match no pipe radius must raise, not hand-write a port."""
    wrong = tmp_path / "wrong.step"
    with gmsh_model(gmsh_module, "wrong_box"):
        gmsh_module.model.occ.addBox(0, 0, 0, 0.3, 0.3, 0.3)
        gmsh_module.model.occ.synchronize()
        gmsh_module.write(str(wrong))

    with pytest.raises(ValueError, match="no detected port face matches"):
        build_model(wrong)
```

This test module needs these imports added at the top:

```python
import pytest
import gmsh as gmsh_module

from tuba.meshing._gmsh import gmsh_model
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_imported_component_mixed_example.py -v`
Expected: FAIL — the STEP branch still hand-writes its port, so `port.metadata` has no `gmsh_face_tag` and `_confirm_nozzle_port` does not exist.

- [ ] **Step 4: Rewrite the example**

In `examples/imported_component_mixed_system.py`, replace `DEFAULT_LOCAL_BOUNDS`-driven STEP handling. Keep `infer_source_format`, `local_to_global_point`, `local_to_global_vector`, `_placement_transform`, `_mesh_metadata_for_source` and the STL branch exactly as they are. Add the confirmation helper:

```python
PORT_ID = "port_equipment_nozzle_a"
PORT_FACE_GROUP = "G_EQUIP_PORT_A"
PORT_EDGE_GROUP = "G_EQUIP_PORT_EDGE_A"


def _confirm_nozzle_port(model: tuba.Model, *, component_id: str, pipe_radius: float) -> Any:
    """Pick the detected face a DN100 pipe can land on, and confirm it.

    Detection proposes one candidate per planar face - here the stub end
    annulus, the vessel end caps and the blind bore bottom. Selection is by
    matched radius, never by face tag: tags renumber across a STEP round trip.
    """
    owner = f"component:{component_id}"
    candidates = [
        port
        for port in model.ports.values()
        if str(port.owner) == owner and abs(port.radius - pipe_radius) <= max(0.001, pipe_radius * 0.02)
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one detected port face of radius {pipe_radius} m on "
            f"{component_id!r}; no detected port face matches ({len(candidates)} found). "
            "A supplied component must carry a face the pipe can land on."
        )
    detected = candidates[0]
    for port_id in [port.id for port in model.ports.values() if str(port.owner) == owner]:
        del model.ports[port_id]
    return model.add_port(
        id=PORT_ID,
        owner=owner,
        kind=detected.kind,
        position=list(detected.position),
        axis=list(detected.axis),
        radius=detected.radius,
        face_group=PORT_FACE_GROUP,
        edge_group=PORT_EDGE_GROUP,
        status="confirmed",
        metadata={
            **dict(detected.metadata),
            "source": "gmsh_planar_face_detection",
            "confirmed_from": detected.id,
        },
    )
```

Then restructure `build_model` so the STEP path imports first and routes the pipe to the detected port. Replace the body from `model = tuba.Model(...)` through `model.validate()` with:

```python
    model = tuba.Model(project_name="Imported_Component_Mixed_System")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1, WT=0.008)
    pipe_radius = 0.05

    importer = StepAnalysisImporter()
    if fmt in ANALYSIS_FORMATS:
        # A STEP carries BREP faces, so the port is detected and confirmed
        # rather than asserted. Bounds and the display mesh come from the
        # importer's tessellation.
        importer.import_component(
            model,
            source,
            id="component_custom_equipment",
            asset_id="cad_asset_custom_equipment",
            role="equipment",
            placement=placement,
            metadata={"source_format": fmt},
        )
        port = _confirm_nozzle_port(
            model,
            component_id="component_custom_equipment",
            pipe_radius=pipe_radius,
        )
        global_port = [float(value) for value in port.position]
    else:
        # STL has no faces to detect, so it stays hand-written review geometry.
        global_port = local_to_global_point(local_port_position, placement)
        global_axis = local_to_global_vector(local_port_axis, placement)
        importer.record_component_from_metadata(
            model,
            source_path=source,
            source_format=fmt,
            component_id="component_custom_equipment",
            asset_id="cad_asset_custom_equipment",
            role="equipment",
            placement=placement,
            importer="manual-port-metadata",
            metadata={
                "local_bounds": [float(value) for value in local_bounds],
                **_mesh_metadata_for_source(source, fmt),
            },
            ports=[
                {
                    "id": PORT_ID,
                    "position": global_port,
                    "axis": global_axis,
                    "radius": pipe_radius,
                    "face_group": PORT_FACE_GROUP,
                    "edge_group": PORT_EDGE_GROUP,
                    "status": "confirmed",
                    "metadata": {
                        "source": "user_confirmed_port",
                        "coordinate_basis": "asset_local_transformed_to_global",
                        "local_position": [float(value) for value in local_port_position],
                        "local_axis": [float(value) for value in local_port_axis],
                        "asset_placement": placement,
                    },
                }
            ],
        )

    with model.pipe(section="DN100", material="Steel", route="line_to_equipment") as pipe:
        pipe.start([0.0, global_port[1], global_port[2]], support="anchor")
        pipe.end(global_port)

    model.define_load_case(
        "Hot",
        gravity=True,
        pressure=1.0e6,
        temperature=120.0,
        ref_temperature=20.0,
    )
    model.add_analysis_region(
        id="region_equipment_solid",
        owner="component:component_custom_equipment",
        role="solid_3d",
        code_aster_modelisation="3D",
        material="Steel",
        mesh_group="G_EQUIP_SOLID",
        status="reviewed",
        metadata={"source_format": fmt},
    )
    model.connect_pipe_to_port(
        pipe="element:pipe_str_0",
        node="node:N1",
        port=f"port:{PORT_ID}",
        method="3D_TUYAU",
        id="coupling_pipe_to_equipment_a",
    )
    model.validate()
    return model
```

Update the module docstring's second paragraph to state that a STEP port is detected and confirmed while STL stays hand-written review geometry, and add a comment above the asset path recording how the STEP was generated (the gmsh calls from Step 1).

Point the gallery at the new asset — `scripts/official_gallery.py:172`:

```python
            Path("examples/assets/imported_component_demo.step"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_imported_component_mixed_example.py -v`
Expected: PASS, including the two unchanged STL tests.

Run: `uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add examples/assets/imported_component_demo.step examples/imported_component_mixed_system.py scripts/official_gallery.py tests/test_imported_component_mixed_example.py
git rm --cached examples/assets/imported_component_demo.stl 2>/dev/null || true
git commit -m "feat(examples): couple the demo pipe to a meshed STEP component

The gallery asked how a supplied component joins an authored line and answered
with a four-facet STL tetrahedron. STL never reaches _write_med_with_gmsh, so
the solid and port face groups shipped as empty cell sets and LIAISON_ELEM
pointed at a group holding zero cells.

The asset is now a bored nozzle stub on a vessel, whose end face detects at
exactly pipe OD/2. The example selects that face by matched radius and confirms
it; position, radius and axis all come from gmsh. STL stays hand-written review
geometry, which is what it can honestly be.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Name the imported-component marks in the viewport key

The builder emits `imported_components`, `mixed_ports`, `mixed_couplings` and `local_coordinate_axes`. None appears in `BODY_SPECS` or `OVERLAY_SPECS`, so they are drawn and named nowhere. The key exists for exactly this and is under-fed; the scene's own question is discarded on entry.

**Files:**
- Modify: `viewer/src/app.js` (`renderViewportLegend` at `:1267`, `bodyLegendOpen` at `:1877`, catalog handling at `:174-204`)
- Test: `viewer/test/workflow-rendering.test.js`

**Interfaces:**
- Consumes: catalog entries shaped by `normalizeCatalog` — `{id, title, question?, summary?}`.
- Produces: module-level `let activeCatalogEntry = null;` in `app.js`, set during boot.

- [ ] **Step 1: Write the failing test**

Add to `viewer/test/workflow-rendering.test.js`, following the source-assertion style already used there:

```js
test("the viewport key names the imported-component marks and leads with the scene question", () => {
  assert.match(app, /activeCatalogEntry/);
  assert.match(app, /IMPORTED_LAYER_NOTE/);
  // The four layers the builder draws but nothing named.
  assert.match(app, /imported_components/);
  assert.match(app, /mixed_ports/);
  assert.match(app, /mixed_couplings/);
  assert.match(app, /local_coordinate_axes/);
});

test("the viewport key opens on a first visit and remembers being dismissed", () => {
  assert.match(app, /let bodyLegendOpen = readLegendPreference\(\)/);
  // Absent storage, or storage that throws, must still open the key.
  assert.match(app, /tuba\.viewportKeyDismissed/);
  assert.match(app, /catch\s*\{\s*return true;/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix viewer test`
Expected: FAIL — `activeCatalogEntry` and `IMPORTED_LAYER_NOTE` are not in `app.js`, and `bodyLegendOpen` is `false`.

- [ ] **Step 3: Write the implementation**

In `viewer/src/app.js`, add near the other module-level view state:

```js
// The gallery card's question is the only sentence that says what a scene is
// for, and it was thrown away the moment you opened the scene.
let activeCatalogEntry = null;
```

In the boot path, after `currentBundleUrl` is resolved (around `:194`), record the matching entry:

```js
  activeCatalogEntry =
    normalizeCatalog(catalog).find((entry) => bundleKey(entry.id) === bundleKey(currentBundleUrl)) ?? null;
```

Change the declaration at `:1877` and persist a dismissal:

```js
let bodyLegendOpen = readLegendPreference();

function readLegendPreference() {
  // A first visit should not have to discover the key to understand the scene.
  try {
    return window.localStorage.getItem("tuba.viewportKeyDismissed") !== "1";
  } catch {
    return true;
  }
}
```

In the toggle handler at `:2196`, persist the new state:

```js
  bodyLegendOpen = !bodyLegendOpen;
  try {
    window.localStorage.setItem("tuba.viewportKeyDismissed", bodyLegendOpen ? "0" : "1");
  } catch {
    // A private window still gets a working toggle, just no memory of it.
  }
```

Add the layer notes beside `BODY_LEGEND_NOTE` at `:1371`:

```js
// Drawn by tuba/visualization/builders/_imported.py and, until now, named
// nowhere in this UI - which is how a grey solid beside a pipe reads as a bug.
const IMPORTED_LAYER_NOTE = Object.freeze([
  ["imported_components", "Imported component — supplied CAD, meshed as a 3D solid"],
  ["mixed_ports", "Connection port — the face the authored line couples to"],
  ["mixed_couplings", "Coupling — LIAISON_ELEM between the pipe node and that face"],
  ["local_coordinate_axes", "Local frame — the supplied asset's own X/Y/Z"]
]);
```

In `renderViewportLegend`, extend the `hasKey` gate and prepend the scene question. Replace the `hasKey` computation and the block that follows it:

```js
  const importedRows = IMPORTED_LAYER_NOTE.filter(([layerId]) => (currentState.layers?.[layerId]?.count ?? 0) > 0);
  const hasKey =
    bodies.length > 0 || Boolean(loadCase) || visibleVectors.length > 0 || importedRows.length > 0;
```

and, immediately after the early `if (dom.bodyLegend.hidden) return;`:

```js
  if (activeCatalogEntry?.question) {
    const question = document.createElement("p");
    question.className = "body-legend-question";
    question.textContent = activeCatalogEntry.question;
    dom.bodyLegend.append(question);
  }
  if (activeCatalogEntry?.summary) {
    const summary = document.createElement("p");
    summary.className = "body-legend-summary";
    summary.textContent = activeCatalogEntry.summary;
    dom.bodyLegend.append(summary);
  }
  for (const [, label] of importedRows) appendViewportKeyRow(label);
```

Add matching styles to `viewer/src/styles.css` beside the other `.body-legend` rules:

```css
.body-legend-question {
  margin: 0 0 0.25rem;
  font-weight: 600;
}

.body-legend-summary {
  margin: 0 0 0.5rem;
  opacity: 0.8;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix viewer test`
Expected: PASS, including the two pre-existing assertions at `workflow-rendering.test.js:143-144`, which still match.

- [ ] **Step 5: Commit**

```bash
git add viewer/src/app.js viewer/src/styles.css viewer/test/workflow-rendering.test.js
git commit -m "fix(viewer): name the imported-component marks in the viewport key

The builder draws imported components, ports, couplings and local frames, and
none of the four layers appeared in BODY_SPECS or OVERLAY_SPECS - so a grey
solid beside a pipe read as a bug with nothing in the UI to say otherwise. The
key also now leads with the gallery card's question, which was discarded the
moment you opened the scene, and opens on a first visit.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Docs and the packaged viewer

`viewer/public/<bundle>` and `viewer/dist/` are gitignored — only `tuba/visualization/_viewer/` is committed, and CI enforces it is in sync via `npm run build` followed by `git diff --exit-code`.

**Files:**
- Modify: `docs/content/examples.md:47`
- Modify: `docs/content/modeling.md:76`
- Modify: `tuba/visualization/_viewer/**` (build output)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Rebuild the bundle locally and look at it**

Run:
```bash
UV_NO_SYNC=1 uv run python scripts/build_pages.py examples --output viewer/public --audience dev --only imported_component_mixed_demo
```
Expected: exit 0. The gallery build now invokes gmsh for the import; the geometry is small, so it stays fast.

Confirm the scene carries the real shape rather than a box:
```bash
UV_NO_SYNC=1 uv run python -c "
import json
scene = json.load(open('viewer/public/imported_component_mixed_demo/scene.json'))
kinds = sorted({o['kind'] for o in scene['objects']})
print('kinds:', kinds)
mesh = [a for a in scene['geometry_assets'] if a.get('generation_config', {}).get('source') == 'tuba.imported_component']
print('component assets:', len(mesh))
"
```
Expected: `imported_component`, `imported_port`, `mixed_coupling` and `local_coordinate_axis` all present.

- [ ] **Step 2: Update the docs**

In `docs/content/modeling.md:76`, replace the paragraph so it describes what the bundle now is, while keeping the no-results statement that `AGENTS.md` requires:

```markdown
The model-review bundle shows a programmatic pipe coupled to an imported STEP
component: the nozzle face is detected from the CAD, confirmed, and joined to
the pipe with `LIAISON_ELEM`. It contains geometry, a mesh handoff and model
provenance only—**it has no solver results**.
```

In `docs/content/examples.md:47`, leave the evidence badge (`Model only - no results`) unchanged and update only the prose describing the component to say STEP rather than STEP/STL.

- [ ] **Step 3: Rebuild the packaged viewer**

Run: `npm --prefix viewer run build`
Expected: writes `tuba/visualization/_viewer/`. Note the working tree already carried an uncommitted viewer rebuild before this plan started; include only the assets this build produces.

- [ ] **Step 4: Verify the whole suite and the pages build**

Run: `uv run pytest`
Expected: PASS

Run: `npm --prefix viewer test`
Expected: PASS

Run: `UV_NO_SYNC=1 uv run python scripts/build_pages.py pages --output .build/pages-check`
Expected: exit 0

- [ ] **Step 5: Commit**

```bash
git add docs/content/examples.md docs/content/modeling.md tuba/visualization/_viewer
git commit -m "docs(gallery): describe the imported component as a real coupling

Rebuilds the packaged viewer for the viewport-key change. The no-solver-results
statement stays on both surfaces, because there are still none.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
