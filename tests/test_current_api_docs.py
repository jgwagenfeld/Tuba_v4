import json
import re
import unittest
from html import unescape
from pathlib import Path

from tuba.builder import PipingBuilder
from tuba.model import TubaModel

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "docs" / "content"


class TestCurrentApiDocs(unittest.TestCase):
    def test_public_api_reference_uses_live_import_directives(self):
        text = (CONTENT / "reference" / "public-api.md").read_text(encoding="utf-8")

        self.assertIn("::: tuba.model.TubaModel", text)
        self.assertIn("::: tuba.analysis.code_aster_artifacts.import_code_aster_artifacts", text)
        self.assertIn("::: tuba.reporting.build_engineering_review", text)
        self.assertIn("::: tuba.visualization.build_visualization_scene", text)
        self.assertNotRegex(text, r"Model\.solve\(self,")

    def test_generated_public_api_renders_the_live_model_solve_signature(self):
        output = ROOT / ".build" / "zensical-site" / "reference" / "public-api.html"
        if not output.is_file():
            self.skipTest("run the strict Zensical build before checking generated HTML")
        rendered = output.read_text(encoding="utf-8")
        match = re.search(
            r'id="tuba\.model\.TubaModel\.solve"(?P<section>.*?)(?=id="tuba\.model\.TubaModel\.|</article>)',
            rendered,
            re.DOTALL,
        )

        self.assertIsNotNone(match, "generated API reference is missing TubaModel.solve")
        plain = " ".join(re.sub(r"<[^>]+>", " ", unescape(match.group("section"))).split())
        self.assertRegex(plain, r"solve\s*\(")
        self.assertIn("load_case", plain)
        self.assertIn("operation", plain)
        self.assertNotRegex(plain, r"\bsolver\s*=")

    def test_generated_public_api_renders_top_level_function_heading_and_signature(self):
        output = ROOT / ".build" / "zensical-site" / "reference" / "public-api.html"
        if not output.is_file():
            self.skipTest("run the strict Zensical build before checking generated HTML")
        rendered = output.read_text(encoding="utf-8")
        object_id = "tuba.analysis.code_aster_artifacts.import_code_aster_artifacts"
        match = re.search(
            rf'id="{re.escape(object_id)}"(?P<section>.*?)(?=id="tuba\.reporting\.build_engineering_review")',
            rendered,
            re.DOTALL,
        )

        self.assertIn(f'<h2 id="{object_id}" class="doc doc-heading">', rendered)
        self.assertIsNotNone(match)
        plain = " ".join(re.sub(r"<[^>]+>", " ", unescape(match.group("section"))).split())
        self.assertRegex(plain, r"import_code_aster_artifacts\s*\(")
        for parameter in ("model", "work_dir", "study"):
            self.assertIn(parameter, plain)

    def test_generated_public_api_renders_autorouting_dataclass_heading_and_fields(self):
        output = ROOT / ".build" / "zensical-site" / "reference" / "public-api.html"
        if not output.is_file():
            self.skipTest("run the strict Zensical build before checking generated HTML")
        rendered = output.read_text(encoding="utf-8")
        object_id = "tuba.routing.PipeRouteRequest"
        match = re.search(
            rf'id="{re.escape(object_id)}"(?P<section>.*?)(?=id="tuba\.routing\.PipeRouteResult")',
            rendered,
            re.DOTALL,
        )

        self.assertIn(f'<h2 id="{object_id}" class="doc doc-heading">', rendered)
        self.assertIsNotNone(match)
        plain = " ".join(re.sub(r"<[^>]+>", " ", unescape(match.group("section"))).split())
        self.assertRegex(plain, r"PipeRouteRequest\s*\(")
        for field in ("id", "start", "goal", "section", "material"):
            self.assertIn(field, plain)

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

    def test_artifact_import_examples_do_not_use_removed_load_case_argument(self):
        pattern = re.compile(r"import_code_aster_artifacts\s*\([^)]*\bload_case\s*=", re.DOTALL)
        offenders = [label for label, source in _current_user_facing_sources() if pattern.search(source)]

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
    root = ROOT
    yield "README.md", (root / "README.md").read_text(encoding="utf-8")
    yield "CONTRIBUTING.md", (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for path in sorted(CONTENT.rglob("*.md")):
        yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
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
