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
import math
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple, Optional

from tuba.model import (
    LoadCase,
    TubaModel,
)
from tuba.solver.base import (
    FEAResults,
)
from tuba.solver.aster_sidecar import (
    SolverNameMap,
    build_solver_name_map,
    dump_solver_sidecar,
    dump_study_manifest,
    load_and_validate_artifact_chain,
)
from tuba.solver.code_aster_runtime import (
    CodeAsterExecution,
    CodeAsterRuntimeConfig,
    run_code_aster_export,
    write_code_aster_execution_attestation,
)
from tuba.analysis import AnalysisRun, AnalysisStudy
from tuba.project.evidence import exported_study_matches
from tuba.solver.modelisation import PipeModelization, needs_discrete_element
from tuba.analysis.provenance import (
    SolverInputIdentity,
    build_solver_input_identity,
)
from tuba.solver.aster_comm import _CommWriterMixin
from tuba.solver.aster_mesh import _MeshWriterMixin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class StudyInputs(NamedTuple):
    """What a beam or TUYAU export compiles, resolved without writing anything."""

    load_case_name: str
    load_case: LoadCase
    compiler_inputs: Optional[dict[str, Any]]
    solver_input_identity: SolverInputIdentity


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
    line_segments : int, optional
        Solver segments per straight beam, beam-modelled pipe or cable (default 8).
        Increase to check mesh convergence; 1 explicitly requests a single span.
    runner_command : str, optional
        Shell command used inside WSL or the container before ``study.export``.
        When omitted, Tuba tries ``as_run``, ``aster``, and the documented
        ``conda run -n base aster`` path.
    """

    # Name reported in :class:`FEAResults`
    SOLVER_NAME = "Code_Aster"

    #: Constructor options that choose how Code_Aster runs on this machine: not the study's
    #: choice and not part of the solver input identity. ``timeout_seconds`` is not here,
    #: because no environment variable or command-line flag sets a solve's timeout.
    RUNTIME_OPTIONS = frozenset(
        {"work_dir", "exec_method", "docker_image", "wsl_distro", "runner_command", "bridge_python"}
    )

    def __init__(
        self,
        work_dir: Optional[str] = None,
        exec_method: Optional[str] = None,
        docker_image: Optional[str] = None,
        wsl_distro: Optional[str] = None,
        runner_command: Optional[str] = None,
        bridge_python: Optional[str] = None,
        timeout_seconds: int = 7200,
        pipe_modelization: PipeModelization | str = PipeModelization.TUYAU_3M,
        load_path=None,
        load_step: float = 0.1,
        line_segments: int = 8,
    ) -> None:
        if isinstance(line_segments, bool) or not isinstance(line_segments, int) or line_segments < 1:
            raise ValueError("line_segments must be a positive integer.")
        if isinstance(load_step, bool) or not isinstance(load_step, (int, float)) or not math.isfinite(load_step) or not 0 < load_step <= 1:
            raise ValueError("load_step must be finite and in (0, 1].")
        self.line_segments = line_segments
        self.pipe_modelization = PipeModelization(pipe_modelization)
        if isinstance(load_path, str):
            raise ValueError("load_path must be a sequence of names, not a string.")
        self.load_path = tuple(load_path) if load_path is not None else None
        self.load_step = load_step
        if self.pipe_modelization is PipeModelization.POU_D_T:
            self._BEND_SEGMENTS = 32
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
        self._bend_node_cache: dict = {}

    # ==================================================================
    # Public API
    # ==================================================================

    def solve(
        self,
        model: TubaModel,
        load_case_name: Optional[str] = None,
        *,
        force: bool = False,
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
        return self.solve_exported_study(model, study, force=force)

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
        self._bend_node_cache.clear()
        if self.pipe_modelization is PipeModelization.SOLID_3D:
            raise ValueError("Use export_volume_study for SOLID_3D.")
        # Resolve load case ------------------------------------------------
        if self.load_path is not None:
            if not self.load_path or isinstance(self.load_path, str):
                raise ValueError('load_path must be a nonempty sequence of load-case names.')
            if load_case_name is not None and load_case_name != self.load_path[-1]:
                raise ValueError('The compatibility load case must be the final load_path stage.')
            load_case_name = self.load_path[-1]
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

    def analysis_study_inputs(self, model: TubaModel, load_case_name: Optional[str] = None) -> StudyInputs:
        """Resolve the solved case and fingerprint what :meth:`export_analysis_study` compiles.

        It writes, meshes and solves nothing, so a caller can ask which identity an export
        of the current model would attest (spec decision 15) without exporting.
        """
        if self.pipe_modelization is PipeModelization.SOLID_3D:
            raise ValueError("Use export_volume_study for SOLID_3D.")
        if self.load_path is not None:
            if not self.load_path or isinstance(self.load_path, str):
                raise ValueError('load_path must be a nonempty sequence of load-case names.')
            if load_case_name is not None and load_case_name != self.load_path[-1]:
                raise ValueError('The compatibility load case must be the final load_path stage.')
            load_case_name = self.load_path[-1]
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()
        compiler_inputs = (
            {"pipe_modelization": self.pipe_modelization.value, "bend_segments": self._BEND_SEGMENTS}
            if self.pipe_modelization is PipeModelization.POU_D_T else None
        )
        if any(len(self._straight_segment_node_pairs(e)) > 1 for e in model.elements if e.type != "pipe_bend"):
            compiler_inputs = dict(compiler_inputs or {}, line_segments=self.line_segments)
        if any(needs_discrete_element(s) for s in model.supports):
            # CREA_POI1 once named its node with NOEUD and put these supports on the wrong node;
            # evidence solved before GROUP_NO lacks this input, so it reads stale.
            compiler_inputs = dict(compiler_inputs or {}, discrete_support_nodes="GROUP_NO")
        from tuba.solver.aster_contact import shoes, validate_path
        contact_specs = shoes(model, self.pipe_modelization)
        if self.load_path is not None and (not contact_specs or self.pipe_modelization is not PipeModelization.POU_D_T):
            raise ValueError("load_path histories require pipe_modelization='POU_D_T' and a resting shoe.")
        if contact_specs:
            if self.load_path is not None:
                names, _cases = validate_path(model, load_case, self.load_path)
            else:
                names = (load_case_name,)
            compiler_inputs = dict(compiler_inputs or {}, pipe_modelization=self.pipe_modelization.value,
                                  load_path=list(names), load_step=self.load_step,
                                  contact_law='DIS_CHOC', contact_stiffness_defaults=[1e10, 1e8])
            if self.load_path is not None:
                model_dict = model.to_dict()
                all_cases = {**model_dict.get('load_cases', {}), **model_dict.get('operations', {})}
                compiler_inputs['load_path_inputs'] = {name: all_cases[name] for name in names}
        solver_input_identity = build_solver_input_identity(
            model, load_case_name, compiler_inputs=compiler_inputs,
        )
        return StudyInputs(load_case_name, load_case, compiler_inputs, solver_input_identity)

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: Optional[str] = None,
        output_dir: Optional[str | Path] = None,
    ) -> AnalysisStudy:
        """Generate Code_Aster input files plus a traceable analysis manifest."""
        self._bend_node_cache.clear()
        load_case_name, load_case, compiler_inputs, solver_input_identity = self.analysis_study_inputs(
            model, load_case_name
        )

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
            metadata={
                "project_name": model.project_name,
                **({"compiler_inputs": compiler_inputs} if compiler_inputs is not None else {}),
                "pipe_stress_exported": self.pipe_modelization is PipeModelization.TUYAU_3M and any(
                    element.type in {"pipe_straight", "pipe_bend"} for element in model.elements
                ),
            },
            solver_input_identity=solver_input_identity,
        )
        dump_study_manifest(manifest_path, study, analysis_mesh)
        return study

    def export_mixed_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str,
        output_dir: str | Path,
    ) -> AnalysisStudy:
        """Generate a MED-backed mixed Code_Aster study without running the solver."""
        if self.load_path is not None:
            raise ValueError('Native contact load paths require POU_D_T; volume/mixed paths are unsupported.')
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
        export_tensor_stress: bool = False,
    ) -> AnalysisStudy:
        """Export a native Gmsh pipe-volume study without claiming solver results."""
        if self.load_path is not None:
            raise ValueError('Native contact load paths require POU_D_T; volume/mixed paths are unsupported.')
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

    def volume_study_inputs(
        self,
        model: TubaModel,
        load_case_name: str | None,
        *,
        element_ids,
        max_element_size: float,
        element_order: int = 2,
        export_tensor_stress: bool = False,
    ):
        """Resolve and fingerprint what :meth:`export_volume_study` compiles, without meshing or writing."""
        if self.load_path is not None:
            raise ValueError('Native contact load paths require POU_D_T; volume/mixed paths are unsupported.')
        from tuba.solver.aster_volume import volume_study_inputs

        return volume_study_inputs(
            model,
            load_case_name,
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
        export_tensor_stress: bool = False,
        force: bool = False,
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
        return self.solve_exported_study(model, study, force=force)

    def solve_exported_study(
        self,
        model: TubaModel,
        study: AnalysisStudy,
        *,
        force: bool = False,
    ) -> AnalysisRun:
        """Execute an exported study and return its verified analysis run.

        A previous solve in the same work directory is reused when its
        attestation still binds to this study's solver input identity. Any
        model edit changes that identity and forces a fresh solve; pass
        ``force=True`` to re-execute regardless.
        """
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
        identity = (manifest_study or study).solver_input_identity
        if force or not exported_study_matches(work_dir, identity):
            execution = self._execute(work_dir)
            write_code_aster_execution_attestation(work_dir, execution, identity)
        else:
            logger.info("Reusing attested Code_Aster solve in %s", work_dir)
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
            "F libr study_contact.json R 42",
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
    # Result parsing (single public entry; see tuba.solver.parse_tables)
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
        from tuba.solver import parse_tables

        return parse_tables.parse_result_artifacts(model, work_dir, load_case_name, study=study)

