"""Supports: the closed type list and attachment to another node."""
import unittest

from tuba import Model
from tuba.model import SUPPORT_TYPES
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project.script import generate_model_script
from tuba.validation import ModelValidationError


def cantilever():
    """A 6 m DN100 pipe along X with its two end nodes."""
    model = Model("Attach")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    root = model.add_node([0.0, 0.0, 0.0])
    tip = model.add_node([6.0, 0.0, 0.0])
    model.add_element(id="pipe", type="pipe_straight", n1=root, n2=tip, section="DN100", material="Steel")
    return model, root, tip


class SupportTypes(unittest.TestCase):
    def test_documented_types_are_accepted(self):
        self.assertEqual(SUPPORT_TYPES, ("anchor", "guide", "rest", "spring", "hanger", "custom"))
        model, _root, tip = cantilever()
        for kind in SUPPORT_TYPES:
            model.add_support(tip, kind)

    def test_unknown_type_is_refused_with_the_valid_types(self):
        model, _root, tip = cantilever()
        with self.assertRaisesRegex(
            ValueError, "Unknown support type 'sliding'; use one of anchor, guide, rest, spring, hanger, custom"
        ):
            model.add_support(tip, "sliding")


class SupportAttachment(unittest.TestCase):
    def test_attachment_round_trips_through_dict_script_and_patch(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "rest", attached_to=rack, id="shoe")
        self.assertEqual(Model.from_dict(model.to_dict()).supports[-1].attached_to, rack)
        self.assertIn(f"attached_to={rack!r}", generate_model_script(model))

        patched, _root, tip = cantilever()
        result = ModelTransaction(patched).apply(ModelPatch.from_dict({"operations": [
            {"op": "add_node", "local_id": "rack", "coords": [6.0, 0.0, -0.25]},
            {"op": "add_support", "node": tip, "type": "rest", "attached_to": "rack"},
        ]}))
        self.assertEqual(patched.supports[-1].attached_to, result.node_ids["rack"])

    def test_builder_carries_the_attachment(self):
        model, _root, _tip = cantilever()
        rack = model.add_node([0.0, 3.0, -0.25])
        with model.pipe(section="DN100", material="Steel") as builder:
            builder.start([0.0, 3.0, 0.0])
            builder.add_support("rest", attached_to=rack)
        self.assertEqual(model.supports[-1].attached_to, rack)

    def test_attachment_must_name_another_existing_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to="N99", id="lost")
        with self.assertRaisesRegex(ModelValidationError, "Support 'lost' is attached to missing node 'N99'"):
            model.validate()

    def test_a_support_cannot_attach_to_its_own_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to=tip, id="self")
        with self.assertRaisesRegex(ModelValidationError, "Support 'self' is attached to its own node"):
            model.validate()

    def test_attached_support_cannot_impose_a_displacement(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "anchor", attached_to=rack, imposed_displacement=[0.0, 0.0, 0.01], id="moved")
        with self.assertRaisesRegex(ModelValidationError, "Support 'moved' is attached to a node, so it cannot impose a displacement"):
            model.validate()


if __name__ == "__main__":
    unittest.main()
