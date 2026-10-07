"""Portable ZIP or TGZ project handoffs with unchanged source and a readable manifest.

Packing source never executes it. Only the optional saved-results check executes
model.py/study.py; opening in Studio executes Python just like opening a folder.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager, nullcontext
import hashlib
import gzip
import io
import json
import os
import importlib.machinery
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import sys
import sysconfig
import tarfile
import tempfile
import zipfile
import zlib

from tuba.project import load_project
from tuba.analysis.staged_run import operation_folder_name

FORMAT = "tuba.project-package.v1"
MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_EXPANDED_BYTES = 4 * 1024**3
MAX_FILES = 20000
MAX_PATH_BYTES = 1024
MAX_PATH_DEPTH = 32
MAX_TOTAL_PATH_BYTES = 8 * 1024**2
MAX_CENTRAL_DIRECTORY_BYTES = 32 * 1024**2
MAX_TAR_METADATA_BYTES = 32 * 1024**2
PACKAGE_SUFFIXES = (".tubaproject", ".tar.gz", ".tgz", ".zip")
_EXCLUDED = {".git", ".tuba", ".build", ".scratch", ".tmp", ".cache", ".worktrees", ".agents",
             ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
             "build", "dist", "evidence", "review", "review_scene", "results"}
_ARCHIVES = (".tubaproject", ".zip", ".tgz", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".7z", ".rar")
_GENERATED = (".pyc", ".pyo", ".rmed", ".mess", ".mail", ".export", ".msh")
_PRIVATE = (".pem", ".key", ".p12", ".pfx", ".env", ".secret")


def _portable(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError(f"Invalid portable path: {name!r}.")
    if len(name.encode("utf-8")) > MAX_PATH_BYTES or name.count("/") >= MAX_PATH_DEPTH:
        raise ValueError("Package path exceeds the encoded length or component depth limit.")
    for part in name.split("/"):
        try:
            operation_folder_name(part)
        except ValueError:
            raise ValueError(f"Path is not portable to Windows and Linux: {name!r}.")
    return name


def _excluded(path: Path) -> bool:
    name = path.name.casefold()
    return (any(part.casefold() in _EXCLUDED for part in path.parts)
            or name.startswith((".env", "credentials", "service-account")) or name in {".npmrc", ".pypirc"}
            or name.endswith(_ARCHIVES + _GENERATED + _PRIVATE))


def _source_files(root: Path) -> list[str]:
    files = []
    for directory, folders, names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in folders + names:
            path = base / name
            relative = path.relative_to(root)
            if _excluded(relative):
                continue
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError(f"Move linked input into the project before sharing: {relative}.")
            _portable(relative.as_posix())
        folders[:] = [name for name in folders if not _excluded((base / name).relative_to(root))]
        files.extend((base / name).relative_to(root).as_posix() for name in names
                     if not _excluded((base / name).relative_to(root)))
    return sorted(files)


def _result_files(root: Path) -> list[str]:
    from tuba.project.evidence import ATTESTATION, evidence_dir, evidence_verdict
    from tuba.project.freshness import expected_identity
    project = load_project(root)
    settings = project.load_settings()
    if not settings.operations:
        raise ValueError("Saved results require study.py with LOAD_CASES and current verified Code_Aster evidence.")
    model = project.run_model()["model"]
    files = []
    for operation in settings.operations:
        folder = evidence_dir(root, operation)
        identity = expected_identity(model, operation, solver_options=settings.solver_options,
                                     volume_export=settings.volume_export)
        verdict = evidence_verdict(folder, identity)
        if not verdict.reusable:
            reason = verdict.state.reason if verdict.state.status != "verified" else "solver inputs differ from the current model or study"
            raise ValueError(f"Saved results for {operation!r} are missing, damaged, unverified or stale: {reason} Solve before sharing results.")
        for name in [ATTESTATION, *verdict.state.attestation["artifacts"]]:
            files.append((folder / name).relative_to(root).as_posix())
    return sorted(files)


def _inventory(root: Path, include_results: bool, external_sources=None) -> tuple[dict, dict[str, Path]]:
    """The manifest and project-contained or explicitly approved source files."""
    from tuba import __version__
    load_project(root)
    names = _source_files(root) + (_result_files(root) if include_results else [])
    sources = {name: root / name for name in names}
    for helper, path in _check_local_imports(root, names, external_sources).items():
        if helper in sources:
            raise ValueError(f"Workspace helper {helper} collides with a project file of the same path.")
        sources[helper] = path
    names = sorted(sources)
    if len(names) > MAX_FILES:
        raise ValueError(f"Project exceeds {MAX_FILES} files; move generated output out of the project.")
    records = []
    seen = set()
    for name in names:
        _portable(name)
        if name.casefold() in seen:
            raise ValueError(f"Case-colliding project paths: {name}.")
        seen.add(name.casefold())
        path = sources[name]
        if not path.is_file() or any(parent.is_symlink() or getattr(parent, "is_junction", lambda: False)()
                                     for parent in [path, *path.parents] if parent != root and root in parent.parents):
            raise ValueError(f"Package input must be a regular file: {name}.")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        records.append({"path": name, "size": path.stat().st_size, "sha256": digest,
                        **({"external_source": str(path.resolve())} if not path.resolve().is_relative_to(root) else {})})
    if sum(len(name.encode("utf-8")) for name in names) > MAX_TOTAL_PATH_BYTES:
        raise ValueError("Project exceeds the total encoded path limit.")
    total = sum(record["size"] for record in records)
    if total > MAX_EXPANDED_BYTES:
        raise ValueError("Project exceeds the 4 GiB expanded size limit.")
    return {"format": FORMAT, "name": root.name, "tuba_version": __version__,
            "project_root": "project", "include_results": include_results, "files": records,
            "size_bytes": total}, sources


def _workspace_module(workspaces: list[Path], module: str, names: list[str]) -> dict[str, Path]:
    """Files for ``module`` (or its imported submodules) under a workspace folder, by archive path."""
    found = {}
    for dotted in [module, *(f"{module}.{name}" for name in names)]:
        parts = dotted.split(".")
        for workspace in workspaces:
            base = workspace.joinpath(*parts)
            path = next((candidate for candidate in (base.with_suffix(".py"), base / "__init__.py") if candidate.is_file()), None)
            if path is None or not path.resolve().is_relative_to(workspace):
                continue
            found[path.relative_to(workspace).as_posix()] = path
            for depth in range(1, len(parts)):
                package_init = workspace.joinpath(*parts[:depth], "__init__.py")
                if package_init.is_file():
                    found[package_init.relative_to(workspace).as_posix()] = package_init
            break
    return found


def _check_local_imports(root: Path, names: list[str], external_sources=None) -> dict[str, Path]:
    """Refuse out-of-project imports unless each source and archive path is explicitly approved.

    ponytail: static imports only; dynamic imports and computed paths remain the
    author's responsibility. A sandboxed dependency recorder would cover those.
    """
    approved = {}
    for name, path in (external_sources or {}).items():
        _portable(name)
        source = Path(path).resolve()
        if (_excluded(Path(name)) or _excluded(source) or not source.is_file()
                or Path(path).is_symlink() or any(parent.is_symlink() or getattr(parent, "is_junction", lambda: False)()
                                                for parent in Path(path).absolute().parents)):
            raise ValueError(f"External package source must be a non-sensitive regular file: {name}.")
        approved[name] = source
    installed = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
                 Path(sysconfig.get_path("stdlib")).resolve()]
    workspaces = [workspace for workspace in (Path(entry or ".").resolve() for entry in sys.path)
                  if workspace != root and root.is_relative_to(workspace)]
    helpers: dict[str, Path] = {}
    pending = [(name, root / name) for name in names if name.endswith(".py")]
    while pending:
        name, path = pending.pop()
        try:
            tree = ast.parse(path.read_bytes(), filename=name)
        except SyntaxError as exc:
            raise ValueError(f"{name} has invalid Python: {exc.msg} at line {exc.lineno}.") from exc
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module] if isinstance(node, ast.ImportFrom) and not node.level and node.module else [])
            for module in modules:
                first = module.split(".")[0]
                if first == "tuba" or first in sys.builtin_module_names or (root / first).exists() or (root / (first + ".py")).exists():
                    continue
                spec = importlib.machinery.PathFinder.find_spec(first)
                locations = ([spec.origin] if spec and spec.origin and spec.origin not in {"built-in", "frozen"}
                             else list(spec.submodule_search_locations or ()) if spec else [])
                for location in locations:
                    source = Path(location).resolve()
                    if any(source.is_relative_to(prefix) for prefix in [root, *installed]):
                        continue
                    imported = [alias.name for alias in node.names] if isinstance(node, ast.ImportFrom) else []
                    found = _workspace_module(workspaces, module, imported)
                    if not found:
                        raise ValueError(f"{name} imports workspace code outside this project: {module}. Move the helper into the project before sharing.")
                    for helper, helper_path in found.items():
                        if approved.get(helper) != helper_path.resolve():
                            raise ValueError(f"{name} imports workspace code outside this project: {module}. Explicitly approve {helper_path.resolve()} as {helper}, or move it into the project.")
                        if helper not in helpers:
                            helpers[helper] = helper_path
                            if helper.endswith(".py"):
                                pending.append((helper, helper_path))
                    break
            if isinstance(node, ast.Call) and node.args:
                function = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                value = node.args[0]
                if function in {"Path", "open"} and isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if value.value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value.value):
                        raise ValueError(f"{name} uses an absolute input path. Keep inputs project-local and resolve them from Path(__file__).parent before sharing.")
    return helpers


def plan_project_package(root: str | Path, *, include_results: bool = False, external_sources=None) -> dict:
    """Return the manifest, including uncompressed size. Results must be current and verified."""
    from tuba.project.claim import claim_solve
    root = Path(root).resolve()
    with claim_solve(root) if include_results else nullcontext():
        return _inventory(root, include_results, external_sources)[0]


def package_suffix(path: str | Path) -> str | None:
    """Supported archive suffix, including the complete .tar.gz extension."""
    return next((suffix for suffix in PACKAGE_SUFFIXES if Path(path).name.casefold().endswith(suffix)), None)


def export_project_package(root: str | Path, output: str | Path, *, include_results: bool = False, external_sources=None) -> dict:
    """Write ZIP (.tubaproject/.zip) or TGZ (.tgz/.tar.gz); never overwrite a package."""
    from tuba.project.claim import claim_solve
    root, output = Path(root).resolve(), Path(output).resolve()
    suffix = package_suffix(output)
    if suffix is None:
        raise ValueError("Use .tubaproject/.zip for ZIP or .tgz/.tar.gz for gzip/tar.")
    if output.exists():
        raise FileExistsError(f"Package already exists: {output}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with claim_solve(root) if include_results else nullcontext():
        manifest, sources = _inventory(root, include_results, external_sources)
        with tempfile.TemporaryDirectory(prefix="tuba-package-", dir=output.parent) as temporary:
            archive = Path(temporary) / ("package.tgz" if suffix in {".tgz", ".tar.gz"} else "package.zip")
            raw_manifest = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            if suffix in {".tgz", ".tar.gz"}:
                with tarfile.open(archive, "w:gz", compresslevel=6) as bundle:
                    header = tarfile.TarInfo("manifest.json")
                    header.size = len(raw_manifest)
                    bundle.addfile(header, io.BytesIO(raw_manifest))
                    for record in manifest["files"]:
                        bundle.add(sources[record["path"]], "project/" + record["path"], recursive=False)
            else:
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                    bundle.writestr("manifest.json", raw_manifest)
                    for record in manifest["files"]:
                        bundle.write(sources[record["path"]], "project/" + record["path"])
            inspect_project_package(archive)
            if manifest != _inventory(root, include_results, external_sources)[0]:
                raise ValueError("Project changed during export; retry after saving and solving.")
            with output.open("xb") as destination, archive.open("rb") as source:
                try:
                    shutil.copyfileobj(source, destination)
                except BaseException:
                    destination.close()
                    output.unlink()
                    raise
    return {**manifest, "archive_bytes": output.stat().st_size, "output_path": str(output)}


@contextmanager
def _open_package(archive: Path):
    """Format adapters expose only regular files/directories to the shared validator."""
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Package exceeds the 2 GiB archive limit.")
    try:
        if zipfile.is_zipfile(archive):
            _preflight_zip(archive)
            with zipfile.ZipFile(archive) as bundle:
                entries = []
                path_bytes = 0
                for info in bundle.infolist():
                    _portable(info.filename.rstrip("/") if info.is_dir() else info.filename)
                    path_bytes += len(info.filename.encode("utf-8"))
                    if path_bytes > MAX_TOTAL_PATH_BYTES:
                        raise ValueError("Package exceeds the total encoded path limit.")
                    mode = stat.S_IFMT(info.external_attr >> 16)
                    if (mode not in {0, stat.S_IFREG, stat.S_IFDIR} or info.flag_bits & 1
                            or mode == stat.S_IFDIR and not info.is_dir() or info.is_dir() and info.file_size):
                        raise ValueError(f"Package contains a link, special or encrypted entry: {info.filename}.")
                    entries.append((info.filename.rstrip("/") if info.is_dir() else info.filename, info.file_size, info.is_dir()))
                yield entries, bundle.open
        else:
            with _PackageGzip(archive, "rb") as compressed, tarfile.open(fileobj=compressed, mode="r:", tarinfo=_PackageTarInfo) as bundle:
                entries = []
                expanded = 0
                path_bytes = 0
                for info in bundle:
                    _portable(info.name.rstrip("/") if info.isdir() else info.name)
                    path_bytes += len(info.name.encode("utf-8"))
                    if path_bytes > MAX_TOTAL_PATH_BYTES:
                        raise ValueError("Package exceeds the total encoded path limit.")
                    if (not (info.isfile() or info.isdir()) or getattr(info, "sparse", None) is not None
                            or info.isdir() and info.size):
                        raise ValueError(f"Package contains a link, special or sparse entry: {info.name}.")
                    entries.append((info.name.rstrip("/") if info.isdir() else info.name, info.size, info.isdir()))
                    expanded += info.size if info.name != "manifest.json" else 0
                    if len(entries) > 2 * MAX_FILES + 1 or expanded > MAX_EXPANDED_BYTES or info.size < 0:
                        raise ValueError("Package exceeds the file count or expanded size limit.")
                    if info.name == "manifest.json" and info.size > 8 * 1024**2:
                        raise ValueError("Package manifest exceeds 8 MiB.")
                compressed.checking_metadata = False
                yield entries, bundle.extractfile
                # Read the gzip trailer too: tar parsing alone can miss truncated
                # gzip streams. Bound extra padding/metadata rather than expanding
                # unlimited data after the tar end marker.
                while bundle.fileobj.read(1024 * 1024):
                    if bundle.fileobj.tell() > MAX_EXPANDED_BYTES + 64 * 1024**2:
                        raise ValueError("Package tar metadata/padding exceeds the size limit.")
    except (zipfile.BadZipFile, tarfile.TarError, gzip.BadGzipFile, zlib.error,
            EOFError, KeyError, UnicodeError, NotImplementedError) as exc:
        raise ValueError(f"Invalid ZIP/TGZ project package: {exc}") from exc


def _preflight_zip(archive: Path) -> None:
    """Bound eager ZIP metadata allocation, including ZIP64, before ZipFile constructs entries."""
    with archive.open("rb") as source:
        size = archive.stat().st_size
        source.seek(max(0, size - 65557))
        tail = source.read(65557)
        offset = tail.rfind(b"PK\x05\x06")
        if offset < 0 or len(tail) - offset < 22:
            raise ValueError("Invalid ZIP end record.")
        _, disk, directory_disk, disk_count, count, directory_bytes, directory_offset, comment = struct.unpack_from("<4s4H2LH", tail, offset)
        if disk or directory_disk or disk_count != count or offset + 22 + comment != len(tail):
            raise ValueError("Invalid or multi-disk ZIP end record.")
        end_offset = max(0, size - 65557) + offset
        directory_end_offset = end_offset
        if end_offset >= 20:
            source.seek(end_offset - 20)
            locator = source.read(20)
            if locator.startswith(b"PK\x06\x07"):
                _, zip64_disk, zip64_offset, disks = struct.unpack("<4sLQL", locator)
                if zip64_disk or disks != 1 or zip64_offset != end_offset - 76:
                    raise ValueError("Invalid ZIP64 locator.")
                source.seek(zip64_offset)
                record = source.read(56)
                if len(record) != 56 or not record.startswith(b"PK\x06\x06"):
                    raise ValueError("Invalid ZIP64 end record.")
                _, record_size, _, _, disk, directory_disk, disk_count, count, directory_bytes, directory_offset = struct.unpack("<4sQ2H2L4Q", record)
                if record_size != 44 or disk or directory_disk or disk_count != count:
                    raise ValueError("Invalid or over-budget ZIP64 end record.")
                directory_end_offset = zip64_offset
        if count > 2 * MAX_FILES + 1 or directory_bytes > MAX_CENTRAL_DIRECTORY_BYTES:
            raise ValueError("ZIP central directory exceeds the entry or metadata size limit.")
        # ZipFile reads backwards from the physical end record, not the declared
        # offset, for concatenated archives. Validate the same directory it reads.
        if directory_offset + directory_bytes != directory_end_offset:
            raise ValueError("Invalid ZIP central directory bounds.")
        source.seek(directory_offset)
        actual_count = path_bytes = 0
        directory_end = directory_offset + directory_bytes
        while source.tell() < directory_end:
            header = source.read(46)
            if len(header) != 46 or not header.startswith(b"PK\x01\x02"):
                raise ValueError("Invalid ZIP central directory entry.")
            name_bytes, extra_bytes, comment_bytes = struct.unpack_from("<3H", header, 28)
            if name_bytes > MAX_PATH_BYTES or source.tell() + name_bytes + extra_bytes + comment_bytes > directory_end:
                raise ValueError("ZIP entry exceeds path or directory bounds.")
            raw_name = source.read(name_bytes)
            flags = struct.unpack_from("<H", header, 8)[0]
            _portable(raw_name.decode("utf-8" if flags & 0x800 else "cp437").rstrip("/"))
            actual_count += 1
            path_bytes += name_bytes
            if actual_count > 2 * MAX_FILES + 1 or path_bytes > MAX_TOTAL_PATH_BYTES:
                raise ValueError("ZIP central directory exceeds the entry or path size limit.")
            source.seek(extra_bytes + comment_bytes, 1)
        if actual_count != count:
            raise ValueError("ZIP central directory entry count differs from its end record.")


class _PackageTarInfo(tarfile.TarInfo):
    def _proc_member(self, bundle):
        # PAX/GNU headers recursively parse the next header while retaining their
        # buffers. This also guards TarFile's eager first-member construction.
        depth = getattr(bundle, "_package_header_depth", 0)
        if depth >= MAX_PATH_DEPTH:
            raise ValueError("Package tar metadata nesting exceeds the depth limit.")
        bundle._package_header_depth = depth + 1
        try:
            return super()._proc_member(bundle)
        finally:
            bundle._package_header_depth = depth


class _PackageGzip(gzip.GzipFile):
    """Bound tar's seeks and metadata allocations before tarfile parses untrusted headers."""
    def __init__(self, *args, **kwargs):
        self.checking_metadata = True
        self.metadata_bytes = 0
        super().__init__(*args, **kwargs)

    def read(self, size=-1):
        if not 0 <= size <= 8 * 1024**2 + tarfile.BLOCKSIZE:
            raise ValueError("Package tar metadata read exceeds 8 MiB.")
        if self.checking_metadata:
            self.metadata_bytes += size
            if self.metadata_bytes > MAX_TAR_METADATA_BYTES:
                raise ValueError("Package tar metadata exceeds the cumulative size limit.")
        data = super().read(size)
        if self.tell() > MAX_EXPANDED_BYTES + 64 * 1024**2:
            raise ValueError("Package tar metadata/padding exceeds the size limit.")
        return data

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else super().seek(0, 1) + offset if whence == 1 else -1
        if not 0 <= target <= MAX_EXPANDED_BYTES + 64 * 1024**2:
            raise ValueError("Package tar seek exceeds the size limit.")
        return super().seek(offset, whence)


def _read_manifest(entries, open_member) -> dict:
    files = [(name, size) for name, size, is_dir in entries if not is_dir]
    if (len(entries) > 2 * MAX_FILES + 1 or len(files) > MAX_FILES + 1
            or sum(size for name, size in files if name != "manifest.json") > MAX_EXPANDED_BYTES):
        raise ValueError("Package exceeds the file count or expanded size limit.")
    members = {}
    directories = set()
    spellings = {}
    declared_directories = set()
    for name, size, is_dir in entries:
        _portable(name)
        folded = name.casefold()
        for ancestor in [PurePosixPath(name), *PurePosixPath(name).parents]:
            spelling = str(ancestor)
            if spellings.setdefault(spelling.casefold(), spelling) != spelling:
                raise ValueError(f"Case-colliding paths: {name}.")
        if folded in members or (is_dir and folded in declared_directories) or (not is_dir and folded in directories):
            raise ValueError(f"Duplicate or case-colliding entry: {name}.")
        if is_dir:
            declared_directories.add(folded)
            directories.add(folded)
        else:
            members[folded] = (name, size)
        for parent in PurePosixPath(folded).parents:
            if str(parent) in members:
                raise ValueError(f"File/directory collision: {name}.")
            directories.add(str(parent))
    if "manifest.json" not in members or members["manifest.json"][0] != "manifest.json" or members["manifest.json"][1] > 8 * 1024**2:
        raise ValueError("Package needs a readable manifest.json (up to 8 MiB).")
    with open_member("manifest.json") as source:
        manifest = json.load(source)
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or manifest.get("project_root") != "project":
        raise ValueError("Unsupported Tuba project package format.")
    records = manifest.get("files")
    if not isinstance(records, list) or type(manifest.get("include_results")) is not bool:
        raise ValueError("Invalid package manifest.")
    expected = {"manifest.json"}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid package file record.")
        name = _portable(record.get("path"))
        path = PurePosixPath(name)
        if _excluded(Path(name)) and not (manifest["include_results"] and path.parts[0] == "evidence" and len(path.parts) == 3):
            raise ValueError(f"Package contains excluded output/state: {name}.")
        archive_name = "project/" + name
        info = members.get(archive_name.casefold())
        if (archive_name in expected or info is None or info[0] != archive_name
                or type(record.get("size")) is not int or record["size"] != info[1]
                or not isinstance(record.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", record["sha256"])):
            raise ValueError(f"Invalid inventory for {name}.")
        expected.add(archive_name)
    if expected != {name for name, _ in files} or "project/model.py" not in expected:
        raise ValueError("Package inventory must list every file and contain project/model.py.")
    if any(not any(name.casefold().startswith(directory + "/") for name in expected) for directory in declared_directories):
        raise ValueError("Package contains directories outside its inventory.")
    if manifest.get("size_bytes") != sum(record["size"] for record in records):
        raise ValueError("Invalid package size in manifest.")
    return manifest


def inspect_project_package(archive: str | Path) -> dict:
    """Validate paths, limits, inventory and every SHA-256 without running Python."""
    archive = Path(archive)
    with _open_package(archive) as (entries, open_member):
        manifest = _read_manifest(entries, open_member)
        records = {"project/" + record["path"]: record for record in manifest["files"]}
        for name, _, _ in entries:
            if (record := records.get(name)) is not None:
                with open_member(name) as source:
                    if hashlib.file_digest(source, "sha256").hexdigest() != record["sha256"]:
                        raise ValueError(f"Package checksum failed: {record['path']}.")
        return manifest


def unpack_project_package(archive: str | Path, destination: str | Path) -> Path:
    """Extract unchanged files to a new working folder. Existing folders are never replaced."""
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"Choose a new working folder; destination already exists: {destination}.")
    inspect_project_package(archive)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the destination first so a competing opener cannot be overwritten.
    destination.mkdir()
    try:
        with _open_package(archive) as (entries, open_member):
            manifest = _read_manifest(entries, open_member)
            records = {"project/" + record["path"]: record for record in manifest["files"]}
            for name, _, _ in entries:
                if name not in records:
                    continue
                record = records[name]
                path = destination / record["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                with open_member(name) as source, path.open("xb") as target:
                    shutil.copyfileobj(source, target)
                with path.open("rb") as source:
                    if hashlib.file_digest(source, "sha256").hexdigest() != record["sha256"]:
                        raise ValueError(f"Package checksum failed: {record['path']}.")
    except BaseException:
        shutil.rmtree(destination)  # Only the new, owned folder; archives cannot create links.
        raise
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Share editable projects as ZIP (.tubaproject/.zip) or TGZ (.tgz/.tar.gz).")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Package clean saved source, optionally current verified Code_Aster evidence")
    export.add_argument("project", type=Path)
    export.add_argument("--output", required=True, type=Path, help=".tubaproject/.zip for ZIP; .tgz/.tar.gz for gzip/tar")
    export.add_argument("--include-results", action="store_true")
    inspect = commands.add_parser("inspect", help="Validate and print the readable manifest without executing Python")
    inspect.add_argument("package", type=Path)
    unpack = commands.add_parser("unpack", help="Extract to a new working folder without executing Python")
    unpack.add_argument("package", type=Path)
    unpack.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            result = export_project_package(args.project, args.output, include_results=args.include_results)
        elif args.command == "inspect":
            result = inspect_project_package(args.package)
        else:
            result = {"project_root": str(unpack_project_package(args.package, args.output))}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
