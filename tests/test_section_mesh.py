from collections import Counter

import numpy as np
import pytest

from tuba.geometry.section_mesh import section_loops, straight_section_surface_mesh
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
