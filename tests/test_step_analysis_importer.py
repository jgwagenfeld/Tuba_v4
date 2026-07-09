from __future__ import annotations

from pathlib import Path

import pytest

from tuba import Model
from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError


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

    class FakeModel:
        occ = FakeOcc()

        @staticmethod
        def add(name):
            calls.append(f"add:{name}")

        @staticmethod
        def remove():
            calls.append("remove")

        @staticmethod
        def getBoundary(entities, oriented=False, recursive=False):
            calls.append(f"boundary:{entities}:{oriented}:{recursive}")
            return [(2, 7)]

        @staticmethod
        def getBoundingBox(dim, tag):
            return (0.0, 0.0, 0.0, 0.1, 0.0, 0.1)

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
    assert "port_candidate_0" in model.ports
    assert "initialize" not in calls
    assert "finalize" not in calls
    assert "remove" not in calls
