import unittest

from tuba import Model
from tuba.visualization import build_visualization_scene


class TestVisualizationIfc(unittest.TestCase):
    def _model(self):
        model = Model(project_name="IfcScene")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05)
        model.assign_insulation(f"element:{elem.id}", "mw_50")
        model.assign_attribute(f"element:{elem.id}", "ifc.type", "IfcPipeSegment")
        return model

    def test_scene_object_carries_ifc_guid_and_property_set_mapping(self):
        scene = build_visualization_scene(
            self._model(),
            ifc_guid_map={"element:pipe_0": "2Y$TubaGuid0000000001"},
            ifc_context={"file": "plant.ifc", "schema": "IFC4"},
            scene_id="scene_ifc",
        )

        pipe = next(obj for obj in scene.objects if obj.entity_ref and str(obj.entity_ref) == "element:pipe_0")
        self.assertEqual(pipe.source["ifc"]["guid"], "2Y$TubaGuid0000000001")
        self.assertEqual(pipe.source["ifc"]["type"], "IfcPipeSegment")
        self.assertEqual(pipe.source["ifc"]["property_sets"]["Pset_TubaIdentity"]["EntityRef"], "element:pipe_0")
        self.assertEqual(pipe.source["ifc"]["property_sets"]["Pset_TubaInsulation"]["InsulationSpec"], "mw_50")
        self.assertEqual(scene.extra["ifc_context"], {"file": "plant.ifc", "schema": "IFC4"})

    def test_scene_build_does_not_require_ifc_mapping(self):
        scene = build_visualization_scene(self._model(), scene_id="scene_ifc_native")

        pipe = next(obj for obj in scene.objects if obj.entity_ref and str(obj.entity_ref) == "element:pipe_0")
        self.assertEqual(pipe.entity_ref.id, "pipe_0")
        self.assertNotIn("ifc", pipe.source)


if __name__ == "__main__":
    unittest.main()
