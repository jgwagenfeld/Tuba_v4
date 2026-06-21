import unittest

from tuba.visualization.scene import GeometryAsset, Issue, Overlay, SceneObject, VisualizationScene
from tuba.visualization.scene_diff import apply_scene_diff, build_scene_diff


class TestVisualizationSceneDiff(unittest.TestCase):
    def _scene(self, *, pipe_name="Pipe", pipe_end=1.0, include_marker=True, issue_status="open") -> VisualizationScene:
        objects = [
            SceneObject(
                id="object:pipe",
                kind="pipe",
                name=pipe_name,
                geometry_asset_id="asset:pipe",
                layer_ids=["cold_geometry"],
            )
        ]
        assets = [
            GeometryAsset(
                id="asset:pipe",
                format="polyline",
                bounds=[0, 0, 0, pipe_end, 0, 0],
                object_ids=["object:pipe"],
                generation_config={"points": [[0, 0, 0], [pipe_end, 0, 0]]},
            )
        ]
        if include_marker:
            objects.append(
                SceneObject(
                    id="object:marker",
                    kind="clash_marker",
                    name="Marker",
                    geometry_asset_id="asset:marker",
                    layer_ids=["issues:clash"],
                )
            )
            assets.append(
                GeometryAsset(
                    id="asset:marker",
                    format="marker",
                    bounds=[0.5, 0, 0, 0.5, 0, 0],
                    object_ids=["object:marker"],
                    generation_config={"point": [0.5, 0, 0]},
                )
            )
        return VisualizationScene(
            scene_id="scene:base",
            model_id="model:rv15",
            objects=objects,
            geometry_assets=assets,
            overlays=[
                Overlay(
                    id="overlay:clash",
                    kind="clash",
                    object_ids=["object:marker"] if include_marker else [],
                    visible=include_marker,
                )
            ],
            issues=[
                Issue(
                    id="issue:clash",
                    type="clash",
                    title="Pipe clash",
                    severity="error",
                    status=issue_status,
                )
            ],
        )

    def test_build_scene_diff_tracks_added_updated_removed_objects_assets_and_review_data(self):
        base = self._scene()
        next_scene = self._scene(pipe_name="Pipe revised", pipe_end=2.0, include_marker=False, issue_status="resolved")
        next_scene.objects.append(
            SceneObject(
                id="object:support",
                kind="support",
                name="New support",
                geometry_asset_id="asset:support",
                layer_ids=["supports"],
            )
        )
        next_scene.geometry_assets.append(
            GeometryAsset(
                id="asset:support",
                format="point",
                bounds=[2, 0, 0, 2, 0, 0],
                object_ids=["object:support"],
                generation_config={"point": [2, 0, 0]},
            )
        )

        result = build_scene_diff(base, next_scene, diff_id="diff:rv15")

        self.assertFalse(result.requires_full_reload)
        diff = result.scene_diff
        self.assertEqual(diff.diff_id, "diff:rv15")
        self.assertEqual([obj.id for obj in diff.added_objects], ["object:support"])
        self.assertEqual([obj.id for obj in diff.updated_objects], ["object:pipe"])
        self.assertEqual(diff.removed_object_ids, ["object:marker"])
        self.assertEqual({asset.id for asset in diff.added_geometry_assets}, {"asset:pipe", "asset:support"})
        self.assertEqual(diff.updated_overlays[0].object_ids, [])
        self.assertEqual(diff.updated_issues[0].status, "resolved")

    def test_apply_scene_diff_updates_scene_without_mutating_base_scene(self):
        base = self._scene()
        next_scene = self._scene(pipe_name="Pipe revised", pipe_end=2.0, include_marker=False, issue_status="resolved")
        diff = build_scene_diff(base, next_scene, diff_id="diff:rv15").scene_diff

        applied = apply_scene_diff(base, diff)

        self.assertEqual([obj.id for obj in base.objects], ["object:pipe", "object:marker"])
        self.assertEqual([obj.id for obj in applied.objects], ["object:pipe"])
        self.assertEqual(applied.objects[0].name, "Pipe revised")
        self.assertEqual(applied.geometry_assets[0].bounds, [0, 0, 0, 2.0, 0, 0])
        self.assertEqual(applied.issues[0].status, "resolved")

    def test_build_scene_diff_requests_full_reload_for_incompatible_scene_identity(self):
        base = self._scene()
        next_scene = self._scene()
        next_scene.model_id = "model:other"

        result = build_scene_diff(base, next_scene, diff_id="diff:rv15")

        self.assertTrue(result.requires_full_reload)
        self.assertIsNone(result.scene_diff)
        self.assertEqual(result.diagnostics[0].code, "visualization.scene_diff.full_reload_required")


if __name__ == "__main__":
    unittest.main()
