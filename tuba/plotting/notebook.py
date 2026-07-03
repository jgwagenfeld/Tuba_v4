"""Notebook visualization backend selection."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


INTERACTIVE_NOTEBOOK_BACKEND = "html"
STATIC_NOTEBOOK_BACKEND = "static"
NOTEBOOK_BACKEND_ENV = "TUBA_NOTEBOOK_BACKEND"


def resolve_notebook_backend(
    *,
    default: str = INTERACTIVE_NOTEBOOK_BACKEND,
    env: Mapping[str, str] | None = None,
) -> str:
    """Return the PyVista notebook backend for this process.

    Local notebooks (including VS Code) default to a zoomable, rotatable
    embedded HTML scene. The ``html`` backend renders as a self-contained
    ``iframe`` srcdoc with no localhost server, so it avoids the front-end/proxy
    failures of the trame ``client``/``server`` backends. CI and explicitly
    headless runs default to static output so nbconvert checks stay reliable.
    Set ``TUBA_NOTEBOOK_BACKEND`` to override either mode (or
    ``TUBA_NOTEBOOK_STATIC`` to force a static image locally).
    """

    values = os.environ if env is None else env
    configured = values.get(NOTEBOOK_BACKEND_ENV)
    if configured:
        return configured.strip().lower()
    if _truthy(values.get("CI")) or _truthy(values.get("TUBA_NOTEBOOK_STATIC")):
        return STATIC_NOTEBOOK_BACKEND
    return default


def configure_notebook_backend(
    *,
    default: str = INTERACTIVE_NOTEBOOK_BACKEND,
    pyvista_module: Any | None = None,
) -> str:
    """Configure PyVista's Jupyter backend and return the selected backend."""

    backend = resolve_notebook_backend(default=default)
    pv = pyvista_module
    if pv is None:
        import pyvista as pv
    pv.set_jupyter_backend(backend)
    return backend


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
