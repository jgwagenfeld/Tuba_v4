"""Bridge script executed by a Code_Aster Python interpreter."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_export(export_path: Path, workdir: Path | None = None) -> int:
    export_path = export_path.resolve()
    root = workdir.resolve() if workdir is not None else export_path.parent
    if not export_path.exists():
        print(f"Code_Aster export file not found: {export_path}", file=sys.stderr)
        return 2
    try:
        return _run_export_with_python_api(export_path, root)
    except ImportError:
        return _run_export_with_cli(export_path, root)


def _run_export_with_python_api(export_path: Path, workdir: Path) -> int:
    from run_aster.export import Export
    from run_aster.run import RunAster

    export = Export(filename=str(export_path), check=True)
    runner = RunAster.factory(export, tee=True, output=str(workdir / "stdout.run_aster_api.log"))
    status = runner.execute(str(workdir))
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
