"""A welding tee: header, branch and one anchor, for 3D solid and mesh reviews."""

from tuba import Model

model = Model("PipeTeeVolumeReview")
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    allowable_stress={20.0: 137.0e6},
)
model.add_pipe_section("Header", OD=0.1, WT=0.01)
junction = model.add_node([0.0, 0.0, 0.0])
left = model.add_node([-0.08, 0.0, 0.0])
right = model.add_node([0.08, 0.0, 0.0])
branch = model.add_node([0.0, 0.08, 0.0])
model.add_element(id="header_left", type="pipe_straight", n1=junction, n2=left, section="Header", material="Steel")
model.add_element(id="header_right", type="pipe_straight", n1=junction, n2=right, section="Header", material="Steel")
model.add_element(id="branch", type="pipe_straight", n1=junction, n2=branch, section="Header", material="Steel")
model.define_tee(junction, type="welding_tee")
model.add_support(left, type="anchor")
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
model.validate()
