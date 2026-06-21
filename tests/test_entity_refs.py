import unittest

from tuba import Model
from tuba.refs import EntityRef, resolve_entity_ref


class TestEntityRef(unittest.TestCase):
    def test_entity_ref_parses_and_formats_known_targets(self):
        ref = EntityRef.parse("element:pipe_str_0")

        self.assertEqual(ref.kind, "element")
        self.assertEqual(ref.id, "pipe_str_0")
        self.assertEqual(str(ref), "element:pipe_str_0")
        self.assertEqual(ref.to_dict(), {"kind": "element", "id": "pipe_str_0"})
        self.assertEqual(EntityRef.from_dict(ref.to_dict()), ref)

    def test_entity_ref_rejects_invalid_text(self):
        with self.assertRaises(ValueError):
            EntityRef.parse("pipe_str_0")

        with self.assertRaises(ValueError):
            EntityRef.parse("unknown:thing")

        with self.assertRaises(ValueError):
            EntityRef.parse("element:")

    def test_model_entities_resolve_from_refs(self):
        model = Model("EntityRefs")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n1 = model.add_node([0.0, 0.0, 0.0])
        n2 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(
            id="pipe_str_0",
            type="pipe_straight",
            n1=n1,
            n2=n2,
            section="PipeSec",
            material="Steel",
        )
        support = model.add_support(n1, "anchor")
        obstacle = model.add_obstacle(
            id="equipment_box",
            type="cuboid",
            min_point=[2.0, -0.5, -0.5],
            max_point=[3.0, 0.5, 0.5],
        )
        model.groups["rack_A"] = {"name": "rack_A", "elements": [elem.id]}

        self.assertIs(resolve_entity_ref(model, EntityRef("element", elem.id)), elem)
        self.assertIs(resolve_entity_ref(model, EntityRef("support", support.id)), support)
        self.assertIs(resolve_entity_ref(model, EntityRef("obstacle", "equipment_box")), obstacle)
        self.assertIs(resolve_entity_ref(model, EntityRef("group", "rack_A")), model.groups["rack_A"])

    def test_support_ids_roundtrip_through_model_dict(self):
        model = Model("SupportRefs")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        node = model.add_node([0.0, 0.0, 0.0])

        first = model.add_support(node, "anchor")
        second = model.add_support(node, "rest")

        self.assertEqual(first.id, "support_0")
        self.assertEqual(second.id, "support_1")

        loaded = Model.from_dict(model.to_dict())
        self.assertEqual([support.id for support in loaded.supports], ["support_0", "support_1"])
        third = loaded.add_support(node, "guide")
        self.assertEqual(third.id, "support_2")


if __name__ == "__main__":
    unittest.main()
