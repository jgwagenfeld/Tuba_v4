# tests/test_tee_sif.py
import unittest
import numpy as np

from tuba import Model
from tuba.compliance.sif import compute_sif_set, compute_sifs


class TestTeeSif(unittest.TestCase):
    def setUp(self):
        self.model = Model(project_name="TestTee", standard="ASME_B31.3")
        self.model.add_material("St37", E=2.1e11, nu=0.3, allowable_stress={20: 120e6})
        self.model.add_pipe_section("3inch", OD=0.0889, WT=0.00549)

    def test_tee_junction_detection_and_sifs(self):
        # Build a 3-way Tee junction at node N1
        # N0 (0,0,0) -> N1 (2,0,0) -> N2 (4,0,0) (Header run)
        # N1 (2,0,0) -> N3 (2,2,0) (Branch run)
        with self.model.pipe(section="3inch", material="St37") as b:
            # Main Run 1
            b.start([0, 0, 0]).run(2.0) # Ends at N1
            # Main Run 2
            b.run(2.0) # Ends at N2
            
        with self.model.pipe(section="3inch", material="St37") as b:
            # Branch Run (starts from N1)
            b.start([2, 0, 0]).set_direction([0, 1, 0]).run(2.0) # Starts at N1, ends at N3

        # We verify that node N1 connects exactly 3 elements
        connecting = [e for e in self.model.elements if e.n1 == "N1" or e.n2 == "N1"]
        self.assertEqual(len(connecting), 3)

        with self.assertRaisesRegex(ValueError, "requires B31J Table 1-1"):
            compute_sif_set(self.model.elements[0], self.model, node_id="N1")

        # Explicit legacy opt-in: N1 acts as an unreinforced tee using Appendix-D equations.
        i_i, i_o, k, h = compute_sifs(
            self.model.elements[0],
            self.model,
            node_id="N1",
            allow_appendix_d_tee=True,
        )
        
        # For unreinforced fabricated tee: h = t_h / r_mh
        t_h = 0.00549
        r_mh = (0.0889 - 0.00549) / 2.0
        expected_h = t_h / r_mh
        expected_sif = max(0.9 / (expected_h ** (2.0 / 3.0)), 1.0)
        
        self.assertAlmostEqual(h, expected_h)
        self.assertAlmostEqual(i_i, expected_sif)
        self.assertAlmostEqual(i_o, expected_sif)
        self.assertEqual(k, 1.0) # Rigid

        # Let's test explicit Welding Tee definition
        self.model.define_tee("N1", type="welding_tee")
        i_i, i_o, k, h = compute_sifs(
            self.model.elements[0],
            self.model,
            node_id="N1",
            allow_appendix_d_tee=True,
        )
        
        # For welding tee: h = 4.4 * t_h / r_mh
        expected_h_w = 4.4 * t_h / r_mh
        expected_sif_w = max(0.9 / (expected_h_w ** (2.0 / 3.0)), 1.0)
        self.assertAlmostEqual(h, expected_h_w)
        self.assertAlmostEqual(i_i, expected_sif_w)

        # Let's test explicit Reinforced Tee definition
        self.model.define_tee("N1", type="reinforced_tee", pad_thickness=0.006)
        i_i, i_o, k, h = compute_sifs(
            self.model.elements[0],
            self.model,
            node_id="N1",
            allow_appendix_d_tee=True,
        )
        
        # For reinforced tee: h = (t_h + 0.5 * t_r)^2.5 / (t_h^1.5 * r_mh)
        t_r = 0.006
        expected_h_r = ((t_h + 0.5 * t_r) ** 2.5) / (t_h ** 1.5 * r_mh)
        expected_sif_r = max(0.9 / (expected_h_r ** (2.0 / 3.0)), 1.0)
        self.assertAlmostEqual(h, expected_h_r)
        self.assertAlmostEqual(i_i, expected_sif_r)

        # Check that the other end of element 0 (Node N0) which is not a Tee
        # resolves to a standard straight SIF of 1.0
        i_i_n0, i_o_n0, k_n0, h_n0 = compute_sifs(self.model.elements[0], self.model, node_id="N0")
        self.assertEqual(i_i_n0, 1.0)
        self.assertEqual(i_o_n0, 1.0)
        self.assertEqual(k_n0, 1.0)
        self.assertEqual(h_n0, 0.0)


if __name__ == "__main__":
    unittest.main()
