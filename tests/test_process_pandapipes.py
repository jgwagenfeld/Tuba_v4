"""Real hydraulic smoke and evidence guards; structural qualification is separate."""

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from examples.process_network.model import build_model, process_inputs
from tuba.process import modelica, pandapipes


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory):
    pytest.importorskip("pandapipes")
    bound = process_inputs(build_model({"size": "larger", "offset_m": 1.0}))
    result = pandapipes.PandapipesBackend().solve(bound, tmp_path_factory.mktemp("real") / "hydraulics")
    return bound, result


def test_saved_real_results_verify_without_modelica(evaluated, monkeypatch):
    bound, result = evaluated
    monkeypatch.setattr(modelica, "_run_process", lambda *args: pytest.fail("Must not execute Modelica"))
    result.verify_for(bound)
    assert result.provenance["solver"] == "pandapipes"
    assert result.source_pressure_pa > result.sink_pressure_pa
    assert result.mass_flow_kg_s == pytest.approx(10.0)
    assert len(result.segments) == len(bound.segments)
    assert all(row.velocity_m_s > 0 for row in result.segments)
    assert json.loads(Path(result.manifest_path).read_text())["status"] == "succeeded"


@pytest.mark.parametrize("artifact", ["csv", "solver_network", "solver_input", "solver_log", "dependency_identity"])
def test_changed_raw_artifact_is_refused(evaluated, artifact):
    bound, result = evaluated
    path = Path(result.artifacts[artifact]["path"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"\nmodified")
        with pytest.raises(ValueError, match="missing or modified"):
            result.verify_for(bound)
    finally:
        path.write_bytes(original)


def test_stale_geometry_and_copied_measurements_are_refused(evaluated):
    bound, result = evaluated
    changed = process_inputs(build_model({"size": "larger", "offset_m": 2.0}))
    with pytest.raises(ValueError, match="stale"):
        result.verify_for(changed)
    with pytest.raises(ValueError, match="issued"):
        replace(result, source_pressure_pa=result.source_pressure_pa + 1000).verify_for(bound)


def test_changed_runtime_identity_is_refused(evaluated, monkeypatch):
    bound, result = evaluated
    monkeypatch.setattr(pandapipes, "_dependency_identity", lambda: {"changed": True})
    with pytest.raises(ValueError, match="runtime/dependency code has changed"):
        result.verify_for(bound)


def test_missing_optional_runtime_has_install_instruction(monkeypatch):
    monkeypatch.setitem(sys.modules, "pandapipes", None)
    with pytest.raises(pandapipes.PandapipesEvaluationError, match=r"tuba\[process\]"):
        pandapipes._runtime()


def test_laminar_case_is_refused_before_pipeflow(tmp_path, monkeypatch):
    pp = pytest.importorskip("pandapipes")
    bound = process_inputs(build_model({"size": "larger", "offset_m": 1.0}))
    bound = replace(bound, scenario=replace(bound.scenario, mass_flow_kg_s=0.01))
    monkeypatch.setattr(pp, "pipeflow", lambda *args, **kwargs: pytest.fail("Unsupported flow must not execute"))
    with pytest.raises(pandapipes.PandapipesEvaluationError, match="Reynolds"):
        pandapipes.PandapipesBackend().solve(bound, tmp_path / "failed")
    assert json.loads((tmp_path / "failed/manifest.json").read_text())["status"] == "failed"


def test_solver_exception_retains_failed_attempt(tmp_path, monkeypatch):
    pp = pytest.importorskip("pandapipes")
    bound = process_inputs(build_model({"size": "larger", "offset_m": 1.0}))
    def fail(*args, **kwargs):
        raise RuntimeError("Injected solver failure for error-path test")
    monkeypatch.setattr(pp, "pipeflow", fail)
    with pytest.raises(pandapipes.PandapipesEvaluationError, match="Injected solver failure"):
        pandapipes.PandapipesBackend().solve(bound, tmp_path / "failed")
    manifest = json.loads((tmp_path / "failed/manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert "results" not in manifest
    assert "Injected solver failure" in (tmp_path / "failed/solver.log").read_text()
