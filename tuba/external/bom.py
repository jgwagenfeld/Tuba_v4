"""Bill-of-materials export adapters."""

from __future__ import annotations

import csv
import io
from typing import Any

from tuba.model import TubaModel
from tuba.physical import physical_properties_for_element
from tuba.quantities import quantity_takeoff


def bom_to_dict(model: TubaModel) -> dict[str, Any]:
    takeoff = quantity_takeoff(model)
    rows = []
    for record in takeoff.records:
        elem = _element_by_id(model, record.element.id)
        insulation = model.get_insulation(record.element)
        rows.append(
            {
                "element_id": elem.id,
                "section": elem.section,
                "material": elem.material,
                "length_m": record.length_m,
                "mass_kg": record.total_mass_kg,
                "surface_area_m2": record.surface_area_m2,
                "wind_projected_area_m2": record.wind_projected_area_m2,
                "insulation_spec": insulation.id if insulation else "",
                "insulation_material": insulation.material if insulation else "",
                "insulation_cost": record.insulation_cost,
                "effective_od_m": physical_properties_for_element(model, elem).effective_od_m,
            }
        )
    return {
        "rows": rows,
        "totals": dict(takeoff.totals),
        "groups": {name: dict(values) for name, values in takeoff.groups.items()},
    }


def bom_to_csv(model: TubaModel) -> str:
    data = bom_to_dict(model)
    fieldnames = [
        "element_id",
        "section",
        "material",
        "length_m",
        "mass_kg",
        "surface_area_m2",
        "wind_projected_area_m2",
        "insulation_spec",
        "insulation_material",
        "insulation_cost",
        "effective_od_m",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data["rows"])
    return buffer.getvalue()


def _element_by_id(model: TubaModel, element_id: str):
    for elem in model.elements:
        if elem.id == element_id:
            return elem
    raise KeyError(f"Unknown element {element_id!r}.")
