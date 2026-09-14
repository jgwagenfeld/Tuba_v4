import unittest
from unittest.mock import Mock, patch


class TestNotebookBackendSelection(unittest.TestCase):
    def test_defaults_to_zoomable_embedded_html_backend(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "html")

    def test_environment_override_wins(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "static"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_environment_can_select_client_backend(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "client"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "client")

    def test_ci_defaults_to_static_backend(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_vscode_defaults_to_interactive_html_backend(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict(
            "os.environ",
            {"TERM_PROGRAM": "vscode", "VSCODE_PID": "123"},
            clear=True,
        ):
            self.assertEqual(resolve_notebook_backend(), "html")

    def test_ci_wins_over_vscode(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict(
            "os.environ",
            {"CI": "true", "TERM_PROGRAM": "vscode", "VSCODE_PID": "123"},
            clear=True,
        ):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_static_override_forces_static_in_vscode(self):
        from tuba.plotting.notebook import resolve_notebook_backend

        with patch.dict(
            "os.environ",
            {"TUBA_NOTEBOOK_STATIC": "1", "TERM_PROGRAM": "vscode"},
            clear=True,
        ):
            self.assertEqual(resolve_notebook_backend(), "static")

    def test_configure_applies_selected_backend(self):
        from tuba.plotting.notebook import configure_notebook_backend

        fake_pyvista = Mock()
        with patch.dict("os.environ", {"TUBA_NOTEBOOK_BACKEND": "client"}, clear=True):
            selected = configure_notebook_backend(pyvista_module=fake_pyvista)

        self.assertEqual(selected, "client")
        fake_pyvista.set_jupyter_backend.assert_called_once_with("client")

    def test_result_plot_passes_show_kwargs(self):
        from tuba.plotting.plots import plot_deformed_stress
        from tuba.solver.base import FEAResults

        fake_plotter = Mock()
        fake_plotter.show.return_value = "shown"

        with (
            patch("tuba.plotting.plots._require_pyvista"),
            patch("tuba.plotting.scenes.build_model_scene", return_value=fake_plotter),
        ):
            returned = plot_deformed_stress(
                FEAResults(solver_name="fixture", result_file=None),
                model=Mock(),
                jupyter_backend="html",
            )

        self.assertEqual(returned, "shown")
        fake_plotter.show.assert_called_once_with(jupyter_backend="html")


if __name__ == "__main__":
    unittest.main()
