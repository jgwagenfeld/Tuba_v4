"""Supports: the closed type list and attachment to another node."""
import unittest

from tuba import Model
from tuba.model import SUPPORT_TYPES


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


if __name__ == "__main__":
    unittest.main()
