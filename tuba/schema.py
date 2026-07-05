"""JSON Schema contracts for model and agent-facing payloads."""

from __future__ import annotations

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


class SchemaValidationError(ValueError):
    """Raised when a JSON-like payload does not match a Tuba schema."""


MODEL_SCHEMA_V4 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TubaModelV4",
    "type": "object",
    "required": ["meta", "materials", "sections", "nodes", "elements", "supports", "load_cases"],
    "properties": {
        "meta": {
            "type": "object",
            "required": ["project_name", "standard", "version"],
            "properties": {
                "project_name": {"type": "string"},
                "standard": {"type": "string"},
                "version": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "materials": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["E", "nu"],
                "properties": {
                    "E": {"type": "number"},
                    "nu": {"type": "number"},
                    "rho": {"type": "number"},
                    "alpha": {"type": "number"},
                    "allowable_stress": {"type": "object"},
                },
                "additionalProperties": True,
            },
        },
        "sections": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["type", "OD", "WT"],
                        "properties": {
                            "type": {"const": "pipe"},
                            "OD": {"type": "number"},
                            "WT": {"type": "number"},
                            "corrosion_allowance": {"type": "number"},
                        },
                        "additionalProperties": True,
                    },
                    {
                        "type": "object",
                        "required": ["type", "OD", "WT"],
                        "properties": {
                            "type": {"const": "bar"},
                            "OD": {"type": "number"},
                            "WT": {"type": "number"},
                        },
                        "additionalProperties": True,
                    },
                    {
                        "type": "object",
                        "required": ["type", "radius"],
                        "properties": {
                            "type": {"const": "cable"},
                            "radius": {"type": "number"},
                            "pretension": {"type": "number"},
                        },
                        "additionalProperties": True,
                    },
                    {
                        "type": "object",
                        "required": ["type", "height_y", "height_z"],
                        "properties": {
                            "type": {"const": "rectangular"},
                            "height_y": {"type": "number"},
                            "height_z": {"type": "number"},
                            "thickness_y": {"type": "number"},
                            "thickness_z": {"type": "number"},
                        },
                        "additionalProperties": True,
                    },
                    {
                        "type": "object",
                        "required": ["type", "profile_name"],
                        "properties": {
                            "type": {"const": "ibeam"},
                            "profile_name": {"type": "string"},
                            "properties": {"type": "object"},
                        },
                        "additionalProperties": True,
                    },
                ]
            },
        },
        "nodes": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "number"},
            },
        },
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "n1", "n2", "section", "material"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"enum": ["pipe_straight", "pipe_bend", "beam", "bar", "cable"]},
                    "n1": {"type": "string"},
                    "n2": {"type": "string"},
                    "section": {"type": "string"},
                    "material": {"type": "string"},
                    "bend_radius": {"type": "number"},
                    "bend_angle": {"type": "number"},
                    "bend_geometry": {"$ref": "#/$defs/bendGeometry"},
                    "twist_angle": {"type": "number"},
                    "route_id": {"type": "string"},
                    "station_start": {"type": "number"},
                    "station_end": {"type": "number"},
                },
                "additionalProperties": True,
            },
        },
        "supports": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["node", "type"],
                "properties": {
                    "node": {"type": "string"},
                    "type": {"type": "string"},
                    "id": {"type": "string"},
                    "direction": {"$ref": "#/$defs/vector3"},
                    "stiffness": {"type": "number"},
                    "imposed_displacement": {"$ref": "#/$defs/vector3"},
                    "stiffness_matrix": {"type": "array", "items": {"type": "number"}},
                    "blocked_dof": {"type": "array"},
                    "mass": {"type": "number"},
                    "friction_coefficient": {"type": "number"},
                },
                "additionalProperties": True,
            },
        },
        "load_cases": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["gravity", "internal_pressure", "temperature", "ref_temperature"],
                "properties": {
                    "gravity": {"type": "boolean"},
                    "internal_pressure": {"type": "number"},
                    "temperature": {"type": "number"},
                    "ref_temperature": {"type": "number"},
                },
                "additionalProperties": True,
            },
        },
        "operations": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["gravity", "internal_pressure", "temperature", "ref_temperature"],
                "properties": {
                    "gravity": {"type": "boolean"},
                    "internal_pressure": {"type": "number"},
                    "temperature": {"type": "number"},
                    "ref_temperature": {"type": "number"},
                    "metadata": {"type": "object"},
                    "fields": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/operationField"},
                    },
                },
                "additionalProperties": True,
            },
        },
        "obstacles": {"type": "array"},
        "tees": {"type": "object"},
        "groups": {"type": "object"},
        "placement_frames": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/placementFrame"},
        },
        "placement_assignments": {
            "type": "array",
            "items": {"$ref": "#/$defs/placementAssignment"},
        },
        "specs": {
            "type": "object",
            "properties": {
                "insulation": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["material", "thickness_m"],
                        "properties": {
                            "material": {"type": "string"},
                            "thickness_m": {"type": "number", "minimum": 0.0},
                            "density_kg_m3": {"type": "number", "minimum": 0.0},
                            "cost_per_m": {"type": "number", "minimum": 0.0},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": True,
                    },
                },
            },
            "additionalProperties": {"type": "object"},
        },
        "attributes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["target", "key", "value"],
                "properties": {
                    "target": {"$ref": "#/$defs/entityRef"},
                    "key": {"type": "string", "minLength": 1},
                    "value": {},
                    "source": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "additionalProperties": True,
            },
        },
        "cad_assets": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/cadAsset"},
        },
        "imported_components": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/importedComponent"},
        },
        "analysis_regions": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/analysisRegion"},
        },
        "ports": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/port"},
        },
        "mesh_groups": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/meshGroup"},
        },
        "couplings": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/couplingSpec"},
        },
    },
    "$defs": {
        "entityRef": {
            "type": "object",
            "required": ["kind", "id"],
            "properties": {
                "kind": {
                    "enum": [
                        "node",
                        "element",
                        "support",
                        "obstacle",
                        "group",
                        "assembly",
                        "route",
                        "material",
                        "section",
                        "load_case",
                        "operation",
                        "placement_frame",
                        "cad_asset",
                        "component",
                        "analysis_region",
                        "port",
                        "mesh_group",
                        "coupling",
                    ]
                },
                "id": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        },
        "operationField": {
            "type": "object",
            "required": ["quantity", "value"],
            "properties": {
                "quantity": {"enum": ["pressure", "temperature", "wind"]},
                "value": {"type": "number"},
                "direction": {"$ref": "#/$defs/vector3"},
                "scope": {"enum": ["all", "group", "route", "elements"]},
                "profile": {"enum": ["uniform", "linear", "piecewise"]},
                "group": {"type": "string"},
                "route_id": {"type": "string"},
                "station_start": {"type": "number"},
                "station_end": {"type": "number"},
                "element_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "bendGeometry": {
            "type": "object",
            "required": [
                "center",
                "normal",
                "radius",
                "angle",
                "start_tangent",
                "end_tangent",
                "generation_mode",
            ],
            "properties": {
                "center": {"$ref": "#/$defs/vector3"},
                "normal": {"$ref": "#/$defs/vector3"},
                "radius": {"type": "number", "exclusiveMinimum": 0.0},
                "angle": {"type": "number"},
                "start_tangent": {"$ref": "#/$defs/vector3"},
                "end_tangent": {"$ref": "#/$defs/vector3"},
                "generation_mode": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "placementFrame": {
            "type": "object",
            "required": ["id", "origin"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "origin": {"$ref": "#/$defs/vector3"},
                "axis": {"$ref": "#/$defs/vector3"},
                "ref_direction": {"$ref": "#/$defs/vector3"},
                "parent": {"type": "string"},
                "frame_type": {"type": "string"},
                "source": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "placementAssignment": {
            "type": "object",
            "required": ["target", "frame"],
            "properties": {
                "target": {"type": "string", "pattern": "^[^:]+:.+$"},
                "frame": {"type": "string", "pattern": "^placement_frame:.+$"},
                "role": {"type": "string"},
                "source": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "entityRefLike": {
            "oneOf": [
                {
                    "type": "string",
                    "pattern": (
                        "^(node|element|support|obstacle|group|assembly|route|"
                        "material|section|load_case|operation|placement_frame|cad_asset|"
                        "component|analysis_region|port|mesh_group|coupling):.+$"
                    ),
                },
                {"$ref": "#/$defs/entityRef"},
            ]
        },
        "cadAsset": {
            "type": "object",
            "required": ["id", "source_path"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "source_path": {"type": "string", "minLength": 1},
                "source_format": {"type": "string", "minLength": 1},
                "unit_scale_to_m": {"type": "number", "exclusiveMinimum": 0.0},
                "placement": {"type": "object"},
                "content_digest": {"type": "string"},
                "importer": {"type": "string", "minLength": 1},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "importedComponent": {
            "type": "object",
            "required": ["id", "asset"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "asset": {"$ref": "#/$defs/entityRefLike"},
                "name": {"type": "string"},
                "role": {"type": "string"},
                "status": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "analysisRegion": {
            "type": "object",
            "required": [
                "id",
                "owner",
                "role",
                "code_aster_modelisation",
                "material",
                "mesh_group",
            ],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "owner": {"$ref": "#/$defs/entityRefLike"},
                "role": {"type": "string", "minLength": 1},
                "code_aster_modelisation": {"type": "string", "minLength": 1},
                "material": {"type": "string", "minLength": 1},
                "mesh_group": {"type": "string", "minLength": 1},
                "element_order": {"type": "integer", "minimum": 1},
                "status": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "port": {
            "type": "object",
            "required": ["id", "owner", "kind", "position", "axis", "radius"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "owner": {"$ref": "#/$defs/entityRefLike"},
                "kind": {"type": "string", "minLength": 1},
                "position": {"$ref": "#/$defs/vector3"},
                "axis": {"$ref": "#/$defs/vector3"},
                "radius": {"type": "number", "exclusiveMinimum": 0.0},
                "face_group": {"type": "string"},
                "edge_group": {"type": "string"},
                "status": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "meshGroup": {
            "type": "object",
            "required": ["id", "owner", "solver_name", "dimension"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "owner": {"$ref": "#/$defs/entityRefLike"},
                "solver_name": {"type": "string", "minLength": 1},
                "dimension": {"type": "integer", "minimum": 0, "maximum": 3},
                "members": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "couplingSpec": {
            "type": "object",
            "required": [
                "id",
                "kind",
                "source",
                "source_node",
                "target",
                "code_aster_keyword",
                "code_aster_option",
            ],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "kind": {"type": "string", "minLength": 1},
                "source": {"$ref": "#/$defs/entityRefLike"},
                "source_node": {"$ref": "#/$defs/entityRefLike"},
                "target": {"$ref": "#/$defs/entityRefLike"},
                "code_aster_keyword": {"type": "string", "minLength": 1},
                "code_aster_option": {"type": "string", "minLength": 1},
                "status": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "bendGeometry": {
            "type": "object",
            "required": [
                "center",
                "normal",
                "radius",
                "angle",
                "start_tangent",
                "end_tangent",
                "generation_mode",
            ],
            "properties": {
                "center": {"$ref": "#/$defs/vector3"},
                "normal": {"$ref": "#/$defs/vector3"},
                "radius": {"type": "number", "exclusiveMinimum": 0.0},
                "angle": {"type": "number"},
                "start_tangent": {"$ref": "#/$defs/vector3"},
                "end_tangent": {"$ref": "#/$defs/vector3"},
                "generation_mode": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "vector3": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "number"},
        },
    },
    "additionalProperties": True,
}

PATCH_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TubaModelPatchV1",
    "type": "object",
    "required": ["operations"],
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["op", "local_id", "coords"],
                        "properties": {
                            "op": {"const": "add_node"},
                            "local_id": {"type": "string"},
                            "coords": {"$ref": "#/$defs/vector3"},
                            "reuse_existing": {"type": "boolean"},
                            "tolerance": {"type": "number", "exclusiveMinimum": 0.0},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "local_id", "type", "n1", "n2", "section", "material"],
                        "properties": {
                            "op": {"const": "add_element"},
                            "local_id": {"type": "string"},
                            "type": {"enum": ["pipe_straight", "pipe_bend", "beam", "bar", "cable"]},
                            "n1": {"type": "string"},
                            "n2": {"type": "string"},
                            "section": {"type": "string"},
                            "material": {"type": "string"},
                            "bend_radius": {"type": "number"},
                            "bend_angle": {"type": "number"},
                            "bend_geometry": {"$ref": "#/$defs/bendGeometry"},
                            "twist_angle": {"type": "number"},
                            "route_id": {"type": "string"},
                            "station_start": {"type": "number"},
                            "station_end": {"type": "number"},
                            "id_prefix": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "node", "type"],
                        "properties": {
                            "op": {"const": "add_support"},
                            "node": {"type": "string"},
                            "type": {"type": "string"},
                            "direction": {"$ref": "#/$defs/vector3"},
                            "stiffness": {"type": "number"},
                            "imposed_displacement": {"$ref": "#/$defs/vector3"},
                            "stiffness_matrix": {
                                "type": "array",
                                "items": {"type": "number"},
                            },
                            "blocked_dof": {"type": "array"},
                            "mass": {"type": "number"},
                            "friction_coefficient": {"type": "number"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "id", "material", "thickness_m"],
                        "properties": {
                            "op": {"const": "add_insulation_spec"},
                            "id": {"type": "string", "minLength": 1},
                            "material": {"type": "string", "minLength": 1},
                            "thickness_m": {"type": "number", "minimum": 0.0},
                            "density_kg_m3": {"type": "number", "minimum": 0.0},
                            "cost_per_m": {"type": "number", "minimum": 0.0},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "id", "origin"],
                        "properties": {
                            "op": {"const": "add_placement_frame"},
                            "id": {"type": "string", "minLength": 1},
                            "origin": {"$ref": "#/$defs/vector3"},
                            "axis": {"$ref": "#/$defs/vector3"},
                            "ref_direction": {"$ref": "#/$defs/vector3"},
                            "parent": {"type": "string"},
                            "frame_type": {"type": "string"},
                            "source": {"type": "string"},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "target", "frame"],
                        "properties": {
                            "op": {"const": "assign_placement"},
                            "target": {"type": "string", "pattern": "^[^:]+:.+$"},
                            "frame": {"type": "string", "pattern": "^placement_frame:.+$"},
                            "role": {"type": "string"},
                            "source": {"type": "string"},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "target"],
                        "properties": {
                            "op": {"const": "remove_placement_assignment"},
                            "target": {"type": "string", "pattern": "^[^:]+:.+$"},
                            "role": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "name"],
                        "properties": {
                            "op": {"const": "create_group"},
                            "name": {"type": "string", "minLength": 1},
                            "nodes": {"type": "array", "items": {"type": "string"}},
                            "elements": {"type": "array", "items": {"type": "string"}},
                            "supports": {"type": "array", "items": {"type": "string"}},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "required": ["op", "target", "key", "value"],
                        "properties": {
                            "op": {"const": "assign_attribute"},
                            "target": {
                                "oneOf": [
                                    {"type": "string", "pattern": "^[^:]+:.+$"},
                                    {"$ref": "#/$defs/entityRef"},
                                ]
                            },
                            "key": {"type": "string", "minLength": 1},
                            "value": {},
                            "source": {"type": "string"},
                            "metadata": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                ]
            },
        },
        "provenance": {"type": "object"},
    },
    "$defs": {
        "entityRef": {
            "type": "object",
            "required": ["kind", "id"],
            "properties": {
                "kind": {
                    "enum": [
                        "node",
                        "element",
                        "support",
                        "obstacle",
                        "group",
                        "assembly",
                        "route",
                        "material",
                        "section",
                        "load_case",
                        "placement_frame",
                        "cad_asset",
                        "component",
                        "analysis_region",
                        "port",
                        "mesh_group",
                        "coupling",
                    ]
                },
                "id": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        },
        "vector3": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "number"},
        },
    },
    "additionalProperties": False,
}


def validate_model_dict(data: dict) -> None:
    _validate(_MODEL_VALIDATOR, data)


def validate_patch_dict(data: dict) -> None:
    _validate(_PATCH_VALIDATOR, data)


_MODEL_VALIDATOR = Draft202012Validator(MODEL_SCHEMA_V4)
_PATCH_VALIDATOR = Draft202012Validator(PATCH_SCHEMA_V1)


def _validate(validator: Draft202012Validator, data: dict) -> None:
    errors = sorted(validator.iter_errors(data), key=lambda error: str(list(error.path)))
    if errors:
        message = "\n".join(_format_error(error) for error in errors)
        raise SchemaValidationError(message)


def _format_error(error: ValidationError) -> str:
    path = ".".join(str(item) for item in error.path)
    if not path:
        path = "<root>"
    return f"{path}: {error.message}"
