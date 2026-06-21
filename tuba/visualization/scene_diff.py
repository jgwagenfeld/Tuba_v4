"""Conservative SceneDiff helpers for realtime preview."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar

from tuba.visualization.scene import (
    AgentProposal,
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneDiff,
    SceneObject,
    VisualizationScene,
)


@dataclass(frozen=True)
class SceneDiffBuildResult:
    scene_diff: SceneDiff | None
    requires_full_reload: bool = False
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)


def build_scene_diff(
    base_scene: VisualizationScene,
    next_scene: VisualizationScene,
    *,
    diff_id: str | None = None,
) -> SceneDiffBuildResult:
    """Build a conservative diff, or request a full reload when identity changes."""
    base_scene.validate()
    next_scene.validate()

    diagnostics = _compatibility_diagnostics(base_scene, next_scene)
    if diagnostics:
        return SceneDiffBuildResult(scene_diff=None, requires_full_reload=True, diagnostics=diagnostics)

    base_objects = _by_key(base_scene.objects, lambda obj: obj.id)
    next_objects = _by_key(next_scene.objects, lambda obj: obj.id)
    added_objects = [next_objects[key] for key in sorted(next_objects.keys() - base_objects.keys())]
    updated_objects = [
        next_objects[key]
        for key in sorted(next_objects.keys() & base_objects.keys())
        if next_objects[key].to_dict() != base_objects[key].to_dict()
    ]
    removed_object_ids = sorted(base_objects.keys() - next_objects.keys())

    added_geometry_assets = _changed_records(
        base_scene.geometry_assets,
        next_scene.geometry_assets,
        lambda asset: asset.id,
    )
    updated_overlays = _changed_records(base_scene.overlays, next_scene.overlays, lambda overlay: overlay.id)
    updated_issues = _changed_records(base_scene.issues, next_scene.issues, lambda issue: issue.id)
    updated_route_reviews = _changed_records(
        base_scene.route_reviews,
        next_scene.route_reviews,
        lambda review: review.request_id,
    )
    updated_agent_proposals = _changed_records(
        base_scene.agent_proposals,
        next_scene.agent_proposals,
        lambda proposal: proposal.proposal_id,
    )

    scene_diff = SceneDiff(
        diff_id=diff_id or f"diff:{base_scene.scene_id}",
        base_scene_id=base_scene.scene_id,
        added_objects=added_objects,
        updated_objects=updated_objects,
        removed_object_ids=removed_object_ids,
        added_geometry_assets=added_geometry_assets,
        updated_overlays=updated_overlays,
        updated_issues=updated_issues,
        updated_route_reviews=updated_route_reviews,
        updated_agent_proposals=updated_agent_proposals,
    )
    return SceneDiffBuildResult(scene_diff=scene_diff, requires_full_reload=False, diagnostics=[])


def apply_scene_diff(base_scene: VisualizationScene, scene_diff: SceneDiff) -> VisualizationScene:
    """Apply a SceneDiff to a copy of *base_scene*."""
    if base_scene.scene_id != scene_diff.base_scene_id:
        raise ValueError(
            f"SceneDiff base_scene_id {scene_diff.base_scene_id!r} does not match scene {base_scene.scene_id!r}."
        )
    scene = VisualizationScene.from_dict(base_scene.to_dict())
    scene.objects = _apply_object_updates(scene.objects, scene_diff.added_objects, scene_diff.updated_objects, scene_diff.removed_object_ids)
    scene.geometry_assets = _upsert_records(scene.geometry_assets, scene_diff.added_geometry_assets, lambda asset: asset.id)
    scene.geometry_assets = _filter_geometry_assets_for_objects(scene.geometry_assets, scene.objects)
    scene.overlays = _upsert_records(scene.overlays, scene_diff.updated_overlays, lambda overlay: overlay.id)
    scene.issues = _upsert_records(scene.issues, scene_diff.updated_issues, lambda issue: issue.id)
    scene.route_reviews = _upsert_records(scene.route_reviews, scene_diff.updated_route_reviews, lambda review: review.request_id)
    scene.agent_proposals = _upsert_records(
        scene.agent_proposals,
        scene_diff.updated_agent_proposals,
        lambda proposal: proposal.proposal_id,
    )
    scene.diagnostics = [*scene.diagnostics, *scene_diff.diagnostics]
    scene.validate()
    return scene


def _compatibility_diagnostics(base_scene: VisualizationScene, next_scene: VisualizationScene) -> list[SceneDiagnostic]:
    checks = {
        "schema_version": (base_scene.schema_version, next_scene.schema_version),
        "model_id": (base_scene.model_id, next_scene.model_id),
        "units": (base_scene.units, next_scene.units),
        "coordinate_system": (base_scene.coordinate_system, next_scene.coordinate_system),
    }
    changed = [name for name, (base_value, next_value) in checks.items() if base_value != next_value]
    if not changed:
        return []
    return [
        SceneDiagnostic(
            severity="warning",
            code="visualization.scene_diff.full_reload_required",
            message=f"SceneDiff fallback required because {', '.join(changed)} changed.",
            source="visualization.scene_diff",
            extra={"changed_fields": changed},
        )
    ]


T = TypeVar("T")


def _changed_records(base_values: list[T], next_values: list[T], key: Callable[[T], str]) -> list[T]:
    base = _by_key(base_values, key)
    next_by_id = _by_key(next_values, key)
    changed = []
    for record_key in sorted(next_by_id.keys()):
        if record_key not in base or _to_dict(next_by_id[record_key]) != _to_dict(base[record_key]):
            changed.append(next_by_id[record_key])
    return changed


def _apply_object_updates(
    objects: list[SceneObject],
    added_objects: list[SceneObject],
    updated_objects: list[SceneObject],
    removed_object_ids: list[str],
) -> list[SceneObject]:
    removed = set(removed_object_ids)
    updates = {obj.id: obj for obj in [*updated_objects, *added_objects]}
    result = [updates.get(obj.id, obj) for obj in objects if obj.id not in removed]
    existing = {obj.id for obj in result}
    result.extend(obj for obj in added_objects if obj.id not in existing)
    return result


def _upsert_records(values: list[T], updates: list[T], key: Callable[[T], str]) -> list[T]:
    update_map = {key(item): item for item in updates}
    result = [update_map.get(key(item), item) for item in values]
    existing = {key(item) for item in result}
    result.extend(item for item in updates if key(item) not in existing)
    return result


def _filter_geometry_assets_for_objects(assets: list[GeometryAsset], objects: list[SceneObject]) -> list[GeometryAsset]:
    object_ids = {obj.id for obj in objects}
    filtered = []
    for asset in assets:
        if not asset.object_ids:
            filtered.append(asset)
            continue
        surviving_ids = [object_id for object_id in asset.object_ids if object_id in object_ids]
        if surviving_ids:
            data = asset.to_dict()
            data["object_ids"] = surviving_ids
            filtered.append(GeometryAsset.from_dict(data))
    return filtered


def _by_key(values: list[T], key: Callable[[T], str]) -> dict[str, T]:
    return {key(value): value for value in values}


def _to_dict(value: object) -> dict:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"SceneDiff record {value!r} is not serializable.")
