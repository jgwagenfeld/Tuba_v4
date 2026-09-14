import importlib.util
import os
import unittest


@unittest.skipUnless(importlib.util.find_spec("nbclient"), "nbclient is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("nbformat"), "nbformat is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("pyvista"), "pyvista is required for notebook render checks")
class TestVSCodeNotebookRender(unittest.TestCase):
    def test_vscode_emits_interactive_widget_for_result_plot(self):
        import nbformat
        from nbclient import NotebookClient

        code = r'''
import numpy as np
from tuba import Model
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.plotting.notebook import configure_notebook_backend
from tuba.plotting import plots

JUPYTER_BACKEND = configure_notebook_backend()
model = Model(project_name="VSCodeRenderSmoke")
model.add_material("Steel", E=2.0e11, nu=0.3)
model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
n0 = model.add_node([0.0, 0.0, 0.0])
n1 = model.add_node([1.0, 0.0, 0.0])
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
model.add_support(node=n0, type="anchor", id="support_anchor_0")
model.define_load_case("Hot", temperature=20.0, ref_temperature=20.0)

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

        client = NotebookClient(nb, timeout=120, kernel_name="python3", allow_errors=False)
        client.execute(cwd=os.getcwd(), env=_isolated_notebook_env())

        all_mimes: set[str] = set()
        widget_mimes: list[str] = []
        iframe_repr = False
        for output in nb.cells[0].get("outputs", []):
            data = output.get("data") or {}
            all_mimes.update(data)
            widget_mimes += [m for m in data if m.startswith("application/vnd.jupyter.widget")]
            text = _payload_text(data.get("text/plain", ""))
            if "srcdoc" in text or "iframe" in text:
                iframe_repr = True

        self.assertTrue(
            widget_mimes,
            "expected an interactive PyVista widget-view output in VS Code",
        )
        self.assertTrue(
            iframe_repr,
            "expected the self-contained iframe scene repr from the html backend",
        )
        self.assertNotIn(
            "image/png",
            all_mimes,
            "VS Code should render the interactive html scene, not a static image",
        )


def _isolated_notebook_env() -> dict[str, str]:
    allowed_keys = (
        "APPDATA",
        "COMSPEC",
        "DISPLAY",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "PATH",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "PROGRAMDATA",
        "PYTHONHOME",
        "PYTHONPATH",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
        "XAUTHORITY",
    )
    env = {key: os.environ[key] for key in allowed_keys if key in os.environ}
    env["TERM_PROGRAM"] = "vscode"
    env["VSCODE_PID"] = "12345"
    return env


def _payload_text(payload: object) -> str:
    if isinstance(payload, list):
        return "".join(str(part) for part in payload)
    return str(payload)


if __name__ == "__main__":
    unittest.main()
