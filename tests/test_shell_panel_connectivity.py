"""Adjacent authored shell panels must form a continuous physical mesh."""

import os

import pytest

from tuba import Model
from tuba.meshing.step_component import build_step_component_mesh


@pytest.mark.skipif(os.environ.get("TUBA_RUN_GMSH_INTEGRATION") != "1", reason="native Gmsh mesh check")
def test_adjacent_panels_share_the_entire_edge_and_native_corner(tmp_path):
    model = Model("Two joined panels")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    corner = model.add_node([1, 0, 0])
    model.add_shell_panel("left", polygon=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                          thickness=0.01, material="Steel", mesh_size=0.08)
    model.add_shell_panel("right", polygon=[[1, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0]],
                          thickness=0.01, material="Steel", mesh_size=0.25)
    mesh = build_step_component_mesh(model, tmp_path / "joined.med").analysis_mesh

    def nodes(panel):
        return {n for cell in mesh.groups[f"G_{panel}_SHELL"] for n in mesh.elements[cell]}

    left, right = nodes("left"), nodes("right")
    edge_left = {n for n in left if abs(mesh.nodes[n][0] - 1) < 1e-10}
    edge_right = {n for n in right if abs(mesh.nodes[n][0] - 1) < 1e-10}
    assert len(edge_left) > 6, "the common edge must retain the finer panel's sizing"
    assert edge_left == edge_right, "coincident shell edges must share every analysis DOF"
    assert set(mesh.groups[f"G_NODE_{corner}"]) <= edge_left
    assert len(mesh.groups[f"G_NODE_{corner}"]) == 1
