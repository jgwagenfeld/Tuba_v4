import math

import pytest

from tuba import Model
from tuba.analysis.results import ResultState
from tuba.visualization.builders._helpers import (
    GLYPH_RADIAL_SEGMENT_RANGE,
    SWEEP_FACET_TOLERANCE,
    SWEEP_RADIAL_SEGMENT_RANGE,
    glyph_radial_segments,
    sweep_radial_segments,
)
from tuba.visualization.builders._results import (
    _result_state_reaction_overlays,
    _tuyau_subpoint_glyph_points,
    _tuyau_subpoint_glyph_radius,
)


def test_reaction_glyphs_preserve_magnitude_ratios_and_separate_moment_units():
    model = Model("Glyph sizing")
    a, b = model.add_node([0, 0, 0]), model.add_node([2, 0, 0])
    state = ResultState("result", "study", 0, "Code_Aster", "Hot", None, {},
                        {a: (0, 1200, 0, 0, 0, 1e6), b: (0, 300, 0, 0, 0, 5e5)}, {})
    overlays = _result_state_reaction_overlays(model, state, None)
    lengths = {
        overlay.data["result_type"]: [math.dist(v["start"], v["end"]) for v in overlay.data["vectors"]]
        for overlay in overlays
    }
    assert math.isclose(lengths["reaction_force"][0], 0.3)
    assert math.isclose(lengths["reaction_force"][1], 0.075)
    assert math.isclose(lengths["reaction_moment"][0], 0.3)
    assert math.isclose(lengths["reaction_moment"][1], 0.15)


def _wall_row(station_radius, *, inner=0.04, outer=0.05, ncou=3, nsec=16):
    return {
        "centerline_position": [0.0, 0.0, 0.0],
        "inner_radius_m": inner,
        "outer_radius_m": outer,
        "tuyau_ncou": ncou,
        "tuyau_nsec": nsec,
    }, [0.0, 0.0, station_radius]


def test_tuyau_glyph_tick_is_sized_to_the_wall_and_never_overshoots_the_od():
    # An outer-wall sub-point used to be drawn to 1.25 x its station radius,
    # which fattened the run past its real OD. The tick now stops at the OD.
    row, point = _wall_row(0.05)
    start, end = _tuyau_subpoint_glyph_points(row, point)
    assert math.isclose(start[2], 0.05 - 0.01 / 12.0)
    assert math.isclose(end[2], 0.05)

    row, point = _wall_row(0.04)
    start, end = _tuyau_subpoint_glyph_points(row, point)
    assert math.isclose(start[2], 0.04)
    assert math.isclose(end[2], 0.04 + 0.01 / 12.0)

    row, point = _wall_row(0.045)
    start, end = _tuyau_subpoint_glyph_points(row, point)
    assert math.isclose(start[2], 0.045 - 0.01 / 12.0)
    assert math.isclose(end[2], 0.045 + 0.01 / 12.0)


def test_tuyau_glyph_radius_tracks_the_wall_instead_of_a_constant():
    # A third of a 10 mm wall is 3.33 mm; the sector gap caps it lower only on
    # small bores. Here the wall term wins.
    row, _ = _wall_row(0.045)
    assert math.isclose(_tuyau_subpoint_glyph_radius([row]), 0.01 / 3.0)

    # A heavy wall on a small bore is capped by the gap between sectors so the
    # rosette stays a ring of separate ticks instead of a solid collar.
    row, _ = _wall_row(0.085, inner=0.07, outer=0.1)
    gap_term = (2.0 * math.pi * 0.1 / 33.0) / 2.5
    assert gap_term < 0.03 / 3.0
    assert math.isclose(_tuyau_subpoint_glyph_radius([row]), gap_term)

    # Rows without section dimensions keep the legacy thickness.
    assert _tuyau_subpoint_glyph_radius([{"centerline_position": [0, 0, 0]}]) == 0.006


def test_sweep_faceting_follows_a_stated_budget_not_a_literal():
    # The count a sweep is drawn at used to be a literal in the renderer, which
    # meant nothing in the contract could be checked against what appeared on
    # screen. It is derived from the faceting budget instead, so tightening the
    # budget has to move the count.
    assert sweep_radial_segments() == 16
    assert sweep_radial_segments(0.01) > sweep_radial_segments(0.02) > sweep_radial_segments(0.05)

    # A 16-gon sags 1.9% of its own radius, which is the budget it is solved for.
    sag = 1.0 - math.cos(math.pi / sweep_radial_segments())
    assert sag < SWEEP_FACET_TOLERANCE

    low, high = SWEEP_RADIAL_SEGMENT_RANGE
    assert low <= sweep_radial_segments(1e-6) <= high, "a tight budget clamps rather than exploding"
    assert low <= sweep_radial_segments(0.999) <= high, "a loose one clamps too"


def test_a_facet_tolerance_outside_the_unit_interval_is_refused():
    for bad in (0.0, 1.0, -0.5, 1.5):
        with pytest.raises(ValueError, match=r"Facet tolerance must be in \(0, 1\)"):
            sweep_radial_segments(bad)


def test_sub_point_ticks_get_their_own_cheaper_circle():
    # A tick is read at a glance, not shaded, so it must not cost more than the
    # run it marks - the glyph batch is the largest triangle count in a scene.
    assert glyph_radial_segments() == 8
    low, high = GLYPH_RADIAL_SEGMENT_RANGE
    assert low <= glyph_radial_segments() <= high
    assert glyph_radial_segments() < sweep_radial_segments()


def test_both_display_surfaces_facet_a_section_identically():
    # `tuba/plotting/pipeline.py` sweeps its section loops with n_sides=16. The
    # two surfaces draw the same section, so they have to agree on how round it
    # is; a drift here is a review bundle and a notebook disagreeing about the
    # geometry of the same pipe.
    from tuba.plotting import pipeline

    default_sides = pipeline._get_profile_2d_loops.__defaults__[0]
    assert default_sides == sweep_radial_segments()
