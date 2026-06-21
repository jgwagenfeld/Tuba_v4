import unittest

from tuba.refs import EntityRef
from tuba.visualization import (
    AgentProposal,
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneDiff,
    SceneMaterial,
    SceneObject,
    SceneStyle,
    ViewState,
    VisualizationScene,
)
from tuba.visualization.schema import SceneValidationError, validate_scene_dict


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
            materials=[SceneMaterial(id="mat_pipe", name="Pipe", color="#4c78a8")],
            styles=[SceneStyle(id="style_pipe", material_id="mat_pipe")],
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
            agent_proposals=[
                AgentProposal(
                    proposal_id="proposal_001",
                    agent_id="agent_a",
                    goal="route pipe",
                    rationale="shortest valid route",
                    model_patch={"operations": []},
                    before_metrics={"cost": 2.0},
                    after_metrics={"cost": 1.0},
                    changed_entity_refs=[EntityRef("route", "P-100")],
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
            validate_scene_dict(scene.to_dict())

    def test_scene_preserves_unknown_future_top_level_fields(self):
        payload = self._minimal_scene().to_dict()
        payload["x_future_viewer_state"] = {"enabled": True}

        restored = VisualizationScene.from_dict(payload)

        self.assertEqual(restored.extra["x_future_viewer_state"], {"enabled": True})
        self.assertEqual(restored.to_dict()["x_future_viewer_state"], {"enabled": True})

    def test_scene_diff_roundtrips_changed_objects_and_diagnostics(self):
        pipe = self._minimal_scene().objects[0]
        diff = SceneDiff(
            diff_id="diff_001",
            base_scene_id="scene_001",
            created_at="2026-06-20T12:01:00Z",
            updated_objects=[pipe],
            removed_object_ids=["object_old"],
            diagnostics=[SceneDiagnostic(severity="warning", message="partial rebuild")],
        )

        restored = SceneDiff.from_dict(diff.to_dict())

        self.assertEqual(restored.diff_id, "diff_001")
        self.assertEqual(restored.updated_objects[0].entity_ref, EntityRef("element", "pipe_0"))
        self.assertEqual(restored.removed_object_ids, ["object_old"])
        self.assertEqual(restored.to_dict(), diff.to_dict())


if __name__ == "__main__":
    unittest.main()
