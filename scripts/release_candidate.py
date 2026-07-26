"""Build an isolated Git tree from an explicit release-change overlay."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Iterable


def _run_git(
    root: Path,
    env: dict[str, str],
    *args: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        check=True,
        capture_output=capture_output,
        text=capture_output,
    )


def _is_present_or_tracked(root: Path, env: dict[str, str], path: str) -> bool:
    if root.joinpath(path).exists():
        return True
    tracked = _run_git(root, env, "ls-files", "--cached", "-z", "--", path, capture_output=True)
    return bool(tracked.stdout)


def changed_paths(root: Path) -> list[str]:
    """Return every current tracked change plus non-ignored untracked files."""

    root = root.resolve()
    env = os.environ.copy()
    tracked = _run_git(
        root,
        env,
        "diff",
        "--no-renames",
        "--name-only",
        "-z",
        "HEAD",
        capture_output=True,
    ).stdout
    untracked = _run_git(
        root,
        env,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        capture_output=True,
    ).stdout
    return sorted({path for path in f"{tracked}{untracked}".split("\0") if path})


def create_candidate_tree(root: Path, index_file: Path, overlay_paths: Iterable[str]) -> str:
    """Return a tree containing HEAD plus the requested available changes.

    A missing path is retained in the overlay when it exists in the seeded
    index, which stages a current deletion. Once that deletion is committed,
    the path is absent from both the worktree and index and is safely omitted.
    The caller's real Git index is never touched.
    """

    root = root.resolve()
    index_file = index_file.resolve()
    index_file.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(index_file)
    _run_git(root, env, "read-tree", "HEAD")

    requested = list(dict.fromkeys(overlay_paths))
    selected = [path for path in requested if _is_present_or_tracked(root, env, path)]

    if ".gitattributes" in selected:
        _run_git(root, env, "add", "-A", "--", ".gitattributes")
        selected.remove(".gitattributes")
    if selected:
        _run_git(root, env, "add", "-A", "--", *selected)

    return _run_git(root, env, "write-tree", capture_output=True).stdout.strip()
