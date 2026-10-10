import hashlib
import json
from pathlib import Path

import pytest

from tuba.model import TubaModel
from tuba.project import Project
from tuba.search.artifacts import ArtifactStore
from tuba.search.contracts import Candidate
from tuba.search.history import History


def test_rejected_attempt_retains_bytes_and_detects_damage(tmp_path):
    root = tmp_path / "run"
    store = ArtifactStore(root)
    attempt = store.begin_attempt("C")
    folder = store.operation_dir(attempt, "Hot")
    (folder / "diagnostic.txt").write_bytes(b"not a solver result")
    ref = store.seal_attempt(attempt, "failed")
    inventory = ArtifactStore(root).verify_inventory(ref)
    entry = next(f for f in inventory["files"] if f["path"].endswith("diagnostic.txt"))
    assert entry["size_bytes"] == 19
    assert entry["sha256"] == hashlib.sha256(b"not a solver result").hexdigest()
    assert inventory["status"] == "failed"
    (folder / "diagnostic.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        store.verify_inventory(ref)


@pytest.mark.parametrize("reference", ["../escape", "/absolute", "C:/escape", "a\\..\\b"])
def test_unsafe_references_are_refused(tmp_path, reference):
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path).path(reference)


def test_symlink_is_not_followed(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    root = tmp_path / "run"
    root.mkdir()
    try:
        (root / "link").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit creating a symlink")
    with pytest.raises(ValueError, match="link|reparse"):
        ArtifactStore(root).path("link/output.txt")


def test_capture_only_explicit_sources_and_share_identical_bytes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    for name in ("model.py", "study.py", "search.py", "helper.py"):
        (project / name).write_text("# source\n")
    (project / ".scratch").mkdir()
    (project / ".scratch/old.zip").write_bytes(b"discard")
    store = ArtifactStore(tmp_path / "run")
    ref = store.capture_source(Project(project), (project / "helper.py",))
    assert ref == store.capture_source(Project(project), (project / "helper.py",))
    inventory = json.loads(store.path(ref).read_text())
    assert {f["logical_name"] for f in inventory["files"]} == {"model.py", "study.py", "search.py", "helper.py"}
    assert not list(store.root.rglob("*.zip"))
    with pytest.raises(ValueError):
        store.capture_source(Project(project), (project / ".scratch/old.zip",))
    with pytest.raises(FileNotFoundError):
        store.capture_source(Project(project), (project / "missing.step",))


def test_model_is_archived_without_rewriting_authored_source(tmp_path):
    store = ArtifactStore(tmp_path)
    model = TubaModel("Diagnostic")
    ref = store.save_model("C", model)
    assert json.loads(store.path(ref).read_text()) == model.to_dict()
    with pytest.raises(FileExistsError):
        store.save_model("C", model)


@pytest.mark.parametrize("sealed", [False, True])
def test_recovery_preserves_orphan_artifacts_and_is_idempotent(tmp_path, sealed):
    store = ArtifactStore(tmp_path)
    with History.create(tmp_path / "history.sqlite3", {"schema": "tuba.search.history.v1", "run_id": "R"}) as h:
        h.record_candidate(Candidate("C", (), {}, "Trial"))
        attempt = store.begin_attempt("C")
        (store.operation_dir(attempt, "Hot") / "diagnostic.txt").write_text("partial output")
        if sealed:
            store.seal_attempt(attempt, "complete")
        assert store.recover(h) == [attempt]
        assert store.recover(h) == []
        assert h.events()[-1]["kind"] == "attempt.recovered"
        assert store.verify_inventory(f"attempts/{attempt}/inventory.json")["candidate_id"] == "C"


def test_full_disk_seal_preserves_output_and_recovery_can_retry(tmp_path, monkeypatch):
    store = ArtifactStore(tmp_path)
    attempt = store.begin_attempt("C")
    folder = store.operation_dir(attempt, "Hot")
    (folder / "diagnostic.txt").write_text("retained")
    import tuba.search.artifacts as artifacts
    original = artifacts.atomic_json
    def fail(*args, **kwargs):
        raise OSError("No space left on device")
    monkeypatch.setattr(artifacts, "atomic_json", fail)
    with pytest.raises(OSError):
        store.seal_attempt(attempt, "failed")
    assert (folder / "diagnostic.txt").read_text() == "retained"
    monkeypatch.setattr(artifacts, "atomic_json", original)
    assert store.seal_attempt(attempt, "interrupted")


def test_source_copy_interruption_reuses_completed_bytes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    for name in ("model.py", "study.py", "search.py"):
        (project / name).write_text("# source\n")
    store = ArtifactStore(tmp_path / "run")
    import tuba.search.artifacts as artifacts
    original = artifacts.atomic_json
    monkeypatch.setattr(artifacts, "atomic_json", lambda *a, **k: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError):
        store.capture_source(Project(project), ())
    assert len(list((store.root / "source").rglob("*.py"))) == 3
    monkeypatch.setattr(artifacts, "atomic_json", original)
    store.verify_inventory(store.capture_source(Project(project), ()))


def test_recovery_retries_event_transaction_without_rewriting_inventory(tmp_path, monkeypatch):
    store = ArtifactStore(tmp_path)
    with History.create(tmp_path / "history.sqlite3", {"schema": "tuba.search.history.v1", "run_id": "R"}) as h:
        h.record_candidate(Candidate("C", (), {}, "Trial"))
        attempt = store.begin_attempt("C")
        ref = store.seal_attempt(attempt, "complete")
        before = store.path(ref).read_bytes()
        original = h.append
        monkeypatch.setattr(h, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("recorder interrupted")))
        with pytest.raises(OSError):
            store.recover(h)
        assert store.path(ref).read_bytes() == before
        monkeypatch.setattr(h, "append", original)
        assert store.recover(h) == [attempt]
