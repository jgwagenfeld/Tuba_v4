from __future__ import annotations

from pathlib import Path

import gmsh as gmsh_module
import pytest

from tuba import Model
from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError
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


def test_missing_step_file_raises_clear_error(tmp_path):
    model = Model(project_name="Missing STEP")
    importer = StepAnalysisImporter()

    with pytest.raises(FileNotFoundError, match="missing.step"):
        importer.import_component(
            model,
            str(tmp_path / "missing.step"),
            id="component_missing",
        )


def test_missing_gmsh_raises_optional_dependency_error(tmp_path, monkeypatch):
    step_file = tmp_path / "tiny.step"
    step_file.write_text("ISO-10303-21;", encoding="utf-8")

    model = Model(project_name="Missing gmsh")
    importer = StepAnalysisImporter()
    monkeypatch.setattr("tuba.geometry.step_analysis_importer.gmsh", None)

    with pytest.raises(StepImportError, match="gmsh is required"):
        importer.import_component(
            model,
            str(step_file),
            id="component_no_gmsh",
        )


def test_manual_candidate_can_be_recorded_without_solver_activation(tmp_path: Path):
    model = Model(project_name="Manual candidate")
    importer = StepAnalysisImporter()

    source_path = tmp_path / "component.step"
    source_path.write_text("ISO-10303-21;", encoding="utf-8")

    component = importer.record_component_from_metadata(
        model,
        source_path=source_path,
        component_id="component_manual",
        asset_id="cad_asset_manual",
        role="equipment",
        unit_scale_to_m=0.001,
        content_digest="sha256:unit",
        ports=[
            {
                "id": "port_candidate_0",
                "position": [1.0, 2.0, 3.0],
                "radius": 0.05,
                "face_group": "G_PORT_CANDIDATE_0",
                "metadata": {"source": "manual"},
            }
        ],
    )

    asset = model.cad_assets["cad_asset_manual"]
    assert asset.source_path == str(source_path)
    assert asset.source_format == "STEP"
    assert asset.unit_scale_to_m == 0.001
    assert asset.importer == "gmsh-occ"
    assert model.imported_components["component_manual"] == component
    assert component.status == "review"

    port = model.ports["port_candidate_0"]
    assert port.owner.kind == "component"
    assert port.owner.id == "component_manual"
    assert port.kind == "circular_face"
    assert port.status == "detected"
    assert port.face_group == "G_PORT_CANDIDATE_0"
    assert port.metadata == {"source": "manual"}

    assert model.analysis_regions == {}
    assert model.mesh_groups == {}
    assert model.couplings == {}


def test_manual_candidate_preserves_source_format(tmp_path: Path):
    model = Model(project_name="Manual STL candidate")
    importer = StepAnalysisImporter()
    source_path = tmp_path / "component.stl"
    source_path.write_text("solid component\nendsolid component\n", encoding="utf-8")

    importer.record_component_from_metadata(
        model,
        source_path=source_path,
        source_format="stl",
        component_id="component_manual",
        asset_id="cad_asset_manual",
        importer="manual-port-metadata",
        ports=[
            {
                "id": "port_candidate_0",
                "position": [1.0, 0.0, 0.0],
                "radius": 0.05,
            }
        ],
    )

    asset = model.cad_assets["cad_asset_manual"]
    assert asset.source_path == str(source_path)
    assert asset.source_format == "STL"
    assert asset.importer == "manual-port-metadata"


def test_malformed_candidate_does_not_partially_mutate_model(tmp_path: Path):
    model = Model(project_name="Malformed candidate")
    importer = StepAnalysisImporter()
    source_path = tmp_path / "component.step"
    source_path.write_text("ISO-10303-21;", encoding="utf-8")

    with pytest.raises(StepImportError, match="position"):
        importer.record_component_from_metadata(
            model,
            source_path=source_path,
            component_id="component_manual",
            asset_id="cad_asset_manual",
            ports=[{"id": "port_bad", "radius": 0.05}],
        )

    assert model.cad_assets == {}
    assert model.imported_components == {}
    assert model.ports == {}


def test_import_component_preserves_existing_gmsh_session(tmp_path: Path, monkeypatch):
    step_file = tmp_path / "component.step"
    step_file.write_text("ISO-10303-21;", encoding="utf-8")
    calls: list[str] = []

    class FakeOcc:
        @staticmethod
        def importShapes(path):
            calls.append(f"import:{Path(path).name}")
            return [(3, 1)]

        @staticmethod
        def synchronize():
            calls.append("synchronize")

        @staticmethod
        def getCenterOfMass(dim, tag):
            return (0.05, -0.05, 0.05)

    class FakeModel:
        occ = FakeOcc()
        current = "caller_model"

        @classmethod
        def add(cls, name):
            calls.append(f"add:{name}")
            cls.current = name

        @staticmethod
        def remove():
            calls.append("remove")

        @classmethod
        def getCurrent(cls):
            return cls.current

        @classmethod
        def setCurrent(cls, name):
            calls.append(f"set:{name}")
            cls.current = name

        @staticmethod
        def getBoundary(entities, oriented=False, recursive=False):
            calls.append(f"boundary:{entities}:{oriented}:{recursive}")
            return [(2, 7)]

        @staticmethod
        def getBoundingBox(dim, tag):
            return (0.0, 0.0, 0.0, 0.1, 0.0, 0.1)

        @staticmethod
        def getType(dim, tag):
            return "Plane"

        @staticmethod
        def getParametrizationBounds(dim, tag):
            return ([0.0, 0.0], [1.0, 1.0])

        @staticmethod
        def getNormal(tag, parametric_coord):
            # The fake face is flat in y, so its normal is the y axis.
            return [0.0, 1.0, 0.0]

    class FakeGmsh:
        model = FakeModel()

        @staticmethod
        def isInitialized():
            return True

        @staticmethod
        def initialize():
            calls.append("initialize")

        @staticmethod
        def finalize():
            calls.append("finalize")

    monkeypatch.setattr("tuba.geometry.step_analysis_importer.gmsh", FakeGmsh)

    model = Model(project_name="Fake gmsh")
    component = StepAnalysisImporter().import_component(model, step_file, id="component_fake")

    assert component.id == "component_fake"
    assert model.ports["port_candidate_0"].axis == (0.0, 1.0, 0.0)
    assert "initialize" not in calls
    assert "finalize" not in calls
    assert "remove" in calls
    assert FakeModel.current == "caller_model"


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


def test_outward_face_axis_flips_a_normal_that_points_into_the_solid():
    """One real face, solid on either side of it, yields exactly opposite axes."""
    with gmsh_model(gmsh_module, "test_flip"):
        box = gmsh_module.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh_module.model.occ.synchronize()
        face_tag = abs(int(gmsh_module.model.getBoundary([(3, box)], oriented=False)[0][1]))
        bounds = gmsh_module.model.getBoundingBox(2, face_tag)
        centre = [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]
        behind = StepAnalysisImporter._outward_face_axis(
            face_tag, centre, [value - 1.0 for value in centre]
        )
        ahead = StepAnalysisImporter._outward_face_axis(
            face_tag, centre, [value + 1.0 for value in centre]
        )

    # Opposite vectors, so this cannot pass on a normal the helper failed to
    # read: an unreadable normal is None, which the negation below would raise on.
    assert behind == pytest.approx([-value for value in ahead], abs=1e-12)
    assert sum(value * value for value in behind) == pytest.approx(1.0, abs=1e-12)


def test_face_with_an_unreadable_normal_yields_no_candidate(monkeypatch):
    """A face we cannot orient is dropped, not handed a guessed axis."""

    class FakeOcc:
        @staticmethod
        def getCenterOfMass(dim, tag):
            return (0.0, 0.0, -1.0)

    class FakeModel:
        occ = FakeOcc()

        @staticmethod
        def getBoundary(entities, oriented=False, recursive=False):
            return [(2, 7), (2, 8)]

        @staticmethod
        def getType(dim, tag):
            return "Plane"

        @staticmethod
        def getBoundingBox(dim, tag):
            return (0.0, 0.0, 0.0, 0.1, 0.1, 0.0)

        @staticmethod
        def getParametrizationBounds(dim, tag):
            return ([0.0, 0.0], [1.0, 1.0])

        @staticmethod
        def getNormal(tag, parametric_coord):
            if tag == 8:
                raise RuntimeError("gmsh cannot evaluate this normal")
            return [0.0, 0.0, 1.0]

    class FakeGmsh:
        model = FakeModel()

    monkeypatch.setattr("tuba.geometry.step_analysis_importer.gmsh", FakeGmsh)

    candidates = StepAnalysisImporter()._detect_port_candidates([(3, 1)])

    assert [candidate["metadata"]["gmsh_face_tag"] for candidate in candidates] == [7]
    assert candidates[0]["id"] == "port_candidate_0"
    assert candidates[0]["axis"] == [0.0, 0.0, 1.0]
