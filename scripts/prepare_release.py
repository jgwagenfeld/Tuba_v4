"""Synchronize generated viewer assets and remove stale package build output."""

from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]


def main(*, out_dir: Path | None = None) -> int:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None and os.name == "nt":
        npm = str(Path(os.environ["ProgramFiles"]) / "nodejs" / "npm.cmd")
    command = [npm, "run", "build"]
    if out_dir is not None:
        command += ["--", "--outDir", str(Path(out_dir).resolve())]
    subprocess.run(command, cwd=ROOT / "viewer", check=True)
    if out_dir is not None:
        return 0

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
