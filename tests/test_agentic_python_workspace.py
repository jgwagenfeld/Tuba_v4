import unittest

from tuba import Model
from tuba.visualization.agent_workspace import AgenticPythonWorkspace


class TestAgenticPythonWorkspace(unittest.TestCase):
    def _model(self):
        model = Model(project_name="AgentWorkspace")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def test_cells_share_persistent_variables_and_capture_stdout(self):
        workspace = AgenticPythonWorkspace(self._model(), agent_id="agent_a", goal="test")

        first = workspace.execute_cell("x = 41\nprint('ready')")
        second = workspace.execute_cell("y = x + 1")

        self.assertEqual(first.stdout.strip(), "ready")
        self.assertEqual(second.variables["y"]["repr"], "42")
        self.assertEqual(len(workspace.session.cells), 2)

    def test_unsafe_operations_are_blocked_without_execution(self):
        workspace = AgenticPythonWorkspace(self._model(), agent_id="agent_a", goal="test")

        result = workspace.execute_cell("open('bad.txt', 'w')")

        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0]["code"], "agent_workspace.unsafe_code")

    def test_workspace_final_proposal_contains_patch_trace_and_preview(self):
        model = self._model()
        workspace = AgenticPythonWorkspace(model, agent_id="agent_route", goal="add pipe")

        workspace.execute_cell(
            "patch = ModelPatch(operations=[\n"
            "    AddNode(local_id='a', coords=(0, 0, 0)),\n"
            "    AddNode(local_id='b', coords=(1, 0, 0)),\n"
            "    AddElement(local_id='pipe', type='pipe_straight', n1='a', n2='b', section='PipeSec', material='Steel'),\n"
            "])"
        )
        proposal = workspace.finalize_proposal("patch", rationale="simple connection")

        self.assertEqual(model.elements, [])
        self.assertEqual(proposal.agent_id, "agent_route")
        self.assertEqual(proposal.model_patch["operations"][2]["op"], "add_element")
        self.assertEqual(proposal.extra["execution_trace"][0]["ok"], True)
        self.assertEqual(proposal.extra["preview"]["type"], "scene_diff")


if __name__ == "__main__":
    unittest.main()
