"""Shared joints and member admission for procedural construction units."""

import numpy as np
import pytest

from tuba import Model
from tuba.patches import AddNode, ModelPatch, ModelTransaction
from tuba.validation import ModelValidationError


def test_node_resolution_reuses_by_distance_and_preserves_explicit_nodes():
    model = Model("Shared joints")
    joint = model.get_or_create_node(np.array([1000.0, 0.0, 0.0]))
    assert model.get_or_create_node((1000.0005, 0.0, 0.0), tolerance=0.001) == joint
    assert model.get_or_create_node((1000.0, 0.0, 0.0)) == joint
    assert model.get_or_create_node((1000.005, 0.0, 0.0), tolerance=0.001) != joint
    restored = Model.from_dict(model.to_dict())
    assert restored.get_or_create_node((1000.0, 0.0, 0.0)) == joint
    assert restored.add_node((1000.0, 0.0, 0.0)) != joint
    assert len(restored.nodes) == 3


@pytest.mark.parametrize(("point", "tolerance"), [
    ((0, 0), 1e-6), ((0, 0, 0, 0), 1e-6),
    ((float("nan"), 0, 0), 1e-6), ((float("inf"), 0, 0), 1e-6),
    (("1", 0, 0), 1e-6), ((True, 0, 0), 1e-6), ((1j, 0, 0), 1e-6),
    ((0, 0, 0), 0), ((0, 0, 0), -1), ((0, 0, 0), float("inf")),
    ((0, 0, 0), float("nan")), ((0, 0, 0), True), ((0, 0, 0), "1"),
    ((1e308, 0, 0), 1e308), ((1, 0, 0), 5e-324),
])
def test_invalid_node_resolution_leaves_model_unmodified(point, tolerance):
    model = Model("Invalid joint")
    with pytest.raises(ValueError):
        model.get_or_create_node(point, tolerance=tolerance)
    assert not model.nodes
    assert not model._node_point_index
    assert model.add_node((0, 0, 0)) == "N0"


def test_transaction_node_resolution_uses_the_same_validation_and_rolls_back():
    model = Model("Atomic joints")
    joint = model.add_node((0, 0, 0))
    result = ModelTransaction(model).apply(ModelPatch(operations=[
        AddNode(local_id="joint", coords=(0, 0, 0)),
    ]))
    assert result.node_ids["joint"] == joint
    with pytest.raises(ValueError):
        ModelTransaction(model).apply(ModelPatch(operations=[
            AddNode(local_id="new", coords=(1, 0, 0)),
            AddNode(local_id="bad", coords=(2, 0, 0), tolerance=0),
        ]))
    assert list(model.nodes) == [joint]


def test_member_validation_collects_connectivity_and_property_errors():
    model = Model("Invalid member")
    start = model.add_node((0, 0, 0))
    end = model.add_node((0, 0, 0))
    model.add_element(id="bad", type="unknown", n1=start, n2=end,
                      section="missing", material="missing", twist_angle=float("nan"))
    with pytest.raises(ModelValidationError) as error:
        model.validate()
    for message in ("unsupported type", "twist_angle", "zero length",
                    "missing section", "missing material"):
        assert message in str(error.value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "90"])
def test_member_twist_validation_cannot_be_bypassed_by_mutation_or_import(value):
    model = Model("Member rotation")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_ibeam_section("Beam", "IPE80")
    start, end = model.add_node((0, 0, 0)), model.add_node((1, 0, 0))
    member = model.add_element(id="beam", type="beam", n1=start, n2=end,
                               section="Beam", material="Steel", twist_angle=90.0)
    model.validate()
    payload = model.to_dict()
    member.twist_angle = value
    with pytest.raises(ModelValidationError, match="twist_angle"):
        model.validate()
    payload["elements"][0]["twist_angle"] = value
    with pytest.raises(ValueError):
        Model.from_dict(payload).validate()


def test_malformed_mutated_coordinates_preserve_collected_diagnostics():
    model = Model("Malformed joint")
    start = model.add_node((0, 0, 0))
    end = model.add_node((1, 0, 0))
    model.add_element(id="bad", type="unknown", n1=start, n2=end,
                      section="missing", material="missing")
    model.nodes[end].coords = ["invalid", 0, 0]
    with pytest.raises(ModelValidationError) as error:
        model.validate()
    assert "invalid coordinates" in str(error.value)
    assert "unsupported type" in str(error.value)


def test_member_length_overflow_is_rejected_after_node_mutation():
    model = Model("Unrepresentable member")
    start, end = model.add_node((0, 0, 0)), model.add_node((1, 0, 0))
    model.add_element(id="beam", type="beam", n1=start, n2=end,
                      section="missing", material="missing")
    model.nodes[start].coords = np.array([-1e308, 0, 0])
    model.nodes[end].coords = np.array([1e308, 0, 0])
    with pytest.raises(ModelValidationError, match="non-finite length"):
        model.validate()
