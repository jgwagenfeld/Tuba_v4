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
#: The notebooks this repository keeps, and why there are only two.
#:
#: The course used to be fourteen. Twelve of them taught what the gallery,
#: the tutorial and modeling.md now teach better - several by hand-copying a
#: gallery model and reading that gallery's own evidence, two by stating that
#: Tuba emits no friction law to Code_Aster while aster_comm.py writes
#: COULOMB= and native-friction-review publishes the result. These two remain
#: because nothing else in the repo runs what they run.
EXPECTED_NOTEBOOKS = {
    # The only exercise of PLY, glTF, Blender-script and standalone-HTML export.
    "04_visualization_gallery.ipynb",
    # The only executed IFC4 export -> inspect -> re-import round-trip.
    "07_bim_data_exchange.ipynb",
}

#: Notebooks that must emit an image, because a render is their whole point.
#: 07 is text-only by design: it round-trips IFC and prints, so it is absent.
VISIBLE_NOTEBOOKS = {
    "04_visualization_gallery.ipynb",
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
        # Names rather than a count: a count says fourteen became thirteen, a
        # name says which one, and it catches a rename that a count sails past.
        found = {path.name for path in notebooks}
        if found != EXPECTED_NOTEBOOKS:
            missing = sorted(EXPECTED_NOTEBOOKS - found)
            unexpected = sorted(found - EXPECTED_NOTEBOOKS)
            raise RuntimeError(
                f"notebooks/ does not match EXPECTED_NOTEBOOKS; missing={missing} unexpected={unexpected}"
            )
        if args.real_solver_smoke:
            # 04 is the one that renders a solved result, so it is the smoke test.
            notebooks = [snapshot / "notebooks" / "04_visualization_gallery.ipynb"]
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
