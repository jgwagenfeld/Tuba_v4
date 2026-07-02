"""Notebook helpers for Code_Aster-backed result loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tuba.analysis.code_aster_artifacts import CodeAsterArtifactImport, import_code_aster_artifacts
from tuba.analysis.study import AnalysisStudy
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.base import FEAResults
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCheck, CodeAsterRuntimeConfig, preflight_code_aster_runtimes


REQUIRED_CODE_ASTER_TABLES = (
    "study_depl.csv",
    "study_effo.csv",
    "study_reac.csv",
    "study_sieq.csv",
)
REFRESHED_CODE_ASTER_OUTPUTS = REQUIRED_CODE_ASTER_TABLES + ("study.rmed",)


@dataclass(frozen=True)
class CodeAsterNotebookRun:
    results: FEAResults
    artifact: CodeAsterArtifactImport
    study: AnalysisStudy
    work_dir: Path
    ran_solver: bool
    missing_before_run: tuple[str, ...]


@dataclass(frozen=True)
class CodeAsterNotebookRuntime:
    exec_method: str
    wsl_distro: str | None
    docker_image: str | None


def configure_code_aster_notebook_runtime(
    *,
    exec_method: str = "wsl",
    wsl_distro: str | None = "Ubuntu",
    docker_image: str | None = None,
) -> CodeAsterNotebookRuntime:
    """Configure the default Code_Aster runtime used by notebooks."""
    os.environ["TUBA_CODE_ASTER_EXEC_METHOD"] = exec_method
    if wsl_distro is not None:
        os.environ["TUBA_CODE_ASTER_WSL_DISTRO"] = wsl_distro
    elif "TUBA_CODE_ASTER_WSL_DISTRO" in os.environ:
        del os.environ["TUBA_CODE_ASTER_WSL_DISTRO"]
    if docker_image is not None:
        os.environ["TUBA_CODE_ASTER_DOCKER_IMAGE"] = docker_image
    elif "TUBA_CODE_ASTER_DOCKER_IMAGE" in os.environ:
        del os.environ["TUBA_CODE_ASTER_DOCKER_IMAGE"]
    return CodeAsterNotebookRuntime(
        exec_method=exec_method,
        wsl_distro=wsl_distro,
        docker_image=docker_image,
    )


def load_or_run_code_aster_results(
    model: Any,
    load_case: str,
    work_dir: str | Path,
    *,
    run_solver: bool = True,
    exec_method: str = "auto",
    wsl_distro: str | None = None,
    docker_image: str | None = None,
    solver_factory: Callable[..., Any] = CodeAsterSolver,
) -> CodeAsterNotebookRun:
    """Load Code_Aster result artifacts, running the exported study when requested."""
    root = Path(work_dir)

    if run_solver:
        require_code_aster_runtime(
            exec_method=exec_method,
            wsl_distro=wsl_distro,
            docker_image=docker_image,
        )
        root.mkdir(parents=True, exist_ok=True)
    else:
        missing_before = tuple(_missing_result_tables(root))
        if missing_before:
            raise FileNotFoundError(_missing_tables_message(root, missing_before, run_solver=False))
        artifact = import_code_aster_artifacts(model=model, work_dir=root, study=None, load_case=load_case)
        artifact.results._model = model
        return CodeAsterNotebookRun(
            results=artifact.results,
            artifact=artifact,
            study=artifact.study,
            work_dir=root,
            ran_solver=False,
            missing_before_run=missing_before,
        )

    solver = _make_solver(
        solver_factory,
        root,
        exec_method=exec_method,
        wsl_distro=wsl_distro,
        docker_image=docker_image,
    )
    study = solver.export_analysis_study(model, load_case, root)

    missing_before = tuple(_missing_result_tables(root))
    _remove_result_artifacts(root)
    solver.solve_exported_study(model, study)

    missing_after = tuple(_missing_result_tables(root))
    if missing_after:
        raise FileNotFoundError(_missing_tables_message(root, missing_after, run_solver=True))

    artifact = import_code_aster_artifacts(model=model, work_dir=root, study=study, load_case=load_case)
    artifact.results._model = model
    return CodeAsterNotebookRun(
        results=artifact.results,
        artifact=artifact,
        study=study,
        work_dir=root,
        ran_solver=True,
        missing_before_run=missing_before,
    )


def require_code_aster_runtime(
    *,
    exec_method: str,
    wsl_distro: str | None,
    docker_image: str | None,
) -> CodeAsterRuntimeCheck:
    config = CodeAsterRuntimeConfig(
        exec_method=exec_method,
        wsl_distro=wsl_distro,
        docker_image=_resolve_docker_image(docker_image),
    )
    checks = preflight_code_aster_runtimes(config)
    for check in checks:
        if check.ok:
            return check
    details = "; ".join(
        f"{check.runtime.kind}: {check.reason or check.stderr or check.stdout or 'not ready'}"
        for check in checks
    )
    raise RuntimeError(
        "Code_Aster runtime is not ready. Existing result tables were left in place. "
        "Set RUN_CODE_ASTER = False to load existing artifacts, or configure Code_Aster and rerun. "
        f"Checks: {details}"
    )


def _resolve_docker_image(docker_image: str | None) -> str:
    return docker_image or os.environ.get("TUBA_CODE_ASTER_DOCKER_IMAGE") or CodeAsterRuntimeConfig().docker_image


def _make_solver(
    solver_factory: Callable[..., Any],
    work_dir: Path,
    *,
    exec_method: str,
    wsl_distro: str | None,
    docker_image: str | None,
) -> Any:
    kwargs = {
        "work_dir": str(work_dir),
        "exec_method": exec_method,
    }
    if wsl_distro is not None:
        kwargs["wsl_distro"] = wsl_distro
    if docker_image is None:
        return solver_factory(**kwargs)
    return solver_factory(**kwargs, docker_image=docker_image)


def _missing_result_tables(work_dir: Path) -> list[str]:
    return [name for name in REQUIRED_CODE_ASTER_TABLES if not (work_dir / name).exists()]


def _remove_result_artifacts(work_dir: Path) -> None:
    for name in REFRESHED_CODE_ASTER_OUTPUTS:
        path = work_dir / name
        if path.exists():
            path.unlink()


def _missing_tables_message(work_dir: Path, missing: tuple[str, ...], *, run_solver: bool) -> str:
    base = (
        "Code_Aster result tables are required before this notebook displays solver results. "
        f"Study files are in {work_dir.resolve()}. "
    )
    if run_solver:
        return (
            base
            + "Code_Aster execution finished but did not produce all required study_*.csv tables. "
            f"Missing: {', '.join(missing)}"
        )
    return (
        base
        + "Set RUN_CODE_ASTER = True to execute the solver from the notebook, or run study.export "
        + "with Code_Aster and re-run the cell. "
        + f"Missing: {', '.join(missing)}"
    )
