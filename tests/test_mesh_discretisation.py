"""Bend-chord discretisation and the TUYAU sub-point indexing convention."""

import math
import unittest

from tuba.analysis import AnalysisMesh, MeshElementSource
from tuba.analysis.mesh_quality import (
    DEFAULT_CHORD_TOLERANCE_RATIO,
    bend_discretisation,
    chord_deviation,
    discretisation_summary,
)
from tuba.analysis.tuyau import (
    CODE_ASTER_TUYAU_NCOU,
    CODE_ASTER_TUYAU_NSEC,
    layers_through_wall,
    section_profile,
    sectors_per_layer,
    subpoint_station,
)
from tuba.refs import EntityRef
from tuba.visualization.builders._layers import mesh_identity


def _bend_mesh(*, segments: int, radius: float, angle: float) -> AnalysisMesh:
    """A mesh whose only content is one bend cut into ``segments`` spans."""
    nodes = {f"N{index}": (float(index), 0.0, 0.0) for index in range(segments + 1)}
    elements = {f"B_s{index}": (f"N{index}", f"N{index + 1}") for index in range(segments)}
    geometry = {
        "center": [0.0, radius, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "radius": radius,
        "angle": angle,
        "start_tangent": [1.0, 0.0, 0.0],
        "end_tangent": [0.0, 1.0, 0.0],
        "generation_mode": "bend",
    }
    element_sources = {
        element_id: MeshElementSource(
            element_id=element_id,
            source_ref=EntityRef("element", "B"),
            role="bend_segment",
            segment_index=index,
            metadata={"bend_geometry": geometry},
        )
        for index, element_id in enumerate(elements)
    }
    return AnalysisMesh(
        id="m",
        model_revision=1,
        solver_name="Code_Aster",
        nodes=nodes,
        elements=elements,
        groups={"AllPipes": tuple(elements)},
        node_sources={},
        element_sources=element_sources,
        modelisations={"AllPipes": "TUYAU_3M"},
    )


def _straight_mesh(node_count: int = 2) -> AnalysisMesh:
    nodes = {f"N{index}": (float(index), 0.0, 0.0) for index in range(node_count)}
    return AnalysisMesh(
        id="m",
        model_revision=1,
        solver_name="Code_Aster",
        nodes=nodes,
        elements={"E1": tuple(nodes)},
        groups={"AllPipes": ("E1",)},
        node_sources={},
        element_sources={
            "E1": MeshElementSource(
                element_id="E1",
                source_ref=EntityRef("element", "E1"),
                role="native_element",
            )
        },
        modelisations={"AllPipes": "TUYAU_3M"},
    )


class TestChordDeviation(unittest.TestCase):
    def test_sagitta_matches_the_closed_form(self):
        # A 90 deg arc of R=1 in two spans: each span subtends 45 deg, so the
        # deepest excursion of one chord is R(1 - cos(22.5 deg)).
        self.assertAlmostEqual(chord_deviation(1.0, 90.0, 2), 1.0 - math.cos(math.radians(22.5)))

    def test_refining_the_mesh_shrinks_the_deviation(self):
        coarse = chord_deviation(0.3429, 90.0, 2)
        fine = chord_deviation(0.3429, 90.0, 8)
        self.assertGreater(coarse, fine)
        self.assertGreater(fine, 0.0)

    def test_deviation_scales_with_radius(self):
        self.assertAlmostEqual(chord_deviation(2.0, 90.0, 3), 2.0 * chord_deviation(1.0, 90.0, 3))

    def test_degenerate_input_reports_zero_rather_than_raising(self):
        self.assertEqual(chord_deviation(0.0, 90.0, 4), 0.0)
        self.assertEqual(chord_deviation(1.0, 90.0, 0), 0.0)
        self.assertEqual(chord_deviation(float("nan"), 90.0, 4), 0.0)


class TestBendDiscretisation(unittest.TestCase):
    def test_segments_are_grouped_back_onto_their_source_bend(self):
        records = bend_discretisation(_bend_mesh(segments=4, radius=0.3429, angle=90.0))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_element_id, "B")
        self.assertEqual(records[0].element_count, 4)
        self.assertAlmostEqual(records[0].chord_deviation, chord_deviation(0.3429, 90.0, 4))

    def test_a_coarse_bend_falls_outside_the_declared_tolerance(self):
        coarse = bend_discretisation(_bend_mesh(segments=1, radius=0.3429, angle=90.0))[0]
        fine = bend_discretisation(_bend_mesh(segments=16, radius=0.3429, angle=90.0))[0]
        self.assertFalse(coarse.within_tolerance)
        self.assertTrue(fine.within_tolerance)
        self.assertEqual(coarse.tolerance_ratio, DEFAULT_CHORD_TOLERANCE_RATIO)
        self.assertAlmostEqual(coarse.tolerance, 0.3429 * DEFAULT_CHORD_TOLERANCE_RATIO)

    def test_the_caller_can_supply_its_own_tolerance(self):
        loose = bend_discretisation(_bend_mesh(segments=1, radius=1.0, angle=90.0), tolerance_ratio=0.5)[0]
        self.assertTrue(loose.within_tolerance)

    def test_a_mesh_without_bends_has_nothing_to_report(self):
        straight = _straight_mesh()
        self.assertEqual(bend_discretisation(straight), [])
        # None, not an empty shell: a straight run must omit the panel rather
        # than show a check that passed vacuously.
        self.assertIsNone(discretisation_summary(straight))


class TestDiscretisationSummary(unittest.TestCase):
    def test_summary_leads_with_the_worst_bend(self):
        summary = discretisation_summary(_bend_mesh(segments=2, radius=0.3429, angle=90.0))
        self.assertEqual(summary["check"], "bend_chord_deviation")
        self.assertEqual(summary["unit"], "m")
        self.assertEqual(summary["bend_count"], 1)
        self.assertEqual(summary["min_elements_per_bend"], 2)
        self.assertAlmostEqual(summary["max_chord_deviation"], chord_deviation(0.3429, 90.0, 2))
        self.assertEqual(summary["worst_bend"]["source_element_id"], "B")

    def test_summary_carries_the_criterion_not_just_a_verdict(self):
        summary = discretisation_summary(_bend_mesh(segments=1, radius=1.0, angle=90.0))
        self.assertIn("tolerance_ratio", summary)
        self.assertFalse(summary["within_tolerance"])


class TestMeshIdentityCarriesTheCheck(unittest.TestCase):
    def test_identity_names_quadratic_hexahedral_volume_cells(self):
        nodes = {f"N{index}": (float(index), 0.0, 0.0) for index in range(20)}
        mesh = AnalysisMesh(
            id="solid",
            model_revision=0,
            solver_name="Code_Aster",
            nodes=nodes,
            elements={"H0": tuple(nodes)},
            groups={"G_SOLID": ("H0",)},
            node_sources={},
            element_sources={},
            modelisations={"G_SOLID": "3D"},
        )

        self.assertEqual(mesh_identity(mesh)["element_families"], [{"family": "HEXA20", "element_count": 1}])

    def test_identity_reports_element_family_and_discretisation(self):
        identity = mesh_identity(_bend_mesh(segments=3, radius=0.3429, angle=90.0))
        self.assertEqual(identity["element_families"], [{"family": "SEG2", "element_count": 3}])
        self.assertEqual(identity["discretisation"]["bend_count"], 1)

    def test_identity_omits_discretisation_when_there_are_no_bends(self):
        identity = mesh_identity(_straight_mesh(node_count=3))
        self.assertNotIn("discretisation", identity)
        self.assertEqual(identity["element_families"], [{"family": "SEG3", "element_count": 1}])


class TestTuyauSubpointIndexing(unittest.TestCase):
    def test_grid_shape_follows_the_code_aster_convention(self):
        self.assertEqual(sectors_per_layer(16), 33)
        self.assertEqual(layers_through_wall(3), 7)
        profile = section_profile(16, 3)
        self.assertEqual(profile["subpoints_per_node"], 33 * 7)
        self.assertEqual(profile["display_generatrice"], [0.0, 0.0, 1.0])

    def test_first_subpoint_sits_on_the_generatrice_at_the_bore(self):
        station = subpoint_station(1, nsec=16, ncou=3)
        self.assertEqual((station.sector_index, station.layer_index), (0, 0))
        self.assertEqual(station.angle_deg, 0.0)
        self.assertEqual(station.radius_fraction, 0.0)

    def test_indices_run_angle_fastest(self):
        stride = sectors_per_layer(16)
        self.assertEqual(subpoint_station(stride, nsec=16, ncou=3).layer_index, 0)
        self.assertEqual(subpoint_station(stride + 1, nsec=16, ncou=3).layer_index, 1)
        self.assertEqual(subpoint_station(stride + 1, nsec=16, ncou=3).sector_index, 0)

    def test_last_subpoint_reaches_the_outer_wall(self):
        last = sectors_per_layer(16) * layers_through_wall(3)
        station = subpoint_station(last, nsec=16, ncou=3)
        self.assertEqual(station.layer_index, 2 * 3)
        self.assertEqual(station.radius_fraction, 1.0)

    def test_malformed_indices_degrade_to_none(self):
        for bad in (0, -3, "9", None, True):
            self.assertIsNone(subpoint_station(bad))

    def test_decode_agrees_with_the_solver_fibre_offset(self):
        # The solver places display glyphs from this same convention. If the two
        # drift, sub-points land in the wrong place on the wall.
        from tuba.solver.aster import CodeAsterSolver

        r_ext, thickness = 0.05715, 0.00602
        for index in (1, 9, 34, 200):
            station = subpoint_station(index)
            y_offset, z_offset = CodeAsterSolver._code_aster_tuyau_fibre_offset(
                index, r_ext=r_ext, thickness=thickness
            )
            radius = (r_ext - thickness) + thickness * station.radius_fraction
            self.assertAlmostEqual(y_offset, radius * math.cos(station.angle_rad))
            self.assertAlmostEqual(z_offset, -radius * math.sin(station.angle_rad))

    def test_defaults_match_what_the_solver_requests(self):
        self.assertEqual((CODE_ASTER_TUYAU_NSEC, CODE_ASTER_TUYAU_NCOU), (16, 3))


if __name__ == "__main__":
    unittest.main()
