"""Bind the already-tested solver-produced Pages tree to its immutable Actions run."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_code_aster_references import passed_reference_count


MANIFEST = "publication.json"


def file_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 1024:
            raise ValueError("Pages artifact must not contain links")
        if path.is_file() and path != root / MANIFEST:
            with path.open("rb") as stream:
                hashes[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    if not hashes:
        raise ValueError("Pages artifact is empty")
    return hashes


def attest(root: Path, sha: str, run_id: str, run_attempt: str, qualification: Path) -> None:
    if os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1":
        raise ValueError("Only the native Code_Aster integration job may attest Pages")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != sha:
        raise ValueError("Solver-produced Pages revision differs from checked-out source")
    passed_reference_count(qualification)
    retained = root / "qualification" / qualification.name
    retained.parent.mkdir(exist_ok=True)
    shutil.copyfile(qualification, retained)
    (root / MANIFEST).write_text(json.dumps({
        "schema": "tuba.pages-publication.v1", "source_sha": sha,
        "workflow_run_id": run_id, "workflow_run_attempt": run_attempt,
        "solver": "Code_Aster", "qualification": retained.relative_to(root).as_posix(),
        "files": file_hashes(root),
    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def verify(root: Path, sha: str, run_id: str, run_attempt: str) -> None:
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if (manifest.get("schema") != "tuba.pages-publication.v1" or manifest.get("solver") != "Code_Aster"
            or manifest.get("source_sha") != sha or manifest.get("workflow_run_id") != run_id
            or manifest.get("workflow_run_attempt") != run_attempt):
        raise ValueError("Pages artifact does not belong to the approved revision and Actions run")
    if manifest.get("files") != file_hashes(root) or manifest.get("qualification") not in manifest["files"]:
        raise ValueError("Pages artifact changed after solver qualification and browser checks")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attest", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sha = os.environ.get("SOURCE_SHA", os.environ.get("GITHUB_SHA", ""))
    run_id = os.environ.get("SOURCE_RUN_ID", os.environ.get("GITHUB_RUN_ID", ""))
    attempt = os.environ.get("SOURCE_RUN_ATTEMPT", os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    if not re.fullmatch(r"[a-f0-9]{40}", sha) or not run_id.isdecimal() or not attempt.isdecimal():
        parser.error("Expected immutable source SHA and numeric Actions run id/attempt")
    root = args.output.resolve()
    if args.command == "attest":
        attest(root, sha, run_id, attempt, Path(".build/qualification/code-aster-references.xml"))
    else:
        verify(root, sha, run_id, attempt)


if __name__ == "__main__":
    main()
