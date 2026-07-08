import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterTuyauSubpoints(unittest.TestCase):
    def test_parse_sieq_table_preserves_tuyau_subpoints(self):
        model = Model(project_name="TuyauSubpoints")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study_depl.csv").write_text(
                "\n".join(
                    [
                        "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                        "N0,0,0,0,0,0,0",
                        "N1,0.001,0,0,0,0,0",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "study_effo.csv").write_text(
                "\n".join(
                    [
                        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                        "pipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0",
                        "pipe_0,N1,100.0,0.0,0.0,0.0,0.0,0.0",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "study_sieq.csv").write_text(
                "\n".join(
                    [
                        "MAILLE,NOEUD,SOUS_POINT,COOR_X,COOR_Y,COOR_Z,VMIS",
                        "pipe_0,N0,1,0,0,0,10",
                        "pipe_0,N0,2,0,0,0,20",
                        "pipe_0,N1,1,1,0,0,30",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "study_manifest.json").write_text(
                json.dumps(
                    {
                        "analysis_mesh": {
                            "nodes": {"N0": [0.0, 0.0, 0.0], "N1": [1.0, 0.0, 0.0]},
                            "elements": {"pipe_0": ["N0", "N1"]},
                        }
                    }
                ),
                encoding="utf-8",
            )

            results = CodeAsterSolver().parse_result_artifacts(model, root, "Hot")

        self.assertEqual(len(results.tuyau_subpoints), 3)
        self.assertEqual(results.tuyau_subpoints[0]["subpoint_index"], 1)
        self.assertEqual(results.tuyau_subpoints[0]["centerline_position"], [0.0, 0.0, 0.0])
        self.assertEqual(results.tuyau_subpoints[0]["position_source"], "code_aster_tuyau_subpoint_formula")
        self.assertAlmostEqual(results.tuyau_subpoints[0]["display_position"][0], 0.0)
        self.assertAlmostEqual(results.tuyau_subpoints[0]["display_position"][1], 0.0)
        self.assertAlmostEqual(results.tuyau_subpoints[0]["display_position"][2], 0.04)
        self.assertEqual(results.tuyau_subpoints[1]["value"], 20.0)
        self.assertGreater(results.tuyau_subpoints[1]["display_position"][1], 0.0)
        self.assertGreater(results.tuyau_subpoints[1]["display_position"][2], 0.0)
        self.assertEqual(results.tuyau_subpoints[2]["node_id"], "N1")
        self.assertAlmostEqual(results.tuyau_subpoints[2]["display_position"][0], 1.0)
        self.assertAlmostEqual(results.tuyau_subpoints[2]["display_position"][2], 0.04)
        self.assertEqual(results.get_max_von_mises("pipe_0"), 30.0)


if __name__ == "__main__":
    unittest.main()
