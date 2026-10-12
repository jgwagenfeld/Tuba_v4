"""External OpenModelica evaluation of the bounded forward liquid circuit.

The adapter writes generated inputs into a fresh attempt directory. It never
edits authored Modelica or Tuba source. Hydraulic evidence is separate from
Code_Aster evidence and does not establish structural acceptance.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .network import BoundProcessNetwork

MODELICA_VERSION = "4.1.0"
MEDIUM = "Modelica.Media.Water.ConstantPropertyLiquidWater"
MODEL_NAME = "TubaLiquidCircuit"
STOP_TIME = 1.0
LIMITATIONS = (
    "Forward, fully filled, single-phase constant-property liquid water only",
    "273.15 <= temperature <= 353.15 K and 100000 <= absolute pressure <= 10000000 Pa",
    "Steady serial circuit; no storage, transients, reverse flow, pumps or branches",
    "Measured bend arc contributes distributed friction; declared bend excess loss is applied once",
    "Fixed-loss data remain declared correlations, not calibrated equipment characteristics",
    "Hydraulic evaluation alone provides no Code_Aster or piping-code acceptance",
)


class ModelicaEvaluationError(RuntimeError):
    """A failed or unavailable real simulation; retained manifest locates evidence."""


@dataclass(frozen=True)
class HydraulicSegmentResult:
    segment_id: str
    component_id: str
    element_id: str | None
    pressure_in_pa: float
    pressure_out_pa: float
    mass_flow_kg_s: float
    temperature_k: float
    density_kg_m3: float
    dynamic_viscosity_pa_s: float
    velocity_m_s: float


@dataclass(frozen=True)
class _ExecutionReceipt:
    result_sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class HydraulicResults:
    """Serializable measurements; only solve-issued, matching evidence verifies.

    Constructing this record does not qualify a simulation. The mechanical
    mapper must call ``verify_for(bound)`` before consuming any measurement.
    """

    scenario_id: str
    bound_fingerprint: str
    geometry_fingerprint: str
    segments: tuple[HydraulicSegmentResult, ...]
    port_pressures_pa: dict[str, float]
    source_pressure_pa: float
    sink_pressure_pa: float
    mass_flow_kg_s: float
    artifacts: dict[str, dict[str, str]]
    provenance: dict
    manifest_path: str
    limitations: tuple[str, ...] = LIMITATIONS
    _receipt: _ExecutionReceipt | None = field(default=None, init=False, repr=False, compare=False)

    def to_dict(self) -> dict:
        result = asdict(self)
        result.pop("_receipt")
        result["schema"] = "tuba.process.hydraulic-results.v1"
        return result

    def verify_for(self, bound: BoundProcessNetwork) -> None:
        """Reject constructed, changed, stale, missing or altered evidence."""
        if self._receipt is None or _json_sha(self.to_dict()) != self._receipt.result_sha256:
            raise ValueError("Hydraulic results are not unchanged solve-issued evidence")
        if (self.bound_fingerprint != bound.fingerprint
                or self.geometry_fingerprint != bound.geometry_fingerprint
                or self.scenario_id != bound.scenario.id):
            raise ValueError("Hydraulic results are stale for this network/scenario")
        manifest_path = Path(self.manifest_path)
        if not manifest_path.is_file() or _sha(manifest_path) != self._receipt.manifest_sha256:
            raise ValueError("Hydraulic execution manifest is missing or modified")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "succeeded" or manifest.get("results") != _json_value(self.to_dict()):
            raise ValueError("Hydraulic execution manifest does not establish successful evaluation")
        for name, artifact in self.artifacts.items():
            path = Path(artifact["path"])
            if not path.is_file() or _sha(path) != artifact["sha256"]:
                raise ValueError(f"Hydraulic {name} artifact is missing or modified")
        network_path = Path(self.artifacts["network"]["path"])
        if json.loads(network_path.read_text(encoding="utf-8")) != _json_value(bound.to_dict()):
            raise ValueError("Hydraulic network artifact does not match this bound network")
        solver = self.provenance.get("solver", "OpenModelica").lower()
        if solver == "openmodelica":
            parsed = _verify_modelica_raw(self, bound)
        elif solver == "pandapipes":
            from .pandapipes import _verify_raw
            parsed = _verify_raw(self, bound)
        else:
            raise ValueError(f"Unsupported hydraulic solver provenance: {solver}")
        if parsed != (self.segments, self.port_pressures_pa, self.source_pressure_pa,
                      self.sink_pressure_pa, self.mass_flow_kg_s):
            raise ValueError("Hydraulic measurements do not match their raw solver outputs")


def _verify_modelica_raw(result: HydraulicResults, bound: BoundProcessNetwork) -> tuple:
    if _library_sha(Path(result.provenance["library_source"])) != result.provenance["library_sha256"]:
        raise ValueError("The evaluated Modelica library sources have changed")
    source = Path(result.artifacts["modelica_source"]["path"]).read_text(encoding="utf-8")
    if source != modelica_source(bound):
        raise ValueError("Hydraulic Modelica source does not match this bound network")
    _validate_log(Path(result.artifacts["compiler_log"]["path"]).read_text(encoding="utf-8"),
                  Path(result.artifacts["csv"]["path"]))
    return _read_csv(Path(result.artifacts["csv"]["path"]), bound)


def _json_value(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _json_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _library_sha(package_file: Path) -> str:
    """Hash the loaded MSL .mo source tree and paths, excluding docs/build output."""
    root = package_file.parent
    if not package_file.is_file() or package_file.name != "package.mo":
        raise ValueError("OpenModelica did not identify the loaded Modelica package.mo")
    sources = sorted(root.rglob("*.mo"), key=lambda path: path.relative_to(root).as_posix())
    return _json_sha([(path.relative_to(root).as_posix(), _sha(path)) for path in sources])


def discover_omc(omc: str | Path | None = None) -> Path:
    """Use explicit path, TUBA_OMC, PATH or an existing Windows installation."""
    candidates = ([Path(omc)] if omc is not None else [])
    if omc is None:
        configured = os.environ.get("TUBA_OMC")
        if configured:
            candidates.append(Path(configured))
        located = shutil.which("omc")
        if located:
            candidates.append(Path(located))
        installation = os.environ.get("OPENMODELICAHOME")
        if installation:
            candidates.append(Path(installation) / "bin" / ("omc.exe" if os.name == "nt" else "omc"))
        if os.name == "nt":
            candidates.extend(sorted(Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                                     .glob("OpenModelica*/bin/omc.exe"), reverse=True))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ModelicaEvaluationError(
        "OpenModelica compiler unavailable; install OpenModelica with Modelica 4.1.0, "
        "set TUBA_OMC or pass OpenModelicaBackend(omc=...). No hydraulic results were evaluated.")


def _validate_subset(bound: BoundProcessNetwork) -> None:
    scenario = bound.scenario
    if scenario.medium != MEDIUM:
        raise ValueError(f"Supported medium is exactly {MEDIUM}")
    if not 273.15 <= scenario.source_temperature_k <= 353.15:
        raise ValueError("Supported single-phase temperature is 273.15..353.15 K")
    if not 100_000 <= scenario.sink_pressure_pa <= 10_000_000:
        raise ValueError("Supported absolute sink pressure is 100000..10000000 Pa")
    if not math.isfinite(scenario.mass_flow_kg_s) or scenario.mass_flow_kg_s <= 0:
        raise ValueError("Only finite positive forward mass flow is supported")
    if not bound.segments:
        raise ValueError("A bound circuit requires pipe segments")
    for segment in bound.segments:
        for name in ("length_m", "bore_m", "height_change_m", "roughness_m", "local_loss_coefficient"):
            if not math.isfinite(getattr(segment, name)):
                raise ValueError(f"{segment.segment_id}: {name} must be finite")
        if segment.bore_m <= 0 or segment.roughness_m < 0 or segment.local_loss_coefficient < 0:
            raise ValueError(f"{segment.segment_id}: positive bore and nonnegative roughness/loss required")
        if segment.element_id is not None and segment.length_m <= 0:
            raise ValueError(f"{segment.segment_id}: measured pipe length must be positive")
        if segment.element_id is None and (segment.length_m != 0 or segment.local_loss_coefficient <= 0):
            raise ValueError(f"{segment.segment_id}: fixed loss requires zero length and positive coefficient")
        if segment.local_loss_coefficient and not segment.loss_source:
            raise ValueError(f"{segment.segment_id}: local loss requires correlation/source information")


def _outputs(bound: BoundProcessNetwork) -> tuple[str, ...]:
    names = ["sourceMassFlow", "sinkMassFlow", "sourcePressure", "sinkPressure"]
    for index, _ in enumerate(bound.segments):
        names.extend(f"{name}{index}" for name in
                     ("pressureIn", "pressureOut", "massFlow", "massFlowOut", "temperature",
                      "temperatureIn", "temperatureOut", "density", "viscosity", "velocity"))
    return tuple(names)


def modelica_source(bound: BoundProcessNetwork) -> str:
    """Use MSL components per measured element, with each excess loss once."""
    _validate_subset(bound)
    scenario = bound.scenario
    lines = [f"model {MODEL_NAME}", f"  package Medium = {MEDIUM};",
             "  inner Modelica.Fluid.System system(allowFlowReversal=false);",
             "  Modelica.Fluid.Sources.MassFlowSource_T source(",
             f"    redeclare package Medium = Medium, nPorts=1, m_flow={scenario.mass_flow_kg_s}, T={scenario.source_temperature_k});",
             "  Modelica.Fluid.Sources.Boundary_pT sink(",
             f"    redeclare package Medium = Medium, nPorts=1, p={scenario.sink_pressure_pa}, T={scenario.source_temperature_k});"]
    connections = []
    previous = "source.ports[1]"
    for index, segment in enumerate(bound.segments):
        first = last = f"pipe{index}"
        if segment.element_id is not None:
            lines.extend([f"  Modelica.Fluid.Pipes.StaticPipe pipe{index}(",
                          f"    redeclare package Medium = Medium, length={segment.length_m}, diameter={segment.bore_m},",
                          f"    roughness={segment.roughness_m}, height_ab={segment.height_change_m});"])
        if segment.local_loss_coefficient > 0:
            last = f"loss{index}"
            lines.extend([f"  Modelica.Fluid.Fittings.SimpleGenericOrifice {last}(",
                          f"    redeclare package Medium = Medium, diameter={segment.bore_m}, zeta={segment.local_loss_coefficient});"])
            if segment.element_id is None:
                first = last
            else:
                connections.append(f"  connect({first}.port_b, {last}.port_a);")
        inlet, outlet = f"{first}.port_a", f"{last}.port_b"
        connections.append(f"  connect({previous}, {inlet});")
        previous = outlet
        lines.extend([
            f"  Medium.ThermodynamicState stateIn{index} = Medium.setState_phX({inlet}.p, actualStream({inlet}.h_outflow));",
            f"  Medium.ThermodynamicState stateOut{index} = Medium.setState_phX({outlet}.p, actualStream({outlet}.h_outflow));",
            f'  output Real pressureIn{index}(unit="Pa") = {inlet}.p;',
            f'  output Real pressureOut{index}(unit="Pa") = {outlet}.p;',
            f'  output Real massFlow{index}(unit="kg/s") = {inlet}.m_flow;',
            f'  output Real massFlowOut{index}(unit="kg/s") = -{outlet}.m_flow;',
            f'  output Real temperatureIn{index}(unit="K") = Medium.temperature(stateIn{index});',
            f'  output Real temperatureOut{index}(unit="K") = Medium.temperature(stateOut{index});',
            f'  output Real temperature{index}(unit="K") = (temperatureIn{index} + temperatureOut{index}) / 2;',
            f'  output Real density{index}(unit="kg/m3") = Medium.density(stateIn{index});',
            f'  output Real viscosity{index}(unit="Pa.s") = Medium.dynamicViscosity(stateIn{index});',
            f'  output Real velocity{index}(unit="m/s") = massFlow{index} / (density{index} * Modelica.Constants.pi * {segment.bore_m}^2 / 4);',
        ])
    connections.append(f"  connect({previous}, sink.ports[1]);")
    lines.extend(['  output Real sourceMassFlow(unit="kg/s") = -source.ports[1].m_flow;',
                  '  output Real sinkMassFlow(unit="kg/s") = sink.ports[1].m_flow;',
                  '  output Real sourcePressure(unit="Pa") = source.ports[1].p;',
                  '  output Real sinkPressure(unit="Pa") = sink.ports[1].p;',
                  "equation", *connections, f"end {MODEL_NAME};", ""])
    return "\n".join(lines)


def _script(bound: BoundProcessNetwork) -> str:
    return (f'loadModel(Modelica, {{"{MODELICA_VERSION}"}}, requireExactVersion=true);\n'
            'print("TUBA_MSL_VERSION=" + getVersion(Modelica) + "\\n");\n'
            'print("TUBA_LIBRARY_SOURCE=" + getSourceFile(Modelica) + "\\n");\n'
            f'loadFile("{MODEL_NAME}.mo");\n'
            f'simulate({MODEL_NAME}, startTime=0, stopTime={STOP_TIME}, numberOfIntervals=1,\n'
            f'  tolerance=1e-8, outputFormat="csv", variableFilter="time|{"|".join(_outputs(bound))}");\n'
            'getErrorString();\n')


def _run_process(command: list[str], directory: Path, timeout_s: float) -> subprocess.CompletedProcess:
    """Own a process group; on timeout terminate the compiler and its children."""
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with subprocess.Popen(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", **options) as process:
        try:
            output, _ = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as error:
            if process.poll() is None:
                if os.name == "nt":
                    try:
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, timeout=15, check=False)
                    finally:
                        if process.poll() is None:
                            process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            output, _ = process.communicate(timeout=15)
            raise subprocess.TimeoutExpired(command, timeout_s, output=output) from error
        return subprocess.CompletedProcess(command, process.returncode, output, "")


def _markers(log: str, name: str) -> list[str]:
    return [line.split("=", 1)[1].strip() for line in log.splitlines() if line.startswith(name + "=")]


def _validate_log(log: str, result_path: Path) -> None:
    if _markers(log, "TUBA_MSL_VERSION") != [MODELICA_VERSION]:
        raise ValueError(f"The actual loaded Modelica library must be exactly {MODELICA_VERSION}")
    results = re.findall(r'resultFile\s*=\s*"([^"]*)"', log)
    if (len(results) != 1 or not results[0]
            or Path(results[0]).resolve() != result_path.resolve()
            or "The simulation finished successfully." not in log or "Error:" in log):
        raise ValueError("OpenModelica did not report a successful simulation with the expected CSV")


def _close(actual: float, expected: float, label: str, abs_tol: float = 1e-6) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=abs_tol):
        raise ValueError(f"OpenModelica {label} boundary/conservation check failed")


def _read_csv(path: Path, bound: BoundProcessNetwork) -> tuple:
    _validate_subset(bound)
    required = ("time", *_outputs(bound))
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("OpenModelica CSV has missing or duplicate columns")
        missing = set(required).difference(reader.fieldnames)
        if missing:
            raise ValueError(f"OpenModelica CSV is missing columns: {sorted(missing)}")
        rows = []
        for row in reader:
            try:
                values = {name: float(row[name]) for name in required}
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError("OpenModelica CSV has malformed numeric outputs") from error
            if not all(math.isfinite(value) for value in values.values()):
                raise ValueError("OpenModelica CSV has nonfinite outputs")
            rows.append(values)
    if not rows or not math.isclose(rows[-1]["time"], STOP_TIME, abs_tol=1e-8, rel_tol=0):
        raise ValueError("OpenModelica did not reach the requested stop time")
    if rows[0]["time"] != 0 or any(b["time"] < a["time"] for a, b in zip(rows, rows[1:])):
        raise ValueError("OpenModelica CSV time history is incomplete or unordered")
    for values in rows:
        if values["sourceMassFlow"] <= 0 or values["sinkMassFlow"] <= 0:
            raise ValueError("Evaluated mass flow must be strictly positive and forward")
        _close(values["sourceMassFlow"], bound.scenario.mass_flow_kg_s, "source mass flow", abs_tol=0)
        _close(values["sinkMassFlow"], values["sourceMassFlow"], "sink mass flow", abs_tol=0)
        _close(values["sinkPressure"], bound.scenario.sink_pressure_pa, "sink pressure")
        _close(values["pressureIn0"], values["sourcePressure"], "source connection")
        _close(values["temperatureIn0"], bound.scenario.source_temperature_k, "source temperature")
        for index, segment in enumerate(bound.segments):
            if values[f"massFlow{index}"] <= 0 or values[f"massFlowOut{index}"] <= 0:
                raise ValueError("Evaluated segment mass flow must be strictly positive and forward")
            _close(values[f"massFlow{index}"], values["sourceMassFlow"], "segment mass flow", abs_tol=0)
            _close(values[f"massFlowOut{index}"], values[f"massFlow{index}"], "segment mass balance", abs_tol=0)
            next_pressure = values[f"pressureIn{index + 1}"] if index + 1 < len(bound.segments) else values["sinkPressure"]
            _close(values[f"pressureOut{index}"], next_pressure, "segment connection")
            if index + 1 < len(bound.segments):
                _close(values[f"temperatureOut{index}"], values[f"temperatureIn{index + 1}"], "temperature connection")
            for name in ("pressureIn", "pressureOut"):
                if not 100_000 <= values[f"{name}{index}"] <= 10_000_000:
                    raise ValueError("Evaluated pressure is outside supported single-phase liquid bounds")
            for name in ("temperatureIn", "temperatureOut", "temperature"):
                if not 273.15 <= values[f"{name}{index}"] <= 353.15:
                    raise ValueError("Evaluated temperature is outside supported single-phase liquid bounds")
            _close(values[f"temperature{index}"],
                   (values[f"temperatureIn{index}"] + values[f"temperatureOut{index}"]) / 2, "temperature")
            if values[f"density{index}"] <= 0 or values[f"viscosity{index}"] <= 0:
                raise ValueError("Evaluated density and viscosity must be positive")
            velocity = values[f"massFlow{index}"] / (values[f"density{index}"] * math.pi * segment.bore_m ** 2 / 4)
            _close(values[f"velocity{index}"], velocity, "velocity", abs_tol=0)
    values = rows[-1]
    segments = tuple(HydraulicSegmentResult(
        segment.segment_id, segment.component_id, segment.element_id,
        values[f"pressureIn{index}"], values[f"pressureOut{index}"], values[f"massFlow{index}"],
        values[f"temperature{index}"], values[f"density{index}"], values[f"viscosity{index}"],
        values[f"velocity{index}"],
    ) for index, segment in enumerate(bound.segments))
    ports = {bound.ordered_components[0].outlet_port: values["sourcePressure"],
             bound.ordered_components[-1].inlet_port: values["sinkPressure"]}
    for component in bound.ordered_components[1:-1]:
        component_results = [segment for segment in segments if segment.component_id == component.id]
        ports[component.inlet_port] = component_results[0].pressure_in_pa
        ports[component.outlet_port] = component_results[-1].pressure_out_pa
    return segments, ports, values["sourcePressure"], values["sinkPressure"], values["sourceMassFlow"]


class OpenModelicaBackend:
    """Optional real external compiler, with no additional Python dependency."""

    def __init__(self, omc: str | Path | None = None, timeout_s: float = 180):
        if isinstance(timeout_s, bool) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self.omc = omc
        self.timeout_s = timeout_s

    def solve(self, bound: BoundProcessNetwork, output_directory: str | Path) -> HydraulicResults:
        output = Path(output_directory).resolve()
        checkout = Path(__file__).resolve().parents[2]
        if output.is_relative_to(checkout) or any((parent / ".git").exists() for parent in (output, *output.parents)):
            raise ValueError("OpenModelica attempt output must be outside the source checkout")
        output.mkdir(parents=True, exist_ok=False)
        manifest_path = output / "manifest.json"
        manifest = {"schema": "tuba.process.modelica-attempt.v1", "status": "started",
                    "bound_fingerprint": bound.fingerprint, "geometry_fingerprint": bound.geometry_fingerprint,
                    "scenario_id": bound.scenario.id, "limitations": LIMITATIONS}
        def save_manifest():
            manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
        save_manifest()
        try:
            source = modelica_source(bound)
            paths = {"network": output / "network.json", "modelica_source": output / f"{MODEL_NAME}.mo",
                     "script": output / "run.mos", "compiler_log": output / "compiler.log",
                     "csv": output / f"{MODEL_NAME}_res.csv"}
            paths["network"].write_text(json.dumps(bound.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
            paths["modelica_source"].write_text(source, encoding="utf-8")
            paths["script"].write_text(_script(bound), encoding="utf-8")
            omc = discover_omc(self.omc)
            version_run = _run_process([str(omc), "--version"], output, min(30, self.timeout_s))
            (output / "version.log").write_text(version_run.stdout, encoding="utf-8")
            if version_run.returncode or "OpenModelica" not in version_run.stdout:
                raise ValueError("The compiler did not provide an OpenModelica version")
            manifest["compiler_version"] = version_run.stdout.strip()
            completed = _run_process([str(omc), "run.mos"], output, self.timeout_s)
            paths["compiler_log"].write_text(completed.stdout, encoding="utf-8")
            manifest["compiler_returncode"] = completed.returncode
            if completed.returncode or not paths["csv"].is_file():
                raise ValueError("OpenModelica compile/simulation failed or produced no CSV")
            _validate_log(completed.stdout, paths["csv"])
            library_sources = _markers(completed.stdout, "TUBA_LIBRARY_SOURCE")
            if len(library_sources) != 1:
                raise ValueError("OpenModelica did not identify the actual loaded Modelica library")
            library_source = Path(library_sources[0]).resolve()
            parsed = _read_csv(paths["csv"], bound)
            paths["compiler_executable"] = omc
            paths["compiler_version"] = output / "version.log"
            for name, filename in (("simulation_log", f"{MODEL_NAME}.log"),
                                   ("initialization_xml", f"{MODEL_NAME}_init.xml")):
                if (output / filename).is_file():
                    paths[name] = output / filename
            artifacts = {name: {"path": str(path), "sha256": _sha(path)} for name, path in paths.items()}
            provenance = {"solver": "OpenModelica", "compiler_version": version_run.stdout.strip(),
                          "modelica_version": MODELICA_VERSION, "medium": MEDIUM,
                          "library_source": str(library_source), "library_sha256": _library_sha(library_source),
                          "library_hash_scope": "all .mo source files and their paths in the loaded Modelica package",
                          "stop_time_s": STOP_TIME, "simulation_tolerance": 1e-8,
                          "loss_partition": "element arc/straight distributed friction plus one declared excess loss per segment"}
            result = HydraulicResults(bound.scenario.id, bound.fingerprint, bound.geometry_fingerprint,
                                      *parsed, artifacts, provenance, str(manifest_path))
            manifest.update(status="succeeded", artifacts=artifacts, provenance=provenance, results=result.to_dict())
            save_manifest()
            manifest["completed_build_cleanup"] = cleanup_completed_modelica_build(output)
            save_manifest()
            object.__setattr__(result, "_receipt", _ExecutionReceipt(_json_sha(result.to_dict()), _sha(manifest_path)))
            return result
        except Exception as error:
            if isinstance(error, subprocess.TimeoutExpired):
                partial = error.output or ""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", errors="replace")
                (output / "compiler.log").write_text(partial + "\nOpenModelica timed out; owned process tree termination requested.\n", encoding="utf-8")
            if not (output / "compiler.log").is_file():
                (output / "compiler.log").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
            manifest.update(status="failed", error_type=type(error).__name__, error=str(error))
            save_manifest()
            raise ModelicaEvaluationError(f"OpenModelica evaluation failed: {error}; evidence: {manifest_path}") from error


def cleanup_completed_modelica_build(output_directory: str | Path) -> dict:
    """Remove only top-level generated compiler payload after a successful solve.

    Inputs, manifest, raw CSV, solver logs and initialization XML stay intact.
    No recursive deletion or link traversal is performed.
    """
    output = Path(output_directory).resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "succeeded":
        raise ValueError("Failed or incomplete Modelica attempts must retain their compiler evidence")
    removed, size = [], 0
    suffixes = {".c", ".h", ".o", ".obj", ".exe", ".bat", ".makefile", ".libs", ".a", ".so", ".dll"}
    for path in output.iterdir():
        if (not path.name.startswith(MODEL_NAME) or path.is_symlink()
                or getattr(path, "is_junction", lambda: False)() or not path.is_file()
                or path.resolve().parent != output):
            continue
        if (path.suffix not in suffixes and path.name != MODEL_NAME
                and path.name not in {f"{MODEL_NAME}_info.json", f"{MODEL_NAME}_external_functions.json"}):
            continue
        size += path.stat().st_size
        path.unlink()
        removed.append(path.name)
    return {"removed_files": sorted(removed), "removed_bytes": size}
