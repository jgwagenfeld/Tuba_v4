"""Build interface footprints describe authored selections, not geometric guesses."""

import pytest

from tuba import Model
from tuba.analysis.mesh import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.visualization import SceneRequest, build_visualization_scene
from tuba.visualization.builders._mappings import build_interface_mapping_scene
from tuba.visualization.builders._layers import mesh_identity


def part_model(*, partitions=True):
    model = Model("Mapping footprint")
    model.add_material("steel", E=2e11, nu=.3)
    selector = {"position": [0, 0, 0], "type": "Plane", "shape": "planar_face"}
    metadata = {"mesh_vertices_local": [[0, 0, 0], [1000, 0, 0], [0, 1000, 0], [0, 0, 1000]],
                "mesh_faces": [[0, 1, 2], [0, 1, 3]]}
    if partitions:
        metadata["display_face_partitions"] = [{"selector": selector, "face_indices": [0]}]
    model.add_cad_asset(id="asset", source_path="fixture.step", source_format="STEP", unit_scale_to_m=.001,
                        placement={"origin": [10, 20, 30]}, metadata=metadata)
    model.add_imported_component(id="part", asset="cad_asset:asset", name="Part")
    model.add_analysis_region(id="solid", owner="component:part", role="solid_3d", code_aster_modelisation="3D",
                              material="steel", mesh_group="G_SOLID")
    ref = model.add_reference_point("ref", position=[10, 20, 31])
    model.add_rigid_patch("mount", reference=ref, component="part", faces=[selector])
    return model, ref


def target_assets(contribution):
    return [a for a in contribution.assets if a.generation_config["part"] == "target"]


def test_step_partition_highlights_only_selected_face_with_placement_once():
    model, ref = part_model()
    contribution = build_interface_mapping_scene(model)
    obj, = contribution.objects
    target, = target_assets(contribution)
    assert obj.id == "object:interface_mapping:mount"
    assert obj.kind == "interface_mapping"
    assert obj.metadata["interface_mapping"] == "0D reference ↔ 2D face"
    assert obj.metadata["model_mapping"] == "0D reference ↔ 3D solid"
    assert obj.metadata["status"] == "authored"
    assert obj.metadata["owner_refs"] == ["coupling:mount", f"node:{ref}", "component:part"]
    assert target.generation_config["faces"] == [[0, 1, 2]]
    assert target.generation_config["vertices"] == [[10, 20, 30], [11, 20, 30], [10, 21, 30]]
    assert not contribution.diagnostics
    assert all(a.object_ids == [obj.id] for a in contribution.assets)


def test_missing_source_partition_does_not_guess_a_face():
    model, _ = part_model(partitions=False)
    contribution = build_interface_mapping_scene(model)
    assert not target_assets(contribution)
    assert contribution.objects[0].metadata["target_geometry_available"] is False
    assert contribution.objects[0].metadata["status"] == "authored"
    assert contribution.diagnostics[0].code == "interface_mapping.unavailable_target"


def test_partial_face_footprint_clips_before_placement_and_keeps_selected_nodes():
    model, ref = part_model()
    model.couplings["mount"].metadata["node_filter"] = {
        "coordinate_frame": "source-local mm", "axis": "x", "comparison": "<=", "threshold": 250.}
    model.validate()
    contribution = build_interface_mapping_scene(model)
    target, = target_assets(contribution)
    vertices = target.generation_config["vertices"]
    assert all(10 <= point[0] <= 10.25 and point[2] == 30 for point in vertices)
    assert max(point[0] for point in vertices) == 10.25
    assert len(target.generation_config["faces"]) == 2
    assert contribution.objects[0].metadata["node_filter"]["threshold"] == 250
    # A selected midside node need not belong to a completely selected triangle.
    mesh = AnalysisMesh(id="partial", model_revision=0, solver_name="Code_Aster",
        nodes={"R": [10,20,31], "A": [10,20,30], "M": [10.2,20,30]}, elements={},
        groups={"G_mount_PATCH": ("R", "A", "M"), f"G_NODE_{ref}": ("R",)},
        node_sources={}, element_sources={})
    resolved = build_interface_mapping_scene(model, analysis_meshes=[mesh])
    metadata = resolved.objects[0].metadata
    assert metadata["status"] == "meshed"
    assert metadata["node_ids"] == ["A", "M"] and metadata["target_node_count"] == 2
    assert metadata["target_face_count"] == 0
    assert len(target_assets(resolved)) == 2


@pytest.mark.parametrize("partition", [
    {"selector": {"position": [0, 0, 0], "type": "Plane", "shape": "planar_face"}, "face_indices": [-1]},
    {"selector": None, "face_indices": [0]},
])
def test_invalid_display_partition_cannot_select_an_unrelated_face(partition):
    model, _ = part_model()
    model.cad_assets["asset"].metadata["display_face_partitions"] = [partition]
    contribution = build_interface_mapping_scene(model)
    assert not target_assets(contribution)
    assert contribution.diagnostics[0].code == "interface_mapping.unavailable_target"


@pytest.mark.parametrize("selection, mapping, format", [
    ("vertices", "0D reference ↔ 0D vertices", "marker"),
    ("edges", "0D reference ↔ 1D edges", "line"),
])
def test_shell_selection_dimension_is_not_the_parent_shell_dimension(selection, mapping, format):
    model = Model("Shell mapping")
    model.add_material("steel", E=2e11, nu=.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], thickness=.01, material="steel")
    ref = model.add_reference_point("ref", position=[0, 0, 1])
    model.add_rigid_patch("mount", reference=ref, shell="panel", **{selection: [0]})
    contribution = build_interface_mapping_scene(model)
    assert contribution.objects[0].metadata["interface_mapping"] == mapping
    assert contribution.objects[0].metadata["model_mapping"] == "0D reference ↔ 2D shell"
    assert all(a.format == format for a in target_assets(contribution))


def test_meshed_patch_uses_actual_group_members_and_cell_connectivity():
    model, ref = part_model(partitions=False)
    nodes = {"A": (10, 20, 30), "B": (11, 20, 30), "C": (10, 21, 30), "R": (10, 20, 31), "X": (10, 20, 32)}
    mesh = AnalysisMesh(id="mesh", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"F": ("A", "B", "C"), "OTHER": ("A", "B", "X")},
        groups={"G_mount_PATCH": ("A", "B", "C", "R"), f"G_NODE_{ref}": ("R",)},
        node_sources={n: MeshNodeSource(n, "component:part", "volume_node") for n in nodes},
        element_sources={e: MeshElementSource(e, "component:part", "volume_skin") for e in ("F", "OTHER")})
    contribution = build_interface_mapping_scene(model, analysis_meshes=[mesh])
    metadata = contribution.objects[0].metadata
    assert metadata["status"] == "meshed"
    assert metadata["node_ids"] == ["A", "B", "C"]
    assert metadata["element_ids"] == ["F"]
    assert metadata["target_node_count"] == 3
    assert metadata["target_face_count"] == 1
    assert len(target_assets(contribution)) == 1
    assert target_assets(contribution)[0].generation_config["show_edges"] is True
    assert not contribution.diagnostics


def tee_model():
    model = Model("Mixed tee")
    model.add_material("steel", E=2e11, nu=.3)
    model.add_pipe_section("pipe", OD=.1, WT=.01)
    hub = model.add_node([0, 0, 0])
    for eid, point in (("left", [-.2, 0, 0]), ("right", [.2, 0, 0]), ("branch", [0, .2, 0])):
        cut = model.add_node(point)
        far = model.add_node([2*v for v in point])
        model.add_element(id=eid, type="pipe_straight", n1=hub, n2=cut, section="pipe", material="steel")
        model.add_element(id=f"line_{eid}", type="pipe_straight", n1=cut, n2=far, section="pipe", material="steel")
    model.define_tee(hub, type="welding_tee")
    return model


def test_tee_border_mappings_require_explicit_volume_study_selection():
    model = tee_model()
    assert not build_interface_mapping_scene(model).objects
    contribution = build_interface_mapping_scene(model, volume_export={"element_ids": ["left", "right", "branch"]})
    assert len(contribution.objects) == 3
    for obj in contribution.objects:
        assert obj.metadata["interface_mapping"] == "0D endpoint ↔ 2D cut face"
        assert obj.metadata["model_mapping"] == "1D pipe ↔ 3D solid"
        assert obj.metadata["method"] == "LIAISON_ELEM / 3D_TUYAU"
        assert obj.metadata["source_ref"].startswith("element:line_")
        assert obj.metadata["status"] == "authored"
        assert obj.metadata["target_face_count"] == 64
        label = next(a.generation_config for a in contribution.assets
                     if a.object_ids == [obj.id] and a.format == "label")
        assert label["text"] == f"{obj.metadata['source_node_ref'].split(':', 1)[1]} · 0D ↔ 2D"
        assert label["height"] <= .01


def test_mapping_layer_is_design_and_scene_contract_is_serializable():
    model, _ = part_model()
    scene = build_visualization_scene(SceneRequest(model))
    scene.validate()
    assert next(l for l in scene.layers if l.id == "interface_mappings").category == "design"
    assert any(o["kind"] == "interface_mapping" for o in scene.to_dict()["objects"])


def test_native_surface_quad8_is_a_face_family_not_a_volume_family():
    nodes = {str(i): (float(i), 0, 0) for i in range(20)}
    mesh = AnalysisMesh(id="mesh", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"SOLID": tuple(nodes), "CUT": tuple(list(nodes)[:8])}, groups={}, node_sources={},
        element_sources={"SOLID": MeshElementSource("SOLID", "element:tee", "volume_cell"),
                         "CUT": MeshElementSource("CUT", "element:tee", "volume_skin")})
    assert {e["family"] for e in mesh_identity(mesh)["element_families"]} == {"HEXA20", "QUAD8"}


def test_generated_cut_uses_actual_mesh_face_connectivity_when_supplied():
    model = tee_model()
    terminal = model.get_element("right").n2
    mesh = AnalysisMesh(id="cut_mesh", model_revision=0, solver_name="Code_Aster",
        nodes={"A": (.2, .05, 0), "B": (.2, 0, .05), "C": (.2, -.05, 0)},
        elements={"CUT": ("A", "B", "C")}, groups={f"G_END_{terminal}": ("CUT",)}, node_sources={},
        element_sources={"CUT": MeshElementSource("CUT", "element:right", "volume_skin")})
    contribution = build_interface_mapping_scene(model, analysis_meshes=[mesh],
        volume_export={"element_ids": ["left", "right", "branch"]})
    mapping = next(o for o in contribution.objects if o.metadata["face_group"] == f"G_END_{terminal}")
    assert mapping.metadata["status"] == "meshed"
    assert mapping.metadata["element_ids"] == ["CUT"]
    assert mapping.metadata["node_ids"] == ["A", "B", "C"]
    assert mapping.metadata["target_face_count"] == 1


def test_meshed_shell_edge_shows_actual_boundary_nodes_and_connectivity():
    model = Model("Meshed shell edge")
    model.add_material("steel", E=2e11, nu=.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], thickness=.01, material="steel")
    ref = model.add_reference_point("ref", position=[0, 0, 1])
    model.add_rigid_patch("mount", reference=ref, shell="panel", edges=[0])
    nodes = {"A": (0, 0, 0), "M": (.5, 0, 0), "B": (1, 0, 0), "C": (0, 1, 0), "R": (0, 0, 1)}
    mesh = AnalysisMesh(id="mesh", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"T1": ("A", "M", "C"), "T2": ("M", "B", "C")},
        groups={"G_mount_PATCH": ("A", "M", "B", "R"), f"G_NODE_{ref}": ("R",)}, node_sources={},
        element_sources={e: MeshElementSource(e, "group:panel", "shell_cell") for e in ("T1", "T2")})
    contribution = build_interface_mapping_scene(model, analysis_meshes=[mesh])
    targets = target_assets(contribution)
    segments = [a.generation_config["points"] for a in targets if a.format == "line"]
    assert len(segments) == 2
    assert any([.5, 0, 0] in segment for segment in segments)
    assert not any([0, 1, 0] in segment for segment in segments)
    assert contribution.objects[0].metadata["target_node_count"] == 3
    assert contribution.objects[0].metadata["target_edge_count"] == 2
    assert contribution.objects[0].metadata["status"] == "meshed"


def test_studio_build_reads_the_authored_volume_selection(tmp_path):
    import json
    from pathlib import Path
    from tuba.visualization.preview.server import ProjectStudioServer
    project = tmp_path / "project"
    project.mkdir()
    source = Path(__file__).resolve().parents[1] / "examples" / "pipe-tee-volume-review" / "model.py"
    (project / "model.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (project / "study.py").write_text("VOLUME_EXPORT={'element_ids':['header_left','header_right','branch'],'max_element_size':.005}\n", encoding="utf-8")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    assert server._run_script()[0]["ok"]
    server._publish_scene()
    scene = json.loads((tmp_path / "out" / "build" / "scene.json").read_text(encoding="utf-8"))
    mappings = [o for o in scene["objects"] if o["kind"] == "interface_mapping"]
    assert len(mappings) == 3
    assert all(o["metadata"]["status"] == "authored" for o in mappings)


def mapping_server_fixture(tmp_path, monkeypatch):
    """Deterministic artifact-loader fixture; it does not claim engineering solver results."""
    from types import SimpleNamespace
    from tuba.analysis.provenance import SolverInputIdentity
    from tuba.visualization.preview.server import ProjectStudioServer
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text("from tuba import Model\nmodel=Model('Mapping fixture')\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    model, ref = part_model(partitions=False)
    server.model = model
    server.study = SimpleNamespace(LOAD_CASES=())
    identity = SolverInputIdentity("fixture", "Operating", "tuba.model.v4", "tuba.code_aster.mixed.v2")
    mesh = AnalysisMesh(id="fixture", model_revision=0, solver_name="Code_Aster",
        nodes={"A": (10, 20, 30), "B": (11, 20, 30), "C": (10, 21, 30), "R": (10, 20, 31)},
        elements={"CUT": ("A", "B", "C")}, groups={"G_mount_PATCH": ("A", "B", "C", "R"), f"G_NODE_{ref}": ("R",)},
        node_sources={}, element_sources={"CUT": MeshElementSource("CUT", "component:part", "volume_skin")},
        solver_input_identity=identity)
    state = {"stale": False, "loads": 0}
    monkeypatch.setattr(ProjectStudioServer, "review_stale", property(lambda _: state["stale"]))

    def load(model, folder):
        state["loads"] += 1
        assert model is server.model
        assert folder == server.out_dir / "review" / "artifacts" / "Operating"
        return SimpleNamespace(solver_input_identity=identity), mesh, None, {"execution_method": "python"}

    monkeypatch.setattr("tuba.solver.aster_sidecar.load_and_attest_artifact_chain", load)
    return server, identity, state


def test_studio_build_reuses_verified_mesh_once_and_drops_it_when_stale(tmp_path, monkeypatch):
    import json
    server, identity, state = mapping_server_fixture(tmp_path, monkeypatch)
    server._review_identities = [identity]
    for _ in range(2):
        server._publish_scene()
        scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
        mapping, = [o for o in scene["objects"] if o["kind"] == "interface_mapping"]
        assert mapping["metadata"]["status"] == "meshed"
        assert mapping["metadata"]["node_ids"] == ["A", "B", "C"]
        assert not scene["result_fields"]
        assert not any(o["kind"] == "result_state" for o in scene["objects"])
    assert state["loads"] == 1
    state["stale"] = True
    server._publish_scene()
    scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
    mapping, = [o for o in scene["objects"] if o["kind"] == "interface_mapping"]
    assert mapping["metadata"]["status"] == "authored"
    assert "node_ids" not in mapping["metadata"]
    assert state["loads"] == 1


def test_review_publication_refreshes_build_mapping_membership(tmp_path, monkeypatch):
    import json
    from tuba.visualization import write_scene_bundle
    server, identity, state = mapping_server_fixture(tmp_path, monkeypatch)
    server._publish_scene()

    def review(namespace, output, *, artifact_dir):
        root = output / "review_scene"
        write_scene_bundle(build_visualization_scene(SceneRequest(server.model)), root)
        return root

    monkeypatch.setattr(server, "_review_builder", lambda: review)
    monkeypatch.setattr("tuba.project.freshness.attested_identities", lambda root: [identity])
    server._produce_review({}, artifact_dir=tmp_path)
    scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
    mapping, = [o for o in scene["objects"] if o["kind"] == "interface_mapping"]
    assert mapping["metadata"]["status"] == "meshed"
    assert state["loads"] == 1


def test_build_mesh_reuse_requires_a_current_study(tmp_path, monkeypatch):
    server, identity, state = mapping_server_fixture(tmp_path, monkeypatch)
    server._review_identities = [identity]
    server.study = None
    assert server._current_mapping_meshes() == ()
    assert state["loads"] == 0


@pytest.mark.parametrize("failure", ["damaged", "wrong_identity", "unverified"])
def test_build_refuses_meshes_without_current_verified_review_lineage(tmp_path, monkeypatch, failure):
    import json
    from dataclasses import replace
    server, identity, state = mapping_server_fixture(tmp_path, monkeypatch)
    server._review_identities = [identity]
    original = __import__("tuba.solver.aster_sidecar", fromlist=["load_and_attest_artifact_chain"]).load_and_attest_artifact_chain

    def invalid(model, root):
        if failure == "damaged":
            raise ValueError("Artifact hash mismatch")
        study, mesh, sidecar, attestation = original(model, root)
        if failure == "wrong_identity":
            mesh = replace(mesh, solver_input_identity=replace(identity, fingerprint="other"))
        else:
            attestation = {"execution_method": "docker"}
        return study, mesh, sidecar, attestation

    monkeypatch.setattr("tuba.solver.aster_sidecar.load_and_attest_artifact_chain", invalid)
    server._publish_scene()
    scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
    mapping, = [o for o in scene["objects"] if o["kind"] == "interface_mapping"]
    assert mapping["metadata"]["status"] == "authored"
    assert "node_ids" not in mapping["metadata"]
    assert any(d["code"] == "interface_mapping.unavailable_mesh" for d in scene["diagnostics"])
