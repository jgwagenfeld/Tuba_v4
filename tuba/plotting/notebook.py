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

    Local notebooks default to a zoomable embedded HTML scene. That avoids
    front-end/proxy failures with localhost-backed trame client iframes. CI and
    explicitly headless runs default to static output so nbconvert checks stay
    reliable. Set ``TUBA_NOTEBOOK_BACKEND`` to override either mode.
    """

    values = os.environ if env is None else env
    configured = values.get(NOTEBOOK_BACKEND_ENV)
    if configured:
        return configured.strip().lower()
    if _truthy(values.get("CI")) or _truthy(values.get("TUBA_NOTEBOOK_STATIC")):
        return STATIC_NOTEBOOK_BACKEND
    if _running_in_vscode(values):
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


def _running_in_vscode(values: Mapping[str, str]) -> bool:
    return (
        values.get("TERM_PROGRAM", "").strip().lower() == "vscode"
        or any(key.upper().startswith("VSCODE_") for key in values)
    )
