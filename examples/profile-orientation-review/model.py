"""Three identical IPE100 cantilevers rolled 0, 45 and 90 degrees, each loaded by the same 500 N force.

The force is the only thing the members share besides their section: it is applied
in global -Z at every tip, so the difference in response is the section orientation
alone. Solving one case keeps the comparison single-sourced.
"""

from tuba import Model

ROLLS = (0, 45, 90)
LENGTH = 3.0
FORCE = 500.0

model = Model("I-section orientation: the same tip force at 0, 45 and 90 degrees")
model.add_material("steel", E=2e11, nu=0.3, rho=7850, alpha=1.2e-5)
model.add_ibeam_section("IPE100", "IPE100")
case = model.define_load_case("global", gravity=False)
for index, roll in enumerate(ROLLS):
    nodes = [model.add_node([station * LENGTH / 12, index * 1.2, 0]) for station in range(13)]
    for station in range(12):
        model.add_element(id=f"roll{roll}_{station}", type="beam", n1=nodes[station], n2=nodes[station + 1],
                          section="IPE100", material="steel", twist_angle=roll)
    model.add_support(id=f"anchor{roll}", node=nodes[0], type="anchor")
    case.add_nodal_force(nodes[-1], [0, 0, -FORCE])
