"""Reject releases whose Git tag differs from this checkout's metadata."""

from __future__ import annotations

from pathlib import Path
import sys
import tomllib


PROJECT_FILE = Path(__file__).resolve().parents[1] / "pyproject.toml"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: check_release_tag.py REF_TYPE REF_NAME", file=sys.stderr)
        return 2
    ref_type, tag = args
    if ref_type != "tag":
        print(
            f"release requires a Git tag ref, received {ref_type!r} named {tag!r}",
            file=sys.stderr,
        )
        return 1
    with PROJECT_FILE.open("rb") as stream:
        package_version = tomllib.load(stream)["project"]["version"]
    if tag != f"v{package_version}":
        print(
            f"release tag {tag!r} does not match package version {package_version!r}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
