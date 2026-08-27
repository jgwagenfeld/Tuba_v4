"""Code_Aster load-block helpers for operation/load-case compilation."""

from __future__ import annotations

from typing import Callable, List

import numpy as np

from tuba.model import LoadCase, TubaModel
from tuba.physical import physical_properties_for_element

FieldGroups = List[tuple[List[str], float]]
WindGroups = List[tuple[List[str], float, float, float]]
NameMapper = Callable[[str], str]
LineWriter = Callable[[str], None]


def group_ma_value(group_names: List[str], map_name: NameMapper) -> str:
    mapped = [map_name(group_name) for group_name in group_names]
    if len(mapped) == 1:
        return f"'{mapped[0]}'"
    return "(" + ", ".join(f"'{group_name}'" for group_name in mapped) + ",)"


def resolve_operation_field_groups(
    model: TubaModel,
    load_case: LoadCase,
    quantity: str,
) -> FieldGroups:
    rows: FieldGroups = []
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.quantity != quantity:
            continue
        if field_record.profile == "uniform":
            elements = model.resolve_operation_field_elements(field_record)
            if not elements:
                raise ValueError(
                    f"Operation field {index} for {quantity!r} selects no pipe elements."
                )
            rows.append(([elem.id for elem in elements], float(field_record.value)))
            continue
        if quantity in {"temperature", "pressure"} and field_record.profile == "linear":
            rows.extend(_linear_route_field_groups(model, load_case, field_record, index, quantity))
            continue
        if field_record.profile != "uniform":
            raise ValueError(
                f"Operation field {index} for {quantity!r} uses profile "
                f"{field_record.profile!r}; only uniform fields can be exported."
            )
    if quantity != "pressure" or not rows:
        return rows

    values_by_element = {
        element.id: float(load_case.internal_pressure)
        for element in model.elements
        if element.type in {"pipe_straight", "pipe_bend"}
    }
    for element_ids, value in rows:
        for element_id in element_ids:
            values_by_element[element_id] = value
    groups_by_value: dict[float, list[str]] = {}
    for element_id, value in values_by_element.items():
        groups_by_value.setdefault(value, []).append(element_id)
    return [(element_ids, value) for value, element_ids in groups_by_value.items()]


def _linear_route_field_groups(
    model: TubaModel,
    load_case: LoadCase,
    field_record,
    index: int,
    quantity: str,
) -> FieldGroups:
    start = field_record.station_start
    end = field_record.station_end
    if start is None or end is None or float(end) <= float(start):
        raise ValueError(
            f"Operation field {index} for {quantity!r} uses linear profile without a valid station range."
        )

    rows: FieldGroups = []
    selected = model.resolve_operation_field_elements(field_record)
    if not selected:
        raise ValueError(f"Operation field {index} for {quantity!r} selects no pipe elements.")

    start = float(start)
    end = float(end)
    base = float(load_case.temperature if quantity == "temperature" else load_case.internal_pressure)
    target = float(field_record.value)
    for elem in selected:
        if elem.station_start is None or elem.station_end is None:
            raise ValueError(
                f"Operation field {index} for {quantity!r} selected element {elem.id!r} "
                "without station metadata."
            )
        overlap_start = max(float(elem.station_start), start)
        overlap_end = min(float(elem.station_end), end)
        station_mid = (overlap_start + overlap_end) / 2.0
        fraction = (station_mid - start) / (end - start)
        value = base + fraction * (target - base)
        rows.append(([elem.id], value))
    return rows


def has_pressure_load(load_case: LoadCase, pressure_fields: FieldGroups) -> bool:
    return load_case.internal_pressure > 0.0 or bool(pressure_fields)


def has_temperature_load(load_case: LoadCase, temperature_fields: FieldGroups) -> bool:
    delta_t = load_case.temperature - load_case.ref_temperature
    return (
        abs(delta_t) > 1e-10
        or any(abs(value - load_case.ref_temperature) > 1e-10 for _, value in temperature_fields)
    )


def resolve_wind_field_groups(model: TubaModel, load_case: LoadCase) -> WindGroups:
    rows: WindGroups = []
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.quantity != "wind":
            continue
        if field_record.profile != "uniform":
            raise ValueError(
                f"Operation field {index} for 'wind' uses profile "
                f"{field_record.profile!r}; only uniform fields can be exported."
            )
        direction = np.asarray(field_record.direction, dtype=float)
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-12:
            raise ValueError(f"Operation field {index} for 'wind' requires a non-zero direction.")
        direction = direction / norm
        elements = model.resolve_operation_field_elements(field_record)
        if not elements:
            raise ValueError(f"Operation field {index} for 'wind' selects no beam-modelized elements.")
        for elem in elements:
            diameter = physical_properties_for_element(model, elem).wind_diameter_m
            line_load = float(field_record.value) * diameter
            rows.append((
                [elem.id],
                line_load * float(direction[0]),
                line_load * float(direction[1]),
                line_load * float(direction[2]),
            ))
    return rows


def has_wind_load(wind_fields: WindGroups) -> bool:
    return bool(wind_fields)


def write_wind_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    wind_fields: WindGroups,
) -> None:
    for index, (_, fx, fy, fz) in enumerate(wind_fields):
        for suffix, value in (("X", fx), ("Y", fy), ("Z", fz)):
            w(f"WF{suffix}_{index} = FORMULE(")
            w("    NOM_PARA='X',")
            w(f"    VALE='{value:.6E}',")
            w(");")
            w()

    w("# ----- Wind line loads on beam-modelized pipe -----")
    w("WIND = AFFE_CHAR_MECA_F(")
    w("    MODELE=MODELE,")
    w("    FORCE_POUTRE=(")
    for index, (group_names, _, _, _) in enumerate(wind_fields):
        w("        _F(")
        w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
        w("            TYPE_CHARGE='VENT',")
        w(f"            FX=WFX_{index},")
        w(f"            FY=WFY_{index},")
        w(f"            FZ=WFZ_{index},")
        w("        ),")
    w("    ),")
    w(");")
    w()


def write_pressure_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    load_case: LoadCase,
    pressure_fields: FieldGroups,
) -> None:
    w("# ----- Internal pressure -----")
    w("PRESSURE = AFFE_CHAR_MECA(")
    w("    MODELE=MODELE,")
    if pressure_fields:
        w("    FORCE_TUYAU=(")
        for group_names, value in pressure_fields:
            w("        _F(")
            w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
            w(f"            PRES={value:.6E},")
            w("        ),")
        w("    ),")
    else:
        w("    FORCE_TUYAU=_F(")
        w(f"        GROUP_MA='{map_name('AllPipes')}',")
        w(f"        PRES={load_case.internal_pressure:.6E},")
        w("    ),")
    w(");")
    w()


def write_thermal_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    affe_entries: List[str],
    is_nonlinear: bool,
) -> None:
    w("# ----- Thermal expansion -----")
    if is_nonlinear:
        _write_temperature_field(
            w,
            name="TEMP_REF_FIELD",
            value=load_case.ref_temperature,
            map_name=map_name,
            temperature_fields=[],
        )
        _write_temperature_field(
            w,
            name="TEMP_HOT_FIELD",
            value=load_case.temperature,
            map_name=map_name,
            temperature_fields=temperature_fields,
        )
        w("TEMP_EVOL = CREA_RESU(")
        w("    OPERATION='AFFE',")
        w("    TYPE_RESU='EVOL_THER',")
        w("    NOM_CHAM='TEMP',")
        w("    AFFE=(")
        w("        _F(CHAM_GD=TEMP_REF_FIELD, INST=0.0),")
        w("        _F(CHAM_GD=TEMP_HOT_FIELD, INST=1.0),")
        w("    ),")
        w(");")
        w()
    else:
        _write_temperature_field(
            w,
            name="TEMP_FIELD",
            value=load_case.temperature,
            map_name=map_name,
            temperature_fields=temperature_fields,
        )

    w("CHMAT = AFFE_MATERIAU(")
    w("    MAILLAGE=MAIL,")
    w("    AFFE=(")
    for entry in affe_entries:
        w(entry)
    w("    ),")
    w("    AFFE_VARC=_F(")
    w("        TOUT='OUI',")
    w("        NOM_VARC='TEMP',")
    if is_nonlinear:
        w("        EVOL=TEMP_EVOL,")
        w("        NOM_CHAM='TEMP',")
    else:
        w("        CHAM_GD=TEMP_FIELD,")
    w(f"        VALE_REF={load_case.ref_temperature:.6E},")
    w("    ),")
    w(");")
    w()


def _write_temperature_field(
    w: LineWriter,
    *,
    name: str,
    value: float,
    map_name: NameMapper,
    temperature_fields: FieldGroups,
) -> None:
    w(f"{name} = CREA_CHAMP(")
    w("    TYPE_CHAM='NOEU_TEMP_R',")
    w("    OPERATION='AFFE',")
    if temperature_fields:
        w("    MODELE=MODELE,")
        w("    AFFE=(")
        w("        _F(")
        w("            TOUT='OUI',")
        w("            NOM_CMP='TEMP',")
        w(f"            VALE={value:.6E},")
        w("        ),")
        for group_names, field_value in temperature_fields:
            w("        _F(")
            w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
            w("            NOM_CMP='TEMP',")
            w(f"            VALE={field_value:.6E},")
            w("        ),")
        w("    ),")
    else:
        w("    MAILLAGE=MAIL,")
        w("    AFFE=_F(")
        w("        TOUT='OUI',")
        w("        NOM_CMP='TEMP',")
        w(f"        VALE={value:.6E},")
        w("    ),")
    w(");")
    w()
