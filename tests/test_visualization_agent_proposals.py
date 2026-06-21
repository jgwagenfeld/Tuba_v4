import unittest

from tuba import Model
from tuba.patches import AddElement, AddNode, ModelPatch
from tuba.visualization import build_visualization_scene


class TestVisualizationAgentProposals(unittest.TestCase):
    def _model(self):
        model = Model(project_name="ProposalReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def _patch(self):
        return ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(2.0, 0.0, 0.0)),
                AddElement(
                    local_id="pipe",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
            ],
            provenance={"source": "agent"},
        )

    def test_agent_patch_preview_adds_proposal_diff_without_mutating_model(self):
        model = self._model()
        patch = self._patch()

        scene = build_visualization_scene(
            model,
            agent_proposals=[
                {
                    "proposal_id": "proposal_001",
                    "agent_id": "agent_route",
                    "goal": "add pipe",
                    "rationale": "connect the two endpoints",
                    "model_patch": patch,
                }
            ],
            scene_id="scene_agent_review",
        )
        scene.validate()

        self.assertEqual(model.nodes, {})
        self.assertEqual(model.elements, [])

        proposal = scene.agent_proposals[0]
        self.assertEqual(proposal.proposal_id, "proposal_001")
        self.assertEqual(proposal.approval_state, "pending")
        self.assertEqual([str(ref) for ref in proposal.created_entity_refs], ["element:pipe_str_0"])
        self.assertEqual(proposal.model_patch["operations"][2]["op"], "add_element")

        diff = scene.scene_diffs[0]
        self.assertEqual(diff.diff_id, "diff:proposal:proposal_001")
        self.assertEqual(diff.added_objects[0].kind, "proposal_added")
        self.assertEqual(diff.added_geometry_assets[0].generation_config["points"], [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "agent_proposal")
        self.assertEqual(overlay.data["proposal_id"], "proposal_001")
        self.assertEqual(overlay.object_ids, [diff.added_objects[0].id])


if __name__ == "__main__":
    unittest.main()
