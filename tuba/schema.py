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
                    "twist_angle": {"type": "number"},
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
        "obstacles": {"type": "array"},
        "tees": {"type": "object"},
        "groups": {"type": "object"},
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
                            "twist_angle": {"type": "number"},
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
