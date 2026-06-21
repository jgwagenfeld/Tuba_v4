import unittest

from tuba import Model
from tuba.visualization import build_visualization_scene


class TestVisualizationFederation(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Federation")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return model

    def test_external_source_objects_are_loaded_with_transform_and_metadata(self):
        scene = build_visualization_scene(
            self._model(),
            external_sources=[
                {
                    "source_id": "ifc_context",
                    "source_type": "ifc",
                    "transform": {"translation": [10.0, 0.0, 0.0]},
                    "objects": [
                        {
                            "id": "pump_1",
                            "name": "Pump 1",
                            "kind": "equipment",
                            "bounds": [0.0, -1.0, 0.0, 2.0, 1.0, 2.0],
                            "metadata": {"ifc_guid": "3IfcPumpGuid000000001"},
                        }
                    ],
                }
            ],
            scene_id="scene_federation",
        )
        scene.validate()

        external = next(obj for obj in scene.objects if obj.kind == "external_context")
        self.assertEqual(external.id, "object:external:ifc_context:pump_1")
        self.assertEqual(external.source["external"]["source_id"], "ifc_context")
        self.assertEqual(external.metadata["ifc_guid"], "3IfcPumpGuid000000001")

        asset = next(asset for asset in scene.geometry_assets if asset.id == external.geometry_asset_id)
        self.assertEqual(asset.bounds, [10.0, -1.0, 0.0, 12.0, 1.0, 2.0])

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "external_source")
        self.assertEqual(overlay.object_ids, [external.id])
        self.assertEqual(overlay.data["source_id"], "ifc_context")
        self.assertEqual(overlay.data["transform"], {"translation": [10.0, 0.0, 0.0]})


if __name__ == "__main__":
    unittest.main()
