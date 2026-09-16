"""Code_Aster load-block helpers for operation/load-case compilation."""

from __future__ import annotations

import math
from typing import Callable, List, Sequence

import numpy as np

from tuba.model import Element, LoadCase, TubaModel
from tuba.physical import physical_properties_for_element
from tuba.validation import _node_field_problem, _pipe_node_ids

FieldGroups = List[tuple[List[str], float]]
WindGroups = List[tuple[List[str], float, float, float]]
LineLoadGroups = List[tuple[List[str], float, float, float]]
TuyauWindRows = List[tuple[str, str, tuple[str, str, str]]]
BendFrame = Callable[[Element], tuple[Sequence[float], Sequence[float]]]
NameMapper = Callable[[str], str]
LineWriter = Callable[[str], None]
NodeTemperatureEntries = Sequence[tuple[str, float]]
SolverNodes = Callable[[Element], Sequence[tuple[str, float]]]


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
        if quantity == "temperature" and field_record.scope == "nodes":
            continue  # Node temperatures reach the field through node_temperature_entries.
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


def has_temperature_load(
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    node_temperatures: NodeTemperatureEntries = (),
) -> bool:
    delta_t = load_case.temperature - load_case.ref_temperature
    return (
        abs(delta_t) > 1e-10
        or any(abs(value - load_case.ref_temperature) > 1e-10 for _, value in temperature_fields)
        or any(abs(value - load_case.ref_temperature) > 1e-10 for _, value in node_temperatures)
    )


def resolve_node_temperatures(model: TubaModel, load_case: LoadCase) -> dict[str, float]:
    """Node-scoped temperature fields of one load case, as model node id -> temperature.

    Validation walks only operations, so this applies its node rules to load-case fields.
    """
    pipe_nodes = _pipe_node_ids(model)
    values: dict[str, float] = {}
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.scope != "nodes" and not field_record.node_ids:
            continue
        problem = _node_field_problem(field_record, model, pipe_nodes)
        if problem is not None:
            raise ValueError(f"Operation field {index} {problem}")
        value = float(field_record.value)
        for node_id in field_record.node_ids:
            previous = values.get(node_id)
            if previous is not None and previous != value:
                raise ValueError(
                    f"Operation field {index} gives node {node_id!r} {value!r}, "
                    f"but an earlier node field gives it {previous!r}."
                )
            values[node_id] = value
    if not values:
        return values
    covered: set[str] = set()
    for field_record in getattr(load_case, "fields", []):
        if field_record.quantity == "temperature" and field_record.scope != "nodes":
            for elem in model.resolve_operation_field_elements(field_record):
                covered.update((elem.n1, elem.n2))
    shared = sorted(set(values) & covered)
    if shared:
        raise ValueError(
            f"Nodes {shared!r} have a node temperature and belong to elements an element temperature "
            "field covers; a node takes one or the other."
        )
    return values


def node_temperature_entries(
    model: TubaModel,
    load_case: LoadCase,
    temperature_fields: FieldGroups,
    solver_nodes: SolverNodes,
) -> list[tuple[str, float]]:
    """Temperatures for every solver node of the elements a node temperature touches, in write order.

    Code_Aster's temperature field has one value per node, and the solver mesh has
    nodes the model does not: bend and subdivision nodes, TUYAU midsides. A touched
    element gets its two end values and interpolates its generated nodes linearly at
    the fractions ``solver_nodes`` gives. An end without a node temperature keeps
    what the rest of the field gives it: the last element row covering it, else the
    case temperature.
    """
    node_values = resolve_node_temperatures(model, load_case)
    if not node_values:
        return []
    row_values: dict[str, float] = {}
    for element_ids, value in temperature_fields:
        for element_id in element_ids:
            elem = model.get_element(element_id)
            row_values[elem.n1] = value
            row_values[elem.n2] = value

    def end_value(node_id: str) -> float:
        if node_id in node_values:
            return node_values[node_id]
        return row_values.get(node_id, float(load_case.temperature))

    entries: dict[str, float] = {}
    for elem in model.elements:
        if elem.n1 not in node_values and elem.n2 not in node_values:
            continue
        start, end = end_value(elem.n1), end_value(elem.n2)
        for node_id, fraction in solver_nodes(elem):
            entries.setdefault(node_id, (1.0 - fraction) * start + fraction * end)
    return list(entries.items())


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
            raise ValueError(f"Operation field {index} for 'wind' selects no pipe or beam elements.")
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


def resolve_line_load_groups(model: TubaModel, load_case: LoadCase) -> LineLoadGroups:
    """Line loads as force per metre in global axes, grouped by value.

    Code_Aster keeps only the last FORCE_POUTRE occurrence on an element within
    one AFFE_CHAR_MECA (two loads on one group solved as the second alone), so
    every element lands in exactly one row. Line loads add, so a second field on
    an element is refused rather than applied once. This also covers load-case
    fields, which validation does not walk.
    """
    forces: dict[str, tuple[float, float, float]] = {}
    for index, field_record in enumerate(getattr(load_case, "fields", [])):
        if field_record.quantity != "line_load":
            continue
        if field_record.profile != "uniform":
            raise ValueError(
                f"Operation field {index} for 'line_load' uses profile "
                f"{field_record.profile!r}; only uniform fields can be exported."
            )
        direction = np.asarray(field_record.direction, dtype=float)
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-12:
            raise ValueError(f"Operation field {index} for 'line_load' requires a non-zero direction.")
        elements = model.resolve_operation_field_elements(field_record)
        if not elements:
            raise ValueError(f"Operation field {index} for 'line_load' selects no pipe or beam elements.")
        force = (
            float(field_record.value) * float(direction[0]) / norm,
            float(field_record.value) * float(direction[1]) / norm,
            float(field_record.value) * float(direction[2]) / norm,
        )
        for elem in elements:
            if elem.id in forces:
                raise ValueError(
                    f"Operation field {index} for 'line_load' loads element {elem.id!r}, which an earlier "
                    "line_load field already loads; line loads add, so author one combined line_load field."
                )
            forces[elem.id] = force
    groups: dict[tuple[float, float, float], List[str]] = {}
    for element_id, force in forces.items():
        groups.setdefault(force, []).append(element_id)
    return [(element_ids, fx, fy, fz) for (fx, fy, fz), element_ids in groups.items()]


def write_line_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    line_loads: LineLoadGroups,
) -> None:
    w("# ----- Line loads on pipes and beams -----")
    w("LINELOAD = AFFE_CHAR_MECA(")
    w("    MODELE=MODELE,")
    w("    FORCE_POUTRE=(")
    for group_names, fx, fy, fz in line_loads:
        w("        _F(")
        w(f"            GROUP_MA={group_ma_value(group_names, map_name)},")
        w(f"            FX={fx:.6E},")
        w(f"            FY={fy:.6E},")
        w(f"            FZ={fz:.6E},")
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
    node_temperatures: NodeTemperatureEntries,
    affe_entries: List[str],
    is_nonlinear: bool,
    varc_groups: Sequence[str] | None = None,
) -> None:
    w("# ----- Thermal expansion -----")
    if is_nonlinear:
        _write_temperature_field(
            w,
            name="TEMP_REF_FIELD",
            value=load_case.ref_temperature,
            map_name=map_name,
            temperature_fields=[],
            node_temperatures=[],
        )
        _write_temperature_field(
            w,
            name="TEMP_HOT_FIELD",
            value=load_case.temperature,
            map_name=map_name,
            temperature_fields=temperature_fields,
            node_temperatures=node_temperatures,
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
            node_temperatures=node_temperatures,
        )

    w("CHMAT = AFFE_MATERIAU(")
    w("    MAILLAGE=MAIL,")
    w("    AFFE=(")
    for entry in affe_entries:
        w(entry)
    w("    ),")
    w("    AFFE_VARC=_F(")
    if varc_groups is None:
        w("        TOUT='OUI',")
    else:
        w(f"        GROUP_MA={tuple(map_name(group) for group in varc_groups)!r},")
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
    node_temperatures: NodeTemperatureEntries,
) -> None:
    w(f"{name} = CREA_CHAMP(")
    w("    TYPE_CHAM='NOEU_TEMP_R',")
    w("    OPERATION='AFFE',")
    if temperature_fields or node_temperatures:
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
        # A later occurrence overwrites an earlier one on a node, so the node rows go last.
        for node_id, node_value in node_temperatures:
            w("        _F(")
            w(f"            GROUP_NO='{map_name(f'GN_{node_id}')}',")
            w("            NOM_CMP='TEMP',")
            w(f"            VALE={node_value:.6E},")
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


def cross_flow_line_load(line_load: Sequence[float], tangent: Sequence[float]) -> tuple[float, float, float]:
    """The wind force per metre an element whose axis is ``tangent`` actually carries.

    This is the rule Code_Aster applies for FORCE_POUTRE(TYPE_CHARGE='VENT'):
    keep the part of the wind across the axis, and scale it once more by the
    sine of the angle between wind and axis. A pipe at 30 degrees to the wind
    carries a quarter of the head-on load (solved on POU_D_T: 1000 N/m at 30
    degrees over 4 m gave 1000 N). TUYAU_3M refuses VENT, so Tuba applies the
    same rule itself on pipe elements.
    """
    force = np.asarray(line_load, dtype=float)
    magnitude = float(np.linalg.norm(force))
    if magnitude == 0.0:
        return (0.0, 0.0, 0.0)
    axis = np.asarray(tangent, dtype=float)
    axis = axis / float(np.linalg.norm(axis))
    across = force - float(np.dot(force, axis)) * axis
    carried = across * (float(np.linalg.norm(across)) / magnitude)
    return (float(carried[0]), float(carried[1]), float(carried[2]))


def cross_flow_formula(
    line_load: Sequence[float],
    center: Sequence[float],
    axis: Sequence[float],
) -> tuple[str, str, str]:
    """``cross_flow_line_load`` along a circular bend, as FORMULE text in X, Y, Z.

    The bend tangent at a point P is ``axis x (P - center)``; only its direction
    matters, so it stays unnormalized. Numbers use ``repr`` so the text is exact.
    Solved on TUYAU_3M, this text matched POU_D_T VENT on an elbow within 0.06%.
    """
    fx, fy, fz = (float(value) for value in line_load)
    magnitude = math.sqrt(fx * fx + fy * fy + fz * fz)
    if magnitude == 0.0:
        return ("0.0", "0.0", "0.0")
    unit = np.asarray(axis, dtype=float)
    ax, ay, az = (float(value) for value in unit / float(np.linalg.norm(unit)))
    cx, cy, cz = (float(value) for value in center)
    rx, ry, rz = f"(X-({cx!r}))", f"(Y-({cy!r}))", f"(Z-({cz!r}))"
    tx = f"(({ay!r})*{rz}-({az!r})*{ry})"
    ty = f"(({az!r})*{rx}-({ax!r})*{rz})"
    tz = f"(({ax!r})*{ry}-({ay!r})*{rx})"
    along = f"((({fx!r})*{tx}+({fy!r})*{ty}+({fz!r})*{tz})/({tx}**2+{ty}**2+{tz}**2))"
    across = [f"(({f!r})-{along}*{t})" for f, t in ((fx, tx), (fy, ty), (fz, tz))]
    scale = f"(sqrt({across[0]}**2+{across[1]}**2+{across[2]}**2)/({magnitude!r}))"
    return (f"{scale}*{across[0]}", f"{scale}*{across[1]}", f"{scale}*{across[2]}")


def tuyau_wind_rows(model: TubaModel, wind_fields: WindGroups, bend_frame: BendFrame) -> TuyauWindRows:
    """Wind on TUYAU_3M pipe elements as ``(element id, NOM_PARA, FORMULE texts)``.

    Code_Aster refuses TYPE_CHARGE='VENT' on pipe elements (PIPE1_44), so the
    cross-flow rule VENT uses on beams is applied here: a constant on a straight
    pipe, a function of X, Y, Z along a bend. One row per element, because one
    FORCE_POUTRE command keeps only its last occurrence on an element.
    """
    loads: dict[str, tuple[float, float, float]] = {}
    for group_names, fx, fy, fz in wind_fields:
        for element_id in group_names:
            loads[element_id] = (fx, fy, fz)
    rows: TuyauWindRows = []
    for element_id, line_load in loads.items():
        elem = model.get_element(element_id)
        if elem.type == "pipe_bend":
            center, axis = bend_frame(elem)
            rows.append((element_id, "('X', 'Y', 'Z')", cross_flow_formula(line_load, center, axis)))
            continue
        start = np.asarray(model.nodes[elem.n1].coords, dtype=float)
        end = np.asarray(model.nodes[elem.n2].coords, dtype=float)
        fx, fy, fz = cross_flow_line_load(line_load, end - start)
        rows.append((element_id, "'X'", (f"{fx:.6E}", f"{fy:.6E}", f"{fz:.6E}")))
    return rows


def write_tuyau_wind_load(
    w: LineWriter,
    *,
    map_name: NameMapper,
    rows: TuyauWindRows,
) -> None:
    # ponytail: Code_Aster concept names cap at 8 characters, so TFX_9999 is the last
    # formula; group equal straight-pipe loads if a model ever carries 10 000 wind elements.
    for index, (_, nom_para, texts) in enumerate(rows):
        for suffix, text in zip(("X", "Y", "Z"), texts):
            w(f"TF{suffix}_{index} = FORMULE(")
            w(f"    NOM_PARA={nom_para},")
            w(f"    VALE='''{text}''',")
            w(");")
            w()

    w("# ----- Wind line loads on TUYAU pipes (VENT's cross-flow rule, applied by Tuba) -----")
    w("WIND_TUY = AFFE_CHAR_MECA_F(")
    w("    MODELE=MODELE,")
    w("    FORCE_POUTRE=(")
    for index, (element_id, _, _) in enumerate(rows):
        w("        _F(")
        w(f"            GROUP_MA='{map_name(element_id)}',")
        w(f"            FX=TFX_{index},")
        w(f"            FY=TFY_{index},")
        w(f"            FZ=TFZ_{index},")
        w("        ),")
    w("    ),")
    w(");")
    w()
