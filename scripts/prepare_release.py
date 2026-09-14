"""Synchronize generated viewer assets and remove stale package build output."""

from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None and os.name == "nt":
        npm = str(Path(os.environ["ProgramFiles"]) / "nodejs" / "npm.cmd")
    subprocess.run([npm, "run", "build"], cwd=ROOT / "viewer", check=True)

    build_dir = (ROOT / "build").resolve()
    if build_dir.parent != ROOT.resolve():
        raise RuntimeError(f"Refusing to clean unexpected build directory: {build_dir}")
    if build_dir.exists():
        for attempt in range(3):
            try:
                shutil.rmtree(build_dir)
                break
            except OSError as exc:
                transient = exc.errno == errno.ENOTEMPTY or getattr(exc, "winerror", None) == 145
                if not transient or attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
