"""
Tuba v4 — AI-ready piping stress analysis & routing library.

Top-level API:
    model = tuba.Model(project_name="MyProject")
    model.add_material(...)
    model.add_pipe_section(...)
    with model.pipe(section=..., material=...) as builder:
        builder.start(...).run(...).bend(...).end(...)
    results = model.solve()
"""

from tuba.model import (
    Material,
    PipeSection,
    Node,
    Element,
    BendGeometry,
    Support,
    Tee,
    LoadCase,
    NodalForce,
    Operation,
    OperationField,
    TubaModel as Model,
)
__version__ = "4.0.0"

_LAZY_EXPORTS = {
    "BuildStep": "tuba.builder", "BuiltRun": "tuba.builder",
    "PipeRunRecipe": "tuba.builder", "PipingBuilder": "tuba.builder",
    "CoordinateSystem": "tuba.coordinates",
    "PlacementAssignment": "tuba.placements", "PlacementFrame": "tuba.placements",
    "ModelFragment": "tuba.fragments", "PlacementResult": "tuba.fragments",
    "place_fragment": "tuba.fragments",
    "AddElement": "tuba.patches", "AddInsulationSpec": "tuba.patches",
    "AddNode": "tuba.patches", "AddPlacementFrame": "tuba.patches",
    "AddSupport": "tuba.patches", "AssignAttribute": "tuba.patches",
    "AssignPlacement": "tuba.patches", "CreateGroup": "tuba.patches",
    "ModelPatch": "tuba.patches", "ModelTransaction": "tuba.patches",
    "PatchResult": "tuba.patches", "RemovePlacementAssignment": "tuba.patches",
    "AttributeAssignment": "tuba.attributes", "InsulationSpec": "tuba.attributes",
    "RackBay": "tuba.assemblies",
    "ElementPhysicalProperties": "tuba.physical", "ElementQuantities": "tuba.physical",
    "element_length": "tuba.physical", "element_quantities": "tuba.physical",
    "physical_properties_for_element": "tuba.physical",
    "QuantityRecord": "tuba.quantities", "QuantityTakeoff": "tuba.quantities",
    "quantity_takeoff": "tuba.quantities", "wind_loads": "tuba.quantities",
    "LoadPathReport": "tuba.load_path", "SupportRackAssociation": "tuba.load_path",
    "analyze_load_paths": "tuba.load_path",
    "ClashFreeRule": "tuba.rules", "RuleEngine": "tuba.rules",
    "RuleReport": "tuba.rules", "RuleResult": "tuba.rules",
    "SupportSpacingRule": "tuba.rules", "rule_report_to_markdown": "tuba.rules",
    "ClashResult": "tuba.clash", "ClashEngine": "tuba.clash",
    "TrimeshClashEngine": "tuba.clash", "clash_report_to_dict": "tuba.clash",
    "clash_report_to_markdown": "tuba.clash",
    "EntityRef": "tuba.refs", "resolve_entity_ref": "tuba.refs",
    "MODEL_SCHEMA_V4": "tuba.schema", "PATCH_SCHEMA_V1": "tuba.schema",
    "SchemaValidationError": "tuba.schema", "validate_model_dict": "tuba.schema",
    "validate_patch_dict": "tuba.schema",
    "IBeamProfile": "tuba.sections", "SectionCatalog": "tuba.sections",
    "ModelValidationError": "tuba.validation", "validate_model": "tuba.validation",
    "write_model_benchmark_summary": "tuba.benchmarks",
}


def __getattr__(name):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "Model",
    "CoordinateSystem",
    "PlacementAssignment",
    "PlacementFrame",
    "ModelFragment",
    "PlacementResult",
    "place_fragment",
    "AddElement",
    "AddInsulationSpec",
    "AddNode",
    "AddPlacementFrame",
    "AddSupport",
    "AssignAttribute",
    "AssignPlacement",
    "CreateGroup",
    "ModelPatch",
    "ModelTransaction",
    "PatchResult",
    "RemovePlacementAssignment",
    "AttributeAssignment",
    "InsulationSpec",
    "RackBay",
    "ElementPhysicalProperties",
    "ElementQuantities",
    "QuantityRecord",
    "QuantityTakeoff",
    "LoadPathReport",
    "SupportRackAssociation",
    "ClashFreeRule",
    "RuleEngine",
    "RuleReport",
    "RuleResult",
    "SupportSpacingRule",
    "element_length",
    "element_quantities",
    "physical_properties_for_element",
    "quantity_takeoff",
    "wind_loads",
    "analyze_load_paths",
    "rule_report_to_markdown",
    "write_model_benchmark_summary",
    "ClashResult",
    "ClashEngine",
    "TrimeshClashEngine",
    "clash_report_to_dict",
    "clash_report_to_markdown",
    "EntityRef",
    "resolve_entity_ref",
    "MODEL_SCHEMA_V4",
    "PATCH_SCHEMA_V1",
    "SchemaValidationError",
    "validate_model_dict",
    "validate_patch_dict",
    "IBeamProfile",
    "SectionCatalog",
    "ModelValidationError",
    "validate_model",
    "Material",
    "PipeSection",
    "Node",
    "Element",
    "BendGeometry",
    "Support",
    "Tee",
    "LoadCase",
    "NodalForce",
    "Operation",
    "OperationField",
    "PipingBuilder",
    "PipeRunRecipe",
    "BuildStep",
    "BuiltRun",
]
