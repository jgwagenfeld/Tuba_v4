"""Portable parser contracts and opt-in real mixed-connection qualification.

CSV fixtures below test missing-data handling only. They are never solver
evidence or engineering results. Native tests execute Code_Aster explicitly.
"""

from dataclasses import replace
import importlib.util
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.analysis.results import result_state_from_fea_results
from tuba.solver.aster_volume_results import parse_volume_result_artifacts
from tuba.visualization import SceneRequest, build_visualization_scene
from tuba.visualization.builders._states import _analysis_line_element_ids, _build_shell_scene


NATIVE = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 for real mixed Code_Aster qualification",
)


def _parser_fixture(root):
    model = Model("Explicit mixed parser fixture")
    model.add_material("Elastic", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    a, b, c, ref = [model.add_node([float(i), 0, 0]) for i in range(4)]
    model.add_element(id="frame", type="beam", n1=a, n2=b, section="Pipe", material="Elastic")
    model.add_element(id="pipe", type="pipe_straight", n1=b, n2=c, section="Pipe", material="Elastic")
    model.add_support(a, "custom", blocked_dof=[1, 1, 1, 1, 1, 1])
    model.define_load_case("Fixture", gravity=False)
    nodes = {f"VN{i}": (float(i), 0.0, 0.0) for i in range(1, 12)}
    nodes.update({"VN5": (0.0, 0.0, 0.0), "VN6": (1.0, 0.0, 0.0), "VN7": (0.0, 1.0, 0.0)})
    mesh = AnalysisMesh(
        id="fixture", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"VM1": ("VN1", "VN2", "VN3", "VN4"),
                  "SM2": ("VN5", "VN6", "VN7"), "RC3": ("VN11",),
                  "LM4": ("VN8", "VN9"), "LM5": ("VN9", "VN10"),
                  "VS6": ("VN1", "VN2", "VN3")},
        groups={"solid": ("VM1",), "shell": ("SM2",), "reference": ("RC3",),
                "frame": ("LM4",), "pipe": ("LM5",), "base": ("VS6",),
                "shell_base": ("VN5",), f"G_NODE_{a}": ("VN8",)},
        modelisations={"solid": "3D", "shell": "DKT", "reference": "DIS_TR",
                       "frame": "POU_D_T", "pipe": "TUYAU_3M"},
        node_sources={"VN8": MeshNodeSource("VN8", f"node:{a}", "native_node"),
                      "VN9": MeshNodeSource("VN9", f"node:{b}", "native_node"),
                      "VN10": MeshNodeSource("VN10", f"node:{c}", "native_node"),
                      "VN11": MeshNodeSource("VN11", f"node:{ref}", "native_node")},
        element_sources={"VM1": MeshElementSource("VM1", "group:solid", "volume_cell"),
                         "SM2": MeshElementSource("SM2", "group:shell", "shell_cell"),
                         "RC3": MeshElementSource("RC3", f"node:{ref}", "reference_carrier"),
                         "LM4": MeshElementSource("LM4", "element:frame", "native_element"),
                         "LM5": MeshElementSource("LM5", "element:pipe", "native_element")},
        surface_mesh={"vertices": [nodes[f"VN{i}"] for i in range(1, 4)],
                      "faces": [(0, 1, 2)], "node_ids": ["VN1", "VN2", "VN3"]},
    )
    study = AnalysisStudy(
        id="fixture", model_revision=0, solver_name="Code_Aster", load_case="Fixture",
        work_dir=str(root), input_files={}, mesh_id=mesh.id,
        metadata={"mixed_analysis": True, "step_component_analysis": True,
                  "fixed_face_groups": ["base"], "fixed_node_groups": ["shell_base"],
                  "compiler_inputs": {"element_ids": [], "line_element_ids": ["frame", "pipe"],
                                      "shell_coque_ncou": {"shell": 1}}},
    )
    header = "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
    (root / "study_depl.csv").write_text(header + "\n".join(
        f"{i},0,0,0," + ("-,-,-" if i <= 4 else "0,0,0") for i in range(1, 12)))
    (root / "study_reac.csv").write_text(header + "\n".join(
        f"{i},0,0,0," + ("-,-,-" if i <= 4 else "0,0,0") for i in (1, 2, 3, 5, 8)))
    stress = [f"1,{i},,10" for i in range(1, 4)]
    stress += [f"2,{i},{subpoint},{value}" for i in (5, 6, 7)
               for subpoint, value in ((1, 20), (2, 2), (3, 30))]
    stress += [f"5,{i},,10" for i in (9, 10)]
    (root / "study_sieq.csv").write_text("MAILLE,NOEUD,SOUS_POINT,VMIS\n" + "\n".join(stress))
    (root / "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n" + "\n".join(
        f"{element},{node},1,0,0,0,0,0" for element, endpoints in ((4, (8, 9)), (5, (9, 10)))
        for node in endpoints))
    return model, mesh, study


@pytest.mark.parametrize("node", [5, 8, 9, 11])
def test_mixed_reader_requires_rotations_on_shell_frame_pipe_and_reference(tmp_path, node):
    model, mesh, study = _parser_fixture(tmp_path)
    path = tmp_path / "study_depl.csv"
    path.write_text(path.read_text().replace(f"{node},0,0,0,0,0,0", f"{node},0,0,0,-,-,-"))
    with pytest.raises(RuntimeError, match="component DRX"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


@pytest.mark.parametrize("node", [5, 8])
def test_mixed_reader_requires_shell_and_custom_support_reaction_moments(tmp_path, node):
    model, mesh, study = _parser_fixture(tmp_path)
    path = tmp_path / "study_reac.csv"
    path.write_text(path.read_text().replace(f"{node},0,0,0,0,0,0", f"{node},0,0,0,-,-,-"))
    with pytest.raises(RuntimeError, match="component DRX"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


@pytest.mark.parametrize("missing_patch_node", [False, True])
@pytest.mark.parametrize("grounding", ["reference", "physical_corner"])
@pytest.mark.parametrize("fanout", [False, True])
def test_grounded_rigid_patch_reactions_include_physical_nodes_and_exclude_free_patch(tmp_path, missing_patch_node, grounding, fanout):
    from types import SimpleNamespace

    model, references = _example().build_shell_reference(length=2.0, width=2.0)
    model.define_load_case("Fixture", gravity=False)
    if fanout:
        _example().shell_strip(model, name="auxiliary", start=0, end=2, width=1.5,
                               thickness=0.008, material="Panel", mesh_size=0.02,
                               start_reference=references["base"], end_reference=references["tip"])
        # The auxiliary patch is visited before the directly grounded patch.
        model.couplings = dict(reversed(list(model.couplings.items())))
    if grounding == "physical_corner":
        model.supports.clear()
        corner = model.add_node([0, -1, 0])
        model.add_support(corner, "anchor")
    mesh = AnalysisMesh(
        id="patch-fixture", model_revision=0, solver_name="Code_Aster",
        nodes={"VN1": (0, 0, 0), "VN2": (2, 0, 0), "VN3": (0, -1, 0),
               "VN4": (2, -1, 0), "VN5": (2, 1, 0), "VN6": (0, 1, 0)},
        elements={"RC1": ("VN1",), "RC2": ("VN2",),
                  "SM3": ("VN3", "VN4", "VN5"), "SM4": ("VN3", "VN5", "VN6")},
        groups={"G_base_REF": ("RC1",), "G_tip_REF": ("RC2",),
                "G_panel_SHELL": ("SM3", "SM4"),
                f"G_NODE_{references['base']}": ("VN1",), f"G_NODE_{references['tip']}": ("VN2",),
                "G_panel_base_PATCH": ("VN1", "VN3", "VN6"),
                "G_panel_tip_PATCH": ("VN2", "VN4", "VN5")},
        modelisations={"G_base_REF": "DIS_TR", "G_tip_REF": "DIS_TR", "G_panel_SHELL": "DKT"},
        node_sources={"VN1": MeshNodeSource("VN1", f"node:{references['base']}", "native_node"),
                      "VN2": MeshNodeSource("VN2", f"node:{references['tip']}", "native_node")},
        element_sources={"RC1": MeshElementSource("RC1", f"node:{references['base']}", "reference_carrier"),
                         "RC2": MeshElementSource("RC2", f"node:{references['tip']}", "reference_carrier"),
                         "SM3": MeshElementSource("SM3", "group:panel", "shell_cell"),
                         "SM4": MeshElementSource("SM4", "group:panel", "shell_cell")},
    )
    if grounding == "physical_corner":
        mesh = replace(mesh, groups={**mesh.groups, f"G_NODE_{corner}": ("VN3",)},
                       node_sources={**mesh.node_sources,
                                     "VN3": MeshNodeSource("VN3", f"node:{corner}", "native_node")})
    if fanout:
        mesh = replace(mesh,
                       nodes={**mesh.nodes, "VN7": (0, -0.75, 0), "VN8": (0, 0.75, 0),
                              "VN9": (2, -0.75, 0), "VN10": (2, 0.75, 0)},
                       elements={**mesh.elements, "SM5": ("VN7", "VN9", "VN10"), "SM6": ("VN7", "VN10", "VN8")},
                       groups={**mesh.groups, "G_auxiliary_SHELL": ("SM5", "SM6"),
                               "G_auxiliary_base_PATCH": ("VN1", "VN7", "VN8"),
                               "G_auxiliary_tip_PATCH": ("VN2", "VN9", "VN10")},
                       modelisations={**mesh.modelisations, "G_auxiliary_SHELL": "DKT"},
                       element_sources={**mesh.element_sources,
                                        "SM5": MeshElementSource("SM5", "group:auxiliary", "shell_cell"),
                                        "SM6": MeshElementSource("SM6", "group:auxiliary", "shell_cell")})
    study = AnalysisStudy(
        id="patch-fixture", model_revision=0, solver_name="Code_Aster", load_case="Fixture",
        work_dir=str(tmp_path), input_files={}, mesh_id=mesh.id,
        metadata={"mixed_analysis": True, "step_component_analysis": True,
                  "compiler_inputs": {"element_ids": [], "line_element_ids": [],
                                      "shell_coque_ncou": {"panel": 1, **({"auxiliary": 1} if fanout else {})}}},
    )
    header = "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
    (tmp_path / "study_depl.csv").write_text(header + "\n".join(f"{i},0,0,0,0,0,0" for i in range(1, len(mesh.nodes) + 1)))
    reactions = ["1,0,0,0,0,0,0", "2,0,0,-10,0,0,0", "3,0,0,-0.25,0,0.1,0",
                 "4,0,0,5,0,0,0", "5,0,0,5,0,0,0", "6,0,0,-0.75,0,0.3,0"]
    if fanout:
        reactions += ["7,0,0,-0.25,0,0.1,0", "8,0,0,-0.75,0,0.3,0", "9,0,0,0,0,0,0", "10,0,0,0,0,0,0"]
    if missing_patch_node:
        reactions.remove("8,0,0,-0.75,0,0.3,0" if fanout else "6,0,0,-0.75,0,0.3,0")
    (tmp_path / "study_reac.csv").write_text(header + "\n".join(reactions))
    (tmp_path / "study_sieq.csv").write_text("MAILLE,NOEUD,SOUS_POINT,VMIS\n" + "\n".join(
        f"{cell[2:]},{node[2:]},{subpoint},0" for cell, nodes in mesh.elements.items() if cell.startswith("SM")
        for node in nodes for subpoint in (1, 2, 3)))
    if missing_patch_node:
        with pytest.raises(RuntimeError, match="missing reactions"):
            parse_volume_result_artifacts(model, tmp_path, mesh, study)
        return
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    assert {node for node, value in results.analysis_node_results.items() if value.reaction_force is not None} == {"VN1", "VN3", "VN6"} | ({"VN7", "VN8"} if fanout else set())
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    force, moment = _reaction_resultant(SimpleNamespace(analysis_mesh=mesh, result_state=state))
    assert force == pytest.approx([0, 0, -1 - int(fanout)])
    assert moment == pytest.approx([-0.5 - 0.375 * int(fanout), 0.4 * (1 + int(fanout)), 0])


def test_shell_stress_maximum_preserves_native_samples_and_persistence(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    assert np.isnan(results.analysis_node_results["VN1"].displacement[3:]).all()
    assert results.metadata["shell_von_mises"] == {f"VN{i}": 30 for i in (5, 6, 7)}
    assert results.metadata["shell_element_von_mises"] == {"SM2": 30}
    assert len(results.metadata["shell_stress_samples"]) == 9
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    assert state.metadata["shell_stress_samples"] == results.metadata["shell_stress_samples"]
    json.dumps(state.to_dict(), allow_nan=False)


def test_shell_reader_rejects_missing_thickness_sample(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    path = tmp_path / "study_sieq.csv"
    path.write_text(path.read_text().replace("2,5,3,30\n", ""))
    with pytest.raises(RuntimeError, match="through-thickness VMIS"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


@pytest.mark.parametrize("replace_outer", [True, False])
def test_shell_reader_rejects_unknown_thickness_subpoint(tmp_path, replace_outer):
    model, mesh, study = _parser_fixture(tmp_path)
    path = tmp_path / "study_sieq.csv"
    text = path.read_text()
    if replace_outer:
        text = text.replace("2,5,3,30", "2,5,99,30")
    else:
        text += "\n2,5,99,30\n"
    path.write_text(text)
    with pytest.raises(RuntimeError, match="unexpected through-thickness VMIS"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


@pytest.mark.parametrize("layers", [None, {}, {"unknown": 1}, {"shell": 1, "unknown": 1},
                                   {"shell": 2}, {"shell": True}])
def test_shell_reader_requires_matching_qualified_layer_contract(tmp_path, layers):
    model, mesh, study = _parser_fixture(tmp_path)
    inputs = {**study.metadata["compiler_inputs"], "shell_coque_ncou": layers}
    study = replace(study, metadata={**study.metadata, "compiler_inputs": inputs})
    with pytest.raises(RuntimeError, match="shell COQUE_NCOU contract"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


def test_mixed_reader_accepts_exact_prefixed_med_labels(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    for name in ("depl", "reac", "sieq", "effo"):
        path = tmp_path / f"study_{name}.csv"
        lines = path.read_text().splitlines()
        rows = []
        for line in lines[1:]:
            columns = line.split(",")
            if name in {"sieq", "effo"}:
                columns[0] = {"1": "VM1", "2": "SM2", "4": "LM4", "5": "LM5"}[columns[0]]
                columns[1] = "VN" + columns[1]
            else:
                columns[0] = "VN" + columns[0]
            rows.append(",".join(columns))
        path.write_text(lines[0] + "\n" + "\n".join(rows))
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    assert results.element_results["frame"].forces_n1[0] == 1
    assert results.metadata["shell_element_von_mises"] == {"SM2": 30}


def test_mixed_reader_requires_line_endpoints_without_step_flag(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    study = replace(study, metadata={**study.metadata, "step_component_analysis": False})
    path = tmp_path / "study_effo.csv"
    path.write_text(path.read_text().replace("4,8,1,0,0,0,0,0\n", ""))
    with pytest.raises(RuntimeError, match="endpoint forces"):
        parse_volume_result_artifacts(model, tmp_path, mesh, study)


def test_shell_only_reader_needs_no_solid_stress_or_line_table(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    mesh = replace(mesh, elements={"SM2": mesh.elements["SM2"], "RC3": mesh.elements["RC3"]},
                   element_sources={key: mesh.element_sources[key] for key in ("SM2", "RC3")},
                   nodes={node: mesh.nodes[node] for node in ("VN5", "VN6", "VN7", "VN11")},
                   node_sources={"VN11": mesh.node_sources["VN11"]},
                   groups={key: mesh.groups[key] for key in ("shell", "reference", "shell_base")},
                   modelisations={"shell": "DKT", "reference": "DIS_TR"},
                   surface_mesh=None)
    study = replace(study, metadata={**study.metadata, "fixed_face_groups": [],
                    "compiler_inputs": {"element_ids": [], "line_element_ids": [],
                                        "shell_coque_ncou": {"shell": 1}}})
    (tmp_path / "study_effo.csv").unlink()
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    assert results.volume_von_mises == {}
    assert results.metadata["shell_element_von_mises"] == {"SM2": 30}


def test_combined_scene_retains_true_shell_surface_and_native_line_forces(tmp_path):
    model, mesh, study = _parser_fixture(tmp_path)
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    scene = build_visualization_scene(SceneRequest(model, result_states=[state], analysis_meshes=[mesh]))
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    assert _analysis_line_element_ids(mesh) == {"LM4", "LM5"}
    assert {obj.kind for obj in scene.objects} >= {"volume_stress_field", "shell_stress_field", "shell_displacement_field"}
    # The one displacement field also carries the line elements' nodes, so the
    # frame and pipe bodies are coloured by it instead of left grey.
    displacement = next(overlay for overlay in scene.overlays if "volume_displacement:" in overlay.id)
    line_nodes = {node for element in ("LM4", "LM5") for node in mesh.elements[element]}
    assert line_nodes <= set(displacement.data["values"])
    assert displacement.data["range"]["max"] >= max(displacement.data["values"][node] for node in line_nodes)
    # Likewise one von Mises field: the solid and the line elements on one scale.
    stress = [overlay for overlay in scene.overlays if overlay.data.get("result_type") == "stress"]
    assert len(stress) == 1
    volume_object = next(obj.id for obj in scene.objects if obj.kind == "volume_stress_field")
    assert volume_object in stress[0].data["values"]
    assert any(key.startswith("object:element:") for key in stress[0].data["values"])
    # Each family's basis stays with its family: the solid's surface averaging
    # is not a statement about the line elements.
    assert "averaging" not in stress[0].data
    assert any(part.get("averaging") for part in stress[0].data["parts"])
    forces = next(overlay for overlay in scene.overlays if overlay.data.get("result_type") == "internal_forces")
    assert {str(ref) for ref in forces.entity_refs} == {"element:frame", "element:pipe"}
    shell = next(asset for asset in scene.geometry_assets if asset.id.startswith("geometry:shell:stress:"))
    assert shell.generation_config["faces"] == [[0, 1, 2]]
    assert shell.generation_config["vertex_values"] == [30, 30, 30]
    assert all(field.components == ("magnitude",) for field in scene.result_fields
               if "shell:displacement:" in field.overlay_id or "volume_displacement:" in field.overlay_id)
    assert not any(obj.kind == "analysis_mesh_element" and obj.metadata.get("element_id") == "SM2"
                   for obj in scene.objects)


def test_shell_review_uses_real_displaced_vertices_and_refuses_missing_fields(tmp_path):
    from tuba.analysis.states import GeometryState
    model, mesh, study = _parser_fixture(tmp_path)
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    state = replace(state, node_displacements={**state.node_displacements, "VN5": (0, 0, 0.01, 0, 0, 0)})
    geometry = GeometryState(id="deformed", model_revision=0, state_type="deformed",
                             displacement_scale=2, purpose="visualization")
    contribution = _build_shell_scene(mesh, state, geometry)
    assert contribution.assets[0].generation_config["vertices"][0] == [0, 0, 0.02]
    with pytest.raises(ValueError, match="native through-thickness VMIS"):
        _build_shell_scene(mesh, replace(state, metadata={}))


def test_mixed_result_glyphs_use_physical_mesh_nodes_once_and_preserve_legacy_ids(tmp_path):
    from tuba.visualization.builders._results import _result_state_displacement_overlay, _result_state_reaction_overlays
    model, mesh, study = _parser_fixture(tmp_path)
    results = parse_volume_result_artifacts(model, tmp_path, mesh, study)
    state = result_state_from_fea_results(model=model, study=study, results=results, analysis_mesh=mesh)
    alias = mesh.node_sources["VN8"].source_ref.id
    state = replace(state, node_displacements={alias: (0.01, 0, 0, 0, 0, 0), "VN8": (0.01, 0, 0, 0, 0, 0)},
                    node_reactions={alias: (1, 0, 0, 0, 1, 0), "VN8": (1, 0, 0, 0, 1, 0)})
    displacement = _result_state_displacement_overlay(model, state, mesh, [])
    reactions = _result_state_reaction_overlays(model, state, mesh)
    for overlay in (displacement, *reactions):
        assert len(overlay.data["vectors"]) == 1
        vector = overlay.data["vectors"][0]
        assert vector["node_id"] == "VN8" and vector["coordinate_source"] == "analysis_mesh"
    legacy = AnalysisMesh(id="legacy", model_revision=0, solver_name="Code_Aster",
                          nodes={alias: model.nodes[alias].coords}, elements={}, groups={}, element_sources={},
                          node_sources={alias: MeshNodeSource(alias, f"node:{alias}", "native_node")})
    state = replace(state, mesh_id=legacy.id, node_displacements={alias: state.node_displacements[alias]},
                    node_reactions={alias: state.node_reactions[alias]})
    for overlay in (_result_state_displacement_overlay(model, state, legacy, []),
                    *_result_state_reaction_overlays(model, state, legacy)):
        assert overlay.data["vectors"][0]["node_id"] == alias


def _example():
    path = Path(__file__).parents[1] / "examples" / "code_aster_mixed_connections_review.py"
    spec = importlib.util.spec_from_file_location("mixed_connections_reference_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_authored_shell_reference_records_are_parametric_and_compiler_ready():
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    model, nodes = _example().build_shell_reference(length=0.6, mesh_size=0.03)
    model.define_load_case("Bending", gravity=False).add_nodal_force(nodes["tip"], force=[0, 0, 1])
    model.validate()
    assert len(model.nodes) == 2 and not model.elements
    assert model.analysis_regions["panel"].metadata["polygon_m"][1][0] == 0.6
    assert model.couplings["panel_base"].metadata["edges"] == [3]
    assert model.couplings["panel_tip"].metadata["edges"] == [1]
    inputs = MixedCodeAsterStudyExporter().step_study_inputs(model, "Bending")
    assert inputs.compiler_inputs["mixed_mechanics_version"] == "solid-shell-line-reference-v2"


def _portable_mechanics_model():
    model, nodes = _example().build_shell_reference()
    model.add_material("Frame", E=2.1e11, nu=0.3, rho=7850, alpha=1.2e-5)
    model.add_material("Pipe", E=1.9e11, nu=0.3, rho=7900, alpha=1.1e-5)
    model.add_rectangular_section("RHS", height_y=0.06, height_z=0.06, thickness_y=0.006, thickness_z=0.006)
    model.add_pipe_section("Annulus", OD=0.1, WT=0.01)
    frame_top = model.add_node([0.39, 0, 0])
    pipe_tip = model.add_node([1.4, 0, 0])
    model.add_element(id="frame", type="beam", n1=nodes["base"], n2=frame_top, section="RHS", material="Frame")
    model.add_element(id="pipe", type="pipe_straight", n1=nodes["tip"], n2=pipe_tip, section="Annulus", material="Pipe")
    model.add_support(nodes["tip"], "custom", attached_to=frame_top, blocked_dof=[1, 1, 0, 1, 1, 1], attachment_mode="dof_equality")
    # A genuine bilateral pipe guide; it must not silently clamp the TUYAU WO.
    model.add_support(pipe_tip, "custom", blocked_dof=[1, 0, 1, 0, 0, 0])
    model.define_operation("Scoped", gravity=True)
    return model, nodes


def _portable_comm(model, root):
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    from tuba.solver.aster_sidecar import build_solver_name_map
    from tuba.solver.aster_volume import _write_comm
    inputs = MixedCodeAsterStudyExporter().step_study_inputs(model, "Scoped")
    families = {region.mesh_group: region.code_aster_modelisation for region in model.analysis_regions.values()}
    families.update({"G_FRAME": "POU_D_T", "G_TUBE": "TUYAU_3M"} if model.elements else {})
    groups = set(families) | set(inputs.comm_context["rigid_patch_groups"])
    groups.update(f"G_NODE_{node}" for node in model.nodes)
    groups.update(f"G_LINE_{element.id}" for element in model.elements)
    name_map = build_solver_name_map(groups)
    path = root / "study.comm"
    _write_comm(model, path, name_map=name_map, pressure=inputs.pressure,
                support_groups=tuple(inputs.supports), couplings=tuple(inputs.couplings),
                line_elements=inputs.line_elements, nodal_forces=inputs.load_case.nodal_forces,
                node_groups={}, gravity=inputs.load_case.gravity, material_name="Panel",
                export_tensor_stress=False, solid_group=None, skin_groups_raw=(),
                pressure_groups_raw=(), modelisations=families, load_case=inputs.load_case,
                **inputs.comm_context)
    return path.read_text(), inputs, name_map


def test_portable_compiler_keeps_v3_mask_motion_temperatures_and_fluid_identity(tmp_path):
    model, nodes = _portable_mechanics_model()
    model.supports[0].imposed_displacement = [0.08, 0, 0]
    case = model.operations["Scoped"]
    case.add_field("temperature", value=120, scope="group", group="panel")
    case.add_field("temperature", value=80, scope="elements", element_ids=["frame"])
    case.add_field("temperature", value=60, scope="elements", element_ids=["pipe"])
    case.add_field("fluid_density", value=1000, scope="elements", element_ids=["pipe"])
    text, inputs, names = _portable_comm(model, tmp_path)
    assert "DX=8.000000000000E-02" in text
    equations = [line for line in text.splitlines() if "COEF_MULT" in line]
    assert len(equations) == 5
    assert all("COEF_MULT=(1.0, -1.0)" in line for line in equations)
    assert not any("'DZ'" in line for line in equations)
    tip_guide = next(line for line in text.splitlines() if f"GROUP_NO='{names['G_NODE_' + model.get_element('pipe').n2]}'" in line and "DX=" in line)
    assert "WO=" not in tip_guide
    resolved = inputs.compiler_inputs["resolved_loads"]
    assert resolved["region_temperatures"]["G_panel_SHELL"] == 120
    assert resolved["line_temperatures"] == {"frame": 80, "pipe": 60}
    assert resolved["line_properties"]["pipe"]["rho"] == pytest.approx(7900 + 1000 * 0.04**2 / (0.05**2 - 0.04**2))
    original_identity = inputs.solver_input_identity
    case.fields[-1] = replace(case.fields[-1], value=1100)
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    assert MixedCodeAsterStudyExporter().step_study_inputs(model, "Scoped").solver_input_identity != original_identity
    model.supports[-1].imposed_displacement = [0, 0.01, 0]
    with pytest.raises(ValueError, match="free DOF"):
        MixedCodeAsterStudyExporter().step_study_inputs(model, "Scoped")


def test_portable_shell_only_commands_export_layers_without_line_forces(tmp_path):
    model, _ = _example().build_shell_reference()
    model.define_load_case("Scoped", gravity=False)
    text, inputs, _ = _portable_comm(model, tmp_path)
    assert "MODELISATION='DKT'" in text and "LIAISON_SOLIDE=" in text
    assert "NOM_CHAM='SIEQ_ELNO', TOUT='OUI'" in text
    assert "TAB_EFFO" not in text
    assert "SOLVEUR=_F(METHODE='MULT_FRONT', NPREC=8, STOP_SINGULIER='OUI')" in text
    assert inputs.compiler_inputs["solver_policy"] == {
        "method": "MULT_FRONT", "nprec": 8, "stop_singulier": "OUI",
    }
    from tuba.analysis.provenance import build_solver_input_identity
    without_policy = {key: value for key, value in inputs.compiler_inputs.items() if key != "solver_policy"}
    assert build_solver_input_identity(
        model, "Scoped", compiler_id=inputs.solver_input_identity.compiler_id,
        compiler_inputs=without_policy,
    ) != inputs.solver_input_identity


def test_portable_shell_without_reference_preserves_default_solver(tmp_path):
    model = Model("Physical shell without reference carrier")
    model.add_material("Panel", E=7e10, nu=0.0)
    model.add_shell_panel(
        "panel", polygon=[[0, -0.02, 0], [0.4, -0.02, 0],
                          [0.4, 0.02, 0], [0, 0.02, 0]],
        thickness=0.008, material="Panel", mesh_size=0.02,
    )
    model.add_support(model.add_node([0, -0.02, 0]), "anchor")
    model.define_load_case("Scoped", gravity=False)
    text, inputs, _ = _portable_comm(model, tmp_path)
    assert "MODELISATION='DKT'" in text
    assert "MODELISATION='DIS_TR'" not in text
    assert "SOLVEUR=" not in text
    assert "solver_policy" not in inputs.compiler_inputs


def _native_solve(model, case, root):
    from tuba.solver.aster import CodeAsterSolver
    solver = CodeAsterSolver(work_dir=root, exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"))
    study = solver.export_mixed_analysis_study(model, case, root)
    run = solver.solve_exported_study(model, study)
    assert run.result_state.metadata["result_trust"] == "verified"
    assert run.study.solver_input_identity == run.result_state.solver_input_identity == run.analysis_mesh.solver_input_identity
    assert (root / "study.rmed").is_file()
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=[run]))
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    assert any(obj.kind == "shell_stress_field" for obj in scene.objects)
    return run


def _reaction_resultant(run):
    force, moment = np.zeros(3), np.zeros(3)
    for node, point in run.analysis_mesh.nodes.items():
        reaction = run.result_state.node_reactions.get(node)
        if reaction is not None:
            nodal_force = np.asarray(reaction[:3], dtype=float)
            nodal_moment = np.asarray([0 if value is None else value for value in reaction[3:]], dtype=float)
            force += nodal_force
            moment += np.cross(point, nodal_force) + nodal_moment
    return force, moment


def _check_rigid_patches(model, run):
    for coupling in model.couplings.values():
        if coupling.kind != "rigid_patch":
            continue
        reference = coupling.source_node.id
        ref_position = model.nodes[reference].coords
        ref_displacement = np.asarray(run.result_state.node_displacements[reference])
        for node in run.analysis_mesh.groups[coupling.metadata["mesh_node_group"]]:
            expected = ref_displacement[:3] + np.cross(ref_displacement[3:], np.asarray(run.analysis_mesh.nodes[node]) - ref_position)
            actual = np.asarray(run.result_state.node_displacements[node][:3])
            assert actual == pytest.approx(expected, rel=1e-5, abs=1e-10)


@NATIVE
def test_native_four_families_axial_stiffness_released_guide_and_patch_kinematics(tmp_path):
    model, nodes = _example().build_model()
    force = 1000.0
    transverse = 10.0
    model.define_load_case("Axial", gravity=False).add_nodal_force(nodes["tip"], force=[force, 0, transverse])
    run = _native_solve(model, "Axial", tmp_path)
    assert set(run.analysis_mesh.modelisations.values()) == {"3D", "DKT", "DIS_TR", "TUYAU_3M", "POU_D_T"}
    area = math.pi * (0.05**2 - 0.04**2)
    frame_area = 0.06**2 - (0.06 - 2 * 0.006)**2
    foundation_stiffness = 7e10 * 0.04 * 0.008 / 0.4 + 2.1e11 * frame_area / 0.39
    expected = force * (0.2 / (2.1e11 * area) + 1 / (1.9e11 * area) + 1 / foundation_stiffness)
    assert run.result_state.node_displacements[nodes["tip"]][0] == pytest.approx(expected, rel=0.05)
    # The tip displacement alone can conceal a missing parallel shell load path.
    expected_frame_force = force * (2.1e11 * frame_area / 0.39) / foundation_stiffness
    frame = run.results.element_results["frame"]
    assert abs(frame.forces_n1[0]) == pytest.approx(expected_frame_force, rel=0.01)
    assert abs(frame.forces_n2[0]) == pytest.approx(expected_frame_force, rel=0.01)
    held = [0, 1, 3, 4, 5]
    assert np.asarray(run.result_state.node_displacements[nodes["interface"]])[held] == pytest.approx(np.asarray(run.result_state.node_displacements[nodes["frame_top"]])[held], abs=1e-10)
    assert abs(run.result_state.node_displacements[nodes["interface"]][2] - run.result_state.node_displacements[nodes["frame_top"]][2]) > 1e-7
    _check_rigid_patches(model, run)
    reactions, moments = _reaction_resultant(run)
    assert reactions == pytest.approx([-force, 0, -transverse], abs=0.01)
    assert moments == pytest.approx([0, transverse * 1.2, 0], abs=0.01)
    for element in model.elements:
        result = run.results.element_results[element.id]
        assert np.isfinite(result.forces_n1).all() and np.isfinite(result.forces_n2).all()


@NATIVE
@pytest.mark.parametrize("fanout", [False, True])
def test_native_shell_physical_corner_anchor_preserves_clamped_edge_balance_and_pose(tmp_path, fanout):
    force, length, width, thickness, E = 1.0, 0.4, 0.04, 0.008, 7e10
    model, nodes = _example().build_shell_reference(
        mesh_size=0.02, length=length, width=width, thickness=thickness, E=E,
    )
    if fanout:
        _example().shell_strip(model, name="auxiliary", start=0, end=length, width=0.03,
                               thickness=thickness, material="Panel", mesh_size=0.02,
                               start_reference=nodes["base"], end_reference=nodes["tip"])
    model.supports.clear()
    corner = model.add_node([0, -width / 2, 0])
    model.add_support(corner, "anchor")
    model.define_load_case("Bending", gravity=False).add_nodal_force(nodes["tip"], force=[0, 0, force])
    run = _native_solve(model, "Bending", tmp_path)
    if fanout:
        auxiliary = set(run.analysis_mesh.groups["G_auxiliary_base_PATCH"])
        primary = set(run.analysis_mesh.groups["G_panel_base_PATCH"])
        assert run.analysis_mesh.groups[f"G_NODE_{corner}"][0] not in auxiliary
        assert primary & auxiliary == set(run.analysis_mesh.groups[f"G_NODE_{nodes['base']}"])
    total_width = width + (0.03 if fanout else 0)
    expected_tip = force * length**3 / (3 * E * total_width * thickness**3 / 12)
    assert run.result_state.node_displacements[nodes["tip"]][2] == pytest.approx(expected_tip, rel=0.04)
    _check_rigid_patches(model, run)
    reaction_force, reaction_moment = _reaction_resultant(run)
    assert reaction_force == pytest.approx([0, 0, -force], abs=1e-5)
    assert reaction_moment == pytest.approx([0, force * length, 0], abs=1e-5)


@NATIVE
def test_native_shell_bending_outer_layer_stress_and_refinement(tmp_path):
    values = []
    force, length, width, thickness, E = 1.0, 0.4, 0.04, 0.008, 7e10
    expected_tip = force * length**3 / (3 * E * width * thickness**3 / 12)
    for mesh_size in (0.02, 0.01):
        model, nodes = _example().build_shell_reference(mesh_size=mesh_size)
        model.define_load_case("Bending", gravity=False).add_nodal_force(nodes["tip"], force=[0, 0, force])
        run = _native_solve(model, "Bending", tmp_path / str(mesh_size))
        assert not run.study.metadata["line_force_exported"]
        assert run.analysis_mesh.surface_mesh is None
        value = run.result_state.node_displacements[nodes["tip"]][2]
        assert value == pytest.approx(expected_tip, rel=0.04)
        values.append(value)
        _check_rigid_patches(model, run)
        reaction_force, reaction_moment = _reaction_resultant(run)
        assert reaction_force == pytest.approx([0, 0, -force], abs=1e-5)
        assert reaction_moment == pytest.approx([0, force * length, 0], abs=1e-5)
        # Interior samples avoid rigid-edge local stress perturbations. This
        # verifies actual native outer-layer VMIS instead of fixture numbers.
        errors = []
        for sample in run.results.metadata["shell_stress_samples"]:
            x = run.analysis_mesh.nodes[sample["node_id"]][0]
            if 0.1 < x < 0.3:
                expected = 6 * force * (length - x) / (width * thickness**2)
                errors.append((sample["subpoint_index"], sample["value"], expected))
        assert errors
        per_node = {}
        for sample in run.results.metadata["shell_stress_samples"]:
            per_node.setdefault((sample["analysis_element_id"], sample["node_id"]), []).append(sample)
        # Native Code_Aster output confirms 1 and 3 are the outer subpoints and
        # 2 is the middle. These indices do not identify physical INF/SUP faces.
        for (cell, node), samples in per_node.items():
            if 0.1 < run.analysis_mesh.nodes[node][0] < 0.3:
                layers = {sample["subpoint_index"]: sample["value"] for sample in samples}
                assert set(layers) == {1, 2, 3}
                assert layers[1] == pytest.approx(layers[3], rel=1e-5)
                assert layers[2] < 0.05 * max(layers[1], layers[3])
        maxima = [max(s["value"] for s in samples) for (cell, node), samples in per_node.items()
                  if 0.1 < run.analysis_mesh.nodes[node][0] < 0.3]
        expected_values = [6 * force * (length - run.analysis_mesh.nodes[node][0]) / (width * thickness**2)
                           for (cell, node) in per_node if 0.1 < run.analysis_mesh.nodes[node][0] < 0.3]
        assert np.median(np.asarray(maxima) / expected_values) == pytest.approx(1, rel=0.08)
    assert values[0] == pytest.approx(values[1], rel=0.025)


@NATIVE
def test_native_mixed_imposed_translation_and_fluid_weight_balance(tmp_path):
    model, nodes = _example().build_model()
    ground = next(s for s in model.supports if s.attached_to is None)
    ground.imposed_displacement = [0.08, 0, 0]
    model.define_load_case("Movement", gravity=False)
    run = _native_solve(model, "Movement", tmp_path / "motion")
    for node in run.analysis_mesh.nodes:
        assert run.result_state.node_displacements[node][:3] == pytest.approx([0.08, 0, 0], abs=1e-7)
    assert _reaction_resultant(run)[0] == pytest.approx([0, 0, 0], abs=0.01)
    ground.imposed_displacement = None
    case = model.define_operation("Fluid", gravity=True)
    case.add_field("fluid_density", value=1000, scope="elements", element_ids=[nodes["pipe"]])
    run = _native_solve(model, "Fluid", tmp_path / "fluid")
    area = math.pi * (0.05**2 - 0.04**2)
    frame_area = 0.06**2 - (0.06 - 2 * 0.006)**2
    mass = area * 1.2 * 7850 + frame_area * 0.39 * 7850 + 0.4 * 0.04 * 0.008 * 2700 + math.pi * 0.04**2 * 1000
    assert _reaction_resultant(run)[0] == pytest.approx([0, 0, 9.80665 * mass], abs=0.01)
    _check_rigid_patches(model, run)


@NATIVE
def test_native_shell_uniform_temperature_has_known_axial_expansion(tmp_path):
    model, nodes = _example().build_shell_reference()
    model.define_load_case("Thermal", gravity=False, temperature=80, ref_temperature=20)
    run = _native_solve(model, "Thermal", tmp_path)
    assert run.result_state.node_displacements[nodes["tip"]][0] == pytest.approx(1.2e-5 * 60 * 0.4, rel=0.005)
    assert _reaction_resultant(run)[0] == pytest.approx([0, 0, 0], abs=0.01)


@NATIVE
def test_native_connected_shells_and_beams_keep_their_own_thermal_expansion(tmp_path):
    """An independent sum(alpha * deltaT * length) checks group isolation at shared joints."""
    model = Model("Thermal chain")
    model.add_material("Elastic", E=7e10, nu=0.0, alpha=1e-5)
    model.add_rectangular_section("Bar", height_y=.04, height_z=.008)
    base = model.add_reference_point("base", position=[0, 0, 0])
    shell_tip = model.add_reference_point("shell_tip", position=[.4, 0, 0])
    for name, start in (("cold_panel", 0), ("hot_panel", .2)):
        model.add_shell_panel(name, polygon=[[start, -.02, 0], [start+.2, -.02, 0],
            [start+.2, .02, 0], [start, .02, 0]], thickness=.008, material="Elastic", mesh_size=.025)
    model.add_rigid_patch("base_edge", reference=base, shell="cold_panel", edges=[3])
    # Adjacent authored patch selections can include the same physical corner.
    model.add_rigid_patch("base_corner", reference=base, shell="cold_panel", vertices=[0])
    model.add_rigid_patch("tip_edge", reference=shell_tip, shell="hot_panel", edges=[1])
    joint, tip = model.add_node([.6, 0, 0]), model.add_node([.8, 0, 0])
    model.add_element(id="warm_beam", type="beam", n1=shell_tip, n2=joint, section="Bar", material="Elastic")
    model.add_element(id="hot_beam", type="beam", n1=joint, n2=tip, section="Bar", material="Elastic")
    model.add_support(base, "anchor")
    case = model.define_operation("Thermal", gravity=False, temperature=20, ref_temperature=20)
    for group, temperature in (("cold_panel", 30), ("hot_panel", 50)):
        case.add_field("temperature", temperature, group=group)
    for element, temperature in (("warm_beam", 60), ("hot_beam", 80)):
        case.add_field("temperature", temperature, element_ids=[element])
    run = _native_solve(model, "Thermal", tmp_path)
    for node, delta_sum in ((shell_tip, 10+30), (joint, 10+30+40), (tip, 10+30+40+60)):
        assert run.result_state.node_displacements[node][0] == pytest.approx(1e-5 * .2 * delta_sum, rel=1e-5)
    assert _reaction_resultant(run)[0] == pytest.approx([0, 0, 0], abs=.01)
