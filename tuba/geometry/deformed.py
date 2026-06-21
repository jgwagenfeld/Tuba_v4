"""Derived deformed envelopes for clash, routing, and review workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.projection import project_deformed_centerline
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.geometry.spatial import SpatialIndex
from tuba.model import TubaModel
from tuba.physical import physical_properties_for_element
from tuba.refs import EntityRef


@dataclass(frozen=True)
class DeformedEnvelope:
    entity: EntityRef
    geometry_state_id: str
    envelope_type: str
    polyline: tuple[tuple[float, float, float], ...]
    radius_m: float
    bounds: tuple[float, float, float, float, float, float]
    source_mesh_nodes: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


_ENVELOPE_CACHE: dict[tuple[Any, ...], tuple[DeformedEnvelope, ...]] = {}


def build_deformed_envelopes(
    *,
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    envelope_type: str = "insulation",
    clearance_m: float = 0.0,
    analysis_mesh: AnalysisMesh | None = None,
) -> tuple[DeformedEnvelope, ...]:
    cache_key = (
        id(model),
        int(getattr(model, "revision", 0)),
        result_state.id,
        geometry_state.id,
        envelope_type,
        float(clearance_m),
        id(analysis_mesh) if analysis_mesh is not None else None,
    )
    cached = _ENVELOPE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    envelopes = tuple(
        _build_element_envelope(
            model=model,
            result_state=result_state,
            geometry_state=geometry_state,
            analysis_mesh=analysis_mesh,
            envelope_type=envelope_type,
            clearance_m=clearance_m,
            element=element,
        )
        for element in model.elements
    )
    _ENVELOPE_CACHE[cache_key] = envelopes
    return envelopes


def build_deformed_envelope_index(envelopes: tuple[DeformedEnvelope, ...]) -> SpatialIndex[str]:
    return SpatialIndex.from_bounds((str(envelope.entity), envelope.bounds) for envelope in envelopes)


def _build_element_envelope(
    *,
    model: TubaModel,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None,
    envelope_type: str,
    clearance_m: float,
    element: Any,
) -> DeformedEnvelope:
    projected = project_deformed_centerline(
        model=model,
        element=element,
        result_state=result_state,
        geometry_state=geometry_state,
        analysis_mesh=analysis_mesh,
    )
    radius = _radius_for_envelope(model, element, envelope_type, clearance_m)
    return DeformedEnvelope(
        entity=EntityRef("element", element.id),
        geometry_state_id=geometry_state.id,
        envelope_type=envelope_type,
        polyline=projected.points,
        radius_m=radius,
        bounds=_bounds_for_polyline(projected.points, radius),
        source_mesh_nodes=projected.source_mesh_nodes,
        diagnostics=projected.diagnostics,
        metadata={
            "load_case": geometry_state.load_case,
            "result_state_id": result_state.id,
            "safety_factor": geometry_state.safety_factor,
        },
    )


def _radius_for_envelope(model: TubaModel, element: Any, envelope_type: str, clearance_m: float) -> float:
    props = physical_properties_for_element(model, element)
    if envelope_type == "bare":
        return props.bare_radius_m
    if envelope_type == "insulation":
        return props.effective_radius_m
    if envelope_type == "clearance":
        return props.effective_radius_m + float(clearance_m)
    if envelope_type == "maintenance":
        return props.effective_radius_m + float(clearance_m)
    if envelope_type == "wind":
        return props.wind_diameter_m / 2.0
    raise ValueError(f"Unknown deformed envelope type {envelope_type!r}.")


def _bounds_for_polyline(
    polyline: tuple[tuple[float, float, float], ...],
    radius: float,
) -> tuple[float, float, float, float, float, float]:
    points = np.asarray(polyline, dtype=float)
    lo = points.min(axis=0) - radius
    hi = points.max(axis=0) + radius
    return tuple(float(value) for value in (*lo, *hi))
