import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from tuba import Model


@unittest.skipUnless(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1",
    "set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster smoke test",
)
class TestCodeAsterRealSmoke(unittest.TestCase):
    def test_minimal_pipe_model_solves_with_real_code_aster(self):
        model = Model(project_name="CodeAsterRealSmoke")
        model.add_material(
            "Steel",
            E=2.0e11,
            nu=0.3,
            rho=7850.0,
            alpha=1.2e-5,
            allowable_stress={20.0: 137e6},
        )
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(node=n0, type="anchor", id="support_anchor_0")
        model.define_load_case("Operating", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            results = model.solve("code_aster", load_case="Operating", work_dir=tmpdir)
            root = Path(tmpdir)

            self.assertTrue((root / "study.export").exists())
            self.assertTrue((root / "study_depl.csv").exists())
            self.assertTrue((root / "study_effo.csv").exists())
            self.assertTrue((root / "study_reac.csv").exists())
            self.assertTrue((root / "study_sieq.csv").exists())

        self.assertEqual(results.solver_name, "Code_Aster")
        self.assertEqual(results.load_case, "Operating")
        self.assertGreater(np.linalg.norm(results.node_results[n1].displacement[:3]), 0.0)
        self.assertIsNotNone(results.node_results[n0].reaction_force)
        self.assertGreater(np.linalg.norm(results.node_results[n0].reaction_force[:3]), 0.0)
        self.assertGreater(results.element_results["pipe_0"].max_von_mises, 0.0)


if __name__ == "__main__":
    unittest.main()
