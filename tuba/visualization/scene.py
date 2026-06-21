"""Data contracts for semantic visualization scenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.refs import EntityRef
from tuba.visualization.schema import SceneValidationError


SCENE_SCHEMA_VERSION = "visualization.scene.v1"


@dataclass
class SceneDiagnostic:
    severity: str
    message: str
    code: str | None = None
    target: str | None = None
    source: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneDiagnostic":
        known = {"severity", "message", "code", "target", "source"}
        return cls(
            severity=data["severity"],
            message=data["message"],
            code=data.get("code"),
            target=data.get("target"),
            source=data.get("source"),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"severity": self.severity, "message": self.message}
        _add_optional(data, "code", self.code)
        _add_optional(data, "target", self.target)
        _add_optional(data, "source", self.source)
        data.update(self.extra)
        return data


@dataclass
class SceneMaterial:
    id: str
    name: str = ""
    color: str | None = None
    opacity: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneMaterial":
        known = {"id", "name", "color", "opacity"}
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            color=data.get("color"),
            opacity=data.get("opacity"),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id}
        _add_optional(data, "name", self.name, skip_empty=True)
        _add_optional(data, "color", self.color)
        _add_optional(data, "opacity", self.opacity)
        data.update(self.extra)
        return data


@dataclass
class SceneStyle:
    id: str
    material_id: str | None = None
    color: str | None = None
    opacity: float | None = None
    visible: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneStyle":
        known = {"id", "material_id", "color", "opacity", "visible"}
        return cls(
            id=data["id"],
            material_id=data.get("material_id"),
            color=data.get("color"),
            opacity=data.get("opacity"),
            visible=data.get("visible", True),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "visible": self.visible}
        _add_optional(data, "material_id", self.material_id)
        _add_optional(data, "color", self.color)
        _add_optional(data, "opacity", self.opacity)
        data.update(self.extra)
        return data


@dataclass
class GeometryAsset:
    id: str
    format: str
    uri: str = ""
    bounds: list[float] = field(default_factory=list)
    lod: str | None = None
    object_ids: list[str] = field(default_factory=list)
    hash: str = ""
    generation_config: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeometryAsset":
        known = {"id", "format", "uri", "bounds", "lod", "object_ids", "hash", "generation_config"}
        return cls(
            id=data["id"],
            format=data["format"],
            uri=data.get("uri", ""),
            bounds=list(data.get("bounds", [])),
            lod=data.get("lod"),
            object_ids=list(data.get("object_ids", [])),
            hash=data.get("hash", ""),
            generation_config=dict(data.get("generation_config", {})),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "format": self.format,
            "uri": self.uri,
            "bounds": list(self.bounds),
            "object_ids": list(self.object_ids),
            "generation_config": dict(self.generation_config),
        }
        _add_optional(data, "lod", self.lod)
        _add_optional(data, "hash", self.hash, skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class SceneObject:
    id: str
    entity_ref: EntityRef | None = None
    kind: str = ""
    name: str = ""
    geometry_asset_id: str | None = None
    parent_id: str | None = None
    group_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    quantities: dict[str, Any] = field(default_factory=dict)
    physical: dict[str, Any] = field(default_factory=dict)
    style_id: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneObject":
        known = {
            "id",
            "entity_ref",
            "kind",
            "name",
            "geometry_asset_id",
            "parent_id",
            "group_ids",
            "layer_ids",
            "metadata",
            "quantities",
            "physical",
            "style_id",
            "source",
            "diagnostics",
        }
        return cls(
            id=data["id"],
            entity_ref=_entity_ref_from_value(data.get("entity_ref")),
            kind=data.get("kind", ""),
            name=data.get("name", ""),
            geometry_asset_id=data.get("geometry_asset_id"),
            parent_id=data.get("parent_id"),
            group_ids=list(data.get("group_ids", [])),
            layer_ids=list(data.get("layer_ids", [])),
            metadata=dict(data.get("metadata", {})),
            quantities=dict(data.get("quantities", {})),
            physical=dict(data.get("physical", {})),
            style_id=data.get("style_id"),
            source=dict(data.get("source", {})),
            diagnostics=_diagnostics_from_dicts(data.get("diagnostics", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "kind": self.kind, "name": self.name}
        _add_optional(data, "entity_ref", _entity_ref_to_value(self.entity_ref))
        _add_optional(data, "geometry_asset_id", self.geometry_asset_id)
        _add_optional(data, "parent_id", self.parent_id)
        _add_optional(data, "group_ids", list(self.group_ids), skip_empty=True)
        _add_optional(data, "layer_ids", list(self.layer_ids), skip_empty=True)
        _add_optional(data, "metadata", dict(self.metadata), skip_empty=True)
        _add_optional(data, "quantities", dict(self.quantities), skip_empty=True)
        _add_optional(data, "physical", dict(self.physical), skip_empty=True)
        _add_optional(data, "style_id", self.style_id)
        _add_optional(data, "source", dict(self.source), skip_empty=True)
        _add_optional(data, "diagnostics", [diagnostic.to_dict() for diagnostic in self.diagnostics], skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class Overlay:
    id: str
    kind: str
    object_ids: list[str] = field(default_factory=list)
    entity_refs: list[EntityRef] = field(default_factory=list)
    style_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    visible: bool = True
    name: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Overlay":
        known = {"id", "kind", "object_ids", "entity_refs", "style_id", "data", "visible", "name"}
        return cls(
            id=data["id"],
            kind=data["kind"],
            object_ids=list(data.get("object_ids", [])),
            entity_refs=_entity_refs_from_values(data.get("entity_refs", [])),
            style_id=data.get("style_id"),
            data=dict(data.get("data", {})),
            visible=data.get("visible", True),
            name=data.get("name", ""),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "kind": self.kind, "visible": self.visible}
        _add_optional(data, "object_ids", list(self.object_ids), skip_empty=True)
        _add_optional(data, "entity_refs", [_entity_ref_to_value(ref) for ref in self.entity_refs], skip_empty=True)
        _add_optional(data, "style_id", self.style_id)
        _add_optional(data, "data", dict(self.data), skip_empty=True)
        _add_optional(data, "name", self.name, skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class Issue:
    id: str
    type: str
    title: str
    severity: str
    status: str
    entity_refs: list[EntityRef] = field(default_factory=list)
    view_id: str | None = None
    description: str = ""
    source_report_id: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    comments: list[dict[str, Any]] = field(default_factory=list)
    external_refs: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Issue":
        known = {
            "id",
            "type",
            "title",
            "description",
            "severity",
            "status",
            "entity_refs",
            "view_id",
            "source_report_id",
            "created_by",
            "created_at",
            "comments",
            "external_refs",
        }
        return cls(
            id=data["id"],
            type=data["type"],
            title=data["title"],
            description=data.get("description", ""),
            severity=data["severity"],
            status=data["status"],
            entity_refs=_entity_refs_from_values(data.get("entity_refs", [])),
            view_id=data.get("view_id"),
            source_report_id=data.get("source_report_id"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at"),
            comments=list(data.get("comments", [])),
            external_refs=dict(data.get("external_refs", {})),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
        }
        _add_optional(data, "description", self.description, skip_empty=True)
        _add_optional(data, "entity_refs", [_entity_ref_to_value(ref) for ref in self.entity_refs], skip_empty=True)
        _add_optional(data, "view_id", self.view_id)
        _add_optional(data, "source_report_id", self.source_report_id)
        _add_optional(data, "created_by", self.created_by)
        _add_optional(data, "created_at", self.created_at)
        _add_optional(data, "comments", list(self.comments), skip_empty=True)
        _add_optional(data, "external_refs", dict(self.external_refs), skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class RouteReview:
    request_id: str
    selected_candidate_id: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    cost_terms: list[dict[str, Any]] = field(default_factory=list)
    rule_results: list[dict[str, Any]] = field(default_factory=list)
    clash_results: list[dict[str, Any]] = field(default_factory=list)
    support_plan: dict[str, Any] = field(default_factory=dict)
    structure_plan: dict[str, Any] = field(default_factory=dict)
    patch_preview: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouteReview":
        known = {
            "request_id",
            "selected_candidate_id",
            "candidates",
            "cost_terms",
            "rule_results",
            "clash_results",
            "support_plan",
            "structure_plan",
            "patch_preview",
            "diagnostics",
        }
        return cls(
            request_id=data["request_id"],
            selected_candidate_id=data.get("selected_candidate_id"),
            candidates=list(data.get("candidates", [])),
            cost_terms=list(data.get("cost_terms", [])),
            rule_results=list(data.get("rule_results", [])),
            clash_results=list(data.get("clash_results", [])),
            support_plan=dict(data.get("support_plan", {})),
            structure_plan=dict(data.get("structure_plan", {})),
            patch_preview=dict(data.get("patch_preview", {})),
            diagnostics=_diagnostics_from_dicts(data.get("diagnostics", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"request_id": self.request_id}
        _add_optional(data, "selected_candidate_id", self.selected_candidate_id)
        _add_optional(data, "candidates", list(self.candidates), skip_empty=True)
        _add_optional(data, "cost_terms", list(self.cost_terms), skip_empty=True)
        _add_optional(data, "rule_results", list(self.rule_results), skip_empty=True)
        _add_optional(data, "clash_results", list(self.clash_results), skip_empty=True)
        _add_optional(data, "support_plan", dict(self.support_plan), skip_empty=True)
        _add_optional(data, "structure_plan", dict(self.structure_plan), skip_empty=True)
        _add_optional(data, "patch_preview", dict(self.patch_preview), skip_empty=True)
        _add_optional(data, "diagnostics", [diagnostic.to_dict() for diagnostic in self.diagnostics], skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class AgentProposal:
    proposal_id: str
    agent_id: str
    goal: str
    rationale: str
    model_patch: dict[str, Any]
    before_metrics: dict[str, Any] = field(default_factory=dict)
    after_metrics: dict[str, Any] = field(default_factory=dict)
    changed_entity_refs: list[EntityRef] = field(default_factory=list)
    created_entity_refs: list[EntityRef] = field(default_factory=list)
    removed_entity_refs: list[EntityRef] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    approval_state: str = "pending"
    review_comments: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentProposal":
        known = {
            "proposal_id",
            "agent_id",
            "goal",
            "rationale",
            "model_patch",
            "before_metrics",
            "after_metrics",
            "changed_entity_refs",
            "created_entity_refs",
            "removed_entity_refs",
            "risks",
            "approval_state",
            "review_comments",
        }
        return cls(
            proposal_id=data["proposal_id"],
            agent_id=data["agent_id"],
            goal=data["goal"],
            rationale=data["rationale"],
            model_patch=dict(data.get("model_patch", {})),
            before_metrics=dict(data.get("before_metrics", {})),
            after_metrics=dict(data.get("after_metrics", {})),
            changed_entity_refs=_entity_refs_from_values(data.get("changed_entity_refs", [])),
            created_entity_refs=_entity_refs_from_values(data.get("created_entity_refs", [])),
            removed_entity_refs=_entity_refs_from_values(data.get("removed_entity_refs", [])),
            risks=list(data.get("risks", [])),
            approval_state=data.get("approval_state", "pending"),
            review_comments=list(data.get("review_comments", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "goal": self.goal,
            "rationale": self.rationale,
            "model_patch": dict(self.model_patch),
            "approval_state": self.approval_state,
        }
        _add_optional(data, "before_metrics", dict(self.before_metrics), skip_empty=True)
        _add_optional(data, "after_metrics", dict(self.after_metrics), skip_empty=True)
        _add_optional(data, "changed_entity_refs", [_entity_ref_to_value(ref) for ref in self.changed_entity_refs], skip_empty=True)
        _add_optional(data, "created_entity_refs", [_entity_ref_to_value(ref) for ref in self.created_entity_refs], skip_empty=True)
        _add_optional(data, "removed_entity_refs", [_entity_ref_to_value(ref) for ref in self.removed_entity_refs], skip_empty=True)
        _add_optional(data, "risks", list(self.risks), skip_empty=True)
        _add_optional(data, "review_comments", list(self.review_comments), skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class ViewState:
    id: str
    name: str = ""
    camera: dict[str, Any] = field(default_factory=dict)
    section_box: dict[str, Any] = field(default_factory=dict)
    visible_layers: list[str] = field(default_factory=list)
    hidden_object_ids: list[str] = field(default_factory=list)
    selected_object_ids: list[str] = field(default_factory=list)
    active_overlay_ids: list[str] = field(default_factory=list)
    issue_id: str | None = None
    snapshot_uri: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ViewState":
        known = {
            "id",
            "name",
            "camera",
            "section_box",
            "visible_layers",
            "hidden_object_ids",
            "selected_object_ids",
            "active_overlay_ids",
            "issue_id",
            "snapshot_uri",
        }
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            camera=dict(data.get("camera", {})),
            section_box=dict(data.get("section_box", {})),
            visible_layers=list(data.get("visible_layers", [])),
            hidden_object_ids=list(data.get("hidden_object_ids", [])),
            selected_object_ids=list(data.get("selected_object_ids", [])),
            active_overlay_ids=list(data.get("active_overlay_ids", [])),
            issue_id=data.get("issue_id"),
            snapshot_uri=data.get("snapshot_uri"),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id}
        _add_optional(data, "name", self.name, skip_empty=True)
        _add_optional(data, "camera", dict(self.camera), skip_empty=True)
        _add_optional(data, "section_box", dict(self.section_box), skip_empty=True)
        _add_optional(data, "visible_layers", list(self.visible_layers), skip_empty=True)
        _add_optional(data, "hidden_object_ids", list(self.hidden_object_ids), skip_empty=True)
        _add_optional(data, "selected_object_ids", list(self.selected_object_ids), skip_empty=True)
        _add_optional(data, "active_overlay_ids", list(self.active_overlay_ids), skip_empty=True)
        _add_optional(data, "issue_id", self.issue_id)
        _add_optional(data, "snapshot_uri", self.snapshot_uri)
        data.update(self.extra)
        return data


@dataclass
class SceneDiff:
    diff_id: str
    base_scene_id: str
    created_at: str | None = None
    added_objects: list[SceneObject] = field(default_factory=list)
    updated_objects: list[SceneObject] = field(default_factory=list)
    removed_object_ids: list[str] = field(default_factory=list)
    added_geometry_assets: list[GeometryAsset] = field(default_factory=list)
    updated_overlays: list[Overlay] = field(default_factory=list)
    updated_issues: list[Issue] = field(default_factory=list)
    updated_route_reviews: list[RouteReview] = field(default_factory=list)
    updated_agent_proposals: list[AgentProposal] = field(default_factory=list)
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneDiff":
        known = {
            "diff_id",
            "base_scene_id",
            "created_at",
            "added_objects",
            "updated_objects",
            "removed_object_ids",
            "added_geometry_assets",
            "updated_overlays",
            "updated_issues",
            "updated_route_reviews",
            "updated_agent_proposals",
            "diagnostics",
        }
        return cls(
            diff_id=data["diff_id"],
            base_scene_id=data["base_scene_id"],
            created_at=data.get("created_at"),
            added_objects=_objects_from_dicts(data.get("added_objects", [])),
            updated_objects=_objects_from_dicts(data.get("updated_objects", [])),
            removed_object_ids=list(data.get("removed_object_ids", [])),
            added_geometry_assets=_assets_from_dicts(data.get("added_geometry_assets", [])),
            updated_overlays=_overlays_from_dicts(data.get("updated_overlays", [])),
            updated_issues=_issues_from_dicts(data.get("updated_issues", [])),
            updated_route_reviews=_route_reviews_from_dicts(data.get("updated_route_reviews", [])),
            updated_agent_proposals=_agent_proposals_from_dicts(data.get("updated_agent_proposals", [])),
            diagnostics=_diagnostics_from_dicts(data.get("diagnostics", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"diff_id": self.diff_id, "base_scene_id": self.base_scene_id}
        _add_optional(data, "created_at", self.created_at)
        _add_optional(data, "added_objects", [obj.to_dict() for obj in self.added_objects], skip_empty=True)
        _add_optional(data, "updated_objects", [obj.to_dict() for obj in self.updated_objects], skip_empty=True)
        _add_optional(data, "removed_object_ids", list(self.removed_object_ids), skip_empty=True)
        _add_optional(data, "added_geometry_assets", [asset.to_dict() for asset in self.added_geometry_assets], skip_empty=True)
        _add_optional(data, "updated_overlays", [overlay.to_dict() for overlay in self.updated_overlays], skip_empty=True)
        _add_optional(data, "updated_issues", [issue.to_dict() for issue in self.updated_issues], skip_empty=True)
        _add_optional(data, "updated_route_reviews", [review.to_dict() for review in self.updated_route_reviews], skip_empty=True)
        _add_optional(
            data,
            "updated_agent_proposals",
            [proposal.to_dict() for proposal in self.updated_agent_proposals],
            skip_empty=True,
        )
        _add_optional(data, "diagnostics", [diagnostic.to_dict() for diagnostic in self.diagnostics], skip_empty=True)
        data.update(self.extra)
        return data


@dataclass
class VisualizationScene:
    scene_id: str
    model_id: str
    schema_version: str = SCENE_SCHEMA_VERSION
    created_at: str | None = None
    units: dict[str, Any] = field(default_factory=dict)
    coordinate_system: dict[str, Any] = field(default_factory=dict)
    objects: list[SceneObject] = field(default_factory=list)
    geometry_assets: list[GeometryAsset] = field(default_factory=list)
    materials: list[SceneMaterial] = field(default_factory=list)
    styles: list[SceneStyle] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    route_reviews: list[RouteReview] = field(default_factory=list)
    agent_proposals: list[AgentProposal] = field(default_factory=list)
    views: list[ViewState] = field(default_factory=list)
    scene_diffs: list[SceneDiff] = field(default_factory=list)
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualizationScene":
        known = {
            "schema_version",
            "scene_id",
            "model_id",
            "created_at",
            "units",
            "coordinate_system",
            "objects",
            "geometry_assets",
            "materials",
            "styles",
            "overlays",
            "issues",
            "route_reviews",
            "agent_proposals",
            "views",
            "scene_diffs",
            "diagnostics",
        }
        return cls(
            schema_version=data.get("schema_version", SCENE_SCHEMA_VERSION),
            scene_id=data["scene_id"],
            model_id=data["model_id"],
            created_at=data.get("created_at"),
            units=dict(data.get("units", {})),
            coordinate_system=dict(data.get("coordinate_system", {})),
            objects=_objects_from_dicts(data.get("objects", [])),
            geometry_assets=_assets_from_dicts(data.get("geometry_assets", [])),
            materials=_materials_from_dicts(data.get("materials", [])),
            styles=_styles_from_dicts(data.get("styles", [])),
            overlays=_overlays_from_dicts(data.get("overlays", [])),
            issues=_issues_from_dicts(data.get("issues", [])),
            route_reviews=_route_reviews_from_dicts(data.get("route_reviews", [])),
            agent_proposals=_agent_proposals_from_dicts(data.get("agent_proposals", [])),
            views=_views_from_dicts(data.get("views", [])),
            scene_diffs=_scene_diffs_from_dicts(data.get("scene_diffs", [])),
            diagnostics=_diagnostics_from_dicts(data.get("diagnostics", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "model_id": self.model_id,
            "units": dict(self.units),
            "coordinate_system": dict(self.coordinate_system),
            "objects": [obj.to_dict() for obj in self.objects],
            "geometry_assets": [asset.to_dict() for asset in self.geometry_assets],
            "materials": [material.to_dict() for material in self.materials],
            "styles": [style.to_dict() for style in self.styles],
            "overlays": [overlay.to_dict() for overlay in self.overlays],
            "issues": [issue.to_dict() for issue in self.issues],
            "route_reviews": [review.to_dict() for review in self.route_reviews],
            "agent_proposals": [proposal.to_dict() for proposal in self.agent_proposals],
            "views": [view.to_dict() for view in self.views],
            "scene_diffs": [diff.to_dict() for diff in self.scene_diffs],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
        _add_optional(data, "created_at", self.created_at)
        data.update(self.extra)
        return data

    def validate(self) -> None:
        _require_unique("object", [obj.id for obj in self.objects])
        _require_unique("geometry asset", [asset.id for asset in self.geometry_assets])
        _require_unique("material", [material.id for material in self.materials])
        _require_unique("style", [style.id for style in self.styles])
        _require_unique("overlay", [overlay.id for overlay in self.overlays])
        _require_unique("issue", [issue.id for issue in self.issues])
        _require_unique("view", [view.id for view in self.views])

        object_ids = {obj.id for obj in self.objects}
        asset_ids = {asset.id for asset in self.geometry_assets}
        style_ids = {style.id for style in self.styles}
        material_ids = {material.id for material in self.materials}
        view_ids = {view.id for view in self.views}

        for obj in self.objects:
            if obj.geometry_asset_id and obj.geometry_asset_id not in asset_ids:
                raise SceneValidationError(f"Object {obj.id!r} references missing geometry asset {obj.geometry_asset_id!r}.")
            if obj.parent_id and obj.parent_id not in object_ids:
                raise SceneValidationError(f"Object {obj.id!r} references missing parent object {obj.parent_id!r}.")
            if obj.style_id and obj.style_id not in style_ids:
                raise SceneValidationError(f"Object {obj.id!r} references missing style {obj.style_id!r}.")

        for asset in self.geometry_assets:
            for object_id in asset.object_ids:
                if object_id not in object_ids:
                    raise SceneValidationError(f"Geometry asset {asset.id!r} references unknown object {object_id!r}.")

        for style in self.styles:
            if style.material_id and style.material_id not in material_ids:
                raise SceneValidationError(f"Style {style.id!r} references missing material {style.material_id!r}.")

        for overlay in self.overlays:
            if overlay.style_id and overlay.style_id not in style_ids:
                raise SceneValidationError(f"Overlay {overlay.id!r} references missing style {overlay.style_id!r}.")
            for object_id in overlay.object_ids:
                if object_id not in object_ids:
                    raise SceneValidationError(f"Overlay {overlay.id!r} references unknown object {object_id!r}.")

        for issue in self.issues:
            if issue.view_id and issue.view_id not in view_ids:
                raise SceneValidationError(f"Issue {issue.id!r} references missing view {issue.view_id!r}.")


def _add_optional(data: dict[str, Any], key: str, value: Any, *, skip_empty: bool = False) -> None:
    if value is None:
        return
    if skip_empty and value in ("", [], {}):
        return
    data[key] = value


def _extra(data: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in known}


def _entity_ref_from_value(value: Any) -> EntityRef | None:
    if value is None:
        return None
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, str):
        return EntityRef.parse(value)
    if isinstance(value, dict):
        return EntityRef.from_dict(value)
    raise TypeError(f"Unsupported entity ref value {value!r}.")


def _entity_ref_to_value(value: EntityRef | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _entity_refs_from_values(values: list[Any]) -> list[EntityRef]:
    return [_entity_ref_from_value(value) for value in values if value is not None]


def _diagnostics_from_dicts(values: list[Any]) -> list[SceneDiagnostic]:
    return [value if isinstance(value, SceneDiagnostic) else SceneDiagnostic.from_dict(value) for value in values]


def _objects_from_dicts(values: list[Any]) -> list[SceneObject]:
    return [value if isinstance(value, SceneObject) else SceneObject.from_dict(value) for value in values]


def _assets_from_dicts(values: list[Any]) -> list[GeometryAsset]:
    return [value if isinstance(value, GeometryAsset) else GeometryAsset.from_dict(value) for value in values]


def _materials_from_dicts(values: list[Any]) -> list[SceneMaterial]:
    return [value if isinstance(value, SceneMaterial) else SceneMaterial.from_dict(value) for value in values]


def _styles_from_dicts(values: list[Any]) -> list[SceneStyle]:
    return [value if isinstance(value, SceneStyle) else SceneStyle.from_dict(value) for value in values]


def _overlays_from_dicts(values: list[Any]) -> list[Overlay]:
    return [value if isinstance(value, Overlay) else Overlay.from_dict(value) for value in values]


def _issues_from_dicts(values: list[Any]) -> list[Issue]:
    return [value if isinstance(value, Issue) else Issue.from_dict(value) for value in values]


def _route_reviews_from_dicts(values: list[Any]) -> list[RouteReview]:
    return [value if isinstance(value, RouteReview) else RouteReview.from_dict(value) for value in values]


def _agent_proposals_from_dicts(values: list[Any]) -> list[AgentProposal]:
    return [value if isinstance(value, AgentProposal) else AgentProposal.from_dict(value) for value in values]


def _views_from_dicts(values: list[Any]) -> list[ViewState]:
    return [value if isinstance(value, ViewState) else ViewState.from_dict(value) for value in values]


def _scene_diffs_from_dicts(values: list[Any]) -> list[SceneDiff]:
    return [value if isinstance(value, SceneDiff) else SceneDiff.from_dict(value) for value in values]


def _require_unique(label: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for entity_id in ids:
        if entity_id in seen:
            raise SceneValidationError(f"Duplicate {label} id {entity_id!r}.")
        seen.add(entity_id)
