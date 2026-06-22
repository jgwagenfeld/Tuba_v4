import unittest

import ifcopenshell

from tuba.external.ifc import IfcExporter
from tuba.external.ifc_mapping import IfcGuidRegistry, add_property_set, ifc_property


class TestIfcMapping(unittest.TestCase):
    def test_ifc_exporter_exposes_operating_state_property_set_name(self):
        self.assertEqual(IfcExporter.OPERATING_STATE_PSET, "Pset_TubaOperatingState")

    def test_guid_registry_reuses_guid_for_same_ref(self):
        registry = IfcGuidRegistry()
        first = registry.guid_for("element:pipe_0")
        second = registry.guid_for("element:pipe_0")
        other = registry.guid_for("element:pipe_1")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 22)

    def test_property_set_helper_attaches_typed_values(self):
        f = ifcopenshell.file(schema="IFC4")
        wall = f.create_entity("IfcBuildingElementProxy", GlobalId=IfcGuidRegistry().guid_for("obstacle:x"), Name="x")
        add_property_set(
            f,
            wall,
            "Pset_Tuba_Test",
            [
                ifc_property(f, "Name", "Pipe"),
                ifc_property(f, "Count", 3),
                ifc_property(f, "Ratio", 1.25),
                ifc_property(f, "Enabled", True),
            ],
        )

        psets = [
            rel.RelatingPropertyDefinition
            for rel in wall.IsDefinedBy
            if rel.is_a("IfcRelDefinesByProperties")
        ]
        self.assertEqual(psets[0].Name, "Pset_Tuba_Test")
        values = {prop.Name: prop.NominalValue.wrappedValue for prop in psets[0].HasProperties}
        self.assertEqual(values["Name"], "Pipe")
        self.assertEqual(values["Count"], 3)
        self.assertEqual(values["Ratio"], 1.25)
        self.assertEqual(values["Enabled"], True)


if __name__ == "__main__":
    unittest.main()
