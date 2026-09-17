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
# The pipe centreline sits 0.25 m above the beam nodes (half the IPE140, the shoe and the pipe radius)
# and runs right down the middle of the rack along Y = 0.0.
start = model.add_node((-2.0, 0.0, 3.25))
approach = model.add_node((-1.0, 0.0, 3.25))
on_left = model.add_node((0.0, 0.0, 3.25))
on_right = model.add_node((4.0, 0.0, 3.25))
end = model.add_node((6.0, 0.0, 3.25))
model.add_element(id="pipe_inlet", type="pipe_straight", n1=start, n2=approach, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_approach", type="pipe_straight", n1=approach, n2=on_left, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_rack_span", type="pipe_straight", n1=on_left, n2=on_right, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_outlet", type="pipe_straight", n1=on_right, n2=end, section="DN100", material="Steel", route_id="P-100")

# Ground-connected supports:
model.add_support(start, "anchor")
model.add_support(approach, "guide", direction=[0.0, 1.0, 0.0])
model.add_support(end, "anchor")

# Element-connected supports (rest shoes on the rack beams):
model.add_support(on_left, "rest", attached_to=mid_left, friction_coefficient=0.3)
model.add_support(on_right, "rest", attached_to=mid_right, friction_coefficient=0.3)

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
