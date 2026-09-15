import unittest

from tuba import Model
from tuba.visualization import build_visualization_scene


class TestVisualizationFieldNotes(unittest.TestCase):
    def test_field_note_descriptors_are_scene_objects(self):
        model = Model(project_name="FieldNoteReview")

        scene = build_visualization_scene(
            model,
            field_notes=[
                {
                    "id": "note_001",
                    "text": "Verify pipe clearance in field",
                    "position": [1.0, 2.0, 0.5],
                    "entity_refs": ["element:pipe_0"],
                }
            ],
            scene_id="scene_field_notes",
        )
        scene.validate()

        note = next(obj for obj in scene.objects if obj.kind == "field_note")
        self.assertEqual(note.metadata["text"], "Verify pipe clearance in field")
        self.assertEqual(note.metadata["entity_refs"], ["element:pipe_0"])

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "field_context")
        self.assertEqual(overlay.object_ids, [note.id])


if __name__ == "__main__":
    unittest.main()
