"""STEP meshing guards using portable topology and mocked native entry points."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tuba import Model
from tuba.geometry import step_analysis_importer
from tuba.meshing import step_component
from tuba.refs import EntityRef


def _boundary(cells):
    faces = [tuple(sorted(cell[i] for i in indices)) for cell in cells
             for indices in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))]
    return [face for face in faces if faces.count(face) == 1]


def test_public_step_import_defaults_to_physical_mm_to_m(monkeypatch):
    seen = []
    monkeypatch.setattr(step_analysis_importer.StepAnalysisImporter, "import_component",
                        lambda self, model, source, **options: seen.append(options))
    model = Model("Default STEP units")
    model.import_step("source.step", id="solid")
    model.import_step("source.step", id="scaled", unit_scale_to_m=1.0)
    assert [options["unit_scale_to_m"] for options in seen] == [0.001, 1.0]


def test_tetra_boundary_requires_one_connected_solid_and_complete_unique_skin():
    cells = [("a", "b", "c", "d"), ("a", "b", "c", "e")]
    skin = _boundary(cells)
    step_component._require_tetra_boundary(cells, skin)
    for bad_skin in (skin[:-1], skin + [skin[0]]):
        with pytest.raises(RuntimeError, match="skin does not match"):
            step_component._require_tetra_boundary(cells, bad_skin)
    disconnected = [cells[0], ("e", "f", "g", "h")]
    with pytest.raises(RuntimeError, match="disconnected"):
        step_component._require_tetra_boundary(disconnected, _boundary(disconnected))
    with pytest.raises(RuntimeError, match="non-manifold"):
        step_component._require_tetra_boundary(cells + [("a", "b", "c", "f")], [])


@pytest.mark.parametrize("segments", [0, -1, True, 1.5])
def test_native_line_count_requires_positive_integer(tmp_path, segments):
    with pytest.raises(ValueError, match="line_segments must be a positive integer"):
        Model("Diagnostic mesh").mesh(tmp_path / "preview.med", line_segments=segments)


@pytest.mark.parametrize("operation", ["import", "mesh"])
def test_step_native_entry_points_explicitly_import_mm(tmp_path, monkeypatch, operation):
    source = tmp_path / "source.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    model = Model("Portable units")
    seen = []

    @contextmanager
    def capture_options(_gmsh, _name, **kwargs):
        seen.append(kwargs["options"]["Geometry.OCCTargetUnit"])
        raise RuntimeError("native entry intercepted")
        yield  # pragma: no cover

    if operation == "import":
        monkeypatch.setattr(step_analysis_importer, "gmsh_model", capture_options)
        call = lambda: step_analysis_importer.StepAnalysisImporter().import_component(model, source, id="solid")
    else:
        importer = step_analysis_importer.StepAnalysisImporter()
        importer.record_component_from_metadata(model, source_path=source,
            component_id="solid", asset_id="asset", content_digest=importer._compute_digest(source))
        region = SimpleNamespace(owner=EntityRef("component", "solid"), element_order=2)
        monkeypatch.setattr(step_component, "gmsh_model", capture_options)
        call = lambda: step_component.build_step_component_mesh(model, tmp_path / "source.med",
            region=region, max_element_size=0.01, line_modelisation="TUYAU_3M")
    with pytest.raises(RuntimeError, match="native entry intercepted"):
        call()
    assert seen == ["MM"]
    assert not (tmp_path / "source.med").exists()
