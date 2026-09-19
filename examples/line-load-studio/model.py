"""Tuba Studio Live Project: Piping system with line loads and point loads."""

from tuba import Model

model = Model("LineLoadStudioProject")

# Materials & Sections
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 137e6, 150.0: 127e6},
)
model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
model.add_ibeam_section("IPE140", profile_name="IPE140")

# 1. Structural Rack Crossbeam (underneath the pipe at Z=2.8m)
with model.pipe(section="IPE140", material="Steel", route="SupportBeam") as builder:
    builder.start([2.5, -1.0, 2.8], support="anchor")
    builder.set_direction([0.0, 1.0, 0.0])
    builder.beam(1.0)
    beam_rest_node = builder.last_node_id               # Midpoint node directly under pipe
    builder.beam(1.0)
    builder.end(support="anchor")

# 2. Main Piping Route (with rest support attached to the beam)
with model.pipe(section="DN100", material="Steel", route="MainLine") as builder:
    builder.start([0.0, 0.0, 3.0], support="anchor")
    builder.run(2.5)                                    # Run to the support location
    builder.add_support("rest", attached_to=beam_rest_node, friction_coefficient=0.3)
    builder.run(2.5)                                    # Run to elbow inlet
    elbow_node = builder.last_node_id
    builder.bend(radius=0.3, angle=90.0, plane="XY")    # 90° elbow turning to +Y
    builder.run(3.0)                                    # 4m straight run
    builder.end(support="anchor")

# 3. Operating Scenario with Distributed and Point Loads
# (gravity=False: the downward line load represents self-weight/ice; Code_Aster permits one distributed load field per beam in CALC_CHAMP)
op = model.define_operation("Operating", gravity=False, pressure=1.2e6, temperature=150.0)

# Distributed line load along the entire piping route (e.g. ice + cladding: 350 N/m downwards)
op.add_field(
    "line_load",
    value=350.0,
    direction=[0.0, 0.0, -1.0],
    route_id="MainLine",
)

# Distributed lateral wind load along the transverse beam (500 N/m)
op.add_field(
    "line_load",
    value=500.0,
    direction=[1.0, 0.0, 0.0],
    route_id="SupportBeam",
)

# Concentrated point force (3.5 kN downwards) + moment (500 N·m) at the elbow corner
op.add_nodal_force(
    node=elbow_node,
    force=[0.0, 0.0, -3500.0],
    moment=[0.0, 500.0, 0.0],
)

model.validate()
