"""Freshness: a solve's expected identity comes from the exporters' own code (spec decision 15)."""

import json
from pathlib import Path

import pytest

from tuba import Model
from tuba.analysis.provenance import SolverInputIdentity
from tuba.project import run_model_script
from tuba.project.freshness import attested_identities, expected_identity, export_study, stale_operations
from tuba.solver.aster import CodeAsterSolver

SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"


def _hot_line():
    model = Model("FreshnessLine")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1143, WT=0.00602)
    with model.pipe(section="Pipe", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(2.0)
        builder.end(support="anchor")
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model


def _pressure_pipe():
    model = Model("FreshnessVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.2, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
    model.add_support(n0, type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
    return model


def _rack(tmp_path: Path, edit=lambda text: text):
    """The support-rack model, built from a copy of its model.py with *edit* applied."""
    script = tmp_path / "model.py"
    script.write_text(edit((SUPPORT_RACK / "model.py").read_text(encoding="utf-8")), encoding="utf-8")
    return run_model_script(script)["model"]


def _rack_attestation() -> list[SolverInputIdentity]:
    record = json.loads((SUPPORT_RACK / "evidence" / "Operating" / "study_execution.json").read_text(encoding="utf-8"))
    return [SolverInputIdentity.from_dict(record["solver_input_identity"])]


@pytest.mark.parametrize("options", [{}, {"pipe_modelization": "POU_D_T", "line_segments": 4}])
def test_expected_identity_is_the_identity_a_beam_export_writes(tmp_path, options):
    model = _hot_line()

    study = export_study(CodeAsterSolver(**options), model, "Hot", tmp_path, None)

    assert expected_identity(model, "Hot", solver_options=options) == study.solver_input_identity


def test_expected_identity_is_the_identity_a_volume_export_writes(tmp_path):
    model = _pressure_pipe()
    volume = {"element_ids": ["pipe_0"], "max_element_size": 0.005}

    study = export_study(CodeAsterSolver(), model, "Pressure", tmp_path, volume)

    assert expected_identity(model, "Pressure", volume_export=volume) == study.solver_input_identity


def test_volume_study_inputs_refuse_a_load_path_like_the_volume_export():
    with pytest.raises(ValueError, match="load paths"):
        CodeAsterSolver(pipe_modelization="POU_D_T", load_path=["Pressure"]).volume_study_inputs(
            _pressure_pipe(), "Pressure", element_ids=["pipe_0"], max_element_size=0.005
        )


def test_expected_identity_never_meshes(monkeypatch):
    import tuba.solver.aster_volume as aster_volume

    def refuse(*args, **kwargs):
        raise AssertionError("expected_identity must not mesh")

    monkeypatch.setattr(aster_volume, "build_pipe_volume_mesh", refuse)

    identity = expected_identity(
        _pressure_pipe(), "Pressure", volume_export={"element_ids": ["pipe_0"], "max_element_size": 0.005}
    )

    assert identity.compiler_id == "tuba.code_aster.volume.v2"


def test_committed_support_rack_evidence_is_fresh(tmp_path):
    assert stale_operations(_rack(tmp_path), _rack_attestation()) == []


def test_a_rename_or_an_unsolved_load_case_leaves_the_evidence_fresh(tmp_path):
    model = _rack(
        tmp_path,
        lambda text: text.replace('Model("SupportRackReview")', 'Model("RenamedRack")')
        + 'model.define_load_case("Hydrotest", gravity=True, pressure=2.0e6)\n',
    )

    assert stale_operations(model, _rack_attestation()) == []


def test_a_moved_node_makes_the_operation_stale(tmp_path):
    model = _rack(tmp_path, lambda text: text.replace("(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)"))

    assert stale_operations(model, _rack_attestation()) == ["Operating"]


def test_a_changed_study_solver_option_makes_the_operation_stale(tmp_path):
    assert stale_operations(_rack(tmp_path), _rack_attestation(), solver_options={"line_segments": 4}) == ["Operating"]


def test_invalid_study_solver_options_raise_instead_of_reading_as_stale(tmp_path):
    with pytest.raises(ValueError, match="line_segments"):
        stale_operations(_rack(tmp_path), _rack_attestation(), solver_options={"line_segments": 0})


def test_an_operation_the_model_no_longer_defines_is_stale(tmp_path):
    model = _rack(tmp_path, lambda text: text.replace('"Operating",', '"Cold",'))

    assert stale_operations(model, _rack_attestation()) == ["Operating"]


def test_attested_identities_come_from_the_review_scene(tmp_path):
    identity = {
        "fingerprint": "f" * 64,
        "load_case": "Operating",
        "schema_id": "tuba.model.v4",
        "compiler_id": "tuba.code_aster.v2",
    }
    (tmp_path / "scene.json").write_text(json.dumps({"solver_input_identities": [identity]}), encoding="utf-8")

    assert attested_identities(tmp_path) == [SolverInputIdentity.from_dict(identity)]
    assert attested_identities(tmp_path / "missing") == []
