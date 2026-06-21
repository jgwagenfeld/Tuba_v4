import unittest

from tuba import Model
from tuba.visualization import build_visualization_scene


class TestVisualizationPointCloud(unittest.TestCase):
    def test_point_cloud_and_field_note_descriptors_are_scene_objects(self):
        model = Model(project_name="PointCloudReview")

        scene = build_visualization_scene(
            model,
            point_clouds=[
                {
                    "id": "scan_001",
                    "uri": "scans/scan_001.las",
                    "bounds": [0.0, 0.0, 0.0, 10.0, 5.0, 3.0],
                    "point_count": 1200,
                    "source": {"scanner": "BLK", "date": "2026-06-20"},
                }
            ],
            field_notes=[
                {
                    "id": "note_001",
                    "text": "Verify pipe clearance in field",
                    "position": [1.0, 2.0, 0.5],
                    "entity_refs": ["point_cloud:scan_001"],
                }
            ],
            scene_id="scene_point_cloud",
        )
        scene.validate()

        point_cloud = next(obj for obj in scene.objects if obj.kind == "point_cloud")
        self.assertEqual(point_cloud.id, "object:point_cloud:scan_001")
        self.assertEqual(point_cloud.metadata["point_count"], 1200)
        asset = next(asset for asset in scene.geometry_assets if asset.id == point_cloud.geometry_asset_id)
        self.assertEqual(asset.format, "point_cloud")
        self.assertEqual(asset.uri, "scans/scan_001.las")

        note = next(obj for obj in scene.objects if obj.kind == "field_note")
        self.assertEqual(note.metadata["text"], "Verify pipe clearance in field")
        self.assertEqual(note.metadata["entity_refs"], ["point_cloud:scan_001"])

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "field_context")
        self.assertEqual(set(overlay.object_ids), {point_cloud.id, note.id})


if __name__ == "__main__":
    unittest.main()
