"""Gated real OpenModelica -> Tuba loads -> Code_Aster qualification.

This verifies steady pressure/temperature/filled-contents transfer, not momentum
loads, vibration, pressure-collapse or comprehensive flow-induced stresses.
Outputs must remain in an external pytest temporary directory.
"""

import json
import math
import os

import numpy as np
import pytest

from tuba import Model
from tuba.process.modelica import OpenModelicaBackend
from tuba.process.network import (
    Connection, HydraulicRequirements, MassFlowSource, OperatingScenario,
    PipeComponent, PressureSink, ProcessNetwork,
)
from tuba.process.structural import WALL_TEMPERATURE_MODEL, apply_fluid_loads

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_PROCESS_INTEGRATION") != "1",
    reason="set TUBA_RUN_PROCESS_INTEGRATION=1 to run real OpenModelica and Code_Aster",
)


def test_real_fluid_loads_match_native_operation_and_cantilever_weight(tmp_path):
    length, outside_diameter, wall = 3.0, 0.1, 0.01
    steel_density, alpha = 7850.0, 1.2e-5
    model = Model("Real fluid-load cantilever qualification")
    model.add_material("Steel", E=210e9, nu=0.3, rho=steel_density, alpha=alpha)
    model.add_pipe_section("Pipe", OD=outside_diameter, WT=wall)
    with model.pipe("Pipe", "Steel", route="L-101") as pipe:
        pipe.start([0, 0, 0], support="anchor")
        pipe.run(length)
    element = model.elements[0]
    network = ProcessNetwork("WaterCantilever", (
        MassFlowSource("SRC", "SRC.out"),
        PipeComponent("L-101", "L-101.in", "L-101.out", "L-101", 4.6e-5, 0.0, "Straight-pipe qualification: no bends or excess local losses"),
        PressureSink("SNK", "SNK.in"),
    ), (Connection("SRC.out", "L-101.in"), Connection("L-101.out", "SNK.in")))
    scenario = OperatingScenario("water", 10.0, 333.15, 300_000.0, 101_325.0, 293.15)
    requirements = HydraulicRequirements("qualification", 3.0, 10.0, 600_000.0, 300_000.0)
    bound = network.bind(model, scenario, requirements)
    hydraulics = OpenModelicaBackend().solve(bound, tmp_path / "hydraulics")
    hydraulics.verify_for(bound)
    fluid = hydraulics.segments[0]
    mapping = apply_fluid_loads(
        model, bound, hydraulics, operation_name="Mapped",
        wall_temperature_model=WALL_TEMPERATURE_MODEL,
    )
    (tmp_path / "mapping.json").write_text(json.dumps(mapping.evidence, indent=2), encoding="utf-8")
    exec_method = os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto")
    mapped = model.solve(operation="Mapped", pipe_modelization="TUYAU_3M",
                         work_dir=str(tmp_path / "mapped"), exec_method=exec_method)
    mapped.validate_for_publication(model)

    bore = outside_diameter - 2 * wall
    area_metal = math.pi / 4 * (outside_diameter**2 - bore**2)
    area_bore = math.pi / 4 * bore**2
    line_weight = (steel_density * area_metal + fluid.density_kg_m3 * area_bore) * 9.81
    support_reaction = sum((np.asarray(mapped.results.node_results[support.node].reaction_force)
                            for support in model.supports), start=np.zeros(6))
    assert support_reaction[2] == pytest.approx(line_weight * length, rel=1e-5, abs=1e-6)
    assert support_reaction[4] == pytest.approx(-line_weight * length**2 / 2, rel=1e-5, abs=1e-6)

    pressure = (fluid.pressure_in_pa + fluid.pressure_out_pa) / 2 - scenario.external_pressure_pa
    reference = model.define_operation("NativeReference", gravity=True, pressure=pressure,
                                       temperature=60.0, ref_temperature=20.0)
    reference.add_field("fluid_density", fluid.density_kg_m3)
    native = model.solve(operation=reference.name, pipe_modelization="TUYAU_3M",
                         work_dir=str(tmp_path / "native-reference"), exec_method=exec_method)
    native.validate_for_publication(model)
    for node_id in model.nodes:
        mapped_node, native_node = mapped.results.node_results[node_id], native.results.node_results[node_id]
        np.testing.assert_allclose(mapped_node.displacement, native_node.displacement, rtol=1e-5, atol=1e-10)
        if mapped_node.reaction_force is None:
            assert native_node.reaction_force is None
        else:
            assert native_node.reaction_force is not None
            np.testing.assert_allclose(mapped_node.reaction_force, native_node.reaction_force, rtol=1e-5, atol=1e-5)

    model.define_operation("ThermalOnly", gravity=False, pressure=0, temperature=60, ref_temperature=20)
    thermal = model.solve(operation="ThermalOnly", pipe_modelization="TUYAU_3M",
                          work_dir=str(tmp_path / "thermal-reference"), exec_method=exec_method)
    thermal.validate_for_publication(model)
    thermal_dx = thermal.results.node_results[element.n2].displacement[0]
    assert thermal_dx == pytest.approx(alpha * 40 * length, rel=1e-4, abs=1e-10)
    receipt = {
        "scope": "real steady pressure/temperature/filled-contents load transfer",
        "hydraulic_manifest": hydraulics.manifest_path,
        "mapped_operation": mapping.operation.name,
        "pressure_differential_pa": pressure,
        "fluid_density_kg_m3": fluid.density_kg_m3,
        "expected_support_vertical_n": line_weight * length,
        "observed_support_vertical_n": float(support_reaction[2]),
        "expected_support_moment_y_nm": -line_weight * length**2 / 2,
        "observed_support_moment_y_nm": float(support_reaction[4]),
        "expected_thermal_expansion_m": alpha * 40 * length,
        "observed_thermal_expansion_m": thermal_dx,
        "native_operation_comparison": "all original-node displacement and reaction components matched",
    }
    (tmp_path / "qualification.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
