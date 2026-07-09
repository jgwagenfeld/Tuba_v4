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

    def test_roadmap_architecture_docs_are_explicitly_labeled(self):
        offenders = [
            f"docs/architecture/{path.name}"
            for path in _roadmap_architecture_docs()
            if "roadmap" not in path.read_text(encoding="utf-8").lower()
        ]

        self.assertEqual([], offenders)

    def test_export_only_examples_warn_that_exports_are_not_completed_evaluations(self):
        offenders: list[str] = []

        for path in sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            exports = ".export_study(" in source or ".export_analysis_study(" in source
            imports_or_solves = (
                "solve_exported_study(" in source
                or "import_code_aster_artifacts(" in source
                or "load_or_run_code_aster_results(" in source
            )
            if exports and not imports_or_solves and "not a completed engineering evaluation" not in source.lower():
                offenders.append(f"examples/{path.name}")

        self.assertEqual([], offenders)

    def test_readme_does_not_promote_removed_roadmap_docs(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "README.md").read_text(encoding="utf-8")
        removed = [
            "docs/future_ready_architecture.md",
            "docs/visualization_engine_vision.md",
            ".agents/",
        ]

        self.assertEqual([], [item for item in removed if item in text])


def _current_user_facing_sources():
    root = Path(__file__).resolve().parents[1]
    yield "README.md", (root / "README.md").read_text(encoding="utf-8")
    yield "CONTRIBUTING.md", (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for path in _current_architecture_docs():
        yield f"docs/architecture/{path.name}", path.read_text(encoding="utf-8")

    for path in sorted((root / "examples").glob("*.py")):
        yield f"examples/{path.name}", path.read_text(encoding="utf-8")

    for path in sorted((root / "notebooks").glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook.get("cells", [])):
            yield f"notebooks/{path.name}:cell {index}", "".join(cell.get("source", []))


def _current_architecture_docs():
    architecture_dir = Path(__file__).resolve().parents[1] / "docs" / "architecture"
    roadmap_names = {path.name for path in _roadmap_architecture_docs()}
    return [
        path
        for path in sorted(architecture_dir.glob("*.md"))
        if path.name not in roadmap_names
    ]


def _roadmap_architecture_docs():
    root = Path(__file__).resolve().parents[1]
    return [
        root / "docs" / "architecture" / "user-facing-piping-dsl-and-agent-ops.md",
    ]


if __name__ == "__main__":
    unittest.main()
