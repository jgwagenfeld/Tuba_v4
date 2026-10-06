"""Shared procedural shell/reference authoring and actual mixed MED families."""
from dataclasses import replace
import os

import numpy as np
import pytest

from tuba import Model
from tuba.model import OperationField
from tuba.meshing.step_component import step_line_modelisation, step_mesh_size
from tuba.validation import operation_field_problem, operation_fields_problem


POLYGON = [[0,0,0], [1,0,0], [1,0.2,0], [0,0.2,0]]


def shell_model():
    model = Model("Procedural panel")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    panel = model.add_shell_panel("panel", polygon=POLYGON, thickness=0.01, material="Steel", mesh_size=0.1)
    reference = model.add_reference_point("root", position=[0,0.1,0])
    model.add_rigid_patch("clamp", reference=reference, shell="panel", edges=[3])
    return model, panel, reference


def test_shell_reference_patch_records_are_stable_and_separate_from_fem_nodes(tmp_path):
    model, panel, reference = shell_model()
    model.validate()
    assert len(model.nodes) == 1 and not model.elements
    assert panel.metadata["polygon_m"] == POLYGON
    assert model.couplings["clamp"].metadata == {
        "mesh_node_group":"G_clamp_PATCH", "selection":"shell_edges", "edges":[3]}
    assert model.analysis_regions["root"].owner.id == reference
    assert step_mesh_size(model, panel) == 0.1
    assert step_mesh_size(model, replace(panel,metadata={**panel.metadata,"mesh_size":"auto"})) == 0.05
    rebuilt = Model.from_dict(model.to_dict())
    assert rebuilt.to_dict() == model.to_dict()
    from tuba.project.script import write_model_script
    text = write_model_script(tmp_path/"model.py",model,last_text=None)
    namespace = {}
    exec(compile(text,"generated_model.py","exec"),namespace)
    assert namespace["model"].to_dict() == model.to_dict()


@pytest.mark.parametrize("polygon", [
    [[0,0,0],[1,0,0]],
    [[0,0,0],[1,0,0],[0,1,float("nan")]],
    [[0,0,0],[1,0,0],[1,1,0],[0,1,0.1]],
    [[0,0,0],[2,0,0],[0,2,0],[2,2,0],[1,-1,0]],
    POLYGON + [[0,0,0]],
])
def test_invalid_shell_geometry_is_rejected_before_registry_mutation(polygon):
    model = Model("Rejected panel")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    with pytest.raises(ValueError):
        model.add_shell_panel("bad",polygon=polygon,thickness=0.01,material="Steel")
    assert not model.groups and not model.analysis_regions and not model.nodes


def test_rigid_patch_refuses_empty_invalid_and_colliding_selections():
    model, _, reference = shell_model()
    for kwargs in ({"vertices":[]}, {"edges":[4]}, {"vertices":[True]}, {"edges":[0,0]}, {"vertices":[0],"edges":[0]}):
        with pytest.raises(ValueError):
            model.add_rigid_patch("bad",reference=reference,shell="panel",**kwargs)
    with pytest.raises(ValueError,match="already exists"):
        model.add_reference_point("root",position=[0,0,0])
    with pytest.raises(ValueError,match="already exists"):
        model.add_rigid_patch("clamp",reference=reference,nodes=[reference])
    model.couplings["clamp"].metadata["edges"] = [-1]
    with pytest.raises(ValueError,match="invalid rigid patch"):
        model.validate()


def test_reference_and_component_face_patch_inputs_fail_before_mutation():
    model, _, reference = shell_model()
    for id,position in (("",[0,0,0]),("  ",[0,0,0]),("bad",[0,True,0]),("bad",[0,0,float("inf")])):
        with pytest.raises(ValueError):
            model.add_reference_point(id,position=position)
    model.add_cad_asset(id="cube_asset",source_path="unread_fixture.step")
    model.add_imported_component(id="cube",asset="cad_asset:cube_asset",name="Cube")
    model.add_analysis_region(id="cube_solid",owner="component:cube",role="solid_3d",code_aster_modelisation="3D",material="Steel",mesh_group="G_cube_SOLID")
    for faces in ([],[{}],[{"position":[None,0,0]}],[{"position":[0,0,0],"gmsh_face_tag":1}]):
        with pytest.raises(ValueError):
            model.add_rigid_patch("bad",reference=reference,component="cube",faces=faces)
    assert "bad" not in model.couplings


@pytest.mark.parametrize("node_filter", [
    {}, {"coordinate_frame":"global", "axis":"x", "comparison":"<=", "threshold":60},
    {"coordinate_frame":"source-local mm", "axis":"bad", "comparison":"<=", "threshold":60},
    {"coordinate_frame":"source-local mm", "axis":"x", "comparison":"=", "threshold":60},
    {"coordinate_frame":"source-local mm", "axis":"x", "comparison":"<=", "threshold":True},
    {"coordinate_frame":"source-local mm", "axis":"x", "comparison":"<=", "threshold":float("nan")},
])
def test_partial_component_face_filter_refuses_invalid_inputs_without_registry_mutation(node_filter):
    model, _, reference = shell_model()
    model.add_cad_asset(id="asset",source_path="fixture.step")
    model.add_imported_component(id="cube",asset="cad_asset:asset",name="Cube")
    model.add_analysis_region(id="solid",owner="component:cube",role="solid_3d",
        code_aster_modelisation="3D",material="Steel",mesh_group="G_SOLID")
    with pytest.raises(ValueError,match="node_filter"):
        model.add_rigid_patch("bad",reference=reference,component="cube",
            faces=[{"position":[0,0,0],"type":"Plane"}],node_filter=node_filter)
    assert "bad" not in model.couplings and "bad" not in model.mesh_groups


def test_partial_face_filter_round_trip_and_noncomponent_validation():
    from tests.test_interface_mapping_scene import part_model
    model, reference = part_model()
    definition = {"coordinate_frame":"source-local mm", "axis":"x", "comparison":"<=", "threshold":250}
    del model.couplings["mount"]
    del model.mesh_groups["mount"]
    model.add_rigid_patch("mount",reference=reference,component="part",
        faces=[{"position":[0,0,0],"type":"Plane","shape":"planar_face"}],node_filter=definition)
    definition["threshold"] = 999
    assert model.couplings["mount"].metadata["node_filter"]["threshold"] == 250
    rebuilt = Model.from_dict(model.to_dict())
    rebuilt.validate()
    assert rebuilt.to_dict() == model.to_dict()
    other, _, ref = shell_model()
    with pytest.raises(ValueError,match="component faces"):
        other.add_rigid_patch("bad",reference=ref,shell="panel",edges=[0],node_filter=definition)
    other.couplings["clamp"].metadata["node_filter"] = definition
    with pytest.raises(ValueError,match="node_filter"):
        other.validate()


@pytest.mark.skipif(os.environ.get("TUBA_RUN_GMSH_INTEGRATION") != "1", reason="explicit native mesh qualification")
def test_native_partial_face_patches_keep_midside_nodes_and_source_frame_after_rotation(tmp_path):
    import math
    import gmsh
    import meshio
    from tuba.meshing._gmsh import gmsh_model
    source = tmp_path/"cube.step"
    with gmsh_model(gmsh,"partial_face_cube",options={"Geometry.OCCTargetUnit":"MM"}):
        gmsh.model.occ.addBox(0,0,0,100,100,100)
        gmsh.model.occ.synchronize()
        gmsh.write(str(source))
    model = Model("Disjoint patches on a rotated STEP face")
    model.add_material("Steel",E=2.1e11,nu=.3)
    rotation = [math.sqrt(.5),0,math.sqrt(.5),0]
    model.import_step(source,id="cube",material="Steel",mesh_size=.025,
        placement={"origin":[1,2,3],"rotation":rotation})
    refs = {}
    for name, x, comparison, threshold in (("left",15,"<=",30),("right",85,">=",70)):
        refs[name] = model.add_reference_point(name,position=[1,2.05,3-x*.001])
        model.add_rigid_patch(f"{name}_patch",reference=refs[name],component="cube",
            faces=[{"position":[50,50,0],"type":"Plane"}],
            node_filter={"coordinate_frame":"source-local mm","axis":"x",
                         "comparison":comparison,"threshold":threshold})
    mesh = model.mesh(tmp_path/"partial.med")
    face_nodes = {node for cell in mesh.groups["G_SKIN_cube_solid"] for node in mesh.elements[cell]
                  if abs(mesh.nodes[node][0]-1) < 1e-9}
    midside = {node for cell in mesh.groups["G_SKIN_cube_solid"] for node in mesh.elements[cell][3:]}
    patches = {}
    for name in refs:
        reference_node = mesh.groups[f"G_NODE_{refs[name]}"][0]
        selected = set(mesh.groups[f"G_{name}_patch_PATCH"])-{reference_node}
        expected = {node for node in face_nodes
                    if (3000-1000*mesh.nodes[node][2] <= 30+1e-8 if name == "left"
                        else 3000-1000*mesh.nodes[node][2] >= 70-1e-8)}
        assert selected == expected and len(selected)>5 and selected & midside
        patches[name] = selected
    assert not patches["left"] & patches["right"]
    med = meshio.read(tmp_path/"partial.med")
    for name in refs:
        families = med.point_data["point_tags"]
        ordinals = {f"VN{i+1}" for i,family in enumerate(families)
                    if f"G_{name}_patch_PATCH" in med.point_tags.get(int(family),[])}
        assert ordinals == set(mesh.groups[f"G_{name}_patch_PATCH"])


def test_temperature_scope_resolves_regions_and_beams_without_id_collision():
    model, panel, _ = shell_model()
    model.add_rectangular_section("Frame",height_y=0.1,height_z=0.1)
    a,b = model.add_node([0,0,-1]),model.add_node([0,0,-2])
    model.add_element(id="panel",type="beam",n1=a,n2=b,section="Frame",material="Steel")
    all_field = OperationField(quantity="temperature",value=80,scope="all")
    assert [e.id for e in model.resolve_operation_field_elements(all_field)] == ["panel"]
    assert model.resolve_operation_field_regions(all_field) == [panel]
    for name in ("panel", "G_panel_SHELL"):
        region_field = OperationField(quantity="temperature",value=120,scope="group",group=name)
        assert operation_field_problem(region_field,model) is None
        assert model.resolve_operation_field_regions(region_field) == [panel]
    regional = OperationField(quantity="temperature",value=120,scope="group",group="panel")
    problems = operation_fields_problem([all_field,regional],model)
    assert len(problems) == 1 and "analysis region" in problems[0]
    assert model.resolve_operation_field_regions(OperationField(quantity="pressure",value=1e5,scope="all")) == []
    assert step_line_modelisation(model) == "POU_D_T"


def _serializer_mesh():
    from tuba.analysis import AnalysisMesh, MeshNodeSource, MeshElementSource
    points = [[0,0,0],[1,0,0],[0,1,0],[0,0,1],[.5,0,0],[.5,.5,0],[0,.5,0],[0,0,.5],[0,.5,.5],[.5,0,.5]]
    nodes = {f"VN{112 if i == 9 else i+1}":p for i,p in enumerate(points)}
    cells = {"VM101":tuple(nodes), "VS102":("VN1","VN2","VN3","VN5","VN6","VN7"),
             "SM103":("VN1","VN2","VN3"), "LM104":("VN1","VN2","VN5"),
             "LM105":("VN1","VN4"), "RC106":("VN4",)}
    roles = ["volume_cell","volume_skin","shell_cell","native_element","native_element","reference_carrier"]
    groups = {"SOLID":("VM101",),"SKIN":("VS102",),"SHELL":("SM103",),"PIPE":("LM104",),
              "FRAME":("LM105",),"REF":("RC106",), "G_NODE_N0":("VN4",),"PATCH":("VN1","VN2","VN4")}
    mesh = AnalysisMesh(id="serializer-fixture",model_revision=0,solver_name="Code_Aster",nodes=nodes,elements=cells,groups=groups,
        node_sources={n:MeshNodeSource(n,"node:N0","native_node") for n in nodes},
        element_sources={c:MeshElementSource(c,"node:N0",role) for c,role in zip(cells,roles)})
    return mesh


def test_med_ordinals_normalize_all_references_without_changing_geometry_or_lineage(tmp_path):
    from tuba.meshing.step_component import _normalize_med_ordinals, _write_exact_med
    from tuba.solver.aster_sidecar import build_solver_name_map
    mesh = _serializer_mesh()
    source = mesh.node_sources["VN112"]
    mesh = replace(mesh, node_sources={**mesh.node_sources, "VN112":replace(source, metadata={"note":"retain"}, parametric_t=0.5)},
                   surface_mesh={"vertices":[mesh.nodes[n] for n in ("VN1","VN2","VN112")],
                                 "faces":[[0,1,2]],"node_ids":["VN1","VN2","VN112"]})
    normalized = _normalize_med_ordinals(mesh)
    assert list(normalized.nodes) == [f"VN{i}" for i in range(1,11)]
    assert list(normalized.nodes.values()) == list(mesh.nodes.values())
    assert list(normalized.elements) == ["RC1","LM2","LM3","SM4","VS5","VM6"]
    assert normalized.elements["VM6"] == tuple(normalized.nodes)
    assert normalized.groups == {"SOLID":("VM6",),"SKIN":("VS5",),"SHELL":("SM4",),"PIPE":("LM3",),
                                 "FRAME":("LM2",),"REF":("RC1",),"G_NODE_N0":("VN4",),"PATCH":("VN1","VN2","VN4")}
    assert normalized.node_sources["VN10"].metadata == {"note":"retain","gmsh_node_tag":112}
    assert normalized.node_sources["VN10"].parametric_t == 0.5
    assert normalized.element_sources["VM6"].source_ref == mesh.element_sources["VM101"].source_ref
    assert normalized.element_sources["VM6"].metadata == {"gmsh_element_tag":101,"solver_element_tag":6}
    assert normalized.surface_mesh["node_ids"] == ["VN1","VN2","VN10"]
    assert normalized.surface_mesh["vertices"] == mesh.surface_mesh["vertices"]
    assert normalized.surface_mesh["faces"] == mesh.surface_mesh["faces"]
    output=tmp_path/"normalized.med"
    _write_exact_med(output,normalized,{"G_NODE_N0","PATCH"},build_solver_name_map(normalized.groups))
    _assert_dense_med_ordinals(normalized,output)


def _assert_dense_med_ordinals(mesh,path):
    import h5py
    assert list(mesh.nodes) == [f"VN{i}" for i in range(1,len(mesh.nodes)+1)]
    assert [int(cell[2:]) for cell in mesh.elements] == list(range(1,len(mesh.elements)+1))
    assert all(source.metadata["solver_element_tag"] == int(cell[2:]) for cell,source in mesh.element_sources.items())
    with h5py.File(path) as file:
        step=next(iter(file["ENS_MAA"]["mesh"].values()))
        assert step["NOE"]["NUM"][()].tolist() == list(range(1,len(mesh.nodes)+1))
        assert [bytes(row).decode().strip() for row in step["NOE"]["NOM"]] == [str(i) for i in range(1,len(mesh.nodes)+1)]
        families=sorted(step["MAI"].values(),key=lambda group:int(group.attrs["GEO"]))
        numbers=[int(number) for group in families for number in group["NUM"]]
        assert numbers == list(range(1,len(mesh.elements)+1))


def test_exact_med_serializer_preserves_native_labels_families_and_overlapping_node_groups(tmp_path):
    import h5py
    import meshio
    from tuba.meshing.step_component import _write_exact_med
    from tuba.solver.aster_sidecar import build_solver_name_map
    mesh = _serializer_mesh()
    groups = mesh.groups
    output=tmp_path/"exact.med"
    _write_exact_med(output,mesh,{"G_NODE_N0","PATCH"},build_solver_name_map(groups))
    actual=meshio.read(output)
    assert {block.type for block in actual.cells} == {"tetra10","triangle6","triangle","line3","line","vertex"}
    tetra = next(block for block in actual.cells if block.type=="tetra10")
    # Numbered one-cell Gmsh MED experiment independently establishes this order.
    assert tetra.data.tolist() == [[0,2,1,3,6,5,4,7,8,9]]
    memberships=[set(actual.point_tags.get(int(tag),[])) for tag in actual.point_data["point_tags"]]
    assert memberships[3] == {"G_NODE_N0","PATCH"}
    assert sum("PATCH" in tags for tags in memberships) == 3
    with h5py.File(output) as file:
        ensemble=file["ENS_MAA"]["mesh"]
        step=next(iter(ensemble.values()))
        # MED geometric codes independently verified with native Gmsh/libMED.
        # meshio can read a missing-GEO file that Code_Aster cannot enumerate.
        expected_geometry = {"PO1":1,"SE2":102,"SE3":103,"TR3":203,"TR6":206,"T10":310}
        assert {name:int(group.attrs["GEO"]) for name,group in step["MAI"].items()} == expected_geometry
        assert all(ensemble.attrs[name] == -1 for name in ("NXI","NXT"))
        assert all(step.attrs[name] == -1 for name in ("NXI","NXT","PVI","PVT"))
        for group in step["MAI"].values():
            assert group.attrs["CGT"] == 1 and group.attrs["CGS"] == 1
            assert group.attrs["PFL"] == b"MED_NO_PROFILE_INTERNAL"
            assert group["NOD"].attrs["NBR"] == 1 and group["FAM"].attrs["NBR"] == 1
        assert bytes(step["NOE"]["NOM"][3]).decode().strip() == "4"
        assert bytes(step["NOE"]["NOM"][-1]).decode().strip() == "112"
        assert bytes(step["MAI"]["T10"]["NOM"][0]).decode().strip() == "101"
        # Standard MED metadata preserves supplied tags; the mesher separately
        # normalizes actual Code_Aster ordinals before invoking this serializer.
        assert step["NOE"]["NUM"].dtype == np.dtype("int32")
        assert step["NOE"]["NUM"][()].tolist() == [1,2,3,4,5,6,7,8,9,112]
        expected_numbers = {"T10":101,"TR6":102,"TR3":103,"SE3":104,"SE2":105,"PO1":106}
        for name, group in [("NOE",step["NOE"]), *step["MAI"].items()]:
            assert group["NUM"].attrs["CGT"] == 1
            assert group["NUM"].attrs["NBR"] == (10 if name == "NOE" else 1)
            if name != "NOE":
                assert group["NUM"].dtype == np.dtype("int32")
                assert group["NUM"][()].tolist() == [expected_numbers[name]]


def test_med_fanout_families_have_bounded_names_and_retain_every_membership(tmp_path):
    import h5py
    import meshio
    from tuba.meshing.step_component import _write_exact_med
    from tuba.solver.aster_sidecar import build_solver_name_map
    mesh = _serializer_mesh()
    patches = {f"G_mounting_plate_sector_{i}_weld_PATCH": ("VN4",) for i in range(32)}
    regions = {f"G_overlapping_cell_region_{i}": ("VM101",) for i in range(8)}
    mesh = replace(mesh, groups={**mesh.groups, **patches, **regions})
    names = build_solver_name_map(mesh.groups)
    output = tmp_path / "fanout.med"
    _write_exact_med(output, mesh, {"G_NODE_N0", "PATCH", *patches}, names)
    with h5py.File(output) as file:
        for kind in ("NOEUD", "ELEME"):
            assert all(len(name) < 64 for name in file["FAS/mesh"][kind])
    actual = meshio.read(output)
    memberships = set(actual.point_tags[int(actual.point_data["point_tags"][3])])
    assert memberships == {names[g] for g in ("G_NODE_N0", "PATCH", *patches)}
    assert any(set(values) == {names[g] for g in ("SOLID", *regions)} for values in actual.cell_tags.values())


def test_quadratic_tetra_topology_rejects_skin_midside_mismatch():
    from tuba.meshing.step_component import _require_tetra_boundary
    cell=tuple(range(10))
    skin=[(0,1,2,4,5,6),(0,1,3,4,9,7),(0,2,3,6,8,7),(1,2,3,5,8,9)]
    _require_tetra_boundary([cell],skin)
    with pytest.raises(RuntimeError,match="quadratic skin nodes"):
        _require_tetra_boundary([cell],[(0,1,2,4,5,99),*skin[1:]])


@pytest.mark.skipif(os.environ.get("TUBA_RUN_GMSH_INTEGRATION") != "1", reason="explicit native mesh qualification")
def test_native_shell_and_mixed_lines_use_distinct_families_and_real_patch_nodes(tmp_path):
    import meshio
    model, panel, reference = shell_model()
    model.add_pipe_section("Pipe",OD=0.1,WT=0.01)
    model.add_rectangular_section("Frame",height_y=0.1,height_z=0.1)
    with model.pipe(section="Pipe",material="Steel",route="route") as route:
        route.start([2,0,0]).set_direction([1,0,0]).run(0.3)
    a,b = model.add_node([2,1,0]),model.add_node([2,1,-0.3])
    model.add_element(id="frame",type="beam",n1=a,n2=b,section="Frame",material="Steel")
    shell_corner=model.add_node(POLYGON[0])
    mesh=model.mesh(tmp_path/"combined.med",max_element_size=0.1)
    _assert_dense_med_ordinals(mesh,tmp_path/"combined.med")
    assert mesh.modelisations == {"G_panel_SHELL":"DKT","G_root_REF":"DIS_TR","G_TUBE":"TUYAU_3M","G_FRAME":"POU_D_T"}
    assert mesh.surface_mesh is None
    assert {len(mesh.elements[c]) for c in mesh.groups["G_panel_SHELL"]} == {3}
    assert {len(mesh.elements[c]) for c in mesh.groups["G_TUBE"]} == {3}
    assert {len(mesh.elements[c]) for c in mesh.groups["G_FRAME"]} == {2}
    assert len(mesh.elements[mesh.groups["G_root_REF"][0]]) == 1
    ref_node=mesh.groups[f"G_NODE_{reference}"][0]
    physical=set(mesh.groups["G_clamp_PATCH"])-{ref_node}
    assert len(physical) >= 3
    assert all(np.allclose(mesh.nodes[n][0],0) for n in physical)
    assert all(n in {node for c in mesh.groups[panel.mesh_group] for node in mesh.elements[c]} for n in physical)
    assert mesh.groups[f"G_NODE_{shell_corner}"][0] in {node for c in mesh.groups[panel.mesh_group] for node in mesh.elements[c]}
    med=meshio.read(tmp_path/"combined.med")
    assert {block.type for block in med.cells} >= {"triangle","line","line3","vertex"}
    families=med.point_data["point_tags"]
    names=med.point_tags
    selected={i for i,family in enumerate(families) if "G_clamp_PATCH" in names.get(int(family),[])}
    assert len(selected) == len(mesh.groups["G_clamp_PATCH"])
    assert all(f"G_NODE_{node}" in {name for group in names.values() for name in group} for node in model.nodes)


@pytest.mark.skipif(os.environ.get("TUBA_RUN_GMSH_INTEGRATION") != "1", reason="explicit native mesh qualification")
def test_native_multiple_step_solids_reselect_physical_faces_and_keep_placements(tmp_path):
    import gmsh
    import meshio
    from tuba.meshing._gmsh import gmsh_model
    source=tmp_path/"cube.step"
    with gmsh_model(gmsh,"cube_fixture",options={"General.Terminal":0,"Geometry.OCCTargetUnit":"MM"}):
        gmsh.model.occ.addBox(0,0,0,100,100,100)
        gmsh.model.occ.synchronize()
        gmsh.write(str(source))
    model, _, reference = shell_model()
    model.add_material("SecondSteel",E=1.8e11,nu=0.28)
    for i, material in enumerate(("Steel","SecondSteel")):
        model.import_step(source,id=f"cube{i}",material=material,mesh_size=0.05,
                          placement={"origin":[2*i,0,0]})
    face_reference=model.add_reference_point("face",position=[0,0.05,0.05])
    model.add_rigid_patch("cube_face",reference=face_reference,component="cube0",
                          faces=[{"position":[0,50,50],"type":"Plane"}])
    mesh=model.mesh(tmp_path/"multiple.med",max_element_size=0.05)
    _assert_dense_med_ordinals(mesh,tmp_path/"multiple.med")
    assert mesh.modelisations == {"G_panel_SHELL":"DKT","G_root_REF":"DIS_TR","G_face_REF":"DIS_TR",
                                 "G_cube0_SOLID":"3D","G_cube1_SOLID":"3D"}
    assert all(len(mesh.elements[c])==10 for raw in ("G_cube0_SOLID","G_cube1_SOLID") for c in mesh.groups[raw])
    assert all(len(mesh.elements[c])==6 for raw in ("G_SKIN_cube0_solid","G_SKIN_cube1_solid") for c in mesh.groups[raw])
    first={n for c in mesh.groups["G_cube0_SOLID"] for n in mesh.elements[c]}
    second={n for c in mesh.groups["G_cube1_SOLID"] for n in mesh.elements[c]}
    assert not first.intersection(second)
    assert np.allclose(np.max([mesh.nodes[n] for n in first],axis=0),[0.1,0.1,0.1])
    assert np.allclose(np.min([mesh.nodes[n] for n in second],axis=0),[2,0,0])
    reference_node=mesh.groups[f"G_NODE_{face_reference}"][0]
    patch=set(mesh.groups["G_cube_face_PATCH"])-{reference_node}
    assert len(patch)>4 and patch <= first
    assert all(abs(mesh.nodes[n][0])<1e-10 for n in patch)
    med=meshio.read(tmp_path/"multiple.med")
    assert {block.type for block in med.cells} == {"tetra10","triangle6","triangle","vertex"}
    names={name for group in med.point_tags.values() for name in group}
    assert {"G_cube_face_PATCH","G_clamp_PATCH",f"G_NODE_{reference}"} <= names
