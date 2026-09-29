"""The native section properties, checked against the Autochar (Sillage) table.

``tuba/sections/data/IBeam.output`` is a Sillage section-characteristics table,
generated offline and committed: 47 columns of area, centroid, second moments,
radii and elastic/plastic moduli for 174 rolled profiles. It is the only source
of ``SECTION='GENERALE'`` numbers ``tuba/solver/aster_comm.py`` can write for a
rolled section, because an I-profile has no Code_Aster primitive.

These tests pin the native kernel in ``tuba.sections.properties`` to that table
for the whole catalog, so the two cannot drift. The bounds below are measured,
not chosen: the residual is the difference between Sillage's real rolled
geometry - tapered flanges, true root radii - and the nominal-plate idealisation
this module integrates. Reporting a tighter bound than the data supports would
be the real failure here.
"""

import math
import unittest

from tuba import Model
from tuba.sections import SectionCatalog, properties_for_section


#: Catalog area, and the two second moments, agree to this relative bound over
#: every profile in the table. The worst case is 0.040% (HE100M area).
GEOMETRY_TOLERANCE = 5e-4

#: The torsion constant does not, and is not expected to. An open section's
#: Saint-Venant constant is 1/3 * sum(b t**3) over the wall mid-lines, and the
#: four root radii are not separate walls in that sum: Sillage integrates the
#: thickening they create, the strip sum cannot. The worst case is 39.7%
#: (HE100AA, where the fillets are a large share of a very light section).
#: Nothing in the solve path uses this number - ``aster_comm.py`` reads the
#: catalog's JX - so the estimate is bounded rather than tight on purpose.
TORSION_TOLERANCE = 0.45


def _catalog_sections() -> dict[str, object]:
    """Every catalog I-beam as a Tuba section, built once for the sweep."""
    model = Model("catalog")
    for name in SectionCatalog.default()._load_ibeam_profiles():
        model.add_ibeam_section(name, name)
    return dict(model.sections)


class TestSectionPropertiesAgainstSillage(unittest.TestCase):
    """The native kernel against the committed Autochar table, catalog wide."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = SectionCatalog.default()
        cls.sections = _catalog_sections()

    def test_the_catalog_is_swept_not_sampled(self):
        # A spot check passes on a formula that is wrong for wide sections. The
        # catalog holds light IPEs and heavy HEs, and they break differently.
        self.assertGreater(len(self.sections), 150)

    def test_area_and_second_moments_match_sillage_for_every_profile(self):
        for name, section in self.sections.items():
            with self.subTest(profile=name):
                properties = properties_for_section(section)
                published = self.catalog.get_ibeam_profile(name).properties
                for label, mine, theirs in (
                    ("A", properties.area_m2, published["A"]),
                    ("IY", properties.iy_m4, published["IY"]),
                    ("IZ", properties.iz_m4, published["IZ"]),
                ):
                    self.assertLess(
                        abs(mine - theirs) / abs(theirs),
                        GEOMETRY_TOLERANCE,
                        f"{name} {label}: native {mine:.6e} vs Sillage {theirs:.6e}",
                    )

    def test_the_torsion_estimate_stays_inside_its_documented_bound(self):
        for name, section in self.sections.items():
            with self.subTest(profile=name):
                properties = properties_for_section(section)
                published = self.catalog.get_ibeam_profile(name).properties["JX"]
                self.assertLess(abs(properties.j_m4 - published) / published, TORSION_TOLERANCE)

    def test_an_ibeam_torsion_estimate_is_declared_inexact(self):
        properties = properties_for_section(self.sections["IPE200"])
        self.assertFalse(properties.j_is_exact)


class TestSectionPropertiesAxisConvention(unittest.TestCase):
    """``IY`` and ``IZ`` mean what the catalog and ``AFF_CHAR_MECA`` mean.

    A swapped pair would still sum to the right polar moment and would pass any
    test that only checks a total, so the order is pinned directly.
    """

    def test_iz_is_the_strong_axis_of_an_upright_ibeam(self):
        model = Model("axes")
        model.add_ibeam_section("IPE200", "IPE200")
        properties = properties_for_section(model.sections["IPE200"])
        # IPE200: 1943 cm4 strong, 142 cm4 weak, a factor of 13.7 apart.
        self.assertAlmostEqual(properties.iz_m4 / properties.iy_m4, 13.65, delta=0.1)

    def test_a_circular_section_is_identically_biaxial(self):
        model = Model("round")
        model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
        properties = properties_for_section(model.sections["DN100"])
        self.assertAlmostEqual(properties.iy_m4, properties.iz_m4, places=18)
        self.assertTrue(properties.j_is_exact)
        self.assertAlmostEqual(properties.j_m4, 2.0 * properties.iy_m4, places=18)


class TestSectionPropertiesClosedForms(unittest.TestCase):
    """The kinds that have an exact answer are checked against the formula."""

    def test_pipe_area_and_inertia_are_the_annulus_closed_forms(self):
        model = Model("pipe")
        model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
        outer, wall = 0.1143, 0.00602
        bore = outer - 2.0 * wall
        properties = properties_for_section(model.sections["DN100"])
        self.assertAlmostEqual(properties.area_m2, math.pi / 4.0 * (outer**2 - bore**2), places=12)
        # Second moment about a diameter is pi (ro**4 - ri**4) / 4 on radii, which
        # is pi (OD**4 - ID**4) / 64 on diameters. The two are the same number and
        # differ by the factor of sixteen the fourth power of two costs.
        self.assertAlmostEqual(
            properties.iy_m4, math.pi / 64.0 * (outer**4 - bore**4), places=18
        )

    def test_a_solid_bar_is_a_solid_circle(self):
        model = Model("bar")
        model.add_bar_section("Round", OD=0.18, WT=0.0)
        properties = properties_for_section(model.sections["Round"])
        self.assertAlmostEqual(properties.area_m2, math.pi * 0.09**2, places=12)
        self.assertAlmostEqual(properties.j_m4, math.pi * 0.09**4 / 2.0, places=18)

    def test_a_closed_box_torsion_is_bredt_exact(self):
        model = Model("box")
        model.add_rectangular_section(
            "RHS", height_y=0.2, height_z=0.1, thickness_y=0.01, thickness_z=0.01
        )
        properties = properties_for_section(model.sections["RHS"])
        self.assertTrue(properties.j_is_exact)
        # Uniform wall: J = 4 A_m**2 t / p_m, over the full median perimeter.
        median_y, median_z, wall = 0.095, 0.045, 0.01
        enclosed = 4.0 * median_y * median_z
        perimeter = 4.0 * (median_y + median_z)
        self.assertAlmostEqual(properties.j_m4, enclosed**2 * wall / perimeter, places=15)

    def test_a_box_void_is_subtracted_not_added(self):
        model = Model("void")
        model.add_rectangular_section(
            "RHS", height_y=0.2, height_z=0.1, thickness_y=0.01, thickness_z=0.01
        )
        section = model.sections["RHS"]
        properties = properties_for_section(section)
        self.assertAlmostEqual(
            properties.area_m2, 0.2 * 0.1 - 0.18 * 0.08, places=12
        )
        self.assertAlmostEqual(properties.iy_m4, (0.2 * 0.1**3 - 0.18 * 0.08**3) / 12.0, places=15)

    def test_a_solid_rectangle_declares_an_inexact_torsion(self):
        model = Model("plate")
        model.add_rectangular_section(
            "Plate", height_y=0.2, height_z=0.01, thickness_y=0.0, thickness_z=0.0
        )
        self.assertFalse(properties_for_section(model.sections["Plate"]).j_is_exact)


class TestSectionPropertiesRefusals(unittest.TestCase):
    """Dimensions that do not describe a solid are refused, with the reason."""

    def test_a_bore_wider_than_the_pipe_is_refused(self):
        model = Model("bad-pipe")
        with self.assertRaises(ValueError) as ctx:
            model.add_pipe_section("Impossible", OD=0.1, WT=0.06)
            properties_for_section(model.sections["Impossible"])
        self.assertIn("bore", str(ctx.exception))

    def test_a_box_hollow_on_one_axis_only_is_refused(self):
        model = Model("half-box")
        model.add_rectangular_section(
            "Slit", height_y=0.2, height_z=0.1, thickness_y=0.01, thickness_z=0.0
        )
        with self.assertRaises(ValueError) as ctx:
            properties_for_section(model.sections["Slit"])
        self.assertIn("single wall thickness", str(ctx.exception))

    def test_root_radii_that_swallow_the_web_are_refused(self):
        model = Model("fat-roots")
        with self.assertRaises(ValueError):
            model.add_ibeam_section("Fat", "IPE200")
            section = model.sections["Fat"]
            # A root radius wider than half the web cannot exist on this profile.
            section.properties["R"] = 0.05
            properties_for_section(section)

    def test_a_negative_root_radius_is_refused(self):
        model = Model("negative-root")
        model.add_ibeam_section("Bad", "IPE200")
        section = model.sections["Bad"]
        section.properties["R"] = -0.001
        with self.assertRaises(ValueError) as ctx:
            properties_for_section(section)
        self.assertIn("cannot be negative", str(ctx.exception))


class TestSectionPropertiesSerialization(unittest.TestCase):
    """What a surface publishes, so a report or the viewer can read it."""

    def test_as_dict_reports_every_derived_quantity_in_si_units(self):
        model = Model("dict")
        model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
        published = properties_for_section(model.sections["DN100"]).as_dict()
        self.assertEqual(
            set(published),
            {
                "kind",
                "area_m2",
                "centroid",
                "iy_m4",
                "iz_m4",
                "iyz_m4",
                "j_m4",
                "j_is_exact",
                "gyration_y_m",
                "gyration_z_m",
                "polar_moment_m4",
            },
        )
        self.assertEqual(published["kind"], "pipe")
        self.assertAlmostEqual(published["polar_moment_m4"], published["iy_m4"] + published["iz_m4"], places=18)

    def test_the_code_aster_names_are_the_ones_the_comm_writer_emits(self):
        model = Model("names")
        model.add_ibeam_section("IPE200", "IPE200")
        properties = properties_for_section(model.sections["IPE200"])
        self.assertEqual(set(properties.code_aster), {"A", "IY", "IZ", "JX"})


if __name__ == "__main__":
    unittest.main()
