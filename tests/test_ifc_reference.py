import io
import http.client
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest

ifc = pytest.importorskip("ifcopenshell")

from tuba.external.ifc_reference import conversion_zip, convert_pipes, extract
from tuba.project import run_model_script
from tuba.visualization.preview.server import ProjectStudioServer


def fixture_bytes():
    f = ifc.file(schema="IFC4")
    project = f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="Reference")
    origin = f.create_entity("IfcCartesianPoint", Coordinates=(0., 0., 0.))
    world = f.create_entity("IfcAxis2Placement3D", Location=origin)
    context = f.create_entity("IfcGeometricRepresentationContext", ContextIdentifier="Model", ContextType="Model",
                              CoordinateSpaceDimension=3, Precision=1e-6, WorldCoordinateSystem=world)
    project.RepresentationContexts = [context]
    unit = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE", Prefix="MILLI")
    project.UnitsInContext = f.create_entity("IfcUnitAssignment", Units=[unit])

    def placement(x, y, parent=None):
        point = f.create_entity("IfcCartesianPoint", Coordinates=(x, y, 0.))
        ref = f.create_entity("IfcDirection", DirectionRatios=(0., 1., 0.))
        axis = f.create_entity("IfcAxis2Placement3D", Location=point, RefDirection=ref)
        return f.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=axis)

    parent = placement(2000., 0.)
    child = placement(1000., 0., parent)
    pipe = f.create_entity("IfcPipeSegment", GlobalId=ifc.guid.new(), Name="P-01", ObjectPlacement=child)
    p0 = f.create_entity("IfcCartesianPoint", Coordinates=(0., 0., 0.))
    p1 = f.create_entity("IfcCartesianPoint", Coordinates=(1000., 0., 0.))
    line = f.create_entity("IfcPolyline", Points=[p0, p1])
    solid = f.create_entity("IfcSweptDiskSolid", Directrix=line, Radius=50., InnerRadius=40.)
    axis_rep = f.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Axis",
                               RepresentationType="Curve3D", Items=[line])
    body_rep = f.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body",
                               RepresentationType="SweptSolid", Items=[solid])
    pipe.Representation = f.create_entity("IfcProductDefinitionShape", Representations=[axis_rep, body_rep])
    prop = f.create_entity("IfcPropertySingleValue", Name="Tag", NominalValue=f.create_entity("IfcLabel", "A1"))
    pset = f.create_entity("IfcPropertySet", GlobalId=ifc.guid.new(), Name="Pset_Test", HasProperties=[prop])
    f.create_entity("IfcRelDefinesByProperties", GlobalId=ifc.guid.new(), RelatedObjects=[pipe], RelatingPropertyDefinition=pset)
    fitting = f.create_entity("IfcPipeFitting", GlobalId=ifc.guid.new(), Name="Elbow")
    return f.to_string().encode(), pipe.GlobalId, fitting.GlobalId


MATERIAL = {"name": "Steel", "E_pa": 2.1e11, "nu": 0.3, "rho_kg_m3": 7850.}
SECTION = {"name": "DN100", "outer_diameter_m": 0.1, "wall_thickness_m": 0.01}


def test_millimetres_nested_rotation_and_portable_conversion(tmp_path):
    data, guid, fitting = fixture_bytes()
    preview, meshes = extract(data, "plant.ifc")
    pipe = next(p for p in preview["products"] if p["guid"] == guid)
    assert preview["metres_per_unit"] == 0.001
    assert pipe["convertible"] and pipe["properties"]["Pset_Test"]["Tag"] == "A1"
    bounds = meshes[guid]["bounds_m"]
    assert np.allclose([bounds[0], bounds[3], bounds[2], bounds[5]], [1, 2, -0.05, 0.05], atol=1e-5)
    assert 0.95 <= bounds[1] < 0.951 and 1.049 < bounds[4] <= 1.05
    assert any(w["guid"] == fitting for w in preview["warnings"])
    archive = conversion_zip(data, [guid], MATERIAL, SECTION)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        z.extractall(tmp_path)
        assert z.read("source.ifc") == data
    model = run_model_script(tmp_path / "model.py")["model"]
    ends = [model.nodes[n].coords for n in (model.elements[0].n1, model.elements[0].n2)]
    assert np.allclose(ends, [[2, 1, 0], [1, 1, 0]])
    assert model.sections["DN100"].OD == 0.1
    assert model.materials["Steel"].E == 2.1e11
    with pytest.raises(ValueError):
        conversion_zip(data, [fitting], MATERIAL, SECTION)
    missing_units = ifc.file.from_string(data.decode())
    missing_units.by_type("IfcProject")[0].UnitsInContext = None
    with pytest.raises(ValueError, match="length unit"):
        extract(missing_units.to_string().encode())


def test_large_coordinate_axis_body_mismatch_is_rejected(tmp_path):
    data, guid, _ = fixture_bytes()
    file = ifc.file.from_string(data.decode())
    reps = file.by_guid(guid).Representation.Representations
    axis = next(rep.Items[0] for rep in reps if rep.RepresentationIdentifier == "Axis")
    body = next(rep.Items[0] for rep in reps if rep.RepresentationIdentifier == "Body")
    for point, x in zip(axis.Points, (1_000_000., 1_001_000.)):
        point.Coordinates = (x, 0., 0.)
    matching = file.to_string().encode()
    preview, _ = extract(matching)
    assert next(p for p in preview["products"] if p["guid"] == guid)["convertible"]

    shifted = [file.create_entity("IfcCartesianPoint", Coordinates=(x + 5., 0., 0.))
               for x in (1_000_000., 1_001_000.)]
    body.Directrix = file.create_entity("IfcPolyline", Points=shifted)
    mismatch = file.to_string().encode()
    preview, _ = extract(mismatch)
    pipe = next(p for p in preview["products"] if p["guid"] == guid)
    assert not pipe["convertible"] and "does not match" in pipe["reason"]
    source = tmp_path / "mismatch.ifc"
    source.write_bytes(mismatch)
    with pytest.raises(ValueError, match="does not match"):
        convert_pipes(source, [guid], MATERIAL, SECTION)


def test_studio_preview_attach_restart_remove_and_boundaries(tmp_path):
    data, guid, _ = fixture_bytes()
    project = tmp_path / "project"
    project.mkdir()
    script = ("from tuba import Model\nmodel = Model('Authored')\n"
              "model.add_material('Steel', E=2e11, nu=0.3)\n"
              "model.add_pipe_section('DN', OD=0.1, WT=0.01)\n"
              "a = model.add_node([0, 0, 0])\nb = model.add_node([1, 0, 0])\n"
              "model.add_element(id='P', type='pipe_straight', n1=a, n2=b, section='DN', material='Steel')\n")
    (project / "model.py").write_text(script)

    def start():
        return ProjectStudioServer(project, tmp_path / "out", port=0).start()

    def post(server, route, body, content_type="application/octet-stream", **headers):
        req = Request(server.base_url + "api/ifc/" + route, body,
                      headers={"Content-Type": content_type, **headers}, method="POST")
        try:
            with urlopen(req) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    server = start()
    try:
        assert post(server, "preview", data)[0] == 200
        assert not (project / "references").exists()
        assert post(server, "preview", b"bad")[0] == 422
        assert post(server, "remove", b"{bad", "application/json")[0] == 400
        assert post(server, "preview", data, Origin="https://foreign.example")[0] == 403
        connection = http.client.HTTPConnection("127.0.0.1", server.port)
        connection.putrequest("POST", "/api/ifc/preview")
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-Length", str(16777217))
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 413 and not json.loads(response.read())["ok"]
        connection.close()
        shutil.copytree(tmp_path / "out" / "build", tmp_path / "out" / "review")
        status, result = post(server, "attach", data)
        assert status == 201
        identity = result["reference"]["id"]
        assert (project / "references" / "ifc" / identity / "source.ifc").read_bytes() == data
        assert (project / "model.py").read_text() == script
        scene = json.loads((tmp_path / "out" / "build" / "scene.json").read_text())
        assert any(obj.get("source", {}).get("ifc_guid") == guid for obj in scene["objects"])
        review = json.loads((tmp_path / "out" / "review" / "scene.json").read_text())
        assert any(obj.get("source", {}).get("ifc_guid") == guid for obj in review["objects"])
        native_asset = next(asset for asset in review["geometry_assets"] if not asset["id"].startswith("ifc:"))
        native_payload = json.loads((tmp_path / "out" / "review" / native_asset["uri"]).read_text())
        assert native_payload["generation_config"]
        assert post(server, "attach", data)[0] == 200
        assert post(server, "remove", b'{"id":"../bad"}', "application/json")[0] == 400
        assert post(server, "convert", json.dumps({"reference_id": identity, "guids": ["unknown"],
                                                   "material": MATERIAL, "section": SECTION}).encode(),
                    "application/json")[0] == 404
        request = Request(server.base_url + "api/ifc/convert",
                          json.dumps({"reference_id": identity, "guids": [guid],
                                      "material": MATERIAL, "section": SECTION}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            assert response.headers["Content-Type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                assert archive.read("source.ifc") == data
        with urlopen(server.base_url + "api/ifc/export") as response:
            assert response.headers["Content-Type"] == "application/x-step"
            assert ifc.file.from_string(response.read().decode()).by_type("IfcProject")
    finally:
        server.stop()
    server = start()
    try:
        with urlopen(server.base_url + "api/project") as response:
            assert json.load(response)["ifc"]["references"][0]["id"] == identity
        assert post(server, "remove", json.dumps({"id": identity}).encode(), "application/json")[0] == 200
        assert not (project / "references" / "ifc" / identity).exists()
        for bundle in ("build", "review"):
            scene = json.loads((tmp_path / "out" / bundle / "scene.json").read_text())
            assert not any(obj["id"].startswith("ifc:") for obj in scene["objects"])
    finally:
        server.stop()


def test_export_has_metre_context_and_local_placement(tmp_path):
    from tuba import Model
    from tuba.external.ifc import IfcExporter
    from tuba.placements import PlacementAssignment, PlacementFrame

    model = Model("Export")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_pipe_section("DN", OD=0.1, WT=0.01)
    a = model.add_node([10, 20, 0])
    b = model.add_node([11, 20, 0])
    model.add_element(id="P", type="pipe_straight", n1=a, n2=b, section="DN", material="Steel")
    model.add_support(node=a, type="anchor")
    model.placement_frames["rotated"] = PlacementFrame(id="rotated", origin=(10, 20, 0), ref_direction=(0, 1, 0))
    model.placement_assignments.append(PlacementAssignment(target="element:P", frame="placement_frame:rotated", role="object_placement"))
    path = tmp_path / "export.ifc"
    IfcExporter().export_model(model, path)
    file = ifc.open(str(path))
    project = file.by_type("IfcProject")[0]
    product = file.by_type("IfcPipeSegment")[0]
    assert project.UnitsInContext.Units[0].Name == "METRE"
    assert product.Representation.Representations[0].ContextOfItems.is_a("IfcGeometricRepresentationContext")
    preview, meshes = extract(path.read_bytes())
    assert np.allclose(meshes[product.GlobalId]["bounds_m"][:3], [10, 19.95, -0.05], atol=5e-4)
    assert not any("Stress" in k or "Operating" in k for k in preview["products"][0]["properties"])
    assert not any(pset.Name == "Pset_TubaSupportForces" for pset in file.by_type("IfcPropertySet"))


def test_missing_declared_evidence_starts_unsolved(tmp_path):
    project = tmp_path / "portable"
    project.mkdir()
    (project / "model.py").write_text("from tuba import Model\nmodel = Model('Portable')\n")
    (project / "study.py").write_text("ARTIFACT_DIR = 'absent-evidence'\nLOAD_CASES = ('Operating',)\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0).start()
    try:
        info = server.project_info()
        assert info["can_solve"] and not info["has_review"] and info["review_error"] is None
    finally:
        server.stop()


def test_rotated_placement_preserves_world_cuboid_bounds(tmp_path):
    from tuba import Model
    from tuba.external.ifc import IfcExporter
    from tuba.placements import PlacementAssignment, PlacementFrame

    model = Model("WorldBox")
    model.obstacles.append({"id": "nonsquare", "type": "cuboid", "min_point": [0, 0, 0], "max_point": [2, 1, 1]})
    model.placement_frames["turn"] = PlacementFrame(id="turn", origin=(3, 4, 0), ref_direction=(0, 1, 0))
    model.placement_assignments.append(PlacementAssignment(target="obstacle:nonsquare", frame="placement_frame:turn",
                                                           role="object_placement"))
    path = tmp_path / "box.ifc"
    IfcExporter().export_model(model, path)
    product = ifc.open(str(path)).by_type("IfcBuildingElementProxy")[0]
    box = product.Representation.Representations[0].Items[0]
    assert product.ObjectPlacement is None
    assert list(box.Corner.Coordinates) == [0, 0, 0]
    assert [box.XDim, box.YDim, box.ZDim] == [2, 1, 1]


def test_geometry_only_support_friction_roundtrip(tmp_path):
    from tuba import Model
    from tuba.external.ifc import IfcExporter, IfcImporter

    model = Model("Support")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_pipe_section("DN", OD=0.1, WT=0.01)
    a = model.add_node([0., 0., 0.])
    b = model.add_node([1., 0., 0.])
    model.add_element(id="P", type="pipe_straight", n1=a, n2=b, section="DN", material="Steel")
    model.add_support(node=a, type="rest", friction_coefficient=0.3)
    path = tmp_path / "support.ifc"
    IfcExporter().export_model(model, path)
    assert not any(p.Name == "Pset_TubaSupportForces" for p in ifc.open(str(path)).by_type("IfcPropertySet"))
    imported = IfcImporter().import_model(path)
    assert len(imported.supports) == 1
    assert imported.supports[0].type == "rest"
    assert imported.supports[0].friction_coefficient == 0.3


def test_missing_ifc_dependency_and_partial_export_rejection(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text("from tuba import Model\nmodel = Model('Native')\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0).start()
    try:
        server.model.obstacles.append({"id": "cylinder", "type": "cylinder"})
        assert server.ifc_request("export")[0] == 409
        assert not server.project_info()["ifc"]["export_available"]

        def missing():
            raise ImportError("IfcOpenShell unavailable; pip install 'tuba[ifc]'")

        monkeypatch.setattr("tuba.external.ifc_reference.require_ifc", missing)
        assert server.ifc_request("preview", b"data")[0] == 503
        assert "pip install" in server.project_info()["ifc"]["reason"]
    finally:
        server.stop()
