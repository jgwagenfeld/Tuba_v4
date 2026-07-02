"""ASME B31J / B31.3-2020 compliance additions.

Covers the safe, source-verified subset:
- the pveng.com B31.3 sample-report elbow SIF/section values (solver-free);
- the B31J directional SIFSet structure;
- the edition-gated stress-range reduction factor f;
- the liberal displacement-stress-range allowable.
"""

import unittest

import numpy as np

import tuba
from tuba.compliance import (
    ASMEB313Evaluator,
    SIFSet,
    compute_sif_set,
    compute_sifs,
    stress_range_reduction_factor,
)
from tuba.solver.base import ElementResult, FEAResults

INCH = 0.0254


def _nps4_sch80_elbow_model() -> tuba.Model:
    m = tuba.Model("ref")
    m.add_material("DSS", E=195e9, nu=0.3)
    m.add_pipe_section("NPS4S80", OD=4.500 * INCH, WT=0.337 * INCH)  # NPS 4 SCH 80
    n0 = m.add_node([0.0, 0.0, 0.0])
    n1 = m.add_node([0.15, 0.0, 0.0])
    m.add_element(
        id="pipe_bend_0", type="pipe_bend", n1=n0, n2=n1,
        section="NPS4S80", material="DSS", bend_radius=6.000 * INCH,  # long-radius R = 1.5*NPS
    )
    return m


class TestPvengReferenceElbow(unittest.TestCase):
    """Solver-free regression vs the pveng.com ASME B31.3 sample report."""

    def test_elbow_sif_and_section_match_published_values(self):
        m = _nps4_sch80_elbow_model()
        elbow = m.elements[0]
        sif = compute_sif_set(elbow, m)

        self.assertAlmostEqual(sif.h, 0.46669, places=4)
        self.assertAlmostEqual(sif.i_i, 1.4959, places=3)
        self.assertAlmostEqual(sif.i_o, 1.2465, places=3)
        self.assertAlmostEqual(sif.k_i, 3.5355, places=3)
        # Section modulus (corroded=0): 4.2713 in^3 = 6.999e-5 m^3.
        self.assertAlmostEqual(m.sections["NPS4S80"].corroded_Z, 4.2713 * INCH ** 3, places=8)

        # Backward-compatible 4-tuple still returns the same numbers.
        i_i, i_o, k, h = compute_sifs(elbow, m)
        self.assertEqual((i_i, i_o, k, h), (sif.i_i, sif.i_o, sif.k_i, sif.h))


class TestSIFSetStructure(unittest.TestCase):
    def test_elbow_has_b31j_directional_indices(self):
        m = _nps4_sch80_elbow_model()
        sif = compute_sif_set(m.elements[0], m)
        self.assertIsInstance(sif, SIFSet)
        self.assertEqual(sif.basis, "b31j_elbow")
        self.assertEqual(sif.i_t, 1.0)      # torsional index (new vs Appendix D)
        self.assertEqual(sif.i_a, 1.0)      # axial index (new vs Appendix D)
        self.assertEqual(sif.k_i, sif.k_o)  # directional flexibility equal for elbows
        self.assertEqual(sif.k, sif.k_i)

    def test_straight_pipe_is_unity(self):
        m = tuba.Model("s")
        m.add_material("steel", E=210e9, nu=0.3)
        m.add_pipe_section("P", OD=0.1143, WT=0.006)
        n0 = m.add_node([0, 0, 0])
        n1 = m.add_node([1, 0, 0])
        m.add_element(id="pipe_str_0", type="pipe_straight", n1=n0, n2=n1, section="P", material="steel")
        sif = compute_sif_set(m.elements[0], m)
        self.assertEqual((sif.i_i, sif.i_o, sif.i_t, sif.i_a, sif.k_i, sif.k_o), (1.0,) * 6)
        self.assertEqual(sif.basis, "straight")


class TestStressRangeReductionFactor(unittest.TestCase):
    def test_edition_gated_values(self):
        # 2020 curve: f = 6 N^-0.2
        self.assertAlmostEqual(stress_range_reduction_factor(100_000, "2020"), 0.6000, places=3)
        # 2022 curve: f = 20 N^-(1/3) — steeper, so smaller f at high N.
        self.assertAlmostEqual(stress_range_reduction_factor(100_000, "2022"), 0.4309, places=3)
        self.assertLess(
            stress_range_reduction_factor(100_000, "2022"),
            stress_range_reduction_factor(100_000, "2020"),
        )

    def test_cap_and_floor(self):
        self.assertEqual(stress_range_reduction_factor(1_000, "2020"), 1.2)     # capped at 1.2
        self.assertEqual(stress_range_reduction_factor(1_000_000_000, "2020"), 0.15)  # floored at 0.15


class TestLiberalAllowable(unittest.TestCase):
    def _solved_model(self):
        m = tuba.Model("liberal")
        # Sc = Sh = 120 MPa (both temperatures) so hand math is simple.
        m.add_material("steel", E=210e9, nu=0.3, allowable_stress={20.0: 120e6, 200.0: 120e6})
        m.add_pipe_section("P", OD=0.1143, WT=0.00602)
        n0 = m.add_node([0, 0, 0])
        n1 = m.add_node([1, 0, 0])
        m.add_element(id="pipe_str_0", type="pipe_straight", n1=n0, n2=n1, section="P", material="steel")
        m.define_load_case("op", gravity=True, pressure=1.0e6, temperature=200.0, ref_temperature=20.0)

        results = FEAResults(solver_name="test", load_case="op")
        moment = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1000.0])  # modest bending -> modest SL
        results.element_results["pipe_str_0"] = ElementResult(
            element_id="pipe_str_0", forces_n1=moment, forces_n2=moment,
        )
        return m, results

    def test_liberal_allowable_exceeds_standard(self):
        m, results = self._solved_model()

        standard = ASMEB313Evaluator().evaluate(m, results).results[0]
        liberal = ASMEB313Evaluator(use_liberal_allowable=True).evaluate(m, results).results[0]

        SL = standard.sustained_stress
        self.assertGreater(SL, 0.0)
        self.assertLess(SL, 120e6)  # so the liberal credit is positive
        # Standard SA = 1.25 Sc + 0.25 Sh (f=1) = 180 MPa.
        self.assertAlmostEqual(standard.expansion_allowable, 1.25 * 120e6 + 0.25 * 120e6, delta=1.0)
        # Liberal SA = 1.25(Sc+Sh) - SL = 300 MPa - SL.
        self.assertAlmostEqual(liberal.expansion_allowable, 1.25 * (120e6 + 120e6) - SL, delta=1.0)
        self.assertGreater(liberal.expansion_allowable, standard.expansion_allowable)


if __name__ == "__main__":
    unittest.main()
