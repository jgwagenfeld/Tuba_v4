"""An instrumented water-circuit P&ID and an editable procedural Tuba route.

The fixed loss is downstream of the mechanical outlet anchor, outside this
structural study. Loss coefficients and support limits are demo assumptions.
"""

import math

from tuba import Model
from tuba.process import EquipmentDefinition, Instrument, PidDefinition, SignalConnection
from tuba.process.network import (
    Connection, FixedLossComponent, HydraulicRequirements, MassFlowSource,
    OperatingScenario, PipeComponent, PressureSink, ProcessNetwork,
)

SIZES = {"small": (0.0603, 0.00391), "larger": (0.0889, 0.00549)}
BEND_RADIUS_M = 0.3
STRAIGHT_LEG_M = 2.0


def build_model(parameters):
    """Build one offset water line; allow only declared bore and offset edits."""
    if set(parameters) != {"size", "offset_m"}:
        raise ValueError("Expected exactly size and offset_m")
    if parameters["size"] not in SIZES:
        raise ValueError("size must be small or larger")
    offset = parameters["offset_m"]
    if type(offset) not in (int, float) or not math.isfinite(offset) or not 0.5 <= offset <= 4.0:
        raise ValueError("offset_m must be a finite number from 0.5 to 4.0 m")
    outside_diameter, wall = SIZES[parameters["size"]]
    model = Model("Coupled water line")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850, alpha=1.2e-5)
    model.add_pipe_section("WaterPipe", OD=outside_diameter, WT=wall)
    with model.pipe("WaterPipe", "Steel", route="L-101") as pipe:
        pipe.start([0, 0, 0], support="anchor")
        pipe.run(STRAIGHT_LEG_M)
        for angle, length in [(90, offset), (-90, STRAIGHT_LEG_M),
                              (-90, offset), (90, STRAIGHT_LEG_M)]:
            pipe.bend(radius=BEND_RADIUS_M, angle=angle, plane="XY")
            pipe.run(length)
        pipe.end(support="anchor")
    return model


def process_inputs(model, *, network=None):
    """Bind a supplied or authored graph to the route and explicit demo SI data."""
    if network is None:
        network = ProcessNetwork("WaterCircuit", components=(
            MassFlowSource("SRC-101", "SRC-101.out"),
            PipeComponent("L-101", "L-101.in", "L-101.out", "L-101",
                          roughness_m=4.6e-5, bend_loss_coefficient=0.2,
                          bend_loss_source="Demo assumption: excess zeta per bend"),
            FixedLossComponent("V-101", "V-101.in", "V-101.out",
                               bore_m=model.sections["WaterPipe"].ID,
                               loss_coefficient=5.0, loss_source="Demo downstream restriction",
                               mechanical_domain="external"),
            PressureSink("SNK-101", "SNK-101.in"),
        ), connections=(Connection("SRC-101.out", "L-101.in"),
                        Connection("L-101.out", "V-101.in"),
                        Connection("V-101.out", "SNK-101.in")), pid=PidDefinition(
            equipment=(
                EquipmentDefinition("TK-101", "SRC-101", "tank", "Supply tank; prescribed mass-flow boundary"),
                EquipmentDefinition("TK-102", "SNK-101", "tank", "Receiving tank; prescribed pressure boundary"),
                EquipmentDefinition("FCV-101", "V-101", "control_valve",
                                    "Illustrative K=5 operating point; no valve characteristic or control dynamics"),
            ),
            instruments=(
                Instrument("PT-101", "PT", "L-101.in", "Calculated pipe inlet absolute pressure"),
                Instrument("FT-101", "FT", "L-101.out", "Calculated pipe outlet mass flow"),
                Instrument("FIC-101", "FIC", None, "Declared flow-control loop; not simulated"),
            ),
            signals=(SignalConnection("FT-101", "FIC-101"),
                     SignalConnection("FIC-101", "FCV-101")),
        ))
    scenario = OperatingScenario("WaterOperating", mass_flow_kg_s=10.0,
        source_temperature_k=333.15, sink_pressure_pa=300_000.0,
        external_pressure_pa=101_325.0, mechanical_reference_temperature_k=293.15)
    requirements = HydraulicRequirements("WaterRequirements", max_velocity_m_s=3.0,
        min_delivered_mass_flow_kg_s=10.0, max_source_pressure_pa=600_000.0,
        min_sink_pressure_pa=300_000.0)
    return network.bind(model, scenario, requirements)
