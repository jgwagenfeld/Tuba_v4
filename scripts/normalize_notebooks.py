"""Normalize committed course notebooks without changing cell source."""

from __future__ import annotations

from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=nbformat.NO_CONVERT)
        notebook["nbformat"] = nbformat.current_nbformat
        notebook["nbformat_minor"] = nbformat.current_nbformat_minor
        notebook.metadata.pop("widgets", None)
        notebook.metadata["kernelspec"] = {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
        notebook.metadata["language_info"] = {"name": "python"}
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.execution_count = None
                cell.outputs = []
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
