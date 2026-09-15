"""Put CFD clouds, Python functions and route tables onto operation fields.

Each helper evaluates its source once, in Python, and writes ordinary operation
fields: node temperatures for ``temperature``, and one element field per element
for ``pressure``, ``wind`` and ``line_load``. The model keeps only the numbers the
solver receives, so fingerprints, saved models and reports stay exact.
"""

from __future__ import annotations

import math
from typing import Callable, List, NamedTuple, Optional, Sequence

import numpy as np

from tuba.model import Element, Operation, OperationField, TubaModel, sample_bend_geometry
from tuba.physical import physical_properties_for_element

_QUANTITIES = ("temperature", "pressure", "wind", "line_load")
_DIRECTED = ("wind", "line_load")
# Builder stations are running float sums, so a table ending exactly at a route's last
# station can miss it by float noise; the line-load station check uses the same tolerance.
_STATION_NOISE = 1e-9


class _Target(NamedTuple):
    name: str  # node id for temperature, element id otherwise
    position: np.ndarray
    station: Optional[float]
    elements: tuple[Element, ...]  # the selected elements at this target


def field_from_cloud(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    points,
    values,
    *,
    capture_radius: Optional[float] = None,
    direction: Optional[Sequence[float]] = None,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> List[OperationField]:
    """Average a point cloud onto nodes (temperature) or elements (pressure, wind, line_load).

    A target takes the mean of the values within ``capture_radius`` metres of it, by
    default 1.25 x the largest bare outer radius of the selected elements there, so a
    ring of wall points around a centreline node gives its circumferential mean.
    Targets with no point inside are refused, and then nothing is written.
    """
    targets = _targets(
        model, quantity, direction, group=group, route_id=route_id,
        station_start=station_start, station_end=station_end, element_ids=element_ids,
    )
    cloud = np.asarray(points, dtype=float)
    samples = np.asarray(values, dtype=float)
    if cloud.ndim != 2 or cloud.shape[1] != 3 or cloud.shape[0] == 0 or samples.shape != (cloud.shape[0],):
        raise ValueError("points must have shape (N, 3) and values shape (N,), with N >= 1.")
    if not (np.all(np.isfinite(cloud)) and np.all(np.isfinite(samples))):
        raise ValueError("points and values must be finite.")
    if capture_radius is not None and not (math.isfinite(capture_radius) and capture_radius > 0.0):
        raise ValueError("capture_radius must be a finite distance greater than zero, in metres.")

    sampled: list[tuple[_Target, float]] = []
    missed: list[tuple[_Target, float, float]] = []
    for target in targets:
        radius = capture_radius
        if radius is None:
            radius = 1.25 * max(physical_properties_for_element(model, elem).bare_radius_m for elem in target.elements)
        # ponytail: one target at a time keeps memory at O(points) but time at O(targets x points);
        # switch to a KD-tree if clouds or models outgrow it.
        distances = np.linalg.norm(cloud - target.position, axis=1)
        inside = distances <= radius
        if inside.any():
            sampled.append((target, float(samples[inside].mean())))
        else:
            missed.append((target, float(distances.min()), radius))
    if missed:
        listed = "; ".join(
            f"{target.name!r} nearest point {nearest:.4g} m, radius {radius:.4g} m" for target, nearest, radius in missed[:10]
        )
        more = f"; and {len(missed) - 10} more" if len(missed) > 10 else ""
        raise ValueError(
            f"{len(missed)} target(s) have no cloud point within the capture radius: {listed}{more}. "
            "Check the cloud's units (mm vs m), its coordinate frame and that it covers the selection, "
            "or pass a larger capture_radius."
        )
    return _write(operation, quantity, direction, sampled)


def field_from_function(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    function: Callable[[float, float, float], float],
    *,
    direction: Optional[Sequence[float]] = None,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> List[OperationField]:
    """Evaluate ``function(x, y, z)`` at each node, or at each element's midpoint (arc midpoint on bends)."""
    if not callable(function):
        raise TypeError("function must be a Python callable taking x, y, z; formula strings are not evaluated.")
    sampled: list[tuple[_Target, float]] = []
    for target in _targets(
        model, quantity, direction, group=group, route_id=route_id,
        station_start=station_start, station_end=station_end, element_ids=element_ids,
    ):
        x, y, z = (float(value) for value in target.position)
        value = float(function(x, y, z))
        if not math.isfinite(value):
            raise ValueError(f"function returned {value} at {target.name!r}.")
        sampled.append((target, value))
    return _write(operation, quantity, direction, sampled)


def field_from_route_table(
    model: TubaModel,
    operation: Operation,
    quantity: str,
    route_id: str,
    table: Sequence[Sequence[float]],
    *,
    direction: Optional[Sequence[float]] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
) -> List[OperationField]:
    """Interpolate a ``(station, value)`` table linearly along one route.

    Targets outside the table's stations are refused rather than extrapolated;
    ``station_start`` and ``station_end`` limit the helper to the part the table covers.
    """
    if not isinstance(route_id, str) or not route_id:
        raise ValueError(
            "field_from_route_table needs the route_id of the route the table follows; "
            "name unnamed runs with model.pipe(..., route=...)."
        )
    rows = [(float(station), float(value)) for station, value in table]
    stations = np.array([station for station, _ in rows])
    table_values = np.array([value for _, value in rows])
    if (
        len(rows) < 2
        or not (np.all(np.isfinite(stations)) and np.all(np.isfinite(table_values)))
        or np.any(np.diff(stations) <= 0.0)
    ):
        raise ValueError("table needs at least 2 finite (station, value) rows with strictly increasing stations.")
    sampled: list[tuple[_Target, float]] = []
    for target in _targets(
        model, quantity, direction, route_id=route_id, station_start=station_start, station_end=station_end
    ):
        if target.station is None:
            raise ValueError(f"{target.name!r} has no station metadata, so the route table cannot place it.")
        if not stations[0] - _STATION_NOISE <= target.station <= stations[-1] + _STATION_NOISE:
            raise ValueError(
                f"{target.name!r} sits at station {target.station:g}, outside the table's stations "
                f"{stations[0]:g} to {stations[-1]:g}; narrow the selection with station_start/station_end."
            )
        sampled.append((target, float(np.interp(target.station, stations, table_values))))
    return _write(operation, quantity, direction, sampled)


def _targets(
    model: TubaModel,
    quantity: str,
    direction: Optional[Sequence[float]],
    *,
    group: Optional[str] = None,
    route_id: Optional[str] = None,
    station_start: Optional[float] = None,
    station_end: Optional[float] = None,
    element_ids: Optional[List[str]] = None,
) -> list[_Target]:
    if quantity not in _QUANTITIES:
        raise ValueError(f"quantity must be one of {', '.join(_QUANTITIES)}; got {quantity!r}.")
    if (direction is None) == (quantity in _DIRECTED):
        raise ValueError(f"{quantity} {'needs a direction' if quantity in _DIRECTED else 'takes no direction'}.")
    # A probe field picks the scope exactly as add_field does, and selection applies the field rules.
    probe = Operation("probe").add_field(
        quantity, 0.0, group=group, route_id=route_id, station_start=station_start,
        station_end=station_end, element_ids=element_ids, direction=direction,
    )
    selected = model.resolve_operation_field_elements(probe)
    if not selected:
        raise ValueError(f"The selection holds no elements that can carry {quantity!r}.")
    if quantity != "temperature":
        return [
            _Target(
                elem.id,
                _midpoint(model, elem),
                None if elem.station_start is None or elem.station_end is None
                else (float(elem.station_start) + float(elem.station_end)) / 2.0,
                (elem,),
            )
            for elem in selected
        ]
    nodes: dict[str, _Target] = {}
    for elem in selected:
        for node_id, station in ((elem.n1, elem.station_start), (elem.n2, elem.station_end)):
            known = nodes.get(node_id)
            if known is None:
                nodes[node_id] = _Target(
                    node_id,
                    np.asarray(model.nodes[node_id].coords, dtype=float),
                    None if station is None else float(station),
                    (elem,),
                )
            else:
                nodes[node_id] = known._replace(
                    station=known.station if known.station is not None else (None if station is None else float(station)),
                    elements=known.elements + (elem,),
                )
    return list(nodes.values())


def _midpoint(model: TubaModel, elem: Element) -> np.ndarray:
    start = np.asarray(model.nodes[elem.n1].coords, dtype=float)
    if elem.type != "pipe_bend":
        return (start + np.asarray(model.nodes[elem.n2].coords, dtype=float)) / 2.0
    if elem.bend_geometry is None:
        raise ValueError(f"Bend {elem.id!r} has no stored bend_geometry, so its arc midpoint is unknown.")
    return sample_bend_geometry(start, elem.bend_geometry, n_segments=2)[1]


def _write(
    operation: Operation,
    quantity: str,
    direction: Optional[Sequence[float]],
    sampled: list[tuple[_Target, float]],
) -> List[OperationField]:
    if quantity == "temperature":
        return [operation.add_field("temperature", value, node_ids=[target.name]) for target, value in sampled]
    return [
        operation.add_field(quantity, value, element_ids=[target.name], direction=direction)
        for target, value in sampled
    ]
