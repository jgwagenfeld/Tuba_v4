"""Native OCC regression for annular STEP ports whose circles use multiple arcs."""

import math

import gmsh
import pytest

from tuba.geometry.step_analysis_importer import StepAnalysisImporter
from tuba.meshing._gmsh import gmsh_model


@pytest.fixture
def split_annulus(tmp_path):
    path = tmp_path / "split_annulus.step"
    options = {"General.Terminal": 0, "Geometry.OCCTargetUnit": "MM"}
    with gmsh_model(gmsh, "write_split_annulus", options=options):
        loops = []
        for radius in (40, 37):
            arcs = [gmsh.model.occ.addCircle(0, 0, 0, radius, angle1=start, angle2=end)
                    for start, end in ((0, math.pi), (math.pi, 2*math.pi))]
            loops.append(gmsh.model.occ.addCurveLoop(arcs))
        face = gmsh.model.occ.addPlaneSurface(loops)
        gmsh.model.occ.extrude([(2, face)], 0, 0, 200)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    with gmsh_model(gmsh, "read_split_annulus", options=options):
        imported = gmsh.model.occ.importShapes(str(path))
        gmsh.model.occ.synchronize()
        yield imported


def test_split_annulus_has_actual_outer_and_bore_radii_and_selectable_ports(split_annulus):
    importer = StepAnalysisImporter()
    faces = importer._describe_faces(split_annulus)
    for z, axis in ((0, [0, 0, -1]), (200, [0, 0, 1])):
        face = importer._select_face(faces, {"position": [0, 0, z], "axis": axis,
            "radius": 40, "inner_radius": 37, "shape": "annular_face"})
        assert face["area"] == pytest.approx(math.pi*(40**2-37**2), rel=1e-9)
        edges = gmsh.model.getBoundary([(2, face["gmsh_face_tag"])], oriented=False)
        assert len(edges) == 4, "Regression must exercise split arcs, not full-circle edges."
        for dim, tag in edges:
            low, high = gmsh.model.getParametrizationBounds(dim, abs(tag))
            assert math.dist(gmsh.model.getValue(dim, abs(tag), low),
                             gmsh.model.getValue(dim, abs(tag), high)) > 70
        assert importer.resolve_face_selector(split_annulus, importer._selector(face)) == face["gmsh_face_tag"]


def test_split_cylinder_radii_remain_selectable_for_pressure_surfaces(split_annulus):
    importer = StepAnalysisImporter()
    faces = importer._describe_faces(split_annulus)
    cylinders = [face for face in faces if face["type"] == "Cylinder"]
    assert len(cylinders) == 4
    for radius in (40, 37):
        for sign in (-1, 1):
            face = importer._select_face(faces, {"position": [0, sign*2*radius/math.pi, 100],
                                                "type": "Cylinder", "radius": radius})
            assert face["area"] == pytest.approx(math.pi*radius*200, rel=1e-9)
            edges = gmsh.model.getBoundary([(2, face["gmsh_face_tag"])], oriented=False)
            assert any(gmsh.model.getType(dim, abs(tag)) == "Line" for dim, tag in edges)
            assert importer.resolve_face_selector(split_annulus, importer._selector(face)) == face["gmsh_face_tag"]


@pytest.mark.parametrize("fault", ["partial", "inconsistent", "non_circle"])
def test_split_annulus_rejects_incomplete_or_inconsistent_circle_boundaries(split_annulus, monkeypatch, fault):
    face = next(face for face in StepAnalysisImporter()._describe_faces(split_annulus)
                if face["type"] == "Plane")
    tag = abs(gmsh.model.getBoundary([(2, face["gmsh_face_tag"])], oriented=False)[0][1])
    if fault == "partial":
        original = gmsh.model.occ.getMass
        monkeypatch.setattr(gmsh.model.occ, "getMass", lambda dim, entity:
            original(dim, entity) / 2 if dim == 1 and entity == tag else original(dim, entity))
    elif fault == "inconsistent":
        original = gmsh.model.getCurvature
        monkeypatch.setattr(gmsh.model, "getCurvature", lambda dim, entity, parameters:
            [1/41] if entity == tag else original(dim, entity, parameters))
    else:
        original = gmsh.model.getType
        monkeypatch.setattr(gmsh.model, "getType", lambda dim, entity:
            "Line" if dim == 1 and entity == tag else original(dim, entity))
    assert StepAnalysisImporter._circular_boundaries(face["gmsh_face_tag"]) == []
