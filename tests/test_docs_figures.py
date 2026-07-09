import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "docs" / "site" / "assets" / "generate_figures.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_figures", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDocsFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()

    def test_every_registered_figure_renders_a_png(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for name, fn in self.gen.FIGURES.items():
                path = fn(out)
                self.assertTrue(path.exists(), f"{name}: no file")
                self.assertGreater(path.stat().st_size, 2000, f"{name}: PNG too small")
                with path.open("rb") as fh:
                    self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n", f"{name}: not a PNG")


if __name__ == "__main__":
    unittest.main()
