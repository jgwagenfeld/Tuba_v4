"""Staging an Analysis run's Evidence into a review bundle, and reading it back (spec decisions 14 and 22)."""

import json
import shutil
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import operation_folder_name, read_staged_runs, stage_runs
from tuba.project import load_project
from tuba.reporting import build_engineering_review
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _run(tmp_path, example, operation):
    """One committed Evidence folder, copied out of the repository and imported."""
    source = EXAMPLES / example / "evidence" / operation
    work_dir = tmp_path / "evidence" / operation
    shutil.copytree(source, work_dir)
    model = load_project(EXAMPLES / example).run_model()["model"]
    return import_code_aster_artifacts(model=model, work_dir=work_dir)


def _bundle(tmp_path, example="support-rack-review", operation="Operating"):
    """A real review bundle: committed Evidence, staged, with a scene and a review written over it."""
    run = _run(tmp_path, example, operation)
    model = load_project(EXAMPLES / example).run_model()["model"]
    root = tmp_path / "bundle"
    staged = stage_runs({operation: run}, root)[operation]
    scene = build_visualization_scene(model, analysis_runs=[staged], scene_id="scene:test")
    review = build_engineering_review(model, analysis_runs=[staged], package_id="review:test")
    write_engineering_review_with_scene(review, root, scene=scene, title="Staged run test")
    return root


def _edit_review(bundle, change):
    """Rewrite a bundle's review.json through *change*, the way a tampered bundle would arrive."""
    path = bundle / "review.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    change(review)
    path.write_text(json.dumps(review), encoding="utf-8")


def _result_state(review):
    return next(item for item in review["provenance"] if item["kind"] == "result_state")


def _repoint(bundle, role, uri):
    def change(review):
        _result_state(review)["files"][role] = uri

    _edit_review(bundle, change)


def test_a_run_lands_in_the_folder_its_operation_names(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")
    bundle = tmp_path / "bundle"

    staged = stage_runs({"Operating": run}, bundle)

    folder = bundle / "artifacts" / "Operating"
    attested = set(run.result_state.metadata["solve_attestation"]["artifacts"])
    assert {path.name for path in folder.iterdir()} == attested | {"study_execution.json"}
    assert staged["Operating"].study.work_dir is None
    assert staged["Operating"].result_state.files["execution"] == "artifacts/Operating/study_execution.json"
    # Unattested files stay behind: the solver's own listing and its logs.
    assert not (folder / "study.resu").exists()


def test_every_operation_gets_its_own_folder(tmp_path):
    runs = {case: _run(tmp_path, "profile-orientation-review", case) for case in ("global", "local")}
    bundle = tmp_path / "bundle"

    staged = stage_runs(runs, bundle)

    assert sorted(path.name for path in (bundle / "artifacts").iterdir()) == ["global", "local"]
    for case in ("global", "local"):
        assert staged[case].result_state.files["mess"] == f"artifacts/{case}/study.mess"


def test_a_key_that_is_not_the_runs_operation_is_refused(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")

    with pytest.raises(ValueError, match="attested for 'Operating'"):
        stage_runs({"Hot": run}, tmp_path / "bundle")


def test_two_operations_claiming_one_folder_are_refused(tmp_path):
    # The refusal comes before any run is touched, so the runs need not exist.
    with pytest.raises(ValueError, match="claim one bundle folder"):
        stage_runs({"Hot": None, "hot": None}, tmp_path / "bundle")


@pytest.mark.parametrize("name", ["", "a/b", "Hot:Cold", "CON", "Hot ", "x" * 256])
def test_an_operation_that_cannot_name_a_folder_is_refused(name):
    with pytest.raises(ValueError, match="cannot name"):
        operation_folder_name(name)


def test_a_staged_bundle_reads_back_as_its_runs(tmp_path):
    bundle = _bundle(tmp_path)

    (run,) = read_staged_runs(bundle)

    assert (run.operation, run.folder) == ("Operating", "artifacts/Operating")
    assert run.trust == "verified"
    assert run.modelization == "TUYAU_3M"
    assert run.contact is True                      # the rack rests on friction shoes
    assert "study.rmed" in run.inventory
    # Two roles may share one attested file.
    assert run.files["sieq"] == run.files["tuyau_subpoints"] == "artifacts/Operating/study_sieq.csv"
    assert run.path("mess").read_text(encoding="utf-8", errors="ignore")


def test_a_bundle_without_a_review_holds_no_runs(tmp_path):
    (tmp_path / "empty").mkdir()

    assert read_staged_runs(tmp_path / "empty") == ()


def test_a_role_pointing_outside_its_run_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    decoy = bundle / "artifacts" / "decoy"
    decoy.mkdir(parents=True)
    (decoy / "study.rmed").write_bytes((bundle / "artifacts" / "Operating" / "study.rmed").read_bytes())
    _repoint(bundle, "rmed", "artifacts/decoy/study.rmed")

    with pytest.raises(ValueError, match="role 'rmed' names"):
        read_staged_runs(bundle)


def test_an_unattested_file_in_the_folder_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "artifacts" / "Operating" / "study.resu").write_text("left behind", encoding="utf-8")

    with pytest.raises(ValueError, match="carries 'study.resu'"):
        read_staged_runs(bundle)


def test_a_renamed_folder_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "artifacts" / "Operating").rename(bundle / "artifacts" / "Renamed")

    def change(review):
        for record in review["provenance"]:
            record["files"] = {
                role: uri.replace("artifacts/Operating/", "artifacts/Renamed/")
                for role, uri in record["files"].items()
            }

    _edit_review(bundle, change)

    with pytest.raises(ValueError, match="Bundle folder 'artifacts/Renamed'"):
        read_staged_runs(bundle)


def test_one_changed_byte_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    mess = bundle / "artifacts" / "Operating" / "study.mess"
    mess.write_bytes(mess.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="study.mess size does not match"):
        read_staged_runs(bundle)


def test_a_record_without_a_solver_identity_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    _edit_review(bundle, lambda review: _result_state(review)["metadata"].pop("solver_input_identity"))

    with pytest.raises(ValueError, match="carries no solver input identity"):
        read_staged_runs(bundle)


def test_a_run_missing_its_mesh_record_is_refused(tmp_path):
    bundle = _bundle(tmp_path)

    def change(review):
        review["provenance"] = [
            record for record in review["provenance"] if record["kind"] != "analysis_mesh"
        ]

    _edit_review(bundle, change)

    with pytest.raises(ValueError, match="missing its analysis_mesh"):
        read_staged_runs(bundle)


def test_a_run_without_its_execution_envelope_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    _edit_review(bundle, lambda review: _result_state(review)["files"].pop("execution"))

    with pytest.raises(ValueError, match="no 'execution' envelope"):
        read_staged_runs(bundle)


def test_a_hash_in_the_review_is_not_read(tmp_path):
    """The attestation is the only hash record, so review.json's own copy decides nothing."""
    bundle = _bundle(tmp_path)
    _edit_review(
        bundle,
        lambda review: _result_state(review)["metadata"]["file_sha256"].update({"mess": "0" * 64}),
    )

    (run,) = read_staged_runs(bundle)

    assert run.path("mess").is_file()


def test_two_operations_read_back_as_two_runs(tmp_path):
    runs = {case: _run(tmp_path, "profile-orientation-review", case) for case in ("global", "local")}
    model = load_project(EXAMPLES / "profile-orientation-review").run_model()["model"]
    root = tmp_path / "bundle"
    staged = stage_runs(runs, root)
    scene = build_visualization_scene(model, analysis_runs=list(staged.values()), scene_id="scene:two")
    review = build_engineering_review(model, analysis_runs=list(staged.values()), package_id="review:two")
    write_engineering_review_with_scene(review, root, scene=scene, title="Two operations")

    assert [run.operation for run in read_staged_runs(root)] == ["global", "local"]
