"""Data contracts for semantic visualization scenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
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
    data: dict[str, Any] = field(default_factory=dict)
    visible: bool = True
    name: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Overlay":
        known = {"id", "kind", "object_ids", "entity_refs", "data", "visible", "name"}
        return cls(
            id=data["id"],
            kind=data["kind"],
            object_ids=list(data.get("object_ids", [])),
            entity_refs=_entity_refs_from_values(data.get("entity_refs", [])),
            data=dict(data.get("data", {})),
            visible=data.get("visible", True),
            name=data.get("name", ""),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "kind": self.kind, "visible": self.visible}
        _add_optional(data, "object_ids", list(self.object_ids), skip_empty=True)
        _add_optional(data, "entity_refs", [_entity_ref_to_value(ref) for ref in self.entity_refs], skip_empty=True)
        _add_optional(data, "data", dict(self.data), skip_empty=True)
        _add_optional(data, "name", self.name, skip_empty=True)
        data.update(self.extra)
        return data


#: The four layer categories. Each is a rule, not a bucket:
#: what was authored, what was solved, what came back, what comments on it.
LAYER_CATEGORIES = ("design", "analysis_mesh", "results", "annotations")


@dataclass
class SceneLayer:
    """A toggleable group of scene content.

    Layers used to be reconstructed viewer-side by guessing at layer-id string
    prefixes. The builders know the truth, so they state it here instead.
    """

    id: str
    category: str
    label: str
    parent_id: str | None = None
    default_visible: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneLayer":
        known = {"id", "category", "label", "parent_id", "default_visible"}
        return cls(
            id=data["id"],
            category=data["category"],
            label=data.get("label", ""),
            parent_id=data.get("parent_id"),
            default_visible=data.get("default_visible", True),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "label": self.label,
            "default_visible": self.default_visible,
        }
        _add_optional(data, "parent_id", self.parent_id)
        data.update(self.extra)
        return data


@dataclass
class ResultField:
    """A selectable result field: what can colour the scene.

    Decouples "which fields exist" from "which overlay happens to hold values",
    so the viewer lists fields rather than overlays. Follows the MED model of
    (support, components) and the ParaView rule of one field, one scale.
    """

    id: str
    label: str
    load_case: str
    result_state_id: str
    overlay_id: str
    support: str = "node"  # node | cell | subpoint | gauss
    components: tuple[str, ...] = ("magnitude",)
    unit: str = ""
    range: tuple[float, float] | None = None
    compliance_role: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResultField":
        known = {
            "id",
            "label",
            "load_case",
            "result_state_id",
            "overlay_id",
            "support",
            "components",
            "unit",
            "range",
            "compliance_role",
        }
        value_range = data.get("range")
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            load_case=data.get("load_case", ""),
            result_state_id=data.get("result_state_id", ""),
            overlay_id=data["overlay_id"],
            support=data.get("support", "node"),
            components=tuple(data.get("components", ("magnitude",))),
            unit=data.get("unit", ""),
            range=(float(value_range[0]), float(value_range[1])) if value_range else None,
            compliance_role=data.get("compliance_role"),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "load_case": self.load_case,
            "result_state_id": self.result_state_id,
            "overlay_id": self.overlay_id,
            "support": self.support,
            "components": list(self.components),
        }
        _add_optional(data, "unit", self.unit, skip_empty=True)
        _add_optional(data, "range", list(self.range) if self.range else None)
        _add_optional(data, "compliance_role", self.compliance_role)
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
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouteReview":
        known = {
            "request_id",
            "selected_candidate_id",
            "candidates",
            "cost_terms",
            "diagnostics",
        }
        return cls(
            request_id=data["request_id"],
            selected_candidate_id=data.get("selected_candidate_id"),
            candidates=list(data.get("candidates", [])),
            cost_terms=list(data.get("cost_terms", [])),
            diagnostics=_diagnostics_from_dicts(data.get("diagnostics", [])),
            extra=_extra(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"request_id": self.request_id}
        _add_optional(data, "selected_candidate_id", self.selected_candidate_id)
        _add_optional(data, "candidates", list(self.candidates), skip_empty=True)
        _add_optional(data, "cost_terms", list(self.cost_terms), skip_empty=True)
        _add_optional(data, "diagnostics", [diagnostic.to_dict() for diagnostic in self.diagnostics], skip_empty=True)
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
class VisualizationScene:
    scene_id: str
    model_id: str
    schema_version: str = SCENE_SCHEMA_VERSION
    created_at: str | None = None
    units: dict[str, Any] = field(default_factory=dict)
    coordinate_system: dict[str, Any] = field(default_factory=dict)
    objects: list[SceneObject] = field(default_factory=list)
    geometry_assets: list[GeometryAsset] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    layers: list[SceneLayer] = field(default_factory=list)
    result_fields: list[ResultField] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    route_reviews: list[RouteReview] = field(default_factory=list)
    views: list[ViewState] = field(default_factory=list)
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
            "overlays",
            "layers",
            "result_fields",
            "issues",
            "route_reviews",
            "views",
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
            overlays=_overlays_from_dicts(data.get("overlays", [])),
            layers=[SceneLayer.from_dict(value) for value in data.get("layers", [])],
            result_fields=[ResultField.from_dict(value) for value in data.get("result_fields", [])],
            issues=_issues_from_dicts(data.get("issues", [])),
            route_reviews=_route_reviews_from_dicts(data.get("route_reviews", [])),
            views=_views_from_dicts(data.get("views", [])),
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
            "overlays": [overlay.to_dict() for overlay in self.overlays],
            "layers": [layer.to_dict() for layer in self.layers],
            "result_fields": [result_field.to_dict() for result_field in self.result_fields],
            "issues": [issue.to_dict() for issue in self.issues],
            "route_reviews": [review.to_dict() for review in self.route_reviews],
            "views": [view.to_dict() for view in self.views],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
        _add_optional(data, "created_at", self.created_at)
        data.update(self.extra)
        return data

    def validate(self) -> None:
        _require_unique("object", [obj.id for obj in self.objects])
        _require_unique("geometry asset", [asset.id for asset in self.geometry_assets])
        _require_unique("overlay", [overlay.id for overlay in self.overlays])
        _require_unique("issue", [issue.id for issue in self.issues])
        _require_unique("view", [view.id for view in self.views])

        object_ids = {obj.id for obj in self.objects}
        asset_ids = {asset.id for asset in self.geometry_assets}
        view_ids = {view.id for view in self.views}

        for obj in self.objects:
            if obj.geometry_asset_id and obj.geometry_asset_id not in asset_ids:
                raise SceneValidationError(f"Object {obj.id!r} references missing geometry asset {obj.geometry_asset_id!r}.")
            if obj.parent_id and obj.parent_id not in object_ids:
                raise SceneValidationError(f"Object {obj.id!r} references missing parent object {obj.parent_id!r}.")

        for asset in self.geometry_assets:
            for object_id in asset.object_ids:
                if object_id not in object_ids:
                    raise SceneValidationError(f"Geometry asset {asset.id!r} references unknown object {object_id!r}.")
            if asset.format == "label":
                config = asset.generation_config
                position = config.get("position")
                height = config.get("height")
                if not isinstance(config.get("text"), str) or not config["text"].strip():
                    raise SceneValidationError(f"Label asset {asset.id!r} requires non-empty text.")
                if not isinstance(position, (list, tuple)) or len(position) != 3 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in position):
                    raise SceneValidationError(f"Label asset {asset.id!r} requires a finite three-number position.")
                if isinstance(height, bool) or not isinstance(height, (int, float)) or not isfinite(height) or height <= 0:
                    raise SceneValidationError(f"Label asset {asset.id!r} requires a positive finite height.")

        for overlay in self.overlays:
            for object_id in overlay.object_ids:
                if object_id not in object_ids:
                    raise SceneValidationError(f"Overlay {overlay.id!r} references unknown object {object_id!r}.")

        for issue in self.issues:
            if issue.view_id and issue.view_id not in view_ids:
                raise SceneValidationError(f"Issue {issue.id!r} references missing view {issue.view_id!r}.")

        _require_unique("layer", [layer.id for layer in self.layers])
        _require_unique("result field", [result_field.id for result_field in self.result_fields])

        layer_ids = {layer.id for layer in self.layers}
        for layer in self.layers:
            if layer.category not in LAYER_CATEGORIES:
                raise SceneValidationError(
                    f"Layer {layer.id!r} has unknown category {layer.category!r}; "
                    f"expected one of {', '.join(LAYER_CATEGORIES)}."
                )
            if layer.parent_id and layer.parent_id not in layer_ids:
                raise SceneValidationError(f"Layer {layer.id!r} references missing parent layer {layer.parent_id!r}.")

        overlay_ids = {overlay.id for overlay in self.overlays}
        for result_field in self.result_fields:
            if result_field.overlay_id not in overlay_ids:
                raise SceneValidationError(
                    f"Result field {result_field.id!r} references missing overlay {result_field.overlay_id!r}."
                )
            if not result_field.components:
                raise SceneValidationError(f"Result field {result_field.id!r} must declare at least one component.")


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


def _overlays_from_dicts(values: list[Any]) -> list[Overlay]:
    return [value if isinstance(value, Overlay) else Overlay.from_dict(value) for value in values]


def _issues_from_dicts(values: list[Any]) -> list[Issue]:
    return [value if isinstance(value, Issue) else Issue.from_dict(value) for value in values]


def _route_reviews_from_dicts(values: list[Any]) -> list[RouteReview]:
    return [value if isinstance(value, RouteReview) else RouteReview.from_dict(value) for value in values]


def _views_from_dicts(values: list[Any]) -> list[ViewState]:
    return [value if isinstance(value, ViewState) else ViewState.from_dict(value) for value in values]


def _require_unique(label: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for entity_id in ids:
        if entity_id in seen:
            raise SceneValidationError(f"Duplicate {label} id {entity_id!r}.")
        seen.add(entity_id)
