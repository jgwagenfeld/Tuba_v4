import json
import re
import unittest
from pathlib import Path

from tuba.builder import PipingBuilder
from tuba.model import TubaModel


class TestCurrentApiDocs(unittest.TestCase):
    def test_current_docs_do_not_call_unshipped_future_dsl_methods(self):
        future_methods = {
            PipingBuilder: {
                "anchor",
                "guide",
                "block",
                "bend_to",
                "bend_by_orientation",
                "bend_in_plane",
            },
            TubaModel: {
                "operation",
                "define_operation",
            },
        }
        unshipped = {
            method
            for owner, methods in future_methods.items()
            for method in methods
            if not callable(getattr(owner, method, None))
        }
        patterns = {method: re.compile(rf"\.{re.escape(method)}\s*\(") for method in unshipped}
        offenders: list[str] = []

        for label, source in _current_user_facing_sources():
            matches = sorted(method for method, pattern in patterns.items() if pattern.search(source))
            if matches:
                offenders.append(f"{label}: {', '.join(matches)}")

        self.assertEqual([], offenders)


def _current_user_facing_sources():
    root = Path(__file__).resolve().parents[1]
    yield "README.md", (root / "README.md").read_text(encoding="utf-8")

    for path in sorted((root / "examples").glob("*.py")):
        yield f"examples/{path.name}", path.read_text(encoding="utf-8")

    for path in sorted((root / "notebooks").glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook.get("cells", [])):
            yield f"notebooks/{path.name}:cell {index}", "".join(cell.get("source", []))


if __name__ == "__main__":
    unittest.main()
