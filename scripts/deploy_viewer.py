"""Publish the packaged viewer and completed review bundles to a static web folder.

    python scripts/deploy_viewer.py viewer /path/to/web/tuba
    python scripts/deploy_viewer.py bundle /path/to/project-review /path/to/web/tuba

The bundle command accepts a project output containing review_scene/ or a scene
bundle directly. It copies the complete bundle, including its printable report.
This publishes existing artifacts; authoring and Code_Aster solving happen first.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tuba.visualization.viewer import viewer_assets_path

_SHELL_NAMES = {
    "assets", "licenses", "downloads", "gallery", "index.html", "favicon.svg",
    "profiles.json", "bundles.json", "tuba-browser.zip",
}


def _reject_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"Refusing linked path: {path}")


def _plain_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    for part in (path, *path.parents):
        _reject_link(part)
    return path.resolve()


def _check_tree(root: Path) -> None:
    _plain_path(root)
    pending = [root] if root.is_dir() else []
    while pending:
        for path in pending.pop().iterdir():
            _reject_link(path)
            if path.is_dir():
                pending.append(path)


def _separate(source: Path, destination: Path) -> None:
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and web root must be separate, non-nested folders.")


def _valid_id(value: str) -> str:
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value)
            or value.endswith(".") or value.lower() in _SHELL_NAMES
            or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", value.split(".")[0], re.I)):
        raise ValueError(f"Bundle id must be a safe folder name, distinct from viewer assets: {value!r}")
    return value


def _json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _catalog(web_root: Path) -> list:
    path = _plain_path(web_root / "bundles.json")
    if not path.exists():
        return []
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError(f"Expected a list of bundle ids or catalog entries: {path}")
    ids = [_valid_id(entry.get("id") if isinstance(entry, dict) else entry) for entry in catalog]
    if len({value.casefold() for value in ids}) != len(ids):
        raise ValueError(f"Duplicate bundle ids in {path}")
    return catalog


def _publish_tree(source: Path, destination: Path, *, catalog: list | None = None) -> None:
    """Stage the copy, swap it in, and restore the old tree if publishing fails."""
    _check_tree(source)
    _check_tree(destination)
    work = destination.with_name(f".{destination.name}.deploy-{uuid4().hex}")
    work.mkdir()
    retained = False
    try:
        staged, backup = work / "new", work / "old"
        shutil.copytree(source, staged)
        if catalog is not None:
            (work / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            destination.replace(backup)
        try:
            staged.replace(destination)
            if catalog is not None:
                (work / "catalog.json").replace(destination.parent / "bundles.json")
        except BaseException:
            try:
                if destination.exists():
                    destination.replace(staged)
                if backup.exists():
                    backup.replace(destination)
            except BaseException as rollback_error:
                retained = True
                raise RuntimeError(f"Publish rollback failed; original files retained in {work}") from rollback_error
            raise
    finally:
        if not retained:
            _check_tree(work)
            shutil.rmtree(work)


def cmd_viewer(web_root: Path) -> None:
    source, web_root = _plain_path(Path(viewer_assets_path())), _plain_path(web_root)
    if not (source / "index.html").is_file():
        raise ValueError(f"Packaged viewer is incomplete: {source}")
    _separate(source, web_root)
    _check_tree(source)
    _catalog(web_root)  # Refuse a damaged catalog before changing the viewer.
    web_root.mkdir(parents=True, exist_ok=True)
    # ponytail: shell files update separately; use a new web root for uninterrupted viewer upgrades.
    for item in source.iterdir():
        destination = _plain_path(web_root / item.name)
        if item.name == "bundles.json" and destination.exists():
            continue
        if item.is_dir():
            _publish_tree(item, destination)
        else:
            staged = destination.with_name(f".{item.name}.deploy-{uuid4().hex}")
            try:
                shutil.copy2(item, staged)
                staged.replace(destination)
            finally:
                staged.unlink(missing_ok=True)
    print(f"Viewer installed: {web_root}")


def cmd_bundle(output_dir: Path, web_root: Path) -> None:
    output_dir, web_root = _plain_path(output_dir), _plain_path(web_root)
    source = _plain_path(output_dir / "review_scene" if (output_dir / "review_scene").is_dir() else output_dir)
    if not (source / "scene.json").is_file():
        raise ValueError(f"No scene.json in {source}; build the review with python -m tuba.project first.")
    _check_tree(source)
    _json_object(source / "scene.json")
    review = _json_object(source / "review.json") if (source / "review.json").exists() else {}
    package_id = review.get("package_id", "")
    if not isinstance(package_id, str):
        raise ValueError("review.json package_id must be a string.")
    fallback = source.parent.name if source.name == "review_scene" else source.name
    bundle_id = _valid_id(package_id.removeprefix("review:") if package_id else fallback)
    _separate(source, web_root)
    catalog = _catalog(web_root)
    ids = [entry["id"] if isinstance(entry, dict) else entry for entry in catalog]
    if any(value.casefold() == bundle_id.casefold() and value != bundle_id for value in ids):
        raise ValueError(f"Bundle id differs only in case from an existing bundle: {bundle_id}")
    destination = _plain_path(web_root / bundle_id)
    if destination.exists() and bundle_id not in ids:
        raise ValueError(f"Refusing to replace an unregistered folder: {destination}")
    if bundle_id not in ids:
        catalog.append(bundle_id)
    web_root.mkdir(parents=True, exist_ok=True)
    # ponytail: one publisher per web root; add a filesystem lock for concurrent publishers.
    _publish_tree(source, destination, catalog=catalog)
    print(f"Bundle published: {destination}\nOpen the hosted viewer with ?bundle={bundle_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    viewer = commands.add_parser("viewer", help="Install or update the packaged viewer shell")
    viewer.add_argument("web_root", type=Path)
    bundle = commands.add_parser("bundle", help="Publish a completed review bundle")
    bundle.add_argument("output_dir", type=Path)
    bundle.add_argument("web_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "viewer":
            cmd_viewer(args.web_root)
        else:
            cmd_bundle(args.output_dir, args.web_root)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Publish failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
