"""Demonstration of distributed line loads authoring and 3D visualization.

This example builds a piping system with straight runs, an elbow, and a supporting
crossbeam, imposes distributed line loads along routes and members, and exports a
reviewable web-scene bundle.
"""

from pathlib import Path

from tuba import Model
from tuba.visualization import build_visualization_scene, write_scene_bundle


def main() -> Path:
    # 1. Initialize model
    model = Model(project_name="LineLoadVisualizationDemo")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100_Sch40", OD=0.1143, WT=0.006)
    model.add_ibeam_section("IPE140", profile_name="IPE140")

    # 2. Build a structural rack member underneath the pipe at Z=2.8m
    with model.pipe(section="IPE140", material="Steel", route="B-100") as builder:
        builder.start([2.5, -1.0, 2.8], support="anchor")
        builder.set_direction([0.0, 1.0, 0.0])
        builder.beam(1.0)
        beam_rest_node = builder.last_node_id               # Midpoint node directly under pipe
        builder.beam(1.0)
        builder.end(support="anchor")

    # 3. Build piping route with an attached rest support and elbow
    with model.pipe(section="DN100_Sch40", material="Steel", route="P-100") as builder:
        builder.start([0.0, 0.0, 3.0], support="anchor")
        builder.run(2.5)                                    # Run to the support location
        builder.add_support("rest", attached_to=beam_rest_node, friction_coefficient=0.3)
        builder.run(2.5)                                    # Run to elbow inlet
        elbow_node = builder.last_node_id
        builder.bend(radius=0.3, angle=90.0, plane="XY")    # 90° bend turning into +Y
        builder.run(4.0)                                    # 4 m run along +Y
        builder.end(support="anchor")

    # 4. Impose distributed line loads in an Operating scenario
    # (gravity=False: line load represents gravity/ice; Code_Aster CALC_CHAMP allows one distributed load field per beam)
    operating = model.define_operation("Operating", gravity=False, pressure=1.2e6, temperature=150.0)

    # Global downward line load on the pipe route (e.g. ice / insulation weight)
    operating.add_field(
        "line_load",
        value=350.0,                 # N/m
        direction=[0.0, 0.0, -1.0],  # Downward (-Z)
        route_id="P-100",
    )

    # Localized lateral wind / equipment load on the structural beam
    operating.add_field(
        "line_load",
        value=500.0,                 # N/m
        direction=[1.0, 0.0, 0.0],   # Lateral (+X)
        route_id="B-100",
    )

    # Concentrated point force at elbow corner node (e.g. valve weight / trunnion load)
    operating.add_nodal_force(
        node=elbow_node,
        force=[0.0, 0.0, -3500.0],   # 3.5 kN downward point force
        moment=[0.0, 500.0, 0.0],
    )

    # 5. Build visualization scene & write bundle
    scene = build_visualization_scene(model)
    scene.validate()

    out_dir = Path(".build/line-load-demo-scene").resolve()
    bundle = write_scene_bundle(scene, out_dir, source=__file__)
    print(f"Exported line load visualization bundle to: {out_dir}")
    print(f"Objects in scene: {len(scene.objects)}")
    line_load_objects = [o for o in scene.objects if o.kind == "applied_load" and o.metadata.get("vector_kind") == "line_load"]
    print(f"Line load comb glyphs: {len(line_load_objects)}")
    return out_dir


if __name__ == "__main__":
    main()
