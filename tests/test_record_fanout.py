"""Element and Support are the one definition every surface projects.

The record's ``to_dict()`` is the canonical encoding; the model schema, the patch
schema and the patch records must all agree with the dataclass fields, so a new
field cannot be added to one surface and forgotten on another.
"""

from __future__ import annotations

import dataclasses

import pytest

from tuba import Model
from tuba.model import Element, Support
from tuba.patches import AddElement, AddSupport
from tuba.schema import MODEL_SCHEMA_V4, PATCH_SCHEMA_V1

#: Fields the records serialize; the codelink lines are deliberately not encoded.
ELEMENT_KEYS = {field.name for field in dataclasses.fields(Element)} - {"source_line", "source_call_line"}
SUPPORT_KEYS = {field.name for field in dataclasses.fields(Support)} - {"source_line", "source_call_line"}


def _record_model() -> Model:
    model = Model(project_name="RecordFanOut")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    node_a = model.add_node([0.0, 0.0, 0.0])
    node_b = model.add_node([1.0, 0.0, 0.0])
    model.add_element(
        id="run",
        type="pipe_straight",
        n1=node_a,
        n2=node_b,
        section="Pipe",
        material="Steel",
        bend_radius=5,
        bend_angle=90,
        twist_angle=15,
        route_id="line",
        station_start=0,
        station_end=1,
    )
    model.add_support(
        node=node_a,
        type="guide",
        direction=[1.0, 0.0, 0.0],
        stiffness=1.0e6,
        imposed_displacement=[0.0, 0.0, 0.001],
        stiffness_matrix=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        blocked_dof=[True, False, False, False, False, False],
        mass=10.0,
        friction_coefficient=0.3,
        gap=0.001,
        normal_stiffness=1.0e7,
        tangential_stiffness=1.0e6,
        attached_to=node_b,
        id="shoe",
    )
    return model


def test_model_serialization_projects_the_record_encoding():
    model = _record_model()

    assert model.to_dict()["elements"] == [element.to_dict() for element in model.elements]
    assert model.to_dict()["supports"] == [support.to_dict() for support in model.supports]


def test_element_encoding_stays_conditional_and_float_cast():
    model = Model(project_name="BareElement")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    node_a = model.add_node([0.0, 0.0, 0.0])
    node_b = model.add_node([1.0, 0.0, 0.0])
    element = model.add_element(
        id="run", type="pipe_straight", n1=node_a, n2=node_b, section="Pipe", material="Steel",
        bend_radius=5, bend_angle=90,
    )

    encoded = element.to_dict()

    # Declared floats serialize as float even from int literals; the fingerprint
    # hashes this payload, so 90 and 90.0 must not differ.
    assert encoded["bend_radius"] == 5.0 and isinstance(encoded["bend_radius"], float)
    assert encoded["bend_angle"] == 90.0 and isinstance(encoded["bend_angle"], float)
    assert set(encoded) == {
        "id", "type", "n1", "n2", "section", "material", "bend_radius", "bend_angle"
    }


def test_support_encoding_omits_imposed_displacement():
    """Pinned, not accidental: the record carries the field, the encoding drops it.

    ``imposed_displacement`` is consumed by reporting and contact code but was never
    serialized; making the encoding canonical must not silently change that. A
    follow-up decides whether the encoding should carry it.
    """
    model = _record_model()
    support = model.supports[0]

    assert support.imposed_displacement == [0.0, 0.0, 0.001]
    assert "imposed_displacement" not in support.to_dict()
    assert set(support.to_dict()) == SUPPORT_KEYS - {"imposed_displacement"}


def _operation_schema(op: str) -> dict:
    for candidate in PATCH_SCHEMA_V1["properties"]["operations"]["items"]["oneOf"]:
        if candidate["properties"]["op"].get("const") == op:
            return candidate
    raise AssertionError(f"No patch schema for {op!r}.")


def test_model_schema_describes_the_record_fields():
    element_properties = MODEL_SCHEMA_V4["properties"]["elements"]["items"]["properties"]
    support_properties = MODEL_SCHEMA_V4["properties"]["supports"]["items"]["properties"]

    assert set(element_properties) == ELEMENT_KEYS
    assert set(support_properties) == SUPPORT_KEYS


def test_patch_schema_describes_the_record_fields():
    assert set(_operation_schema("add_element")["properties"]) == (
        {"op", "local_id", "id_prefix"} | (ELEMENT_KEYS - {"id"})
    )
    assert set(_operation_schema("add_support")["properties"]) == {"op"} | (SUPPORT_KEYS - {"id"})


def test_patch_records_mirror_the_model_records():
    add_element_fields = {field.name for field in dataclasses.fields(AddElement)}
    add_support_fields = {field.name for field in dataclasses.fields(AddSupport)}

    assert add_element_fields == (ELEMENT_KEYS - {"id"}) | {"local_id", "id_prefix"}
    assert add_support_fields == SUPPORT_KEYS - {"id"}


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
