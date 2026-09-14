"""Install and smoke the exact wheel selected from a release dist directory."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.request import urlopen
import zipfile


INSTALL_TIMEOUT_SECONDS = 300


def _select_wheel(candidate: Path) -> Path:
    wheels = sorted(candidate.glob("*.whl")) if candidate.is_dir() else [candidate]
    wheels = [wheel.resolve() for wheel in wheels if wheel.suffix == ".whl" and wheel.is_file()]
    if len(wheels) != 1:
        raise ValueError(f"expected exactly one wheel, found {len(wheels)} in {candidate}")
    return wheels[0]


def _wheel_viewer_files(wheel: Path) -> dict[str, str]:
    prefix = "tuba/visualization/_viewer/"
    with zipfile.ZipFile(wheel) as archive:
        return {
            name.removeprefix(prefix): sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if name.startswith(prefix) and not name.endswith("/")
        }


def _viewer_files(viewer: Path) -> dict[str, str]:
    return {
        path.relative_to(viewer).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in viewer.rglob("*")
        if path.is_file()
    }


def _readline_bounded(stream, timeout: float = 20.0) -> str:
    lines: Queue[str] = Queue()
    Thread(target=lambda: lines.put(stream.readline()), daemon=True).start()
    try:
        return lines.get(timeout=timeout)
    except Empty as exc:
        raise TimeoutError(f"tuba-viewer did not print its URL within {timeout:g}s") from exc


def _venv_paths(root: Path) -> tuple[Path, Path]:
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe", root / "Scripts" / "tuba-viewer.exe"
    return root / "bin" / "python", root / "bin" / "tuba-viewer"


def _install_wheel(python: Path, wheel: Path, root: Path, env: dict[str, str]) -> None:
    command = [
        shutil.which("uv") or "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--force-reinstall",
        str(wheel),
    ]
    try:
        subprocess.run(
            command,
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"wheel dependency installation exceeded {INSTALL_TIMEOUT_SECONDS} seconds; "
            "check package-index access and the uv cache"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"wheel dependency installation failed: {detail}") from exc


def verify_wheel(wheel: Path) -> None:
    expected_assets = _wheel_viewer_files(wheel)
    if not expected_assets:
        raise RuntimeError(f"wheel has no packaged viewer assets: {wheel}")

    with tempfile.TemporaryDirectory(prefix="tuba-wheel-smoke-") as tmpdir:
        root = Path(tmpdir)
        environment = root / "venv"
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        clean_env["PYTHONNOUSERSITE"] = "1"
        clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        subprocess.run(
            [shutil.which("uv") or "uv", "venv", "--python", sys.executable, environment],
            cwd=root,
            env=clean_env,
            check=True,
        )
        python, launcher = _venv_paths(environment)
        _install_wheel(python, wheel, root, clean_env)

        probe = subprocess.run(
            [
                python,
                "-c",
                "import importlib.metadata as metadata, json, pathlib, tuba; "
                "from tuba.visualization import viewer_assets_path; "
                "print(json.dumps({'module': str(pathlib.Path(tuba.__file__).resolve()), "
                "'assets': str(viewer_assets_path().resolve()), 'version': tuba.__version__, "
                "'dependencies': {name: str(pathlib.Path(metadata.distribution(name).locate_file('')).resolve()) "
                "for name in ('numpy', 'jsonschema', 'gmsh')}}))",
            ],
            cwd=root,
            env=clean_env,
            check=True,
            capture_output=True,
            text=True,
        )
        installed = json.loads(probe.stdout)
        module_path = Path(installed["module"])
        assets_path = Path(installed["assets"])
        if environment.resolve() not in module_path.parents:
            raise RuntimeError(f"isolated import did not use the installed wheel: {module_path}")
        for dependency, location in installed["dependencies"].items():
            if environment.resolve() not in Path(location).parents:
                raise RuntimeError(
                    f"declared dependency {dependency} was not installed in the isolated environment: {location}"
                )
        if _viewer_files(assets_path) != expected_assets:
            raise RuntimeError("installed viewer assets differ from the selected wheel")
        if not launcher.is_file():
            raise RuntimeError(f"installed tuba-viewer entry point is missing: {launcher}")

        bundle = root / "bundle"
        bundle.mkdir()
        bundle.joinpath("scene.json").write_text(
            '{"schema_version":"visualization.scene.v1","scene_id":"scene:release-wheel",'
            '"model_id":"model:release-wheel","objects":[],"geometry_assets":[],"overlays":[]}',
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [launcher, bundle, "--port", "0"],
            cwd=root,
            env=clean_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            url = _readline_bounded(process.stdout).strip()
            if not re.fullmatch(r"http://127\.0\.0\.1:\d+/\?bundle=/bundle", url):
                raise RuntimeError(f"unexpected tuba-viewer URL: {url!r}")
            if "Tuba Viewer" not in urlopen(url, timeout=5).read().decode():
                raise RuntimeError("installed tuba-viewer did not serve the packaged application")
            scene_url = url.split("/?", 1)[0] + "/bundle/scene.json"
            scene = json.loads(urlopen(scene_url, timeout=5).read())
            if scene.get("scene_id") != "scene:release-wheel":
                raise RuntimeError("installed tuba-viewer did not serve the requested bundle")
        finally:
            process.terminate()
            process.wait(timeout=10)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: verify_release_wheel.py WHEEL_OR_DIST_DIR", file=sys.stderr)
        return 2
    try:
        wheel = _select_wheel(Path(args[0]))
        verify_wheel(wheel)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"release wheel verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"verified release wheel: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
