"""Real meshing changes, scoped density, finite CAD distance and native fields."""
from dataclasses import replace
import json

import gmsh
import meshio
import numpy as np
import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh
from tuba.meshing import build_pipe_volume_mesh
from tuba.meshing.policy import resolve_mesh_policy, element_point, gmsh_policy
from tuba.meshing.quality import mesh_review, MeshQualityError
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_mesh import AsterMeshGenerator, generate_analysis_mesh
from tuba.solver.aster_loads import node_temperature_entries
from tests.test_mesh_policy import straight_model
from tests.test_pipe_volume_mesh import _straight_pipe_model, _bend_pipe_model, _tee_model


def test_native_narrow_off_midpoint_plateau_and_temperature_stations(tmp_path):
    model = straight_model()
    elem = model.elements[0]
    model.set_mesh_size(.2)
    model.add_mesh_refinement("narrow",target={"kind":"sphere","center_m":[.231,0,0],"radius_m":.000001},
                              size_m=.005,transition_distance_m=.01)
    operation = model.define_operation("heat",gravity=False)
    operation.add_field("temperature",10,node_ids=[elem.n1])
    operation.add_field("temperature",110,node_ids=[elem.n2])
    generator = AsterMeshGenerator()
    mesh = generator._write_mail(model,tmp_path/"native.mail",analysis_mesh_id="native")
    stations = generator._mesh_stations[elem.id]
    assert .231 in stations
    assert len({round(b-a,9) for a,b in zip(stations,stations[1:])})>2
    temperatures = dict(node_temperature_entries(model,operation.to_load_case(),[],generator._element_solver_nodes))
    for id,source in mesh.node_sources.items():
        if source.parametric_t is not None:
            # Independent expectation from real x-coordinates, rather than reproducing the station formula.
            assert temperatures[id] == pytest.approx(10+100*mesh.nodes[id][0])
            assert source.parametric_t == pytest.approx(mesh.nodes[id][0])
    assert all(len(mesh.elements[id])==3 for id in mesh.groups[elem.id])
    assert mesh.mesh_review["quality"]["invalid_count"]==0
    study = CodeAsterSolver().export_analysis_study(model,"heat",tmp_path/"study")
    assert study.metadata["compiler_inputs"]["element_stations"][elem.id]==stations
    assert study.metadata["compiler_inputs"]["mesh_policy"]==mesh.mesh_review["policy"]


def test_native_grazing_box_stations_and_spatial_temperature_agree_with_compiler(tmp_path):
    model = Model("GrazingBoxFields")
    model.add_material("steel", E=2.1e11, nu=.3)
    model.add_pipe_section("pipe", OD=.1, WT=.01)
    with model.pipe(section="pipe", material="steel") as route:
        route.start([-.01,.05,.05])
        route.end([.01,-.15,.05])
    element = model.elements[0]
    model.set_mesh_size(.1)
    model.add_mesh_refinement("box", target={"kind":"box", "min_m":[0,0,0], "max_m":[.1,.1,.1]},
                              size_m=.001, influence_distance_m=.00498, transition_distance_m=5e-7)
    operation = model.define_operation("heat", gravity=False)
    operation.add_field("temperature",10,node_ids=[element.n1])
    operation.add_field("temperature",110,node_ids=[element.n2])
    solver = CodeAsterSolver()
    study = solver.export_analysis_study(model,"heat",tmp_path)
    mesh = AnalysisMesh.from_dict(json.loads((tmp_path/"study_manifest.json").read_text())["analysis_mesh"])
    stations = solver._mesh_stations[element.id]
    closest_t = .0102/.0404
    assert all(np.hypot(.02,.2)*(b-a) <= .001*(1+1e-12)
               for a,b in zip(stations,stations[1:]) if a <= closest_t <= b)
    temperatures = dict(node_temperature_entries(model,operation.to_load_case(),[],solver._element_solver_nodes))
    for node_id,source in mesh.node_sources.items():
        if source.parametric_t is not None:
            # Independently recover the fraction and temperature from spatial y.
            y = mesh.nodes[node_id][1]
            assert source.parametric_t == pytest.approx((.05-y)/.2)
            assert temperatures[node_id] == pytest.approx(10+500*(.05-y))
    assert all(len(mesh.elements[cell])==3 for cell in mesh.groups[element.id])
    assert mesh.mesh_review["quality"]["invalid_count"]==0
    assert study.metadata["compiler_inputs"]["element_stations"][element.id]==stations
    assert study.metadata["compiler_inputs"]["mesh_policy"]==mesh.mesh_review["policy"]


def test_nonuniform_bend_midpoints_groups_and_material_assignment(tmp_path):
    model,_,_ = _bend_pipe_model()
    elem = model.elements[0]
    model.set_mesh_size(.012)
    model.add_mesh_refinement("bend",target={"kind":"sphere","center_m":element_point(model,elem,.27).tolist(),"radius_m":.001},
                              size_m=.003,transition_distance_m=.03)
    operation = model.define_operation("heat",gravity=False)
    operation.add_field("temperature",10,node_ids=[elem.n1])
    operation.add_field("temperature",110,node_ids=[elem.n2])
    solver = CodeAsterSolver()
    study = solver.export_analysis_study(model,"heat",tmp_path)
    mesh = AnalysisMesh.from_dict(json.loads((tmp_path/"study_manifest.json").read_text())["analysis_mesh"])
    generated = [s for s in mesh.node_sources.values() if s.parametric_t is not None]
    assert generated
    for source in generated:
        assert mesh.nodes[source.node_id] == pytest.approx(element_point(model,elem,source.parametric_t))
    assert len(mesh.groups[elem.id])>16
    material_group = solver._material_group_name(elem.material)
    assert mesh.groups[material_group]==mesh.groups[elem.id]
    assert all(len(mesh.elements[id])==3 for id in mesh.groups[elem.id])
    comm=(tmp_path/"study.comm").read_text()
    assert "GROUP_MA='bend_0'" in comm
    assert study.metadata["compiler_inputs"]["element_stations"][elem.id]==solver._mesh_stations[elem.id]


@pytest.mark.parametrize("builder,target", [(_straight_pipe_model,"pipe_0"),(_bend_pipe_model,"bend_0"),(_tee_model,"branch")])
def test_refines_real_hexa20_straight_bend_and_tee(tmp_path,builder,target):
    model,*_ = builder()
    ids=[e.id for e in model.elements]
    coarse=build_pipe_volume_mesh(model,tmp_path/"coarse.med",element_ids=ids,max_element_size=.005)
    model.add_mesh_refinement("detail",target=f"element:{target}",size_m=.003,transition_distance_m=.01)
    fine=build_pipe_volume_mesh(model,tmp_path/"fine.med",element_ids=ids,max_element_size=.005)
    assert len(fine.groups["G_SOLID_region_0"])>len(coarse.groups["G_SOLID_region_0"])
    assert fine.analysis_mesh.mesh_review["quality"]["invalid_count"]==0
    assert all(len(fine.analysis_mesh.elements[id])==20 for id in fine.groups["G_SOLID_region_0"])
    assert set(coarse.groups)==set(fine.groups)
    assert "hexahedron20" in {c.type for c in meshio.read(fine.med_path).cells}


def test_step_face_scope_remote_density_and_exact_trimmed_distance(tmp_path):
    from examples.code_aster_step_component_review import SOURCE
    from tuba.meshing._gmsh import gmsh_model
    model=Model("Two components")
    model.add_material("steel",E=2.1e11,nu=.3)
    for name,offset in (("spool",0),("remote",.211)):
        model.import_step(SOURCE,id=name,material="steel",mesh_size=.012 if name=="spool" else .025,unit_scale_to_m=1.,
                          placement={"origin":[offset,0,0],"rotation":[1,0,0,0]},
                          interfaces={"outlet":{"position":[.2,0,0],"axis":[1,0,0],"radius":.05}})
    model.set_mesh_size(.025)
    model.set_mesh_size(.012,region="spool_solid")
    with gmsh_model(gmsh,"curvature_scope",options={"Mesh.MeshSizeFromCurvature":24}):
        coarse=model.mesh(tmp_path/"coarse.med")
    model.add_mesh_refinement("outlet",target="port:spool_outlet",size_m=.003,transition_distance_m=.02)
    policy=resolve_mesh_policy(model)
    assert policy.preview()["samples"][0]["status"]=="pending_cad_binding"
    # The neighbouring solid starts 11 mm from the refined face, inside the
    # transition zone. Its coarser base also catches an unscoped SizeMax clamp.
    assert policy.size_at((.211,.045,0),source_ref="component:remote")==.025
    with gmsh_model(gmsh,"curvature_scope",options={"Mesh.MeshSizeFromCurvature":24}):
        fine=model.mesh(tmp_path/"fine.med")
    assert len(fine.groups["G_spool_outlet"])>len(coarse.groups["G_spool_outlet"])*2
    assert len(fine.groups["G_remote_SOLID"])/len(coarse.groups["G_remote_SOLID"])==pytest.approx(1.,rel=.05)
    def remote_edges(mesh):
        lengths=[]
        for id in mesh.groups["G_remote_SOLID"]:
            points=[np.asarray(mesh.nodes[n]) for n in mesh.elements[id][:4]]
            lengths.extend(np.linalg.norm(a-b) for i,a in enumerate(points) for b in points[i+1:])
        return np.quantile(lengths,[.1,.5,.9])
    assert remote_edges(fine)==pytest.approx(remote_edges(coarse),rel=.05)
    assert fine.mesh_review["quality"]["invalid_count"]==0
    assert all(s["status"]=="resolved" for s in fine.mesh_review["size_preview"]["samples"])
    assert {c.type for c in meshio.read(fine.files["med"]).cells}=={"tetra10","triangle6"}
    # A finite annulus's bore has positive distance to the face even on its plane.
    from tuba.geometry.step_analysis_importer import StepAnalysisImporter
    with gmsh_model(gmsh,"finite_distance",options={"Geometry.OCCTargetUnit":"MM"}):
        imported=gmsh.model.occ.importShapes(str(SOURCE))
        gmsh.model.occ.synchronize()
        selector=model.ports["spool_outlet"].metadata["face_selector"]
        face=StepAnalysisImporter.resolve_face_selector(imported,selector)
        with gmsh_policy(gmsh,policy,{},face_bindings={"outlet":face}) as bound:
            assert bound.size_at((.2,0,0),source_ref="component:spool")==pytest.approx(.012)
            assert bound.size_at((.2,.045,0),source_ref="component:spool")==pytest.approx(.003)
            assert bound.size_at((.2,.2,0),source_ref="component:spool")==pytest.approx(.012)


def test_shell_and_line_refinement_retains_families(tmp_path):
    model=straight_model(.2)
    shell=model.add_shell_panel("panel",polygon=[[0,0,0],[.2,0,0],[.2,.2,0],[0,.2,0]],thickness=.005,material="steel",mesh_size=.05)
    coarse=model.mesh(tmp_path/"coarse.med")
    model.set_mesh_size(.05)
    model.set_mesh_size(.025,region=shell.id)
    model.add_mesh_refinement("corner",target={"kind":"sphere","center_m":[.2,0,0],"radius_m":.025},size_m=.01,transition_distance_m=.05)
    fine=model.mesh(tmp_path/"fine.med")
    assert len(fine.groups[shell.mesh_group])>len(coarse.groups[shell.mesh_group])
    assert len(fine.groups["G_TUBE"])>len(coarse.groups["G_TUBE"])
    assert {c.type for c in meshio.read(fine.files["med"]).cells}=={"triangle","line3"}
    assert fine.mesh_review["quality"]["invalid_count"]==0


def test_invalid_quality_retains_cell_location_and_blocks_publication(tmp_path):
    model=straight_model()
    model.set_mesh_size(.1)
    policy=resolve_mesh_policy(model)
    mesh=generate_analysis_mesh(model)
    id=next(iter(mesh.elements))
    broken=replace(mesh,elements={**mesh.elements,id:(mesh.elements[id][0],mesh.elements[id][0])})
    output=tmp_path/"invalid.med"
    with pytest.raises(MeshQualityError):
        mesh_review(broken,policy,output_path=output)
    diagnostic=json.loads(output.with_suffix(".quality.json").read_text())
    assert diagnostic["quality"]["invalid_cell_ids"]==[id]
    assert diagnostic["quality"]["problem_locations"][0]["source_ref"]==f"element:{model.elements[0].id}"
    assert not output.exists()


def test_batched_quality_preserves_corner_metrics_and_full_failure_bounds(tmp_path):
    from tuba.analysis import MeshElementSource

    nodes = {"a":(0,0,0), "b":(2,0,0), "c":(0,3,0), "d":(2,3,0),
             "ab":(1,0,0), "bc":(1,1.5,0), "ac":(0,1.5,0), "bd":(2,1.5,0), "cd":(1,3,0)}
    cells = {"LM1":("a","b"), "LM2":("a","c","ac"), "SM3":("a","b","c"),
             "VS4":("a","b","c","ab","bc","ac"),
             "VS5":("a","b","d","c","ab","bd","cd","ac"), "RC6":("a",)}
    roles = {"LM1":"native_element", "LM2":"native_element", "SM3":"shell_cell",
             "VS4":"volume_skin", "VS5":"volume_skin", "RC6":"reference_carrier"}
    mesh = AnalysisMesh(id="corner-metrics", model_revision=0, solver_name="Code_Aster",
        nodes=nodes, elements=cells, groups={}, node_sources={},
        element_sources={id:MeshElementSource(id,"analysis_region:panel",roles[id]) for id in cells})
    policy = resolve_mesh_policy(straight_model())
    review = mesh_review(mesh,policy)
    metrics = {item["applicable_family"]:item for item in review["quality"]["metrics"]}
    assert {family:item["minimum"] for family,item in metrics.items()} == {
        "SEG2":2., "SEG3":3., "TRI3":3., "TRI6":3., "QUAD8":6.}
    assert review["statistics"]["by_family"] == dict.fromkeys(["SEG2","SEG3","TRI3","TRI6","QUAD8","POI1"],1)
    broken = replace(mesh,elements={**cells,"VS5":("a","b","a","b","ab","bd","cd","ac")})
    with pytest.raises(MeshQualityError) as caught:
        mesh_review(broken,policy,output_path=tmp_path/"invalid.med")
    quality = caught.value.mesh_review["quality"]
    assert quality["invalid_cell_ids"] == ["VS5"]
    assert quality["problem_locations"] == [{"cell_id":"VS5", "source_ref":"analysis_region:panel",
        "metric":"area_m2", "value":0., "bounds_m":[0.,0.,0.,2.,3.,0.]}]


def test_bulk_native_quality_retains_invalid_poor_and_nonfinite_locations(tmp_path):
    from types import SimpleNamespace
    from tuba.analysis import MeshElementSource

    points = [(0,0,0),(1,0,0),(0,1,0),(0,0,1),(.5,0,0),(.5,.5,0),
              (0,.5,0),(0,0,.5),(0,.5,.5),(.5,0,.5)]
    nodes = {f"VN{i}":point for i,point in enumerate(points,1)}
    tags = {"VM1":13,"VM2":29,"VM3":47}
    def measured(actual_tags, metric):
        assert actual_tags == [13,29,47] and metric == "minSJ"
        return [-1.,.05,float("nan")]  # deterministic API fixture, never solver results
    native = SimpleNamespace(model=SimpleNamespace(mesh=SimpleNamespace(getElementQualities=measured)))
    mesh = AnalysisMesh(id="invalid-solid-fixture",model_revision=0,solver_name="Code_Aster",
        nodes=nodes,elements={id:tuple(nodes) for id in tags},groups={},node_sources={},
        element_sources={id:MeshElementSource(id,"component:solid","volume_cell",
            metadata={"gmsh_element_tag":tag}) for id,tag in tags.items()})
    with pytest.raises(MeshQualityError) as caught:
        mesh_review(mesh,resolve_mesh_policy(straight_model()),gmsh=native,output_path=tmp_path/"invalid.med")
    quality = caught.value.mesh_review["quality"]
    assert quality["invalid_cell_ids"] == ["VM1","VM3"]
    assert quality["poor_cell_ids"] == ["VM2"]
    assert [location["value"] for location in quality["problem_locations"]] == [-1.,None,.05]
    assert all(location["bounds_m"] == [0.,0.,0.,1.,1.,1.] for location in quality["problem_locations"])
    assert json.loads((tmp_path/"invalid.quality.json").read_text())["quality"] == quality


def test_refined_shell_preserves_caller_gmsh_session_and_callback(tmp_path,monkeypatch):
    model=Model("Shell")
    model.add_material("steel",E=2.1e11,nu=.3)
    model.add_shell_panel("panel",polygon=[[0,0,0],[.1,0,0],[.1,.1,0],[0,.1,0]],thickness=.005,material="steel",mesh_size=.05)
    model.set_mesh_size(.02)
    gmsh.initialize(interruptible=False)
    try:
        gmsh.model.add("caller")
        a=gmsh.model.occ.addPoint(0,0,1)
        b=gmsh.model.occ.addPoint(1,0,1)
        gmsh.model.occ.addLine(a,b)
        gmsh.model.occ.synchronize()
        calls=[]
        gmsh.model.mesh.setSizeCallback(lambda dim,tag,x,y,z,lc: calls.append((x,y,z)) or .1)
        callback=gmsh.api_callback_
        threads=gmsh.option.getNumber("General.NumThreads")
        sizing_options={name:gmsh.option.getNumber(name) for name in
                        ("Mesh.MeshSizeFromPoints","Mesh.MeshSizeExtendFromBoundary","Mesh.MeshSizeMin")}
        monkeypatch.setattr(gmsh.model.mesh,"setSizeCallback",lambda *args: pytest.fail("meshing must use native fields"))
        model.mesh(tmp_path/"shell.med")
        assert gmsh.isInitialized() and gmsh.model.getCurrent()=="caller"
        assert gmsh.api_callback_ is callback
        assert gmsh.option.getNumber("General.NumThreads")==threads
        assert {name:gmsh.option.getNumber(name) for name in sizing_options}==sizing_options
        gmsh.model.mesh.generate(1)
        assert calls
    finally:
        gmsh.finalize()


@pytest.mark.parametrize("target", [
    {"kind":"sphere","center_m":[.05,0,0],"radius_m":.01},
    {"kind":"box","min_m":[.04,-.01,-.01],"max_m":[.06,.01,.01]},
])
def test_native_spatial_fields_refine_real_curve_without_callback(target,monkeypatch):
    from tuba.meshing._gmsh import gmsh_model
    model=straight_model(.1)
    model.set_mesh_size(.02)
    model.add_mesh_refinement("local",target=target,size_m=.002,transition_distance_m=.01)
    policy=resolve_mesh_policy(model)
    monkeypatch.setattr(gmsh.model.mesh,"setSizeCallback",lambda *args: pytest.fail("meshing must use native fields"))
    with gmsh_model(gmsh,"spatial_fields"):
        a=gmsh.model.occ.addPoint(0,0,0)
        b=gmsh.model.occ.addPoint(.1,0,0)
        curve=gmsh.model.occ.addLine(a,b)
        gmsh.model.occ.synchronize()
        with gmsh_policy(gmsh,policy,{(1,curve):f"element:{model.elements[0].id}"}):
            gmsh.model.mesh.generate(1)
        tags,coords,_=gmsh.model.mesh.getNodes(1,curve,includeBoundary=True)
        positions=dict(zip(map(int,tags),np.asarray(coords).reshape(-1,3)))
        _,_,blocks=gmsh.model.mesh.getElements(1,curve)
        lengths=[]
        remote=[]
        for a,b in np.asarray(blocks[0]).reshape(-1,2):
            midpoint=(positions[a][0]+positions[b][0])/2
            length=np.linalg.norm(positions[b]-positions[a])
            if .045<=midpoint<=.055:
                lengths.append(length)
            if midpoint<.02 or midpoint>.08:
                remote.append(length)
        assert lengths and max(lengths)<.0021
        assert remote and np.median(remote)>5*np.median(lengths)
        assert len(gmsh.model.mesh.field.list())==0


def test_generic_curved_step_face_selector_is_supported_and_stale_selection_fails(tmp_path):
    from examples.code_aster_step_component_review import build_model
    model=build_model(mesh_size=.015)
    selector=next(p.metadata["face_selector"] for p in model.ports.values())
    # The source-local importer supports finite general face selection by type,
    # position and area. Obtain a cylinder from its persistent face partitions.
    from examples.code_aster_step_component_review import SOURCE
    from tuba.geometry.step_analysis_importer import StepAnalysisImporter
    from tuba.meshing._gmsh import gmsh_model
    with gmsh_model(gmsh,"selector",options={"Geometry.OCCTargetUnit":"MM"}):
        imported=gmsh.model.occ.importShapes(str(SOURCE))
        gmsh.model.occ.synchronize()
        face=next(f for f in StepAnalysisImporter()._describe_faces(imported) if f["type"]=="Cylinder")
        selector={k:face[k] for k in ("type","position","area")}
    model.add_mesh_refinement("curved",target={"kind":"face","component":"spool","selector":selector},size_m=.006)
    mesh=model.mesh(tmp_path/"curved.med")
    assert mesh.mesh_review["quality"]["invalid_count"]==0
    stale=Model.from_dict(model.to_dict())
    stale.mesh_refinements["curved"]["target"]["selector"]["position"][0]+=1
    with pytest.raises(Exception,match="exactly one face"):
        stale.mesh(tmp_path/"stale.med")
    assert not (tmp_path/"stale.med").exists()
