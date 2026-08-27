import pytest

from tuba import Model
from tuba.geometry.junctions import classify_tee_junction


def _tee_model(directions):
    model = Model("TeeTopology")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Header", OD=0.1143, WT=0.00602)
    junction = model.add_node([0.0, 0.0, 0.0])
    for element_id, direction in zip(("left", "right", "branch"), directions):
        end = model.add_node(direction)
        model.add_element(
            id=element_id,
            type="pipe_straight",
            n1=junction,
            n2=end,
            section="Header",
            material="Steel",
        )
    model.define_tee(junction)
    return model, junction


def test_classifies_opposite_pair_as_header():
    model, junction = _tee_model(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    classified = classify_tee_junction(model, junction)

    assert set(classified.header_element_ids) == {"left", "right"}
    assert classified.branch_element_id == "branch"
    assert classified.directions["branch"] == (0.0, 1.0, 0.0)


def test_rejects_symmetric_wye_as_ambiguous():
    model, junction = _tee_model(
        ((1.0, 0.0, 0.0), (-0.5, 0.8660254038, 0.0), (-0.5, -0.8660254038, 0.0))
    )

    with pytest.raises(ValueError, match="ambiguous header"):
        classify_tee_junction(model, junction)


def test_rejects_zero_length_direction():
    model, junction = _tee_model(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    with pytest.raises(ValueError, match="zero-length"):
        classify_tee_junction(model, junction)


def test_selected_elements_must_form_exactly_three_way_junction():
    model, junction = _tee_model(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    with pytest.raises(ValueError, match="exactly three"):
        classify_tee_junction(model, junction, element_ids=["left", "branch"])


def test_rejects_missing_junction_node():
    model, _junction = _tee_model(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    with pytest.raises(ValueError, match="does not exist"):
        classify_tee_junction(model, "missing")


def test_rejects_non_circular_section():
    model, junction = _tee_model(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
    model.add_rectangular_section("Box", height_y=0.1, height_z=0.1)
    model.get_element("branch").section = "Box"

    with pytest.raises(ValueError, match="circular PipeSection"):
        classify_tee_junction(model, junction)
