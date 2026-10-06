"""Analysis study, mesh, result, and geometry-state records."""

from tuba.analysis.mesh import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.analysis.provenance import (
    SolverInputIdentity,
    build_solver_input_identity,
    validate_solver_input_identity,
)
from tuba.analysis.projection import DeformedCenterline, project_deformed_centerline
from tuba.analysis.results import ResultState
from tuba.analysis.run import AnalysisRun
from tuba.analysis.states import (
    GeometryState,
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.analysis.study import AnalysisStudy


def run_mesh_convergence(*args, **kwargs):
    """Compare authentic Code_Aster runs at Python-configured mesh scales."""
    from tuba.analysis.mesh_convergence import run_mesh_convergence as run
    return run(*args, **kwargs)

__all__ = [
    "AnalysisMesh",
    "AnalysisRun",
    "AnalysisStudy",
    "DeformedCenterline",
    "GeometryState",
    "MeshElementSource",
    "MeshNodeSource",
    "ResultState",
    "SolverInputIdentity",
    "build_solver_input_identity",
    "create_cold_geometry_state",
    "create_operating_geometry_state",
    "create_visual_deformed_geometry_state",
    "project_deformed_centerline",
    "validate_solver_input_identity",
    "run_mesh_convergence",
]
