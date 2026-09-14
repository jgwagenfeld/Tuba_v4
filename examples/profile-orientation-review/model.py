"""Three identical IPE100 cantilevers rolled 0, 45 and 90 degrees, loaded in global and local axes."""

from tuba import Model
from tuba.geometry.section_mesh import beam_local_frame

ROLLS = (0, 45, 90)
LENGTH = 3.0
FORCE = 500.0

model = Model("I-section orientation: global and local loading")
model.add_material("steel", E=2e11, nu=0.3, rho=7850, alpha=1.2e-5)
model.add_ibeam_section("IPE100", "IPE100")
global_case = model.define_load_case("global", gravity=False)
local_case = model.define_load_case("local", gravity=False)
for index, roll in enumerate(ROLLS):
    nodes = [model.add_node([station * LENGTH / 12, index * 1.2, 0]) for station in range(13)]
    for station in range(12):
        model.add_element(id=f"roll{roll}_{station}", type="beam", n1=nodes[station], n2=nodes[station + 1],
                          section="IPE100", material="steel", twist_angle=roll)
    model.add_support(id=f"anchor{roll}", node=nodes[0], type="anchor")
    global_case.add_nodal_force(nodes[-1], [0, 0, -FORCE])
    _, _, local_z = beam_local_frame([0, 0, 0], [1, 0, 0], twist_angle_deg=roll)
    # Author forces to 1e-10 N: libm's last bit differs across Windows/Linux.
    local_case.add_nodal_force(nodes[-1], [round(float(value), 10) for value in -FORCE * local_z])
