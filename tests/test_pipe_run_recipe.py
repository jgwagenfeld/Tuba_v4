import copy
import json
import unittest

import numpy as np

from tuba import Model
from tuba.builder import BuildStep, PipeRunRecipe
from tuba.patches import ModelPatch, ModelTransaction


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


class TestRememberedPipeRuns(unittest.TestCase):
    def test_a_pipe_block_remembers_its_steps_the_records_they_created_and_where_it_began(self):
        model = _model("remembered")
        model.add_node([9.0, 9.0, 9.0])
        with model.pipe("DN100", "steel", route="P-100") as b:
            b.start([0.0, 0.0, 0.0], support="anchor")
            b.run(2.0)
            b.bend(radius=0.15, angle=90, plane="XY")
            b.add_support(type="guide")
            b.run(3.0)

        [run] = model.pipe_runs
        self.assertEqual(run.offsets, (1, 0, 0))
        self.assertEqual(run.node_ids, ["N1", "N2", "N3", "N4"])
        self.assertEqual(run.element_ids, ["pipe_str_0", "pipe_bend_0", "pipe_str_1"])
        self.assertEqual(run.support_ids, ["support_0", "support_1"])
        self.assertEqual([step.op for step in run.recipe.steps], ["start", "run", "bend", "add_support", "run"])
        self.assertEqual((run.recipe.section, run.recipe.material, run.recipe.route_id), ("DN100", "steel", "P-100"))

    def test_a_model_call_inside_the_block_is_not_part_of_the_run(self):
        model = _model("foreign")
        with model.pipe("DN100", "steel") as b:
            b.start([0.0, 0.0, 0.0])
            b.run(2.0)
            model.add_support(b.last_node_id, "anchor")
            b.run(1.0)

        [run] = model.pipe_runs
        self.assertEqual(run.node_ids, ["N0", "N1", "N2"])
        self.assertEqual(run.support_ids, [])
        self.assertEqual([support.id for support in model.supports], ["support_0"])

    def test_a_recipe_build_remembers_the_run_it_returns(self):
        model = _model("built")
        recipe = PipeRunRecipe(
            section="DN100",
            material="steel",
            steps=[
                BuildStep(op="start", params={"point": [0.0, 0.0, 0.0], "support": "anchor"}),
                BuildStep(op="run", params={"length": 2.0}),
            ],
        )

        built = recipe.build(model)

        self.assertEqual(model.pipe_runs, [built])
        self.assertEqual(
            (built.node_ids, built.element_ids, built.support_ids), (["N0", "N1"], ["pipe_str_0"], ["support_0"])
        )
        self.assertEqual(built.recipe.steps, recipe.steps)
        self.assertEqual(built.offsets, (0, 0, 0))

    def test_a_block_that_creates_nothing_is_not_remembered(self):
        model = _model("nothing")
        model.add_node([0.0, 0.0, 0.0])
        with model.pipe("DN100", "steel") as b:
            b.start([0.0, 0.0, 0.0])  # snaps onto the existing node

        self.assertEqual(model.pipe_runs, [])

    def test_copies_and_patches_keep_the_runs_and_the_model_json_never_carries_them(self):
        model = _model("kept")
        _authored_run(model)
        patch = ModelPatch.from_dict(
            {
                "operations": [{"op": "add_node", "local_id": "extra", "coords": [9.0, 0.0, 0.0]}],
                "provenance": {"source": "test"},
            }
        )
        ModelTransaction(model).apply(patch, validate=False)

        self.assertEqual(len(model.pipe_runs), 1)
        self.assertEqual(copy.deepcopy(model).pipe_runs, model.pipe_runs)
        self.assertNotIn("pipe_runs", json.dumps(model.to_dict()))
        self.assertEqual(Model.from_dict(model.to_dict()).pipe_runs, [])


if __name__ == "__main__":
    unittest.main()
