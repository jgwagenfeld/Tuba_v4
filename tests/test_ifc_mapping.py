import unittest

from tuba.external.ifc import IfcExporter


class TestIfcMapping(unittest.TestCase):
    def test_ifc_exporter_exposes_operating_state_property_set_name(self):
        self.assertEqual(IfcExporter.OPERATING_STATE_PSET, "Pset_TubaOperatingState")


if __name__ == "__main__":
    unittest.main()
