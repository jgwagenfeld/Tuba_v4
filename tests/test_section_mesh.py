from collections import Counter

import numpy as np
import pytest

from tuba.geometry.section_mesh import beam_local_frame, section_loops, straight_section_surface_mesh
from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection


def _sections():
    return [
        PipeSection("Pipe", OD=0.1, WT=0.01),
        BarSection("Bar", OD=0.08, WT=0.0),
        CableSection("Cable", radius=0.02),
        RectangularSection("RHS", height_y=0.12, height_z=0.08, thickness_y=0.01, thickness_z=0.01),
        IBeamSection.load_from_db("Column", "IPE100"),
    ]


@pytest.mark.parametrize("section", _sections(), ids=lambda section: section.name)
def test_straight_section_surface_mesh_is_finite_closed_and_indexed(section):
    mesh = straight_section_surface_mesh(section, (0.0, 0.0, 0.0), (2.0, 0.0, 0.0))
    vertices = np.asarray(mesh.vertices)

    assert len(vertices) >= 8
    assert len(mesh.faces) >= 8
    assert np.isfinite(vertices).all()
    assert all(len(face) == 3 for face in mesh.faces)
    assert max(index for face in mesh.faces for index in face) < len(vertices)

    edges = Counter(
        tuple(sorted((face[index], face[(index + 1) % 3])))
        for face in mesh.faces
        for index in range(3)
    )
    assert set(edges.values()) == {2}

    signed_volume = sum(
        np.dot(vertices[a], np.cross(vertices[b], vertices[c])) / 6.0
        for a, b, c in mesh.faces
    )
    assert signed_volume > 0.0


def test_hollow_section_loops_preserve_outer_and_inner_dimensions():
    loops = section_loops(
        RectangularSection(
            "RHS",
            height_y=0.12,
            height_z=0.08,
            thickness_y=0.01,
            thickness_z=0.01,
        )
    )

    assert len(loops) == 2
    assert np.allclose(sorted(loops[0]), sorted([(-0.06, -0.04), (0.06, -0.04), (0.06, 0.04), (-0.06, 0.04)]))
    assert np.allclose(sorted(loops[1]), sorted([(-0.05, -0.03), (0.05, -0.03), (0.05, 0.03), (-0.05, 0.03)]))


def test_vertical_ipe_keeps_engineering_y_axis_and_honors_twist():
    section = IBeamSection.load_from_db("Column", "IPE100")
    untwisted = np.asarray(
        straight_section_surface_mesh(section, (0.0, 0.0, 0.0), (0.0, 0.0, 2.0)).vertices
    )
    twisted = np.asarray(
        straight_section_surface_mesh(
            section,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 2.0),
            twist_angle_deg=90.0,
        ).vertices
    )

    assert np.ptp(untwisted[:, 1]) == pytest.approx(0.1)
    assert np.ptp(untwisted[:, 0]) == pytest.approx(0.055)
    assert np.ptp(twisted[:, 1]) == pytest.approx(0.055)
    assert np.ptp(twisted[:, 0]) == pytest.approx(0.1)


def test_rejects_zero_length_extrusion():
    with pytest.raises(ValueError, match="distinct finite endpoints"):
        straight_section_surface_mesh(_sections()[0], (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_rejects_circular_profile_with_fewer_than_three_sides():
    with pytest.raises(ValueError, match="at least three sides"):
        straight_section_surface_mesh(
            _sections()[0],
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            n_sides=2,
        )

def test_the_two_display_surfaces_start_from_one_shared_beam_frame():
    # The review bundle extrudes element sections with this frame and the
    # quick-look path starts its parallel transport from it. They used to carry
    # a copy each of the same construction, which agreed only by accident: an
    # I-beam's web could end up oriented differently in a notebook than in the
    # review bundle, and nothing would say so. A round pipe hides the difference,
    # which is exactly why it needs a test.
    from tuba.plotting import pipeline

    for section in _sections():
        if isinstance(section, PipeSection):
            continue  # rotationally symmetric: its frame is unobservable
        start, end = (0.0, 0.0, 0.0), (2.0, 0.4, 0.0)
        local_x, local_y, local_z = beam_local_frame(start, end)

        path = np.array([start, np.asarray(start) * 0.5 + np.asarray(end) * 0.5, end])
        frames = pipeline._parallel_transport_frames(path)

        assert np.allclose(frames[0][0], local_x)
        assert np.allclose(frames[0][1], local_y)
        assert np.allclose(frames[0][2], local_z)

    # And the frame is right-handed with the section on the y-z plane, which is
    # what "matching Code_Aster ANGL_VRIL" is supposed to mean.
    local_x, local_y, local_z = beam_local_frame((0.0, 0.0, 0.0), (1.0, 0.5, 0.0))
    assert np.allclose(np.cross(local_x, local_y), local_z)
    for axis in (local_x, local_y, local_z):
        assert np.isclose(np.linalg.norm(axis), 1.0)
