"""Package the real Python geometry code for the static gallery's browser worker."""

from io import BytesIO
from pathlib import Path
import sys
import tomllib
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def browser_runtime_archive(root: Path = ROOT) -> bytes:
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
            for path in sorted((root / folder).rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
                if (path.is_file() and path.suffix in {".py", ".json", ".input", ".output", ".stl"}
                        and not {"_viewer", "__pycache__", "evidence", "reference"}.intersection(path.parts)):
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
    sys.stdout.buffer.write(browser_runtime_archive())
