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

    def test_pipe_nominal_sizes_and_schedules_have_explicit_valid_dimensions(self):
        catalog = SectionCatalog.default()
        profiles = catalog.list_pipe_profiles()
        self.assertEqual(len(profiles), 226)
        self.assertEqual(len({row.dn for row in profiles}), 31)
        pipe = catalog.get_pipe_profile("DN100_SCH40")
        self.assertEqual((pipe.dn, pipe.nps, pipe.OD, pipe.WT), (100, "4", 0.1143, 0.00602))
        self.assertEqual(catalog.get_pipe_profile("DN6_SCH80").WT, 0.00241)
        self.assertEqual(catalog.get_pipe_profile("DN150_SCH40").WT, 0.00711)
        self.assertEqual(catalog.get_pipe_profile("DN200_SCH40").WT, 0.00818)
        self.assertEqual(catalog.get_pipe_profile("DN300_STD").WT, 0.00953)
        self.assertEqual(catalog.get_pipe_profile("DN300_SCH40").WT, 0.01031)
        self.assertEqual(catalog.get_pipe_profile("DN250_XS").WT, 0.0127)
        self.assertEqual(catalog.get_pipe_profile("DN250_SCH80").WT, 0.01509)
        self.assertEqual(catalog.get_pipe_profile("DN1050_STD").OD, 1.067)
        self.assertTrue(all(0 < 2 * row.WT < row.OD for row in profiles))
        with self.assertRaisesRegex(ValueError, "Pipe profile"):
            catalog.get_pipe_profile("DN550_SCH40")  # No published value in the source chart.
        with self.assertRaisesRegex(ValueError, "Pipe profile"):
            catalog.get_pipe_profile("DN100")  # DN alone does not define a wall thickness.

    def test_pipe_catalog_rejects_invalid_or_duplicate_rows(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "Pipe.input"
            for row in ("100,4,nan,6.02", "100,4,114.3,-1", "100,4,114.3,60", "100,4,114.3,inf"):
                path.write_text("DN,NPS,OD,40\n" + row + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Invalid pipe dimensions"):
                    SectionCatalog(Path(directory)).list_pipe_profiles()
            path.write_text("DN,NPS,OD,40\n100,4,114.3,6.02\n100,4,114.3,6.02\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate pipe profile"):
                SectionCatalog(Path(directory)).list_pipe_profiles()

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
