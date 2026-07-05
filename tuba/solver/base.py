"""
tuba.solver.base — Abstract solver interface and result containers.

Every solver backend (Code_Aster, CalculiX, …) must subclass
:class:`BaseSolver` and populate :class:`FEAResults`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class NodeResult:
    """Per-node result quantities."""

    node_id: str
    displacement: np.ndarray  # shape (6,) — ux, uy, uz, rx, ry, rz
    reaction_force: Optional[np.ndarray] = None  # shape (6,) — Fx, Fy, Fz, Mx, My, Mz


@dataclass
class ElementResult:
    """Per-element result quantities (at each end-node)."""

    element_id: str
    # Internal forces at node 1 (start)
    forces_n1: np.ndarray  # shape (6,) — N, Vy, Vz, Mx, My, Mz
    # Internal forces at node 2 (end)
    forces_n2: np.ndarray  # shape (6,)
    # Stress scalars
    von_mises_n1: float = 0.0
    von_mises_n2: float = 0.0
    max_von_mises: float = 0.0


@dataclass
class FEAResults:
    """Container holding the full set of results from a solver run.

    Provides convenience accessors used by the compliance evaluator and
    the visualiser.
    """

    solver_name: str
    load_case: Optional[str] = None

    node_results: Dict[str, NodeResult] = field(default_factory=dict)
    element_results: Dict[str, ElementResult] = field(default_factory=dict)
    analysis_node_results: Dict[str, NodeResult] = field(default_factory=dict)
    parser_diagnostics: List[str] = field(default_factory=list)

    # Path to the raw result file (e.g. .rmed)
    result_file: Optional[Path] = None

    # Raw meshio mesh (if available) for visualisation
    raw_mesh: Any = None

    # Reference to original model for visualization, SIFs, etc.
    _model: Optional[Any] = None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_displacement(self, node_id: str) -> np.ndarray:
        return self.node_results[node_id].displacement

    def get_analysis_displacement(self, node_id: str) -> np.ndarray:
        return self.analysis_node_results[node_id].displacement

    def get_reaction(self, node_id: str) -> Optional[np.ndarray]:
        nr = self.node_results.get(node_id)
        return nr.reaction_force if nr else None

    def get_forces(self, element_id: str) -> Dict[str, np.ndarray]:
        er = self.element_results[element_id]
        return {"n1": er.forces_n1, "n2": er.forces_n2}

    def get_max_von_mises(self, element_id: str) -> float:
        return self.element_results[element_id].max_von_mises

    # ------------------------------------------------------------------
    # Visualisation shortcuts (delegate to tuba.plotting)
    # ------------------------------------------------------------------

    def plot_deformed(self, scale: float = 50.0, show_undeformed: bool = True, **kwargs):
        """Show the deformed pipe shape."""
        from tuba.plotting.plots import plot_deformed
        return plot_deformed(self, scale=scale, show_undeformed=show_undeformed, **kwargs)

    def plot_stress(self, cmap: str = "jet", **kwargs):
        """Color-map Von Mises stress on the pipe surface."""
        from tuba.plotting.plots import plot_stress
        return plot_stress(self, cmap=cmap, **kwargs)

    def plot_displacement_vectors(self, scale: float = 50.0, **kwargs):
        """Show displacement arrow glyphs."""
        from tuba.plotting.plots import plot_displacement_vectors
        return plot_displacement_vectors(self, scale=scale, **kwargs)

    def plot_reactions(self, scale: float = 1e-3, **kwargs):
        """Show reaction force arrow glyphs at supports."""
        from tuba.plotting.plots import plot_reactions
        return plot_reactions(self, scale=scale, **kwargs)

    def plot_temperature(self, cmap: str = "coolwarm", **kwargs):
        """Color-map temperature distribution."""
        from tuba.plotting.plots import plot_temperature
        return plot_temperature(self, cmap=cmap, **kwargs)

    def plot_deformed_stress(
        self,
        deform_scale: float = 50.0,
        cmap: str = "turbo",
        export_html: Optional[str] = None,
        **kwargs,
    ):
        """Combined deformed shape colored by Von Mises stress — the primary view."""
        from tuba.plotting.plots import plot_deformed_stress
        return plot_deformed_stress(
            self,
            deform_scale=deform_scale,
            cmap=cmap,
            export_html=export_html,
            **kwargs,
        )

    def export_ply(self, path: str, scalar: str = "von_mises"):
        """Export tubes with vertex-color stress to PLY for Blender."""
        from tuba.plotting.export import export_ply
        export_ply(self, path, scalar=scalar)

    def export_gltf(self, path: str):
        """Export to glTF for universal 3-D viewing."""
        from tuba.plotting.export import export_gltf
        export_gltf(self, path)


# ---------------------------------------------------------------------------
# Abstract solver
# ---------------------------------------------------------------------------

class BaseSolver(ABC):
    """Interface that every solver backend must implement."""

    @abstractmethod
    def solve(self, model, load_case_name: Optional[str] = None) -> FEAResults:
        """Run the analysis and return populated :class:`FEAResults`."""
        ...
