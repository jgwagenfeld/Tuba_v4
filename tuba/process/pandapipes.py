"""Real pandapipes evaluation of Tuba's serial constant-property water circuit.

Hydraulic evidence is separate from Code_Aster evidence. No thermal transport,
transient, equipment-characteristic or structural acceptance is implied.
"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import math
import platform
import sys
from pathlib import Path

from .modelica import (
    HydraulicResults, HydraulicSegmentResult, LIMITATIONS, MEDIUM, MODELICA_VERSION,
    _ExecutionReceipt, _json_sha, _sha, _validate_subset,
)
from .network import BoundProcessNetwork

PANDAPIPES_VERSION = "0.15.0"
# Modelica 4.1.0 ConstantPropertyLiquidWater; no temperature-dependent water library.
FLUID_PROPERTIES = {"density": 995.586, "viscosity": 0.001, "heat_capacity": 4184.0}
OPTIONS = {"mode": "hydraulics", "friction_model": "colebrook", "use_numba": False,
           "transient": False, "tol_p": 1e-10, "tol_m": 1e-10, "tol_res": 1e-10,
           "max_iter_hyd": 100, "max_iter_colebrook": 100, "tolerance_colebrook": 1e-10}
PANDAPIPES_LIMITATIONS = (*LIMITATIONS,
    "Measured pipes require Reynolds number >= 4000; laminar and transitional flow are unsupported",
    "Isothermal hydraulics only; bulk temperature is prescribed, with no heat-transfer solve",
    "pandapipes Colebrook uses roughness/(3.71 diameter) and gravity 9.81 m/s2; Modelica correlations differ",
)


class PandapipesEvaluationError(RuntimeError):
    """Unavailable or failed real pipeflow; retained manifest locates evidence."""


def _runtime():
    try:
        import pandapipes as pp
    except ImportError as error:
        raise PandapipesEvaluationError(
            "pandapipes runtime unavailable; install 'tuba[process]'. "
            "No hydraulic results were evaluated.") from error
    if pp.__version__ != PANDAPIPES_VERSION:
        raise PandapipesEvaluationError(f"Supported pandapipes version is exactly {PANDAPIPES_VERSION}")
    return pp


def _dependency_identity() -> dict:
    """Fingerprint executable distribution code, including numerical binaries."""
    packages = {}
    for name in ("pandapipes", "pandapower", "numpy", "scipy", "pandas"):
        distribution = importlib.metadata.distribution(name)
        files = distribution.files
        if files is None:
            raise ValueError(f"Cannot identify installed {name} distribution files")
        code = sorted(str(path) for path in files
                      if Path(path).suffix.lower() in {".py", ".pyd", ".dll", ".so"})
        packages[name] = {"version": distribution.version,
                          "code_sha256": _json_sha([(name, _sha(Path(distribution.locate_file(name))))
                                                    for name in code]),
                          "code_files": len(code)}
    return {"python_version": platform.python_version(), "python_executable": str(Path(sys.executable).resolve()),
            "python_executable_sha256": _sha(Path(sys.executable)), "packages": packages,
            "hash_scope": "installed distribution .py/.pyd/.dll/.so file bytes and paths; Python executable"}


def _ambient_bar(height_m: float) -> float:
    from pandapipes.component_models.component_toolbox import p_correction_height_air
    ambient = float(p_correction_height_air(height_m))
    if not math.isfinite(ambient) or ambient <= 0:
        raise ValueError("Junction elevation is outside the pandapipes atmospheric-pressure model")
    return ambient


def _create_network(bound: BoundProcessNetwork, pp):
    if not isinstance(bound, BoundProcessNetwork):
        raise TypeError("pandapipes requires a bound Tuba process network")
    _validate_subset(bound)
    bound.ordered_components  # Validate the supported serial topology.
    for segment in bound.segments:
        reynolds = 4 * bound.scenario.mass_flow_kg_s / (math.pi * segment.bore_m * FLUID_PROPERTIES["viscosity"])
        if segment.element_id is not None and reynolds < 4000:
            raise ValueError(f"{segment.segment_id}: Colebrook requires turbulent pipe flow with Reynolds >= 4000")
    for previous, following in zip(bound.segments, bound.segments[1:]):
        if any(not math.isclose(a, b, abs_tol=1e-8, rel_tol=0)
               for a, b in zip(previous.end_m, following.start_m)):
            raise ValueError("Bound serial segments must share their adjoining coordinates")
    fluid = pp.Fluid(MEDIUM, "liquid", **{name: pp.FluidPropertyConstant(value)
                                       for name, value in FLUID_PROPERTIES.items()})
    net = pp.create_empty_network(name=bound.scenario.id, fluid=fluid, add_stdtypes=False)
    heights = [bound.segments[0].start_m[2], *(segment.end_m[2] for segment in bound.segments)]
    scenario = bound.scenario
    for index, height in enumerate(heights):
        pp.create_junction(net, pn_bar=scenario.sink_pressure_pa / 1e5 - _ambient_bar(height),
                           tfluid_k=scenario.source_temperature_k, height_m=height, index=index)
    for index, segment in enumerate(bound.segments):
        if segment.element_id is not None:
            pp.create_pipe_from_parameters(
                net, index, index + 1, length_km=segment.length_m / 1000,
                # Make pp's isothermal default explicit so pipeflow cannot mutate this input.
                inner_diameter_mm=segment.bore_m * 1000, outer_diameter_mm=segment.bore_m * 1000,
                k_mm=segment.roughness_m * 1000,
                loss_coefficient=segment.local_loss_coefficient, sections=1,
                u_w_per_m2k=0, text_k=scenario.source_temperature_k,
                name=segment.segment_id, index=index,
            )
        else:
            pp.create_valve(net, index, index + 1, et="ju", inner_diameter_mm=segment.bore_m * 1000,
                            opened=True, loss_coefficient=segment.local_loss_coefficient,
                            name=segment.segment_id, index=index)
    pp.create_source(net, 0, mdot_kg_per_s=scenario.mass_flow_kg_s, index=0)
    pp.create_ext_grid(net, len(bound.segments), p_bar=scenario.sink_pressure_pa / 1e5 - _ambient_bar(heights[-1]),
                       t_k=scenario.source_temperature_k, type="pt", index=0)
    return net


def _check_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-6):
        raise ValueError(f"pandapipes {label} boundary/conservation check failed")


def _read_results(net, bound: BoundProcessNetwork) -> tuple:
    """Read actual pipeflow tables, refusing incomplete or invalid measurements."""
    if not bool(net.get("converged", False)):
        raise ValueError("pandapipes pipeflow did not converge")
    count = len(bound.segments)
    if list(net.res_junction.index) != list(range(count + 1)):
        raise ValueError("pandapipes junction result coverage differs from the bound network")
    source_flow = float(net.res_source.loc[0, "mdot_kg_per_s"])
    sink_flow = float(net.res_ext_grid.loc[0, "mdot_kg_per_s"])
    _check_close(source_flow, bound.scenario.mass_flow_kg_s, "source mass flow")
    _check_close(sink_flow, source_flow, "sink mass flow")
    pressures = [float(row.p_bar + _ambient_bar(float(net.junction.loc[index, "height_m"]))) * 1e5
                 for index, row in net.res_junction.iterrows()]
    if any(not math.isfinite(value) or not 100_000 <= value <= 10_000_000 for value in pressures):
        raise ValueError("Evaluated pressure is outside supported single-phase liquid bounds")
    _check_close(pressures[-1], bound.scenario.sink_pressure_pa, "sink pressure")
    segments = []
    for index, segment in enumerate(bound.segments):
        kind = "pipe" if segment.element_id is not None else "valve"
        row = net["res_" + kind].loc[index]
        names = ("p_from_bar", "p_to_bar", "mdot_from_kg_per_s", "mdot_to_kg_per_s",
                 "t_from_k", "t_to_k", "t_outlet_k", "v_mean_m_per_s", "reynolds", "lambda")
        values = {name: float(row[name]) for name in names}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("pandapipes result table has nonfinite outputs")
        flow = values["mdot_from_kg_per_s"]
        if flow <= 0 or values["mdot_to_kg_per_s"] >= 0:
            raise ValueError("Evaluated segment mass flow must be strictly positive and forward")
        _check_close(flow, source_flow, "segment mass flow")
        _check_close(-values["mdot_to_kg_per_s"], flow, "segment mass balance")
        for offset, name in enumerate(("p_from_bar", "p_to_bar")):
            pressure = (values[name] + _ambient_bar(float(net.junction.loc[index + offset, "height_m"]))) * 1e5
            _check_close(pressure, pressures[index + offset], "segment connection")
        temperatures = (float(net.res_junction.loc[index, "t_k"]),
                        float(net.res_junction.loc[index + 1, "t_k"]),
                        *(values[name] for name in ("t_from_k", "t_to_k", "t_outlet_k")))
        for temperature in temperatures:
            _check_close(temperature, bound.scenario.source_temperature_k, "prescribed temperature")
        temperature = (values["t_from_k"] + values["t_to_k"]) / 2
        density = float(net.fluid.get_density(temperature))
        viscosity = float(net.fluid.get_viscosity(temperature))
        _check_close(density, FLUID_PROPERTIES["density"], "constant density")
        _check_close(viscosity, FLUID_PROPERTIES["viscosity"], "constant viscosity")
        velocity = values["v_mean_m_per_s"]
        _check_close(velocity, flow / (density * math.pi * segment.bore_m ** 2 / 4), "velocity")
        _check_close(values["reynolds"], density * velocity * segment.bore_m / viscosity, "Reynolds number")
        if segment.element_id is not None and (values["reynolds"] < 4000 or values["lambda"] <= 0):
            raise ValueError("Evaluated pipe friction requires positive Colebrook factor and Reynolds >= 4000")
        segments.append(HydraulicSegmentResult(
            segment.segment_id, segment.component_id, segment.element_id, pressures[index], pressures[index + 1],
            flow, temperature, density, viscosity, velocity))
    ports = {bound.ordered_components[0].outlet_port: pressures[0],
             bound.ordered_components[-1].inlet_port: pressures[-1]}
    for component in bound.ordered_components[1:-1]:
        results = [segment for segment in segments if segment.component_id == component.id]
        ports[component.inlet_port] = results[0].pressure_in_pa
        ports[component.outlet_port] = results[-1].pressure_out_pa
    return tuple(segments), ports, pressures[0], pressures[-1], source_flow


def _results_csv(net) -> str:
    """Retain every native result table, including friction and boundary outputs."""
    import pandas as pd
    tables = [table.assign(component=kind, index=table.index)
              for kind in ("res_junction", "res_pipe", "res_valve", "res_source", "res_ext_grid")
              if len(table := net[kind])]
    return pd.concat(tables, ignore_index=True, sort=False).to_csv(
        index=False, float_format="%.17g", lineterminator="\n")


def _verify_raw(result: HydraulicResults, bound: BoundProcessNetwork) -> tuple:
    pp = _runtime()
    identity = json.loads(Path(result.artifacts["dependency_identity"]["path"]).read_text(encoding="utf-8"))
    if identity != _dependency_identity() or result.provenance["dependencies_sha256"] != _json_sha(identity):
        raise ValueError("The evaluated pandapipes runtime/dependency code has changed")
    # Compare inputs at the native JSON precision used by the retained artifact.
    expected = pp.from_json_string(pp.to_json(_create_network(bound, pp)), convert=False)
    original = pp.from_json(result.artifacts["solver_input"]["path"], convert=False)
    solved = pp.from_json(result.artifacts["solver_network"]["path"], convert=False)
    for net in (original, solved):
        for name in ("junction", "pipe", "valve", "source", "ext_grid"):
            if not net[name].equals(expected[name]):
                raise ValueError(f"Hydraulic pandapipes {name} inputs do not match this bound network")
        if json.loads(net.fluid.to_json()) != json.loads(expected.fluid.to_json()):
            raise ValueError("Hydraulic pandapipes fluid does not match the prescribed constant water")
    execution = solved["tuba_execution"]
    if (execution["options"] != result.provenance["actual_options"]
            or any(execution["options"].get(name) != value for name, value in OPTIONS.items())
            or execution["residual_norm_hydraulics"] > OPTIONS["tol_res"]
            or execution["iterations_hydraulics"] <= 0):
        raise ValueError("Hydraulic pandapipes solver options/convergence evidence differs")
    if Path(result.artifacts["csv"]["path"]).read_text(encoding="utf-8") != _results_csv(solved):
        raise ValueError("Hydraulic measurements do not match their raw pandapipes CSV tables")
    log = Path(result.artifacts["solver_log"]["path"]).read_text(encoding="utf-8")
    if f"TUBA_PANDAPIPES_VERSION={PANDAPIPES_VERSION}\n" not in log or "TUBA_CONVERGED=true\n" not in log:
        raise ValueError("pandapipes did not record a successful pipeflow evaluation")
    return _read_results(solved, bound)


class PandapipesBackend:
    """Optional Python solver for the bounded turbulent, isothermal liquid case."""

    def solve(self, bound: BoundProcessNetwork, output_directory: str | Path) -> HydraulicResults:
        output = Path(output_directory).resolve()
        checkout = Path(__file__).resolve().parents[2]
        if output.is_relative_to(checkout) or any((parent / ".git").exists() for parent in (output, *output.parents)):
            raise ValueError("pandapipes attempt output must be outside the source checkout")
        output.mkdir(parents=True, exist_ok=False)
        manifest_path = output / "manifest.json"
        manifest = {"schema": "tuba.process.pandapipes-attempt.v1", "status": "started",
                    "bound_fingerprint": bound.fingerprint, "geometry_fingerprint": bound.geometry_fingerprint,
                    "scenario_id": bound.scenario.id, "limitations": PANDAPIPES_LIMITATIONS}
        paths = {"network": output / "network.json", "solver_input": output / "pandapipes-input.json",
                 "solver_network": output / "pandapipes-results.json", "csv": output / "pandapipes-results.csv",
                 "dependency_identity": output / "dependencies.json", "solver_log": output / "solver.log"}
        def save_manifest():
            manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
        save_manifest()
        try:
            pp = _runtime()
            net = _create_network(bound, pp)
            identity = _dependency_identity()
            paths["network"].write_text(json.dumps(bound.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
            paths["dependency_identity"].write_text(json.dumps(identity, indent=2), encoding="utf-8")
            pp.to_json(net, str(paths["solver_input"]))
            with paths["solver_log"].open("w", encoding="utf-8") as stream:
                stream.write(f"TUBA_PANDAPIPES_VERSION={pp.__version__}\n")
                stream.write(json.dumps({"options": OPTIONS, "fluid_properties": FLUID_PROPERTIES}) + "\n")
                logger = logging.getLogger("pandapipes")
                handler = logging.StreamHandler(stream)
                previous_level = logger.level
                logger.addHandler(handler)
                logger.setLevel(logging.DEBUG)
                try:
                    pp.pipeflow(net, **OPTIONS)
                finally:
                    logger.removeHandler(handler)
                    logger.setLevel(previous_level)
                stats = net["_internal_results"]
                execution = {"options": dict(net["_options"]),
                             "iterations_hydraulics": int(stats["iterations_hydraulics"]),
                             "residual_norm_hydraulics": float(stats["residual_norm_hydraulics"])}
                net["tuba_execution"] = execution
                stream.write(json.dumps(execution, allow_nan=False) + "\n")
                if not bool(net.get("converged", False)) or execution["residual_norm_hydraulics"] > OPTIONS["tol_res"]:
                    raise ValueError("pandapipes did not converge within the required residual tolerance")
                stream.write("TUBA_CONVERGED=true\n")
            pp.to_json(net, str(paths["solver_network"]))
            # Issue measurements from the saved solver output, as the verifier does.
            net = pp.from_json(str(paths["solver_network"]), convert=False)
            paths["csv"].write_text(_results_csv(net), encoding="utf-8")
            parsed = _read_results(net, bound)
            artifacts = {name: {"path": str(path), "sha256": _sha(path)} for name, path in paths.items()}
            provenance = {"solver": "pandapipes", "pandapipes_version": pp.__version__,
                          "medium": MEDIUM, "property_source": f"Modelica {MODELICA_VERSION} ConstantPropertyLiquidWater",
                          "fluid_properties": FLUID_PROPERTIES, "dependencies_sha256": _json_sha(identity),
                          "actual_options": execution["options"], "gravity_m_s2": 9.81,
                          "colebrook_roughness_divisor": 3.71,
                          "pressure_reference": "absolute Pa; pandapipes gauge bar plus its junction-height-corrected ambient bar",
                          "temperature_model": "prescribed uniform isothermal bulk temperature; no heat-transfer solution",
                          "loss_partition": "element arc/straight distributed friction plus one declared excess loss per segment"}
            result = HydraulicResults(bound.scenario.id, bound.fingerprint, bound.geometry_fingerprint,
                                      *parsed, artifacts, provenance, str(manifest_path), PANDAPIPES_LIMITATIONS)
            manifest.update(status="succeeded", artifacts=artifacts, provenance=provenance, results=result.to_dict())
            save_manifest()
            object.__setattr__(result, "_receipt", _ExecutionReceipt(_json_sha(result.to_dict()), _sha(manifest_path)))
            return result
        except Exception as error:
            with paths["solver_log"].open("a", encoding="utf-8") as stream:
                stream.write(f"{type(error).__name__}: {error}\n")
            manifest.update(status="failed", error_type=type(error).__name__, error=str(error))
            save_manifest()
            raise PandapipesEvaluationError(f"pandapipes evaluation failed: {error}; evidence: {manifest_path}") from error
