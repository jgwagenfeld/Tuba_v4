import unittest

from tuba import Model
from tuba.schema import SchemaValidationError, validate_model_dict, validate_patch_dict


class TestSchema(unittest.TestCase):
    def test_model_dict_validates(self):
        model = Model(project_name="Schema")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        validate_model_dict(model.to_dict())

    def test_missing_sections_fails(self):
        data = {
            "meta": {"project_name": "Bad", "standard": "ASME_B31.3", "version": "4.0.0"},
            "materials": {},
            "nodes": {},
            "elements": [],
            "supports": [],
            "load_cases": {},
        }

        with self.assertRaises(SchemaValidationError):
            validate_model_dict(data)

    def test_pipe_section_missing_dimensions_fails_schema_validation(self):
        data = {
            "meta": {"project_name": "Bad", "standard": "ASME_B31.3", "version": "4.0.0"},
            "materials": {},
            "sections": {"PipeSec": {"type": "pipe", "OD": 0.1}},
            "nodes": {},
            "elements": [],
            "supports": [],
            "load_cases": {},
        }

        with self.assertRaises(SchemaValidationError):
            validate_model_dict(data)

    def test_unknown_section_type_fails_schema_validation(self):
        data = {
            "meta": {"project_name": "Bad", "standard": "ASME_B31.3", "version": "4.0.0"},
            "materials": {},
            "sections": {"OddSec": {"type": "mystery", "OD": 0.1, "WT": 0.01}},
            "nodes": {},
            "elements": [],
            "supports": [],
            "load_cases": {},
        }

        with self.assertRaises(SchemaValidationError):
            validate_model_dict(data)

    def test_patch_dict_validates(self):
        data = {
            "operations": [
                {"op": "add_node", "local_id": "a", "coords": [0.0, 0.0, 0.0]},
                {
                    "op": "add_element",
                    "local_id": "e0",
                    "type": "pipe_straight",
                    "n1": "a",
                    "n2": "b",
                    "section": "PipeSec",
                    "material": "Steel",
                },
                {"op": "add_support", "node": "a", "type": "anchor"},
            ],
            "provenance": {"source": "agent"},
        }

        validate_patch_dict(data)

    def test_patch_dict_without_operation_type_fails(self):
        data = {"operations": [{"local_id": "a", "coords": [0.0, 0.0, 0.0]}]}

        with self.assertRaises(SchemaValidationError):
            validate_patch_dict(data)


if __name__ == "__main__":
    unittest.main()
