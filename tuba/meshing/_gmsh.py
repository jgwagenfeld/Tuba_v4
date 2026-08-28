"""Process-global Gmsh model ownership."""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Any, Iterator
from uuid import uuid4

# ponytail: Gmsh is process-global; use subprocess isolation if parallel meshing becomes necessary.
_GMSH_LOCK = RLock()


@contextmanager
def gmsh_model(
    gmsh: Any,
    name_prefix: str,
    *,
    initialize_args: list[str] | None = None,
    options: dict[str, float] | None = None,
) -> Iterator[str]:
    """Yield an isolated model and restore any caller-owned Gmsh session."""
    with _GMSH_LOCK:
        owned_session = not bool(gmsh.isInitialized())
        previous_model = gmsh.model.getCurrent() if not owned_session else ""
        previous_options = (
            {name: gmsh.option.getNumber(name) for name in options or {}}
            if not owned_session
            else {}
        )
        model_name = f"{name_prefix}_{uuid4().hex}"
        model_added = False
        try:
            if owned_session:
                if initialize_args is None:
                    gmsh.initialize()
                else:
                    gmsh.initialize(initialize_args)
            gmsh.model.add(model_name)
            model_added = True
            for name, value in (options or {}).items():
                gmsh.option.setNumber(name, value)
            yield model_name
        finally:
            if gmsh.isInitialized():
                if model_added:
                    try:
                        gmsh.model.setCurrent(model_name)
                        gmsh.model.remove()
                    except Exception:
                        pass
                if owned_session:
                    gmsh.finalize()
                else:
                    for name, value in previous_options.items():
                        gmsh.option.setNumber(name, value)
                    if previous_model:
                        gmsh.model.setCurrent(previous_model)
