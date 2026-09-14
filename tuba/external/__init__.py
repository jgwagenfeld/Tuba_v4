"""External format adapters."""

from tuba.external.bom import bom_to_csv, bom_to_dict

# Lazy import for IFC classes — ifcopenshell is an optional dependency.
try:
    from tuba.external.ifc import IfcExporter, IfcImporter
except ImportError:
    pass

__all__ = ["IfcExporter", "IfcImporter", "bom_to_csv", "bom_to_dict"]
