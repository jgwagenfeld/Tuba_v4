"""Project solver displacement result states onto model centerlines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.model import Element, TubaModel
from tuba.refs import EntityRef


@dataclass(frozen=True)
class DeformedCenterline:
    entity: EntityRef
    geometry_state_id: str
    points: tuple[tuple[float, float, float], ...]
    source_mesh_nodes: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


def project_deformed_centerline(
    *,
    model: TubaModel,
    element: Element,
    result_state: ResultState,
    geometry_state: GeometryState,
    analysis_mesh: AnalysisMesh | None = None,
) -> DeformedCenterline:
    factor = geometry_state.displacement_scale * geometry_state.safety_factor
    diagnostics: list[str] = []

    node_ids: tuple[str, ...]
    if element.type == "pipe_bend":
        generated = _generated_bend_nodes(element, analysis_mesh)
        if generated and all(node_id in result_state.node_displacements for node_id in generated):
            node_ids = (element.n1, *generated, element.n2)
        else:
            node_ids = (element.n1, element.n2)
            diagnostics.append("bend_displacement_interpolated")
    else:
        node_ids = (element.n1, element.n2)

    points = tuple(
        _project_node(model, analysis_mesh, result_state, node_id, factor)
        for node_id in node_ids
    )
    return DeformedCenterline(
        entity=EntityRef("element", element.id),
        geometry_state_id=geometry_state.id,
        points=points,
        source_mesh_nodes=node_ids,
        diagnostics=tuple(diagnostics),
    )


def _generated_bend_nodes(element: Element, analysis_mesh: AnalysisMesh | None) -> tuple[str, ...]:
    if analysis_mesh is None:
        return ()
    generated: list[tuple[float, int, str]] = []
    element_ref = EntityRef("element", element.id)
    for node_id, source in analysis_mesh.node_sources.items():
        if source.source_ref != element_ref or source.role != "generated_bend_node":
            continue
        parametric_t = source.parametric_t if source.parametric_t is not None else 0.0
        segment_index = source.segment_index if source.segment_index is not None else 0
        generated.append((float(parametric_t), int(segment_index), node_id))
    return tuple(node_id for _parametric_t, _segment_index, node_id in sorted(generated))


def _project_node(
    model: TubaModel,
    analysis_mesh: AnalysisMesh | None,
    result_state: ResultState,
    node_id: str,
    factor: float,
) -> tuple[float, float, float]:
    point = _base_point(model, analysis_mesh, node_id)
    displacement = np.asarray(result_state.node_displacements.get(node_id, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float)
    projected = point + displacement[:3] * factor
    return tuple(float(value) for value in projected)


def _base_point(model: TubaModel, analysis_mesh: AnalysisMesh | None, node_id: str) -> np.ndarray:
    if node_id in model.nodes:
        return np.asarray(model.nodes[node_id].coords, dtype=float)
    if analysis_mesh is not None and node_id in analysis_mesh.nodes:
        return np.asarray(analysis_mesh.nodes[node_id], dtype=float)
    raise KeyError(f"Cannot project unknown node {node_id!r}.")
