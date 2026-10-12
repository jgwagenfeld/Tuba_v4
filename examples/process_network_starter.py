"""Small Tuba-route -> OpenModelica experiment, incomplete for engineering use.

This prototype supplies a P&ID-like connection graph directly. It evaluates
single-phase steady hydraulics with real OpenModelica, but does not evaluate
structural loads, stresses, reactions, or acceptance. Those require the later
Code_Aster mapping/solve stage. Valve and bend losses are illustrative inputs.
Generated models, logs, and results must be written outside the source checkout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from tuba import Model
from tuba.physical import element_length


MODELICA_VERSION = "4.1.0"


@dataclass(frozen=True)
class StarterDesign:
    """SI inputs for one water line; loss coefficients are demo assumptions."""

    outside_diameter_m: float = 0.0889
    wall_thickness_m: float = 0.00549
    offset_m: float = 1.0
    straight_leg_m: float = 2.0
    bend_radius_m: float = 0.3
    roughness_m: float = 4.6e-5
    mass_flow_kg_s: float = 10.0
    source_temperature_k: float = 293.15
    sink_pressure_pa: float = 300_000.0
    valve_zeta: float = 5.0
    bend_zeta_each: float = 0.2
    max_velocity_m_s: float = 3.0
    max_source_pressure_pa: float = 600_000.0

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field.name} must be a finite positive number")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field.name} must be a finite positive number")
        if self.outside_diameter_m <= 2 * self.wall_thickness_m:
            raise ValueError("outside_diameter_m must exceed twice wall_thickness_m")
        if self.max_source_pressure_pa <= self.sink_pressure_pa:
            raise ValueError("max_source_pressure_pa must exceed sink_pressure_pa")


def build_model(design: StarterDesign) -> Model:
    """Author an offset line with fixed endpoints; changing offset adds length."""
    model = Model("Water process-network starter: structural solve pending")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850, alpha=1.2e-5)
    model.add_pipe_section("WaterPipe", OD=design.outside_diameter_m,
                           WT=design.wall_thickness_m)
    with model.pipe("WaterPipe", "Steel", route="L-101") as pipe:
        pipe.start([0, 0, 0], support="anchor")
        pipe.run(design.straight_leg_m)
        for angle, length in [(90, design.offset_m), (-90, design.straight_leg_m),
                              (-90, design.offset_m), (90, design.straight_leg_m)]:
            pipe.bend(radius=design.bend_radius_m, angle=angle, plane="XY")
            pipe.run(length)
        pipe.end(support="anchor")
    return model


def network_snapshot(model: Model, design: StarterDesign) -> dict:
    """Associate one fixed process graph with measured built-route geometry.

    This intentionally supports only this starter's one uniform-bore route.
    Local losses are lumped; the snapshot does not define wall-pressure fields
    or a mechanical representation of the valve.
    """
    elements = [element for element in model.elements if element.route_id == "L-101"]
    if not elements or len(elements) != len(model.elements):
        raise ValueError("Starter requires exactly one route, L-101")
    if any(element.type not in {"pipe_straight", "pipe_bend"} for element in elements):
        raise ValueError("Starter supports only straight pipes and bends")
    sections = {element.section for element in elements}
    if len(sections) != 1:
        raise ValueError("Starter requires one uniform pipe section")
    section = model.sections[next(iter(sections))]
    start = model.nodes[elements[0].n1].coords
    end = model.nodes[elements[-1].n2].coords
    network = {
        "schema": "tuba.process-starter.v0",
        "components": [
            {"id": "SRC-101", "kind": "mass_flow_boundary", "ports": ["out"]},
            {"id": "L-101", "kind": "pipe", "ports": ["in", "out"]},
            {"id": "V-101", "kind": "fixed_loss", "ports": ["in", "out"]},
            {"id": "SNK-101", "kind": "pressure_boundary", "ports": ["in"]},
        ],
        "connections": [["SRC-101.out", "L-101.in"],
                        ["L-101.out", "V-101.in"], ["V-101.out", "SNK-101.in"]],
        "medium": "Modelica.Media.Water.ConstantPropertyLiquidWater",
        "modelica_version": MODELICA_VERSION,
        "inputs": asdict(design),
        "route": {
            "id": "L-101", "element_ids": [element.id for element in elements],
            "length_m": sum(element_length(model, element) for element in elements),
            "bore_m": section.ID, "height_change_m": float(end[2] - start[2]),
            "start_m": list(start), "end_m": list(end),
            "bend_count": sum(element.type == "pipe_bend" for element in elements),
        },
        "structural_status": "not_evaluated",
        "limitations": ["Illustrative constant-property liquid and fixed loss coefficients",
                        "Bend excess losses lumped after distributed pipe friction",
                        "Valve has no mechanical model; wall fields not mapped",
                        "No Code_Aster solve or structural acceptance"],
    }
    encoded = json.dumps(network, sort_keys=True, allow_nan=False).encode()
    network["candidate_sha256"] = hashlib.sha256(encoded).hexdigest()
    return network


OUTPUTS = ("massFlow", "sinkMassFlow", "inletPressure", "sinkPressure",
           "pressureDrop", "fluidDensity", "dynamicViscosity", "velocity")


def modelica_source(network: dict) -> str:
    """Compile this fixed topology using Standard Library components."""
    route, data = network["route"], network["inputs"]
    return f'''model TubaWaterStarter
  package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;
  inner Modelica.Fluid.System system(allowFlowReversal=false);
  Modelica.Fluid.Sources.MassFlowSource_T source(
    redeclare package Medium = Medium, nPorts=1,
    m_flow={data['mass_flow_kg_s']}, T={data['source_temperature_k']});
  Modelica.Fluid.Pipes.StaticPipe pipe(
    redeclare package Medium = Medium, length={route['length_m']},
    diameter={route['bore_m']}, roughness={data['roughness_m']},
    height_ab={route['height_change_m']});
  Modelica.Fluid.Fittings.SimpleGenericOrifice bendLoss(
    redeclare package Medium = Medium, diameter={route['bore_m']},
    zeta={route['bend_count'] * data['bend_zeta_each']});
  Modelica.Fluid.Fittings.SimpleGenericOrifice valve(
    redeclare package Medium = Medium, diameter={route['bore_m']},
    zeta={data['valve_zeta']});
  Modelica.Fluid.Sources.Boundary_pT sink(
    redeclare package Medium = Medium, nPorts=1,
    p={data['sink_pressure_pa']}, T={data['source_temperature_k']});
  output Real massFlow(unit="kg/s") = pipe.port_a.m_flow;
  output Real sinkMassFlow(unit="kg/s") = sink.ports[1].m_flow;
  output Real inletPressure(unit="Pa") = pipe.port_a.p;
  output Real sinkPressure(unit="Pa") = sink.ports[1].p;
  output Real pressureDrop(unit="Pa") = inletPressure - sinkPressure;
  output Real fluidDensity(unit="kg/m3") = Medium.density(
    Medium.setState_pT(inletPressure, {data['source_temperature_k']}));
  output Real dynamicViscosity(unit="Pa.s") = Medium.dynamicViscosity(
    Medium.setState_pT(inletPressure, {data['source_temperature_k']}));
  output Real velocity(unit="m/s") = abs(massFlow) /
    (fluidDensity * Modelica.Constants.pi * {route['bore_m']}^2 / 4);
equation
  connect(source.ports[1], pipe.port_a);
  connect(pipe.port_b, bendLoss.port_a);
  connect(bendLoss.port_b, valve.port_a);
  connect(valve.port_b, sink.ports[1]);
end TubaWaterStarter;
'''


def read_results(path: Path, network: dict) -> dict:
    """Reject missing/nonfinite outputs and failed boundary/conservation checks."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("OpenModelica produced no result rows")
    values = {name: float(rows[-1][name]) for name in OUTPUTS}
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("OpenModelica produced nonfinite outputs")
    if not math.isclose(float(rows[-1]["time"]), 1.0, abs_tol=1e-8):
        raise ValueError("OpenModelica did not reach the requested stop time")
    inputs = network["inputs"]
    for actual, expected in [(values["massFlow"], inputs["mass_flow_kg_s"]),
                             (values["sinkMassFlow"], values["massFlow"]),
                             (values["sinkPressure"], inputs["sink_pressure_pa"])]:
        if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-8):
            raise ValueError("OpenModelica boundary or mass-balance check failed")
    if values["fluidDensity"] <= 0 or values["dynamicViscosity"] <= 0:
        raise ValueError("OpenModelica fluid properties must be positive")
    area = math.pi * network["route"]["bore_m"] ** 2 / 4
    velocity = abs(values["massFlow"]) / (values["fluidDensity"] * area)
    if not math.isclose(values["velocity"], velocity, rel_tol=1e-7):
        raise ValueError("OpenModelica velocity is inconsistent with mass flow and bore")
    if not math.isclose(values["pressureDrop"], values["inletPressure"] - values["sinkPressure"],
                        rel_tol=1e-7, abs_tol=1e-6):
        raise ValueError("OpenModelica pressure outputs are inconsistent")
    return {
        "candidate_sha256": network["candidate_sha256"], "outputs_si": values,
        "hydraulic_checks": {
            "maximum_velocity": values["velocity"] <= inputs["max_velocity_m_s"],
            "maximum_source_pressure": values["inletPressure"] <= inputs["max_source_pressure_pa"],
        },
        "structural_status": "not_evaluated", "engineering_acceptance": "not_evaluated",
    }


def run_example(design: StarterDesign, output: Path, omc: Path) -> dict:
    """Run the real compiler in a fresh directory; retain inputs and raw evidence."""
    output, omc = output.resolve(), omc.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output.is_relative_to(checkout):
        raise ValueError("Choose an output directory outside the source checkout")
    if not omc.is_file():
        raise RuntimeError("OpenModelica compiler unavailable; pass --omc with its executable")
    output.mkdir(parents=True, exist_ok=False)
    model = build_model(design)
    network = network_snapshot(model, design)
    (output / "network.json").write_text(json.dumps(network, indent=2), encoding="utf-8")
    model.to_json(output / "tuba_model.json")
    (output / "TubaWaterStarter.mo").write_text(modelica_source(network), encoding="utf-8")
    script = (f'loadModel(Modelica, {{"{MODELICA_VERSION}"}}, requireExactVersion=true);\n'
              + '''print("TUBA_MSL_VERSION=" + getVersion(Modelica) + "\\n");
loadFile("TubaWaterStarter.mo");
simulate(TubaWaterStarter, startTime=0, stopTime=1, numberOfIntervals=1,
  tolerance=1e-8, outputFormat="csv", variableFilter="time|''' + "|".join(OUTPUTS) + '''");
getErrorString();
''')
    (output / "run.mos").write_text(script, encoding="utf-8")
    version = subprocess.run([str(omc), "--version"], capture_output=True,
                             text=True, check=True, timeout=30).stdout.strip()
    try:
        completed = subprocess.run([str(omc), "run.mos"], cwd=output, capture_output=True,
                                   text=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        log = (error.stdout or b"") + (error.stderr or b"")
        (output / "compiler.log").write_bytes(log + b"\nOpenModelica exceeded 180 seconds.\n")
        raise RuntimeError(f"OpenModelica timed out; see {output / 'compiler.log'}") from error
    log = completed.stdout + completed.stderr
    (output / "compiler.log").write_text(log, encoding="utf-8")
    result_path = output / "TubaWaterStarter_res.csv"
    if completed.returncode or not result_path.is_file():
        raise RuntimeError(f"OpenModelica simulation failed; see {output / 'compiler.log'}")
    results = read_results(result_path, network)
    library_versions = [line.split("=", 1)[1] for line in log.splitlines()
                        if line.startswith("TUBA_MSL_VERSION=")]
    if library_versions != [MODELICA_VERSION]:
        raise RuntimeError(f"Expected Modelica {MODELICA_VERSION}; see {output / 'compiler.log'}")
    results.update({"compiler_version": version, "modelica_version": library_versions[0],
                    "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    "modelica_source_sha256": hashlib.sha256(
                        (output / "TubaWaterStarter.mo").read_bytes()).hexdigest(),
                    "limitations": network["limitations"]})
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--omc", type=Path, default=shutil.which("omc"))
    parser.add_argument("--outside-diameter", type=float, default=0.0889)
    parser.add_argument("--wall-thickness", type=float, default=0.00549)
    parser.add_argument("--offset", type=float, default=1.0)
    args = parser.parse_args()
    if args.omc is None:
        parser.error("OpenModelica is not on PATH; provide --omc /path/to/omc")
    design = StarterDesign(outside_diameter_m=args.outside_diameter,
                           wall_thickness_m=args.wall_thickness, offset_m=args.offset)
    print(json.dumps(run_example(design, args.output, args.omc), indent=2))


if __name__ == "__main__":
    main()
