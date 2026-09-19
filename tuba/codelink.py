"""Authoring-script line linkage (the code <-> 3D link).

Records where the running script created a model record as ``(line, call_line)``.
``line`` is the first frame outside the ``tuba`` package, and it counts only when
that frame runs as ``__main__`` - the studio runs model.py that way - so the MCP
server, a test or a helper module gets no line rather than one from a file the
viewer does not show. ``call_line`` is the outermost call in that same script
when it differs: a helper function in model.py that is called twice gives each
copy its own call line.

Kept beside the model rather than in it: lines are never serialized and never
compared, so moving them changes no fingerprint, no script text, and no test
that compares models.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path
from typing import Any, Optional, Tuple


@cache
def _inside_tuba(filename: str) -> bool:
    import tuba

    package_dir = Path(tuba.__file__).resolve().parent
    return Path(filename).resolve().is_relative_to(package_dir)


def script_lines() -> Tuple[Optional[int], Optional[int]]:
    """Where the running script created a model record: ``(line, call_line)``."""
    frame = sys._getframe()
    while frame is not None and _inside_tuba(frame.f_code.co_filename):
        frame = frame.f_back
    if frame is None or frame.f_globals.get("__name__") != "__main__":
        return None, None
    script, line, call_line = frame.f_code.co_filename, frame.f_lineno, None
    while frame is not None:
        if frame.f_code.co_filename == script and frame.f_globals.get("__name__") == "__main__":
            call_line = frame.f_lineno
        frame = frame.f_back
    return line, (call_line if call_line != line else None)


def script_line_field() -> Any:
    """A record's line in the running script (see :func:`script_lines`): never serialized, never compared."""
    from dataclasses import field

    return field(default=None, compare=False, repr=False)
