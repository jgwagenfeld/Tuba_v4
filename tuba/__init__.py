"""
Tuba v4 — AI-ready piping stress analysis & routing library.

Top-level API:
    model = tuba.Model(project_name="MyProject")
    model.add_material(...)
    model.add_pipe_section(...)
    with model.pipe(section=..., material=...) as builder:
        builder.start(...).run(...).bend(...).end(...)
    results = model.solve(solver="code_aster")
"""

from tuba.model import (
    Material,
    PipeSection,
    Node,
    Element,
    Support,
    LoadCase,
    TubaModel as Model,
)
from tuba.builder import PipingBuilder
from tuba.coordinates import CoordinateSystem
from tuba.placements import PlacementAssignment, PlacementFrame
from tuba.fragments import ModelFragment, PlacementResult, place_fragment
from tuba.patches import (
    AddElement,
    AddInsulationSpec,
    AddNode,
    AddPlacementFrame,
    AddSupport,
    AssignAttribute,
    AssignPlacement,
    CreateGroup,
    ModelPatch,
    ModelTransaction,
    PatchResult,
    RemovePlacementAssignment,
)
from tuba.attributes import AttributeAssignment, InsulationSpec
from tuba.assemblies import RackBay
from tuba.physical import ElementPhysicalProperties, ElementQuantities, element_length, element_quantities, physical_properties_for_element
from tuba.quantities import QuantityRecord, QuantityTakeoff, quantity_takeoff, wind_loads
from tuba.load_path import LoadPathReport, SupportRackAssociation, analyze_load_paths
from tuba.rules import ClashFreeRule, RuleEngine, RuleReport, RuleResult, SupportSpacingRule, rule_report_to_markdown
from tuba.clash import ClashResult, ClashEngine, TrimeshClashEngine, clash_report_to_dict, clash_report_to_markdown
from tuba.refs import EntityRef, resolve_entity_ref
from tuba.schema import MODEL_SCHEMA_V4, PATCH_SCHEMA_V1, SchemaValidationError, validate_model_dict, validate_patch_dict
from tuba.sections import IBeamProfile, SectionCatalog
from tuba.validation import ModelValidationError, validate_model

__version__ = "4.0.0"


def write_model_benchmark_summary(*args, **kwargs):
    from tuba.benchmarks import write_model_benchmark_summary as _write_model_benchmark_summary

    return _write_model_benchmark_summary(*args, **kwargs)


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
    "Support",
    "LoadCase",
    "PipingBuilder",
]
