import unittest
from unittest.mock import Mock, patch


class TestNotebookBackendSelection(unittest.TestCase):
    def test_defaults_to_zoomable_embedded_html_backend(self):
        from tuba.visualizer.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "html")

    def test_environment_override_wins(self):
        from tuba.visualizer.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "static"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_environment_can_select_client_backend(self):
        from tuba.visualizer.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "client"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "client")

    def test_ci_defaults_to_static_backend(self):
        from tuba.visualizer.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_vscode_defaults_to_static_backend(self):
        from tuba.visualizer.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"VSCODE_PID": "123"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_configure_applies_selected_backend(self):
        from tuba.visualizer.notebook import configure_notebook_backend

        fake_pyvista = Mock()
        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "client"}, clear=True):
            selected = configure_notebook_backend(pyvista_module=fake_pyvista)

        self.assertEqual(selected, "client")
        fake_pyvista.set_jupyter_backend.assert_called_once_with("client")


if __name__ == "__main__":
    unittest.main()
