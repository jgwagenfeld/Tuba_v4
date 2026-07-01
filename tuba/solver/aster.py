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
from tuba.solver.aster_sidecar import SolverNameMap, build_solver_name_map, dump_solver_sidecar
from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, run_code_aster_export
from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.refs import EntityRef
from tuba.solver.aster_comm import _CommWriterMixin
from tuba.solver.aster_mesh import _MeshWriterMixin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



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

class CodeAsterSolver(_CommWriterMixin, _MeshWriterMixin, BaseSolver):
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
        self.runner_command = (
            runner_command
            or os.environ.get("TUBA_CODE_ASTER_RUNNER_COMMAND")
            or os.environ.get("TUBA_CODE_ASTER_RUNNER")
        )
        self.bridge_python = bridge_python or os.environ.get("TUBA_CODE_ASTER_PYTHON")
        self.timeout_seconds = timeout_seconds
        # Per-export memo of Gmsh-meshed bend interior nodes. A single
        # export_analysis_study writes the .mail file twice (default names,
        # then solver names); without this the OCC bend mesher would run
        # twice. Cleared at each export entry so it never spans models.
        self._bend_gmsh_cache: dict = {}

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
        study = self.export_analysis_study(model, load_case_name)
        return self.solve_exported_study(model, study)

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
        self._bend_gmsh_cache.clear()
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
        self._bend_gmsh_cache.clear()
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
        extra_solver_names = [
            f"DIS_{support.node}"
            for support in model.supports
            if (
                support.type == "spring"
                and (support.stiffness_matrix is not None or support.stiffness is not None)
            )
            or support.mass > 0.0
        ]
        solver_names = list(dict.fromkeys(
            list(analysis_mesh.nodes.keys())
            + list(analysis_mesh.elements.keys())
            + list(analysis_mesh.groups.keys())
            + extra_solver_names
        ))
        name_map = build_solver_name_map(solver_names, max_length=self._ASTER_ENTITY_NAME_LEN)
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
    _ASTER_ENTITY_NAME_LEN = 8


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
        node_label_map, element_label_map = self._read_solver_label_maps(work_dir)
        applied_displacements = self._parse_depl_table(model, work_dir, results, node_label_map)
        # Displacement is the primary result of a static solve and is always
        # emitted by a successful run.  A run that exits cleanly but produced no
        # parseable displacement rows (empty/garbled CSV, bad mesh group, no
        # loads) would otherwise return the all-zero seed above as if it were a
        # valid result.  Refuse that, per the "never present non-real values as
        # solver results" contract (AGENTS.md).
        if applied_displacements == 0:
            raise RuntimeError(
                f"Code_Aster produced no displacement results in {work_dir} "
                "(study_depl.csv is missing or has no parseable rows). The solver "
                "run did not generate real results; refusing to return an all-zero "
                "result. Inspect study.mess for solver errors."
            )
        self._parse_effo_table(model, work_dir, results, node_label_map, element_label_map)
        self._parse_reac_table(model, work_dir, results, node_label_map)
        self._parse_sieq_table(model, work_dir, results, node_label_map, element_label_map)

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

    @staticmethod
    def _read_solver_label_maps(work_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
        """Map Code_Aster's numeric table labels back to Tuba mesh names."""
        mail_path = work_dir / "study.mail"
        node_map: dict[str, str] = {}
        element_map: dict[str, str] = {}
        if not mail_path.exists():
            return node_map, element_map
        solver_to_tuba = CodeAsterSolver._read_solver_name_reverse_map(work_dir)

        node_index = 0
        element_index = 0
        block: str | None = None
        for raw_line in mail_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "COOR_3D":
                block = "nodes"
                continue
            if line in {"SEG2", "SEG3"}:
                block = "elements"
                continue
            if line == "FINSF":
                block = None
                continue
            if line == "FIN" or line.startswith("GROUP_") or line == "TITRE":
                block = None
                continue

            parts = line.split()
            if not parts:
                continue
            label = parts[0].strip()
            tuba_label = solver_to_tuba.get(label, label)
            if block == "nodes":
                node_index += 1
                node_map.setdefault(label, tuba_label)
                node_map.setdefault(tuba_label, tuba_label)
                node_map[str(node_index)] = tuba_label
            elif block == "elements":
                element_index += 1
                element_map.setdefault(label, tuba_label)
                element_map.setdefault(tuba_label, tuba_label)
                element_map[str(element_index)] = tuba_label

        return node_map, element_map

    @staticmethod
    def _read_solver_name_reverse_map(work_dir: Path) -> dict[str, str]:
        sidecar_path = work_dir / "study_tuba_fem.json"
        if not sidecar_path.exists():
            return {}
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        name_map = payload.get("name_map", {})
        if not isinstance(name_map, dict):
            return {}
        reverse: dict[str, str] = {}
        for original, solver_name in name_map.items():
            if isinstance(original, str) and isinstance(solver_name, str):
                reverse[solver_name] = original
        return reverse

    def _parse_depl_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
        node_label_map: dict[str, str],
    ) -> int:
        """Parse displacement table (unit 39). Returns the number of applied rows."""
        rows = self._parse_csv_table(work_dir / "study_depl.csv")
        applied = 0
        for row in rows:
            raw_nid = row.get("NOEUD", "").strip()
            nid = node_label_map.get(raw_nid, raw_nid)
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
                applied += 1
                continue
            results.analysis_node_results[nid] = NodeResult(node_id=nid, displacement=disp)
            results.parser_diagnostics.append(
                f"Preserved displacement row for non-native analysis node {nid!r} without mesh source mapping."
            )
            applied += 1
        return applied

    def _parse_effo_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
        node_label_map: dict[str, str],
        element_label_map: dict[str, str],
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
            raw_eid = row.get("MAILLE", "").strip()
            raw_nid = row.get("NOEUD", "").strip()
            eid = element_label_map.get(raw_eid, raw_eid)
            nid = node_label_map.get(raw_nid, raw_nid)
            
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
        node_label_map: dict[str, str],
    ) -> None:
        """Parse reaction force table (unit 40, ``FORC_NODA``)."""
        rows = self._parse_csv_table(work_dir / "study_reac.csv")
        support_nodes = {s.node for s in model.supports}

        for row in rows:
            raw_nid = row.get("NOEUD", "").strip()
            nid = node_label_map.get(raw_nid, raw_nid)
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
        node_label_map: dict[str, str],
        element_label_map: dict[str, str],
    ) -> None:
        """Parse Von Mises stress table (unit 41, ``SIEQ_ELNO``)."""
        rows = self._parse_csv_table(work_dir / "study_sieq.csv")
        elem_map: Dict[str, Element] = {e.id: e for e in model.elements}

        for row in rows:
            raw_eid = row.get("MAILLE", "").strip()
            raw_nid = row.get("NOEUD", "").strip()
            eid = element_label_map.get(raw_eid, raw_eid)
            nid = node_label_map.get(raw_nid, raw_nid)

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
            try:
                mesh = meshio.read(str(rmed_path), file_format="med")
            except TypeError:
                mesh = meshio.read(str(rmed_path))
            results.raw_mesh = mesh
            logger.info("Loaded MED mesh with %d points.", len(mesh.points))
        except ImportError:
            logger.debug("meshio not installed — skipping .rmed import.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read .rmed: %s", exc)
