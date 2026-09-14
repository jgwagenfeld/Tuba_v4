"""Validate and execute the notebook course from an isolated candidate copy."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
VISIBLE_NOTEBOOKS = {
    "00_welcome_and_setup.ipynb",
    "03_stress_analysis_and_compliance.ipynb",
    "04_visualization_gallery.ipynb",
    "10_interactive_postprocessor.ipynb",
    "visualize_elements_and_supports.ipynb",
}


def candidate_snapshot(destination: Path) -> Path:
    files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode().split("\0")
    for relative in filter(None, files):
        source = ROOT / relative
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


def execute_notebook(path: Path, *, real_solver: bool = False) -> set[str]:
    notebook = nbformat.read(path, as_version=nbformat.NO_CONVERT)
    nbformat.validate(notebook)
    env = os.environ.copy()
    env.update(
        {
            "MPLBACKEND": "Agg",
            "PYVISTA_OFF_SCREEN": "true",
            "TUBA_NOTEBOOK_BACKEND": "static",
            "TUBA_NOTEBOOK_RUN_CODE_ASTER": "1" if real_solver else "0",
        }
    )
    NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        allow_errors=False,
    ).execute(cwd=path.parent.parent, env=env)
    mimes = {
        mime
        for cell in notebook.cells
        for output in cell.get("outputs", [])
        for mime in (output.get("data") or {})
    }
    return mimes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--real-solver-smoke", action="store_true")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="tuba-notebooks-") as tmpdir:
        snapshot = candidate_snapshot(Path(tmpdir))
        notebooks = sorted((snapshot / "notebooks").glob("*.ipynb"))
        if len(notebooks) != 14:
            raise RuntimeError(f"Expected 14 notebooks, found {len(notebooks)}")
        if args.real_solver_smoke:
            notebooks = [snapshot / "notebooks" / "visualize_elements_and_supports.ipynb"]
        for path in notebooks:
            notebook = nbformat.read(path, as_version=nbformat.NO_CONVERT)
            nbformat.validate(notebook)
            if args.schema_only:
                print(f"SCHEMA {path.name}")
                continue
            mimes = execute_notebook(path, real_solver=args.real_solver_smoke)
            if path.name in VISIBLE_NOTEBOOKS and not any(mime.startswith("image/") for mime in mimes):
                raise RuntimeError(f"{path.name} produced no visible image MIME; got {sorted(mimes)}")
            print(f"EXECUTED {path.name} MIME={','.join(sorted(mimes)) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
