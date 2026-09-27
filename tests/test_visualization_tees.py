"""Joined tee display remains one hollow surface and keeps native picking IDs."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from tuba import Model
from tuba.visualization import SceneRequest, build_visualization_scene


@pytest.mark.parametrize("branch_od", [0.1, 0.06])
def test_joined_tee_wall_from_worker_is_connected_and_closed(branch_od):
    pytest.importorskip("gmsh")
    model = Model("tee surface regression")
    model.add_material("steel", E=2e11, nu=0.3)
    model.add_pipe_section("header", OD=0.1, WT=0.01)
    model.add_pipe_section("branch", OD=branch_od, WT=0.008)
    center = model.add_node([1, 2, 3])
    for eid, vector, section in (
        ("left", [-0.12, 0, 0], "header"),
        ("right", [0.12, 0, 0], "header"),
        ("branch", [0, 0, 0.12], "branch"),
    ):
        end = model.add_node((np.array([1, 2, 3]) + vector).tolist())
        model.add_element(id=eid, type="pipe_straight", n1=center, n2=end,
                          section=section, material="steel")
    model.define_tee(center, type="welding_tee")
    model = Model.from_dict(model.to_dict())
    with ThreadPoolExecutor(max_workers=1) as worker:
        scene = worker.submit(build_visualization_scene, SceneRequest(model)).result()
    assert not scene.diagnostics
    assert {str(obj.entity_ref) for obj in scene.objects if obj.kind == "pipe"} == {
        "element:left", "element:right", "element:branch",
    }
    edges = Counter()
    adjacency = defaultdict(set)
    for asset in scene.geometry_assets:
        assert asset.format == "mesh"
        assert asset.generation_config["source"] == "tuba.tee_wall"
        vertices = [tuple(round(v, 10) for v in point) for point in asset.generation_config["vertices"]]
        assert asset.generation_config["faces"]
        for face in asset.generation_config["faces"]:
            points = [vertices[i] for i in face]
            for a, b in zip(points, points[1:] + points[:1]):
                edges[tuple(sorted((a, b)))] += 1
                adjacency[a].add(b)
                adjacency[b].add(a)
    assert set(edges.values()) == {2}, "Tee wall must have no holes or duplicate/internal faces"
    pending = [next(iter(adjacency))]
    visited = set()
    while pending:
        point = pending.pop()
        if point not in visited:
            visited.add(point)
            pending.extend(adjacency[point] - visited)
    assert len(visited) == len(adjacency), "Three capped tubes are not a joined tee wall"
