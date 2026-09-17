"""A welding tee: header, branch and one anchor, for 3D solid and mesh reviews."""

from tuba import Model
from tuba.assemblies import assemble

model = Model("PipeTeeVolumeReview")
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    allowable_stress={20.0: 137.0e6},
)
model.add_pipe_section("Header", OD=0.1, WT=0.01)


def tee_junction(model, section="Header", material="Steel", arm=0.08):
    """Build the 3D solid welding tee and return its ``(hub, left, right, branch)`` nodes.

    One hub at the origin with a header arm each way and a branch, all *arm* metres
    long, registered as a welding tee. This is the solid junction Gmsh meshes; the
    caller runs the 1D extensions out of the returned nodes.
    """
    hub = model.add_node([0.0, 0.0, 0.0])
    left = model.add_node([-arm, 0.0, 0.0])
    right = model.add_node([arm, 0.0, 0.0])
    branch = model.add_node([0.0, arm, 0.0])
    model.add_element(id="header_left", type="pipe_straight", n1=hub, n2=left, section=section, material=material)
    model.add_element(id="header_right", type="pipe_straight", n1=hub, n2=right, section=section, material=material)
    model.add_element(id="branch", type="pipe_straight", n1=hub, n2=branch, section=section, material=material)
    model.define_tee(hub, type="welding_tee")
    return hub, left, right, branch


# 3D solid tee junction (meshed with Gmsh as HEXA20 solids):
junction, left, right, branch = assemble(model, "tee_junction")

# 1D pipe extensions (solved as TUYAU_3M beam elements, kinematically coupled to the 3D solid):
outer_left = model.add_node([-0.2, 0.0, 0.0])
outer_right = model.add_node([0.2, 0.0, 0.0])
outer_branch = model.add_node([0.0, 0.2, 0.0])
model.add_element(id="line_left", type="pipe_straight", n1=left, n2=outer_left, section="Header", material="Steel")
model.add_element(id="line_right", type="pipe_straight", n1=right, n2=outer_right, section="Header", material="Steel")
model.add_element(id="line_branch", type="pipe_straight", n1=branch, n2=outer_branch, section="Header", material="Steel")

# Anchor on the outer 1D pipe run:
model.add_support(outer_left, type="anchor")
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
model.validate()
