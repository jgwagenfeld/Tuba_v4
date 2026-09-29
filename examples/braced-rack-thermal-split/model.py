"""A 4-bay braced steel pipe rack carrying one hot DN250 line on shoes.

The single-bay ``support-rack-review`` proves the attached friction shoe: one
shoe, one cross beam, one pipe node. This case asks the question a real
piperack asks instead: what happens when the anchor, the shoes, the bracing and
the line all sit on a frame that is itself hot and free to move?

Named for the thermal split rather than for its geometry, and it carries one
line on purpose - see "The single line" below. The rack is multi-bay; the
project used to be called ``multibay-rack-review``, which read as a rack of
many lines and is exactly what a reader saw on opening it.

Scale and thermal intent
------------------------
24 m of four 6 m bays, two beam levels, shoes on the top level, X-braced in both
end bays. A 400 C line runs the mid-width of the rack; the steel is warmed to
120 C by radiation and sun, so the structure grows too, but four times less than
the pipe. The pipe therefore wants to grow far more along the rack than the rack
under it does, and the shoes are the only thing arbitrating between the two.

Restraint layout
----------------
Station 2, mid-run, is the anchor, tied to the rack, so the rack carries the
anchor force instead of the ground. Every other station is a one-way friction
rest (mu = 0.3) on the frame midpoint, and both approaches carry a ground guide
plus a ground rest. The line therefore has a single longitudinal fixed point at
the anchor and can slide at every shoe.

That is the right arrangement for a hot line on a rack: one fixed point near the
middle, expansion directed both ways, and the friction shoes carrying the drag
into the frame. The line and the rack happen to share a thermal centre near
mid-run, so the design is close to self-balancing.

The single line
---------------
One pipe, and that is the design rather than a simplification. The question this
case answers is a two-body one: the line grows at roughly four times the rate of
the steel under it, and the friction shoes arbitrate between the two. Add a
second line at a different temperature and there are three growth rates
competing for the same shoes, and the property asserted above - that the line and
the rack share a thermal centre near mid-run - stops being checkable, because it
would no longer be a statement about a line.

A rack carrying several lines is a legitimate and common case, and it deserves
its own example rather than being folded in here.

What this case deliberately leaves out
--------------------------------------
Two things a real rack needs are not expressible yet, and both were found by
building this case:

**No wind load.** Code_Aster computes ``CALC_CHAMP/FORCE='REAC_NODA'`` for a
beam modelisation from its distributed loads and refuses it when a
modelisation carries more than one ("votre chargement contient plus d'une
charge repartie"). Self weight plus any ``FORCE_POUTRE`` load, including the
``VENT`` that a wind field compiles to, therefore cannot be solved at all, and
Tuba emits that ``FORCE='REAC_NODA'`` unconditionally
(``tuba/solver/aster_comm.py``). The insulation weight below is carried as
point loads to stay inside the limit. See :func:`add_uniform_line_weight`.

**No guide shoes.** The two end stations of a real run would carry guide shoes:
a lateral guide and a one-way friction rest on the same node, restrained across
the rack and under it but free along it. ``tuba/solver/aster_contact.py`` refuses
a ``rest`` that shares its node with any support other than another ``rest`` or
a ``spring``, so that combination cannot be stated. The end stations here are
plain friction rests, and the line's lateral restraint comes from the two
approach guides plus shoe friction.
"""

from __future__ import annotations

import numpy as np

from tuba import Model
from tuba.assemblies import RackRow
from tuba.patches import ModelTransaction
from tuba.sections import SectionCatalog

# --- Rack geometry [m] --------------------------------------------------------
BAYS = 4
BAY_LENGTH = 6.0
RACK_WIDTH = 2.4
RACK_HEIGHT = 5.5
LOWER_LEVEL = 3.0
RACK_LEVELS = (LOWER_LEVEL, RACK_HEIGHT)
SHOE_LEVEL = RACK_HEIGHT
# A 24 m rack needs longitudinal bracing, and it goes in the end bays so the
# middle stays clear. Each braced bay gets a full-height X on both frame lines.
BRACED_BAYS = (0, BAYS - 1)

# --- The line ----------------------------------------------------------------
PIPE_SECTION = "DN250"
PIPE_OD = 0.2731
PIPE_ROUTE = "P-100"
# Half the transverse beam, the fabricated shoe, and the pipe radius: the
# distance from a cross-beam midpoint node up to the pipe centreline.
SHOE_HEIGHT = 0.10
TRANSVERSE_SECTION = "RackCrossIPE"
BRACE_SECTION = "RackBraceIPE"
PIPE_OFFSET = (
    SectionCatalog.default().get_ibeam_profile("IPE200").properties["H"] / 2.0
    + SHOE_HEIGHT
    + PIPE_OD / 2.0
)

# Approach runs clear of the frame at each end, plus one ground guide per end
# that keeps the overhanging line laterally aligned.
APPROACH_LENGTH = 3.0
GUIDE_LEAD = 1.0

# --- Restraints --------------------------------------------------------------
FRICTION = 0.3
# The fixed point sits at mid-run so the line expands both ways instead of
# sliding one long way, which is what keeps shoe travel inside a guide's range.
# The two end stations would carry guide shoes in a real run; a rest cannot share
# a node with a guide today, so they are plain sliding rests here. See the
# module docstring.
ANCHOR_STATION = BAYS // 2

# --- Thermal and pressure ----------------------------------------------------
AMBIENT_C = 40.0
STEEL_REF_C = 20.0
PIPE_C = 400.0
RACK_STEEL_C = 120.0
DESIGN_PRESSURE_PA = 4.0e6
# Insulation and walkway weight on the hot line [N/m].
INSULATION_LOAD = 450.0


def shoe_attachment_nodes(model, row_name_prefix):
    """Map each station to the cross-beam midpoint node its shoes attach to.

    Reads the midpoint references the row recorded on its own bay groups, so the
    caller never has to know the row's node naming.
    """
    nodes = {}
    for name, group in model.groups.items():
        if not name.startswith(row_name_prefix):
            continue
        for point_name, node_ref in group.get("metadata", {}).get("attachment_points", {}).items():
            if point_name.startswith("mid_"):
                nodes[int(point_name.removeprefix("mid_"))] = node_ref.split(":", 1)[1]
    return nodes


def frame_node(model, point, label="rack frame node"):
    """Return the existing node at *point*, so a member lands on real geometry.

    :meth:`TubaModel.add_node` always creates a new node, so bracing has to
    resolve its own endpoints or it would hang off duplicate unconnected nodes.
    """
    node_id = model.find_node_by_point(np.asarray(point, dtype=float))
    if node_id is None:
        raise ValueError(f"No {label} at {tuple(float(v) for v in point)}.")
    return node_id


def braced_end_bays(
    model,
    *,
    bays=BAYS,
    bay_length=BAY_LENGTH,
    rack_width=RACK_WIDTH,
    levels=RACK_LEVELS,
    height=RACK_HEIGHT,
    braced_bays=BRACED_BAYS,
    section=BRACE_SECTION,
    material="Steel",
):
    """X-brace each end bay, panel by panel, on both frame lines.

    A rack row long enough to be unbraced is not a buildable rack: the frame
    lines carry all the sway. ``braced_bays`` names the bays to brace, and each
    is braced in every panel between consecutive beam levels rather than as one
    full-height X, because a single diagonal from the base to the top level
    passes straight through the intermediate beam without framing into it.

    Each panel's two diagonals meet at a node at the panel centre, so the X is
    four members framing into a shared gusseted point rather than two members
    crossing without connection. That is how the detail is built, and it is also
    what lets the brace transfer force across the crossing instead of passing
    through it.

    Brace endpoints are resolved against the row's existing nodes, so every
    diagonal frames into a column or beam end rather than floating beside it.

    Returns the ids of the brace elements it added.
    """
    added: list[str] = []
    for bay in braced_bays:
        if bay not in range(bays):
            raise ValueError(f"Braced bay {bay!r} is outside 0..{bays - 1}.")
        near = bay * bay_length
        far = (bay + 1) * bay_length
        for across in (0.0, rack_width):
            for panel, (low, high) in enumerate(zip(levels, levels[1:])):
                corners = [
                    frame_node(model, (near, across, low)),
                    frame_node(model, (far, across, low)),
                    frame_node(model, (near, across, high)),
                    frame_node(model, (far, across, high)),
                ]
                centre = model.add_node([(near + far) / 2.0, across, (low + high) / 2.0])
                for leg, corner in enumerate(corners):
                    length = float(
                        np.linalg.norm(model.nodes[corner].coords - model.nodes[centre].coords)
                    )
                    if length <= 1e-9:
                        raise ValueError(
                            f"Brace in bay {bay} panel {panel} leg {leg} has zero length."
                        )
                    added.append(
                        model.add_element(
                            id=f"brace_{bay}_{int(across)}_{panel}_{leg}",
                            type="beam",
                            n1=corner,
                            n2=centre,
                            section=section,
                            material=material,
                        ).id
                    )
    return added


def route_tributary_lengths(model, route_id):
    """Map each node on a straight route to the length of pipe it carries.

    An interior node carries half the element before it plus half the element
    after it; each end carries half its single element. Returns a node id to
    length mapping in route order.
    """
    elements = [e for e in model.elements if e.route_id == route_id]
    if not elements:
        raise ValueError(f"Route {route_id!r} has no elements.")
    for element in elements:
        if element.type != "pipe_straight":
            raise ValueError(
                f"Tributary lengths need a straight route; element {element.id!r} is "
                f"{element.type!r}."
            )

    def length(element):
        start = np.asarray(model.nodes[element.n1].coords, dtype=float)
        end = np.asarray(model.nodes[element.n2].coords, dtype=float)
        return float(np.linalg.norm(end - start))

    lengths = [length(element) for element in elements]
    order = [elements[0].n1] + [element.n2 for element in elements]
    tributary: dict[str, float] = {order[0]: lengths[0] / 2.0}
    for index in range(1, len(elements)):
        tributary[order[index]] = lengths[index - 1] / 2.0 + lengths[index] / 2.0
    tributary[order[-1]] = lengths[-1] / 2.0
    return tributary


def add_uniform_line_weight(model, operation, route_id, value, direction=(0.0, 0.0, -1.0)):
    """Apply a uniform line weight on a route as point loads at its nodes.

    The insulation and walkway load is carried as point loads rather than an
    ``AFFE_CHAR_MECA/FORCE_POUTRE`` line load. Code_Aster computes
    ``CALC_CHAMP/FORCE='REAC_NODA'`` for a beam modelisation from its
    distributed loads, and it refuses that when a modelisation carries more than
    one: a model with both self weight and a line load fails with
    "votre chargement contient plus d'une charge repartie". The same refusal
    applies to a ``wind`` field, which compiles to ``FORCE_POUTRE`` with
    ``TYPE_CHARGE='VENT'``, so a rack that needs wind cannot be solved until the
    writer stops asking for that reaction field unconditionally. Concentrating
    the line weight at the route nodes, each taking its tributary length, keeps
    the same load path and keeps the reaction field available.
    """
    if not direction or not any(float(component) for component in direction):
        raise ValueError("A line weight needs a non-zero direction.")
    unit = np.asarray([float(component) for component in direction], dtype=float)
    unit /= np.linalg.norm(unit)
    for node_id, carried in route_tributary_lengths(model, route_id).items():
        force = [float(value * carried * component) for component in unit]
        operation.add_nodal_force(node_id, force)


def shoed_line_on_rack(
    model,
    *,
    bays=BAYS,
    bay_length=BAY_LENGTH,
    rack_width=RACK_WIDTH,
    rack_height=RACK_HEIGHT,
    levels=RACK_LEVELS,
    shoe_level=SHOE_LEVEL,
    direction="X",
    column_section="RackColumnIPE",
    longitudinal_section="RackLongIPE",
    transverse_section=TRANSVERSE_SECTION,
    brace_section=BRACE_SECTION,
    braced_bays=BRACED_BAYS,
    material="Steel",
    section=PIPE_SECTION,
    route=PIPE_ROUTE,
    shoe_offset=PIPE_OFFSET,
    approach_length=APPROACH_LENGTH,
    guide_lead=GUIDE_LEAD,
    anchor_station=ANCHOR_STATION,
    friction=FRICTION,
    zone="braced_rack",
    name_prefix="rack",
):
    """Build a braced multi-bay rack row and run one line along it on rack shoes.

    ``bays`` cross frames of ``bay_length`` are generated as one continuous
    frame marching along ``direction``, so the row is ``bays * bay_length`` long.
    The line is centred on the rack's width axis, ``shoe_offset`` above
    ``shoe_level``, and puts a node at every station so the frame can carry a
    shoe there.

    Every station except ``anchor_station`` takes a one-way friction rest on the
    frame midpoint at that station. ``anchor_station`` takes a fixed shoe tied
    to that midpoint, so the rack carries the anchor force. Both ends of the
    line run out to a ground rest, with a ground guide on each approach, so the
    line has a single longitudinal fixed point at the anchor.

    Returns the pipe node id at each station, station 0 first, so a caller can
    label or inspect the shoes.
    """
    if direction not in ("X", "Y"):
        raise ValueError(f'direction must be "X" or "Y", got {direction!r}.')
    if bays < 1:
        raise ValueError("A rack row needs at least one bay.")
    if anchor_station not in range(bays + 1):
        raise ValueError(f"anchor_station {anchor_station!r} is outside 0..{bays}.")
    slidable = [station for station in range(bays + 1) if station != anchor_station]

    # The line runs along the row axis, offset half a rack width across it, and
    # the ground guides restrain the one lateral axis that is left.
    if direction == "X":
        lateral, run_axis = 1, 0
    else:
        lateral, run_axis = 0, 1

    def point(along: float, level: float):
        coords = [0.0, 0.0, level]
        coords[run_axis] = along
        coords[lateral] = rack_width / 2.0
        return coords

    guide_direction = [1.0 if index == lateral else 0.0 for index in range(3)]

    stations: list[str] = []
    with model.pipe(section=section, material=material, route=route) as line:
        # Each approach: a ground rest at the far end and a ground guide that
        # aligns the overhanging line before it reaches the frame.
        line.start(point(-approach_length, shoe_level + shoe_offset), support="rest")
        line.run(guide_lead)
        line.add_support("guide", direction=guide_direction)
        line.run(approach_length - guide_lead)
        stations.append(line.last_node_id)
        # One node per further station, at each bay length.
        for _ in range(bays):
            line.run(bay_length)
            stations.append(line.last_node_id)
        line.run(guide_lead)
        line.add_support("guide", direction=guide_direction)
        line.run(approach_length - guide_lead)
        line.end(support="rest")

    row = RackRow(
        name_prefix=name_prefix,
        origin=(0.0, 0.0, 0.0),
        material=material,
        section=column_section,
        direction=direction,
        bays=bays,
        bay_length=bay_length,
        width=rack_width,
        height=rack_height,
        levels=levels,
        shoe_level=shoe_level,
        column_section=column_section,
        longitudinal_section=longitudinal_section,
        transverse_section=transverse_section,
        # The anchor carries its own restraint, so the row emits only the
        # sliding friction rests.
        shoes=tuple((stations[station], station) for station in slidable),
        anchor_feet=True,
        friction_coefficient=friction,
        zone=zone,
    )
    ModelTransaction(model).apply(row.to_patch(), validate=True)

    mid_nodes = shoe_attachment_nodes(model, name_prefix)
    # The anchor is tied to the frame, so the rack carries the anchor force.
    model.add_support(
        stations[anchor_station], "anchor", attached_to=mid_nodes[anchor_station]
    )

    braced_end_bays(
        model,
        bays=bays,
        bay_length=bay_length,
        rack_width=rack_width,
        levels=sorted({0.0, rack_height, *levels}),
        braced_bays=braced_bays,
        section=brace_section,
        material=material,
    )
    model.validate()
    return stations, bays * bay_length


model = Model("BracedRackThermalSplit", standard="ASME B31.3")
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 137e6, 120.0: 120e6, 400.0: 88e6},
)
model.add_ibeam_section("RackColumnIPE", "IPE400")
model.add_ibeam_section("RackLongIPE", "IPE300")
model.add_ibeam_section(TRANSVERSE_SECTION, "IPE200")
model.add_ibeam_section(BRACE_SECTION, "IPE160")
model.add_pipe_section(PIPE_SECTION, OD=PIPE_OD, WT=0.0071)

station_nodes, rack_run_length = shoed_line_on_rack(model)

# One operating case for the whole assembly. The load case temperature is the
# rack's own steel temperature and reaches every group; the hotter line
# overrides it on the route.
op = model.define_operation(
    "Operating",
    gravity=True,
    pressure=DESIGN_PRESSURE_PA,
    temperature=RACK_STEEL_C,
    ref_temperature=STEEL_REF_C,
)
op.add_field("temperature", PIPE_C, route_id=PIPE_ROUTE)

# Insulation and walkway weight on the hot run. See add_uniform_line_weight for
# why this is point loads rather than a FORCE_POUTRE line load, and why there is
# no wind field on this case.
add_uniform_line_weight(model, op, PIPE_ROUTE, INSULATION_LOAD, direction=[0.0, 0.0, -1.0])
model.validate()
