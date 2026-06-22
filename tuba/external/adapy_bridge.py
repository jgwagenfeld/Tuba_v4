"""Optional bridge between Tuba and ada-py.

This module must not make ada-py a core dependency. It imports `ada` only inside
helper functions and raises an actionable error when the optional dependency is
missing.
"""

from __future__ import annotations

from typing import Any


def adapy_available() -> bool:
    try:
        import ada  # noqa: F401
    except ImportError:
        return False
    return True


def require_adapy() -> Any:
    try:
        import ada
    except ImportError as exc:
        raise ImportError(
            "The optional adapy bridge requires ada-py. Install the bridge extra only after accepting the "
            "GPL-3.0-or-later dependency boundary."
        ) from exc
    return ada


def tuba_to_adapy(model: Any) -> Any:
    ada = require_adapy()
    assembly = ada.Assembly(model.project_name)
    part = ada.Part(model.project_name)
    assembly / part
    return assembly
