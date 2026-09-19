"""The builders' contract: one request in, one named contribution out.

``SceneRequest`` carries the model and every optional source a scene can be built from.
``SceneContribution`` is what one builder produces: named channels the assembly merges, so a
builder that later adds views or diagnostics fills a field no call site has to learn about.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.run import AnalysisRun
from tuba.analysis.states import GeometryState
from tuba.clash.types import ClashResult
from tuba.load_path import LoadPathReport
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.routing.types import PipeRouteResult
from tuba.rules import RuleResult
from tuba.visualization.scene import (
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneObject,
    ViewState,
)


@dataclass(frozen=True)
class SceneBuildOptions:
    include_elements: bool = True
    include_supports: bool = True
    include_obstacles: bool = True
    include_loads: bool = True
    include_imported_components: bool = True
    include_physical: bool = True
    include_quantities: bool = True
    include_attributes: bool = True
    include_physical_envelopes: bool = False
    include_analysis_mesh: bool = False
    clearance_m: float = 0.0
    include_cost_overlays: bool = False
    cost_metric: str = "insulation_cost"


@dataclass(frozen=True)
class SceneRequest:
    """Everything one scene build reads: the model plus the sources already computed for it."""

    model: TubaModel
    options: SceneBuildOptions | None = None
    route_results: Iterable[PipeRouteResult] | None = None
    clash_results: Iterable[ClashResult] | None = None
    operating_clash_results: Iterable[ClashResult] | None = None
    rule_results: Iterable[RuleResult] | None = None
    load_path_report: LoadPathReport | None = None
    analysis_runs: Iterable[AnalysisRun] = ()
    result_states: Iterable[ResultState] | None = None
    geometry_states: Iterable[GeometryState] | None = None
    analysis_meshes: Iterable[AnalysisMesh] | None = None
    include_analysis_mesh: bool | None = None
    ifc_guid_map: dict[str | EntityRef, str] | None = None
    ifc_context: dict[str, Any] | None = None
    field_notes: Iterable[dict[str, Any]] | None = None
    #: What the review is for, when that is not the usual "read the fields".
    #: ``"contact"`` marks a staged contact study: the reader's question is what
    #: the shoes did, so the pipe is coloured neutrally and no scalar field
    #: tints it. A review that merely rests on a shoe leaves this unset - the
    #: viewer used to infer it from the presence of contact records, which took
    #: the stress legend off every review with a friction shoe in it.
    review_focus: str | None = None
    scene_id: str | None = None
    model_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class SceneContribution:
    """What one builder produced, in named channels the assembly merges."""

    objects: tuple[SceneObject, ...] = ()
    assets: tuple[GeometryAsset, ...] = ()
    overlays: tuple[Overlay, ...] = ()
    issues: tuple[Issue, ...] = ()
    route_reviews: tuple[RouteReview, ...] = ()
    views: tuple[ViewState, ...] = ()
    diagnostics: tuple[SceneDiagnostic, ...] = ()
