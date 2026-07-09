import re
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

    def test_every_page_uses_left_sidebar_navigation(self):
        pages = sorted(SITE.glob("*.html"))

        for path in pages:
            text = path.read_text(encoding="utf-8")
            self.assertIn('class="sidebar"', text, path.name)
            self.assertIn('class="side-nav"', text, path.name)
            self.assertIn('href="./tutorial.html"', text, path.name)
            self.assertIn('href="./modeling.html"', text, path.name)
            self.assertIn('href="./workflow.html"', text, path.name)
            self.assertIn('href="./autorouting.html"', text, path.name)
            self.assertIn('href="./commands.html"', text, path.name)
            self.assertNotIn('class="topbar"', text, path.name)

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
                "bend_chord_arc.png", "sections.png", "supports.png",
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
