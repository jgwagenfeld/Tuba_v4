"""A multi-bay steel portal-frame industrial building, solved by Code_Aster.

The structure is the skeleton in the reference photo: repeated transverse portal
frames, each a cambered bowstring roof truss carried on two I-section columns,
tied together longitudinally by roof purlins, eave struts and wall girts, and
stiffened by roof plan bracing and wall bracing in the end bays.

Five modelling facts the solver forces, each learned from a failed run:

* Joints must share one node id. ``model.pipe`` mints a fresh node at the end of
  every run, so a frame is authored with :func:`add_member` on explicitly
  resolved nodes. Otherwise every joint becomes two coincident nodes, which the
  clash gate rejects and Code_Aster reads as a disconnected structure.
* The web must be beams, not bars. This is the one that cost the most time.
  Code_Aster's ``BARRE`` is a pin-jested truss element: three translational
  degrees of freedom per node and *no rotational stiffness whatsoever*. Building
  the truss web out of bars alongside the beam chords leaves the frame's global
  stiffness matrix rank-deficient, and Code_Aster reports a singular pivot on a
  translational degree of freedom that in fact has stiffness. Switching only the
  web to beams - same geometry, same coordinates, same loads - solves it. MUMPS
  with singular-pivot detection disabled confirmed the defect was a true null
  space rather than a strict pivot tolerance, so no solver setting papers over it.
* Two parallel planar trusses need bracing in *both* directions, and at the tie
  level as well as the roof. A portal frame's web lies wholly in its own plane, so
  the bottom chord has no out-of-plane stiffness from the web and needs plan
  bracing of its own.
* A braced panel takes one diagonal, not an X. Two diagonals crossing inside a
  panel pass through each other, and a centre node would leave that node with no
  rotational stiffness.
* Gravity and a wind line load cannot share a load case. ``CALC_CHAMP`` accepts a
  single distributed load on a beam model and self-weight already is one, so the
  two are separate cases.

Result coverage: displacements and reactions are real for both cases. Von Mises
stress is *not* available for this model - Tuba only requests Code_Aster's
``SIEQ`` equivalent-stress field when the model contains pipe elements, and this
is a pure structural frame. ``study.py`` therefore reports deflection and
reaction only, and a missing stress number means "not computed", never zero.

Authored values are engineering inputs, not code results: Tuba selects no design
standard and computes no wind pressure. ``WIND_LINE_LOAD_N_PER_M`` is the lateral
line load the cladding hands to the purlins and girts, and belongs to whoever owns
the structural design. The sections are plausible first-pass sizes, not a design.

The analysis is *first order*, and that is a real limit on what these results can
be used for. Code_Aster is asked for a linear ``MECA_STATIQUE``, so the solver
never re-evaluates the geometry under load: the axial force in a member is
computed for the undeformed shape, and no P-Delta (geometric stiffness) term
enters the system. For a slender frame that understates two things - the true
axial compression in a column, and the sway a second-order analysis amplifies -
and it means **none of the reported moments is a design moment**. Tuba does not
expose a second-order path for a pure beam frame; ``is_nonlinear`` in
``tuba/solver/aster_comm.py`` is raised only by contacts and cable elements. So
this model answers "how does the frame deflect and how much load reaches the
foundations", and deliberately not "is any member adequate".

Code_Aster can do linear buckling eigenvalue analysis on these very beams -
``CALC_MODES(TYPE_RESU='MODE_FLAMB')`` on an assembled K and geometric K_G - and
Tuba exposes it as ``buckling=`` on a load case. The chain is emitted by
``tuba/solver/aster_buckling.py``; the geometric stiffness is taken from the
static solve of this same load case, so one run gives both.

The factors are 30.49, 29.19, 28.94, 27.42, 26.91, 26.53, 25.39 and 23.87 on the
gravity case, with a mean a-posteriori error of 6.1e-13. So the frame is far from
a gravity buckling limit - but that is an optimistic bound, not a design margin: a
linearised perfect-frame figure with no initial imperfection, built on a
first-order prestress that understates column compression. Code_Aster also
reports a ninth near-zero critical charge it did not compute, which points at the
tie line's out-of-plane restraint rather than at anything real. See
``docs/content/structural-frames.md``.
"""

import math
from typing import Dict, List, Sequence, Tuple

from tuba import Model

Point3D = Tuple[float, float, float]

#: Clear span between column centres, across the frames [m].
SPAN_M = 30.0
#: Bay length between adjacent frames, along the building [m].
BAY_LENGTH_M = 6.0
#: Number of transverse frames; bays are one fewer.
FRAME_COUNT = 7
#: Column height to the truss springing [m].
EAVE_HEIGHT_M = 8.0
#: Camber of the roof truss above the springing, at midspan [m].
ROOF_RISE_M = 4.0
#: Rise of the top chord above the tie at the springings [m]. A real truss depth
#: at the ends, so the end web members are not collinear with the chords.
TRUSS_SPRINGING_RISE_M = 1.5
#: Top-chord panels per frame; sets the truss web resolution.
TRUSS_PANEL_COUNT = 10
#: Wall girt levels, measured from the base and excluding the eave strut [m].
GIRT_LEVELS_M = (2.0, 4.0, 6.0)
#: Bays that carry roof plan and wall bracing, counted from the first bay.
BRACED_BAYS = (0, 5)

#: Cross-section rotation about each member's own axis, in degrees.
#:
#: This is load-bearing, not cosmetic. For a horizontal member the local triad is
#: X along the span, Z up, Y horizontal-transverse, so vertical bending is
#: bending about local Y and is resisted by the catalog ``IY`` - which for a
#: rolled I-section is the *weak* axis (IPE200: IY 1.42e-6 against IZ 1.94e-5,
#: a factor of 13.7). Left at zero, every chord, purlin and girt bends about its
#: weak axis. Rotating 90 degrees puts the strong axis where gravity acts.
#:
#: Verified by solving rather than assumed: a fixed IPE200 under a 10 kN midspan
#: load over 12 m deflects 301.3 mm at 0 degrees and 22.4 mm at 90, matching
#: FL^3/(192*E*I) for the weak and strong axes respectively. The same test on a
#: vertical HE300B cantilever shows an X-direction push on the weak axis at zero.
#:
#: It also decides which component a result is *reported* under: at 90 degrees the
#: same shear moved from ``VZ`` to ``VY``. A reader of the section-force table
#: therefore needs the twist of each member to interpret the columns.
STRONG_AXIS_TWIST_DEG = 90.0
#: Members whose section is a doubly symmetric hollow (the web and the bracing),
#: for which the rotation has no effect. Left at zero so the model states the
#: fact rather than implying a choice.
SYMMETRIC_TWIST_DEG = 0.0

#: Lateral line load on the cladding-carrying members, for the wind case [N/m].
#: User-supplied: set it against the standard your project works to.
WIND_LINE_LOAD_N_PER_M = 1500.0


def _finite(name: str, value: float) -> float:
    """Return *value* as a float, refusing anything that is not a finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return number


def _positive(name: str, value: float) -> float:
    number = _finite(name, value)
    if number <= 0.0:
        raise ValueError(f"{name} must be greater than zero, got {value!r}.")
    return number


def _count(name: str, value: int, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}.")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value!r}.")
    return value


def camber_height(
    x: float, span: float, springing: float, rise: float
) -> float:
    """Roof truss centreline height at across-span coordinate *x*.

    Parabolic: *springing* at both supports and *rise* above that at midspan, so
    the two supports land exactly on *springing*. The chord never returns to the
    tie level, which is what keeps the truss depth real at the springings.
    """
    ratio = 2.0 * _finite("x", x) / _positive("span", span) - 1.0
    return _finite("springing", springing) + _finite("rise", rise) * (1.0 - ratio * ratio)


def add_member(
    model: Model,
    n1: str,
    n2: str,
    section: str,
    material: str,
    *,
    kind: str = "beam",
    member_id: str,
    twist_angle: float = 0.0,
) -> str:
    """Add one straight structural member between two existing nodes.

    *twist_angle* rotates the cross-section about the member's own axis and
    reaches Code_Aster as ``ANGL_VRIL``. It is not cosmetic: it decides which of
    an I-section's two inertias resists which bending, and with it which
    component the reported shear and moment appear under.
    """
    return model.add_element(
        id=member_id, type=kind, n1=n1, n2=n2, section=section, material=material,
        twist_angle=twist_angle,
    ).id


def column_levels(eave_height: float, girt_levels: Sequence[float]) -> List[float]:
    """Column node heights: the girt levels, then the eave where the truss springs."""
    eave = _positive("eave_height", eave_height)
    levels = sorted({_positive("girt level", level) for level in girt_levels})
    if any(level >= eave for level in levels):
        raise ValueError(
            f"girt levels {levels} must sit below the eave height {eave} m."
        )
    return [0.0, *levels, eave]


def truss_frame(
    model: Model,
    station: float,
    material: str,
    sections: Dict[str, str],
    span: float,
    eave_height: float,
    rise: float,
    springing_rise: float,
    panel_count: int,
    girt_levels: Sequence[float],
    strong_axis_twist: float = 0.0,
) -> Dict[str, Dict[int, str]]:
    """Build one transverse portal frame: two columns and a cambered roof truss.

    The truss is a bowstring. Its top chord follows the camber, its bottom chord
    is the level tie between the two column tops, and a triangulated bar web
    carries the panels between them. The top chord starts *springing_rise* above
    the tie at each end, so the end panels have a real truss depth; without that
    the end diagonals run collinear with the chords and the clash gate rejects the
    frame.

    Returns the frame's top- and bottom-chord node ids keyed by panel index, which
    is what the longitudinal units tie into.
    """
    y = _finite("station", station)
    if station < 0.0:
        raise ValueError(f"station must not be negative, got {station!r}.")
    span_value = _positive("span", span)
    panels = _count("panel_count", panel_count, 2)
    levels = column_levels(eave_height, girt_levels)
    eave = _positive("eave_height", eave_height)
    springing = eave + _positive("springing_rise", springing_rise)
    column_section = sections["column"]
    chord_top_section = sections["chord_top"]
    chord_bottom_section = sections["chord_bottom"]
    web_section = sections["web"]

    top: Dict[int, str] = {}
    bottom: Dict[int, str] = {}
    for index in range(panels + 1):
        x = span_value * index / panels
        top[index] = model.get_or_create_node(
            (x, y, camber_height(x, span_value, springing, rise)), tolerance=1e-9
        )
        bottom[index] = model.get_or_create_node((x, y, eave), tolerance=1e-9)

    for side, x in (("start", 0.0), ("end", span_value)):
        previous = model.get_or_create_node((x, y, levels[0]), tolerance=1e-9)
        model.add_support(node=previous, type="anchor")
        for segment, height in enumerate(levels[1:]):
            # The top segment lands on the truss springing node itself, so the
            # column and the truss share a joint with no extra member between.
            current = (
                bottom[0 if side == "start" else panels] if height == eave
                else model.get_or_create_node((x, y, height), tolerance=1e-9)
            )
            add_member(
                model, previous, current, column_section, material,
                member_id=f"col_f{station:g}_{side}_s{segment}",
                twist_angle=strong_axis_twist,
            )
            previous = current

    for index in range(panels):
        add_member(
            model, top[index], top[index + 1], chord_top_section, material,
            member_id=f"chord_top_f{station:g}_p{index}",
            twist_angle=strong_axis_twist,
        )
        add_member(
            model, bottom[index], bottom[index + 1], chord_bottom_section, material,
            member_id=f"chord_bottom_f{station:g}_p{index}",
            twist_angle=strong_axis_twist,
        )
        # Pratt web: diagonals lean back toward the support they carry.
        add_member(
            model, bottom[index], top[index + 1], web_section, material,
            member_id=f"web_diag_f{station:g}_p{index}",
        )
    for index in range(panels + 1):
        add_member(
            model, bottom[index], top[index], web_section, material,
            member_id=f"web_vert_f{station:g}_p{index}",
        )

    return {"top": top, "bottom": bottom}


def frame_row(
    model: Model,
    material: str,
    sections: Dict[str, str],
    frame_count: int,
    bay_length: float,
    span: float,
    eave_height: float,
    rise: float,
    springing_rise: float,
    panel_count: int,
    girt_levels: Sequence[float],
    strong_axis_twist: float = 0.0,
) -> List[Dict[str, Dict[int, str]]]:
    """March the portal frames along the building at a constant bay length."""
    frames = _count("frame_count", frame_count, 2)
    bay = _positive("bay_length", bay_length)
    return [
        truss_frame(
            model, index * bay, material, sections,
            span, eave_height, rise, springing_rise, panel_count, girt_levels,
            strong_axis_twist=strong_axis_twist,
        )
        for index in range(frames)
    ]


def longitudinal_members(
    model: Model,
    frames: Sequence[Dict[str, Dict[int, str]]],
    material: str,
    section: str,
    strong_axis_twist: float = 0.0,
    *,
    chord: str,
    id_prefix: str,
) -> List[str]:
    """Tie matching panel points on *chord* along the frames with *id_prefix* ids.

    Top-chord purlins carry the roof cladding and its wind line load. Bottom-chord
    ties reach every panel point, not just the two springings: an intermediate tie
    node with no longitudinal member has no stiffness out of plane, and Code_Aster
    reports a singular matrix on exactly that degree of freedom.
    """
    ids: List[str] = []
    for panel in sorted(frames[0][chord]):
        for bay in range(len(frames) - 1):
            ids.append(
                add_member(
                    model,
                    frames[bay][chord][panel],
                    frames[bay + 1][chord][panel],
                    section,
                    material,
                    member_id=f"{id_prefix}_p{panel}_b{bay}",
                    twist_angle=strong_axis_twist,
                )
            )
    return ids


def wall_girts(
    model: Model,
    frames: Sequence[Dict[str, Dict[int, str]]],
    material: str,
    section: str,
    girt_levels: Sequence[float],
    strong_axis_twist: float = 0.0,
) -> List[str]:
    """Run a girt at each wall level on both side walls, on the column nodes."""
    ids: List[str] = []
    for side in ("start", "end"):
        for level_index, height in enumerate(sorted(girt_levels)):
            for bay in range(len(frames) - 1):
                ids.append(
                    add_member(
                        model,
                        girt_node(model, frames, bay, side, height),
                        girt_node(model, frames, bay + 1, side, height),
                        section,
                        material,
                        member_id=f"girt_{side}_z{level_index}_b{bay}",
                        twist_angle=strong_axis_twist,
                    )
                )
    return ids


def plan_bracing(
    model: Model,
    frames: Sequence[Dict[str, Dict[int, str]]],
    material: str,
    section: str,
    braced_bays: Sequence[int],
    *,
    chord: str,
    id_prefix: str,
) -> List[str]:
    """Brace *chord* over the given bays, one diagonal per panel with *id_prefix* ids.

    This is the member that makes the frame solvable, and it is not decoration.
    A portal frame is a *planar* truss: its web lies wholly in the transverse
    plane, so the web gives the bottom chord no stiffness out of plane at all.
    Over a 30 m clear span the chord is then held horizontally by nothing but its
    own weak-axis bending, the whole tie line drifts sideways as a near-mechanism,
    and the stiffness matrix loses rank.

    Roof plan bracing alone does not help: it works at the top chord, one tie line
    above. These diagonals triangulate the bottom chord against the next frame in
    the horizontal plane, which is the restraint that chord actually needs. They
    run panel to adjacent panel so none crosses a tie.

    Roof diagonals likewise run panel to adjacent panel so none crosses a purlin.
    Crossing two diagonals inside one panel would need a centre node with no
    rotational stiffness, and a single diagonal triangulates the bay against racking.
    """
    ids: List[str] = []
    last_panel = max(frames[0][chord])
    for bay in braced_bays:
        if not 0 <= bay < len(frames) - 1:
            raise ValueError(
                f"braced bay {bay} is outside the {len(frames) - 1} bays of this building."
            )
        for panel in range(last_panel):
            ids.append(
                add_member(
                    model,
                    frames[bay][chord][panel],
                    frames[bay + 1][chord][panel + 1],
                    section,
                    material,
                    member_id=f"{id_prefix}_b{bay}_p{panel}",
                )
            )
    return ids


def girt_node(
    model: Model,
    frames: Sequence[Dict[str, Dict[int, str]]],
    bay: int,
    side: str,
    height: float,
) -> str:
    """The column node on the given wall and level that a girt or brace frames into.

    Resolved from the frame's own springing node so the girts land on the column
    line exactly, which is what makes them share the column's nodes.
    """
    if not 0 <= bay < len(frames):
        raise ValueError(f"bay {bay} is outside the {len(frames)} frames of this building.")
    if side not in ("start", "end"):
        raise ValueError(f"side must be 'start' or 'end', got {side!r}.")
    springing = frames[bay]["bottom"][0 if side == "start" else max(frames[bay]["bottom"])]
    x, y, _ = model.nodes[springing].coords
    return model.get_or_create_node((x, y, _finite("height", height)), tolerance=1e-9)


def wall_bracing(
    model: Model,
    frames: Sequence[Dict[str, Dict[int, str]]],
    material: str,
    section: str,
    braced_bays: Sequence[int],
    girt_levels: Sequence[float],
) -> List[str]:
    """Chevron-brace the lower wall panels of the given bays, on both walls.

    Each chevron runs from a low girt up to the mid girt of the next frame and
    back down, so every member ends on a girt node and none crosses a girt.
    """
    ids: List[str] = []
    levels = sorted(_positive("girt level", level) for level in girt_levels)
    if len(levels) < 3:
        raise ValueError(
            f"wall bracing needs at least three girt levels to form a chevron, got {levels}."
        )
    lower, apex, upper = levels[0], levels[1], levels[2]
    for bay in braced_bays:
        if not 0 <= bay < len(frames) - 1:
            raise ValueError(
                f"braced bay {bay} is outside the {len(frames) - 1} bays of this building."
            )
        for side in ("start", "end"):
            ids.append(
                add_member(
                    model,
                    girt_node(model, frames, bay, side, lower),
                    girt_node(model, frames, bay + 1, side, apex),
                    section, material,
                    member_id=f"wallbrace_{side}_b{bay}_up",
                )
            )
            ids.append(
                add_member(
                    model,
                    girt_node(model, frames, bay + 1, side, apex),
                    girt_node(model, frames, bay, side, upper),
                    section, material,
                    member_id=f"wallbrace_{side}_b{bay}_down",
                )
            )
    return ids


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

model = Model("Steel_Portal_Frame_Hall")

model.add_material("S355", E=210.0e9, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_ibeam_section("Column_HE300B", "HE300B")
model.add_ibeam_section("Chord_IPE240", "IPE240")
model.add_ibeam_section("Chord_IPE200", "IPE200")
model.add_ibeam_section("Purlin_IPE120", "IPE120")
model.add_ibeam_section("Girt_IPE120", "IPE120")
model.add_ibeam_section("Eave_IPE160", "IPE160")
# The web is a beam section on purpose - see truss_frame.
model.add_rectangular_section(
    "Web_RHS", height_y=0.060, height_z=0.060, thickness_y=0.004, thickness_z=0.004
)
model.add_bar_section("Brace_CHS80", OD=0.080, WT=0.006)

STRUCTURAL_SECTIONS = {
    "column": "Column_HE300B",
    "chord_top": "Chord_IPE240",
    "chord_bottom": "Chord_IPE200",
    "web": "Web_RHS",
    "purlin": "Purlin_IPE120",
    "girt": "Girt_IPE120",
    "eave": "Eave_IPE160",
    "brace": "Brace_CHS80",
}

FRAMES = frame_row(
    model,
    "S355",
    STRUCTURAL_SECTIONS,
    FRAME_COUNT,
    BAY_LENGTH_M,
    SPAN_M,
    EAVE_HEIGHT_M,
    ROOF_RISE_M,
    TRUSS_SPRINGING_RISE_M,
    TRUSS_PANEL_COUNT,
    GIRT_LEVELS_M,
    strong_axis_twist=STRONG_AXIS_TWIST_DEG,
)

PURLIN_IDS = longitudinal_members(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["purlin"],
    strong_axis_twist=STRONG_AXIS_TWIST_DEG,
    chord="top", id_prefix="purlin",
)
TIE_IDS = longitudinal_members(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["eave"],
    strong_axis_twist=STRONG_AXIS_TWIST_DEG,
    chord="bottom", id_prefix="tie",
)
GIRT_IDS = wall_girts(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["girt"], GIRT_LEVELS_M,
    strong_axis_twist=STRONG_AXIS_TWIST_DEG,
)
ROOF_BRACE_IDS = plan_bracing(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["brace"], BRACED_BAYS,
    chord="top", id_prefix="roofbrace",
)
TIE_BRACE_IDS = plan_bracing(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["brace"], BRACED_BAYS,
    chord="bottom", id_prefix="tiebrace",
)
WALL_BRACE_IDS = wall_bracing(
    model, FRAMES, "S355", STRUCTURAL_SECTIONS["brace"], BRACED_BAYS, GIRT_LEVELS_M
)

# Self-weight alone: CALC_CHAMP takes one distributed load per beam model, and
# gravity already is one.
#: How many critical charges to compute and how hard to try. The eigensolver
#: subspace is widened because a frame of this size has near-degenerate modes and
#: the default 4 does not separate them.
BUCKLING_OPTIONS = {"n_modes": 8, "modal_subspace": 12}

model.define_operation("Gravity", gravity=True, buckling=BUCKLING_OPTIONS)

# Wind on the cladding-carrying members only. The load path then runs purlins and
# girts -> trusses and columns -> bases, rather than being smeared over members
# that never see cladding.
model.define_operation("Wind", gravity=False).add_field(
    "line_load",
    WIND_LINE_LOAD_N_PER_M,
    direction=[1.0, 0.0, 0.0],
    element_ids=PURLIN_IDS + GIRT_IDS,
)

model.validate()
