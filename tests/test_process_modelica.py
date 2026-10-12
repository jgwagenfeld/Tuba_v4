"""Portable adapter fixtures are test evidence, never hydraulic qualification."""

import csv
import json
import math
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tuba.process import modelica


def bound_fixture():
    segments = [
        SimpleNamespace(segment_id="line:E1", component_id="LINE", element_id="E1",
                        length_m=2.0, bore_m=0.08, height_change_m=0.0, roughness_m=4.6e-5,
                        local_loss_coefficient=0.0, loss_source=None),
        SimpleNamespace(segment_id="line:E2", component_id="LINE", element_id="E2",
                        length_m=math.pi * 0.3 / 2, bore_m=0.08, height_change_m=0.0,
                        roughness_m=4.6e-5, local_loss_coefficient=0.2, loss_source="illustrative bend assumption"),
        SimpleNamespace(segment_id="VALVE", component_id="VALVE", element_id=None,
                        length_m=0.0, bore_m=0.08, height_change_m=0.0, roughness_m=0.0,
                        local_loss_coefficient=5.0, loss_source="illustrative fixed-loss assumption"),
    ]
    bound = SimpleNamespace(
        scenario=SimpleNamespace(id="water", mass_flow_kg_s=10.0, source_temperature_k=293.15,
                                 sink_pressure_pa=300_000.0, medium=modelica.MEDIUM),
        fingerprint="bound-fingerprint", geometry_fingerprint="geometry-fingerprint", segments=tuple(segments),
        ordered_components=(SimpleNamespace(id="SRC", outlet_port="SRC.out"),
                            SimpleNamespace(id="LINE", inlet_port="LINE.in", outlet_port="LINE.out"),
                            SimpleNamespace(id="VALVE", inlet_port="VALVE.in", outlet_port="VALVE.out"),
                            SimpleNamespace(id="SNK", inlet_port="SNK.in")),
    )
    bound.to_dict = lambda: {"fixture": "not a hydraulic qualification", "fingerprint": bound.fingerprint,
                             "scenario": vars(bound.scenario), "segments": [vars(segment) for segment in bound.segments]}
    return bound


def csv_values(bound):
    flow = bound.scenario.mass_flow_kg_s
    temperature = bound.scenario.source_temperature_k
    source_pressure = bound.scenario.sink_pressure_pa + len(bound.segments) * 10_000
    row = {"time": 1.0, "sourceMassFlow": flow, "sinkMassFlow": flow,
           "sourcePressure": source_pressure, "sinkPressure": bound.scenario.sink_pressure_pa}
    for index, segment in enumerate(bound.segments):
        row.update({f"pressureIn{index}": source_pressure - index * 10_000,
                    f"pressureOut{index}": source_pressure - (index + 1) * 10_000,
                    f"massFlow{index}": flow, f"massFlowOut{index}": flow,
                    f"temperature{index}": temperature, f"temperatureIn{index}": temperature,
                    f"temperatureOut{index}": temperature, f"density{index}": 995.586,
                    f"viscosity{index}": 0.001,
                    f"velocity{index}": flow / (995.586 * math.pi * segment.bore_m ** 2 / 4)})
    return row


def write_csv(path, bound, changed=None):
    row = csv_values(bound)
    row.update(changed or {})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow({**row, "time": 0.0})
        writer.writerow(row)


def install_execution_fixture(tmp_path, monkeypatch, bound, *, changed=None, log_change=None, returncode=0):
    """Inject an explicitly synthetic compiler seam; no production fixture API."""
    compiler = tmp_path / "omc-fixture.exe"
    compiler.write_text("not an executable solver", encoding="utf-8")
    library = tmp_path / "library"
    library.mkdir()
    package = library / "package.mo"
    package.write_text("package Modelica end Modelica;", encoding="utf-8")
    def run(command, directory, timeout_s):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "OpenModelica TEST FIXTURE\n", "")
        result = directory / f"{modelica.MODEL_NAME}_res.csv"
        write_csv(result, bound, changed)
        log = (f"TUBA_MSL_VERSION={modelica.MODELICA_VERSION}\nTUBA_LIBRARY_SOURCE={package.as_posix()}\n"
               f'record SimulationResult\n resultFile = "{result.as_posix()}";\n'
               "LOG_SUCCESS | info | The simulation finished successfully.\nend SimulationResult;\n")
        if log_change:
            log = log_change(log)
        return subprocess.CompletedProcess(command, returncode, log, "")
    monkeypatch.setattr(modelica, "_run_process", run)
    return modelica.OpenModelicaBackend(omc=compiler), package


def test_templates_preserve_measured_arcs_and_apply_each_loss_once():
    source = modelica.modelica_source(bound_fixture())
    assert source.count("Modelica.Fluid.Pipes.StaticPipe") == 2
    assert source.count("Modelica.Fluid.Fittings.SimpleGenericOrifice") == 2
    assert f"length={math.pi * 0.3 / 2}" in source
    assert source.count("zeta=0.2") == 1
    assert "connect(pipe1.port_b, loss1.port_a)" in source
    assert "pressureOut1(unit=\"Pa\") = loss1.port_b.p" in source
    assert "actualStream(pipe0.port_a.h_outflow)" in source
    assert "requireExactVersion=true" in modelica._script(bound_fixture())


@pytest.mark.parametrize("name,value", [("medium", "Modelica.Media.Water.StandardWater"),
                                        ("source_temperature_k", 400.0),
                                        ("sink_pressure_pa", 90_000.0),
                                        ("mass_flow_kg_s", -1.0)])
def test_unsupported_regimes_fail_before_compile(name, value, tmp_path, monkeypatch):
    bound = bound_fixture()
    setattr(bound.scenario, name, value)
    monkeypatch.setattr(modelica, "_run_process", lambda *args: pytest.fail("compiler must not run"))
    with pytest.raises(modelica.ModelicaEvaluationError):
        modelica.OpenModelicaBackend().solve(bound, tmp_path / "attempt")
    assert json.loads((tmp_path / "attempt/manifest.json").read_text())["status"] == "failed"


def test_unchanged_issued_result_verifies_and_is_serializable(tmp_path, monkeypatch):
    bound = bound_fixture()
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    result = backend.solve(bound, tmp_path / "attempt")
    result.verify_for(bound)
    assert [segment.element_id for segment in result.segments] == ["E1", "E2", None]
    assert result.port_pressures_pa["LINE.out"] == 310_000.0
    assert json.loads(json.dumps(result.to_dict()))["provenance"]["modelica_version"] == "4.1.0"
    with pytest.raises(ValueError, match="solve-issued"):
        replace(result, mass_flow_kg_s=9).verify_for(bound)
    with pytest.raises(ValueError, match="solve-issued"):
        replace(result).verify_for(bound)


@pytest.mark.parametrize("artifact", ["csv", "modelica_source", "script", "network", "compiler_log", "compiler_executable"])
def test_modified_or_missing_artifacts_rejected(artifact, tmp_path, monkeypatch):
    bound = bound_fixture()
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    result = backend.solve(bound, tmp_path / "attempt")
    path = Path(result.artifacts[artifact]["path"])
    path.write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or modified"):
        result.verify_for(bound)
    path.unlink()
    with pytest.raises(ValueError, match="missing or modified"):
        result.verify_for(bound)


def test_changed_library_manifest_and_bound_rejected(tmp_path, monkeypatch):
    bound = bound_fixture()
    backend, library = install_execution_fixture(tmp_path, monkeypatch, bound)
    result = backend.solve(bound, tmp_path / "attempt")
    other = bound_fixture()
    other.fingerprint = "changed-bound"
    with pytest.raises(ValueError, match="stale"):
        result.verify_for(other)
    original = library.read_bytes()
    library.write_text("package Changed end Changed;", encoding="utf-8")
    with pytest.raises(ValueError, match="library sources have changed"):
        result.verify_for(bound)
    library.write_bytes(original)
    Path(result.manifest_path).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is missing or modified"):
        result.verify_for(bound)


@pytest.mark.parametrize("changed,match", [({"time": 0.9}, "stop time"),
                                         ({"pressureIn1": math.nan}, "nonfinite"),
                                         ({"massFlowOut1": 9.0}, "mass balance"),
                                         ({"massFlow1": 0.0}, "positive and forward"),
                                         ({"pressureIn1": 319_000.0}, "connection"),
                                         ({"sinkPressure": 299_000.0}, "sink pressure"),
                                         ({"velocity0": 0.1}, "velocity"),
                                         ({"density0": 0.0}, "must be positive"),
                                         ({"temperatureIn0": 293.0}, "source temperature"),
                                         ({"temperatureIn1": 293.0}, "temperature connection"),
                                         ({"temperature1": 370.0}, "single-phase"),
                                         ({"pressureIn0": "invalid"}, "malformed")])
def test_invalid_solver_outputs_are_failure_evidence(changed, match, tmp_path, monkeypatch):
    bound = bound_fixture()
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound, changed=changed)
    with pytest.raises(modelica.ModelicaEvaluationError, match=match):
        backend.solve(bound, tmp_path / "attempt")
    manifest = json.loads((tmp_path / "attempt/manifest.json").read_text())
    assert manifest["status"] == "failed" and "results" not in manifest
    assert (tmp_path / "attempt/compiler.log").is_file()


def test_missing_csv_columns_rejected(tmp_path):
    path = tmp_path / "partial.csv"
    path.write_text("time,sourceMassFlow\n0,10\n1,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        modelica._read_csv(path, bound_fixture())


@pytest.mark.parametrize("log_change,returncode", [
    (lambda log: log.replace("The simulation finished successfully.", "Simulation failed."), 0),
    (lambda log: log.replace("4.1.0", "4.0.0"), 0),
    (lambda log: log.replace("resultFile = \"", "resultFile = \"wrong_"), 0),
    (lambda log: log, 1),
])
def test_csv_alone_never_establishes_success(log_change, returncode, tmp_path, monkeypatch):
    bound = bound_fixture()
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound, log_change=log_change, returncode=returncode)
    with pytest.raises(modelica.ModelicaEvaluationError):
        backend.solve(bound, tmp_path / "attempt")
    assert json.loads((tmp_path / "attempt/manifest.json").read_text())["status"] == "failed"


def test_attempt_directory_cannot_reuse_stale_csv(tmp_path, monkeypatch):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / f"{modelica.MODEL_NAME}_res.csv").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(modelica, "_run_process", lambda *args: pytest.fail("compiler must not run"))
    with pytest.raises(FileExistsError):
        modelica.OpenModelicaBackend().solve(bound_fixture(), attempt)


def test_outputs_reject_other_git_checkouts(tmp_path):
    (tmp_path / ".git").write_text("gitdir: fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="outside the source checkout"):
        modelica.OpenModelicaBackend().solve(bound_fixture(), tmp_path / "attempt")
    assert not (tmp_path / "attempt").exists()


def test_timeout_keeps_diagnostic_and_failed_manifest(tmp_path, monkeypatch):
    compiler = tmp_path / "omc.exe"
    compiler.write_text("fixture", encoding="utf-8")
    def timeout(command, directory, timeout_s):
        raise subprocess.TimeoutExpired(command, timeout_s, output="partial compiler output")
    monkeypatch.setattr(modelica, "_run_process", timeout)
    with pytest.raises(modelica.ModelicaEvaluationError, match="timed out"):
        modelica.OpenModelicaBackend(compiler, timeout_s=0.01).solve(bound_fixture(), tmp_path / "attempt")
    assert "partial compiler output" in (tmp_path / "attempt/compiler.log").read_text()
    assert json.loads((tmp_path / "attempt/manifest.json").read_text())["error_type"] == "TimeoutExpired"


def test_missing_runtime_clear_and_never_returns_results(tmp_path):
    with pytest.raises(modelica.ModelicaEvaluationError, match="compiler unavailable"):
        modelica.OpenModelicaBackend(tmp_path / "nonexistent.exe").solve(bound_fixture(), tmp_path / "attempt")
    assert json.loads((tmp_path / "attempt/manifest.json").read_text())["status"] == "failed"


def test_completed_build_cleanup_preserves_evidence_and_unrelated_files(tmp_path):
    (tmp_path / "manifest.json").write_text('{"status":"succeeded"}', encoding="utf-8")
    generated = [f"{modelica.MODEL_NAME}.c", f"{modelica.MODEL_NAME}.exe", f"{modelica.MODEL_NAME}_01exo.o"]
    retained = [f"{modelica.MODEL_NAME}.mo", f"{modelica.MODEL_NAME}_res.csv",
                f"{modelica.MODEL_NAME}_init.xml", f"{modelica.MODEL_NAME}.log", "unrelated.c", "run.mos"]
    for name in generated + retained:
        (tmp_path / name).write_text("payload", encoding="utf-8")
    removed = modelica.cleanup_completed_modelica_build(tmp_path)
    assert removed["removed_files"] == sorted(generated)
    assert all((tmp_path / name).is_file() for name in retained)
    (tmp_path / "manifest.json").write_text('{"status":"failed"}', encoding="utf-8")
    with pytest.raises(ValueError, match="must retain"):
        modelica.cleanup_completed_modelica_build(tmp_path)
