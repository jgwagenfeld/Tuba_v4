"""A DN100 line resting on friction shoes on a steel I-beam rack bay, analysed together with the rack."""

from tuba import Model
from tuba.assemblies import assemble

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
    pipe.add_support("rest", attached_to=mid_left, friction_coefficient=0.3)
    pipe.run(4.0)                     # on the rack's right beam (4.0, 0.0, 3.25)
    pipe.add_support("rest", attached_to=mid_right, friction_coefficient=0.3)
    pipe.run(2.0)                     # outlet node (6.0, 0.0, 3.25)
    pipe.end(support="anchor")

# Operating condition with thermal expansion, pressure, and distributed line load:
op = model.define_operation(
    "Operating",
    gravity=False,
    pressure=1.5e6,
    temperature=180.0,
    ref_temperature=20.0,
)
op.add_field(
    "line_load",
    value=350.0,
    direction=[0.0, 0.0, -1.0],
    route_id="P-100",
)
model.validate()
