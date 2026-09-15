"""A study's settings, checked once when the study loads.

A study names the operations it solves (``LOAD_CASES``), how the model compiles (``SOLVER_OPTIONS``) and which
elements a volume study meshes as solids (``VOLUME_EXPORT``). What a solve could only fail on later is refused
here, before the model runs:
- names that cannot each own an evidence folder (spec decision 10);
- options that choose how Code_Aster runs on this machine, or that the solver rejects;
- volume exports the exporter refuses (decision 19: the tensor-stress table is never a study's choice).
"""

from __future__ import annotations

from dataclasses import dataclass
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
