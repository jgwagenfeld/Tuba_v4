"""Synchronize generated viewer assets and remove stale package build output."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


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
        shutil.rmtree(build_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
