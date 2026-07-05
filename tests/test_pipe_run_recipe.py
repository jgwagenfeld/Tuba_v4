import unittest

import numpy as np

from tuba import Model, PipeRunRecipe


def _model(name: str) -> Model:
    model = Model(project_name=name)
    model.add_material("steel", E=210e9, nu=0.3)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    return model


def _authored_run(model: Model):
    with model.pipe("DN100", "steel") as b:
        b.start([0.0, 0.0, 0.0], support="anchor")
        b.run(2.0)
        b.bend(radius=0.15, angle=90, plane="XY")
        b.run(3.0)
        b.end(support="anchor")
    return b


class TestPipeRunRecipe(unittest.TestCase):
    def test_recipe_replays_to_identical_geometry(self):
        original = _model("original")
        b = _authored_run(original)
        recipe = b.recipe

        # steps recorded: start, run, bend, run, end
        self.assertEqual([s.op for s in recipe.steps], ["start", "run", "bend", "run", "end"])

        regen = _model("regen")
        built = recipe.build(regen)

        # Same element count, and the end node lands at the same hand-computed point.
        self.assertEqual(len(built.element_ids), len(list(original.elements)))
        self.assertEqual(len(built.element_ids), 3)
        end_coords = regen.nodes[built.node_ids[-1]].coords
        self.assertTrue(np.allclose(end_coords, [2.15, 3.15, 0.0]))
        # Anchor supports replayed too (start + end nodes).
        self.assertEqual(len(list(regen.supports)), 2)

    def test_recipe_regenerates_with_changed_length(self):
        recipe = _authored_run(_model("original")).recipe

        # step index 1 is the first run(2.0); lengthen it to 5.0 and rebuild.
        longer = recipe.with_step_params(1, length=5.0)
        regen = _model("regen")
        built = longer.build(regen)

        end_coords = regen.nodes[built.node_ids[-1]].coords
        self.assertTrue(np.allclose(end_coords, [5.15, 3.15, 0.0]))
        # Original recipe is untouched (functional override).
        self.assertEqual(recipe.steps[1].params["length"], 2.0)

    def test_recipe_json_round_trip_regenerates_identically(self):
        recipe = _authored_run(_model("original")).recipe
        restored = PipeRunRecipe.from_dict(recipe.to_dict())

        self.assertEqual(restored.to_dict(), recipe.to_dict())

        a, b = _model("a"), _model("b")
        recipe.build(a)
        restored.build(b)
        a_coords = sorted(tuple(np.round(n.coords, 6)) for n in a.nodes.values())
        b_coords = sorted(tuple(np.round(n.coords, 6)) for n in b.nodes.values())
        self.assertEqual(a_coords, b_coords)

    def test_recipe_preserves_route_id_on_replay(self):
        original = _model("route-original")
        with original.pipe("DN100", "steel", route="P-100") as builder:
            builder.start([0.0, 0.0, 0.0])
            builder.run(2.0)
        recipe = PipeRunRecipe.from_dict(builder.recipe.to_dict())

        regen = _model("route-regen")
        built = recipe.build(regen)

        self.assertEqual(recipe.route_id, "P-100")
        self.assertEqual(regen.get_element(built.element_ids[0]).route_id, "P-100")
        self.assertAlmostEqual(regen.get_element(built.element_ids[0]).station_start, 0.0)
        self.assertAlmostEqual(regen.get_element(built.element_ids[0]).station_end, 2.0)


if __name__ == "__main__":
    unittest.main()
