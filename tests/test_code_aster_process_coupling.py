"""Gated real hydraulic backend -> Tuba loads -> Code_Aster qualification.

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
    Connection, FixedLossComponent, HydraulicRequirements, MassFlowSource, OperatingScenario,
    PipeComponent, PressureSink, ProcessNetwork,
)
from tuba.process.structural import WALL_TEMPERATURE_MODEL, apply_fluid_loads

PANDAPIPES_GATE = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_PANDAPIPES_INTEGRATION") != "1",
    reason="set TUBA_RUN_PANDAPIPES_INTEGRATION=1 to run real pandapipes and Code_Aster",
)


@pytest.mark.parametrize("backend_name", [
    pytest.param("OpenModelica", marks=pytest.mark.skipif(
        os.environ.get("TUBA_RUN_PROCESS_INTEGRATION") != "1",
        reason="set TUBA_RUN_PROCESS_INTEGRATION=1 to run real OpenModelica and Code_Aster",
    )),
    pytest.param("pandapipes", marks=PANDAPIPES_GATE),
])
def test_real_fluid_loads_match_native_operation_and_cantilever_weight(tmp_path, backend_name):
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
    if backend_name == "pandapipes":
        from tuba.process.pandapipes import PandapipesBackend
        backend = PandapipesBackend()
    else:
        backend = OpenModelicaBackend()
    hydraulics = backend.solve(bound, tmp_path / "hydraulics")
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
        "hydraulic_backend": backend_name,
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


@PANDAPIPES_GATE
@pytest.mark.parametrize("start_height,bend_angle", [(125.0, 90.0), (-25.0, -90.0)],
                         ids=["rising", "falling"])
def test_real_pandapipes_matches_independent_colebrook_losses_and_elevation(tmp_path, start_height, bend_angle):
    from tuba.process.pandapipes import PandapipesBackend

    model = Model("Independent pandapipes hydraulic qualification")
    model.add_material("Steel", E=210e9, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    with model.pipe("Pipe", "Steel", route="L-101") as pipe:
        pipe.start([0, 0, start_height])
        pipe.run(2.0)
        pipe.bend(radius=0.3, angle=bend_angle, plane="XZ")
        pipe.run(2.0)
    components = (
        MassFlowSource("SRC", "SRC.out"),
        PipeComponent("L-101", "L-101.in", "L-101.out", "L-101", 4.6e-5, 0.2,
                      "Qualification assumption: one excess bend K=0.2"),
        FixedLossComponent("V-101", "V-101.in", "V-101.out", 0.08, 5.0,
                           "Qualification assumption: external valve K=5"),
        PressureSink("SNK", "SNK.in"),
    )
    network = ProcessNetwork("IndependentWater", components, tuple(
        Connection(before.outlet_port, after.inlet_port) for before, after in zip(components, components[1:])
    ))
    scenario = OperatingScenario("water", 10.0, 333.15, 300_000.0, 101_325.0, 293.15)
    requirements = HydraulicRequirements("qualification", 3.0, 10.0, 600_000.0, 300_000.0)
    bound = network.bind(model, scenario, requirements)
    hydraulics = PandapipesBackend().solve(bound, tmp_path / "hydraulics")
    hydraulics.verify_for(bound)

    # MSL ConstantPropertyLiquidWater constants; the independent reference uses pp's gravity=9.81.
    density, viscosity, gravity = 995.586, 0.001, 9.81
    expected_drop, comparisons = 0.0, []
    for segment, measured in zip(bound.segments, hydraulics.segments, strict=True):
        area = math.pi * segment.bore_m**2 / 4
        velocity = scenario.mass_flow_kg_s / (density * area)
        reynolds = density * velocity * segment.bore_m / viscosity
        assert reynolds > 4000
        if segment.length_m:
            # Bisection in 1/sqrt(lambda) is independent of pp's Newton iteration in lambda.
            lower, upper = 1.0, 100.0
            for _ in range(80):
                inverse_root = (lower + upper) / 2
                residual = inverse_root + 2 * math.log10(
                    segment.roughness_m / (3.71 * segment.bore_m) + 2.51 * inverse_root / reynolds
                )
                if residual > 0:
                    upper = inverse_root
                else:
                    lower = inverse_root
            assert abs(residual) < 1e-12
            friction_factor = inverse_root**-2
        else:
            friction_factor = 0.0
        distributed = friction_factor * segment.length_m / segment.bore_m * density * velocity**2 / 2
        local = segment.local_loss_coefficient * density * velocity**2 / 2
        elevation = density * gravity * segment.height_change_m
        drop = distributed + local + elevation
        observed = measured.pressure_in_pa - measured.pressure_out_pa
        assert observed == pytest.approx(drop, rel=1e-6, abs=1e-4)
        assert measured.mass_flow_kg_s == pytest.approx(scenario.mass_flow_kg_s, rel=1e-8)
        assert measured.velocity_m_s == pytest.approx(velocity, rel=1e-8)
        assert measured.temperature_k == pytest.approx(scenario.source_temperature_k, abs=1e-8)
        assert measured.density_kg_m3 == pytest.approx(density, abs=1e-8)
        assert measured.dynamic_viscosity_pa_s == pytest.approx(viscosity, abs=1e-12)
        expected_drop += drop
        comparisons.append({"segment_id": segment.segment_id, "reynolds": reynolds,
                            "friction_factor": friction_factor, "distributed_loss_pa": distributed,
                            "declared_local_loss_pa": local, "elevation_pa": elevation,
                            "expected_pressure_drop_pa": drop, "observed_pressure_drop_pa": observed})
    assert sum(segment.local_loss_coefficient for segment in bound.segments) == pytest.approx(5.2)
    assert hydraulics.sink_pressure_pa == pytest.approx(scenario.sink_pressure_pa, abs=1e-4)
    assert hydraulics.source_pressure_pa == pytest.approx(scenario.sink_pressure_pa + expected_drop,
                                                         rel=1e-8, abs=1e-4)
    receipt = {
        "scope": "real turbulent pandapipes vs independent Colebrook+K+elevation; no structural qualification",
        "hydraulic_manifest": hydraulics.manifest_path,
        "reference": "Colebrook roughness denominator 3.71, density 995.586 kg/m3, viscosity 0.001 Pa.s, gravity 9.81 m/s2",
        "modelica_difference": "MSL StaticPipe uses gravity 9.80665 m/s2 and inverse Detailed Colebrook roughness term 0.27*(epsilon/D)",
        "source_pressure_pa": hydraulics.source_pressure_pa,
        "sink_pressure_pa": hydraulics.sink_pressure_pa,
        "expected_total_pressure_drop_pa": expected_drop,
        "segments": comparisons,
    }
    (tmp_path / "qualification.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
