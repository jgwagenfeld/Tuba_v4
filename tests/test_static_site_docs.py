import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site"


class TestStaticSiteDocs(unittest.TestCase):
    def test_site_contains_current_workflow_and_reference_pages(self):
        required = {
            "index.html": ["Define the piping model", "Code_Aster solve"],
            "overview.html": ["Current product contract", "From TUBA v2 to v4"],
            "workflow.html": ["model.pipe", "export_analysis_study", "write_scene_bundle"],
            "commands.html": ["Current v4 API surface", "Pipe builder commands", "Solver and artifact commands"],
            "examples.html": ["Local examples", "Preserved Code_Aster review scene"],
            "setup.html": ["code_aster_doctor", "Run the real solver smoke test"],
            "developer.html": ["Module map", "Solver file map", "Contribution rules"],
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


if __name__ == "__main__":
    unittest.main()
