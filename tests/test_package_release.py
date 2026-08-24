from pathlib import Path
from hashlib import sha256
from email.parser import BytesParser
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from scripts import prepare_release
from scripts.release_candidate import changed_paths, create_candidate_tree
from scripts.verify_release_wheel import _install_wheel


ROOT = Path(__file__).resolve().parents[1]


def _npm():
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None and os.name == "nt":
        npm = str(Path(os.environ["ProgramFiles"]) / "nodejs" / "npm.cmd")
    return npm


def _viewer_files(root: Path) -> dict[str, str]:
    viewer = root / "tuba" / "visualization" / "_viewer"
    return {
        path.relative_to(viewer).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in viewer.rglob("*")
        if path.is_file()
    }


def _referenced_viewer_assets(package_root: Path) -> set[str]:
    html = (package_root / "index.html").read_text(encoding="utf-8")
    referenced = set(re.findall(r"\./assets/([^\"']+\.(?:js|css))", html))
    for stylesheet in tuple(referenced):
        if not stylesheet.endswith(".css"):
            continue
        css = (package_root / "assets" / stylesheet).read_text(encoding="utf-8")
        referenced.update(re.findall(r"url\(\./([^\"')]+\.woff2?)\)", css))
    return referenced


# Every subprocess below decodes as UTF-8 explicitly. Left to the platform
# default, Windows uses cp1252 and a single non-ASCII byte in pip output makes
# the decode fail, so captured stderr arrives as None and the assertion that
# reads it dies with a TypeError instead of reporting the real result.
def _build_wheel(root: Path, wheel_dir: Path) -> Path:
    subprocess.run(
        [
            shutil.which("uv") or "uv",
            "build",
            "--wheel",
            "--no-sources",
            "--out-dir",
            wheel_dir,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return next(wheel_dir.glob("*.whl"))


def _add_unavailable_dependency(wheel: Path, destination: Path) -> Path:
    destination.mkdir()
    modified = destination / wheel.name
    requirement = (
        b"Requires-Dist: tuba-release-missing-dependency @ "
        b"file:///tuba-release-missing-dependency-0-py3-none-any.whl"
    )
    with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(modified, "w") as target:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if entry.filename.endswith(".dist-info/METADATA"):
                newline = b"\r\n" if b"\r\n" in data else b"\n"
                separator = newline + newline
                headers, body = data.split(separator, 1)
                data = headers + newline + requirement + separator + body
                requirement_value = requirement.decode().removeprefix("Requires-Dist: ")
                assert requirement_value in BytesParser().parsebytes(data).get_all("Requires-Dist")
            target.writestr(entry, data)
    return modified


def _project():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _git_paths(root: Path, *args: str) -> set[str]:
    output = subprocess.run(
        ["git", *args, "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode()
    return {path for path in output.split("\0") if path}


def _candidate_diff_paths(root: Path, tree: str) -> set[str]:
    return _git_paths(root, "diff", "--no-renames", "--name-only", "HEAD", tree)


def test_distribution_declares_lgpl_license():
    project = _project()

    assert project["license"] == "LGPL-3.0-or-later"
    assert (ROOT / "LICENSE").is_file()


def test_heavy_geometry_readers_are_optional():
    project = _project()
    dependencies = " ".join(project["dependencies"]).lower()

    assert "scipy" not in dependencies
    assert "meshio" not in dependencies
    assert "trimesh" not in dependencies
    assert "python-fcl" not in dependencies
    assert {"collision", "viz"} <= set(project["optional-dependencies"])


def test_collision_extra_uses_python_310_to_312_wheel_floor():
    assert "python-fcl>=0.7.0.11" in _project()["optional-dependencies"]["collision"]


def test_course_extra_includes_dependencies_used_by_all_notebooks():
    course = _project()["optional-dependencies"]["course"]

    assert "h5py>=3.10" in course
    assert "python-fcl>=0.7.0.11" in course


def test_validation_workflows_exist():
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_installed_distribution_owns_the_web_viewer():
    from tuba.visualization import viewer_assets_path

    assets = viewer_assets_path()
    assert assets.joinpath("index.html").is_file()
    assert any(assets.joinpath("assets").glob("*.js"))


def test_viewer_production_build_synchronizes_the_python_package():
    subprocess.run([_npm(), "run", "build"], cwd=ROOT / "viewer", check=True)

    package_root = ROOT / "tuba" / "visualization" / "_viewer"
    referenced_assets = _referenced_viewer_assets(package_root)
    built_assets = {path.name for path in (package_root / "assets").iterdir() if path.is_file()}

    assert any(path.endswith((".js", ".css")) for path in referenced_assets)
    assert any(path.endswith((".woff", ".woff2")) for path in referenced_assets)
    assert built_assets == referenced_assets
    assert {path.name for path in package_root.iterdir()} == {
        "assets",
        "bundles.json",
        "favicon.svg",
        "index.html",
        "licenses",
    }
    source_licenses = ROOT / "viewer" / "public" / "licenses"
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in (package_root / "licenses").iterdir()
        if path.is_file()
    } == {
        path.name: path.read_text(encoding="utf-8")
        for path in source_licenses.iterdir()
        if path.is_file()
    }
    assert json.loads((package_root / "bundles.json").read_text(encoding="utf-8")) == []


def test_distribution_declares_viewer_console_script():
    assert _project()["scripts"]["tuba-viewer"] == "tuba.visualization.viewer:main"


def test_prepare_release_fails_when_stale_build_cannot_be_removed(tmp_path, monkeypatch):
    (tmp_path / "build").mkdir()
    (tmp_path / "viewer").mkdir()
    monkeypatch.setattr(prepare_release, "ROOT", tmp_path)
    monkeypatch.setattr(prepare_release.shutil, "which", lambda _command: "npm")
    monkeypatch.setattr(prepare_release.subprocess, "run", lambda *_args, **_kwargs: None)

    def locked_build(_path, *, ignore_errors=False):
        if not ignore_errors:
            raise PermissionError("stale build is locked")

    monkeypatch.setattr(prepare_release.shutil, "rmtree", locked_build)

    with pytest.raises(PermissionError, match="stale build is locked"):
        prepare_release.main()


def test_prepare_release_retries_transient_nonempty_build_directory(tmp_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    (tmp_path / "viewer").mkdir()
    monkeypatch.setattr(prepare_release, "ROOT", tmp_path)
    monkeypatch.setattr(prepare_release.shutil, "which", lambda _command: "npm")
    monkeypatch.setattr(prepare_release.subprocess, "run", lambda *_args, **_kwargs: None)
    attempts = 0

    def transient_nonempty(path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError(errno.ENOTEMPTY, "directory is not empty")
        Path(path).rmdir()

    monkeypatch.setattr(prepare_release.shutil, "rmtree", transient_nonempty)

    assert prepare_release.main() == 0
    assert attempts == 2


def test_release_wheel_dependency_install_uses_uv_and_has_a_hard_timeout(monkeypatch, tmp_path):
    observed = {}

    def stalled(command, **kwargs):
        observed.update(command=command, kwargs=kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", stalled)

    with pytest.raises(RuntimeError, match="dependency installation exceeded 300 seconds"):
        _install_wheel(tmp_path / "python", tmp_path / "tuba.whl", tmp_path, {})

    assert observed["command"][1:3] == ["pip", "install"]
    assert observed["command"][3:5] == ["--python", str(tmp_path / "python")]
    assert "--no-deps" not in observed["command"]
    assert observed["kwargs"]["timeout"] == 300


def test_release_wheel_dependency_install_reports_uv_failure(monkeypatch, tmp_path):
    def failed(command, **_kwargs):
        raise subprocess.CalledProcessError(2, command, stderr="uv install failed")

    monkeypatch.setattr(subprocess, "run", failed)

    with pytest.raises(RuntimeError, match="uv install failed"):
        _install_wheel(tmp_path / "python", tmp_path / "tuba.whl", tmp_path, {})


def test_built_wheel_launcher_serves_exact_packaged_assets(tmp_path):
    subprocess.run([sys.executable, ROOT / "scripts" / "prepare_release.py"], check=True)

    wheel_dir = tmp_path / "wheel"
    wheel = _build_wheel(ROOT, wheel_dir)
    with zipfile.ZipFile(wheel) as archive:
        packaged = {
            name.removeprefix("tuba/visualization/_viewer/")
            for name in archive.namelist()
            if name.startswith("tuba/visualization/_viewer/")
        }
        assert json.loads(archive.read("tuba/visualization/_viewer/bundles.json")) == []
    expected = {
        path.relative_to(ROOT / "tuba" / "visualization" / "_viewer").as_posix()
        for path in (ROOT / "tuba" / "visualization" / "_viewer").rglob("*")
        if path.is_file()
    }
    assert packaged == expected

    smoke = subprocess.run(
        [sys.executable, ROOT / "scripts" / "verify_release_wheel.py", wheel],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert smoke.returncode == 0, smoke.stderr
    assert "verified release wheel" in smoke.stdout


def test_release_wheel_verifier_rejects_unavailable_declared_dependency(tmp_path):
    wheel = _build_wheel(ROOT, tmp_path / "wheel")
    unavailable = _add_unavailable_dependency(wheel, tmp_path / "unavailable")
    missing_dependency = subprocess.run(
        [sys.executable, ROOT / "scripts" / "verify_release_wheel.py", unavailable],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert missing_dependency.returncode != 0
    assert "release wheel verification failed" in missing_dependency.stderr


def test_candidate_overlay_handles_deleted_paths_before_and_after_commit(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tuba Test"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tuba-test@example.invalid"],
        cwd=repository,
        check=True,
    )
    kept = repository / "kept.txt"
    deleted = repository / "deleted.txt"
    ignored = repository / "ignored.txt"
    kept.write_text("before", encoding="utf-8")
    deleted.write_text("remove me", encoding="utf-8")
    (repository / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    subprocess.run(["git", "add", "kept.txt", "deleted.txt", ".gitignore"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repository, check=True, capture_output=True)

    kept.write_text("after", encoding="utf-8")
    deleted.unlink()
    (repository / "added.txt").write_text("new", encoding="utf-8")
    ignored.write_text("residue", encoding="utf-8")
    overlay_paths = changed_paths(repository)
    assert overlay_paths == ["added.txt", "deleted.txt", "kept.txt"]
    before_tree = create_candidate_tree(
        repository,
        tmp_path / "before.index",
        overlay_paths,
    )
    assert _candidate_diff_paths(repository, before_tree) == set(overlay_paths)

    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "delete legacy path"], cwd=repository, check=True, capture_output=True)
    assert changed_paths(repository) == []
    after_tree = create_candidate_tree(
        repository,
        tmp_path / "after.index",
        changed_paths(repository),
    )

    assert after_tree == subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def test_candidate_overlay_expands_detected_rename_to_source_and_destination(tmp_path):
    repository = tmp_path / "rename-repository"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tuba Test"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tuba-test@example.invalid"],
        cwd=repository,
        check=True,
    )
    source = repository / "source.txt"
    source.write_text("same release payload\n" * 20, encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "mv", "source.txt", "destination.txt"], cwd=repository, check=True)

    assert _git_paths(repository, "diff", "--name-only", "HEAD") == {"destination.txt"}
    overlay_paths = changed_paths(repository)
    assert overlay_paths == ["destination.txt", "source.txt"]
    tree = create_candidate_tree(repository, tmp_path / "rename.index", overlay_paths)

    assert _candidate_diff_paths(repository, tree) == set(overlay_paths)
    tree_paths = _git_paths(repository, "ls-tree", "--name-only", tree)
    assert "source.txt" not in tree_paths
    assert "destination.txt" in tree_paths


def test_clean_git_index_snapshot_rebuilds_identical_viewer_and_installed_launcher(tmp_path):
    overlay_paths = changed_paths(ROOT)
    tree = create_candidate_tree(ROOT, tmp_path / "candidate.index", overlay_paths)
    assert _candidate_diff_paths(ROOT, tree) == set(overlay_paths)
    archive = tmp_path / "tracked.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", archive, tree],
        cwd=ROOT,
        check=True,
    )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(snapshot, filter="data")

    tracked_viewer = _viewer_files(snapshot)
    assert "index.html" in tracked_viewer
    assert any(name.startswith("assets/") and name.endswith(".js") for name in tracked_viewer)
    assert any(name.startswith("assets/") and name.endswith(".css") for name in tracked_viewer)

    subprocess.run(
        [_npm(), "ci", "--ignore-scripts"],
        cwd=snapshot / "viewer",
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    subprocess.run([sys.executable, snapshot / "scripts" / "prepare_release.py"], check=True)
    rebuilt_viewer = _viewer_files(snapshot)
    assert rebuilt_viewer == tracked_viewer
    package_root = snapshot / "tuba" / "visualization" / "_viewer"
    referenced_assets = _referenced_viewer_assets(package_root)
    assert referenced_assets == {
        path.name for path in (package_root / "assets").iterdir() if path.is_file()
    }

    dist = tmp_path / "snapshot-dist"
    subprocess.run(
        [shutil.which("uv") or "uv", "build", "--no-sources", "--out-dir", dist],
        cwd=snapshot,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    artifacts = [*dist.glob("*.whl"), *dist.glob("*.tar.gz")]
    assert len(artifacts) == 2
    subprocess.run([shutil.which("uvx") or "uvx", "twine", "check", *artifacts], check=True)
    wheel = next(dist.glob("*.whl"))
    subprocess.run(
        [sys.executable, snapshot / "scripts" / "verify_release_wheel.py", wheel],
        cwd=tmp_path,
        check=True,
    )
