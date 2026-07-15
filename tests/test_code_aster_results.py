import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from tuba import Model
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterGeneratedMeshResults(unittest.TestCase):
    def test_depl_parser_preserves_generated_mesh_node_displacements(self):
        model = Model(project_name="GeneratedMeshResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_bend_0", type="pipe_bend", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "study_depl.csv").write_text(
                "\n".join(
                    [
                        "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                        "N0,0.001,0.0,0.0,0.0,0.0,0.0",
                        "pipe_bend_0_n1,0.010,0.020,0.030,0.001,0.002,0.003",
                    ]
                ),
                encoding="utf-8",
            )
            Path(tmpdir, "study_effo.csv").write_text(
                "\n".join(
                    [
                        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                        "pipe_bend_0,N0,100.0,0.0,0.0,0.0,0.0,0.0",
                        "pipe_bend_0,N1,100.0,0.0,0.0,0.0,0.0,0.0",
                    ]
                ),
                encoding="utf-8",
            )
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            Path(tmpdir, "study_manifest.json").write_text(
                json.dumps(
                    {
                        "analysis_mesh": {
                            "id": "analysis_mesh:Hot",
                            "nodes": {
                                "N0": [0.0, 0.0, 0.0],
                                "N1": [1.0, 0.0, 0.0],
                                "pipe_bend_0_n1": [0.5, 0.1, 0.0],
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            results = CodeAsterSolver()._parse_results(model, Path(tmpdir))

        self.assertTrue(np.allclose(results.get_displacement("N0")[:3], [0.001, 0.0, 0.0]))
        self.assertNotIn("pipe_bend_0_n1", results.node_results)
        self.assertIn("pipe_bend_0_n1", results.analysis_node_results)
        self.assertTrue(np.allclose(results.get_analysis_displacement("pipe_bend_0_n1")[:3], [0.010, 0.020, 0.030]))
        self.assertNotIn("non-native analysis node", " ".join(results.parser_diagnostics))

    def test_depl_parser_warns_for_generated_node_absent_from_manifest_mesh(self):
        model = Model(project_name="UnmappedGeneratedMeshResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_bend_0", type="pipe_bend", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.001,0.0,0.0,0.0,0.0,0.0\n"
                "unmapped_analysis_node,0.010,0.020,0.030,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_bend_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            root.joinpath("study_manifest.json").write_text(
                json.dumps({"analysis_mesh": {"id": "analysis_mesh:Hot", "nodes": {"N0": [0, 0, 0]}}}),
                encoding="utf-8",
            )

            results = CodeAsterSolver()._parse_results(model, root)

        self.assertIn("unmapped_analysis_node", results.analysis_node_results)
        self.assertIn("without mesh source mapping", " ".join(results.parser_diagnostics))

    def test_parse_raises_on_empty_displacement_results(self):
        """A run that emitted no displacement rows must fail loudly, not return zeros."""
        model = Model(project_name="EmptyResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            # Header-only tables: solver "ran" but produced no data rows.
            Path(tmpdir, "study_depl.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                CodeAsterSolver()._parse_results(model, Path(tmpdir))

    def test_parse_raises_on_empty_force_results(self):
        """Displacement present but no internal forces must fail loudly, not pass compliance on zeros."""
        model = Model(project_name="EmptyForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            # Displacement solved, but the force table came back empty (post-processing
            # failed or labels mismatched). Zero forces would silently pass compliance.
            Path(tmpdir, "study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\nN0,0.001,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            Path(tmpdir, "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                CodeAsterSolver()._parse_results(model, Path(tmpdir))

    def test_parse_result_tables_does_not_auto_open_rmed(self):
        model = Model(project_name="RmedBoundary")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        calls = []

        class FakeMeshio:
            @staticmethod
            def read(path, *, file_format=None):
                calls.append((Path(path).name, file_format))
                raise RuntimeError("RMED loading must be explicit")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\nN0,0.001,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            (root / "study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\npipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            (root / "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            (root / "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            (root / "study.rmed").write_bytes(b"fake-rmed")

            with patch.dict("sys.modules", {"meshio": FakeMeshio}):
                results = CodeAsterSolver()._parse_results(model, root)

            self.assertEqual(root / "study.rmed", results.result_file)
            self.assertIsNone(results.raw_mesh)

        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
