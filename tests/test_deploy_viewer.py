import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import deploy_viewer as deploy


def test_complete_review_and_viewer_updates_preserve_the_catalog(tmp_path, monkeypatch):
    shell = tmp_path / "shell"
    (shell / "assets").mkdir(parents=True)
    (shell / "index.html").write_text("viewer", encoding="utf-8")
    (shell / "bundles.json").write_text("[]", encoding="utf-8")
    (shell / "assets" / "old.js").write_text("old", encoding="utf-8")
    monkeypatch.setattr(deploy, "viewer_assets_path", lambda: shell)
    web = tmp_path / "web"
    assert deploy.main(["viewer", str(web)]) == 0

    source = tmp_path / "project-review" / "review_scene"
    (source / "artifacts").mkdir(parents=True)
    (source / "scene.json").write_text("{}", encoding="utf-8")
    (source / "review.json").write_text('{"package_id": "review:tower"}', encoding="utf-8")
    (source / "index.html").write_text("printable report", encoding="utf-8")
    (source / "artifacts" / "old.csv").write_text("old", encoding="utf-8")
    assert deploy.main(["bundle", str(source.parent), str(web)]) == 0
    assert (web / "tower" / "index.html").read_text() == "printable report"
    assert json.loads((web / "bundles.json").read_text()) == ["tower"]

    rich = [{"id": "tower", "title": "Tower", "downloads": {"project": "downloads/tower.zip"}}]
    (web / "bundles.json").write_text(json.dumps(rich), encoding="utf-8")
    (source / "artifacts" / "old.csv").unlink()
    (source / "artifacts" / "new.csv").write_text("new", encoding="utf-8")
    deploy.cmd_bundle(source, web)  # Also accepts a bundle directly, including Studio output.
    assert not (web / "tower" / "artifacts" / "old.csv").exists()
    assert (web / "tower" / "artifacts" / "new.csv").read_text() == "new"
    assert json.loads((web / "bundles.json").read_text()) == rich

    (shell / "assets" / "old.js").unlink()
    (shell / "assets" / "new.js").write_text("new", encoding="utf-8")
    deploy.cmd_viewer(web)
    assert not (web / "assets" / "old.js").exists()
    assert (web / "assets" / "new.js").is_file()
    assert json.loads((web / "bundles.json").read_text()) == rich
    assert (web / "tower" / "index.html").is_file()
    assert not any(path.name.startswith(".") for path in web.iterdir())

    (source / "review.json").write_text('{"package_id": "review:header"}', encoding="utf-8")
    deploy.cmd_bundle(source, web)
    assert json.loads((web / "bundles.json").read_text()) == rich + ["header"]
    assert (web / "tower" / "index.html").is_file()
    assert (web / "header" / "index.html").is_file()


def test_invalid_input_cannot_overwrite_published_or_unrelated_files(tmp_path):
    source, web = tmp_path / "source", tmp_path / "web"
    source.mkdir()
    (source / "scene.json").write_text("{}", encoding="utf-8")
    web.mkdir()
    sentinel = web / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    for package_id in ("review:../escape", "review:/absolute", "review:C:\\escape", "review:",
                       "review:assets", "review:CON", "review:NUL.txt", "review:tower.", 7):
        (source / "review.json").write_text(json.dumps({"package_id": package_id}), encoding="utf-8")
        with pytest.raises(ValueError):
            deploy.cmd_bundle(source, web)
        assert list(web.iterdir()) == [sentinel]
    (source / "review.json").write_text('{"package_id": "review:tower"}', encoding="utf-8")
    catalog = web / "bundles.json"
    for damaged in ("{broken", "{}", '[{"title":"missing id"}]', '["tower", "Tower"]'):
        catalog.write_text(damaged, encoding="utf-8")
        with pytest.raises(ValueError):
            deploy.cmd_bundle(source, web)
        assert catalog.read_text() == damaged
        assert not (web / "tower").exists()
    catalog.write_text("[]", encoding="utf-8")
    (web / "tower").mkdir()
    (web / "tower" / "keep.txt").write_text("unrelated", encoding="utf-8")
    with pytest.raises(ValueError, match="unregistered"):
        deploy.cmd_bundle(source, web)
    assert (web / "tower" / "keep.txt").read_text() == "unrelated"
    with pytest.raises(ValueError, match="non-nested"):
        deploy.cmd_bundle(source, source)
    assert sentinel.read_text() == "keep"


def test_copy_or_catalog_failure_restores_the_previous_bundle(tmp_path, monkeypatch):
    source, web = tmp_path / "source", tmp_path / "web"
    source.mkdir()
    (source / "scene.json").write_text("{}", encoding="utf-8")
    (source / "review.json").write_text('{"package_id": "review:tower"}', encoding="utf-8")
    (source / "index.html").write_text("new report", encoding="utf-8")
    (web / "tower").mkdir(parents=True)
    (web / "tower" / "index.html").write_text("old report", encoding="utf-8")
    (web / "bundles.json").write_text('["tower"]', encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise OSError("copy interrupted")

    replace = Path.replace

    def fail_catalog(path, target):
        if path.name == "catalog.json":
            raise OSError("catalog write interrupted")
        return replace(path, target)

    for target, name, failure in ((deploy.shutil, "copytree", fail_copy), (Path, "replace", fail_catalog)):
        with monkeypatch.context() as patch:
            patch.setattr(target, name, failure)
            with pytest.raises(OSError, match="interrupted"):
                deploy.cmd_bundle(source, web)
        assert (web / "tower" / "index.html").read_text() == "old report"
        assert (web / "bundles.json").read_text() == '["tower"]'
        assert sorted(path.name for path in web.iterdir()) == ["bundles.json", "tower"]


def test_symlink_or_windows_junction_is_refused_before_copying(tmp_path):
    source, web, outside = tmp_path / "source", tmp_path / "web", tmp_path / "outside"
    source.mkdir()
    web.mkdir()
    outside.mkdir()
    (source / "scene.json").write_text("{}", encoding="utf-8")
    (source / "review.json").write_text('{"package_id": "review:tower"}', encoding="utf-8")
    (web / "bundles.json").write_text('["tower"]', encoding="utf-8")
    link = web / "tower"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="linked path"):
            deploy.cmd_bundle(source, web)
        assert not list(outside.iterdir())
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
