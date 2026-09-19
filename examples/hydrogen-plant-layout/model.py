"""Green Hydrogen Production & Storage Facility — Authored Procedural Layout.

An industrial plant model featuring:
1. Five process buildings and storage vessels (Electrolyzer Hall, Compressor Station,
   Purification & DeOxo Building, HP Hydrogen Storage Bullets, Substation/Control Room)
   modelled as analytical obstacles for clash detection and reviewable scene visualization.
2. A 4-bay central structural steel pipe rack bridge (RackRow assembly with IPE200/180/140
   profiles, anchored footings, and friction shoe supports at cross-beam midpoints).
3. Primary Low-Pressure Hydrogen process line (DN150 SCH40, P265GH) running from the
   Electrolyzer Hall over the roadway onto the pipe rack, supported on friction shoes,
   and delivering raw H2 to the Purification & DeOxo unit.
4. High-Pressure Hydrogen header (DN80 SCH80, SS316L) connecting the Compressor Station
   to the High-Pressure Storage Vessel yard with a 3D thermal expansion loop.
5. Operating load case with internal pressure, operating temperature, and self-weight.
"""

from tuba import Model
from tuba.assemblies import assemble

# -----------------------------------------------------------------------------
# 1. Project Engineering Parameters & Standards
# -----------------------------------------------------------------------------
RACK_ORIGIN_X = 0.0
RACK_ORIGIN_Y = -1.25     # Rack spans Y = -1.25 to +1.25 (centerline at Y = 0.0)
RACK_WIDTH = 2.5          # Clear width between column centers [m]
RACK_BAYS = 4             # 4 bays across the main process corridor
BAY_LENGTH = 4.0          # 4.0 m modular bay spacing [m]
RACK_BEAM_LEVEL = 5.25    # Top-of-steel elevation for clearance [m]
SHOE_OFFSET = 0.25        # Distance from beam centerline to pipe centerline [m]
PIPE_CENTERLINE_Z = RACK_BEAM_LEVEL + SHOE_OFFSET  # 5.50 m elevated pipe level

model = Model("Hydrogen Plant Layout", standard="ASME B31.3")

# -----------------------------------------------------------------------------
# 2. Materials & Cross-Sections
# -----------------------------------------------------------------------------
# P265GH carbon steel for low-pressure hydrogen header
model.add_material(
    "P265GH",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 170.0e6, 100.0: 160.0e6, 200.0: 140.0e6},
)

# Austenitic Stainless Steel 316L for high-pressure hydrogen lines (H2 embrittlement resistant)
model.add_material(
    "SS316L",
    E=1.95e11,
    nu=0.3,
    rho=8000.0,
    alpha=1.6e-5,
    allowable_stress={20.0: 167.0e6, 100.0: 145.0e6, 200.0: 125.0e6},
)

# Structural steel for pipe rack framing
model.add_material("StructuralSteel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)

# Process Piping Cross-Sections
model.add_pipe_section("DN150_SCH40", OD=0.1683, WT=0.00711)  # 6" LP Hydrogen line
model.add_pipe_section("DN80_SCH80", OD=0.0889, WT=0.00762)   # 3" HP Hydrogen line

# European Standard Structural I-Beam Profiles
model.add_ibeam_section("IPE200", profile_name="IPE200")  # Columns
model.add_ibeam_section("IPE180", profile_name="IPE180")  # Longitudinal stringers
model.add_ibeam_section("IPE140", profile_name="IPE140")  # Transverse cross beams

# -----------------------------------------------------------------------------
# 3. Plant Buildings, Equipment & Storage Vessels (Analytical Obstacles)
# -----------------------------------------------------------------------------
# Electrolyzer Generation Hall (PEM / Alkaline modular stacks)
model.add_obstacle(
    id="electrolyzer_building",
    type="cuboid",
    min_point=[-24.0, -8.0, 0.0],
    max_point=[-6.0, 8.0, 6.5],
)

# Multi-Stage Reciprocating Compressor Station
model.add_obstacle(
    id="compressor_station",
    type="cuboid",
    min_point=[10.0, -20.0, 0.0],
    max_point=[22.0, -8.0, 6.5],
)

# Hydrogen Purification & DeOxo / Adsorption Drying Unit
model.add_obstacle(
    id="purification_building",
    type="cuboid",
    min_point=[8.0, 8.0, 0.0],
    max_point=[20.0, 16.0, 6.0],
)

# High-Pressure Hydrogen Buffer Storage Vessels (Horizontal Bullets)
model.add_obstacle(
    id="h2_storage_bullet_1",
    type="cylinder",
    min_point=[34.0, -5.0, 0.0],
    max_point=[46.0, -1.5, 3.5],
)
model.add_obstacle(
    id="h2_storage_bullet_2",
    type="cylinder",
    min_point=[34.0, 1.5, 0.0],
    max_point=[46.0, 5.0, 3.5],
)

# Electrical Substation & Central Control Center
model.add_obstacle(
    id="substation_control_room",
    type="cuboid",
    min_point=[-24.0, 10.0, 0.0],
    max_point=[-10.0, 18.0, 4.5],
)

# -----------------------------------------------------------------------------
# 4. Procedural Piping Routing: Low-Pressure Hydrogen (LP-H2)
# -----------------------------------------------------------------------------
# From Electrolyzer Hall nozzle -> vertical riser -> overhead rack -> Purification unit
rack_shoes = []
with model.pipe(section="DN150_SCH40", material="P265GH", route="LP_H2") as p:
    # Nozzle connection at Electrolyzer Hall face (anchor boundary)
    p.start([-5.0, 0.0, 1.5], support="anchor")
    p.run(4.0)                                    # Ground run towards rack (to X = -1.0)
    p.bend(radius=0.5, angle=90.0, plane="XZ")    # Bend vertically up
    p.run(3.0)                                    # Vertical riser
    p.bend(radius=0.5, angle=90.0, plane="XZ")    # Bend into +X overhead span
    rack_shoes.append((p.last_node_id, 0))        # Station 0 (X = 0.0, Y = 0.0, Z = 5.50)

    # 4 bays across the main pipe rack along X
    for station in range(1, RACK_BAYS + 1):
        p.run(BAY_LENGTH)                         # Stations 1..4 (X = 4.0, 8.0, 12.0, 16.0)
        rack_shoes.append((p.last_node_id, station))

    # Turn North (+Y) at rack end towards the Purification & DeOxo unit
    p.bend(radius=0.5, angle=90.0, plane="XY")    # Turn North
    p.run(4.5)                                    # Run to Y = 5.0
    p.bend_by_orientation(radius=0.5, angle=-90.0, axis=[1.0, 0.0, 0.0])   # Bend vertically down
    p.run(3.0)                                    # Vertical drop
    p.bend_by_orientation(radius=0.5, angle=90.0, axis=[1.0, 0.0, 0.0])   # Bend into +Y (north)
    p.run(1.0)                                    # 1 m stub short of the Purification face
    p.end(support="anchor")

# -----------------------------------------------------------------------------
# 5. Procedural Piping Routing: High-Pressure Hydrogen (HP-H2)
# -----------------------------------------------------------------------------
# From Compressor discharge -> 3D expansion loop -> Storage Bullet Yard manifold
with model.pipe(section="DN80_SCH80", material="SS316L", route="HP_H2") as p:
    # Compressor discharge nozzle on northern utility face (anchor boundary)
    p.start([14.0, -6.5, 1.5], support="anchor")
    p.run(4.0)                                    # Ground approach run East towards storage corridor

    # 3D Thermal Expansion Loop to absorb thermal and high-pressure expansion.
    # Both loop turns keep +X travel: up, 3 m East, down, on. A "XZ" bend axis
    # is cross(direction, up), so its sign flips with the incoming heading -
    # the paired +90/+90/-90/-90 sequence is load-bearing, not cosmetic.
    p.bend(radius=0.4, angle=90.0, plane="XZ")    # Loop riser (up to Z = 3.8)
    p.run(1.5)                                    # Elevation step
    p.bend(radius=0.4, angle=90.0, plane="XZ")    # Level out, continue East
    p.run(3.0)                                    # Span to absorb thermal strain
    p.bend(radius=0.4, angle=-90.0, plane="XZ")   # Loop drop
    p.run(1.5)
    p.bend(radius=0.4, angle=-90.0, plane="XZ")   # Return to run elevation, East

    p.run(6.0)                                    # Route East towards storage yard
    p.bend(radius=0.4, angle=90.0, plane="XY")    # Turn North towards storage bullet manifold
    p.run(2.45)                                   # Approach bullet 1 centreline (Y = -3.25)
    p.bend(radius=0.4, angle=-90.0, plane="XY")   # Turn East into manifold nozzle
    p.run(3.6)                                    # Stop 1.0 m off the bullet 1 face (X = 33.0)
    p.end(support="anchor")

# -----------------------------------------------------------------------------
# 6. Central Structural Pipe Rack Assembly (RackRow)
# -----------------------------------------------------------------------------
# One assemble() call is the retained recipe: the rack's parameters stay editable, and
# a generated model script replays this call instead of unrolling its records.
assemble(
    model,
    "tuba.assemblies:rack_row",
    name_prefix="main_rack",
    origin=(RACK_ORIGIN_X, RACK_ORIGIN_Y, 0.0),
    material="StructuralSteel",
    section="IPE180",
    column_section="IPE200",
    longitudinal_section="IPE180",
    transverse_section="IPE140",
    direction="X",
    bays=RACK_BAYS,
    bay_length=BAY_LENGTH,
    width=RACK_WIDTH,
    height=RACK_BEAM_LEVEL,
    levels=(RACK_BEAM_LEVEL,),
    shoe_level=RACK_BEAM_LEVEL,
    shoes=tuple(rack_shoes),
    anchor_feet=True,
    friction_coefficient=0.3,
    zone="process_corridor",
)

# -----------------------------------------------------------------------------
# 7. Operating Load Case (Pressure + Temperature + Gravity)
# -----------------------------------------------------------------------------
model.define_load_case(
    "Operating",
    pressure=3.0e6,           # 3.0 MPa design operating pressure
    temperature=65.0,         # 65 °C process temperature (thermal expansion)
    ref_temperature=20.0,     # 20 °C ambient reference temperature
    gravity=True,             # Standard self-weight
)

# Final model structural validation
model.validate()
