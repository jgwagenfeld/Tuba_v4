"""Street-crossing pipe rack bridge — authored procedurally.

An ASME B31.3 piping system on ground sleepers that rises to cross
an 8-meter roadway over a 4-bay overhead structural steel pipe rack bridge,
supported by midpoint friction shoe rests, then drops back to ground elevation.
"""

from tuba import Model
from tuba.assemblies import RackRow
from tuba.patches import ModelTransaction

# -----------------------------------------------------------------------------
# 1. Project Parameters & Standards
# -----------------------------------------------------------------------------
ROAD_WIDTH = 8.0          # 8.0 m clear roadway
SLEEPER_ELEVATION = 0.5   # Ground pipe centerline [m]
BRIDGE_CLEARANCE = 5.5    # Overhead bridge pipe centerline [m]
RACK_BEAM_LEVEL = 5.25    # Overhead steel beam top level [m] (0.25 m shoe offset)
PIPE_Y_CENTER = 1.0       # Centerline of rack bay width [m]

model = Model("Street Rack Bridge", standard="ASME B31.3")

# -----------------------------------------------------------------------------
# 2. Materials & Cross Sections
# -----------------------------------------------------------------------------
model.add_material(
    "P265GH",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 170.0e6, 100.0: 160.0e6, 200.0: 140.0e6},
)
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)

# DN150 (6") Process Piping
model.add_pipe_section("DN150_SCH40", OD=0.1683, WT=0.00711)

# Structural I-Beams (European Standard Profiles)
model.add_ibeam_section("IPE160", profile_name="IPE160")
model.add_ibeam_section("IPE100", profile_name="IPE100")

# -----------------------------------------------------------------------------
# 3. Procedural Piping Route (Ground -> Riser -> Bridge -> Drop -> Ground)
# -----------------------------------------------------------------------------
bridge_station_nodes = []  # one pipe node per rack station, at x = 0, 3, 6, 9, 12
with model.pipe(section="DN150_SCH40", material="P265GH") as p:
    # West ground approach on sleepers
    p.start([-4.0, PIPE_Y_CENTER, SLEEPER_ELEVATION], support="anchor")
    p.run(3.0)                                    # approach run to x=-1.0
    p.bend(radius=0.5, angle=90.0, plane="XZ")    # bend vertically up
    p.run(BRIDGE_CLEARANCE - SLEEPER_ELEVATION - 1.0) # vertical riser
    p.bend(radius=0.5, angle=90.0, plane="XZ")    # bend into +X overhead span
    bridge_station_nodes.append(p.last_node_id)   # station 0 (x=0.0)

    # Overhead bridge span (4 bays of 3.0 m across the 8 m road)
    for _ in range(4):
        p.run(3.0)                                # stations 1-4 (x=3.0, 6.0, 9.0, 12.0)
        bridge_station_nodes.append(p.last_node_id)

    # East vertical drop back to ground sleepers
    p.bend(radius=0.5, angle=-90.0, plane="XZ")   # bend vertically down
    p.run(BRIDGE_CLEARANCE - SLEEPER_ELEVATION - 1.0) # vertical drop
    p.bend(radius=0.5, angle=-90.0, plane="XZ")   # bend into +X ground run
    p.run(3.0)                                    # run to x=16.0
    p.end(support="anchor")

# -----------------------------------------------------------------------------
# 4. Structural Steel Pipe Rack Bridge (RackRow Assembly)
# -----------------------------------------------------------------------------
# Hang each rack station's pipe node from the shoe at that station.
bridge_shoes = tuple((nid, station) for station, nid in enumerate(bridge_station_nodes))

# 4-bay structural rack bridge with friction shoe supports
rack = RackRow(
    name_prefix="bridge_rack",
    origin=(0.0, 0.0, 0.0),
    material="Steel",
    section="IPE160",
    column_section="IPE160",
    longitudinal_section="IPE160",
    transverse_section="IPE100",
    direction="X",
    bays=4,
    bay_length=3.0,
    width=2.0,
    height=RACK_BEAM_LEVEL,
    levels=(RACK_BEAM_LEVEL,),
    shoe_level=RACK_BEAM_LEVEL,
    shoes=bridge_shoes,
    anchor_feet=True,
    friction_coefficient=0.3,
    zone="street_crossing",
)

ModelTransaction(model).apply(rack.to_patch(), validate=True)

# -----------------------------------------------------------------------------
# 5. Operating & Environmental Load Cases
# -----------------------------------------------------------------------------
model.define_load_case(
    "Operating",
    pressure=2.0e6,           # 2.0 MPa design pressure
    temperature=150.0,        # 150 °C operating temperature (thermal expansion)
    gravity=-9.81,            # Standard self-weight
)
