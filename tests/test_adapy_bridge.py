import unittest

from tuba import Model
from tuba.external.adapy_bridge import adapy_available, require_adapy, tuba_to_adapy


class TestAdapyBridge(unittest.TestCase):
    def test_require_adapy_reports_optional_dependency_when_missing(self):
        if adapy_available():
            self.skipTest("ada is installed in this environment")
        with self.assertRaisesRegex(ImportError, "optional adapy bridge"):
            require_adapy()

    def test_tuba_to_adapy_requires_adapy(self):
        if adapy_available():
            self.skipTest("covered by integration test when ada is installed")
        model = Model("Bridge")
        with self.assertRaisesRegex(ImportError, "optional adapy bridge"):
            tuba_to_adapy(model)
