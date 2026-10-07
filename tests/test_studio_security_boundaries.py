"""Custom review builders must pass the same current-study evidence gate."""
from types import SimpleNamespace

import pytest

from tuba.visualization.preview.server import ProjectStudioServer
from tuba.visualization.scene import VisualizationScene


def test_custom_review_cannot_bypass_current_study_import_gate(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text("from tuba import Model\nmodel=Model('Gate')\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    settings = SimpleNamespace(operations=("Operating",))
    namespace = {"model": server.model}
    called = []
    monkeypatch.setattr(server, "_study_settings", lambda: settings)
    monkeypatch.setattr(server, "_review_builder", lambda: lambda *args, **kwargs: pytest.fail("unverified evidence reached the builder"))
    def reject(observed_namespace, observed_settings, artifact_dir):
        called.append((observed_namespace, observed_settings, artifact_dir))
        raise ValueError("compiler settings differ from current study")
    monkeypatch.setattr("tuba.project.study.import_study_evidence", reject)
    with pytest.raises(ValueError, match="compiler settings differ"):
        server._produce_review_locked(namespace, artifact_dir=tmp_path / "old-evidence")
    assert called == [(namespace, settings, tmp_path / "old-evidence")]


def test_retained_ifc_scene_serialized_quota_blocks_publication(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text("from tuba import Model\nmodel=Model('Quota')\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    monkeypatch.setattr(server, "_ifc_manifests", lambda: [("reference", {"preview": {"name": "Reference", "products": []}, "meshes": {}})])
    monkeypatch.setattr("tuba.visualization.preview.server.MAX_REFERENCE_SCENE_BYTES", 32)
    with pytest.raises(ValueError, match="before publication"):
        server._merge_ifc_references(VisualizationScene(scene_id="scene", model_id="model"))
