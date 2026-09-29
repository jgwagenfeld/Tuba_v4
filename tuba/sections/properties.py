"""Geometric section properties computed from a Tuba section's own shape.

Code_Aster already derives the characteristics of every section Tuba can express
as a primitive: ``tuba/solver/aster_comm.py`` writes pipes and bars as
``SECTION='CERCLE', CARA=('R', 'EP')`` and rectangles as
``SECTION='RECTANGLE', CARA=('HY', 'HZ', ...)``, and the solver works out the
area and the moments itself. A rolled I-profile has no primitive, so it alone is
written as ``SECTION='GENERALE'`` with a full property vector - and that vector
is read from ``data/IBeam.output``, an Autochar (Sillage) table generated offline
and committed.

This module is the native half of that story. It computes the same quantities
from the section's geometry, so Tuba can state a section's area, its two second
moments and its torsional constant without a catalog lookup and without a solver,
and so a user-defined section - which has no catalog row at all - carries real
numbers. ``tests/test_section_properties.py`` bounds every value against
Sillage for the whole I-beam catalog, which is what keeps the two from drifting.

**Axes.** Coordinates are ``(y, z)``, matching the section loops in
:mod:`tuba.geometry.section_mesh` and the ``AFFE_CARA_ELEM`` names Code_Aster
is given. ``IY`` is the second moment *about the Y axis*, so it integrates
``z**2``; ``IZ`` is about the Z axis and integrates ``y**2``. For an upright
I-beam that makes ``IZ`` the strong axis and ``IY`` the weak one, which is the
order the catalog and ``aster_comm.py`` both use.

**These are derived geometry, not solver results.** A section property is
authored or computed from dimensions, never solved, and no surface may present it
as an evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from tuba.geometry.profiles import profile_for_section


#: Arc segments per quarter-turn in the filleted I-beam outline. A quarter circle
#: inscribed in a polygon loses ``1 - 2sin(pi/4n)/n`` of its area, which is
#: 3.9e-6 at 16 and 6.1e-7 at 64. The disagreement this module is tested on
#: against Sillage is three orders of magnitude larger, so 32 is comfortably
#: past the point of diminishing returns and keeps the outline cheap.
ARC_SEGMENTS = 32


@dataclass(frozen=True)
class SectionProperties:
    """One section's geometric properties, in SI units.

    ``iy_m4`` and ``iz_m4`` are second moments about the Y and Z axes; ``j_m4``
    is the Saint-Venant torsion constant. ``j_is_exact`` records whether ``j_m4``
    is the closed-form value or a thin-wall estimate, because a torsion constant
    that is 24% low for a filleted I-beam is a different claim from one that is
    exact for a circle, and a reader is entitled to know which they have.
    """

    kind: str
    area_m2: float
    centroid: tuple[float, float]
    iy_m4: float
    iz_m4: float
    iyz_m4: float
    j_m4: float
    j_is_exact: bool
    #: The property names Code_Aster is given, for a surface that has to write them.
    code_aster: dict[str, float]

    def _with_kind(self, kind: str) -> "SectionProperties":
        """The same properties under the kind of the section they came from.

        A pipe and a solid bar are both circular sections with identical closed
        forms, so ``_annulus`` builds one and the caller names it.
        """
        return replace(self, kind=kind)

    @property
    def gyration_y_m(self) -> float:
        """Radius of gyration about the Y axis: ``sqrt(IY / A)``.

        Named for what it is and deliberately *not* ``RY``. The catalog's ``RY``
        is the extreme-fibre distance - H/2 on every I-profile in the table - and
        two fields called ``ry_m`` meaning different things in the same product is
        how a reader ends up checking a beam's shear lag against its depth.
        """
        return math.sqrt(self.iy_m4 / self.area_m2) if self.area_m2 > 0.0 else 0.0

    @property
    def gyration_z_m(self) -> float:
        """Radius of gyration about the Z axis: ``sqrt(IZ / A)``."""
        return math.sqrt(self.iz_m4 / self.area_m2) if self.area_m2 > 0.0 else 0.0

    @property
    def polar_moment_m4(self) -> float:
        """Second moment about the member axis: ``IY + IZ``, no cross term."""
        return self.iy_m4 + self.iz_m4

    def as_dict(self) -> dict[str, float | str | bool | list[float]]:
        return {
            "kind": self.kind,
            "area_m2": self.area_m2,
            "centroid": [self.centroid[0], self.centroid[1]],
            "iy_m4": self.iy_m4,
            "iz_m4": self.iz_m4,
            "iyz_m4": self.iyz_m4,
            "j_m4": self.j_m4,
            "j_is_exact": self.j_is_exact,
            "gyration_y_m": self.gyration_y_m,
            "gyration_z_m": self.gyration_z_m,
            "polar_moment_m4": self.polar_moment_m4,
        }


# ---- polygon moments --------------------------------------------------------
def _polygon_moments(points: list[tuple[float, float]]) -> tuple[float, float, float, float, float]:
    """``(area, m_y, m_z, iy_about_origin, iz_about_origin)`` of a simple polygon.

    Green-integral forms, exact for a straight-edged polygon. ``m_y``/``m_z`` are
    the first moments (area times centroid), so the caller shifts to the centroid.
    """
    area = 0.0
    m_y = 0.0
    m_z = 0.0
    int_z2 = 0.0
    int_y2 = 0.0
    count = len(points)
    for index in range(count):
        y0, z0 = points[index]
        y1, z1 = points[(index + 1) % count]
        cross = y0 * z1 - y1 * z0
        area += cross
        m_y += (y0 + y1) * cross
        m_z += (z0 + z1) * cross
        int_z2 += (z0 * z0 + z0 * z1 + z1 * z1) * cross
        int_y2 += (y0 * y0 + y0 * y1 + y1 * y1) * cross
    area *= 0.5
    m_y /= 6.0
    m_z /= 6.0
    int_z2 /= 12.0
    int_y2 /= 12.0
    return area, m_y, m_z, int_z2, int_y2


def _arc(
    centre: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    steps: int,
) -> list[tuple[float, float]]:
    """Points along a circular arc, both endpoints included."""
    points = []
    for step in range(steps + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * step / steps)
        points.append((centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle)))
    return points


def _ibeam_outline(dimensions: dict[str, float], segments: int = ARC_SEGMENTS) -> list[tuple[float, float]]:
    """The filleted I-section outline in ``(y, z)``: ``y`` is depth, ``z`` is width.

    The root radius is a *reflex*-corner fillet, so its arc centre lies in the
    void across the corner and the material bulges outward into it. Each corner
    therefore adds a quarter disc of area ``R**2 * (1 - pi/4)`` beyond the sharp
    flanges-and-web outline - which is what separates a rolled section from the
    three rectangles a quick hand calculation builds.
    """
    height = float(dimensions["H"])
    width = float(dimensions["B"])
    web = float(dimensions["Tw"])
    flange = float(dimensions["Tf"])
    radius = float(dimensions.get("R", 0.0) or 0.0)
    if min(height, width, web, flange) <= 0.0:
        raise ValueError("An I-beam section needs positive H, B, Tw and Tf.")
    if radius < 0.0:
        raise ValueError("An I-beam root radius R cannot be negative.")
    half_depth = height / 2.0
    half_width = width / 2.0
    half_web = web / 2.0
    flange_underside = half_depth - flange
    if flange_underside <= half_web + radius:
        raise ValueError(
            f"An I-beam with H={height}, Tf={flange} leaves no web between the "
            f"flanges once the R={radius} root radii are added."
        )
    if half_width <= half_web + radius:
        raise ValueError(
            f"An I-beam with B={width}, Tw={web} is too narrow to carry R={radius} root radii."
        )

    def corner(centre_u: float, centre_v: float, start: float, end: float) -> list[tuple[float, float]]:
        """The root-radius arc at a reflex corner, or nothing when R is zero."""
        if radius <= 0.0:
            return []
        return _arc((centre_u, centre_v), radius, start, end, segments)[1:]

    # Each root radius rounds a *re-entrant* corner: the void lies between the
    # flanges, outside the web, so the arc centre sits at (u0 - R sign(u0),
    # v0 + R sign(v0)) - toward mid-height and away from the web. Getting that
    # sign wrong puts the arc on the far side of its own chord, which subtracts
    # the fillet instead of adding it and costs a tenth of the section's area.
    inner_u = half_web + radius
    web_top = flange_underside - radius
    web_bottom = -flange_underside + radius
    points: list[tuple[float, float]] = [
        (half_depth, half_width),
        (half_depth, -half_width),
        (flange_underside, -half_width),
        (flange_underside, -inner_u),
    ]
    points.extend(corner(flange_underside - radius, -inner_u, 0.0, 90.0))
    points.append((web_top, -half_web))
    points.append((web_bottom, -half_web))
    points.extend(corner(-flange_underside + radius, -inner_u, 90.0, 180.0))
    points.extend(
        [
            (-flange_underside, -half_width),
            (-half_depth, -half_width),
            (-half_depth, half_width),
            (-flange_underside, half_width),
            (-flange_underside, inner_u),
        ]
    )
    points.extend(corner(-flange_underside + radius, inner_u, 180.0, 270.0))
    points.append((web_bottom, half_web))
    points.append((web_top, half_web))
    points.extend(corner(flange_underside - radius, inner_u, 270.0, 360.0))
    points.append((flange_underside, half_width))
    return _without_duplicate_neighbors(points)


def _without_duplicate_neighbors(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop consecutive repeats, and a final point equal to the first.

    A zero-radius corner emits the vertex that precedes its arc, so a naive
    concatenation repeats it. A repeated vertex is harmless to the reader and
    silently destroys the polygon integral, so it is removed rather than trusted.
    """
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if not cleaned or cleaned[-1] != point:
            cleaned.append(point)
    while len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    return cleaned


def _counterclockwise(loop: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """*loop* wound so its signed area is positive, reversed if it is not."""
    return loop if _polygon_moments(loop)[0] >= 0.0 else list(reversed(loop))


def _outline_loops(section, *, segments: int = ARC_SEGMENTS) -> tuple[list[list[tuple[float, float]]], ...]:
    """The exact section outline: the outer loop, then any void.

    Every loop is wound so its signed area is positive, matching
    :func:`tuba.geometry.section_mesh.section_loops`. The caller then adds the
    first loop and subtracts the rest; a polygon wound the other way contributes
    a negative area and an outline that encloses everything reads as enclosing
    nothing.
    """
    profile = profile_for_section(section)
    dimensions = profile.dimensions
    kind = profile.kind

    if kind in ("pipe", "bar", "cable"):
        raise ValueError("Circular sections use their closed forms, not an outline.")
    if kind == "rectangular":
        half_y = float(dimensions["height_y"]) / 2.0
        half_z = float(dimensions["height_z"]) / 2.0
        outer = [(-half_y, -half_z), (-half_y, half_z), (half_y, half_z), (half_y, -half_z)]
        wall_y = float(dimensions["thickness_y"])
        wall_z = float(dimensions["thickness_z"])
        solid_y, solid_z = wall_y <= 0.0, wall_z <= 0.0
        if solid_y != solid_z:
            raise ValueError(
                f"A rectangular section {profile.dimensions} is hollow on one axis and solid on "
                "the other, which has no single wall thickness. Split it or give it a closed box."
            )
        if solid_y:
            return (_counterclockwise(outer),)
        inner_y = half_y - wall_y
        inner_z = half_z - wall_z
        if inner_y <= 0.0 or inner_z <= 0.0:
            raise ValueError(
                f"A rectangular section {profile.dimensions} has a wall of "
                f"{min(wall_y, wall_z)} on a half-extent of {min(half_y, half_z)}; it has no bore."
            )
        inner = [
            (-inner_y, -inner_z),
            (-inner_y, inner_z),
            (inner_y, inner_z),
            (inner_y, -inner_z),
        ]
        return (_counterclockwise(outer), _counterclockwise(inner))
    if kind == "ibeam":
        return (_counterclockwise(_ibeam_outline(dimensions, segments)),)
    raise ValueError(f"Unsupported section profile kind {kind!r}.")

# ---- closed forms for the circular kinds ------------------------------------
def _annulus(outer_radius: float, inner_radius: float) -> SectionProperties:
    """Exact properties of a circular annulus, or of a solid circle when the bore is 0."""
    if outer_radius <= 0.0:
        raise ValueError("A circular section needs a positive outer radius.")
    if not 0.0 <= inner_radius < outer_radius:
        raise ValueError(
            f"A circular section needs 0 <= bore radius < outer radius, got bore "
            f"{inner_radius} and outer {outer_radius}."
        )
    ro4 = outer_radius**4
    ri4 = inner_radius**4
    area = math.pi * (outer_radius**2 - inner_radius**2)
    # Second moment about a diameter of a circular annulus. A solid circle is
    # pi r**4 / 4, so the annulus is pi (ro**4 - ri**4) / 4 - the /4, not the /64
    # a diameter-based formula would need, because these are radii.
    inertia = math.pi * (ro4 - ri4) / 4.0
    # A circle is the one shape where torsion about the axis and about a
    # diameter differ by exactly a factor of two.
    torsion = 2.0 * inertia
    return SectionProperties(
        kind="circular",
        area_m2=area,
        centroid=(0.0, 0.0),
        iy_m4=inertia,
        iz_m4=inertia,
        iyz_m4=0.0,
        j_m4=torsion,
        j_is_exact=True,
        code_aster={"A": area, "IY": inertia, "IZ": inertia, "JX": torsion},
    )


def _rectangular_torsion(half_y: float, half_z: float, wall_y: float, wall_z: float) -> tuple[float, bool]:
    """Saint-Venant torsion constant of a rectangle or a box.

    A closed box is Bredt-exact. A solid rectangle has no elementary closed form,
    so it uses Saint-Venant's own series for a rectangular bar, which converges
    slowly for a slender section and is flagged inexact.
    """
    if wall_y > 0.0 and wall_z > 0.0:
        # Bredt: J = 4 A_m**2 / closed(ds/t), with the median line between the
        # wall mid-surfaces. For a box, y runs along the width and z along the
        # height, so the walls at |z| = half_z carry wall_z and vice versa.
        median_y = half_y - 0.5 * wall_y
        median_z = half_z - 0.5 * wall_z
        enclosed = 4.0 * median_y * median_z
        integral = 4.0 * median_y / wall_z + 4.0 * median_z / wall_y
        return enclosed**2 / integral, True
    # Solid rectangle, Saint-Venant's series for b >= t.
    long_side, short_side = max(half_y, half_z), min(half_y, half_z)
    if short_side <= 0.0:
        raise ValueError("A rectangular section needs a positive half-extent.")
    width = 2.0 * short_side
    depth = 2.0 * long_side
    ratio = short_side / long_side
    return (width * depth**3) / 3.0 * (1.0 - 0.630 * ratio + 0.052 * ratio**5), False


def _ibeam_torsion(dimensions: dict[str, float]) -> float:
    """Thin-wall torsion constant of an open I-section, ``J = sum(b t**3) / 3``.

    Open sections carry torsion as ``J = 1/3 * sum(b_i t_i**3)`` over the wall
    mid-lines. The root radii are not separate walls in that sum - they thicken
    the web-to-flange transition, and Sillage resolves that thickening into its
    integral while this estimate cannot. The disagreement is measured and bounded
    in ``tests/test_section_properties.py`` rather than papered over.
    """
    height = float(dimensions["H"])
    width = float(dimensions["B"])
    web = float(dimensions["Tw"])
    flange = float(dimensions["Tf"])
    clear_web = height - 2.0 * flange
    return (2.0 * width * flange**3 + clear_web * web**3) / 3.0


# ---- the one public entry ---------------------------------------------------
def properties_for_section(section) -> SectionProperties:
    """The geometric properties of *section*, computed from its own shape.

    Raises ``ValueError`` for a section whose dimensions cannot describe a solid:
    a negative bore, a box that is hollow on one axis only, an I-beam whose root
    radii leave no web.
    """
    profile = profile_for_section(section)
    dimensions = profile.dimensions
    kind = profile.kind

    if kind == "pipe":
        return _annulus(
            float(dimensions["OD"]) / 2.0,
            float(dimensions["ID"]) / 2.0,
        )._with_kind("pipe")
    if kind == "bar":
        outer = float(dimensions["OD"]) / 2.0
        wall = float(dimensions["WT"])
        if wall >= outer:
            raise ValueError(
                f"A hollow bar needs a wall thinner than its outer radius, got WT={wall} on OD={dimensions['OD']}."
            )
        bore = 0.0 if wall <= 0.0 else outer - wall
        return _annulus(outer, bore)._with_kind("bar")
    if kind == "cable":
        return _annulus(float(dimensions["radius"]), 0.0)._with_kind("cable")

    loops = _outline_loops(section)
    area = 0.0
    m_y = 0.0
    m_z = 0.0
    int_z2 = 0.0
    int_y2 = 0.0
    for index, loop in enumerate(loops):
        loop_area, loop_m_y, loop_m_z, loop_z2, loop_y2 = _polygon_moments(loop)
        sign = 1.0 if index == 0 else -1.0
        area += sign * loop_area
        m_y += sign * loop_m_y
        m_z += sign * loop_m_z
        int_z2 += sign * loop_z2
        int_y2 += sign * loop_y2
    if area <= 0.0:
        raise ValueError(
            f"Section {getattr(section, 'name', section)!r} encloses no area; its dimensions "
            f"({dimensions}) do not describe a solid."
        )
    centroid = (m_y / area, m_z / area)
    iy = int_z2 - area * centroid[1] ** 2
    iz = int_y2 - area * centroid[0] ** 2

    if kind == "rectangular":
        wall_y = float(dimensions["thickness_y"])
        wall_z = float(dimensions["thickness_z"])
        torsion, exact = _rectangular_torsion(
            float(dimensions["height_y"]) / 2.0,
            float(dimensions["height_z"]) / 2.0,
            wall_y,
            wall_z,
        )
    else:
        torsion, exact = _ibeam_torsion(dimensions), False

    return SectionProperties(
        kind=kind,
        area_m2=area,
        centroid=centroid,
        iy_m4=iy,
        iz_m4=iz,
        iyz_m4=0.0,
        j_m4=torsion,
        j_is_exact=exact,
        code_aster={"A": area, "IY": iy, "IZ": iz, "JX": torsion},
    )
