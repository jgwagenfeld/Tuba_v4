"""The studio opens a project folder, never a bare model file."""

from pathlib import Path
import threading

import pytest

from tuba import cli_studio


def test_the_studio_refuses_anything_but_a_project_folder(tmp_path: Path, capsys):
    model_json = tmp_path / "model.json"
    model_json.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        cli_studio.main([str(model_json), "--no-open"])

    assert exit_info.value.code == 2
    assert "project folder" in capsys.readouterr().err


class IdleServer:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.base_url = "http://127.0.0.1:54321/"
        self.ws_url = "ws://127.0.0.1:54321/preview/ws"
        self._stop = threading.Event()
        self._stop.set()
        self.started = self.stopped = False
        self.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def open_project(self, path):
        self.opened = path


def test_no_project_launches_welcome_and_explicit_folder_keeps_cli_semantics(tmp_path, monkeypatch):
    IdleServer.instances = []
    monkeypatch.setattr(cli_studio, "StudioLauncher", IdleServer)
    monkeypatch.setattr(cli_studio, "ProjectStudioServer", IdleServer)
    monkeypatch.setattr(cli_studio, "studio_session", lambda root: None)
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "my project ü"
    root.mkdir()
    (root / "model.py").write_text("from tuba import Model\nmodel = Model('demo')\n", encoding="utf-8")
    assert cli_studio.main(["--no-open"]) == 0
    assert IdleServer.instances[0].args == (Path(".tuba") / "studio",)
    assert cli_studio.main([str(root), "--no-open", "--port", "0"]) == 0
    direct_launcher, studio = IdleServer.instances[1:]
    assert studio.args[0] == root.resolve()
    assert studio.args[1].parent == tmp_path / ".build" / "studio"
    assert studio.kwargs["port"] == 0
    assert studio.launcher_url == direct_launcher.base_url
    assert direct_launcher.opened == str(root.resolve())
    assert all(server.started and server.stopped for server in IdleServer.instances)
    assert not (root / "study.py").exists()


def test_existing_session_is_opened_without_starting_or_stopping_it(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text("from tuba import Model\nmodel = Model('demo')\n", encoding="utf-8")
    url = "http://127.0.0.1:57243/?bundle=build"
    monkeypatch.setattr(cli_studio, "studio_session", lambda path: {"viewer_url": url})
    monkeypatch.setattr(cli_studio, "ProjectStudioServer", lambda *args, **kwargs: pytest.fail("Must reuse existing session"))
    opened = []
    monkeypatch.setattr(cli_studio.webbrowser, "open", opened.append)
    assert cli_studio.main([str(root)]) == 0
    assert opened == [url]
    assert url in capsys.readouterr().out


@pytest.mark.parametrize("suffix", [".tubaproject", ".tgz", ".tar.gz"])
def test_cli_opens_a_package_in_an_explicit_new_working_folder(tmp_path, monkeypatch, capsys, suffix):
    from tuba.project.package import export_project_package
    root = tmp_path / "source"
    root.mkdir()
    (root / "model.py").write_text("from tuba import Model\nmodel = Model('demo')\n", encoding="utf-8")
    archive = tmp_path / ("shared" + suffix)
    export_project_package(root, archive)
    destination = tmp_path / "new working folder"
    monkeypatch.setattr(cli_studio, "StudioLauncher", IdleServer)
    monkeypatch.setattr(cli_studio, "ProjectStudioServer", IdleServer)
    monkeypatch.setattr(cli_studio, "studio_session", lambda root: None)
    assert cli_studio.main([str(archive), "--extract-to", str(destination), "--no-open"]) == 0
    assert IdleServer.instances[-1].args[0] == destination
    assert "Extracted project" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli_studio.main([str(archive), "--extract-to", str(destination), "--no-open"])
    if suffix == ".tar.gz":
        assert cli_studio.main([str(archive), "--no-open"]) == 0
        assert (tmp_path / "shared" / "model.py").is_file()
        assert not (tmp_path / "shared.tar").exists()


def test_cli_refuses_external_host(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli_studio.main(["--host", "0.0.0.0", "--no-open"])
    assert "localhost" in capsys.readouterr().err


def test_startup_failure_stops_owned_launcher_and_studio(tmp_path, monkeypatch):
    IdleServer.instances = []
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text("from tuba import Model\nmodel = Model('demo')\n", encoding="utf-8")
    monkeypatch.setattr(cli_studio, "StudioLauncher", IdleServer)
    monkeypatch.setattr(cli_studio, "studio_session", lambda path: None)

    class FailedStudio(IdleServer):
        def start(self):
            raise RuntimeError("startup failed")

    monkeypatch.setattr(cli_studio, "ProjectStudioServer", FailedStudio)
    with pytest.raises(RuntimeError, match="startup failed"):
        cli_studio.main([str(root), "--no-open"])
    assert all(server.stopped for server in IdleServer.instances)
