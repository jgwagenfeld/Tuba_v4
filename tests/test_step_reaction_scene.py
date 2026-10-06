"""Portable scene-contract fixtures; these are not engineering solver results."""

from dataclasses import replace
import json

import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource, ResultState
from tuba.refs import EntityRef
from tuba.visualization import SceneRequest, build_visualization_scene


@pytest.mark.parametrize("state_count", [1, 2])
def test_solid_reaction_targets_keep_physical_mesh_markers_and_provenance(state_count):
    model = Model("STEP reaction scene contract fixture")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start, end = model.add_node([0.2, 0, 0]), model.add_node([1.2, 0, 0])
    model.add_element(id="extension", type="pipe_straight", n1=start, n2=end,
                      section="Pipe", material="Steel")
    model.define_load_case("Axial", gravity=False)
    nodes = {"VN2": (0, 0, 0.05), "VN3": (0, 0.04, 0), "VN4": (0.1, 0, 0.04),
             "VN5": (0.1, 0.04, 0), "LN1": (0.2, 0, 0), "LN2": (1.2, 0, 0)}
    mesh = AnalysisMesh(
        id="step-fixture", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"VM1": ("VN2", "VN3", "VN4", "VN5"), "LM1": ("LN1", "LN2")},
        groups={"G_base": ("VN2", "VN3"), "G_PIPE": ("LM1",)},
        node_sources={
            **{node_id: MeshNodeSource(node_id, "component:component", "volume_node",
                                      metadata={"cad_face_group": "G_base"})
               for node_id in ("VN2", "VN3", "VN4", "VN5")},
            "LN1": MeshNodeSource("LN1", EntityRef("node", start), "native_node"),
            "LN2": MeshNodeSource("LN2", EntityRef("node", end), "native_node"),
        },
        element_sources={"VM1": MeshElementSource("VM1", "component:component", "volume_cell"),
                         "LM1": MeshElementSource("LM1", "element:extension", "native_element")},
        surface_mesh={"vertices": [nodes[n] for n in ("VN2", "VN3", "VN4")],
                      "faces": [[0, 1, 2]], "node_ids": ["VN2", "VN3", "VN4"]},
    )
    state = ResultState(
        id="result:0", study_id="study:fixture", model_revision=0, solver_name="Code_Aster",
        load_case="Axial", mesh_id=mesh.id,
        node_displacements={node_id: (0, 0, 0, None, None, None) for node_id in nodes},
        node_reactions={"VN2": (-1, 0, 0, None, None, None),
                        "LN1": (1, 0, 0, 0, 0, 0), start: (1, 0, 0, 0, 0, 0)},
        element_results={},
        metadata={"volume_analysis": True, "volume_von_mises": {n: 1.0 for n in nodes}},
    )
    scene = build_visualization_scene(SceneRequest(
        model, analysis_meshes=[mesh],
        result_states=[replace(state, id=f"result:{index}") for index in range(state_count)]))
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    markers = {obj.id: obj for obj in scene.objects if obj.kind == "analysis_mesh_node"}
    assert set(markers) == {f"object:analysis_mesh:{mesh.id}:node:{n}" for n in ("VN2", "LN1", "LN2")}
    marker = markers[f"object:analysis_mesh:{mesh.id}:node:VN2"]
    assert marker.entity_ref == EntityRef("component", "component")
    assert marker.metadata["coordinates"] == list(nodes["VN2"])
    assert marker.metadata["source_metadata"] == {"cad_face_group": "G_base"}
    assert marker.group_ids == ["G_base"]
    assert marker.source["analysis_mesh"] == {"id": mesh.id, "member_type": "node", "member_id": "VN2"}
    assert next(asset for asset in scene.geometry_assets if asset.id == marker.geometry_asset_id).generation_config["point"] == list(nodes["VN2"])
    reactions = [overlay for overlay in scene.overlays if overlay.data.get("result_type") == "reaction_force"]
    assert len(reactions) == state_count
    for overlay in reactions:
        vector = next(vector for vector in overlay.data["vectors"] if vector["node_id"] == "VN2")
        assert vector["object_ids"] == [marker.id]
        assert vector["reaction_force_n"] == list(state.node_reactions["VN2"][:3])
