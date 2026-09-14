"""A DN100 line carried across a steel I-beam rack bay, analysed together with the rack."""

from tuba import Model
from tuba.assemblies import RackBay
from tuba.patches import ModelTransaction

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
ModelTransaction(model).apply(
    RackBay(
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
    ).to_patch()
)

rack = model.groups["rack_A"]
for node_id in rack["nodes"]:
    if abs(float(model.nodes[node_id].coords[2])) < 1e-9:
        model.add_support(node_id, "anchor")

left = rack["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
right = rack["metadata"]["attachment_points"]["level_1_right"].split(":", 1)[1]
start = model.add_node((-2.0, -1.0, 3.0))
end = model.add_node((6.0, -1.0, 3.0))
model.add_element(id="pipe_inlet", type="pipe_straight", n1=start, n2=left, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_rack_span", type="pipe_straight", n1=left, n2=right, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_outlet", type="pipe_straight", n1=right, n2=end, section="DN100", material="Steel", route_id="P-100")
model.add_support(start, "anchor")
model.add_support(end, "anchor")
model.add_support(left, "rest")
model.add_support(right, "rest")
model.define_load_case(
    "Operating",
    gravity=True,
    pressure=1.5e6,
    temperature=180.0,
    ref_temperature=20.0,
)
model.validate()
