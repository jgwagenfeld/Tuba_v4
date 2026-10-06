"""Display partitions cannot change solver identity or masquerade as volume cells."""

from dataclasses import replace

from tuba import Model
from tuba.analysis.mesh import AnalysisMesh, MeshElementSource
from tuba.analysis.provenance import build_solver_input_identity
from tuba.visualization.builders._states import _build_analysis_mesh_scene


def test_display_partition_identity_keeps_engineering_geometry_changes_visible():
    model = Model("Display provenance")
    model.define_load_case("Case", gravity=False)
    model.add_cad_asset(id="part", source_path="part.step", source_format="STEP", unit_scale_to_m=1,
                        content_digest="original", metadata={"mesh_size": .01})
    before = build_solver_input_identity(model, "Case")
    model.cad_assets["part"].metadata["display_face_partitions"] = [{"selector": {"position": [0, 0, 0]}, "face_indices": [0]}]
    assert build_solver_input_identity(model, "Case") == before
    # The digest names the content, so the folder the project was copied to does not.
    model.cad_assets["part"] = replace(model.cad_assets["part"], source_path=r"D:\elsewhere\part.step")
    assert build_solver_input_identity(model, "Case") == before
    model.cad_assets["part"] = replace(model.cad_assets["part"], content_digest="changed")
    assert build_solver_input_identity(model, "Case") != before
    # Without a digest the path is all that identifies the CAD, so it still counts.
    model.cad_assets["part"] = replace(model.cad_assets["part"], content_digest=None)
    undigested = build_solver_input_identity(model, "Case")
    model.cad_assets["part"] = replace(model.cad_assets["part"], source_path="other.step")
    assert build_solver_input_identity(model, "Case") != undigested


def test_quad8_cut_face_nodes_do_not_become_hexahedral_volume_edges():
    points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
              (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
              (.5, 0, 0), (1, .5, 0), (.5, 1, 0), (0, .5, 0)]
    nodes = {f"N{i}": point for i, point in enumerate(points)}
    volume = tuple(f"N{i}" for i in range(8))
    surface = ("N0", "N1", "N2", "N3", "N8", "N9", "N10", "N11")
    mesh = AnalysisMesh(id="mesh", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements={"VM1": volume, "VS1": surface}, groups={"G_END_N0": ("VS1",)}, node_sources={},
        element_sources={
            "VM1": MeshElementSource("VM1", "element:pipe", role="volume_cell"),
            "VS1": MeshElementSource("VS1", "element:pipe", role="volume_skin")},
        surface_mesh={"vertices": points[:4], "faces": [[0, 1, 2, 3]], "node_ids": list(surface[:4])})
    contribution = _build_analysis_mesh_scene(mesh)
    skin = next(asset for asset in contribution.assets if asset.generation_config.get("source") == "tuba.analysis_mesh.volume_skin")
    assert len(skin.generation_config["volume_vertices"]) == 8
    assert len(skin.generation_config["volume_edge_indices"]) == 12
