"""A study's settings, checked once when the study loads.

A study names the operations it solves (``LOAD_CASES``), how the model compiles (``SOLVER_OPTIONS``) and which
elements a volume study meshes as solids (``VOLUME_EXPORT``). What a solve could only fail on later is refused
here, before the model runs:
- names that cannot each own an evidence folder (spec decision 10);
- options that choose how Code_Aster runs on this machine, or that the solver rejects;
- volume exports the exporter refuses (decision 19: the tensor-stress table is never a study's choice).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tuba.project.evidence import evidence_dir
from tuba.solver.aster import CodeAsterSolver

#: How Code_Aster runs on this machine: not the study's choice, and not part of the solver input identity.
#: A study may set ``timeout_seconds``, because no environment variable or command-line flag sets a solve's timeout.
_RUNTIME = frozenset({"work_dir", "exec_method", "docker_image", "wsl_distro", "runner_command", "bridge_python"})
_VOLUME_REQUIRED = ("element_ids", "max_element_size")
_VOLUME = frozenset({*_VOLUME_REQUIRED, "element_order"})


@dataclass(frozen=True)
class StudySettings:
    """A study's validated settings; ``volume_export`` is None for a study of beams and pipes."""

    operations: tuple[str, ...]
    solver_options: dict[str, Any]
    volume_export: dict[str, Any] | None


def study_settings(study: Any) -> StudySettings:
    """The validated settings of *study*, as :meth:`Project.load_study` returns it.

    Without a study, or without one of its names, that setting takes its default. Raises ValueError for a
    study that cannot be solved as written.
    """
    names = getattr(study, "LOAD_CASES", None) or ()
    if not isinstance(names, (tuple, list)) or not all(isinstance(name, str) for name in names):
        raise ValueError(f"LOAD_CASES must be a tuple of operation names, got {names!r}.")
    for name in names:
        evidence_dir(".", name)  # raises for a name that cannot be an evidence folder
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError(f"LOAD_CASES names an operation twice (names differing only in case share a folder): {names!r}.")
    options = dict(getattr(study, "SOLVER_OPTIONS", None) or {})
    if runtime := sorted(_RUNTIME & set(options)):
        raise ValueError(f"SOLVER_OPTIONS cannot choose how Code_Aster runs on this machine: {', '.join(runtime)}.")
    try:
        CodeAsterSolver(**options)
    except (TypeError, ValueError) as exc:  # an unknown option, or a value the solver refuses
        raise ValueError(f"SOLVER_OPTIONS: {exc}") from exc
    volume = dict(getattr(study, "VOLUME_EXPORT", None) or {}) or None
    if volume is not None:
        if unknown := sorted(set(volume) - _VOLUME):
            raise ValueError(f"VOLUME_EXPORT cannot set {', '.join(unknown)}; it takes element_ids, max_element_size and element_order.")
        if missing := [key for key in _VOLUME_REQUIRED if key not in volume]:
            raise ValueError(f"VOLUME_EXPORT needs {' and '.join(missing)}.")
        if options.get("load_path") is not None:
            raise ValueError("VOLUME_EXPORT cannot follow a load_path: native contact load paths need POU_D_T beams.")
    return StudySettings(tuple(names), options, volume)


#: Marker for a study.py the MCP server manages: LOAD_CASES is synced from model.py's load
#: cases while it is present. A study without it is user-owned and never rewritten. The
#: literal string is baked into generated studies, so it must not change.
STUDY_MARKER = "TUBA_MCP_MANAGED_STUDY"


def _slug(name: str) -> str:
    """Filesystem/identifier-safe slug for scene ids derived from a project name."""
    slug = re.sub(r"_+", "_", "".join(ch.lower() if ch.isalnum() else "_" for ch in name)).strip("_")
    return slug or "model"


def cases_literal(cases: list[str]) -> str:
    """Python tuple literal for load-case names: () , ('Hot',) , ('A', 'B')."""
    inner = ", ".join(repr(case) for case in cases)
    return f"({inner}{',' if len(cases) == 1 else ''})"


def study_scaffold(project_name: str, cases: list[str]) -> str:
    """The managed study.py: solves each of *cases* with Code_Aster for studio review."""
    slug = _slug(project_name)
    return "\n".join(
        [
            f'"""Code_Aster study scaffolded by the Tuba MCP server ({STUDY_MARKER}).',
            "",
            "LOAD_CASES is synced from model.py's load cases while this marker is present, so the",
            "studio's .comm tabs and Solve stay available. Edit build_review freely, or delete the",
            "marker line to take full ownership (the server then leaves this file alone). Run the",
            "studio from the repository root so the examples import below resolves.",
            '"""',
            "",
            "from pathlib import Path",
            "",
            "from examples.code_aster_artifact_review import run_example, solve_or_import",
            "",
            f"LOAD_CASES = {cases_literal(cases)}",
            "SOLVER_OPTIONS: dict = {}",
            "VOLUME_EXPORT = None",
            "",
            "",
            "def build_review(namespace, output, *, artifact_dir=None, force=False):",
            '    """Solve the study cases with Code_Aster and publish the engineering review."""',
            '    if not LOAD_CASES:',
            '        raise ValueError("study.py defines no LOAD_CASES: add the load case to solve (e.g. LOAD_CASES = (\\"Operating\\",)).")',
            '    model = namespace["model"]',
            "    run = None if artifact_dir is not None else solve_or_import(model, LOAD_CASES[0], Path(output) / \"solver\", solver_options=SOLVER_OPTIONS)",
            "    summary = run_example(",
            "        output,",
            "        artifact_dir=artifact_dir,",
            "        run=run,",
            "        model=model,",
            f'        scene_id="scene:{slug}",',
            f'        title="{project_name} review",',
            '        source=namespace["__file__"],',
            "    )",
            '    return Path(summary["bundle_root"])',
            "",
        ]
    )


def load_cases_in(text: str) -> list[str] | None:
    """LOAD_CASES parsed from study source without executing it; None when absent or not plain strings."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "LOAD_CASES"
            and isinstance(node.value, (ast.Tuple, ast.List))
            and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.value.elts)
        ):
            return [item.value for item in node.value.elts]  # type: ignore[misc]
    return None


def replace_load_cases(text: str, cases: list[str]) -> str | None:
    """Rewrite only the LOAD_CASES assignment in *text*; None when it cannot be located."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "LOAD_CASES"
        ):
            lines = text.splitlines(keepends=True)
            lines[node.lineno - 1 : node.end_lineno] = [f"LOAD_CASES = {cases_literal(cases)}\n"]
            return "".join(lines)
    return None


def ensure_study_file(path: Path, *, project_name: str, cases: list[str]) -> dict[str, Any]:
    """Create the managed study.py at *path*, or sync its LOAD_CASES.

    A missing study is scaffolded from *cases*. A managed study keeps its LOAD_CASES (and
    only that line) in sync, so hand edits to build_review survive. A study without the
    marker is user-owned: reported, never rewritten.
    """
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(study_scaffold(project_name, cases), encoding="utf-8", newline="")
        return {"exists": True, "managed": True, "load_cases": cases, "missing_cases": []}
    if STUDY_MARKER not in current:
        known = load_cases_in(current)
        return {
            "exists": True,
            "managed": False,
            "load_cases": known,
            "missing_cases": [case for case in cases if known is None or case not in known],
        }
    synced = replace_load_cases(current, cases)
    if synced is None:  # the marker survived but the assignment did not: re-scaffold
        synced = study_scaffold(project_name, cases)
    if synced != current:
        path.write_text(synced, encoding="utf-8", newline="")
    return {"exists": True, "managed": True, "load_cases": cases, "missing_cases": []}
