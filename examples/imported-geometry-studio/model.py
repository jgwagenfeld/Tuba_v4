"""Known mixed reference geometry, authored as reusable Python functions.

The STL is inspection/clearance geometry. STEP solids and the authored panel
carry structural stiffness. This example does not reconstruct the old header.
"""

from pathlib import Path

from tuba import Model
from tuba.assemblies import assemble


def solid_part(model, *, name, source, unit_scale_to_m, material, mesh_size, origin, interfaces,
               fixed_interfaces):
    """Import one solid; source selectors are local, origin and mesh size metres."""
    return model.import_step(
        Path(__file__).resolve().parent / source, id=name, material=material,
        unit_scale_to_m=unit_scale_to_m, mesh_size=mesh_size, placement={"origin": origin},
        interfaces=interfaces, fixed_interfaces=fixed_interfaces,
    )


def panel(model, *, name, outline, thickness, material, mesh_size, edge_references):
    """Build one planar panel and attach named end edges to existing references.

    Outline, thickness and mesh size use metres; edge_references maps polygon
    edge indices (string keys) to native reference node ids.
    """
    model.add_shell_panel(name, polygon=outline, thickness=thickness,
                          material=material, mesh_size=mesh_size)
    for edge, reference in edge_references.items():
        model.add_rigid_patch(f"{name}_edge_{edge}", reference=reference,
                              shell=name, edges=[int(edge)])


def frame_member(model, *, name, start, end, section, material):
    """Build one frame member between existing nodes with the supplied properties."""
    model.add_element(id=name, type="beam", n1=start, n2=end,
                      section=section, material=material)


def continuation(model, *, name, port, length, section, material, kind):
    """Continue a confirmed solid port with one pipe or beam of length in metres."""
    if kind not in {"pipe", "beam"} or length <= 0:
        raise ValueError("Expected kind 'pipe' or 'beam' and positive length in metres.")
    interface = model.ports[port]
    with model.pipe(section=section, material=material, route=name) as route:
        route.start(list(interface.position)).set_direction(list(interface.axis))
        route.beam(length) if kind == "beam" else route.run(length)
    element = model.get_element(route.created_element_ids[-1])
    connect = model.connect_beam_to_port if kind == "beam" else model.connect_pipe_to_port
    connect(**{kind: f"element:{element.id}"}, node=f"node:{element.n1}",
            port=f"port:{port}", id=f"{name}_continuity")
    return element.n2


def released_joint(model, *, reference, frame_node, held_dofs):
    """Join two nodes by the held global DOFs; zero entries remain released."""
    model.add_support(reference, "custom", attached_to=frame_node,
                      blocked_dof=held_dofs, attachment_mode="dof_equality")


model = Model("Imported geometry Studio reference")
for name, E, nu, rho in (("Solid", 2.1e11, 0.3, 7850.0),
                         ("Pipe", 1.9e11, 0.3, 7850.0),
                         ("Frame", 2.1e11, 0.3, 7850.0),
                         ("Panel", 7e10, 0.0, 2700.0)):
    model.add_material(name, E=E, nu=nu, rho=rho, alpha=1.2e-5)
model.add_pipe_section("Annulus", OD=0.1, WT=0.01)
model.add_rectangular_section("FrameRHS", height_y=0.06, height_z=0.06,
                              thickness_y=0.006, thickness_z=0.006)

base = model.add_reference_point("base", position=[-0.4, 0, 0])
mount = model.add_reference_point("spool_base", position=[0, 0, 0])
frame_top = model.add_node([-0.01, 0, 0])
assemble(model, "panel", name="panel", outline=[[-0.4, -0.02, 0], [0, -0.02, 0],
         [0, 0.02, 0], [-0.4, 0.02, 0]], thickness=0.008, material="Panel",
         mesh_size=0.02, edge_references={"3": base, "1": mount})
assemble(model, "frame_member", name="frame", start=base, end=frame_top,
         section="FrameRHS", material="Frame")
assemble(model, "released_joint", reference=mount, frame_node=frame_top,
         held_dofs=[1, 1, 0, 1, 1, 1])
model.add_support(base, "anchor")

assemble(model, "solid_part", name="spool", source="geometry/spool.step",
         unit_scale_to_m=1.0, material="Solid", mesh_size=0.015, origin=[0, 0, 0], fixed_interfaces=[],
         interfaces={"outlet": {"position": [0.2, 0, 0], "axis": [1, 0, 0], "radius": 0.05}})
model.add_rigid_patch("spool_mount", reference=mount, component="spool",
                     faces=[{"shape": "annular_face", "position": [0, 0, 0],
                             "axis": [-1, 0, 0], "radius": 0.05, "inner_radius": 0.04}])
pipe_tip = assemble(model, "continuation", name="pipe", port="spool_outlet",
                    length=1.0, section="Annulus", material="Pipe", kind="pipe")

assemble(model, "solid_part", name="beam_spool", source="geometry/spool.step",
         unit_scale_to_m=1.0, material="Solid", mesh_size=0.015, origin=[0, 0.4, 0], fixed_interfaces=["inlet"],
         interfaces={"inlet": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": 0.05},
                     "outlet": {"position": [0.2, 0, 0], "axis": [1, 0, 0], "radius": 0.05}})
beam_tip = assemble(model, "continuation", name="beam", port="beam_spool_outlet",
                    length=0.5, section="FrameRHS", material="Frame", kind="beam")

model.import_stl(Path(__file__).resolve().parent / "geometry/reference.stl",
                 id="enclosure_reference", unit_scale_to_m=0.001,
                 placement={"origin": [0.4, 0.7, 0]})
operating = model.define_load_case("Combined", gravity=False)
operating.add_nodal_force(pipe_tip, force=[1000, 0, 100], moment=[10, 0, 0])
operating.add_nodal_force(beam_tip, force=[0, 0, -50])
