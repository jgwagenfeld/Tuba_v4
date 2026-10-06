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
    options: dict[str, float | str] | None = None,
) -> Iterator[str]:
    """Yield an isolated model and restore any caller-owned Gmsh session."""
    # C++ terminal output bypasses Python redirects and would corrupt MCP stdio.
    options = {"General.Terminal": 0, **(options or {})}
    with _GMSH_LOCK:
        owned_session = not bool(gmsh.isInitialized())
        previous_model = gmsh.model.getCurrent() if not owned_session else ""
        previous_options = (
            {
                name: (gmsh.option.getString(name) if isinstance(value, str) else gmsh.option.getNumber(name))
                for name, value in (options or {}).items()
            }
            if not owned_session
            else {}
        )
        model_name = f"{name_prefix}_{uuid4().hex}"
        model_added = False
        try:
            if owned_session:
                # Studio can build geometry on a worker thread; signal handlers
                # belong to the application's main thread, not the mesher.
                gmsh.initialize(initialize_args or [], interruptible=False)
            gmsh.model.add(model_name)
            model_added = True
            for name, value in (options or {}).items():
                setter = gmsh.option.setString if isinstance(value, str) else gmsh.option.setNumber
                setter(name, value)
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
                        setter = gmsh.option.setString if isinstance(value, str) else gmsh.option.setNumber
                        setter(name, value)
                    if previous_model:
                        gmsh.model.setCurrent(previous_model)
