import unittest

from tuba import Model
from tuba.analysis.provenance import _operation_field_payload
from tuba.model import OperationField, _operation_field_to_dict
from tuba.reporting.tables import _operation_field_dict
from tuba.schema import validate_model_dict
from tuba.validation import ModelValidationError


def _model(name: str = "NodeTemperatures") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route(name: str = "NodeTemperatures") -> Model:
    """pipe_str_0 runs N0 to N1 and pipe_str_1 runs N1 to N2, 1 m each along X, anchored at N0 and N2."""
    model = _model(name)
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


class TestNodeTemperatureAuthoring(unittest.TestCase):
    def test_node_ids_set_the_nodes_scope_and_round_trip(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        field_record = operating.add_field("temperature", 180.0, node_ids=["N1"])
        self.assertEqual(field_record.scope, "nodes")
        self.assertEqual(field_record.node_ids, ["N1"])
        model.validate()

        data = model.to_dict()
        validate_model_dict(data)
        self.assertEqual(
            data["operations"]["Operating"]["fields"],
            [{"quantity": "temperature", "value": 180.0, "scope": "nodes", "profile": "uniform", "node_ids": ["N1"]}],
        )
        restored = Model.from_dict(data)
        self.assertEqual(restored.operations["Operating"].fields[0].node_ids, ["N1"])
        self.assertEqual(restored.operations["Operating"].fields[0].scope, "nodes")
        restored.validate()

    def test_element_fields_keep_their_serialized_shape(self):
        element_field = OperationField("temperature", 120.0, scope="route", route_id="P-100")
        self.assertNotIn("node_ids", _operation_field_to_dict(element_field))
        self.assertNotIn("node_ids", _operation_field_payload(element_field))
        self.assertNotIn("node_ids", _operation_field_dict(element_field))

        node_field = OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"])
        self.assertEqual(_operation_field_to_dict(node_field)["node_ids"], ["N1"])
        self.assertEqual(_operation_field_payload(node_field)["node_ids"], ["N1"])
        self.assertEqual(_operation_field_dict(node_field)["node_ids"], ["N1"])

    def test_node_fields_take_only_uniform_temperatures_on_existing_nodes(self):
        cases = (
            ("pressure", 1.0e6, {"node_ids": ["N1"]}, "scopes 'pressure' to nodes; only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "profile": "linear"}, "only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"scope": "nodes"}, "has scope 'nodes' but no node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "route_id": "P-100"}, "lists node_ids but has scope 'route'"),
            (
                "temperature",
                80.0,
                {"node_ids": ["N1"], "station_start": 0.0},
                "takes no group, route_id, station range, element_ids or direction",
            ),
            ("temperature", 80.0, {"node_ids": ["N9"]}, r"references missing nodes \['N9'\]"),
        )
        for quantity, value, kwargs, message in cases:
            model = _two_element_route()
            model.define_operation("Operating", gravity=False).add_field(quantity, value, **kwargs)
            with self.subTest(message=message):
                with self.assertRaisesRegex(ModelValidationError, message):
                    model.validate()

    def test_node_temperatures_need_a_pipe_node(self):
        model = _model("RackNode")
        with model.pipe("PipeSec", "Steel", route="RACK") as rack:
            rack.start([0.0, 0.0, 0.0], support="anchor")
            rack.run(1.0)
            rack.beam(1.0)
            rack.end(support="anchor")
        # pipe_str_0 runs N0 to N1 and beam_0 runs N1 to N2, so N2 touches only the beam.
        model.define_operation("Operating", gravity=False).add_field("temperature", 80.0, node_ids=["N2"])
        with self.assertRaisesRegex(ModelValidationError, r"nodes on no pipe element: \['N2'\]"):
            model.validate()

    def test_node_temperatures_are_states(self):
        agreeing = _two_element_route()
        operating = agreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 150.0, node_ids=["N1", "N2"])
        agreeing.validate()

        disagreeing = _two_element_route()
        operating = disagreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, node_ids=["N1"])
        with self.assertRaisesRegex(
            ModelValidationError, r"overlapping incompatible temperature fields on node 'N1': 150\.0 vs 90\.0"
        ):
            disagreeing.validate()

    def test_node_and_element_temperatures_may_not_meet_at_a_node(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        with self.assertRaisesRegex(
            ModelValidationError,
            r"gives nodes \['N1'\] a node temperature, but they belong to elements that "
            r"element temperature fields \[1\] cover; a node takes one or the other",
        ):
            model.validate()

        # N0 lies only on pipe_str_0, which no element field covers.
        apart = _two_element_route()
        operating = apart.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N0"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        apart.validate()
