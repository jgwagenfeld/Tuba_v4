import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
            Path(tmpdir, "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            results = CodeAsterSolver()._parse_results(model, Path(tmpdir))

        self.assertTrue(np.allclose(results.get_displacement("N0")[:3], [0.001, 0.0, 0.0]))
        self.assertNotIn("pipe_bend_0_n1", results.node_results)
        self.assertIn("pipe_bend_0_n1", results.analysis_node_results)
        self.assertTrue(np.allclose(results.get_analysis_displacement("pipe_bend_0_n1")[:3], [0.010, 0.020, 0.030]))
        self.assertIn("non-native analysis node", " ".join(results.parser_diagnostics))


if __name__ == "__main__":
    unittest.main()
