import gmsh
import numpy as np
import pytest

from tuba import Model
from tuba.meshing import build_pipe_volume_mesh
from tuba.model import make_bend_geometry


def _straight_pipe_model(*, length=0.2):
    model = Model("StraightPipeVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([length, 0.0, 0.0])
    model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
    )
    return model, n0, n1


def _tee_model(*, branch_od=0.1):
    model = Model("TeeVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Header", OD=0.1, WT=0.01)
    branch_section = "Header"
    if branch_od != 0.1:
        branch_section = "Branch"
        model.add_pipe_section(branch_section, OD=branch_od, WT=0.008)
    junction = model.add_node([0.0, 0.0, 0.0])
    ends = (
        model.add_node([-0.12, 0.0, 0.0]),
        model.add_node([0.12, 0.0, 0.0]),
        model.add_node([0.0, 0.12, 0.0]),
    )
    for element_id, end, section in zip(
        ("left", "right", "branch"),
        ends,
        ("Header", "Header", branch_section),
    ):
        model.add_element(
            id=element_id,
            type="pipe_straight",
            n1=junction,
            n2=end,
            section=section,
            material="Steel",
        )
    model.define_tee(junction)
    return model, junction, ends


def _bend_pipe_model():
    model = Model("BendPipeVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.1, 0.1, 0.0])
    geometry = make_bend_geometry(
        start=model.nodes[n0].coords,
        end=model.nodes[n1].coords,
        radius=0.1,
        angle=90.0,
        normal=[0.0, 0.0, 1.0],
        start_tangent=[1.0, 0.0, 0.0],
        end_tangent=[0.0, 1.0, 0.0],
        generation_mode="bend",
    )
    model.add_element(
        id="bend_0",
        type="pipe_bend",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
        bend_radius=geometry.radius,
        bend_angle=geometry.angle,
        bend_geometry=geometry,
    )
    return model, n0, n1


def _tetra_component_count(elements):
    cells = [tuple(nodes[:4]) for nodes in elements.values()]
    neighbours = [set() for _cell in cells]
    face_owners = {}
    for cell_index, cell in enumerate(cells):
        for omitted in range(4):
            face = frozenset(node for index, node in enumerate(cell) if index != omitted)
            for owner in face_owners.get(face, ()):
                neighbours[cell_index].add(owner)
                neighbours[owner].add(cell_index)
            face_owners.setdefault(face, []).append(cell_index)
    unseen = set(range(len(cells)))
    components = 0
    while unseen:
        components += 1
        pending = [unseen.pop()]
        while pending:
            for neighbour in neighbours[pending.pop()] & unseen:
                unseen.remove(neighbour)
                pending.append(neighbour)
    return components


def test_builds_grouped_quadratic_straight_pipe_med(tmp_path):
    meshio = pytest.importorskip("meshio")
    model, n0, n1 = _straight_pipe_model()
    output = tmp_path / "straight.med"

    generated = build_pipe_volume_mesh(
        model,
        output,
        element_ids=["pipe_0"],
        max_element_size=0.005,
        element_order=2,
    )

    assert generated.med_path == output
    assert output.is_file() and output.stat().st_size > 0
    assert generated.analysis_mesh.modelisations == {"G_SOLID_region_0": "3D"}
    assert generated.analysis_mesh.surface_mesh
    for name in (
        "G_SOLID_region_0",
        "G_INNER_region_0",
        "G_OUTER_region_0",
        f"G_END_{n0}",
        f"G_END_{n1}",
    ):
        assert generated.groups[name]

    assert generated.settings == {"element_order": 2, "max_element_size": 0.005}
    assert generated.gmsh_version
    assert np.isfinite(np.asarray(generated.surface_vertices)).all()
    assert generated.surface_faces
    assert max(index for face in generated.surface_faces for index in face) < len(generated.surface_vertices)

    med = meshio.read(output)
    assert any(block.type == "tetra10" for block in med.cells)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"element_order": 1, "max_element_size": 0.005}, "element_order=2"),
        ({"element_order": 2, "max_element_size": 0.006}, "two elements through"),
    ],
)
def test_rejects_invalid_mesh_settings_before_writing(tmp_path, kwargs, message):
    model, _n0, _n1 = _straight_pipe_model()
    output = tmp_path / "invalid.med"

    with pytest.raises(ValueError, match=message):
        build_pipe_volume_mesh(model, output, element_ids=["pipe_0"], **kwargs)

    assert not output.exists()


def test_builds_grouped_quadratic_bend_pipe_med(tmp_path):
    model, n0, n1 = _bend_pipe_model()

    generated = build_pipe_volume_mesh(
        model,
        tmp_path / "bend.med",
        element_ids=["bend_0"],
        max_element_size=0.005,
    )

    for name in (
        "G_SOLID_region_0",
        "G_INNER_region_0",
        "G_OUTER_region_0",
        f"G_END_{n0}",
        f"G_END_{n1}",
    ):
        assert generated.groups[name]
    assert _tetra_component_count(generated.analysis_mesh.elements) == 1
    assert np.isfinite(np.asarray(generated.surface_vertices)).all()
    assert generated.surface_faces
    assert generated.analysis_mesh.surface_mesh


def test_rejects_bend_without_explicit_geometry_before_writing(tmp_path):
    model, _n0, _n1 = _straight_pipe_model()
    model.get_element("pipe_0").type = "pipe_bend"
    output = tmp_path / "bend.med"

    with pytest.raises(ValueError, match="explicit bend_geometry"):
        build_pipe_volume_mesh(model, output, element_ids=["pipe_0"], max_element_size=0.005)

    assert not output.exists()


def test_preserves_caller_owned_gmsh_session(tmp_path):
    model, _n0, _n1 = _straight_pipe_model(length=0.1)
    if gmsh.isInitialized():
        gmsh.finalize()
    gmsh.initialize()
    gmsh.model.add("caller_model")
    try:
        build_pipe_volume_mesh(
            model,
            tmp_path / "owned.med",
            element_ids=["pipe_0"],
            max_element_size=0.005,
        )

        assert gmsh.isInitialized()
        assert gmsh.model.getCurrent() == "caller_model"
    finally:
        if gmsh.isInitialized():
            gmsh.finalize()


@pytest.mark.parametrize("branch_od", [0.1, 0.06])
def test_meshes_conformal_explicit_tee(tmp_path, branch_od):
    model, junction, ends = _tee_model(branch_od=branch_od)

    generated = build_pipe_volume_mesh(
        model,
        tmp_path / "tee.med",
        element_ids=["left", "right", "branch"],
        max_element_size=0.004,
    )

    assert generated.groups[f"G_TEE_{junction}"]
    assert generated.groups["G_SOLID_region_0"]
    assert {f"G_END_{node}" for node in ends} <= generated.groups.keys()
    assert _tetra_component_count(generated.analysis_mesh.elements) == 1
    expected_sources = ["element:branch", "element:left", "element:right"]
    assert {str(source.source_ref) for source in generated.analysis_mesh.node_sources.values()} == {
        f"node:{junction}"
    }
    assert {str(source.source_ref) for source in generated.analysis_mesh.element_sources.values()} == {
        f"node:{junction}"
    }
    assert all(
        source.metadata["source_element_refs"] == expected_sources
        for source in generated.analysis_mesh.element_sources.values()
    )


def test_rejects_non_finite_generated_coordinates(tmp_path, monkeypatch):
    model, _n0, _n1 = _straight_pipe_model(length=0.1)
    original = gmsh.model.mesh.getNodes

    def non_finite_nodes(*args, **kwargs):
        node_tags, coordinates, parameters = original(*args, **kwargs)
        coordinates = coordinates.copy()
        coordinates[0] = np.nan
        return node_tags, coordinates, parameters

    monkeypatch.setattr(gmsh.model.mesh, "getNodes", non_finite_nodes)

    with pytest.raises(RuntimeError, match="non-finite node coordinates"):
        build_pipe_volume_mesh(
            model,
            tmp_path / "non-finite.med",
            element_ids=["pipe_0"],
            max_element_size=0.005,
        )


def test_rejects_disconnected_generated_volume(tmp_path, monkeypatch):
    model, _n0, _n1 = _straight_pipe_model(length=0.1)
    original = gmsh.model.mesh.getElements

    def disconnected_cells(dim=-1, tag=-1):
        types, element_tag_blocks, node_tag_blocks = original(dim, tag)
        if dim != 3:
            return types, element_tag_blocks, node_tag_blocks
        filtered_tags = []
        filtered_nodes = []
        for element_type, element_tags, element_nodes in zip(types, element_tag_blocks, node_tag_blocks):
            node_count = gmsh.model.mesh.getElementProperties(element_type)[3]
            cells = np.asarray(element_nodes).reshape(-1, node_count)
            first = cells[0]
            other = next(cell for cell in cells[1:] if len(set(first[:4]) & set(cell[:4])) < 3)
            other_index = next(index for index, cell in enumerate(cells) if np.array_equal(cell, other))
            filtered_tags.append(np.asarray([element_tags[0], element_tags[other_index]]))
            filtered_nodes.append(np.concatenate([first, other]))
        return types, filtered_tags, filtered_nodes

    monkeypatch.setattr(gmsh.model.mesh, "getElements", disconnected_cells)

    with pytest.raises(RuntimeError, match="disconnected volume mesh"):
        build_pipe_volume_mesh(
            model,
            tmp_path / "disconnected.med",
            element_ids=["pipe_0"],
            max_element_size=0.005,
        )


def test_rejects_undeclared_tee_before_writing(tmp_path):
    model, junction, _ends = _tee_model()
    del model.tees[junction]
    output = tmp_path / "undeclared.med"

    with pytest.raises(ValueError, match="explicit tee"):
        build_pipe_volume_mesh(
            model,
            output,
            element_ids=["left", "right", "branch"],
            max_element_size=0.004,
        )

    assert not output.exists()
