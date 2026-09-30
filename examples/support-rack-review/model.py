"""Distributed and concentrated loads on one pipe and its frictionless rack shoes.

The attached shoes carry vertical load but slide freely in-plane (mu = 0).
Friction and its load history belong to the separate nonlinear friction example.
"""

from tuba import Model
from tuba.assemblies import assemble

PIPE_LOAD_N_M = 350.0
CROSSBEAM_LOAD_N_M = 500.0
POINT_FORCE_N = 3500.0
POINT_MOMENT_N_M = 500.0

model = Model("SupportRackReview")
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 137e6, 180.0: 120e6},
)
model.add_ibeam_section("RackColumnIPE", "IPE160")
model.add_ibeam_section("RackLongIPE", "IPE140")
model.add_ibeam_section("RackCrossIPE", "IPE100")
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
assemble(
    model,
    "tuba.assemblies:rack_bay",
    name="rack_A",
    origin=(0.0, -1.0, 0.0),
    length=4.0,
    width=2.0,
    height=3.0,
    levels=(3.0,),
    section="RackLongIPE",
    material="Steel",
    zone="north",
    column_section="RackColumnIPE",
    longitudinal_section="RackLongIPE",
    transverse_section="RackCrossIPE",
    shoe_level=3.0,
)

rack = model.groups["rack_A"]
for node_id in rack["nodes"]:
    if abs(float(model.nodes[node_id].coords[2])) < 1e-9:
        model.add_support(node_id, "anchor")

mid_left = rack["metadata"]["attachment_points"]["level_1_mid_left"].split(":", 1)[1]
mid_right = rack["metadata"]["attachment_points"]["level_1_mid_right"].split(":", 1)[1]

# The pipe centreline sits 0.25 m above the beam nodes (half the IPE140, the shoe and
# the pipe radius) and runs right down the middle of the rack along Y = 0.0. The two
# rest shoes hang from the rack's cross-beam midpoints; the guide restrains Y.
with model.pipe(section="DN100", material="Steel", route="P-100") as pipe:
    pipe.start([-2.0, 0.0, 3.25], support="anchor")
    pipe.run(1.0)                     # approach node (-1.0, 0.0, 3.25)
    pipe.add_support("guide", direction=[0.0, 1.0, 0.0])
    pipe.run(1.0)                     # on the rack's left beam (0.0, 0.0, 3.25)
    pipe.add_support("rest", attached_to=mid_left, friction_coefficient=0.0)
    pipe.run(2.0)                     # unsupported span midpoint (2.0, 0.0, 3.25)
    loaded_pipe_node = pipe.last_node_id
    pipe.run(2.0)                     # on the rack's right beam (4.0, 0.0, 3.25)
    pipe.add_support("rest", attached_to=mid_right, friction_coefficient=0.0)
    pipe.run(2.0)                     # outlet node (6.0, 0.0, 3.25)
    pipe.end(support="rest")

# Gravity is deliberately disabled: the pipe line load stands in for its downward
# weight, while the rack's weight is omitted. Combining gravity and FORCE_POUTRE
# on a beam prevents Code_Aster from calculating the requested REAC_NODA field.
op = model.define_operation(
    "Operating",
    gravity=False,
    pressure=1.5e6,
    temperature=180.0,
    ref_temperature=20.0,
)
op.add_field(
    "line_load",
    value=PIPE_LOAD_N_M,
    direction=[0.0, 0.0, -1.0],
    route_id="P-100",
)
# The left crossbeam is split at the shoe attachment. Target both connected
# halves explicitly; the other rack members do not receive this lateral load.
loaded_crossbeam = [
    element.id for element in model.elements
    if element.id in rack["elements"] and element.type == "beam"
    and element.section == "RackCrossIPE" and mid_left in (element.n1, element.n2)
]
op.add_field(
    "line_load",
    value=CROSSBEAM_LOAD_N_M,
    direction=[1.0, 0.0, 0.0],
    element_ids=loaded_crossbeam,
)
op.add_nodal_force(
    loaded_pipe_node,
    force=[0.0, 0.0, -POINT_FORCE_N],
    moment=[0.0, POINT_MOMENT_N_M, 0.0],
)
model.validate()
