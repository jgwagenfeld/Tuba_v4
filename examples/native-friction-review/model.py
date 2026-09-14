"""Two identical pipes on sliding shoes, without and with friction, sharing one load path.

Friction is set per support. There are two copies so that one Code_Aster run can show
the same pipe with mu = 0 and mu = 0.3 side by side; each copy links to the line that
adds it.
"""

from tuba import Model
from tuba.model import BendGeometry

model = Model("Native piping friction comparison")
model.add_material("steel", E=2e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("pipe", OD=0.1143, WT=0.006)
for name, temperature in [("Cold", 20.0), ("Hot", 120.0), ("Lift", 20.0)]:
    model.define_load_case(name, gravity=True, pressure=0.0, temperature=temperature, ref_temperature=20.0)


def add_copy(prefix: str, y_offset: float, mu: float) -> None:
    """One independently supported copy of the qualified horizontal pipe."""
    points = [[x, y + y_offset, z] for x, y, z in ([0, 0, 0], [2, 0, 0], [4, 0, 0], [4.3, 0.3, 0], [4.3, 1.8, 0], [4.3, 3.3, 0])]
    nodes = [model.add_node(point) for point in points]
    for i in (0, 1, 3, 4):
        model.add_element(id=f"{prefix}_pipe_{i}", type="pipe_straight", n1=nodes[i], n2=nodes[i + 1], section="pipe", material="steel")
    model.add_element(id=f"{prefix}_elbow", type="pipe_bend", n1=nodes[2], n2=nodes[3], section="pipe", material="steel",
                      bend_radius=0.3, bend_angle=90,
                      bend_geometry=BendGeometry(center=[4, 0.3 + y_offset, 0], normal=[0, 0, 1], radius=0.3, angle=90,
                                                 start_tangent=[1, 0, 0], end_tangent=[0, 1, 0]))
    model.add_support(node=nodes[0], type="anchor", id=f"{prefix}_anchor")
    for name, node in [("S1", nodes[1]), ("S2", nodes[4])]:
        model.add_support(node=node, type="rest", id=f"{prefix}_{name}", direction=[0.0, 0.0, 1.0], friction_coefficient=mu,
                          normal_stiffness=1e10, tangential_stiffness=1e8)
    for name in ("Cold", "Hot", "Lift"):
        case = model.load_cases[name]
        case.add_nodal_force(nodes[1], force=[0.0, 0.0, -10000.0])
        case.add_nodal_force(nodes[4], force=[0.0, 0.0, 600.0 if name == "Lift" else -10000.0])


add_copy("NF", 0.0, mu=0.0)
add_copy("F", 5.0, mu=0.3)
