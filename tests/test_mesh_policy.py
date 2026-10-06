"""Authored mesh sizes are pure, deterministic and identity bearing."""
import pytest

from tuba import Model
from tuba.meshing.policy import resolve_mesh_policy


def straight_model(length=1.0):
    model = Model("MeshPolicy")
    model.add_material("steel", E=2.1e11, nu=.3)
    model.add_pipe_section("pipe", OD=.1, WT=.01)
    with model.pipe(section="pipe", material="steel") as route:
        route.start([0, 0, 0])
        route.run(length)
    model.define_load_case("case", gravity=False)
    return model


def test_linear_transition_and_overlap_order():
    records = [("coarse", .04), ("fine", .02)]
    policies = []
    for order in (records, list(reversed(records))):
        model = straight_model()
        model.set_mesh_size(.1)
        for name, size in order:
            model.add_mesh_refinement(name, target={"kind": "sphere", "center_m": [0, 0, 0], "radius_m": .1},
                                      size_m=size, transition_distance_m=.2)
        plan = resolve_mesh_policy(model)
        assert plan.size_at((0, 0, 0)) == pytest.approx(.02)
        assert plan.size_at((.2, 0, 0)) == pytest.approx(.06)
        assert plan.size_at((.4, 0, 0)) == pytest.approx(.1)
        assert plan.to_dict() == resolve_mesh_policy(Model.from_dict(model.to_dict())).to_dict()
        policies.append(plan.to_dict())
    assert policies[0] == policies[1]


@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf")])
def test_invalid_sizes(value):
    model = straight_model()
    with pytest.raises(ValueError, match="positive.*finite"):
        model.set_mesh_size(value)
    with pytest.raises(ValueError, match="positive.*finite"):
        model.add_mesh_refinement("bad", target="element:missing", size_m=value)


def test_targets_and_removal():
    model = straight_model()
    model.set_mesh_size(.1)
    element = model.elements[0]
    model.add_mesh_refinement("line", target=f"element:{element.id}", size_m=.02)
    assert resolve_mesh_policy(model).size_at((.5, 0, 0), source_ref=f"element:{element.id}") == .02
    with pytest.raises(ValueError, match="already exists"):
        model.add_mesh_refinement("line", target=f"element:{element.id}", size_m=.02)
    model.remove_mesh_refinement("line")
    assert not model.mesh_refinements
    with pytest.raises(ValueError, match="missing"):
        model.remove_mesh_refinement("line")


@pytest.mark.parametrize("target", ["element:missing", "group:empty", "node:missing", {"kind": "triangle"}])
def test_invalid_or_empty_targets(target):
    model = straight_model()
    model.groups["empty"] = {"elements": []}
    with pytest.raises(ValueError, match="missing|empty|Unsupported"):
        model.add_mesh_refinement("bad", target=target, size_m=.01)


def test_invalid_transitions_and_finite_regions():
    model = straight_model()
    for width in (0, True, float("inf"), -1):
        with pytest.raises(ValueError, match="transition_distance_m"):
            model.add_mesh_refinement("bad", target={"kind": "sphere", "center_m": [0, 0, 0], "radius_m": .1},
                                      size_m=.01, transition_distance_m=width)
    with pytest.raises(ValueError, match="bounds"):
        model.add_mesh_refinement("bad", target={"kind": "box", "min_m": [0, 0, 0], "max_m": [0, 1, 1]}, size_m=.01)


@pytest.mark.parametrize("height", [.05, -.003], ids=["edge", "corner"])
def test_finite_box_grazing_straight_interval_cannot_skip_plateau(height):
    import math
    from tuba.meshing.policy import element_point, line_stations
    model = Model("GrazingBox")
    model.add_material("steel", E=2.1e11, nu=.3)
    model.add_pipe_section("pipe", OD=.1, WT=.01)
    with model.pipe(section="pipe", material="steel") as route:
        route.start([-.01, .05, height])
        route.end([.01, -.15, height])
    element = model.elements[0]
    closest_t = .0102 / .0404  # Independent projection onto the finite edge/corner.
    closest_distance = math.hypot(.005 / math.sqrt(1.01), min(0., height))
    influence = .00498 if height > 0 else closest_distance + 4.8e-6
    model.set_mesh_size(.1)
    model.add_mesh_refinement("box", target={"kind":"box", "min_m":[0,0,0], "max_m":[.1,.1,.1]},
                              size_m=.001, influence_distance_m=influence,
                              transition_distance_m=5e-7)
    policy = resolve_mesh_policy(model)
    assert policy.size_at(element_point(model, element, closest_t), source_ref=f"element:{element.id}")==.001
    stations = line_stations(model, policy)[element.id]
    length = math.hypot(.02, .2)
    covering = [(a,b) for a,b in zip(stations,stations[1:]) if a <= closest_t <= b]
    assert covering and all(length*(b-a) <= .001*(1+1e-12) for a,b in covering)
    assert stations == line_stations(model, policy)[element.id]


def test_finite_box_grazing_arc_interval_cannot_skip_plateau():
    import math
    from tests.test_pipe_volume_mesh import _bend_pipe_model
    from tuba.meshing.policy import line_stations
    model, *_ = _bend_pipe_model()
    element = model.elements[0]
    closest_t = .371
    theta = closest_t*math.pi/2
    # This finite box corner lies 5 mm radially outside the quarter-circle.
    # Its center projection and face-plane crossings differ from closest_t.
    corner_x, corner_y = .105*math.sin(theta), .1-.105*math.cos(theta)
    model.set_mesh_size(.1)
    model.add_mesh_refinement("box", target={"kind":"box", "min_m":[corner_x,corner_y-.1,-.05],
                                             "max_m":[corner_x+.1,corner_y,.05]},
                              size_m=.001, influence_distance_m=.0050001, transition_distance_m=5e-7)
    policy = resolve_mesh_policy(model)
    point = (.1*math.sin(theta), .1*(1-math.cos(theta)), 0.)
    assert policy.size_at(point, source_ref=f"element:{element.id}")==.001
    stations = line_stations(model, policy, minimum_segments={element.id:16})[element.id]
    covering = [(a,b) for a,b in zip(stations,stations[1:]) if a <= closest_t <= b]
    assert covering and all(.1*math.pi/2*(b-a) <= .001*(1+1e-12) for a,b in covering)
    assert stations == line_stations(model, policy, minimum_segments={element.id:16})[element.id]


def test_legacy_and_authored_identity():
    from tuba.analysis.provenance import build_solver_input_identity
    model = straight_model()
    original = build_solver_input_identity(model, "case")
    # Independently checked against cefd4e5's original provenance function.
    assert original.fingerprint == "543fc51efbc10c1f1ecd3860e7f05a3a12af16eccc276e8c22e36b10e74d38a3"
    assert "mesh_settings" not in model.to_dict()
    assert "mesh_refinements" not in model.to_dict()
    assert original == build_solver_input_identity(Model.from_dict(model.to_dict()), "case")
    model.set_mesh_size(.1)
    changed = build_solver_input_identity(model, "case")
    assert changed != original
    model.set_mesh_size(.2)
    assert changed != build_solver_input_identity(model, "case")


def test_generated_script_roundtrip():
    from tuba.project.script import generate_model_script
    model = straight_model()
    model.set_mesh_size(.1)
    model.add_mesh_refinement("box", target={"kind": "box", "min_m": [0, -.1, -.1], "max_m": [.2, .1, .1]}, size_m=.01)
    namespace = {}
    exec(generate_model_script(model), namespace)
    assert namespace["model"].to_dict() == model.to_dict()


def test_global_region_and_invocation_precedence():
    model = straight_model()
    shell = model.add_shell_panel("panel",polygon=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],thickness=.01,material="steel")
    model.set_mesh_size(.1)
    model.set_mesh_size(.04,region=shell.id)
    model.add_mesh_refinement("local",target="analysis_region:panel",size_m=.02)
    plan=resolve_mesh_policy(model)
    assert plan.base_size("group:panel")==.04
    assert plan.base_size(f"element:{model.elements[0].id}")==.1
    assert plan.size_at((.5,.5,0),source_ref="group:panel")==.02
    assert resolve_mesh_policy(model,max_element_size=.08).base_size("group:panel")==.08
    assert plan.to_dict()["refinements"][0]["transition_distance_m"]==pytest.approx(.12)


def test_units_are_explicit_metres_independent_of_cad_source_scale():
    from examples.code_aster_step_component_review import SOURCE
    model=Model("Millimetre CAD")
    model.add_material("steel",E=2.1e11,nu=.3)
    model.import_step(SOURCE,id="spool",material="steel",unit_scale_to_m=.001,mesh_size=.012,
        interfaces={"outlet":{"position":[.2,0,0],"axis":[1,0,0],"radius":.05}})
    model.set_mesh_size(.01)
    model.add_mesh_refinement("port",target="port:spool_outlet",size_m=.003)
    plan=resolve_mesh_policy(model)
    assert plan.base_size("component:spool")==.01
    assert plan.to_dict()["refinements"][0]["size_m"]==.003
    assert plan.to_dict()["source_geometry"]["component:spool"]["unit_scale_to_m"]==.001
    assert model.ports["spool_outlet"].position==pytest.approx((.0002,0,0))


def test_assembly_capture_skips_duplicate_refinement_replay():
    from tuba.assemblies import assemble
    from tuba.project.script import generate_model_script
    model=straight_model()
    code='''def size_detail(model, element, size):
    """Refine one existing element using a size in metres."""
    model.add_mesh_refinement("detail",target="element:"+element,size_m=size)
'''
    namespace={}
    exec(code,namespace)
    assemble(model,"size_detail",_namespace=namespace,element=model.elements[0].id,size=.01)
    assert model.assembly_calls[-1]["created"]["keyed"]["mesh_refinements"]==["detail"]
    text=generate_model_script(model,prologue=[code])
    rebuilt={}
    exec(text,rebuilt)
    assert rebuilt["model"].to_dict()==model.to_dict()


def test_pure_resolution_and_preview_do_not_initialize_cad(monkeypatch):
    from examples.code_aster_step_component_review import build_model
    import gmsh
    model=build_model(mesh_size=.012)
    model.add_mesh_refinement("face",target="port:spool_outlet",size_m=.003)
    monkeypatch.setattr(gmsh,"initialize",lambda *args,**kw: pytest.fail("pure policy invoked CAD"))
    plan=resolve_mesh_policy(model)
    assert any(s["status"]=="pending_cad_binding" for s in plan.preview(max_samples=10)["samples"])
    assert len(plan.preview(max_samples=10)["samples"])==10
    with pytest.raises(ValueError,match="exact CAD face binding"):
        plan.size_at((.2,.045,0),source_ref="component:spool")


def test_unconfirmed_and_unsupported_targets():
    from dataclasses import replace
    from examples.code_aster_step_component_review import build_model
    model=build_model(mesh_size=.012)
    model.ports["spool_outlet"]=replace(model.ports["spool_outlet"],status="detected")
    with pytest.raises(ValueError,match="unconfirmed"):
        model.add_mesh_refinement("bad",target="port:spool_outlet",size_m=.003)
    with pytest.raises(ValueError,match="Unsupported"):
        model.add_mesh_refinement("bad",target={"kind":"face","component":"spool","selector":{"position":[0,0,0],"gmsh_face_tag":2}},size_m=.003)


def test_legacy_interface_exact_execution_moves_identity():
    from examples.code_aster_step_component_review import build_model
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    from tuba.analysis.provenance import build_solver_input_identity
    model=build_model(mesh_size=.012,interface_mesh_sizes={"outlet":.003})
    resolved=MixedCodeAsterStudyExporter().step_study_inputs(model,"Bending")
    inputs=resolved.compiler_inputs
    assert inputs["mesh_policy"]==resolve_mesh_policy(model).to_dict()
    assert inputs["mesh_policy"]["refinements"][0]["transition_distance_m"]==pytest.approx(.036)
    before=build_solver_input_identity(model,"Bending",compiler_id=resolved.solver_input_identity.compiler_id,
        compiler_inputs={key:value for key,value in inputs.items() if key!="mesh_policy"})
    assert before!=resolved.solver_input_identity
    plain=build_model(mesh_size=.012)
    assert "mesh_policy" not in MixedCodeAsterStudyExporter().step_study_inputs(plain,"Bending").compiler_inputs


def test_default_transition_uses_each_spatially_applicable_base():
    model=straight_model()
    model.add_shell_panel("panel",polygon=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],thickness=.01,material="steel")
    model.set_mesh_size(.1)
    model.set_mesh_size(.04,region="panel")
    model.add_mesh_refinement("ball",target={"kind":"sphere","center_m":[0,0,0],"radius_m":.1},size_m=.02)
    policy=resolve_mesh_policy(model)
    assert policy.size_at((.16,0,0),source_ref="group:panel")==pytest.approx(.03)
    assert policy.size_at((.25,0,0),source_ref=f"element:{model.elements[0].id}")==pytest.approx(.06)


def test_native_tee_run_preview_matches_fused_sizing_minimum():
    import numpy as np
    from dataclasses import replace
    from tests.test_pipe_volume_mesh import _tee_model
    from tuba.geometry.volume import build_volume_geometry
    model,*_= _tee_model()
    model.add_mesh_refinement("branch",target="element:branch",size_m=.003,transition_distance_m=.01)
    geometry=build_volume_geometry(model,[e.id for e in model.elements])
    policy=resolve_mesh_policy(model,max_element_size=.005,volume_geometry=geometry)
    assert policy.size_at((0,.08,0),source_ref="element:branch")==.003
    assert policy.size_at((-.12,0,0),source_ref="element:left")==.005
    assert policy.size_at((0,0,0),source_ref="element:left")==.003
    # Prior callback evaluated all three owner refs on the fused volume. The
    # normalized scope makes individual preview samples agree with that same
    # minimum without changing generated sizing at any point.
    data=policy.to_dict()
    data.pop("fingerprint")
    data["refinements"][0]["source_refs"]=["element:branch"]
    prior=replace(policy,_data=data)
    refs=[f"element:{e.id}" for e in model.elements]
    for point in np.random.default_rng(7).uniform(-.15,.15,(100,3)):
        assert min(policy.size_at(point,source_ref=r) for r in refs)==min(prior.size_at(point,source_ref=r) for r in refs)


def test_native_volume_omitted_size_drives_public_solve_and_export(tmp_path,monkeypatch):
    from tests.test_pipe_volume_mesh import _straight_pipe_model
    from tuba.solver.aster import CodeAsterSolver
    from tuba.meshing import pipe_volume
    model,*_= _straight_pipe_model()
    model.define_load_case("case",gravity=False)
    ids=[e.id for e in model.elements]
    solver=CodeAsterSolver()
    automatic=solver.volume_study_inputs(model,"case",element_ids=ids)
    assert automatic.compiler_inputs["max_element_size"]==pytest.approx(.005)
    model.set_mesh_size(.004)
    authored=solver.volume_study_inputs(model,"case",element_ids=ids)
    assert authored.compiler_inputs["max_element_size"]==.004
    assert authored.compiler_inputs["mesh_policy"]["invocation_max_element_size_m"] is None
    explicit=solver.volume_study_inputs(model,"case",element_ids=ids,max_element_size=.003)
    assert explicit.compiler_inputs["max_element_size"]==.003
    with pytest.raises(ValueError,match="positive.*finite"):
        solver.volume_study_inputs(model,"case",element_ids=ids,max_element_size=True)
    # The public solve dispatcher forwards an omitted request rather than
    # converting its effective value into a new overriding invocation.
    def capture_solve(self,model,case,*,element_ids,max_element_size=None,force=False):
        assert max_element_size is None
        return self.volume_study_inputs(model,case,element_ids=element_ids,max_element_size=max_element_size)
    monkeypatch.setattr(CodeAsterSolver,"solve_volume_study",capture_solve)
    received=model.solve("case",pipe_modelization="3D",volume_element_ids=ids)
    assert received.compiler_inputs==authored.compiler_inputs
    sizes=[]
    def intercept_geometry(geometry,size,order):
        sizes.append(size)
        raise RuntimeError("native generation intercepted after resolved sizing")
    monkeypatch.setattr(pipe_volume,"_require_mesh_settings",intercept_geometry)
    with pytest.raises(RuntimeError,match="native generation intercepted"):
        solver.export_volume_study(model,"case",tmp_path/"export",element_ids=ids)
    assert sizes==[.004]
    with pytest.raises(RuntimeError,match="native generation intercepted"):
        pipe_volume.build_pipe_volume_mesh(model,tmp_path/"mesh.med",element_ids=ids)
    assert sizes==[.004,.004]
    assert not (tmp_path/"mesh.med").exists()


def test_omitted_step_invocation_keeps_global_and_region_authoring():
    from examples.code_aster_step_component_review import build_model
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    model=build_model(mesh_size=.012)
    model.set_mesh_size(.02)
    model.set_mesh_size(.006,region="spool_solid")
    inputs=MixedCodeAsterStudyExporter().step_study_inputs(model,"Bending")
    assert inputs.compiler_inputs["region_mesh_sizes"]["spool_solid"]==.006
    assert inputs.compiler_inputs["mesh_policy"]["base_sizes_m"]["component:spool"]==.006
    assert inputs.compiler_inputs["mesh_policy"]["invocation_max_element_size_m"] is None
