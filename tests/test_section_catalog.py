import importlib.util
import unittest

from tuba.sections import SectionCatalog


class TestSectionCatalog(unittest.TestCase):
    def test_loads_ibeam_dimensions_and_properties(self):
        profile = SectionCatalog.default().get_ibeam_profile("IPE80")

        self.assertEqual(profile.name, "IPE80")
        self.assertAlmostEqual(profile.dimensions["H"], 0.08)
        self.assertAlmostEqual(profile.dimensions["B"], 0.046)
        self.assertIn("A", profile.properties)
        self.assertGreater(profile.properties["A"], 0.0)
        self.assertGreater(profile.properties["IY"], 0.0)

    def test_missing_ibeam_profile_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            SectionCatalog.default().get_ibeam_profile("DOES_NOT_EXIST")

        self.assertIn("I-beam profile", str(ctx.exception))

    def test_legacy_geometry_modules_are_not_runtime_modules(self):
        self.assertFalse(_is_importable("tuba.external.euclid"))
        self.assertFalse(_is_importable("tuba.external.Section.structelem"))
        self.assertFalse(_is_importable("tuba.external.Section.structelem_old"))
        self.assertFalse(_is_importable("tuba.external.UnitCalculator"))


def _is_importable(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


if __name__ == "__main__":
    unittest.main()
