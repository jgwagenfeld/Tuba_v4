"""Guard: committed notebooks must not carry interactive widget outputs.

Running a notebook in VS Code / JupyterLab now resolves to the interactive
``html`` PyVista backend, whose ``EmbeddableWidget`` bakes a ~1 MB base64 scene
into the ``.ipynb`` (as widget state) and does not render on GitHub. Committed
outputs should stay static -- the CI / headless path emits PNGs. This test fails
if an interactive widget snuck into a committed notebook; re-run the notebook
headless (``TUBA_NOTEBOOK_STATIC=1``) or strip its outputs before committing.
"""

import json
import unittest
from pathlib import Path

NOTEBOOK_DIR = Path(__file__).resolve().parent.parent / "notebooks"
WIDGET_MIME_PREFIX = "application/vnd.jupyter.widget"


def _widget_offenses(nb: dict) -> list[str]:
    reasons: list[str] = []
    if "widgets" in (nb.get("metadata") or {}):
        reasons.append("notebook metadata carries widget state")
    for idx, cell in enumerate(nb.get("cells", [])):
        for output in cell.get("outputs", []):
            widget_mimes = sorted(
                m for m in (output.get("data") or {}) if m.startswith(WIDGET_MIME_PREFIX)
            )
            if widget_mimes:
                reasons.append(f"cell {idx} output has {', '.join(widget_mimes)}")
    return reasons


class TestNotebooksHaveNoWidgetOutputs(unittest.TestCase):
    def test_committed_notebooks_have_no_interactive_widget_outputs(self):
        notebooks = sorted(
            p for p in NOTEBOOK_DIR.glob("**/*.ipynb") if ".ipynb_checkpoints" not in p.parts
        )
        self.assertTrue(notebooks, f"no notebooks found under {NOTEBOOK_DIR}")

        offenders: dict[str, list[str]] = {}
        for path in notebooks:
            nb = json.loads(path.read_text(encoding="utf-8"))
            reasons = _widget_offenses(nb)
            if reasons:
                offenders[path.name] = reasons

        self.assertEqual(
            offenders,
            {},
            "Interactive widget outputs committed (re-run headless or strip outputs):\n"
            + "\n".join(f"  {name}: {'; '.join(reasons)}" for name, reasons in offenders.items()),
        )


if __name__ == "__main__":
    unittest.main()
