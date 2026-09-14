"""Quantity, weight, cost, and wind-load takeoff helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.model import TubaModel
from tuba.physical import element_quantities
from tuba.refs import EntityRef


@dataclass(frozen=True)
class QuantityRecord:
    element: EntityRef
    length_m: float
    mass_kg_per_m: float
    total_mass_kg: float
    insulation_mass_kg: float
    insulation_volume_m3: float
    insulation_cost: float
    surface_area_m2: float
    wind_projected_area_m2: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element.to_dict(),
            "length_m": self.length_m,
            "mass_kg_per_m": self.mass_kg_per_m,
            "total_mass_kg": self.total_mass_kg,
            "insulation_mass_kg": self.insulation_mass_kg,
            "insulation_volume_m3": self.insulation_volume_m3,
            "insulation_cost": self.insulation_cost,
            "surface_area_m2": self.surface_area_m2,
            "wind_projected_area_m2": self.wind_projected_area_m2,
        }


@dataclass(frozen=True)
class QuantityTakeoff:
    records: list[QuantityRecord] = field(default_factory=list)
    totals: dict[str, float] = field(default_factory=dict)
    groups: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [record.to_dict() for record in self.records],
            "totals": dict(self.totals),
            "groups": {name: dict(values) for name, values in self.groups.items()},
        }


def quantity_takeoff(model: TubaModel) -> QuantityTakeoff:
    records: list[QuantityRecord] = []
    for elem in model.elements:
        quantities = element_quantities(model, elem)
        records.append(
            QuantityRecord(
                element=EntityRef("element", elem.id),
                length_m=quantities.length_m,
                mass_kg_per_m=quantities.mass_kg_per_m,
                total_mass_kg=quantities.total_mass_kg,
                insulation_mass_kg=quantities.insulation_mass_kg,
                insulation_volume_m3=quantities.insulation_volume_m3,
                insulation_cost=quantities.insulation_cost,
                surface_area_m2=quantities.surface_area_m2,
                wind_projected_area_m2=quantities.wind_projected_area_m2,
            )
        )
    return QuantityTakeoff(
        records=records,
        totals=_sum_records(records),
        groups=_group_totals(model, records),
    )


def wind_loads(model: TubaModel, *, pressure_pa: float) -> dict[str, dict[str, float]]:
    loads: dict[str, dict[str, float]] = {}
    for elem in model.elements:
        quantities = element_quantities(model, elem)
        force = quantities.wind_projected_area_m2 * pressure_pa
        loads[elem.id] = {
            "projected_area_m2": quantities.wind_projected_area_m2,
            "pressure_pa": pressure_pa,
            "force_n": force,
        }
    return loads


def _sum_records(records: list[QuantityRecord]) -> dict[str, float]:
    totals = {
        "element_count": float(len(records)),
        "length_m": 0.0,
        "total_mass_kg": 0.0,
        "insulation_mass_kg": 0.0,
        "insulation_volume_m3": 0.0,
        "insulation_cost": 0.0,
        "surface_area_m2": 0.0,
        "wind_projected_area_m2": 0.0,
    }
    for record in records:
        _add_record(totals, record)
    return totals


def _group_totals(model: TubaModel, records: list[QuantityRecord]) -> dict[str, dict[str, float]]:
    by_element = {record.element.id: record for record in records}
    groups: dict[str, dict[str, float]] = {}
    for group_name, group in model.groups.items():
        totals = {
            "element_count": 0.0,
            "length_m": 0.0,
            "total_mass_kg": 0.0,
            "insulation_mass_kg": 0.0,
            "insulation_volume_m3": 0.0,
            "insulation_cost": 0.0,
            "surface_area_m2": 0.0,
            "wind_projected_area_m2": 0.0,
        }
        for element_id in group.get("elements", []):
            record = by_element.get(element_id)
            if record is None:
                continue
            totals["element_count"] += 1.0
            _add_record(totals, record)
        if totals["element_count"]:
            groups[group_name] = totals
    return groups


def _add_record(totals: dict[str, float], record: QuantityRecord) -> None:
    totals["length_m"] += record.length_m
    totals["total_mass_kg"] += record.total_mass_kg
    totals["insulation_mass_kg"] += record.insulation_mass_kg
    totals["insulation_volume_m3"] += record.insulation_volume_m3
    totals["insulation_cost"] += record.insulation_cost
    totals["surface_area_m2"] += record.surface_area_m2
    totals["wind_projected_area_m2"] += record.wind_projected_area_m2
