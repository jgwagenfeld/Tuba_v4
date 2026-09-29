"""Reading ``GENE_TUYAU`` back out of the study's own ``.comm``.

Tuba computes a generatrice per model and writes it into the command file
(``CARA='GENE_TUYAU'``). That vector is what Code_Aster measures sector 0 from,
so anything that draws a sub-point from a different vector rotates every
sector index. These tests pin the read-back and the fallback, against the
evidence files the repository actually ships.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from tuba.analysis.tuyau import (
    DISPLAY_GENERATRICE,
    GENERATRICE_FALLBACK,
    GENERATRICE_SOLVED,
    Generatrice,
    read_gene_tuyau,
    solve_generatrice,
    subpoint_station,
)
from tuba.solver.parse_tables import read_work_dir_generatrice, tuyau_cross_section_axes

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "examples" / "code-aster-review" / "evidence" / "Operating" / "study.comm"

MULTILINE = """
        _F(
            GROUP_NO='G06D7539',
            CARA='GENE_TUYAU',
            VALE=(1.00000000E+00, 1.00000000E+00, 1.00000000E+00),
        ),
"""
SINGLE_LINE = "_F(GROUP_NO='G1',CARA='GENE_TUYAU',VALE=(0.0, 0.0, 1.0)),"


def test_the_read_back_finds_the_orientation_in_either_layout():
    assert read_gene_tuyau(MULTILINE) == (1.0, 1.0, 1.0)
    assert read_gene_tuyau(SINGLE_LINE) == (0.0, 0.0, 1.0)


def test_orientation_is_read_only_from_its_own_factor_and_not_comments():
    assert read_gene_tuyau('_F(CARA="GENE_TUYAU", VALE=(1, -2, 3))') == (1.0, -2.0, 3.0)
    assert read_gene_tuyau("_F(CARA='GENE_TUYAU'), _F(CARA='VECT_Y', VALE=(1, 2, 3))") is None
    assert read_gene_tuyau("# _F(CARA='GENE_TUYAU', VALE=(1, 2, 3))\nFIN()") is None


def test_subpoint_indices_cannot_leave_the_requested_wall_grid():
    last = (2 * 16 + 1) * (2 * 3 + 1)
    assert subpoint_station(last).radius_fraction == 1.0
    assert subpoint_station(last + 1) is None


def test_a_shipped_study_solves_to_the_orientation_its_comm_declares():
    # Not a hand-written fixture: the evidence file the repository publishes. If
    # the writer ever stops emitting a usable orientation, this is what notices.
    comm = EVIDENCE.read_text(encoding="utf-8", errors="replace")
    generatrice = solve_generatrice(comm)
    assert generatrice.solved
    assert generatrice.source == GENERATRICE_SOLVED
    assert math.isclose(math.dist(generatrice.vector, (0.0, 0.0, 1.0)), 0.0, abs_tol=1.0) is False, (
        "the shipped study is the case that was wrong: its solver orientation is not (0, 0, 1), "
        "which is exactly why the display must read it back rather than assume it"
    )


@pytest.mark.parametrize(
    "comm",
    [
        "",
        "PDE = 'RESU_TUYA'",
        "CARA='GENE_TUYAU',",  # names the feature but never gives a value
        "CARA='GENE_TUYAU',VALE=(1.0, 2.0, nan),",
        "CARA='GENE_TUYAU',VALE=(0.0, 0.0, 0.0),",  # not a direction
        "CARA='GENE_TUYAU',VALE=(1.0, 2.0),",  # not a triplet
    ],
)
def test_anything_unusable_falls_back_and_says_so(comm):
    generatrice = solve_generatrice(comm)
    assert not generatrice.solved
    assert generatrice.source == GENERATRICE_FALLBACK
    assert generatrice.vector == DISPLAY_GENERATRICE


def test_a_missing_work_dir_falls_back_rather_than_raising(tmp_path):
    generatrice = read_work_dir_generatrice(tmp_path / "nope")
    assert not generatrice.solved
    assert generatrice.vector == DISPLAY_GENERATRICE


def test_the_solver_orientation_actually_moves_the_glyphs():
    # The whole reason for the read-back: with a different reference direction,
    # sector 0 lands somewhere else. On a straight run along X, the shipped
    # study's (1, 1, 1) puts sector 0 four of the 33 stations away from the
    # fallback's, which on a DN100 is tens of millimetres of wall.
    tangent = np.array([1.0, 0.0, 0.0])
    fallback_y, _ = tuyau_cross_section_axes(tangent, generatrice=Generatrice(DISPLAY_GENERATRICE, GENERATRICE_FALLBACK))
    solved_y, _ = tuyau_cross_section_axes(tangent, generatrice=Generatrice((1.0, 1.0, 1.0), GENERATRICE_SOLVED))

    rotation = math.degrees(math.acos(float(np.clip(np.dot(fallback_y, solved_y), -1.0, 1.0))))
    assert math.isclose(rotation, 45.0, abs_tol=1e-6)
    # 33 stations close the circle, so a full turn is 2*NSEC = 32 steps.
    step = 360.0 / 32
    assert math.isclose(rotation / step, 4.0, abs_tol=1e-6), "station 0 in one frame is station 4 in the other"


def test_a_vertical_run_still_gets_a_frame():
    # The fallback chain exists for a pipe whose direction is parallel to the
    # reference, where the projection collapses. It must still produce an
    # orthonormal frame rather than dividing by zero.
    for tangent in ([0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [0.577, 0.577, 0.577]):
        y_axis, z_axis = tuyau_cross_section_axes(np.asarray(tangent), generatrice=Generatrice((0.0, 0.0, 1.0), GENERATRICE_SOLVED))
        assert math.isclose(float(np.linalg.norm(y_axis)), 1.0, abs_tol=1e-9)
        assert math.isclose(float(np.linalg.norm(z_axis)), 1.0, abs_tol=1e-9)
        assert math.isclose(abs(float(np.dot(y_axis, z_axis))), 0.0, abs_tol=1e-9)


def test_the_frame_stays_orthonormal_for_a_real_study_orientation():
    tangent = np.array([0.0, 0.0, 1.0])
    x_axis = tangent / np.linalg.norm(tangent)
    for reference in ((1.0, 1.0, 1.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (1.0, -1.0, 1.0)):
        y_axis, z_axis = tuyau_cross_section_axes(x_axis, generatrice=Generatrice(reference, GENERATRICE_SOLVED))
        assert math.isclose(abs(float(np.dot(x_axis, y_axis))), 0.0, abs_tol=1e-9)
        assert math.isclose(abs(float(np.dot(x_axis, z_axis))), 0.0, abs_tol=1e-9)
        assert math.isclose(float(np.dot(np.cross(x_axis, y_axis), z_axis)), 1.0, abs_tol=1e-9)
