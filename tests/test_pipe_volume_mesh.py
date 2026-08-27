import gmsh
import numpy as np
import pytest

from tuba import Model
from tuba.meshing import build_pipe_volume_mesh


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


def test_rejects_unsupported_bend_before_writing(tmp_path):
    model, _n0, _n1 = _straight_pipe_model()
    model.get_element("pipe_0").type = "pipe_bend"
    output = tmp_path / "bend.med"

    with pytest.raises(ValueError, match="pipe_straight"):
        build_pipe_volume_mesh(
            model,
            output,
            element_ids=["pipe_0"],
            max_element_size=0.005,
        )

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
