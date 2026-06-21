import unittest

from tuba import Model
from tuba.patches import (
    AddElement,
    AddInsulationSpec,
    AddNode,
    AddSupport,
    AssignAttribute,
    CreateGroup,
    ModelPatch,
    ModelTransaction,
)
from tuba.schema import validate_patch_dict


class TestModelPatch(unittest.TestCase):
    def test_patch_applies_nodes_elements_and_supports(self):
        model = Model(project_name="Patch")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="e0",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                AddSupport(node="a", type="anchor"),
            ]
        )

        result = ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 2)
        self.assertEqual(len(model.elements), 1)
        self.assertEqual(len(model.supports), 1)
        self.assertIn("a", result.node_ids)
        self.assertIn("e0", result.element_ids)

    def test_patch_rolls_back_on_invalid_element_reference(self):
        model = Model(project_name="Rollback")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddElement(
                    local_id="bad",
                    type="pipe_straight",
                    n1="a",
                    n2="missing",
                    section="PipeSec",
                    material="Steel",
                ),
            ]
        )

        with self.assertRaises(ValueError):
            ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)

    def test_unknown_element_type_is_rejected_and_rolls_back(self):
        model = Model(project_name="UnknownElement")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="bad",
                    type="mystery",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
            ]
        )

        with self.assertRaises(ValueError) as ctx:
            ModelTransaction(model).apply(patch)

        self.assertIn("Unknown element type", str(ctx.exception))
        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)

    def test_reuse_existing_false_creates_distinct_node_at_same_point(self):
        model = Model(project_name="ReusePolicy")
        existing = model.add_node((0.0, 0.0, 0.0))
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0), reuse_existing=False),
            ]
        )

        result = ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 2)
        self.assertNotEqual(result.node_ids["a"], existing)

    def test_patch_serializes_to_agent_payload_and_roundtrips(self):
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="e0",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                AddSupport(node="a", type="anchor"),
            ],
            provenance={"source": "agent"},
        )

        data = patch.to_dict()
        validate_patch_dict(data)
        restored = ModelPatch.from_dict(data)

        self.assertEqual(data["operations"][0]["op"], "add_node")
        self.assertEqual(data["operations"][2]["op"], "add_element")
        self.assertEqual(restored.provenance["source"], "agent")
        self.assertEqual(len(restored.operations), 4)

    def test_patch_can_add_semantic_spec_and_assign_to_generated_element(self):
        model = Model(project_name="SemanticPatch")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="pipe",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                AddInsulationSpec(
                    id="mw_50",
                    material="mineral_wool",
                    thickness_m=0.05,
                    density_kg_m3=120.0,
                    cost_per_m=18.5,
                ),
                AssignAttribute(target="element:pipe", key="insulation", value="mw_50"),
            ],
            provenance={"source": "agent"},
        )

        data = patch.to_dict()
        validate_patch_dict(data)
        restored = ModelPatch.from_dict(data)
        result = ModelTransaction(model).apply(restored)
        actual_element_id = result.element_ids["pipe"]

        self.assertEqual(model.get_insulation(f"element:{actual_element_id}").thickness_m, 0.05)
        self.assertEqual(result.spec_count, 1)
        self.assertEqual(result.attribute_count, 1)

    def test_patch_can_create_group_from_generated_ids_and_assign_defaults(self):
        model = Model(project_name="GroupPatch")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="pipe",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                CreateGroup(name="rack_A", elements=["pipe"], metadata={"revision": "A"}),
                AddInsulationSpec(id="mw_30", material="mineral_wool", thickness_m=0.03),
                AssignAttribute(target="group:rack_A", key="insulation", value="mw_30"),
            ]
        )

        result = ModelTransaction(model).apply(patch)
        actual_element_id = result.element_ids["pipe"]

        self.assertEqual(model.groups["rack_A"]["elements"], [actual_element_id])
        self.assertEqual(model.groups["rack_A"]["metadata"], {"revision": "A"})
        self.assertEqual(model.get_insulation(f"element:{actual_element_id}").id, "mw_30")
        self.assertEqual(result.group_names, ["rack_A"])

    def test_patch_rolls_back_on_invalid_semantic_assignment(self):
        model = Model(project_name="SemanticRollback")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        patch = ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(
                    local_id="pipe",
                    type="pipe_straight",
                    n1="a",
                    n2="b",
                    section="PipeSec",
                    material="Steel",
                ),
                AssignAttribute(target="element:pipe", key="insulation", value="missing_spec"),
            ]
        )

        with self.assertRaises(ValueError):
            ModelTransaction(model).apply(patch)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)
        self.assertEqual(model.attributes, [])


if __name__ == "__main__":
    unittest.main()
