"""Contact authoring data survives recipes, schemas, patches and placement."""
import json
import unittest

import numpy as np

from tuba import Model
from tuba.builder import PipeRunRecipe
from tuba.coordinates import CoordinateSystem
from tuba.fragments import ModelFragment, build_fragment_patch, place_fragment
from tuba.patches import ModelPatch, ModelTransaction
from tuba.schema import validate_model_dict, validate_patch_dict
from tuba.solver.aster_contact import shoes


class ContactAuthoringRoundTrip(unittest.TestCase):
    def test_nondefault_contact_fields_survive_all_authoring_paths(self):
        settings = dict(friction_coefficient=.42, gap=.0013,
                        normal_stiffness=8.7e9, tangential_stiffness=3.4e7)
        placement = CoordinateSystem(origin=(10.,20.,30.), x_axis=(0.,1.,0.),
                                     y_axis=(-1.,0.,0.), z_axis=(0.,0.,1.))
        def model():
            result = Model('Contact authoring')
            result.add_material('steel',E=2e11,nu=.3)
            result.add_pipe_section('pipe',OD=.1143,WT=.006)
            return result
        def check(support):
            for key,value in settings.items():
                self.assertEqual(getattr(support,key),value)
        for direction in (None,[1.,0.,0.]):
            with self.subTest(direction=direction):
                authored = model()
                with authored.pipe('pipe','steel') as builder:
                    builder.start([0.,0.,0.],support='anchor').run(2.)
                    builder.add_support('rest',direction=direction,**settings)
                recipe_data = json.loads(json.dumps(builder.recipe.to_dict()))
                recorded = next(step['params'] for step in recipe_data['steps'] if step['op']=='add_support')
                self.assertEqual({key:recorded[key] for key in settings},settings)
                replay = model()
                PipeRunRecipe.from_dict(recipe_data).build(replay)
                check(replay.supports[-1])
                data = json.loads(json.dumps(replay.to_dict()))
                validate_model_dict(data)
                restored = Model.from_dict(data)
                check(restored.supports[-1])
                fragment = ModelFragment.from_dict(ModelFragment('shoe fragment',restored).to_dict())
                patch_data = json.loads(json.dumps(build_fragment_patch(fragment,CoordinateSystem.identity(),name='patch').to_dict()))
                validate_patch_dict(patch_data)
                patched = model()
                ModelTransaction(patched).apply(ModelPatch.from_dict(patch_data))
                check(patched.supports[-1])
                placed = Model('Placed contact')
                place_fragment(placed,fragment,placement,name='rotated')
                check(placed.supports[-1])
                expected_normal = placement.to_global_vector(direction if direction is not None else [0.,0.,1.])
                np.testing.assert_allclose(shoes(placed,'POU_D_T')[0].normal,expected_normal)
                self.assertIsNone(placed.supports[0].direction)
                self.assertEqual(fragment.model.supports[-1].direction,direction)


if __name__ == '__main__':
    unittest.main()
