import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestAdapyAlignmentPolicy(unittest.TestCase):
    def test_policy_document_records_reference_only_boundary(self):
        text = (ROOT / "docs" / "architecture" / "adapy-alignment.md").read_text(encoding="utf-8")
        self.assertIn("Do not vendor adapy code", text)
        self.assertIn("GPL-3.0-or-later", text)
        self.assertIn("reference-only interoperability input", text)
        self.assertIn("No runtime ada-py bridge ships in Tuba core", text)

    def test_core_package_does_not_ship_adapy_bridge(self):
        self.assertFalse((ROOT / "tuba" / "external" / "adapy_bridge.py").exists())

    def test_core_dependencies_do_not_require_adapy(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dependencies_block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("ada-py", dependencies_block)
        self.assertNotIn('"ada"', dependencies_block)
