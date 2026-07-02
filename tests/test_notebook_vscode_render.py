import importlib.util
import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("nbclient"), "nbclient is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("nbformat"), "nbformat is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("pyvista"), "pyvista is required for notebook render checks")
class TestVSCodeNotebookRender(unittest.TestCase):
    def test_vscode_static_backend_emits_image_mime_for_result_plot(self):
        import nbformat
        from nbclient import NotebookClient

        code = r'''
import numpy as np
from tuba import Model
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.visualizer.notebook import configure_notebook_backend
from tuba.visualizer import plots

JUPYTER_BACKEND = configure_notebook_backend()
model = Model(project_name="VSCodeRenderSmoke")
model.add_material("Steel", E=2.0e11, nu=0.3)
model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
n0 = model.add_node([0.0, 0.0, 0.0])
n1 = model.add_node([1.0, 0.0, 0.0])
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
model.add_support(node=n0, type="anchor", id="support_anchor_0")

results = FEAResults(solver_name="fixture", load_case="Hot")
results._model = model
results.node_results[n0] = NodeResult(node_id=n0, displacement=np.zeros(6), reaction_force=np.zeros(6))
results.node_results[n1] = NodeResult(node_id=n1, displacement=np.array([0.0, 0.01, 0.0, 0.0, 0.0, 0.0]))
results.element_results["pipe_0"] = ElementResult(
    element_id="pipe_0",
    forces_n1=np.zeros(6),
    forces_n2=np.zeros(6),
    von_mises_n1=1.0,
    von_mises_n2=2.0,
    max_von_mises=2.0,
)

plots.plot_deformed_stress(results, deform_scale=20.0, model=model)
'''
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(code)])

        env = {"TERM_PROGRAM": "vscode", "VSCODE_PID": "12345"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TUBA_NOTEBOOK_BACKEND", None)
            client = NotebookClient(nb, timeout=120, kernel_name="python3", allow_errors=False)
            client.execute()

        mime_types = set()
        for output in nb.cells[0].get("outputs", []):
            mime_types.update((output.get("data") or {}).keys())

        self.assertIn("image/png", mime_types)
        self.assertIn("image/jpeg", mime_types)


if __name__ == "__main__":
    unittest.main()
