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
import math
import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path, PureWindowsPath
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
    ElementResult,
    FEAResults,
    NodeResult,
)
from tuba.solver.aster_sidecar import (
    SolverNameMap,
    build_solver_name_map,
    dump_solver_sidecar,
    load_and_validate_artifact_chain,
)
from tuba.solver.code_aster_runtime import (
    CodeAsterExecution,
    CodeAsterRuntimeConfig,
    run_code_aster_export,
    validate_code_aster_execution_attestation,
    write_code_aster_execution_attestation,
)
from tuba.analysis import AnalysisMesh, AnalysisRun, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.analysis.tuyau import (
    CODE_ASTER_TUYAU_NCOU,
    CODE_ASTER_TUYAU_NSEC,
    DISPLAY_GENERATRICE,
    subpoint_station,
)
from tuba.analysis.provenance import (
    SolverInputIdentity,
    build_solver_input_identity,
)
from tuba.refs import EntityRef
from tuba.solver.aster_comm import _CommWriterMixin
from tuba.solver.aster_mesh import _MeshWriterMixin

logger = logging.getLogger(__name__)

# The TUYAU sub-point convention has one home; see tuba/analysis/tuyau.py.
_CODE_ASTER_TUYAU_NCOU = CODE_ASTER_TUYAU_NCOU
_CODE_ASTER_TUYAU_NSEC = CODE_ASTER_TUYAU_NSEC
_TUBA_GENE_TUYAU = np.array(DISPLAY_GENERATRICE, dtype=float)

# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class CodeAsterSolver(_CommWriterMixin, _MeshWriterMixin):
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
    ) -> AnalysisRun:
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
        AnalysisRun
            Provenance-bearing study, mesh, persistent state, and transient results.

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
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()

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
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()

        if output_dir is not None:
            wdir = Path(output_dir)
            wdir.mkdir(parents=True, exist_ok=True)
        elif self.work_dir is not None:
            wdir = self.work_dir
            wdir.mkdir(parents=True, exist_ok=True)
        else:
            wdir = Path(tempfile.mkdtemp(prefix="tuba_aster_"))

        model_revision = int(getattr(model, "revision", 0))
        solver_input_identity = build_solver_input_identity(model, load_case_name)
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
        analysis_mesh = replace(analysis_mesh, solver_input_identity=solver_input_identity)
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
            solver_input_identity=solver_input_identity,
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
            solver_input_identity=solver_input_identity,
        )
        portable_study = replace(
            study,
            work_dir=None,
            input_files={role: PureWindowsPath(value).name for role, value in study.input_files.items()},
        )
        portable_mesh = replace(
            analysis_mesh,
            files={role: PureWindowsPath(value).name for role, value in analysis_mesh.files.items()},
        )
        manifest = {
            "study": portable_study.to_dict(),
            "analysis_mesh": portable_mesh.to_dict(),
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

    def export_volume_study(
        self,
        model: TubaModel,
        load_case_name: str | None,
        output_dir: str | Path,
        *,
        element_ids,
        max_element_size: float,
        element_order: int = 2,
        export_tensor_stress: bool = True,
    ) -> AnalysisStudy:
        """Export a native Gmsh pipe-volume study without claiming solver results."""
        from tuba.solver.aster_volume import PipeVolumeStudyExporter

        return PipeVolumeStudyExporter().export_analysis_study(
            model,
            load_case_name,
            output_dir,
            element_ids=element_ids,
            max_element_size=max_element_size,
            element_order=element_order,
            export_tensor_stress=export_tensor_stress,
        )

    def solve_volume_study(
        self,
        model: TubaModel,
        load_case_name: str | None,
        *,
        element_ids,
        max_element_size: float,
        element_order: int = 2,
        export_tensor_stress: bool = True,
    ) -> AnalysisRun:
        """Generate, execute, attest, and import an explicit pipe-volume study."""
        output_dir = self.work_dir or Path(tempfile.mkdtemp(prefix="tuba_aster_volume_"))
        study = self.export_volume_study(
            model,
            load_case_name,
            output_dir,
            element_ids=element_ids,
            max_element_size=max_element_size,
            element_order=element_order,
            export_tensor_stress=export_tensor_stress,
        )
        return self.solve_exported_study(model, study)

    def solve_exported_study(self, model: TubaModel, study: AnalysisStudy) -> AnalysisRun:
        """Execute an exported study and return its verified analysis run."""
        self._require_solve_ready_study(study)
        work_dir = Path(study.work_dir)
        _, manifest_study, _, _ = load_and_validate_artifact_chain(
            model,
            work_dir,
            study=study,
            requested_load_case=study.load_case,
        )
        if manifest_study is not None:
            self._require_solve_ready_study(manifest_study)
        execution = self._execute(work_dir)
        write_code_aster_execution_attestation(
            work_dir,
            execution,
            (manifest_study or study).solver_input_identity,
        )
        from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts

        return import_code_aster_artifacts(model=model, work_dir=work_dir, study=study)

    def _require_solve_ready_study(self, study: AnalysisStudy) -> None:
        metadata = study.metadata
        if metadata.get("result_status") == "export_only" and not metadata.get("code_aster_solve_ready"):
            reason = metadata.get("runtime_blocker") or (
                "Mixed Code_Aster studies are currently export-only until the "
                "mixed STEP solve/import path has real solver proof."
            )
            raise RuntimeError(
                "Mixed Code_Aster study is export-only and cannot be executed "
                f"as solver results. {reason}"
            )


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

    def _execute(self, work_dir: Path) -> CodeAsterExecution:
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
        return run_code_aster_export(export_file, work_dir, config)

    # ==================================================================
    # Result parsing
    # ==================================================================

    def parse_result_artifacts(
        self,
        model: TubaModel,
        work_dir: str | Path,
        load_case_name: Optional[str] = None,
        *,
        study: AnalysisStudy | None = None,
    ) -> FEAResults:
        """Parse an existing Code_Aster output directory without running the solver."""
        root = Path(work_dir)
        validated_study, _, analysis_mesh, sidecar = load_and_validate_artifact_chain(
            model,
            root,
            study=study,
            requested_load_case=load_case_name,
        )
        sidecar_identity = (
            None if sidecar is None or sidecar.get("solver_input_identity") is None
            else SolverInputIdentity.from_dict(sidecar["solver_input_identity"])
        )
        validate_code_aster_execution_attestation(
            root,
            study_identity=validated_study.solver_input_identity,
            mesh_identity=None if analysis_mesh is None else analysis_mesh.solver_input_identity,
            sidecar_identity=sidecar_identity,
        )
        return self._parse_result_artifacts_after_validation(model, root, validated_study.load_case)

    def _parse_result_artifacts_after_validation(
        self,
        model: TubaModel,
        work_dir: Path,
        load_case: str,
    ) -> FEAResults:
        results = self._parse_results(model, work_dir)
        results.load_case = load_case
        return results

    def _parse_results(
        self,
        model: TubaModel,
        work_dir: Path,
    ) -> FEAResults:
        """Parse solver outputs into :class:`FEAResults`.

        The parser reads the CSV text tables (units 38-41), which are generated
        by the solver and fully self-contained. If a ``study.rmed`` file exists
        it is recorded on the result object, but RMED inspection is left to
        explicit visualization/import paths so solver parsing never depends on
        optional mesh readers or their file-handle behavior.
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
                forces_n1=np.full(6, np.nan),
                forces_n2=np.full(6, np.nan),
            )

        # --- Parse CSV tables ----------------------------------------------
        node_label_map, element_label_map = self._read_solver_label_maps(work_dir)
        analysis_mesh_node_ids = self._read_analysis_mesh_node_ids(work_dir)
        displacement_nodes = self._parse_depl_table(
            model,
            work_dir,
            results,
            node_label_map,
            analysis_mesh_node_ids,
        )
        # Displacement is the primary result of a static solve and is always
        # emitted by a successful run.  A run that exits cleanly but produced no
        # parseable displacement rows (empty/garbled CSV, bad mesh group, no
        # loads) would otherwise return the all-zero seed above as if it were a
        # valid result.  Refuse that, per the "never present non-real values as
        # solver results" contract (AGENTS.md).
        if not displacement_nodes:
            raise RuntimeError(
                f"Code_Aster produced no displacement results in {work_dir} "
                "(study_depl.csv is missing or has no parseable rows). The solver "
                "run did not generate real results; refusing to return an all-zero "
                "result. Inspect study.mess for solver errors."
            )
        missing_displacements = sorted(set(model.nodes) - displacement_nodes)
        if missing_displacements:
            raise RuntimeError(
                f"Code_Aster output is missing displacement results for model node(s) "
                f"{missing_displacements} in {work_dir}. Refusing to substitute zeros."
            )
        force_endpoints = self._parse_effo_table(model, work_dir, results, node_label_map, element_label_map)
        # Element internal forces are what the ASME B31.3 evaluator turns into code
        # stress. If displacement parsed but the force table is missing/empty/mismapped,
        # every stress-bearing element keeps its all-zero seed and compliance would
        # silently report PASS on fictitious zero moments. Refuse that, mirroring the
        # displacement guard above and the AGENTS.md "no proxy values as results" contract.
        pipe_elements = [elem for elem in model.elements if elem.type in ("pipe_straight", "pipe_bend")]
        if pipe_elements and not force_endpoints:
            raise RuntimeError(
                f"Code_Aster produced no element internal forces in {work_dir} "
                "(study_effo.csv is missing or has no parseable rows) even though the "
                "model has stress-bearing pipe elements. Refusing to return zero-force "
                "results that would pass compliance on fictitious stress. Inspect "
                "study.mess for solver errors."
            )
        expected_force_endpoints = {
            (element.id, node_id)
            for element in pipe_elements
            for node_id in (element.n1, element.n2)
        }
        missing_force_endpoints = sorted(expected_force_endpoints - force_endpoints)
        if missing_force_endpoints:
            labels = [f"{element_id}:{node_id}" for element_id, node_id in missing_force_endpoints]
            raise RuntimeError(
                f"Code_Aster output is missing internal-force results for pipe endpoint(s) "
                f"{labels} in {work_dir}. Refusing to substitute zeros."
            )
        self._parse_reac_table(model, work_dir, results, node_label_map)
        self._parse_sieq_table(model, work_dir, results, node_label_map, element_label_map)

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

    @staticmethod
    def _read_analysis_mesh_node_ids(work_dir: Path) -> set[str]:
        """Read authoritative analysis-node membership from the study manifest."""
        manifest_path = work_dir / "study_manifest.json"
        if not manifest_path.exists():
            return set()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        analysis_mesh = payload.get("analysis_mesh")
        if not isinstance(analysis_mesh, dict):
            return set()
        nodes = analysis_mesh.get("nodes")
        if not isinstance(nodes, dict):
            return set()
        return {node_id for node_id in nodes if isinstance(node_id, str)}

    def _parse_depl_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
        node_label_map: dict[str, str],
        analysis_mesh_node_ids: set[str],
    ) -> set[str]:
        """Parse displacement table (unit 39); return covered model-node IDs."""
        rows = self._parse_csv_table(work_dir / "study_depl.csv")
        covered_model_nodes: set[str] = set()
        for row in rows:
            raw_nid = row.get("NOEUD", "").strip()
            nid = node_label_map.get(raw_nid, raw_nid)
            if not nid:
                continue

            def finite_component(component: str, kind: str) -> float:
                raw_value = row.get(component, "").strip()
                try:
                    value = float(raw_value)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError(
                        f"Code_Aster displacement row has invalid {kind} "
                        f"{component}={raw_value!r} for node {nid!r}; {kind}s must "
                        "be finite numeric values. Refusing to mark the node covered."
                    ) from exc
                if not np.isfinite(value):
                    raise RuntimeError(
                        f"Code_Aster displacement row has invalid {kind} "
                        f"{component}={raw_value!r} for node {nid!r}; {kind}s must "
                        "be finite numeric values. Refusing to mark the node covered."
                    )
                return value

            translations = [finite_component(component, "translation") for component in ("DX", "DY", "DZ")]
            rotations = [
                np.nan
                if row.get(component, "").strip() == "-"
                else finite_component(component, "rotation")
                for component in ("DRX", "DRY", "DRZ")
            ]
            disp = np.array([*translations, *rotations])
            if nid in results.node_results:
                results.node_results[nid].displacement = disp
                covered_model_nodes.add(nid)
                continue
            results.analysis_node_results[nid] = NodeResult(node_id=nid, displacement=disp)
            if nid not in analysis_mesh_node_ids:
                results.parser_diagnostics.append(
                    f"Preserved displacement row for non-native analysis node {nid!r} without mesh source mapping."
                )
        return covered_model_nodes

    def _result_element_lookup(self, model: TubaModel) -> dict[str, Element]:
        lookup = {element.id: element for element in model.elements}
        for element in model.elements:
            if element.type != "pipe_bend":
                continue
            for segment_id, _, _ in self._bend_segment_node_pairs(element, self._BEND_SEGMENTS):
                lookup[segment_id] = element
        return lookup

    def _parse_effo_table(
        self,
        model: TubaModel,
        work_dir: Path,
        results: FEAResults,
        node_label_map: dict[str, str],
        element_label_map: dict[str, str],
    ) -> set[tuple[str, str]]:
        """Parse internal-force table (unit 38, ``EFGE_ELNO``).

        Each row contains ``MAILLE`` (element) and ``NOEUD`` (node).
        For a SEG2 element there are exactly two rows — one per end-node.
        We map them to ``forces_n1`` / ``forces_n2`` by matching the
        ``NOEUD`` field against the element's ``n1`` / ``n2``.

        Returns the model element/node endpoints that received parsed forces.
        """
        rows = self._parse_csv_table(work_dir / "study_effo.csv")
        # Build a quick lookup: element_id → Element
        element_lookup = self._result_element_lookup(model)
        covered: set[tuple[str, str]] = set()

        for row in rows:
            raw_eid = row.get("MAILLE", "").strip()
            raw_nid = row.get("NOEUD", "").strip()
            eid = element_label_map.get(raw_eid, raw_eid)
            nid = node_label_map.get(raw_nid, raw_nid)
            
            # The mesh subdivides each elbow into sub-elements (pipe_bend_0_s0, _s1, …)
            # for FE accuracy. Fold them back to the single model bend element. Forces
            # attach only at the elbow's own end nodes (n1/n2) below — exactly the input
            # the B31.3 end-node SIF check consumes; interior sub-node moments feed FE
            # displacement fidelity, not the code check, so dropping them here is intended.
            elem = element_lookup.get(eid)
            if elem is None or nid not in (elem.n1, elem.n2):
                continue
            orig_eid = elem.id

            def finite_force_component(
                component: str,
                *aliases: str,
                allow_unavailable: bool = False,
            ) -> float:
                raw_value = ""
                for alias in aliases:
                    candidate = row.get(alias)
                    if candidate is not None and candidate.strip():
                        raw_value = candidate.strip()
                        break
                if allow_unavailable and raw_value == "-":
                    return np.nan
                try:
                    value = float(raw_value)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError(
                        f"Code_Aster row has invalid internal-force component "
                        f"{component}={raw_value!r} for element endpoint {orig_eid}:{nid}; "
                        "all force and moment components must be finite numeric values. "
                        "Refusing to mark the endpoint covered."
                    ) from exc
                if not np.isfinite(value):
                    raise RuntimeError(
                        f"Code_Aster row has invalid internal-force component "
                        f"{component}={raw_value!r} for element endpoint {orig_eid}:{nid}; "
                        "all force and moment components must be finite numeric values. "
                        "Refusing to mark the endpoint covered."
                    )
                return value

            allow_unavailable = elem.type in ("bar", "cable")
            forces = np.array([
                finite_force_component("N", "N", "NXX"),
                finite_force_component("VY", "VY", allow_unavailable=allow_unavailable),
                finite_force_component("VZ", "VZ", allow_unavailable=allow_unavailable),
                finite_force_component("MT", "MT", allow_unavailable=allow_unavailable),
                finite_force_component("MFY", "MFY", allow_unavailable=allow_unavailable),
                finite_force_component("MFZ", "MFZ", allow_unavailable=allow_unavailable),
            ])
            er = results.element_results[orig_eid]
            if nid == elem.n1:
                er.forces_n1 = forces
                covered.add((orig_eid, nid))
            elif nid == elem.n2:
                er.forces_n2 = forces
                covered.add((orig_eid, nid))
        return covered

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
            raw_values = [row.get(key, "").strip() for key in ("DX", "DY", "DZ", "DRX", "DRY", "DRZ")]
            try:
                reaction = np.asarray(raw_values, dtype=float)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Code_Aster row has invalid reaction components for support node {nid!r}; "
                    "all six force and moment components must be finite numeric values."
                ) from exc
            if not np.isfinite(reaction).all():
                raise RuntimeError(
                    f"Code_Aster row has invalid reaction components for support node {nid!r}; "
                    "all six force and moment components must be finite numeric values."
                )
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
        if not any(elem.type in {"pipe_straight", "pipe_bend"} for elem in model.elements):
            return
        rows = self._parse_csv_table(work_dir / "study_sieq.csv")
        element_lookup = self._result_element_lookup(model)
        analysis_tangents = self._read_analysis_element_tangents(work_dir)

        for row in rows:
            raw_eid = row.get("MAILLE", "").strip()
            raw_nid = row.get("NOEUD", "").strip()
            eid = element_label_map.get(raw_eid, raw_eid)
            nid = node_label_map.get(raw_nid, raw_nid)

            elem = element_lookup.get(eid)
            if elem is None:
                continue
            orig_eid = elem.id
            try:
                vmis = float(row.get("VMIS", ""))
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Code_Aster row has invalid VMIS value for element {orig_eid!r}."
                ) from exc
            if not np.isfinite(vmis):
                raise RuntimeError(
                    f"Code_Aster row has invalid VMIS value for element {orig_eid!r}."
                )

            subpoint = row.get("SOUS_POINT", "").strip()
            if subpoint:
                centerline_position: list[float] | None = None
                try:
                    centerline_position = [
                        float(row["COOR_X"]),
                        float(row["COOR_Y"]),
                        float(row["COOR_Z"]),
                    ]
                except (KeyError, ValueError, TypeError):
                    centerline_position = None
                try:
                    subpoint_index: int | str = int(float(subpoint))
                except (ValueError, TypeError):
                    subpoint_index = subpoint
                tangent = analysis_tangents.get(eid)
                if tangent is None:
                    tangent = self._model_element_tangent(model, elem)
                display_position = self._tuyau_subpoint_display_position(
                    model=model,
                    element=elem,
                    centerline_position=centerline_position,
                    tangent=tangent,
                    subpoint_index=subpoint_index,
                )
                results.tuyau_subpoints.append(
                    {
                        "field": "SIEQ_ELNO",
                        "component": "VMIS",
                        "unit": "Pa",
                        "value": vmis,
                        "element_id": orig_eid,
                        "analysis_element_id": eid,
                        "solver_element_label": raw_eid,
                        "node_id": nid or None,
                        "solver_node_label": raw_nid or None,
                        "subpoint_index": subpoint_index,
                        "centerline_position": centerline_position,
                        "display_position": display_position,
                        "position_source": (
                            "code_aster_tuyau_subpoint_formula"
                            if display_position is not None
                            else "centerline_from_sieq_elno"
                        ),
                        "tuyau_ncou": _CODE_ASTER_TUYAU_NCOU,
                        "tuyau_nsec": _CODE_ASTER_TUYAU_NSEC,
                    }
                )

            er = results.element_results[orig_eid]
            if nid == elem.n1:
                er.von_mises_n1 = vmis
            elif nid == elem.n2:
                er.von_mises_n2 = vmis
            er.max_von_mises = (
                vmis if not np.isfinite(er.max_von_mises)
                else max(er.max_von_mises, vmis)
            )

    @staticmethod
    def _read_analysis_element_tangents(work_dir: Path) -> dict[str, np.ndarray]:
        manifest_path = work_dir / "study_manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mesh = manifest["analysis_mesh"]
            nodes = mesh["nodes"]
            elements = mesh["elements"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return {}

        tangents: dict[str, np.ndarray] = {}
        for element_id, node_ids in elements.items():
            if not isinstance(node_ids, list) or len(node_ids) < 2:
                continue
            try:
                start = np.asarray(nodes[node_ids[0]], dtype=float)
                end = np.asarray(nodes[node_ids[-1]], dtype=float)
            except (KeyError, TypeError, ValueError):
                continue
            tangent = end - start
            norm = float(np.linalg.norm(tangent))
            if norm > 1.0e-12:
                tangents[str(element_id)] = tangent / norm
        return tangents

    @staticmethod
    def _model_element_tangent(model: TubaModel, element: Element) -> np.ndarray | None:
        try:
            start = np.asarray(model.nodes[element.n1].coords, dtype=float)
            end = np.asarray(model.nodes[element.n2].coords, dtype=float)
        except (KeyError, AttributeError, TypeError, ValueError):
            return None
        tangent = end - start
        norm = float(np.linalg.norm(tangent))
        return tangent / norm if norm > 1.0e-12 else None

    @staticmethod
    def _tuyau_subpoint_display_position(
        *,
        model: TubaModel,
        element: Element,
        centerline_position: list[float] | None,
        tangent: np.ndarray | None,
        subpoint_index: int | str,
    ) -> list[float] | None:
        if centerline_position is None or tangent is None or not isinstance(subpoint_index, int):
            return None
        section = model.sections.get(element.section)
        if not isinstance(section, PipeSection):
            return None
        y_axis, z_axis = CodeAsterSolver._tuyau_cross_section_axes(tangent)
        y_offset, z_offset = CodeAsterSolver._code_aster_tuyau_fibre_offset(
            subpoint_index,
            r_ext=section.OD / 2.0,
            thickness=section.WT,
        )
        center = np.asarray(centerline_position, dtype=float)
        point = center + y_offset * y_axis + z_offset * z_axis
        return [float(value) for value in point]

    @staticmethod
    def _code_aster_tuyau_fibre_offset(
        subpoint_index: int,
        *,
        r_ext: float,
        thickness: float,
        ncou: int = _CODE_ASTER_TUYAU_NCOU,
        nsec: int = _CODE_ASTER_TUYAU_NSEC,
    ) -> tuple[float, float]:
        station = subpoint_station(subpoint_index, nsec=nsec, ncou=ncou)
        if station is None:
            return 0.0, 0.0
        r_int = r_ext - thickness
        radius = r_int + thickness * station.radius_fraction
        y_offset = radius * math.cos(station.angle_rad)
        z_offset = -radius * math.sin(station.angle_rad)
        return y_offset, z_offset

    @staticmethod
    def _tuyau_cross_section_axes(tangent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x_axis = np.asarray(tangent, dtype=float)
        x_axis = x_axis / np.linalg.norm(x_axis)
        y_axis = _TUBA_GENE_TUYAU - float(np.dot(_TUBA_GENE_TUYAU, x_axis)) * x_axis
        if float(np.linalg.norm(y_axis)) <= 1.0e-12:
            fallback = np.array([0.0, 1.0, 0.0], dtype=float)
            y_axis = fallback - float(np.dot(fallback, x_axis)) * x_axis
        if float(np.linalg.norm(y_axis)) <= 1.0e-12:
            fallback = np.array([1.0, 0.0, 0.0], dtype=float)
            y_axis = fallback - float(np.dot(fallback, x_axis)) * x_axis
        y_axis = y_axis / np.linalg.norm(y_axis)
        z_axis = np.cross(x_axis, y_axis)
        z_axis = z_axis / np.linalg.norm(z_axis)
        return y_axis, z_axis

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
