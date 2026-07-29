import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site"
CONTENT = ROOT / "docs" / "content"


class TestStaticSiteDocs(unittest.TestCase):
    def test_canonical_manual_pages_own_the_public_topics(self):
        required = {
            "setup.md": ["pip installs Tuba, not Code_Aster", "code_aster_doctor", "Run the real solver smoke test"],
            "tutorial.md": ["Build and solve a first pipe", "Expected files", "Done when"],
            "modeling.md": ["Cross-sections", "Local coordinate systems", "Schemas and serialized models", "How errors work"],
            "workflow.md": ["model.pipe", "export_analysis_study", "write_scene_bundle"],
            "autorouting.md": ["Route candidates, not magic signoff", "SolverAcceptanceCriteria", "Current limitations"],
            "examples.md": ["Local examples", "Code_Aster review scene", "Autorouting example outputs"],
            "developer.md": ["Module map", "Solver file map", "How to extend autorouting", "CONTRIBUTING.md"],
        }

        for name, phrases in required.items():
            text = (CONTENT / name).read_text(encoding="utf-8")
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
        text = (CONTENT / "setup.md").read_text(encoding="utf-8")

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
        tutorial = (CONTENT / "tutorial.md").read_text(encoding="utf-8")
        autorouting = (CONTENT / "autorouting.md").read_text(encoding="utf-8")

        self.assertIn("exported study files are a handoff", tutorial)
        self.assertIn("exported `.comm`, `.mail`, and `.export` files are handoff artifacts", autorouting)
        self.assertIn("Network routing is sequential with repair attempts, not global multi-line optimization", autorouting)
        self.assertIn("The current generator emits U-loop candidates only", autorouting)

    def test_pages_use_real_figures_not_sketches(self):
        # Each concept page must reference the real rendered figures (committed
        # under assets/figures/) and must not fall back to Mermaid or CSS sketches.
        required_figures = {
            "tutorial.md": ["tutorial_model.png", "pyvista_deformed_stress.png"],
            "modeling.md": [
                "element_triad.png", "placement_frame.png", "builder_route.png",
                "bend_chord_arc.png", "sections.svg", "bend_detail.svg", "supports.png",
            ],
            "workflow.md": ["tutorial_model.png", "pyvista_deformed_stress.png"],
            "autorouting.md": ["route_preroute.png", "route_candidates.png"],
        }
        forbidden = [
            'class="mermaid"', "diagrams.js", "axis-sketch", "section-gallery",
            "routing-sketch", "artifact-lifecycle", "module-map", "process-map",
        ]
        figures_dir = CONTENT / "assets" / "figures"
        for page, figs in required_figures.items():
            text = (CONTENT / page).read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{page} still contains {token!r}")
            for fig in figs:
                self.assertIn(f"figures/{fig}", text, f"{page} missing {fig}")
                self.assertTrue((figures_dir / fig).exists(), f"missing figure file {fig}")

        # the stylized 3D sections render is retired in favour of the drawing
        self.assertFalse((figures_dir / "sections.png").exists(),
                         "sections.png should be replaced by sections.svg")
        self.assertNotIn("sections.png", (CONTENT / "modeling.md").read_text(encoding="utf-8"))

    def test_no_page_uses_mermaid_or_the_diagram_loader(self):
        for path in sorted(SITE.glob("*.html")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('class="mermaid"', text, path.name)
            self.assertNotIn("diagrams.js", text, path.name)

    def test_frame_and_result_pages_embed_the_viewer(self):
        embeds = {
            "modeling.md": "imported_component_mixed_demo",
            "tutorial.md": "code-aster-review",
            "examples.md": "code-aster-review",
        }
        for page, bundle in embeds.items():
            text = (CONTENT / page).read_text(encoding="utf-8")
            self.assertIn(f"bundle={bundle}", text, f"{page} missing viewer embed")

    def test_modeling_docs_explain_core_beginner_concepts(self):
        text = (CONTENT / "modeling.md").read_text(encoding="utf-8")

        required_phrases = [
            "`OD` is outside diameter",
            "`WT` is wall thickness",
            "`axis` is local Z",
            "`ref_direction` is projected to local X",
            "MODEL_SCHEMA_V4",
            "SchemaValidationError",
            "ModelValidationError",
            "Pipe section ... WT is too large for OD",
            "Code_Aster study",
            "Import the result artifacts before plotting",
        ]

        for phrase in required_phrases:
            self.assertIn(phrase, text)

    def test_modeling_serialization_sample_matches_the_live_schema(self):
        from tuba.schema import validate_model_dict

        text = (CONTENT / "modeling.md").read_text(encoding="utf-8")
        sample = re.search(r"## Schemas and serialized models.*?```json\n(.*?)\n```", text, re.S)
        self.assertIsNotNone(sample)
        validate_model_dict(json.loads(sample.group(1)))


if __name__ == "__main__":
    unittest.main()
