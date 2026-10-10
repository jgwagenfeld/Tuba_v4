"""Owned durable files; inventories describe bytes, never solver trust."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import uuid

from .contracts import safe_id
from .history import encode

EXCLUDED = {".scratch", ".tmp", ".build", ".git", ".venv", "venv", "env",
            "node_modules", "__pycache__", ".pytest_cache", "evidence", "archives", "attempts"}


def no_links(path: Path) -> None:
    """Inspect ancestors before resolving; Windows junctions are reparse points."""
    for item in reversed((path, *path.parents)):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Archive refuses link/reparse point: {item}")


def digest_file(path: Path) -> str:
    no_links(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict, *, replace: bool = False) -> None:
    no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temporary.open("xb") as stream:
        stream.write((encode(value) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        no_links(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, reference: str) -> Path:
        if not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference:
            raise ValueError("Expected a safe relative POSIX archive reference")
        relative = PurePosixPath(reference)
        if relative.is_absolute() or any(p in {".", ".."} for p in relative.parts):
            raise ValueError("Unsafe archive reference")
        target = self.root.joinpath(*relative.parts)
        no_links(target)
        return target

    def _entry(self, path: Path) -> dict:
        no_links(path)
        return {"path": path.relative_to(self.root).as_posix(), "size_bytes": path.stat().st_size,
                "sha256": digest_file(path)}

    def _files(self, folder: Path):
        no_links(folder)
        for current, directories, files in os.walk(folder, followlinks=False):
            for name in directories:
                no_links(Path(current) / name)
            for name in sorted(files):
                path = Path(current) / name
                no_links(path)
                yield path

    def capture_source(self, project, dependency_paths=()) -> str:
        project_root = Path(project.root).absolute()
        no_links(project_root)
        sources = {project_root / name for name in ("model.py", "study.py", "search.py")}
        sources.update(Path(path).absolute() for path in dependency_paths)
        records = []
        for source in sorted(sources):
            no_links(source)
            try:
                logical = source.relative_to(project_root)
            except ValueError:
                raise ValueError(f"Explicit dependencies must be inside the project: {source}") from None
            if any(part.lower() in EXCLUDED for part in logical.parts):
                raise ValueError(f"Excluded source payload: {logical}")
            records.append({"logical_name": logical.as_posix(), "sha256": digest_file(source),
                            "size_bytes": source.stat().st_size})
        digest = hashlib.sha256(encode(records).encode()).hexdigest()
        folder = self.path(f"source/{digest}")
        reference = f"source/{digest}/inventory.json"
        if self.path(reference).exists():
            self.verify_inventory(reference)
            return reference
        folder.mkdir(parents=True, exist_ok=True)
        for record in records:
            target = folder / record["logical_name"]
            no_links(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if digest_file(target) != record["sha256"]:
                    raise ValueError("Partial source integrity failure")
                continue
            temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.partial")
            with (project_root / record["logical_name"]).open("rb") as src, temp.open("xb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            if digest_file(temp) != record["sha256"]:
                raise ValueError("Source changed while being captured")
            os.replace(temp, target)
        inventory = {"schema": "tuba.search.inventory.v1", "kind": "source", "digest": digest,
                     "files": [record | {"path": (folder / record["logical_name"]).relative_to(self.root).as_posix()} for record in records]}
        atomic_json(self.path(reference), inventory)
        return reference

    def save_model(self, candidate_id: str, model) -> str:
        reference = f"candidates/{safe_id(candidate_id)}/model.json"
        atomic_json(self.path(reference), model.to_dict())
        return reference

    def begin_attempt(self, candidate_id: str) -> str:
        attempt_id = "A" + uuid.uuid4().hex
        atomic_json(self.path(f"attempts/{attempt_id}/attempt.json"),
                    {"candidate_id": safe_id(candidate_id), "attempt_id": attempt_id})
        return attempt_id

    def operation_dir(self, attempt_id: str, operation: str) -> Path:
        root = f"attempts/{safe_id(attempt_id)}"
        if self.path(f"{root}/inventory.json").exists():
            raise ValueError("Sealed attempts cannot receive another operation")
        if not self.path(f"{root}/attempt.json").is_file():
            raise ValueError("Unknown attempt")
        folder = self.path(f"{root}/{safe_id(operation)}")
        folder.mkdir(exist_ok=True)
        return folder

    def seal_attempt(self, attempt_id: str, status: str, *, evidence_links=()) -> str:
        if status not in {"complete", "failed", "interrupted", "blocked", "not_started"}:
            raise ValueError("Invalid execution status")
        reference = f"attempts/{safe_id(attempt_id)}/inventory.json"
        inventory_path = self.path(reference)
        if inventory_path.exists():
            self.verify_inventory(reference)
            return reference
        folder = inventory_path.parent
        record = json.loads((folder / "attempt.json").read_text(encoding="utf-8"))
        files = [self._entry(path) for path in self._files(folder)]
        atomic_json(inventory_path, {"schema": "tuba.search.inventory.v1", "kind": "attempt",
                                    **record, "status": status, "files": files,
                                    "evidence_links": list(evidence_links),
                                    "total_bytes": sum(f["size_bytes"] for f in files)})
        return reference

    def verify_inventory(self, manifest_ref: str, *, _ancestors=()) -> dict:
        if manifest_ref in _ancestors:
            raise ValueError("Archive integrity failure: inventory cycle")
        path = self.path(manifest_ref)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "tuba.search.inventory.v1":
            raise ValueError("Unsupported inventory schema")
        for entry in manifest["files"]:
            file = self.path(entry["path"])
            try:
                if file.stat().st_size != entry["size_bytes"] or digest_file(file) != entry["sha256"]:
                    raise ValueError(f"Archive integrity failure: {entry['path']}")
            except FileNotFoundError:
                raise ValueError(f"Archive integrity failure: missing {entry['path']}") from None
        for linked in manifest.get("evidence_links", ()):
            self.verify_inventory(linked, _ancestors=(*_ancestors, manifest_ref))
        return manifest

    def recover(self, history) -> list[str]:
        terminal = {event["payload"].get("attempt_id") for event in history.events()
                    if event["kind"] in {"evaluation.completed", "evaluation.failed", "evaluation.interrupted", "attempt.recovered"}}
        recovered = []
        attempts = self.path("attempts")
        if not attempts.exists():
            return recovered
        for folder in sorted(attempts.iterdir()):
            no_links(folder)
            if not folder.is_dir() or folder.name in terminal:
                continue
            metadata = json.loads(self.path(f"attempts/{folder.name}/attempt.json").read_text(encoding="utf-8"))
            ref = self.seal_attempt(folder.name, "interrupted")
            history.append("attempt.recovered", {**metadata, "status": "interrupted", "evidence_manifest_ref": ref}, metadata["candidate_id"])
            recovered.append(folder.name)
        return recovered
