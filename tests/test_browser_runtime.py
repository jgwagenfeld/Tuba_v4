from io import BytesIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile
import hashlib
import json
import tarfile

import pytest

from scripts import build_browser_runtime
from scripts.build_browser_runtime import browser_runtime_archive


def test_browser_runtime_excludes_untracked_and_ignored_inputs():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "examples/private-project"
        project.mkdir(parents=True)
        (project / "model.py").write_text("# local project\n")
        (root / "examples/untracked.py").write_text("# untracked input\n")
        (root / "examples/public.py").write_text("# published example\n")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".git/info/exclude").write_text("/examples/private-project/\n")
        subprocess.run(["git", "add", "--", "examples/public.py"], cwd=root, check=True)
        (root / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
        for name in ("LICENSE", "LICENSE.GPL"):
            (root / name).write_text("test license\n")
        with ZipFile(BytesIO(browser_runtime_archive(root))) as bundle:
            assert "examples/public.py" in bundle.namelist()
            assert "examples/untracked.py" not in bundle.namelist()
            assert not any("private-project" in name for name in bundle.namelist())


def test_browser_runtime_contains_current_python_and_data_but_no_results_or_viewer():
    root = Path(__file__).resolve().parents[1]
    archive = browser_runtime_archive(root)
    assert archive == browser_runtime_archive(root)
    with ZipFile(BytesIO(archive)) as bundle:
        assert {entry.create_system for entry in bundle.infolist()} == {3}
        assert {entry.compress_type for entry in bundle.infolist()} == {ZIP_STORED}
        assert bundle.read("examples/imported_component_mixed_demo/imported_component_demo.stl") == (root / "examples/imported_component_mixed_demo/imported_component_demo.stl").read_bytes()
        assert bundle.read("tuba/model.py") == (root / "tuba/model.py").read_bytes().replace(b"\r\n", b"\n")
        assert bundle.read("tuba/visualization/builders/_objects.py") == (root / "tuba/visualization/builders/_objects.py").read_bytes().replace(b"\r\n", b"\n")
        assert "examples/code-aster-review/model.py" in bundle.namelist()
        assert any("sections/data/" in name for name in bundle.namelist())
        assert not any(set(Path(name).parts) & {"evidence", "reference", "_viewer", ".tuba", "review"}
                       or name.endswith(".rmed") for name in bundle.namelist())


def test_browser_runtime_rebuilds_source_archive_without_adding_local_files(tmp_path):
    shipped = tmp_path / "tuba/visualization/_viewer/tuba-browser.zip"
    shipped.parent.mkdir(parents=True)
    (tmp_path / "tuba/public.py").write_text("# updated source\n")
    (tmp_path / "tuba/local.py").write_text("# local input\n")
    private = tmp_path / "examples/private-project/model.py"
    private.parent.mkdir(parents=True)
    private.write_text("# local project\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
    for name in ("LICENSE", "LICENSE.GPL"):
        (tmp_path / name).write_text("test license\n")
    with ZipFile(shipped, "w") as bundle:
        bundle.writestr("tuba/public.py", "# previous source\n")
    with ZipFile(BytesIO(browser_runtime_archive(tmp_path))) as bundle:
        assert bundle.read("tuba/public.py") == b"# updated source\n"
        assert set(bundle.namelist()) == {
            "tuba/public.py", "tuba-0.0.0.dist-info/METADATA", "LICENSE", "LICENSE.GPL",
        }


def test_browser_preview_builds_a_scene_without_gmsh():
    # The browser has no gmsh. Every scene build reads the mesh-sizing policy, and
    # importing tuba.meshing once dragged the gmsh-backed generator in with it, so
    # every gallery "Update geometry" failed with "This script needs gmsh".
    import sys

    root = Path(__file__).resolve().parents[1]
    script = (
        "import sys; sys.modules['gmsh'] = None\n"
        "from pathlib import Path\n"
        "from tuba.project import run_model_script\n"
        "from tuba.visualization import SceneRequest, build_visualization_scene\n"
        "model = run_model_script(Path('examples/code-aster-review/model.py'))['model']\n"
        "build_visualization_scene(SceneRequest(model, include_analysis_mesh=False)).validate()\n"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]


def test_pyodide_assets_verify_core_and_dependency_closure(tmp_path, monkeypatch):
    wheels = {name: name.encode() for name in ("numpy", "jsonschema", "schema-specifications")}
    lock = {"packages": {name: {
        "file_name": name + ".whl", "sha256": hashlib.sha256(data).hexdigest(),
        "depends": ["schema_specifications"] if name == "jsonschema" else [],
    } for name, data in wheels.items()}}
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:bz2") as archive:
        for name in ("pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"):
            data = json.dumps(lock).encode() if name == "pyodide-lock.json" else name.encode()
            member = tarfile.TarInfo("pyodide/" + name)
            member.size = len(data)
            archive.addfile(member, BytesIO(data))
    core = output.getvalue()
    downloads = []

    def download(url, destination, digest):
        data = core if url == build_browser_runtime.PYODIDE_CORE_URL else wheels[destination.stem]
        assert hashlib.sha256(data).hexdigest() == digest
        downloads.append(destination.name)
        return data

    monkeypatch.setattr(build_browser_runtime, "PYODIDE_CORE_SHA256", hashlib.sha256(core).hexdigest())
    monkeypatch.setattr(build_browser_runtime, "_verified_download", download)
    assets = build_browser_runtime.pyodide_assets(tmp_path)
    assert set(downloads) == {"core.tar.bz2", "numpy.whl", "jsonschema.whl", "schema-specifications.whl"}
    assert set(json.loads(assets["pyodide-lock.json"])["packages"]) == set(wheels)
    assert json.loads(assets["runtime-manifest.json"])["sha256"]["numpy.whl"] == hashlib.sha256(wheels["numpy"]).hexdigest()


def test_pyodide_download_rejects_tampered_cache_and_upstream(tmp_path, monkeypatch):
    destination = tmp_path / "pyodide.mjs"
    destination.write_bytes(b"tampered cache")
    response = BytesIO(b"tampered upstream")
    response.url = "https://upstream.example/runtime"
    monkeypatch.setattr(build_browser_runtime, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_browser_runtime._verified_download(response.url, destination, hashlib.sha256(b"approved").hexdigest())
    assert destination.read_bytes() == b"tampered cache"
