"""Parametric 8 m hot-oil line: fixed nozzles, a U loop and grounded rack shoes.

The same supports are used by the solver and the viewer. Rack crossbeams are
ideal rigid ground boundaries; their bounding boxes show their reserved space,
not an elastic rack analysis. All coordinates and lengths are metres.
"""

import math

from tuba import Model

LINE_SPAN_M = 8.0
PIPE_HEIGHT_M = 3.0
BEND_RADIUS_M = 0.25
SHOE_X_M = 1.5
INSULATION_M = 0.05
COLD_C = 20.0
HOT_C = 180.0
PRESSURE_PA = 1.2e6
FLUID_DENSITY_KG_M3 = 800.0
DEFAULT_PARAMETERS = {"width_m": 2.4, "depth_m": 1.8, "guide_layout": "end_guides"}


def build_model(parameters):
    """Build one line. width_m/depth_m size the U; guide_layout adds a middle guide."""
    if set(parameters) != set(DEFAULT_PARAMETERS):
        raise ValueError("Expected width_m, depth_m and guide_layout")
    width, depth = parameters["width_m"], parameters["depth_m"]
    for label, value, low, high in (("width_m", width, 1.6, 2.4), ("depth_m", depth, 0.55, 2.0)):
        if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{label} must be a finite number in [{low}, {high}] m")
    guide_layout = parameters["guide_layout"]
    if guide_layout not in {"end_guides", "mid_guide"}:
        raise ValueError("guide_layout must be end_guides or mid_guide")
    model = Model("Retained hot-line piping search")
    model.add_material("Steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6)
    model.add_pipe_section("DN80", OD=0.0889, WT=0.00549)
    model.add_insulation_spec("HotOil", material="mineral wool", thickness_m=INSULATION_M, density_kg_m3=120.0)
    approach = (LINE_SPAN_M - width) / 2.0
    with model.pipe(section="DN80", material="Steel", route="HotOil") as pipe:
        pipe.start([0.0, 0.0, PIPE_HEIGHT_M], support="anchor")
        pump = pipe.last_node_id
        pipe.run(SHOE_X_M)
        pipe.add_support("custom", blocked_dof=[0, 1, 1, 0, 0, 0])
        pipe.run(approach - BEND_RADIUS_M - SHOE_X_M)
        pipe.bend(radius=BEND_RADIUS_M, angle=90.0, axis=[0.0, 0.0, 1.0])
        pipe.run(depth - 2.0 * BEND_RADIUS_M)
        pipe.bend(radius=BEND_RADIUS_M, angle=-90.0, axis=[0.0, 0.0, 1.0])
        pipe.run((width - 2.0 * BEND_RADIUS_M) / 2.0)
        midpoint = pipe.last_node_id
        if guide_layout == "mid_guide":
            pipe.add_support("guide", direction=[0.0, 1.0, 0.0])
        pipe.run((width - 2.0 * BEND_RADIUS_M) / 2.0)
        pipe.bend(radius=BEND_RADIUS_M, angle=-90.0, axis=[0.0, 0.0, 1.0])
        pipe.run(depth - 2.0 * BEND_RADIUS_M)
        pipe.bend(radius=BEND_RADIUS_M, angle=90.0, axis=[0.0, 0.0, 1.0])
        pipe.run(approach - BEND_RADIUS_M - SHOE_X_M)
        pipe.add_support("custom", blocked_dof=[0, 1, 1, 0, 0, 0])
        pipe.run(SHOE_X_M)
        pipe.end(support="anchor")
        tie_in = pipe.last_node_id
    model.groups["HotOil"] = {"name": "HotOil", "elements": list(pipe.created_element_ids)}
    for name, node in (("PumpDischarge", pump), ("RackTieIn", tie_in), ("LoopMidpoint", midpoint)):
        model.groups[name] = {"name": name, "nodes": [node]}
    model.assign_insulation("group:HotOil", "HotOil")
    for operation, temperature in (("Sustained", COLD_C), ("Hot", HOT_C)):
        op = model.define_operation(operation, gravity=True, pressure=PRESSURE_PA,
                                    temperature=temperature, ref_temperature=COLD_C)
        op.add_field("fluid_density", FLUID_DENSITY_KG_M3, route_id="HotOil")
    model.add_obstacle(id="process_equipment", type="cuboid", min_point=(3.4, -0.45, 2.6), max_point=(4.6, 0.45, 3.4))
    # A narrow tray above the shallow U tests actual operating movement.
    model.add_obstacle(id="cable_tray", type="cuboid", min_point=(3.8, 0.928, 2.8), max_point=(4.2, 1.128, 3.2))
    model.add_obstacle(id="corridor_edge", type="cuboid", min_point=(-0.2, 2.4, 2.5), max_point=(8.2, 2.6, 3.5))
    for number, x in enumerate((SHOE_X_M, LINE_SPAN_M - SHOE_X_M), 1):
        model.add_obstacle(id=f"rigid_rack_crossbeam_{number}", type="cuboid",
                           min_point=(x - 0.1, -0.3, 2.655), max_point=(x + 0.1, 2.1, 2.855))
    if guide_layout == "mid_guide":
        model.add_obstacle(id="rigid_mid_guide_bracket", type="cuboid",
                           min_point=(3.9, depth - 0.1, 2.655), max_point=(4.1, depth + 0.1, 2.855))
    model.groups["Assumptions"] = {"metadata": {"rack_boundary": "rigid ground; elastic rack response omitted",
                    "shoes": "bilateral vertical restraints; friction and lift-off omitted",
                    "nozzles": "both fixed; no equipment flexibility", "compliance": "no piping-standard evaluator configured"}}
    return model


model = build_model(DEFAULT_PARAMETERS)
PUMP_NODE = model.groups["PumpDischarge"]["nodes"][0]
TIE_IN_NODE = model.groups["RackTieIn"]["nodes"][0]
LOOP_NODE = model.groups["LoopMidpoint"]["nodes"][0]
