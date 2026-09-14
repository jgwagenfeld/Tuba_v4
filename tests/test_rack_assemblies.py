import unittest

from tuba import Model
from tuba.assemblies import RackBay
from tuba.patches import AddElement, ModelTransaction
from tuba.schema import validate_patch_dict


class TestRackAssemblies(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Rack")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        return model

    def test_rack_bay_generates_patch_without_mutating_model(self):
        model = self._model()
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )

        patch = rack.to_patch()
        validate_patch_dict(patch.to_dict())

        self.assertEqual(len(model.nodes), 0)
        self.assertGreaterEqual(len(patch.operations), 15)
        self.assertEqual(patch.provenance["assembly"], "rack_A")

    def test_rack_bay_identity_and_attachment_points_roundtrip(self):
        model = self._model()
        rack = RackBay(
            name="rack_A",
            origin=(10.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )

        result = ModelTransaction(model).apply(rack.to_patch())
        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(result.group_names, ["rack_A"])
        self.assertIn("rack_A", loaded.groups)
        group = loaded.groups["rack_A"]
        self.assertEqual(group["metadata"]["assembly_type"], "rack_bay")
        self.assertEqual(group["metadata"]["zone"], "north")
        self.assertGreaterEqual(len(group["elements"]), 12)
        self.assertTrue(group["metadata"]["attachment_points"]["level_1_left"].startswith("node:N"))
        self.assertEqual(loaded.get_attributes("group:rack_A")["rack.zone"], "north")

    def test_rack_bay_assigns_sections_by_member_role(self):
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="Fallback",
            material="Steel",
            column_section="ColumnIPE",
            longitudinal_section="LongRHS",
            transverse_section="CrossRHS",
        )

        members = [operation for operation in rack.to_patch().operations if isinstance(operation, AddElement)]

        self.assertEqual(
            {member.section for member in members if "_col_" in member.local_id},
            {"ColumnIPE"},
        )
        self.assertEqual(
            {member.section for member in members if "_long_" in member.local_id},
            {"LongRHS"},
        )
        self.assertEqual(
            {member.section for member in members if "_cross_" in member.local_id},
            {"CrossRHS"},
        )


if __name__ == "__main__":
    unittest.main()
