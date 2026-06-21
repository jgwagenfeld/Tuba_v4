import unittest
from pathlib import Path

from tuba.visualization.optional_adapters import (
    adapter_capability_matrix,
    check_optional_adapter,
    get_optional_adapter,
    list_optional_adapters,
)


class TestVisualizationOptionalAdapters(unittest.TestCase):
    def test_registry_lists_future_renderer_boundaries(self):
        adapters = {adapter.adapter_id: adapter for adapter in list_optional_adapters()}

        self.assertEqual(
            set(adapters),
            {"vtkjs_dense", "thatopen_fragments", "xeokit_xkt"},
        )
        self.assertIn("scalar", adapters["vtkjs_dense"].capabilities)
        self.assertIn("IFC context", adapters["thatopen_fragments"].capabilities)
        self.assertIn("XKT", adapters["xeokit_xkt"].artifact_formats)

    def test_missing_optional_adapter_returns_diagnostic_without_import_crash(self):
        status = check_optional_adapter("vtkjs_dense")

        self.assertEqual(status.adapter_id, "vtkjs_dense")
        self.assertFalse(status.available)
        self.assertEqual(status.status, "missing")
        self.assertEqual(status.diagnostics[0]["code"], "visualization.optional_adapter.missing_dependency")
        self.assertIn("optional", status.diagnostics[0]["message"])

    def test_unknown_optional_adapter_returns_clear_diagnostic(self):
        status = check_optional_adapter("unknown_adapter")

        self.assertEqual(status.adapter_id, "unknown_adapter")
        self.assertFalse(status.available)
        self.assertEqual(status.status, "unknown")
        self.assertEqual(status.diagnostics[0]["code"], "visualization.optional_adapter.unknown_adapter")

    def test_capability_matrix_is_serializable_and_documented(self):
        matrix = adapter_capability_matrix()
        docs = Path("docs/visualization_optional_adapters.md").read_text(encoding="utf-8")

        self.assertEqual([row["adapter_id"] for row in matrix], ["vtkjs_dense", "thatopen_fragments", "xeokit_xkt"])
        self.assertEqual(get_optional_adapter("xeokit_xkt").display_name, "xeokit XKT context adapter")
        self.assertIn("| vtk.js dense mesh/scalar |", docs)
        self.assertIn("| That Open Fragments IFC context |", docs)
        self.assertIn("| xeokit XKT context |", docs)
        self.assertIn("optional adapter", docs)


if __name__ == "__main__":
    unittest.main()
