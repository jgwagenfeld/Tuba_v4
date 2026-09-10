import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "scripts" / "docs" / "generate_figures.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_figures", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDocsFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()

    def test_every_registered_figure_is_a_valid_committed_scene(self):
        # Photographing needs Node and a browser, so the suite checks what the
        # photograph is of: a valid, non-empty viewer scene, committed as a PNG
        # where the pages look for it.
        for name, build in self.gen.FIGURES.items():
            with self.subTest(figure=name):
                scene = build()
                scene.validate()
                self.assertTrue(scene.objects, f"{name}: the scene is empty")
                self.assertTrue((self.gen.FIG_DIR / f"{name}.png").is_file(), f"{name}: no committed figure")


if __name__ == "__main__":
    unittest.main()
