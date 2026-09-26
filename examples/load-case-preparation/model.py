"""Two elastic lines, local operating fields, and four Code_Aster solved states."""

from tuba import Model
from tuba.sampling import field_from_route_table

PRESSURE_PA = 1.5e6
COLD_C = 20.0
HOT_C = 150.0
RETURN_INLET_C = 80.0
RETURN_OUTLET_C = 40.0
RETURN_PRESSURE_PA = 0.4e6
OCCASIONAL_FORCE_N = 500.0
LEG_LENGTH_M = 3.0
BEND_RADIUS_M = 0.3
LINE_SPACING_M = 5.0

model = Model("Load-case preparation")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)

# Separate lines: the pressure difference is not an unexplained jump in a
# connected pipe. Both use fixed anchors; no contact/friction changes by case.
for route, offset in (("ProcessLine", 0.0), ("ReturnLine", LINE_SPACING_M)):
    with model.pipe(section="DN100", material="Steel", route=route) as pipe:
        pipe.start([0.0, offset, 0.0], support="anchor")
        pipe.run(LEG_LENGTH_M)
        if route == "ProcessLine":
            occasional_node = pipe.last_node_id
        pipe.bend(radius=BEND_RADIUS_M, angle=90.0, plane="XY")
        pipe.run(LEG_LENGTH_M)
        pipe.bend(radius=BEND_RADIUS_M, angle=90.0, plane="XZ")
        pipe.run(LEG_LENGTH_M)
        pipe.end(support="anchor")
    model.groups[route] = {"name": route, "elements": list(pipe.created_element_ids)}
    if route == "ReturnLine":
        return_length = pipe.station

model.define_operation("Sustained", gravity=True, pressure=PRESSURE_PA,
                       temperature=COLD_C, ref_temperature=COLD_C)
hot = model.define_operation("OperatingHot", gravity=True, pressure=PRESSURE_PA,
                             temperature=COLD_C, ref_temperature=COLD_C)
# A temperature field can target individual elements, a named group, or a route.
# Here every selected process element receives 150 C; the case default is 20 C.
hot.add_field("temperature", HOT_C, element_ids=model.groups["ProcessLine"]["elements"])
# Cooling along the return: sampled node temperatures interpolate through bends
# and solver subdivisions. Do not overlap node and element temperature fields.
field_from_route_table(model, hot, "temperature", "ReturnLine",
                       [(0.0, RETURN_INLET_C), (return_length, RETURN_OUTLET_C)])
occasional = model.define_operation("Occasional", gravity=True, pressure=PRESSURE_PA,
                                    temperature=COLD_C, ref_temperature=COLD_C)
# Illustrative static lateral event, not a wind/seismic code load generator.
occasional.add_nodal_force(occasional_node, [0.0, OCCASIONAL_FORCE_N, 0.0])
model.define_operation("PressureOnly", gravity=False, pressure=PRESSURE_PA,
                       temperature=COLD_C, ref_temperature=COLD_C)
# Pressure zones are independent of temperature zones. Unselected pipe elements
# retain the case default (15 bar); the return group uses 4 bar in all four cases.
for operation in model.operations.values():
    operation.add_field("pressure", RETURN_PRESSURE_PA, group="ReturnLine")
model.validate()
