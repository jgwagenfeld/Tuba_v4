"""
tuba.solver.aster — Code_Aster solver adapter for Tuba v4.

Automates headless Code_Aster execution: generates the mesh (``.mail``),
command file (``.comm``), and export configuration, invokes the solver
via WSL or Docker, and parses results back into :class:`FEAResults`.

The ``.comm`` file follows the Tuba v2 TUBA_COMM_BASE pattern and uses the
``TUYAU_3M`` beam-shell modelisation for accurate pipe stress analysis.
"""

from __future__ import annotations

import logging
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from tuba.model import (
    Element,
    LoadCase,
    TubaModel,
    PipeSection,
    BarSection,
    CableSection,
    RectangularSection,
    IBeamSection,
)
from tuba.solver.base import (
    BaseSolver,
    ElementResult,
    FEAResults,
    NodeResult,
)
from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, run_code_aster_export
from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.refs import EntityRef

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SegmentMidpoint(NamedTuple):
    node_id: str
    start_node_id: str
    end_node_id: str
    source_element_id: str
    segment_index: int
    coords: np.ndarray

def _node_label(node_id: str) -> str:
    """Convert a Tuba node id (``'N0'``, ``'N12'``) to a plain numeric label.

    Code_Aster mesh nodes are referenced by integer label.  We strip the
    leading ``N`` and use the numeric suffix directly.
    """
    return node_id.lstrip("N")


def _elem_label(elem_id: str) -> str:
    """Convert a Tuba element id (``'E0'``) to a numeric label."""
    return elem_id.lstrip("E")


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class CodeAsterSolver(BaseSolver):
    """Headless Code_Aster backend for piping stress analysis.

    Parameters
    ----------
    work_dir : str or Path, optional
        Explicit working directory.  If *None* a temporary directory is
        created for each :meth:`solve` invocation.
    exec_method : ``'auto'`` | ``'python_bridge'`` | ``'command'`` | ``'wsl'`` | ``'docker'``
        How to invoke Code_Aster.  ``'auto'`` tries WSL first and falls back to
        Docker when no WSL runner is installed. ``'wsl'`` runs the study inside
        Windows Subsystem for Linux. ``'docker'`` launches a container from
        *docker_image*.
    wsl_distro : str, optional
        WSL distro name passed to ``wsl -d <name>``.  Defaults to
        ``TUBA_CODE_ASTER_WSL_DISTRO`` when set.
    docker_image : str, optional
        Docker image name, e.g. ``'simvia/code_aster:stable'``.
        Required when *exec_method* is ``'docker'`` or the auto Docker fallback
        is used.
    runner_command : str, optional
        Shell command used inside WSL or the container before ``study.export``.
        When omitted, Tuba tries ``as_run``, ``aster``, and the documented
        ``conda run -n base aster`` path.
    """

    # Name reported in :class:`FEAResults`
    SOLVER_NAME = "Code_Aster"

    def __init__(
        self,
        work_dir: Optional[str] = None,
        exec_method: Optional[str] = None,
        docker_image: Optional[str] = None,
        wsl_distro: Optional[str] = None,
        runner_command: Optional[str] = None,
        bridge_python: Optional[str] = None,
        timeout_seconds: int = 7200,
    ) -> None:
        self.work_dir = Path(work_dir) if work_dir else None
        self.exec_method = exec_method or os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto")
        self.docker_image = docker_image or os.environ.get("TUBA_CODE_ASTER_DOCKER_IMAGE") or "simvia/code_aster:stable"
        self.wsl_distro = wsl_distro or os.environ.get("TUBA_CODE_ASTER_WSL_DISTRO")
        self.runner_command = runner_command or os.environ.get("TUBA_CODE_ASTER_RUNNER")
        self.bridge_python = bridge_python or os.environ.get("TUBA_CODE_ASTER_PYTHON")
        self.timeout_seconds = timeout_seconds

    # ==================================================================
    # Public API
    # ==================================================================

    def solve(
        self,
        model: TubaModel,
        load_case_name: Optional[str] = None,
    ) -> FEAResults:
        """Run a static piping analysis through Code_Aster.

        Parameters
        ----------
        model : TubaModel
            Fully populated Tuba model.
        load_case_name : str, optional
            Name of the load case inside *model*.  Uses the first defined
            load case when *None*.

        Returns
        -------
        FEAResults
            Populated result container.

        Raises
        ------
        ValueError
            If the requested load case does not exist.
        RuntimeError
            If Code_Aster returns a non-zero exit code.
        """
        # Resolve load case ------------------------------------------------
        if load_case_name is None:
            if not model.load_cases:
                raise ValueError("Model has no load cases defined.")
            load_case_name = next(iter(model.load_cases))
        if load_case_name not in model.load_cases:
            raise ValueError(
                f"Load case '{load_case_name}' not found. "
                f"Available: {list(model.load_cases.keys())}"
            )
        load_case = model.load_cases[load_case_name]

        # Prepare work directory -------------------------------------------
        if self.work_dir is not None:
            wdir = self.work_dir
            wdir.mkdir(parents=True, exist_ok=True)
        else:
            wdir = Path(tempfile.mkdtemp(prefix="tuba_aster_"))
        logger.info("Code_Aster work directory: %s", wdir)

        # Generate input files ---------------------------------------------
        mail_path = wdir / "study.mail"
        comm_path = wdir / "study.comm"
        export_path = wdir / "study.export"

        self._write_mail(model, mail_path)
        self._write_comm(model, load_case, comm_path)
        self._write_export(wdir)

        # Execute solver ---------------------------------------------------
        self._execute(wdir)

        # Parse results ----------------------------------------------------
        results = self._parse_results(model, wdir)
        results.load_case = load_case_name
        return results

    def export_study(
        self,
        model: TubaModel,
        load_case_name: Optional[str] = None,
        output_dir: Optional[str | Path] = None,
    ) -> Path:
        """Generate Code_Aster input files (.comm, .mail, .export) without running the solver.

        Parameters
        ----------
        model : TubaModel
            Fully populated Tuba model.
        load_case_name : str, optional
            Name of the load case inside *model*.
        output_dir : str or Path, optional
            Directory to write the files to. Defaults to self.work_dir or a temporary directory.

        Returns
        -------
        Path
            The path to the output directory containing the study files.
        """
        # Resolve load case ------------------------------------------------
        if load_case_name is None:
            if not model.load_cases:
                raise ValueError("Model has no load cases defined.")
            load_case_name = next(iter(model.load_cases))
        if load_case_name not in model.load_cases:
            raise ValueError(
                f"Load case '{load_case_name}' not found. "
                f"Available: {list(model.load_cases.keys())}"
            )
        load_case = model.load_cases[load_case_name]

        # Prepare directory ------------------------------------------------
        if output_dir is not None:
            wdir = Path(output_dir)
            wdir.mkdir(parents=True, exist_ok=True)
        elif self.work_dir is not None:
            wdir = self.work_dir
            wdir.mkdir(parents=True, exist_ok=True)
        else:
            wdir = Path(tempfile.mkdtemp(prefix="tuba_aster_"))

        # Generate input files ---------------------------------------------
        mail_path = wdir / "study.mail"
        comm_path = wdir / "study.comm"

        self._write_mail(model, mail_path)
        self._write_comm(model, load_case, comm_path)
        self._write_export(wdir)

        return wdir

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: Optional[str] = None,
        output_dir: Optional[str | Path] = None,
    ) -> AnalysisStudy:
        """Generate Code_Aster input files plus a traceable analysis manifest."""
        if load_case_name is None:
            if not model.load_cases:
                raise ValueError("Model has no load cases defined.")
            load_case_name = next(iter(model.load_cases))
        if load_case_name not in model.load_cases:
            raise ValueError(
                f"Load case '{load_case_name}' not found. "
                f"Available: {list(model.load_cases.keys())}"
            )
        load_case = model.load_cases[load_case_name]

        if output_dir is not None:
            wdir = Path(output_dir)
            wdir.mkdir(parents=True, exist_ok=True)
        elif self.work_dir is not None:
            wdir = self.work_dir
            wdir.mkdir(parents=True, exist_ok=True)
        else:
            wdir = Path(tempfile.mkdtemp(prefix="tuba_aster_"))

        model_revision = int(getattr(model, "revision", 0))
        mail_path = wdir / "study.mail"
        comm_path = wdir / "study.comm"
        export_path = wdir / "study.export"
        manifest_path = wdir / "study_manifest.json"
        sidecar_path = wdir / "study_tuba_fem.json"

        mesh_id = f"analysis_mesh:{load_case_name}"
        analysis_mesh = self._write_mail(
            model,
            mail_path,
            analysis_mesh_id=mesh_id,
            model_revision=model_revision,
        )
        if analysis_mesh is None:
            raise RuntimeError("Analysis mesh provenance was not collected.")
        from tuba.solver.aster_sidecar import SolverNameMap, build_solver_name_map, dump_solver_sidecar

        solver_names = list(analysis_mesh.groups.keys()) + list(analysis_mesh.elements.keys())
        name_map = build_solver_name_map(solver_names)
        solver_name_map = SolverNameMap(name_map)
        lineage = {
            name_map[element_id]: str(source.source_ref)
            for element_id, source in analysis_mesh.element_sources.items()
            if element_id in name_map
        }
        dump_solver_sidecar(
            sidecar_path,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            analysis_mesh_id=analysis_mesh.id,
            name_map=name_map,
            lineage=lineage,
        )
        self._write_mail(model, mail_path, name_map=solver_name_map)
        self._write_comm(model, load_case, comm_path, name_map=solver_name_map)
        self._write_export(wdir)

        study = AnalysisStudy(
            id=f"analysis_study:{load_case_name}",
            model_revision=model_revision,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            work_dir=str(wdir),
            input_files={
                "mail": str(mail_path),
                "comm": str(comm_path),
                "export": str(export_path),
                "manifest": str(manifest_path),
                "sidecar": str(sidecar_path),
            },
            mesh_id=analysis_mesh.id,
            metadata={"project_name": model.project_name},
        )
        manifest = {
            "study": study.to_dict(),
            "analysis_mesh": analysis_mesh.to_dict(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return study

    def export_mixed_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str,
        output_dir: str | Path,
    ) -> AnalysisStudy:
        """Generate a MED-backed mixed Code_Aster study without running the solver."""
        from tuba.solver.mixed_study import MixedCodeAsterStudyExporter

        return MixedCodeAsterStudyExporter().export_analysis_study(model, load_case_name, output_dir)

    def solve_exported_study(self, model: TubaModel, study: AnalysisStudy) -> FEAResults:
        """Execute an already-exported Code_Aster analysis study and parse its artifacts."""
        work_dir = Path(study.work_dir)
        self._execute(work_dir)
        return self.parse_result_artifacts(model, work_dir, study.load_case)


    # ==================================================================
    # Mesh generation (.mail)
    # ==================================================================

    # Number of linear subdivisions per pipe bend element before writing
    # each solver segment as a quadratic SEG3 pipe element.
    _BEND_SEGMENTS = 16

    def _write_mail(
        self,
        model: TubaModel,
        path: Path,
        *,
        analysis_mesh_id: str | None = None,
        model_revision: int = 0,
        name_map: Callable[[str], str] | None = None,
    ) -> AnalysisMesh | None:
        """Generate the Code_Aster plain-text mesh file.

        Uses the **Gmsh OCC kernel** to construct proper circular arcs
        for pipe bends and discretise them into quadratic SEG3 pipe elements.
        Straight pipes are represented as single SEG3 elements.  Non-pipe
        beams, bars, and cables remain SEG2 line elements.

        The mesh is written in the Aster native format
        (``FORMAT='ASTER'``) so that ``LIRE_MAILLAGE`` can read it
        directly.
        """
        lines: List[str] = []
        N = self._BEND_SEGMENTS  # shorthand
        map_name = name_map or (lambda value: value)

        # --- Ordered node / element lists ---------------------------------
        node_ids = list(model.nodes.keys())
        pipe_straights = [e for e in model.elements if e.type == "pipe_straight"]
        pipe_bends = [e for e in model.elements if e.type == "pipe_bend"]
        beam_elems = [e for e in model.elements if e.type == "beam"]
        bar_elems = [e for e in model.elements if e.type == "bar"]
        cable_elems = [e for e in model.elements if e.type == "cable"]

        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        bend_elems = pipe_bends

        # --- Compute intermediate bend-node coordinates via Gmsh ----------
        # Dict: elem.id → list of (node_name, coord_array) for the
        #        N-1 intermediate nodes along the arc.
        bend_intermediate: Dict[str, List[Tuple[str, np.ndarray]]] = {}

        if bend_elems:
            bend_intermediate = self._compute_bend_nodes_gmsh(
                model, bend_elems, N
            )
        pipe_midpoints = self._pipe_straight_midpoint_nodes(model, pipe_straights)
        bend_segment_midpoints = self._pipe_bend_segment_midpoint_nodes(
            model,
            pipe_bends,
            bend_intermediate,
            N,
        )

        analysis_mesh = None
        if analysis_mesh_id is not None:
            analysis_mesh = self._build_analysis_mesh_from_mail_parts(
                model=model,
                mesh_id=analysis_mesh_id,
                model_revision=model_revision,
                node_ids=node_ids,
                pipe_straights=pipe_straights,
                pipe_bends=pipe_bends,
                beam_elems=beam_elems,
                bar_elems=bar_elems,
                cable_elems=cable_elems,
                bend_intermediate=bend_intermediate,
                pipe_midpoints=pipe_midpoints,
                bend_segment_midpoints=bend_segment_midpoints,
                mail_path=path,
                n_segments=N,
            )

        # --- COOR_3D ------------------------------------------------------
        lines.append("COOR_3D")
        for nid in node_ids:
            n = model.nodes[nid]
            x, y, z = n.coords
            lines.append(f"  {nid}  {x:+.10E}  {y:+.10E}  {z:+.10E}")

        for elem in bend_elems:
            for name, coord in bend_intermediate[elem.id]:
                lines.append(
                    f"  {name}  {coord[0]:+.10E}  "
                    f"{coord[1]:+.10E}  {coord[2]:+.10E}"
                )
        for midpoint in pipe_midpoints.values():
            coord = midpoint.coords
            lines.append(
                f"  {midpoint.node_id}  {coord[0]:+.10E}  "
                f"{coord[1]:+.10E}  {coord[2]:+.10E}"
            )
        for midpoint in bend_segment_midpoints.values():
            coord = midpoint.coords
            lines.append(
                f"  {midpoint.node_id}  {coord[0]:+.10E}  "
                f"{coord[1]:+.10E}  {coord[2]:+.10E}"
            )
        lines.append("FINSF")
        lines.append("")

        # --- SEG3 for pipe straights --------------------------------------
        if pipe_straights:
            lines.append("SEG3")
            for elem in pipe_straights:
                midpoint = pipe_midpoints[elem.id]
                lines.append(
                    f"  {map_name(elem.id)}  {elem.n1}  {elem.n2}  {midpoint.node_id}"
                )
            lines.append("FINSF")
            lines.append("")

        # --- SEG2 for non-pipe line elements ------------------------------
        non_pipe_straights = beam_elems + bar_elems + cable_elems
        if non_pipe_straights:
            lines.append("SEG2")
            for elem in non_pipe_straights:
                lines.append(f"  {map_name(elem.id)}  {elem.n1}  {elem.n2}")
            lines.append("FINSF")
            lines.append("")

        # --- SEG3 for bend subdivisions -----------------------------------
        if bend_elems:
            lines.append("SEG3")
            for elem in bend_elems:
                for segment_id, _, _ in self._bend_segment_node_pairs(elem, N):
                    midpoint = bend_segment_midpoints[segment_id]
                    lines.append(
                        f"  {map_name(segment_id)}  {midpoint.start_node_id}  "
                        f"{midpoint.end_node_id}  {midpoint.node_id}"
                    )
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=PipeStraights -----------------------------------
        if pipe_straights:
            lines.append(f"GROUP_MA NOM={map_name('PipeStraights')}")
            for elem in pipe_straights:
                lines.append(f"  {map_name(elem.id)}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=PipeElbows --------------------------------------
        if bend_elems:
            lines.append(f"GROUP_MA NOM={map_name('PipeElbows')}")
            for elem in bend_elems:
                for i in range(N):
                    lines.append(f"  {map_name(f'{elem.id}_s{i}')}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=AllPipes ----------------------------------------
        all_pipe_ids: List[str] = []
        for e in pipe_straights:
            all_pipe_ids.append(e.id)
        for e in bend_elems:
            all_pipe_ids.extend([f"{e.id}_s{i}" for i in range(N)])

        if all_pipe_ids:
            lines.append(f"GROUP_MA NOM={map_name('AllPipes')}")
            for eid in all_pipe_ids:
                lines.append(f"  {map_name(eid)}")
            lines.append("FINSF")
            lines.append("")

        pipe_orientation_nodes: list[str] = []
        for elem in pipe_straights:
            pipe_orientation_nodes.append(elem.n1)
        for elem in bend_elems:
            pipe_orientation_nodes.append(elem.n1)
        if pipe_orientation_nodes:
            lines.append(f"GROUP_NO NOM={map_name('PipeOrientationNodes')}")
            for node_id in dict.fromkeys(pipe_orientation_nodes):
                lines.append(f"  {node_id}")
            lines.append("FINSF")
            lines.append("")

        poutre_line_elems = pipe_straights + beam_elems
        section_group_members: dict[str, list[str]] = {}
        for elem in poutre_line_elems:
            section_group_members.setdefault(elem.section, []).append(elem.id)
        for section_name, element_ids in section_group_members.items():
            lines.append(f"GROUP_MA NOM={map_name(self._section_group_name(section_name))}")
            for element_id in element_ids:
                lines.append(f"  {map_name(element_id)}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_TUBE (for beams) ------------------------------
        if beam_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_TUBE')}")
            for elem in beam_elems:
                lines.append(f"  {map_name(elem.id)}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_BAR (for bars) --------------------------------
        if bar_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_BAR')}")
            for elem in bar_elems:
                lines.append(f"  {map_name(elem.id)}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_CABLE (for cables) ----------------------------
        if cable_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_CABLE')}")
            for elem in cable_elems:
                lines.append(f"  {map_name(elem.id)}")
            lines.append("FINSF")
            lines.append("")

        # --- Per-element groups (for COUDE assignment) --------------------
        for elem in bend_elems:
            lines.append(f"GROUP_MA NOM={map_name(elem.id)}")
            for i in range(N):
                lines.append(f"  {map_name(f'{elem.id}_s{i}')}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_NO for supports ----------------------------------------
        for sup in model.supports:
            grp_name = f"GN_{sup.node}"
            lines.append(f"GROUP_NO NOM={map_name(grp_name)}")
            lines.append(f"  {sup.node}")
            lines.append("FINSF")
            lines.append("")

        # --- All support nodes group --------------------------------------
        if model.supports:
            lines.append(f"GROUP_NO NOM={map_name('AllSupports')}")
            for sup in model.supports:
                lines.append(f"  {sup.node}")
            lines.append("FINSF")
            lines.append("")

        lines.append("FIN")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(
            "Wrote mesh: %s (%d nodes, %d elements)",
            path, len(node_ids), len(model.elements),
        )
        return analysis_mesh

    def _build_analysis_mesh_from_mail_parts(
        self,
        *,
        model: TubaModel,
        mesh_id: str,
        model_revision: int,
        node_ids: list[str],
        pipe_straights: list[Element],
        pipe_bends: list[Element],
        beam_elems: list[Element],
        bar_elems: list[Element],
        cable_elems: list[Element],
        bend_intermediate: dict[str, list[tuple[str, np.ndarray]]],
        pipe_midpoints: dict[str, _SegmentMidpoint],
        bend_segment_midpoints: dict[str, _SegmentMidpoint],
        mail_path: Path,
        n_segments: int,
    ) -> AnalysisMesh:
        nodes: dict[str, tuple[float, float, float]] = {}
        node_sources: dict[str, MeshNodeSource] = {}
        for node_id in node_ids:
            node = model.nodes[node_id]
            nodes[node_id] = tuple(float(value) for value in node.coords)
            node_sources[node_id] = MeshNodeSource(
                node_id=node_id,
                source_ref=EntityRef("node", node_id),
                role="native_node",
            )

        for elem in pipe_bends:
            for index, (node_id, coords) in enumerate(bend_intermediate.get(elem.id, []), start=1):
                nodes[node_id] = tuple(float(value) for value in coords)
                node_sources[node_id] = MeshNodeSource(
                    node_id=node_id,
                    source_ref=EntityRef("element", elem.id),
                    role="generated_bend_node",
                    parametric_t=index / n_segments,
                    segment_index=index,
                )

        for midpoint in pipe_midpoints.values():
            nodes[midpoint.node_id] = tuple(float(value) for value in midpoint.coords)
            node_sources[midpoint.node_id] = MeshNodeSource(
                node_id=midpoint.node_id,
                source_ref=EntityRef("element", midpoint.source_element_id),
                role="generated_pipe_mid_node",
                parametric_t=0.5,
                segment_index=0,
            )

        for midpoint in bend_segment_midpoints.values():
            nodes[midpoint.node_id] = tuple(float(value) for value in midpoint.coords)
            node_sources[midpoint.node_id] = MeshNodeSource(
                node_id=midpoint.node_id,
                source_ref=EntityRef("element", midpoint.source_element_id),
                role="generated_bend_mid_node",
                parametric_t=(midpoint.segment_index + 0.5) / n_segments,
                segment_index=midpoint.segment_index,
            )

        elements: dict[str, tuple[str, ...]] = {}
        element_sources: dict[str, MeshElementSource] = {}
        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        for elem in straight_elems:
            elements[elem.id] = (elem.n1, elem.n2)
            element_sources[elem.id] = MeshElementSource(
                element_id=elem.id,
                source_ref=EntityRef("element", elem.id),
                role="native_element",
            )

        for elem in pipe_bends:
            segment_ids = []
            first_segment = f"{elem.id}_s0"
            elements[first_segment] = (elem.n1, f"{elem.id}_n1")
            segment_ids.append(first_segment)
            for index in range(1, n_segments - 1):
                segment_id = f"{elem.id}_s{index}"
                elements[segment_id] = (f"{elem.id}_n{index}", f"{elem.id}_n{index + 1}")
                segment_ids.append(segment_id)
            last_segment = f"{elem.id}_s{n_segments - 1}"
            elements[last_segment] = (f"{elem.id}_n{n_segments - 1}", elem.n2)
            segment_ids.append(last_segment)
            for segment_index, segment_id in enumerate(segment_ids):
                element_sources[segment_id] = MeshElementSource(
                    element_id=segment_id,
                    source_ref=EntityRef("element", elem.id),
                    role="bend_segment",
                    segment_index=segment_index,
                )

        groups: dict[str, tuple[str, ...]] = {}
        if pipe_straights:
            groups["PipeStraights"] = tuple(elem.id for elem in pipe_straights)
        if pipe_bends:
            groups["PipeElbows"] = tuple(f"{elem.id}_s{index}" for elem in pipe_bends for index in range(n_segments))
        all_pipe_ids = [elem.id for elem in pipe_straights]
        all_pipe_ids.extend(f"{elem.id}_s{index}" for elem in pipe_bends for index in range(n_segments))
        if all_pipe_ids:
            groups["AllPipes"] = tuple(all_pipe_ids)
        pipe_orientation_nodes = [elem.n1 for elem in pipe_straights]
        pipe_orientation_nodes.extend(elem.n1 for elem in pipe_bends)
        if pipe_orientation_nodes:
            groups["PipeOrientationNodes"] = tuple(dict.fromkeys(pipe_orientation_nodes))
        section_group_members: dict[str, list[str]] = {}
        for elem in pipe_straights + beam_elems:
            section_group_members.setdefault(elem.section, []).append(elem.id)
        for section_name, element_ids in section_group_members.items():
            groups[self._section_group_name(section_name)] = tuple(element_ids)
        if beam_elems:
            groups["G_TUBE"] = tuple(elem.id for elem in beam_elems)
        if bar_elems:
            groups["G_BAR"] = tuple(elem.id for elem in bar_elems)
        if cable_elems:
            groups["G_CABLE"] = tuple(elem.id for elem in cable_elems)
        for elem in pipe_bends:
            groups[elem.id] = tuple(f"{elem.id}_s{index}" for index in range(n_segments))
        for support in model.supports:
            groups[f"GN_{support.node}"] = (support.node,)
        if model.supports:
            groups["AllSupports"] = tuple(support.node for support in model.supports)

        return AnalysisMesh(
            id=mesh_id,
            model_revision=model_revision,
            solver_name=self.SOLVER_NAME,
            nodes=nodes,
            elements=elements,
            groups=groups,
            node_sources=node_sources,
            element_sources=element_sources,
            files={"mail": str(mail_path)},
        )

    def _pipe_straight_midpoint_nodes(
        self,
        model: TubaModel,
        pipe_straights: list[Element],
    ) -> dict[str, _SegmentMidpoint]:
        midpoints: dict[str, _SegmentMidpoint] = {}
        for elem in pipe_straights:
            start = self._analysis_node_coords(model, {}, elem.n1)
            end = self._analysis_node_coords(model, {}, elem.n2)
            midpoints[elem.id] = _SegmentMidpoint(
                node_id=self._generated_midpoint_node_id(elem.id),
                start_node_id=elem.n1,
                end_node_id=elem.n2,
                source_element_id=elem.id,
                segment_index=0,
                coords=(start + end) / 2.0,
            )
        return midpoints

    def _pipe_bend_segment_midpoint_nodes(
        self,
        model: TubaModel,
        pipe_bends: list[Element],
        bend_intermediate: dict[str, list[tuple[str, np.ndarray]]],
        n_segments: int,
    ) -> dict[str, _SegmentMidpoint]:
        midpoints: dict[str, _SegmentMidpoint] = {}
        for elem in pipe_bends:
            for segment_index, (segment_id, start_id, end_id) in enumerate(
                self._bend_segment_node_pairs(elem, n_segments)
            ):
                start = self._analysis_node_coords(model, bend_intermediate, start_id)
                end = self._analysis_node_coords(model, bend_intermediate, end_id)
                midpoints[segment_id] = _SegmentMidpoint(
                    node_id=self._generated_midpoint_node_id(segment_id),
                    start_node_id=start_id,
                    end_node_id=end_id,
                    source_element_id=elem.id,
                    segment_index=segment_index,
                    coords=(start + end) / 2.0,
                )
        return midpoints

    @staticmethod
    def _bend_segment_node_pairs(elem: Element, n_segments: int) -> list[tuple[str, str, str]]:
        pairs = [(f"{elem.id}_s0", elem.n1, f"{elem.id}_n1")]
        for index in range(1, n_segments - 1):
            pairs.append((f"{elem.id}_s{index}", f"{elem.id}_n{index}", f"{elem.id}_n{index + 1}"))
        pairs.append((f"{elem.id}_s{n_segments - 1}", f"{elem.id}_n{n_segments - 1}", elem.n2))
        return pairs

    @staticmethod
    def _generated_midpoint_node_id(base_id: str) -> str:
        node_id = f"{base_id}_mid"
        if len(node_id) <= 24:
            return node_id
        digest = hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:8].upper()
        return f"N_{digest}"

    @staticmethod
    def _section_group_name(section_name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", section_name)
        group_name = f"SEC_{safe}"
        if len(group_name) <= 24:
            return group_name
        digest = hashlib.sha1(group_name.encode("utf-8")).hexdigest()[:8].upper()
        return f"SEC_{digest}"

    @staticmethod
    def _analysis_node_coords(
        model: TubaModel,
        generated_nodes: dict[str, list[tuple[str, np.ndarray]]],
        node_id: str,
    ) -> np.ndarray:
        if node_id in model.nodes:
            return np.asarray(model.nodes[node_id].coords, dtype=float)
        for nodes in generated_nodes.values():
            for generated_id, coords in nodes:
                if generated_id == node_id:
                    return np.asarray(coords, dtype=float)
        raise KeyError(f"Node {node_id!r} is not present in model or generated bend nodes.")

    # ------------------------------------------------------------------
    # Gmsh-based bend node computation
    # ------------------------------------------------------------------

    def _compute_bend_nodes_gmsh(
        self,
        model: TubaModel,
        bend_elems: List[Element],
        n_segments: int,
    ) -> Dict[str, List[Tuple[str, np.ndarray]]]:
        """Use the Gmsh OCC kernel to discretise bend arcs.

        For each bend element a proper OCC ``CircleArc`` is created from
        *n1* through the computed arc centre to *n2*.  Transfinite
        meshing with ``n_segments + 1`` nodes produces evenly spaced
        intermediate points that lie exactly on the circular arc.

        Returns
        -------
        Dict mapping ``elem.id`` → list of ``(node_name, coord_array)``
        for the ``n_segments - 1`` interior nodes.
        """
        import gmsh

        we_initialised = False
        if not gmsh.isInitialized():
            gmsh.initialize()
            we_initialised = True
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("tuba_bend_mesh")

        result: Dict[str, List[Tuple[str, np.ndarray]]] = {}

        try:
            # --- Create OCC points for every node referenced by bends -----
            bend_node_ids: set[str] = set()
            for elem in bend_elems:
                bend_node_ids.add(elem.n1)
                bend_node_ids.add(elem.n2)

            node_to_occ: Dict[str, int] = {}
            for nid in bend_node_ids:
                n = model.nodes[nid]
                x, y, z = n.coords
                tag = gmsh.model.occ.addPoint(x, y, z)
                node_to_occ[nid] = tag

            # --- Create OCC circle arcs -----------------------------------
            bend_occ_curves: Dict[str, int] = {}
            for elem in bend_elems:
                C, _axis, _r1, _theta = self._get_bend_geometry(
                    model, elem
                )
                center_tag = gmsh.model.occ.addPoint(C[0], C[1], C[2])
                arc_tag = gmsh.model.occ.addCircleArc(
                    node_to_occ[elem.n1],
                    center_tag,
                    node_to_occ[elem.n2],
                )
                bend_occ_curves[elem.id] = arc_tag

            gmsh.model.occ.synchronize()

            # --- Transfinite meshing & 1-D mesh generation ----------------
            for elem in bend_elems:
                gmsh.model.mesh.setTransfiniteCurve(
                    bend_occ_curves[elem.id], n_segments + 1
                )

            gmsh.model.mesh.generate(1)

            # --- Extract intermediate node coordinates --------------------
            for elem in bend_elems:
                curve_tag = bend_occ_curves[elem.id]
                node_tags, coords, param_coords = (
                    gmsh.model.mesh.getNodes(
                        1, curve_tag, includeBoundary=True
                    )
                )
                coords_3d = np.asarray(coords).reshape(-1, 3)

                # Sort along the curve by parametric coordinate
                sorted_idx = np.argsort(param_coords)
                sorted_tags = node_tags[sorted_idx]
                sorted_coords = coords_3d[sorted_idx]

                # The sorted list may run n1→n2 or n2→n1 depending on
                # internal OCC orientation.  Ensure n1 comes first.
                start_occ = node_to_occ[elem.n1]
                if int(sorted_tags[0]) != start_occ:
                    sorted_coords = sorted_coords[::-1]

                # Interior nodes are indices 1 … n_segments-1
                int_nodes: List[Tuple[str, np.ndarray]] = []
                for i in range(1, n_segments):
                    name = f"{elem.id}_n{i}"
                    int_nodes.append((name, sorted_coords[i].copy()))
                result[elem.id] = int_nodes

        finally:
            gmsh.model.remove()
            if we_initialised:
                gmsh.finalize()

        return result

    @staticmethod
    def _get_bend_geometry(model: TubaModel, elem: Element) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        p1 = model.nodes[elem.n1].coords
        p2 = model.nodes[elem.n2].coords
        radius = elem.bend_radius
        angle_deg = elem.bend_angle

        d_in = None
        for e in model.elements:
            if e.id == elem.id:
                continue
            if e.n2 == elem.n1:
                v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
                if np.linalg.norm(v) > 1e-9:
                    d_in = v / np.linalg.norm(v)
                    break
            elif e.n1 == elem.n1:
                v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
                if np.linalg.norm(v) > 1e-9:
                    d_in = v / np.linalg.norm(v)
                    break

        d_out = None
        for e in model.elements:
            if e.id == elem.id:
                continue
            if e.n1 == elem.n2:
                v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
                if np.linalg.norm(v) > 1e-9:
                    d_out = v / np.linalg.norm(v)
                    break
            elif e.n2 == elem.n2:
                v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
                if np.linalg.norm(v) > 1e-9:
                    d_out = v / np.linalg.norm(v)
                    break

        if d_in is None and d_out is not None:
            d_in = d_out.copy()
        elif d_out is None and d_in is not None:
            d_out = d_in.copy()
        elif d_in is None and d_out is None:
            v = p2 - p1
            d_in = v / np.linalg.norm(v)
            d_out = d_in.copy()

        theta = np.radians(angle_deg)
        T = radius * np.tan(theta / 2.0)
        V = p1 + d_in * T

        v_bisect = d_out - d_in
        norm_bisect = np.linalg.norm(v_bisect)
        if norm_bisect > 1e-9:
            v_bisect_u = v_bisect / norm_bisect
        else:
            v_bisect_u = np.array([-d_in[1], d_in[0], 0.0])
            if np.linalg.norm(v_bisect_u) < 1e-9:
                v_bisect_u = np.array([0.0, -d_in[2], d_in[1]])
            v_bisect_u /= np.linalg.norm(v_bisect_u)

        L = radius / np.cos(theta / 2.0)
        C = V + v_bisect_u * L

        r1 = p1 - C
        r2 = p2 - C

        axis = np.cross(r1, r2)
        norm_axis = np.linalg.norm(axis)
        if norm_axis > 1e-9:
            axis /= norm_axis
        else:
            axis = np.array([0.0, 0.0, 1.0])

        return C, axis, r1, theta

    # ==================================================================
    # Command file generation (.comm)
    # ==================================================================

    def _write_comm(
        self,
        model: TubaModel,
        load_case: LoadCase,
        path: Path,
        *,
        name_map: Callable[[str], str] | None = None,
    ) -> None:
        """Generate the Code_Aster command file for static piping analysis.

        Uses ``MODELISATION='TUYAU_3M'`` for pipe elements, ``'POU_D_T'`` for beams,
        ``'BARRE'`` for bars, and ``'CABLE'`` for cables.
        """
        pipe_straights = [e for e in model.elements if e.type == "pipe_straight"]
        pipe_bends = [e for e in model.elements if e.type == "pipe_bend"]
        beam_elems = [e for e in model.elements if e.type == "beam"]
        bar_elems = [e for e in model.elements if e.type == "bar"]
        cable_elems = [e for e in model.elements if e.type == "cable"]

        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        bend_elems = pipe_bends
        map_name = name_map or (lambda value: value)

        # Collect unique materials referenced by elements
        used_mat_names = sorted({e.material for e in model.elements})
        cable_mats = {e.material for e in model.elements if e.type == "cable"}

        # Collect unique sections
        used_sec_names = sorted({e.section for e in model.elements})

        # Check for POI1 requirements (discrete springs or masses)
        has_springs = any(s.stiffness_matrix is not None or s.stiffness is not None for s in model.supports if s.type == "spring")
        has_masses = any(s.mass > 0.0 for s in model.supports)
        has_poi1 = has_springs or has_masses

        # Check if the model requires non-linear simulation (contact, friction, rests)
        is_nonlinear = any(s.type == "rest" or s.friction_coefficient > 0.0 for s in model.supports)

        comm: List[str] = []

        def w(text: str = "") -> None:
            """Append a line."""
            comm.append(text)

        # ==============================================================
        # DEBUT
        # ==============================================================
        w("DEBUT(PAR_LOT='NON');")
        w()

        # ==============================================================
        # LIRE_MAILLAGE / CREA_MAILLAGE
        # ==============================================================
        w("# ----- Read mesh -----")
        w("MAIL0 = LIRE_MAILLAGE(FORMAT='ASTER',")
        w("                      UNITE=20);")
        w()

        if has_poi1:
            w("# ----- Create POI1 elements for discrete springs/masses -----")
            w("MAIL = CREA_MAILLAGE(")
            w("    MAILLAGE=MAIL0,")
            w("    CREA_POI1=(")
            for s in model.supports:
                if (s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None)) or s.mass > 0.0:
                    w(f"        _F(NOM_GROUP_MA='{map_name(f'DIS_{s.node}')}', NOM_NOEUD='{s.node}'),")
            w("    ),")
            w(");")
        else:
            w("MAIL = MAIL0;")
        w()

        # ==============================================================
        # AFFE_MODELE
        # ==============================================================
        w("# ----- Model definition -----")
        w("MODELE = AFFE_MODELE(")
        w("    MAILLAGE=MAIL,")
        w("    AFFE=(")
        if pipe_straights or pipe_bends:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('AllPipes')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='TUYAU_3M',")
            w("        ),")
        if beam_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_TUBE')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='POU_D_T',")
            w("        ),")
        if bar_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_BAR')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='BARRE',")
            w("        ),")
        if cable_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_CABLE')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='CABLE',")
            w("        ),")
        for s in model.supports:
            if (s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None)) or s.mass > 0.0:
                w("        _F(")
                w(f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',")
                w("            PHENOMENE='MECANIQUE',")
                w("            MODELISATION='DIS_TR',")
                w("        ),")
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # DEFI_MATERIAU
        # ==============================================================
        w("# ----- Material definitions -----")
        for mat_name in used_mat_names:
            mat = model.materials[mat_name]
            var = f"MAT_{mat_name.upper().replace(' ', '_').replace('-', '_')}"
            w(f"{var} = DEFI_MATERIAU(")
            w(f"    ELAS=_F(")
            w(f"        E={mat.E:.6E},")
            w(f"        NU={mat.nu:.6E},")
            w(f"        RHO={mat.rho:.6E},")
            w(f"        ALPHA={mat.alpha:.6E},")
            w(f"    ),")
            if mat_name in cable_mats:
                w(f"    CABLE=_F(EC_SUR_E=1.0),")
            w(f");")
            w()

        # ==============================================================
        # AFFE_MATERIAU
        # ==============================================================
        w("# ----- Material assignment -----")

        sec_mat_groups: Dict[Tuple[str, str], List[str]] = {}
        for elem in model.elements:
            key = (elem.section, elem.material)
            sec_mat_groups.setdefault(key, []).append(elem.id)

        delta_t = load_case.temperature - load_case.ref_temperature

        affe_entries: List[str] = []
        for (sec_name, mat_name), elem_ids in sec_mat_groups.items():
            var = f"MAT_{mat_name.upper().replace(' ', '_').replace('-', '_')}"
            # Expand pipe bends to their constituent segments in AFFE_MATERIAU
            expanded_ids = []
            for eid in elem_ids:
                elem = next(e for e in model.elements if e.id == eid)
                if elem.type == "pipe_bend":
                    expanded_ids.extend([f"{elem.id}_s{i}" for i in range(self._BEND_SEGMENTS)])
                else:
                    expanded_ids.append(elem.id)

            maille_list = ", ".join(f"'{map_name(eid)}'" for eid in expanded_ids)
            if set(elem_ids) == {e.id for e in model.elements}:
                group_spec = "TOUT='OUI',"
            else:
                group_spec = f"MAILLE=({maille_list}),"
            affe_entries.append(
                f"        _F(\n"
                f"            {group_spec}\n"
                f"            MATER={var},\n"
                f"        ),"
            )

        w("CHMAT = AFFE_MATERIAU(")
        w("    MAILLAGE=MAIL,")
        w("    AFFE=(")
        for entry in affe_entries:
            w(entry)
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # AFFE_CARA_ELEM
        # ==============================================================
        w("# ----- Cross-section properties -----")
        w("CARA = AFFE_CARA_ELEM(")
        w("    MODELE=MODELE,")

        # POUTRE entries for pipes and beams
        poutre_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_straights = [e.id for e in straight_elems if e.section == sec_name and e.type in ("pipe_straight", "beam")]
            
            if sec_straights:
                section_group = f"'{map_name(self._section_group_name(sec_name))}'"
                
                if isinstance(sec, PipeSection) or isinstance(sec, BarSection):
                    r_ext = sec.OD / 2.0
                    ep = sec.WT
                    poutre_entries.append(
                        f"        _F(\n"
                        f"            GROUP_MA={section_group},\n"
                        f"            SECTION='CERCLE',\n"
                        f"            CARA=('R', 'EP'),\n"
                        f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                        f"        ),"
                    )
                elif isinstance(sec, RectangularSection):
                    h_y = sec.height_y
                    h_z = sec.height_z
                    t_y = sec.thickness_y
                    t_z = sec.thickness_z
                    if t_y == 0.0 and t_z == 0.0:
                        poutre_entries.append(
                            f"        _F(\n"
                            f"            GROUP_MA={section_group},\n"
                            f"            SECTION='RECTANGLE',\n"
                            f"            CARA=('HY', 'HZ'),\n"
                            f"            VALE=({h_y:.8E}, {h_z:.8E}),\n"
                            f"        ),"
                        )
                    else:
                        poutre_entries.append(
                            f"        _F(\n"
                            f"            GROUP_MA={section_group},\n"
                            f"            SECTION='RECTANGLE',\n"
                            f"            CARA=('HY', 'HZ', 'EPY', 'EPZ'),\n"
                            f"            VALE=({h_y:.8E}, {h_z:.8E}, {t_y:.8E}, {t_z:.8E}),\n"
                            f"        ),"
                        )
                elif isinstance(sec, IBeamSection):
                    p = sec.properties
                    beamCaraStr = ['A','IY','IZ','AY','AZ','EY','EZ','JX','JG','IYR2','IZR2','RY','RZ','RT']
                    vals = [p.get(k, 0.0) for k in beamCaraStr]
                    poutre_entries.append(
                        f"        _F(\n"
                        f"            GROUP_MA={section_group},\n"
                        f"            SECTION='GENERALE',\n"
                        f"            CARA=({', '.join(repr(k) for k in beamCaraStr)}),\n"
                        f"            VALE=({', '.join(f'{v:.8E}' for v in vals)}),\n"
                        f"        ),"
                    )

        if poutre_entries:
            w("    POUTRE=(")
            for entry in poutre_entries:
                w(entry)
            w("    ),")

        # COUDE entries for bend elements
        if bend_elems:
            coude_entries: List[str] = []
            for elem in bend_elems:
                sec = model.sections[elem.section]
                r_ext = sec.OD / 2.0
                ep = sec.WT
                rc = elem.bend_radius if elem.bend_radius else r_ext * 1.5
                coude_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(elem.id)}',\n"
                    f"            SECTION='CERCLE',\n"
                    f"            CARA=('R', 'EP'),\n"
                    f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                    f"            COUDE=_F(\n"
                    f"                RAYON={rc:.8E},\n"
                    f"            ),\n"
                    f"        ),"
                )
            w("    COUDE=(")
            for entry in coude_entries:
                w(entry)
            w("    ),")

        # BARRE entries
        barre_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_bars = [e.id for e in straight_elems if e.section == sec_name and e.type == "bar"]
            if sec_bars:
                group_list = ", ".join(f"'{map_name(eid)}'" for eid in sec_bars)
                grp = f"({group_list})" if len(sec_bars) > 1 else f"'{map_name(sec_bars[0])}'"
                r_ext = sec.OD / 2.0
                ep = sec.WT if hasattr(sec, "WT") else 0.0
                if ep == 0.0:
                    ep = r_ext  # Solid bar
                barre_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA={grp},\n"
                    f"            SECTION='CERCLE',\n"
                    f"            CARA=('R', 'EP'),\n"
                    f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                    f"        ),"
                )
        if barre_entries:
            w("    BARRE=(")
            for entry in barre_entries:
                w(entry)
            w("    ),")

        # CABLE entries
        cable_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_cables = [e.id for e in straight_elems if e.section == sec_name and e.type == "cable"]
            if sec_cables:
                group_list = ", ".join(f"'{map_name(eid)}'" for eid in sec_cables)
                grp = f"({group_list})" if len(sec_cables) > 1 else f"'{map_name(sec_cables[0])}'"
                area = sec.area
                pret = sec.pretension
                cable_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA={grp},\n"
                    f"            SECTION={area:.8E},\n"
                    f"            N_INIT={pret:.8E},\n"
                    f"        ),"
                )
        if cable_entries:
            w("    CABLE=(")
            for entry in cable_entries:
                w(entry)
            w("    ),")

        # DISCRET entries for springs/masses
        discret_entries: List[str] = []
        for s in model.supports:
            if s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None):
                if s.stiffness_matrix:
                    k = s.stiffness_matrix
                else:
                    val = s.stiffness if s.stiffness is not None else 1.0e6
                    k = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    if s.direction:
                        for idx, v in enumerate(s.direction):
                            if abs(v) > 1e-12:
                                k[idx] = val
                    else:
                        raise ValueError(
                            f"Spring support at node {s.node} uses scalar stiffness without direction. "
                            "Use stiffness_matrix=[Kx, Ky, Kz, Krx, Kry, Krz] or provide direction."
                        )
                discret_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',\n"
                    f"            REPERE='GLOBAL',\n"
                    f"            CARA='K_TR_D_L',\n"
                    f"            VALE=({k[0]:.8E}, {k[1]:.8E}, {k[2]:.8E}, {k[3]:.8E}, {k[4]:.8E}, {k[5]:.8E}),\n"
                    f"        ),"
                )
            if s.mass > 0.0:
                discret_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',\n"
                    f"            CARA='M_T_D_L',\n"
                    f"            VALE=({s.mass:.8E}, {s.mass:.8E}, {s.mass:.8E}, 0.0, 0.0, 0.0),\n"
                    f"        ),"
                )
        if discret_entries:
            w("    DISCRET=(")
            for entry in discret_entries:
                w(entry)
            w("    ),")

        # Orientation
        orientation_entries: List[str] = []
        if pipe_straights or pipe_bends:
            orientation_entries.append(
                "        _F(\n"
                f"            GROUP_NO='{map_name('PipeOrientationNodes')}',\n"
                "            CARA='GENE_TUYAU',\n"
                "            VALE=(0.0, 0.0, 1.0),\n"
                "        ),"
            )
        if beam_elems:
            for elem in beam_elems:
                angle = getattr(elem, "twist_angle", 0.0)
                orientation_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(elem.id)}',\n"
                    f"            CARA='ANGL_VRIL',\n"
                    f"            VALE={angle:.4f},\n"
                    f"        ),"
                )
        if orientation_entries:
            w("    ORIENTATION=(")
            for entry in orientation_entries:
                w(entry)
            w("    ),")

        w(");")
        w()


        # ==============================================================
        # AFFE_CHAR_MECA — supports
        # ==============================================================
        w("# ----- Boundary conditions -----")
        active_bcs = []
        for i, sup in enumerate(model.supports):
            grp_name = map_name(f"GN_{sup.node}")
            char_name = f"BC_{i}"

            write_bc = False
            lines_bc = []

            if sup.blocked_dof is not None:
                dof_names = ["DX", "DY", "DZ", "DRX", "DRY", "DRZ"]
                blocked = []
                for idx, val in enumerate(sup.blocked_dof):
                    if val not in (False, 0, '0', 'x', 'X', None):
                        blocked.append(dof_names[idx])
                if blocked:
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    for dof in blocked:
                        lines_bc.append(f"        {dof}=0.0,")
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
            else:
                if sup.type == "anchor":
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    lines_bc.append(f"        BLOCAGE=('DEPLACEMENT', 'ROTATION'),")
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "guide":
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        blocked = []
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                blocked.append(dof_map[idx])
                        for dof in blocked:
                            lines_bc.append(f"        {dof}=0.0,")
                    else:
                        lines_bc.append(f"        DX=0.0,")
                        lines_bc.append(f"        DY=0.0,")
                        lines_bc.append(f"        DZ=0.0,")
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "rest":
                    if is_nonlinear:
                        continue
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                lines_bc.append(f"        {dof_map[idx]}=0.0,")
                    else:
                        lines_bc.append(f"        DY=0.0,")
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "spring":
                    pass
                else:
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    lines_bc.append(f"        DX=0.0,")
                    lines_bc.append(f"        DY=0.0,")
                    lines_bc.append(f"        DZ=0.0,")
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")

            if write_bc:
                for line in lines_bc:
                    w(line)
                w()
                active_bcs.append(char_name)

        # ==============================================================
        # AFFE_CHAR_MECA — gravity
        # ==============================================================
        if load_case.gravity:
            w("# ----- Gravity -----")
            w("GRAVITY = AFFE_CHAR_MECA(")
            w("    MODELE=MODELE,")
            w("    PESANTEUR=_F(")
            w("        GRAVITE=9.81,")
            w("        DIRECTION=(0.0, -1.0, 0.0),")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # AFFE_CHAR_MECA — pressure
        # ==============================================================
        if load_case.internal_pressure > 0.0:
            w("# ----- Internal pressure -----")
            w("PRESSURE = AFFE_CHAR_MECA(")
            w("    MODELE=MODELE,")
            w("    FORCE_TUYAU=_F(")
            w(f"        GROUP_MA='{map_name('AllPipes')}',")
            w(f"        PRES={load_case.internal_pressure:.6E},")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # Thermal load (uniform temperature field for expansion)
        # ==============================================================
        if abs(delta_t) > 1e-10:
            w("# ----- Thermal expansion -----")
            w("T_FUNC = DEFI_CONSTANTE(VALE=1.0);")
            w()
            w("TEMP_FIELD = CREA_CHAMP(")
            w("    TYPE_CHAM='NOEU_TEMP_R',")
            w("    OPERATION='AFFE',")
            w("    MAILLAGE=MAIL,")
            w("    AFFE=_F(")
            w("        TOUT='OUI',")
            w(f"        NOM_CMP='TEMP',")
            w(f"        VALE={load_case.temperature:.6E},")
            w("    ),")
            w(");")
            w()

            # Rebuild CHMAT with thermal reference
            w("CHMAT = AFFE_MATERIAU(")
            w("    MAILLAGE=MAIL,")
            w("    AFFE=(")
            for entry in affe_entries:
                w(entry)
            w("    ),")
            w("    AFFE_VARC=_F(")
            w("        TOUT='OUI',")
            w("        NOM_VARC='TEMP',")
            w("        CHAM_GD=TEMP_FIELD,")
            w(f"        VALE_REF={load_case.ref_temperature:.6E},")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # DEFI_CONTACT & Solve
        # ==============================================================
        if is_nonlinear:
            w("# ----- Unilateral contacts -----")
            w("contact = DEFI_CONTACT(")
            w("    MODELE=MODELE,")
            w("    FORMULATION='LIAISON_UNIL',")
            w("    ZONE=(")
            for sup in model.supports:
                if sup.type == "rest":
                    grp_name = map_name(f"GN_{sup.node}")
                    cmp_name = "DY"
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                cmp_name = dof_map[idx]
                                break
                    w(f"        _F(GROUP_NO='{grp_name}', NOM_CMP='{cmp_name}'),")
            w("    ),")
            w(");")
            w()

        w("# ----- Solve -----")

        # Build EXCIT list
        excit_entries: List[str] = []
        for char_name in active_bcs:
            excit_entries.append(f"        _F(CHARGE={char_name}),")
        if load_case.gravity:
            excit_entries.append("        _F(CHARGE=GRAVITY),")
        if load_case.internal_pressure > 0.0:
            excit_entries.append("        _F(CHARGE=PRESSURE),")

        if is_nonlinear:
            w("lst_inst = DEFI_LIST_REEL(VALE=(0.0, 1.0));")
            w("times = DEFI_LIST_INST(DEFI_LIST=_F(LIST_INST=lst_inst));")
            w()
            w("RESU = STAT_NON_LINE(")
            w("    MODELE=MODELE,")
            w("    CHAM_MATER=CHMAT,")
            w("    CARA_ELEM=CARA,")
            w("    EXCIT=(")
            for entry in excit_entries:
                w(entry)
            w("    ),")
            w("    COMPORTEMENT=_F(")
            w("        TOUT='OUI',")
            w("        RELATION='ELAS',")
            w("    ),")
            w("    INCREMENT=_F(")
            w("        LIST_INST=times,")
            w("    ),")
            w("    CONTACT=contact,")
            w("    METHODE='NEWTON',")
            w(");")
        else:
            w("RESU = MECA_STATIQUE(")
            w("    MODELE=MODELE,")
            w("    CHAM_MATER=CHMAT,")
            w("    CARA_ELEM=CARA,")
            w("    EXCIT=(")
            for entry in excit_entries:
                w(entry)
            w("    ),")
            w(");")
        w()

        # ==============================================================
        # CALC_CHAMP — derived fields
        # ==============================================================
        w("# ----- Derived fields -----")
        w("RESU = CALC_CHAMP(")
        w("    reuse=RESU,")
        w("    RESULTAT=RESU,")
        w("    CONTRAINTE=('EFGE_ELNO', 'SIEQ_ELNO'),")
        w("    FORCE='FORC_NODA',")
        w(");")
        w()

        # ==============================================================
        # IMPR_RESU — MED output
        # ==============================================================
        w("# ----- Write MED results file -----")
        w("IMPR_RESU(")
        w("    FORMAT='MED',")
        w("    UNITE=80,")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM=('DEPL', 'SIEQ_ELNO', 'EFGE_ELNO', 'FORC_NODA'),")
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # CREA_TABLE + IMPR_TABLE — parseable text output
        # ==============================================================
        w("# ----- Text table for EFGE_ELNO -----")
        w("TAB_EFFO = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='EFGE_ELNO',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_EFFO,")
        w("    UNITE=38,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        w("# ----- Text table for DEPL -----")
        w("TAB_DEPL = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='DEPL',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('DX', 'DY', 'DZ', 'DRX', 'DRY', 'DRZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_DEPL,")
        w("    UNITE=39,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        w("# ----- Text table for FORC_NODA -----")
        w("TAB_REAC = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='FORC_NODA',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('DX', 'DY', 'DZ', 'DRX', 'DRY', 'DRZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_REAC,")
        w("    UNITE=40,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        w("# ----- Text table for SIEQ_ELNO -----")
        w("TAB_SIEQ = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='SIEQ_ELNO',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('VMIS',),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_SIEQ,")
        w("    UNITE=41,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()

        # ==============================================================
        # FIN
        # ==============================================================
        w("FIN();")

        path.write_text("\n".join(comm), encoding="utf-8")
        logger.info("Wrote command file: %s", path)

    # ==================================================================
    # Export file generation
    # ==================================================================

    def _write_export(self, work_dir: Path) -> None:
        """Generate the ``.export`` file mapping logical units to files.

        The export file tells ``as_run`` where to find the mesh, command
        file, and where to write outputs.
        """
        lines = [
            "P actions make_etude",
            "P version stable",
            "P nomjob study",
            "P debug nodebug",
            "P mode interactif",
            "P ncpus 1",
            "A memjeveux 512",
            "A tpmax 3600",
            "",
            "F comm study.comm D 1",
            "F mail study.mail D 20",
            "F mess study.mess R 6",
            "F resu study.resu R 8",
            "F rmed study.rmed R 80",
            "F effo study_effo.csv R 38",
            "F depl study_depl.csv R 39",
            "F reac study_reac.csv R 40",
            "F sieq study_sieq.csv R 41",
        ]

        export_path = work_dir / "study.export"
        export_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote export file: %s", export_path)

    # ==================================================================
    # Execution
    # ==================================================================

    def _execute(self, work_dir: Path) -> None:
        """Invoke Code_Aster on the generated study files."""
        export_file = work_dir / "study.export"
        config = CodeAsterRuntimeConfig(
            exec_method=self.exec_method,
            docker_image=self.docker_image,
            wsl_distro=self.wsl_distro,
            runner_command=self.runner_command,
            bridge_python=self.bridge_python,
            timeout_seconds=self.timeout_seconds,
        )
        run_code_aster_export(export_file, work_dir, config)

    # ==================================================================
    # Result parsing
    # ==================================================================

    def parse_result_artifacts(
        self,
        model: TubaModel,
        work_dir: str | Path,
        load_case_name: Optional[str] = None,
    ) -> FEAResults:
        """Parse an existing Code_Aster output directory without running the solver."""
        results = self._parse_results(model, Path(work_dir))
        if load_case_name is not None:
            results.load_case = load_case_name
        return results

    def _parse_results(
        self,
        model: TubaModel,
        work_dir: Path,
    ) -> FEAResults:
        """Parse solver outputs into :class:`FEAResults`.

        The parser tries two sources in order:

        1. **CSV text tables** (units 38–41) — always generated and fully
           self-contained.  This is the primary source.
        2. **MED file** via ``meshio`` — used to attach *raw_mesh* for
           visualisation and as a fallback for any missing fields.
        """
        results = FEAResults(solver_name=self.SOLVER_NAME)
        results._model = model

        rmed_path = work_dir / "study.rmed"
        if rmed_path.exists():
            results.result_file = rmed_path

        # --- Initialise empty results for every node/element ---------------
        for nid in model.nodes:
            results.node_results[nid] = NodeResult(
                node_id=nid,
                displacement=np.zeros(6),
            )
        for elem in model.elements:
            results.element_results[elem.id] = ElementResult(
                element_id=elem.id,
                forces_n1=np.zeros(6),
                forces_n2=np.zeros(6),
            )

        # --- Parse CSV tables ----------------------------------------------
        self._parse_depl_table(model, work_dir, results)
        self._parse_effo_table(model, work_dir, results)
        self._parse_reac_table(model, work_dir, results)
        self._parse_sieq_table(model, work_dir, results)

        # --- Attempt to attach MED mesh ------------------------------------
        self._try_load_rmed(work_dir, results)

        return results

    # ------------------------------------------------------------------
    # Individual table parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_csv_table(path: Path) -> List[Dict[str, str]]:
        """Parse a Code_Aster ``IMPR_TABLE`` CSV into a list of row dicts.

        The first non-comment line containing the header columns is
        detected automatically.  Blank lines and lines starting with
        ``#`` are skipped.
        """
        if not path.exists():
            logger.warning("Table file not found: %s", path)
            return []

        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [
            ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]

        if len(lines) < 2:
            return []

        header = [h.strip() for h in lines[0].split(",")]
        rows: List[Dict[str, str]] = []
        for line in lines[1:]:
            vals = [v.strip() for v in line.split(",")]
            if len(vals) != len(header):
                continue
            rows.append(dict(zip(header, vals)))
        return rows

    def _parse_depl_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
    ) -> None:
        """Parse displacement table (unit 39)."""
        rows = self._parse_csv_table(work_dir / "study_depl.csv")
        for row in rows:
            nid = row.get("NOEUD", "").strip()
            if not nid:
                continue
            try:
                disp = np.array([
                    float(row.get("DX", 0)),
                    float(row.get("DY", 0)),
                    float(row.get("DZ", 0)),
                    float(row.get("DRX", 0)),
                    float(row.get("DRY", 0)),
                    float(row.get("DRZ", 0)),
                ])
            except (ValueError, TypeError):
                continue
            if nid in results.node_results:
                results.node_results[nid].displacement = disp
                continue
            results.analysis_node_results[nid] = NodeResult(node_id=nid, displacement=disp)
            results.parser_diagnostics.append(
                f"Preserved displacement row for non-native analysis node {nid!r} without mesh source mapping."
            )

    def _parse_effo_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
    ) -> None:
        """Parse internal-force table (unit 38, ``EFGE_ELNO``).

        Each row contains ``MAILLE`` (element) and ``NOEUD`` (node).
        For a SEG2 element there are exactly two rows — one per end-node.
        We map them to ``forces_n1`` / ``forces_n2`` by matching the
        ``NOEUD`` field against the element's ``n1`` / ``n2``.
        """
        rows = self._parse_csv_table(work_dir / "study_effo.csv")
        # Build a quick lookup: element_id → Element
        elem_map: Dict[str, Element] = {e.id: e for e in model.elements}

        for row in rows:
            eid = row.get("MAILLE", "").strip()
            nid = row.get("NOEUD", "").strip()
            
            # Map segmented elements (e.g. pipe_bend_0_s0) back to the original bend element (pipe_bend_0)
            orig_eid = eid
            if "_s" in eid:
                parts = eid.split("_s")
                if len(parts) == 2 and parts[0] in results.element_results:
                    orig_eid = parts[0]

            if orig_eid not in results.element_results:
                continue
            try:
                forces = np.array([
                    float(row.get("N", row.get("NXX", 0))),
                    float(row.get("VY", 0)),
                    float(row.get("VZ", 0)),
                    float(row.get("MT", 0)),
                    float(row.get("MFY", 0)),
                    float(row.get("MFZ", 0)),
                ])
            except (ValueError, TypeError):
                continue

            elem = elem_map.get(orig_eid)
            if elem is None:
                continue
            er = results.element_results[orig_eid]
            if nid == elem.n1:
                er.forces_n1 = forces
            elif nid == elem.n2:
                er.forces_n2 = forces

    def _parse_reac_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
    ) -> None:
        """Parse reaction force table (unit 40, ``FORC_NODA``)."""
        rows = self._parse_csv_table(work_dir / "study_reac.csv")
        support_nodes = {s.node for s in model.supports}

        for row in rows:
            nid = row.get("NOEUD", "").strip()
            if nid not in support_nodes or nid not in results.node_results:
                continue
            try:
                reaction = np.array([
                    float(row.get("DX", 0)),
                    float(row.get("DY", 0)),
                    float(row.get("DZ", 0)),
                    float(row.get("DRX", 0)),
                    float(row.get("DRY", 0)),
                    float(row.get("DRZ", 0)),
                ])
            except (ValueError, TypeError):
                continue
            results.node_results[nid].reaction_force = reaction

    def _parse_sieq_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
    ) -> None:
        """Parse Von Mises stress table (unit 41, ``SIEQ_ELNO``)."""
        rows = self._parse_csv_table(work_dir / "study_sieq.csv")
        elem_map: Dict[str, Element] = {e.id: e for e in model.elements}

        for row in rows:
            eid = row.get("MAILLE", "").strip()
            nid = row.get("NOEUD", "").strip()

            # Map segmented elements back to the original bend element
            orig_eid = eid
            if "_s" in eid:
                parts = eid.split("_s")
                if len(parts) == 2 and parts[0] in results.element_results:
                    orig_eid = parts[0]

            if orig_eid not in results.element_results:
                continue
            try:
                vmis = float(row.get("VMIS", 0))
            except (ValueError, TypeError):
                continue

            elem = elem_map.get(orig_eid)
            if elem is None:
                continue
            er = results.element_results[orig_eid]
            if nid == elem.n1:
                er.von_mises_n1 = vmis
            elif nid == elem.n2:
                er.von_mises_n2 = vmis
            er.max_von_mises = max(er.max_von_mises, vmis)

    @staticmethod
    def _try_load_rmed(work_dir: Path, results: FEAResults) -> None:
        """Attempt to load the ``.rmed`` file via *meshio* for visualisation."""
        rmed_path = work_dir / "study.rmed"
        if not rmed_path.exists():
            return
        try:
            import meshio  # type: ignore[import-untyped]
            mesh = meshio.read(str(rmed_path))
            results.raw_mesh = mesh
            logger.info("Loaded MED mesh with %d points.", len(mesh.points))
        except ImportError:
            logger.debug("meshio not installed — skipping .rmed import.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read .rmed: %s", exc)
