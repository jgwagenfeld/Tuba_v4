"""Three process lines share one four-bay steel rack and its load path.

Each line has its own diameter, pressure and temperature, one fixed shoe at
mid-run and four sliding friction shoes. The shoes attach to real nodes in
the shared crossbeams; neither the lines nor their loads use separate racks.
The study solves gravity and thermal/pressure loading with Code_Aster.
"""

from dataclasses import replace
from itertools import pairwise
from math import isfinite

from tuba import Model
from tuba.assemblies import RackRow
from tuba.patches import AddElement, AddNode, CreateGroup, ModelTransaction


def rack_with_lanes(model, *, name, bays, bay_length, width, height, lanes,
                    column_section, longitudinal_section, cross_section, material):
    """Build one rack, splitting crossbeams at the lane offsets in metres.

    ``bays`` and ``bay_length`` set its length; ``width`` and ``height`` set
    the cross-frame dimensions. ``lanes`` are ordered offsets inside its width.
    The three sections and material specify its structural members.
    """
    if not lanes or any(not isfinite(y) or not 0 < y < width for y in lanes):
        raise ValueError("lanes must be finite offsets strictly inside the rack width.")
    if any(a >= b for a, b in pairwise(lanes)):
        raise ValueError("lanes must be strictly increasing, with no duplicates.")
    patch = RackRow(
        name_prefix=name, origin=(0.0, 0.0, 0.0), bays=bays,
        bay_length=bay_length, width=width, height=height, levels=(height,),
        section=column_section, column_section=column_section,
        longitudinal_section=longitudinal_section, transverse_section=cross_section,
        material=material, anchor_feet=True,
    ).to_patch()
    operations, splits, attachments = [], {}, {}
    prefix = f"{name}_cross_1_"
    for operation in patch.operations:
        if isinstance(operation, AddElement) and operation.local_id.startswith(prefix):
            station = int(operation.local_id.removeprefix(prefix))
            mids = [f"{name}_lane_{station}_{lane}" for lane in range(len(lanes))]
            attachments[operation.local_id] = mids
            operations.extend(AddNode(node, (station * bay_length, y, height))
                              for node, y in zip(mids, lanes))
            ends = [operation.n1, *mids, operation.n2]
            pieces = [replace(operation, local_id=f"{operation.local_id}_{i}", n1=a, n2=b)
                      for i, (a, b) in enumerate(pairwise(ends))]
            splits[operation.local_id] = [piece.local_id for piece in pieces]
            operations.extend(pieces)
        else:
            operations.append(operation)
    for index, operation in enumerate(operations):
        if isinstance(operation, CreateGroup):
            mids = [node for member in operation.elements for node in attachments.get(member, ())]
            operations[index] = replace(
                operation,
                nodes=[*operation.nodes, *mids],
                elements=[piece for member in operation.elements for piece in splits.get(member, [member])],
                metadata={**operation.metadata,
                          "attachment_points": {node: f"node:{node}" for node in mids}},
            )
    ModelTransaction(model).apply(replace(patch, operations=operations), validate=True)


def pipe_on_rack(model, *, route, section, material, y, height, offset,
                 bays, bay_length, anchor_station, friction):
    """Build a line on rack shoes, returning its station nodes in run order.

    ``route``, ``section`` and ``material`` identify the line; ``y`` locates
    its lane, ``height`` the rack beam, and ``offset`` the pipe centre above it.
    ``bays`` and ``bay_length`` match the rack. ``anchor_station`` is the sole
    fixed shoe; ``friction`` is the coefficient on every other sliding shoe.
    """
    if anchor_station not in range(bays + 1):
        raise ValueError(f"anchor_station must be between 0 and {bays}.")
    stations = []
    with model.pipe(section=section, material=material, route=route) as pipe:
        pipe.start([0.0, y, height + offset])
        stations.append(pipe.last_node_id)
        for _ in range(bays):
            pipe.run(bay_length)
            stations.append(pipe.last_node_id)
    for station, node in enumerate(stations):
        attachment = model.find_node_by_point([station * bay_length, y, height])
        if attachment is None:
            raise ValueError(f"No rack attachment at station {station}, lane {y}.")
        if station == anchor_station:
            model.add_support(node, "anchor", attached_to=attachment)
        else:
            model.add_support(node, "rest", attached_to=attachment, friction_coefficient=friction)
    return stations


BAYS = 4
BAY_LENGTH = 4.0
RACK_WIDTH = 3.6
RACK_HEIGHT = 4.5
ANCHOR_STATION = 2
FRICTION = 0.3
# Route, section, OD [m], wall [m], lane [m], temperature [C], pressure [Pa].
LINES = (
    ("P-100", "DN100", 0.1143, 0.00602, 0.9, 100.0, 1.0e6),
    ("P-200", "DN150", 0.1683, 0.00711, 1.8, 200.0, 2.0e6),
    ("P-300", "DN200", 0.2191, 0.00818, 2.7, 300.0, 3.0e6),
)

model = Model("MultipipeRack", standard="ASME B31.3")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5,
                   allowable_stress={20.0: 137e6, 100.0: 130e6, 200.0: 115e6, 300.0: 100e6})
model.add_ibeam_section("RackColumn", "IPE200")
model.add_ibeam_section("RackLong", "IPE180")
model.add_ibeam_section("RackCross", "IPE160")
rack_with_lanes(
    model, name="rack", bays=BAYS, bay_length=BAY_LENGTH, width=RACK_WIDTH,
    height=RACK_HEIGHT, lanes=[line[4] for line in LINES],
    column_section="RackColumn", longitudinal_section="RackLong",
    cross_section="RackCross", material="Steel",
)

station_nodes = {}
for route, section, od, wall, y, temperature, pressure in LINES:
    model.add_pipe_section(section, OD=od, WT=wall)
    # IPE160 half-depth + fabricated shoe height + pipe radius [m].
    station_nodes[route] = pipe_on_rack(
        model, route=route, section=section, material="Steel", y=y,
        height=RACK_HEIGHT, offset=0.08 + 0.12 + od / 2,
        bays=BAYS, bay_length=BAY_LENGTH, anchor_station=ANCHOR_STATION,
        friction=FRICTION,
    )

operation = model.define_operation("Operating", gravity=True, temperature=40.0, ref_temperature=20.0)
for route, section, od, wall, y, temperature, pressure in LINES:
    operation.add_field("temperature", temperature, route_id=route)
    operation.add_field("pressure", pressure, route_id=route)
model.validate()
