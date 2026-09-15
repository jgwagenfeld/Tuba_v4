import unittest

from tuba.refs import EntityRef
from tuba.visualization import (
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneObject,
    ViewState,
    VisualizationScene,
    add_scene_label,
)
from tuba.visualization.schema import SceneValidationError


class TestVisualizationScene(unittest.TestCase):
    def _minimal_scene(self) -> VisualizationScene:
        return VisualizationScene(
            scene_id="scene_001",
            model_id="model_001",
            created_at="2026-06-20T12:00:00Z",
            units={"length": "m", "mass": "kg"},
            coordinate_system={"up_axis": "Z"},
            objects=[
                SceneObject(
                    id="object_pipe_0",
                    entity_ref=EntityRef("element", "pipe_0"),
                    kind="pipe",
                    name="P-100",
                    geometry_asset_id="geometry_pipe_0",
                    metadata={"section": "DN100", "route": "P-100"},
                    physical={"effective_od_m": 0.2},
                )
            ],
            geometry_assets=[
                GeometryAsset(
                    id="geometry_pipe_0",
                    format="tube",
                    uri="geometry/pipe_0.glb",
                    bounds=[0.0, -0.1, -0.1, 1.0, 0.1, 0.1],
                    object_ids=["object_pipe_0"],
                    generation_config={"segments": 16},
                )
            ],
            overlays=[Overlay(id="overlay_clearance", kind="clearance", object_ids=["object_pipe_0"])],
            issues=[
                Issue(
                    id="issue_001",
                    type="clash",
                    title="Pipe clearance",
                    severity="warning",
                    status="open",
                    entity_refs=[EntityRef("element", "pipe_0")],
                    view_id="view_issue_001",
                )
            ],
            route_reviews=[
                RouteReview(
                    request_id="route:P-100",
                    selected_candidate_id="candidate_0",
                    candidates=[{"id": "candidate_0", "length_m": 1.0}],
                    cost_terms=[{"name": "length", "total": 1.0}],
                )
            ],
            views=[ViewState(id="view_issue_001", name="Issue 001", camera={"position": [1.0, 2.0, 3.0]})],
            diagnostics=[SceneDiagnostic(severity="info", message="fixture scene")],
        )

    def test_scene_roundtrips_to_json_dict_with_entity_refs(self):
        scene = self._minimal_scene()

        payload = scene.to_dict()
        restored = VisualizationScene.from_dict(payload)

        self.assertEqual(payload["schema_version"], "visualization.scene.v1")
        self.assertEqual(payload["objects"][0]["entity_ref"], "element:pipe_0")
        self.assertEqual(restored.objects[0].entity_ref, EntityRef("element", "pipe_0"))
        self.assertEqual(restored.issues[0].entity_refs, [EntityRef("element", "pipe_0")])
        self.assertEqual(restored.to_dict(), payload)

    def test_scene_validation_rejects_missing_geometry_asset_links(self):
        scene = self._minimal_scene()
        scene.objects[0].geometry_asset_id = "missing_asset"

        with self.assertRaisesRegex(SceneValidationError, "missing geometry asset"):
            scene.validate()

    def test_scene_validation_rejects_geometry_assets_with_unknown_object_ids(self):
        scene = self._minimal_scene()
        scene.geometry_assets[0].object_ids = ["object_pipe_0", "ghost_object"]

        with self.assertRaisesRegex(SceneValidationError, "unknown object"):
            VisualizationScene.from_dict(scene.to_dict()).validate()

    def test_scene_preserves_unknown_future_top_level_fields(self):
        payload = self._minimal_scene().to_dict()
        payload["x_future_viewer_state"] = {"enabled": True}

        restored = VisualizationScene.from_dict(payload)

        self.assertEqual(restored.extra["x_future_viewer_state"], {"enabled": True})
        self.assertEqual(restored.to_dict()["x_future_viewer_state"], {"enabled": True})

    def test_scene_with_retired_keys_still_loads_and_round_trips(self):
        data = {
            "scene_id": "legacy",
            "model_id": "model",
            "materials": [{"id": "steel"}],
            "styles": [{"id": "pipe", "material_id": "steel"}],
            "agent_proposals": [{"proposal_id": "p1"}],
            "scene_diffs": [{"diff_id": "d1", "base_scene_id": "legacy"}],
        }
        scene = VisualizationScene.from_dict(data)
        scene.validate()
        restored = scene.to_dict()
        for key in ("materials", "styles", "agent_proposals", "scene_diffs"):
            self.assertEqual(restored[key], data[key])

    def test_scene_label_adds_accessible_object_asset_and_shared_layer(self):
        scene = self._minimal_scene()
        label = add_scene_label(scene, "Low friction", [1, 2, 3], label_id="low", height=0.25)
        add_scene_label(scene, "High friction", [1, 4, 3], label_id="high")
        self.assertEqual((label.kind, label.name, label.layer_ids), ("scene_label", "Low friction", ["annotations:labels"]))
        self.assertEqual(scene.geometry_assets[-2].generation_config, {"text": "Low friction", "position": [1.0, 2.0, 3.0], "height": 0.25})
        self.assertEqual([layer.id for layer in scene.layers].count("annotations:labels"), 1)
        scene.validate()

    def test_scene_label_rejects_invalid_boundary_values(self):
        scene = self._minimal_scene()
        for text, position, height in [("", [0, 0, 0], 1), ("x", [0, float("nan"), 0], 1), ("x", [0, 0], 1), ("x", [0, 0, 0], 0)]:
            with self.subTest(text=text, position=position, height=height), self.assertRaises(SceneValidationError):
                add_scene_label(scene, text, position, label_id="bad", height=height)

        payload = self._minimal_scene().to_dict()
        payload["objects"].append({"id": "label:bad", "kind": "scene_label", "name": "Bad", "geometry_asset_id": "geometry:label:bad"})
        payload["geometry_assets"].append({"id": "geometry:label:bad", "format": "label", "object_ids": ["label:bad"], "generation_config": {"text": "Bad", "position": [0, float("inf"), 0], "height": 1}})
        with self.assertRaisesRegex(SceneValidationError, "finite three-number position"):
            VisualizationScene.from_dict(payload).validate()


if __name__ == "__main__":
    unittest.main()
