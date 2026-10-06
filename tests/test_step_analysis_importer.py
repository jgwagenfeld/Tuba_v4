from __future__ import annotations

from pathlib import Path
import math

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


def test_import_component_preserves_existing_gmsh_session(tmp_path: Path):
    step_file = _write_nozzle_step(tmp_path / "component.step")
    with gmsh_model(gmsh_module, "caller") as caller_model:
        component = StepAnalysisImporter().import_component(Model(project_name="Session"), step_file, id="component")
        assert component.id == "component"
        assert gmsh_module.isInitialized()
        assert gmsh_module.model.getCurrent() == caller_model
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
    assert port.kind == "annular_face"
    assert "gmsh_face_tag" not in port.metadata["face_selector"]
    assert port.metadata["inner_radius_m"] == pytest.approx(0.042)

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
            return (0.0, 0.0, -1.0) if dim == 3 else (0.0, 0.0, 0.0)

        @staticmethod
        def getMass(dim, tag):
            return 0.01

    class FakeModel:
        occ = FakeOcc()

        @staticmethod
        def getBoundary(entities, oriented=False, recursive=False):
            return [(2, 7), (2, 8)] if entities[0][0] == 3 else [(1, 1)]

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
    monkeypatch.setattr(StepAnalysisImporter, "_circular_boundaries", staticmethod(lambda tag: [([0, 0, 0], (0.01 / 3.141592653589793) ** 0.5)]))

    candidates = StepAnalysisImporter()._detect_port_candidates([(3, 1)])

    assert len(candidates) == 1
    assert candidates[0]["id"] == "port_candidate_0"
    assert candidates[0]["axis"] == [0.0, 0.0, 1.0]


def test_named_interfaces_transform_ports_and_preserve_real_local_tessellation(tmp_path):
    source = _write_nozzle_step(tmp_path / "placed.step")
    model = Model(project_name="Placed solid")
    model.add_material("Steel", E=2e11, nu=0.3)
    local_sizes = {"inlet": 0.003}
    component = StepAnalysisImporter().import_component(model, source, id="pump", material="Steel",
        unit_scale_to_m=0.001, mesh_size=0.01,
        interface_mesh_sizes=local_sizes,
        placement={"origin": [1, 2, 3], "rotation": [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]},
        interfaces={"inlet": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": 0.05}},
        pressure_surfaces=[{"type": "Cylinder", "position": [0.085, 0, 0], "radius": 0.042}],
        fixed_interfaces=["inlet"])
    port = model.ports["pump_inlet"]
    assert component.status == "reviewed"
    assert port.status == "confirmed"
    assert port.position == pytest.approx([1, 2, 3])
    assert port.axis == pytest.approx([0, -1, 0])
    assert port.radius == pytest.approx(0.00005)
    assert port.metadata["inner_radius_m"] == pytest.approx(0.000042)
    assert port.metadata["face_selector"]["radius"] == pytest.approx(0.05)
    asset = model.cad_assets["pump_asset"]
    assert len(asset.metadata["mesh_faces"]) > 12
    assert len(asset.metadata["mesh_vertices_local"]) > 8
    assert asset.metadata["mesh_size"] == 0.01
    assert asset.metadata["interface_mesh_sizes"] == {"inlet": 0.003}
    local_sizes["inlet"] = 0.1
    assert asset.metadata["interface_mesh_sizes"] == {"inlet": 0.003}
    assert asset.metadata["analysis_import_version"] == 1
    assert asset.content_digest == StepAnalysisImporter._compute_digest(source)
    assert model.analysis_regions["pump_solid"].metadata["fixed_interfaces"] == ["pump_inlet"]
    assert model.analysis_regions["pump_solid"].metadata["pressure_surfaces"][0]["radius"] == pytest.approx(0.042)
    assert model.mesh_groups["pump_inlet"].dimension == 2
    assert model.mesh_groups["pump_solid"].dimension == 3
    # Import another solid first so every OCC tag changes; the geometry still selects the inlet.
    with gmsh_model(gmsh_module, "retagged"):
        gmsh_module.model.occ.addBox(10, 10, 10, 1, 1, 1)
        imported = gmsh_module.model.occ.importShapes(str(source))
        gmsh_module.model.occ.synchronize()
        tag = StepAnalysisImporter.resolve_face_selector(imported, port.metadata["face_selector"])
        assert gmsh_module.model.occ.getCenterOfMass(2, tag) == pytest.approx([0, 0, 0], abs=1e-9)


def test_rectangular_planar_faces_are_not_circular_candidates(tmp_path):
    source = tmp_path / "box.step"
    with gmsh_model(gmsh_module, "box"):
        gmsh_module.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh_module.model.occ.synchronize()
        gmsh_module.write(str(source))
    model = Model(project_name="Box")
    StepAnalysisImporter().import_component(model, source, id="box")
    assert not model.ports
    named = Model(project_name="Named box")
    StepAnalysisImporter().import_component(named, source, id="box",
        interfaces={"mount": {"position": [0, 0.5, 0.5], "axis": [-1, 0, 0]}})
    assert named.ports["box_mount"].kind == "planar_face"


def test_display_triangles_retain_stable_cad_face_partitions(tmp_path):
    source = tmp_path / "partitioned.step"
    with gmsh_model(gmsh_module, "partitioned_box"):
        gmsh_module.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh_module.model.occ.synchronize()
        gmsh_module.write(str(source))
    model = Model("Face partitions")
    StepAnalysisImporter().import_component(model, source, id="box",
        interfaces={"mount": {"position": [0, 0.5, 0.5], "axis": [-1, 0, 0]}})
    metadata = model.cad_assets["box_asset"].metadata
    partitions = metadata["display_face_partitions"]
    assert len(partitions) == 6
    selected_indices = [index for partition in partitions for index in partition["face_indices"]]
    assert sorted(selected_indices) == list(range(len(metadata["mesh_faces"])))
    assert all("gmsh_face_tag" not in partition["selector"] for partition in partitions)
    candidates = [{**partition["selector"], "face_indices": partition["face_indices"]}
                  for partition in partitions]
    selected = StepAnalysisImporter._select_face(candidates, model.ports["box_mount"].metadata["face_selector"])
    assert selected["face_indices"]
    vertices = metadata["mesh_vertices_local"]
    assert all(abs(vertices[node][0]) < 1e-10 for index in selected["face_indices"]
               for node in metadata["mesh_faces"][index])
    with gmsh_model(gmsh_module, "retagged_partition"):
        gmsh_module.model.occ.addBox(10, 10, 10, 1, 1, 1)
        imported = gmsh_module.model.occ.importShapes(str(source))
        gmsh_module.model.occ.synchronize()
        assert all(StepAnalysisImporter.resolve_face_selector(imported, partition["selector"])
                   for partition in partitions)


@pytest.mark.parametrize("selector", [{"position": [99, 0, 0]}, {"position": [0.2, 0.5, 0.5], "tolerance": 2}])
def test_missing_or_ambiguous_interface_does_not_mutate_model(tmp_path, selector):
    source = tmp_path / "box.step"
    with gmsh_model(gmsh_module, "selection"):
        gmsh_module.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh_module.model.occ.synchronize()
        gmsh_module.write(str(source))
    model = Model(project_name="Bad selection")
    with pytest.raises(StepImportError, match="exactly one"):
        StepAnalysisImporter().import_component(model, source, id="box", interfaces={"bad": selector})
    assert not model.cad_assets and not model.imported_components and not model.ports


@pytest.mark.parametrize("kwargs", [{"unit_scale_to_m": float("nan")}, {"mesh_size": float("inf")},
    {"placement": {"origin": [0, 0, float("nan")]}}, {"placement": {"rotation": [0, 0, 0, 0]}}])
def test_nonfinite_or_degenerate_import_arguments_fail_before_mutation(tmp_path, kwargs):
    source = tmp_path / "source.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    model = Model(project_name="Invalid inputs")
    with pytest.raises(ValueError):
        StepAnalysisImporter().import_component(model, source, id="solid", **kwargs)
    assert not model.cad_assets and not model.imported_components and not model.ports


@pytest.mark.parametrize("name", ["solid", "SOLID", "", "  ", 42])
def test_reserved_or_invalid_interface_names_fail_atomically(tmp_path, name):
    source = tmp_path / "source.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    model = Model(project_name="Reserved interface")
    model.add_material("Steel", E=2e11, nu=0.3)
    with pytest.raises(ValueError, match="Interface"):
        StepAnalysisImporter().import_component(model, source, id="solid", material="Steel",
            interfaces={name: {"position": [0, 0, 0]}})
    assert not model.cad_assets and not model.imported_components and not model.ports
    assert not model.mesh_groups and not model.analysis_regions


def test_selector_typo_fails_instead_of_changing_selection(tmp_path):
    source = _write_nozzle_step(tmp_path / "source.step")
    model = Model(project_name="Typo")
    with pytest.raises(StepImportError, match="Unsupported face selector fields"):
        StepAnalysisImporter().import_component(model, source, id="solid",
            interfaces={"inlet": {"position": [0, 0, 0], "raduis": 0.05}})
    assert not model.cad_assets and not model.ports


@pytest.mark.parametrize("mesh_size", [None, "auto"])
def test_automatic_mesh_size_is_persisted_for_later_mesh_generation(tmp_path, mesh_size):
    source = _write_nozzle_step(tmp_path / "auto.step")
    model = Model(project_name="Auto mesh")
    StepAnalysisImporter().import_component(model, source, id="solid", mesh_size=mesh_size)
    assert model.cad_assets["solid_asset"].metadata["mesh_size"] == "auto"
    assert model.cad_assets["solid_asset"].metadata["interface_mesh_sizes"] == {}


@pytest.mark.parametrize("settings", [
    {"mesh_size": 0}, {"mesh_size": -0.01}, {"mesh_size": True},
    {"mesh_size": "Auto"}, {"mesh_size": "0.01"}, {"mesh_size": float("nan")},
    {"interface_mesh_sizes": []}, {"interface_mesh_sizes": {"unknown": 0.001}},
    {"interface_mesh_sizes": {"inlet": 0}}, {"interface_mesh_sizes": {"inlet": -0.01}},
    {"interface_mesh_sizes": {"inlet": True}}, {"interface_mesh_sizes": {"inlet": "0.01"}},
    {"interface_mesh_sizes": {"inlet": None}}, {"interface_mesh_sizes": {"inlet": float("inf")}},
    {"interface_mesh_sizes": {"inlet": float("nan")}},
])
def test_invalid_mesh_settings_fail_atomically_before_cad_import(tmp_path, settings):
    source = tmp_path / "invalid.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    model = Model(project_name="Invalid mesh settings")
    with pytest.raises(ValueError, match="mesh_size"):
        StepAnalysisImporter().import_component(model, source, id="solid",
            interfaces={"inlet": {"position": [0, 0, 0]}}, **settings)
    assert not model.cad_assets and not model.imported_components and not model.ports
    assert not model.analysis_regions and not model.mesh_groups


def test_local_mesh_size_requires_explicitly_selected_interface(tmp_path):
    source = tmp_path / "invalid.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    model = Model(project_name="Candidate refinement")
    with pytest.raises(ValueError, match="explicitly selected interface"):
        StepAnalysisImporter().import_component(model, source, id="solid",
            interface_mesh_sizes={"port_candidate_0": 0.001})
    assert not model.cad_assets and not model.ports
