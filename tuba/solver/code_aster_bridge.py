"""Bridge script executed by a Code_Aster Python interpreter."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def run_export(export_path: Path, workdir: Path | None = None) -> int:
    export_path = export_path.resolve()
    root = workdir.resolve() if workdir is not None else export_path.parent
    if not export_path.exists():
        print(f"Code_Aster export file not found: {export_path}", file=sys.stderr)
        return 2
    try:
        return _run_export_with_python_api(export_path)
    except ImportError:
        return _run_export_with_cli(export_path, root)


def _run_export_with_python_api(export_path: Path) -> int:
    # Conda puts run_aster in site-packages; its relative root misses the prefix.
    prefix = Path(os.environ.get("RUNASTER_ROOT", sys.prefix))
    if any((prefix / "share" / "aster" / name).is_file() for name in ("config.yaml", "config.json")):
        os.environ.setdefault("RUNASTER_ROOT", str(prefix))
        os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", os.defpath)
        for name, relative in {
            "ASTER_LIBDIR": "lib",
            "ASTER_ELEMENTSDIR": "lib",
            "ASTER_DATADIR": "share/aster",
            "ASTER_LOCALEDIR": "share/locale/aster",
        }.items():
            os.environ.setdefault(name, str(prefix / relative))
    from run_aster.export import Export
    from run_aster.run import RunAster

    export = Export(filename=str(export_path), check=True)
    # The default fort.6 output is copied to the export's required study.mess.
    runner = RunAster.factory(export, tee=True)
    original_cwd = Path.cwd()
    # Reusing fort.80 makes a repeated solve append duplicate MED fields.
    with TemporaryDirectory(prefix="tuba-code-aster-") as scratch:
        try:
            status = runner.execute(scratch)
        finally:
            os.chdir(original_cwd)
    if status is None:
        return 0
    return int(getattr(status, "exitcode", status))


def _run_export_with_cli(export_path: Path, workdir: Path) -> int:
    result = subprocess.run(["run_aster", str(export_path)], cwd=str(workdir))
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python code_aster_bridge.py")
    parser.add_argument("export_positional", nargs="?", help="Path to study.export")
    parser.add_argument("--export", default=None, help="Path to study.export")
    parser.add_argument("--workdir", default=None, help="Directory containing Code_Aster study files")
    args = parser.parse_args(argv)
    export_arg = args.export or args.export_positional
    if not export_arg:
        parser.error("study.export path is required")
    export_path = Path(export_arg)
    workdir = Path(args.workdir) if args.workdir else export_path.parent
    return run_export(export_path, workdir)


if __name__ == "__main__":
    raise SystemExit(main())
