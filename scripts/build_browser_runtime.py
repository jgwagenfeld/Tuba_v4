"""Package the real Python geometry code for the static gallery's browser worker."""

from io import BytesIO
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tomllib
from urllib.request import urlopen
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VERSION = "0.27.7"
# GitHub's authenticated release API: pyodide/pyodide/releases/tags/0.27.7.
# The core archive authenticates its package lock; every wheel is checked against it.
PYODIDE_CORE_SHA256 = "9bc8f127db6c590b191b9aee754022cb41b1a36c7bac233776c11c5ecb541be8"
PYODIDE_CORE_URL = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"
PYODIDE_PACKAGE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"


def _verified_download(url: str, destination: Path, digest: str) -> bytes:
    """Never execute or retain an upstream download until its pinned hash matches."""
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid upstream SHA-256 digest")
    if destination.is_symlink():
        raise ValueError(f"Refusing linked runtime cache: {destination}")
    if destination.exists():
        data = destination.read_bytes()
        if hashlib.sha256(data).hexdigest() == digest:
            return data
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Runtime download redirected outside HTTPS")
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Pyodide download SHA-256 mismatch: {url}")
    temporary = destination.with_name(f".{destination.name}-{uuid4().hex}")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def pyodide_assets(cache: Path | None = None, root: Path = ROOT) -> dict[str, bytes]:
    """Return release-owned runtime assets; download only at build time."""
    if cache is None:
        if os.environ.get("TUBA_BROWSER_RUNTIME_CACHE"):
            cache = Path(os.environ["TUBA_BROWSER_RUNTIME_CACHE"])
        elif (root / ".git").exists():
            common = subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=root, text=True).strip()
            cache = (root / common).resolve().parent / ".cache" / "pyodide"
        else:
            cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tuba" / "pyodide"
    cache = cache / PYODIDE_VERSION
    for parent in (cache, *cache.parents):
        if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(), "st_file_attributes", 0) & 1024):
            raise ValueError(f"Refusing linked runtime cache: {parent}")
    core = _verified_download(PYODIDE_CORE_URL, cache / "core.tar.bz2", PYODIDE_CORE_SHA256)
    assets: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(core), mode="r:bz2") as archive:
        for member in archive.getmembers():
            # Copy individual regular files; never extract paths or links from a tar.
            if member.isfile() and Path(member.name).name in {
                "pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json",
            }:
                assets[Path(member.name).name] = archive.extractfile(member).read()
    required = {"pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"}
    if set(assets) != required:
        raise ValueError("Pinned Pyodide core archive is incomplete")
    lock = json.loads(assets["pyodide-lock.json"])
    packages = lock["packages"]
    selected: dict[str, dict] = {}

    def include(name: str) -> None:
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in selected:
            return
        package = packages[name]
        selected[name] = package
        for dependency in package["depends"]:
            include(dependency)
        filename = package["file_name"]
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", filename):
            raise ValueError("Unsafe Pyodide package filename")
        assets[filename] = _verified_download(PYODIDE_PACKAGE_URL + filename, cache / filename, package["sha256"])

    for name in ("numpy", "jsonschema"):
        include(name)
    # Ship only installed packages: Pyodide cannot fall back to unpinned CDN code.
    lock["packages"] = selected
    assets["pyodide-lock.json"] = (json.dumps(lock, sort_keys=True) + "\n").encode()
    assets["runtime-manifest.json"] = (json.dumps({
        "version": PYODIDE_VERSION, "core_url": PYODIDE_CORE_URL,
        "core_sha256": PYODIDE_CORE_SHA256,
        "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(assets.items())},
    }, sort_keys=True, indent=2) + "\n").encode()
    return assets


def browser_runtime_archive(root: Path = ROOT) -> bytes:
    # Publish repository inputs only; local files must never enter the bundle.
    if (root / ".git").exists():
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z", "--", "tuba", "examples"], cwd=root,
        ).decode("utf-8").split("\0")
    else:
        # Source archives have no index; the shipped runtime records public inputs.
        with ZipFile(root / "tuba/visualization/_viewer/tuba-browser.zip") as shipped:
            tracked = shipped.namelist()
    output = BytesIO()
    # Python versions bundle different zlib implementations; store identical bytes.
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        def add(name: str, data: bytes) -> None:
            entry = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = ZIP_STORED
            archive.writestr(entry, data)

        for folder in ("tuba", "examples"):
            # `evidence` and `reference` are excluded together on purpose: a study card
            # describes evidence for a reader of the repository, so a browser that
            # carries neither carries nothing that depends on them.
            for name in sorted(name for name in tracked if name.startswith(folder + "/")):
                path = root / name
                if (path.is_file() and path.suffix in {".py", ".json", ".input", ".output", ".stl"}
                        and not {"_viewer", "__pycache__", ".tuba", "evidence", "reference", "review"}.intersection(path.parts)):
                    data = path.read_bytes()
                    # Git checkouts may use CRLF; keep the shipped archive identical.
                    if path.suffix != ".stl":
                        data = data.replace(b"\r\n", b"\n")
                    add(path.relative_to(root).as_posix(), data)
        version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        add(f"tuba-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: tuba\nVersion: {version}\n".encode())
        for name in ("LICENSE", "LICENSE.GPL"):
            add(name, (root / name).read_bytes().replace(b"\r\n", b"\n"))
    return output.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyodide-output", type=Path)
    args = parser.parse_args()
    if args.pyodide_output:
        args.pyodide_output.mkdir(parents=True, exist_ok=True)
        for name, data in pyodide_assets().items():
            (args.pyodide_output / name).write_bytes(data)
    else:
        sys.stdout.buffer.write(browser_runtime_archive())
