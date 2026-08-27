import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from tuba import Model
from tuba.benchmarks import write_model_benchmark_summary


def test_benchmark_summary_defaults_to_build_root(tmp_path, monkeypatch):
    model = Model(project_name="DefaultBenchmarkRoot")
    model.add_node((0.0, 0.0, 0.0))
    monkeypatch.chdir(tmp_path)

    path = Path(write_model_benchmark_summary(model))

    assert path.parent == Path(".build/benchmarks")
    assert path.is_file()


class TestModelIndexes(unittest.TestCase):
    def test_find_node_by_point_reuses_existing_node(self):
        model = Model(project_name="Indexes")
        existing = model.add_node((1.0, 2.0, 3.0))

        found = model.find_node_by_point((1.0, 2.0, 3.0))

        self.assertEqual(found, existing)
        self.assertIn((1000000, 2000000, 3000000), model._node_point_index)

    def test_find_node_by_point_returns_none_for_missing_node(self):
        model = Model(project_name="Indexes")

        self.assertIsNone(model.find_node_by_point((1.0, 2.0, 3.0)))

    def test_indexes_rebuild_after_model_roundtrip(self):
        model = Model(project_name="RoundtripIndexes")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        model.add_element(id="pipe_str_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(loaded.find_node_by_point((1.0, 0.0, 0.0)), n1)
        self.assertEqual(loaded.next_element_id("pipe_str"), "pipe_str_1")
        self.assertIn("pipe_str_0", loaded._element_ids)
        self.assertEqual(loaded.get_element("pipe_str_0").id, "pipe_str_0")

    def test_benchmark_summary_is_written(self):
        model = Model(project_name="Benchmarks")
        model.add_node((0.0, 0.0, 0.0))

        with TemporaryDirectory() as tmpdir:
            path = write_model_benchmark_summary(model, directory=tmpdir)

            self.assertTrue(Path(path).exists())
            self.assertIn("model_benchmark", Path(path).name)
            self.assertIn('"nodes": 1', Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
