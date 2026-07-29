import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site"


class TestStaticSiteDocs(unittest.TestCase):
    def test_site_contains_current_workflow_and_reference_pages(self):
        required = {
            "index.html": ["Define the piping model", "Code_Aster solve"],
            "tutorial.html": ["Build and solve a first pipe", "What each part does", "Expected files", "Done when"],
            "modeling.html": [
                "How a Tuba model is put together",
                "Cross-sections",
                "Local coordinate systems",
                "Schemas and serialized models",
                "How errors work",
            ],
            "overview.html": ["Current product contract", "From TUBA v2 to v4"],
            "workflow.html": ["model.pipe", "export_analysis_study", "write_scene_bundle"],
            "autorouting.html": [
                "Route candidates, not magic signoff",
                "Implementation map",
                "SolverAcceptanceCriteria",
                "Current limitations",
            ],
            "commands.html": [
                "Current v4 API surface",
                "Pipe builder commands",
                "Autorouting commands",
                "Solver and artifact commands",
            ],
            "examples.html": ["Local examples", "Preserved Code_Aster review scene", "Autorouting example outputs"],
            "setup.html": ["code_aster_doctor", "Run the real solver smoke test"],
            "developer.html": ["Module map", "Solver file map", "How to extend autorouting", "How to contribute", "CONTRIBUTING.md"],
        }

        for name, phrases in required.items():
            text = (SITE / name).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text, name)

    def test_site_html_has_no_markdown_backticks(self):
        offenders = []
        for path in sorted(SITE.glob("*.html")):
            text = re.sub(r"<pre><code>.*?</code></pre>", "", path.read_text(encoding="utf-8"), flags=re.S)
            if "`" in text:
                offenders.append(path.name)

        self.assertEqual([], offenders)

    def test_setup_uses_the_tagged_github_checkout(self):
        text = (SITE / "setup.html").read_text(encoding="utf-8")

        self.assertIn(
            "git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git",
            text,
        )
        self.assertIn("python -m pip install .", text)
        self.assertIn("sudo apt-get install -y libglu1-mesa", text)
        self.assertIn(".\\.venv\\Scripts\\jupyter.exe lab", text)
        self.assertNotIn("your-tuba-v4-repo-url", text)
        self.assertNotIn("pip install -e", text)

    def test_zensical_build_uses_canonical_markdown_and_docs_only_dependencies(self):
        config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
        project = config["project"]
        self.assertEqual("docs/content", project["docs_dir"])
        self.assertEqual(".build/zensical-site", project["site_dir"])
        self.assertFalse(project["use_directory_urls"])
        self.assertTrue(project["validation"]["invalid_links"])
        self.assertTrue(project["validation"]["invalid_link_anchors"])

        package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        docs_dependencies = package["dependency-groups"]["docs"]
        self.assertIn("zensical==0.0.51", docs_dependencies)
        self.assertIn("mkdocstrings[python]>=1.0", docs_dependencies)

        runtime_dependencies = package["project"]["dependencies"]
        optional_dependencies = [
            dependency
            for dependencies in package["project"]["optional-dependencies"].values()
            for dependency in dependencies
        ]
        for dependency in runtime_dependencies + optional_dependencies:
            self.assertNotIn("zensical", dependency.lower())
            self.assertNotIn("mkdocstrings", dependency.lower())

        self.assertTrue((ROOT / "docs" / "content" / "index.md").is_file())

    def test_docs_do_not_overclaim_autorouting_or_export_only_files(self):
        tutorial = (SITE / "tutorial.html").read_text(encoding="utf-8")
        autorouting = (SITE / "autorouting.html").read_text(encoding="utf-8")

        self.assertIn("exported study files are a handoff", tutorial)
        self.assertIn("exported <code>.comm</code>, <code>.mail</code>, and <code>.export</code> files are handoff artifacts", autorouting)
        self.assertIn("Network routing is sequential with repair attempts, not global multi-line optimization", autorouting)
        self.assertIn("The current generator emits U-loop candidates only", autorouting)

    def test_pages_use_real_figures_not_sketches(self):
        # Each concept page must reference the real rendered figures (committed
        # under assets/figures/) and must not fall back to Mermaid or CSS sketches.
        required_figures = {
            "index.html": ["money_shot.png"],
            "tutorial.html": ["tutorial_model.png", "money_shot.png"],
            "modeling.html": [
                "element_triad.png", "placement_frame.png", "builder_route.png",
                "bend_chord_arc.png", "sections.svg", "bend_detail.svg", "supports.png",
            ],
            "overview.html": ["money_shot.png"],
            "workflow.html": ["tutorial_model.png", "money_shot.png"],
            "autorouting.html": ["route_preroute.png", "route_candidates.png"],
        }
        forbidden = [
            'class="mermaid"', "diagrams.js", "axis-sketch", "section-gallery",
            "routing-sketch", "artifact-lifecycle", "module-map", "process-map",
        ]
        figures_dir = SITE / "assets" / "figures"
        for page, figs in required_figures.items():
            text = (SITE / page).read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{page} still contains {token!r}")
            for fig in figs:
                self.assertIn(f"figures/{fig}", text, f"{page} missing {fig}")
                self.assertTrue((figures_dir / fig).exists(), f"missing figure file {fig}")

        # the stylized 3D sections render is retired in favour of the drawing
        self.assertFalse((figures_dir / "sections.png").exists(),
                         "sections.png should be replaced by sections.svg")
        self.assertNotIn("sections.png", (SITE / "modeling.html").read_text(encoding="utf-8"))

    def test_no_page_uses_mermaid_or_the_diagram_loader(self):
        for path in sorted(SITE.glob("*.html")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('class="mermaid"', text, path.name)
            self.assertNotIn("diagrams.js", text, path.name)

    def test_frame_and_result_pages_embed_the_viewer(self):
        embeds = {
            "modeling.html": "imported_component_mixed_demo",
            "tutorial.html": "code-aster-review",
            "examples.html": "code-aster-review",
        }
        for page, bundle in embeds.items():
            text = (SITE / page).read_text(encoding="utf-8")
            self.assertIn(f"bundle={bundle}", text, f"{page} missing viewer embed")

    def test_modeling_docs_explain_core_beginner_concepts(self):
        text = (SITE / "modeling.html").read_text(encoding="utf-8")

        required_phrases = [
            "OD</code> is outside diameter",
            "WT</code> is wall thickness",
            "axis</code> is local Z",
            "ref_direction</code> is projected to local X",
            "MODEL_SCHEMA_V4",
            "SchemaValidationError",
            "ModelValidationError",
            "Pipe section ... WT is too large for OD",
            "Code_Aster study",
            "Import the result artifacts before plotting",
        ]

        for phrase in required_phrases:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
