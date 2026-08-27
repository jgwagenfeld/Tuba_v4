import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "docs" / "content"


class TestStaticSiteDocs(unittest.TestCase):
    def test_canonical_markdown_is_the_only_public_docs_authority(self):
        self.assertFalse((ROOT / "docs" / "site").exists())
        self.assertFalse((ROOT / "docs" / "tuba-workflow.md").exists())
        self.assertFalse((ROOT / "docs" / "code_aster_installation.md").exists())
        self.assertFalse(
            (CONTENT / "assets" / "figures" / ("viewer_frames" + "_poster.png")).exists()
        )

    def test_current_docs_sources_have_no_legacy_public_source_links(self):
        forbidden = (
            "docs" + "/site",
            "docs" + "/tuba-workflow",
            "docs" + "/code_aster_installation",
            "viewer_frames" + "_poster",
            "commands" + ".html",
            "workflow" + ".html",
        )
        offenders = {}
        for root in (CONTENT,):
            for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                matches = [token for token in forbidden if token in text]
                if matches:
                    offenders[str(path.relative_to(ROOT))] = matches

        for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
            notebook = json.loads(path.read_text(encoding="utf-8"))
            source = "".join(
                line
                for cell in notebook.get("cells", [])
                for line in cell.get("source", [])
            )
            matches = [token for token in forbidden if token in source]
            if matches:
                offenders[str(path.relative_to(ROOT))] = matches

        self.assertEqual({}, offenders)

    def test_reference_and_current_architecture_pages_are_canonical(self):
        required = {
            "reference/index.md": ["Generated public API", "`tuba.Model`", "`TubaModel`"],
            "architecture/index.md": [
                "Tuba model",
                "Code_Aster",
                "Artifact import",
                "PyVista quick-look",
                "Reviewable web scene",
            ],
            "architecture/visualization.md": [
                "exactly two visualization paths",
                "Review",
                "Model",
                "Results",
                "Issues",
                "Summary",
                "Diagnostics",
                "Compliance",
                "Reports",
                "physical deformation",
                "visual deformation",
                "true clipping",
            ],
        }

        for relative_path, phrases in required.items():
            text = (CONTENT / relative_path).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase.casefold(), text.casefold(), relative_path)

        design = (ROOT / "docs" / "architecture" / "visualization-layer-structure-design.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("**Status:** Implemented; retained as a design record", design)
        self.assertIn("../content/architecture/visualization.md", design)

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

    def test_setup_uses_the_tagged_github_checkout(self):
        text = (CONTENT / "setup.md").read_text(encoding="utf-8")

        self.assertIn(
            "git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git",
            text,
        )
        self.assertIn("python -m pip install .", text)
        self.assertIn("sudo apt-get install -y libglu1-mesa libxft2 libgomp1", text)
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

    def test_readme_and_home_lead_with_the_code_aster_review_hero(self):
        figure = CONTENT / "assets" / "figures" / "code_aster_review.png"
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        home = (CONTENT / "index.md").read_text(encoding="utf-8")

        self.assertTrue(figure.is_file())
        self.assertIn("docs/content/assets/figures/code_aster_review.png", readme)
        self.assertIn("assets/figures/code_aster_review.png", home)
        self.assertIn("viewer/?bundle=code-aster-review", readme)
        self.assertIn("viewer/?bundle=code-aster-review", home)

    def test_examples_page_lists_the_five_clickable_review_bundles(self):
        text = (CONTENT / "examples.md").read_text(encoding="utf-8")

        for bundle_id in (
            "autorouted-expansion-loop",
            "code-aster-review",
            "imported_component_mixed_demo",
            "pipe-tee-volume-review",
            "support-rack-review",
        ):
            self.assertIn(f"bundle={bundle_id}", text)

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
