"""A handoff preserves source and refuses unsafe/incomplete archives before extraction."""
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tarfile
import zipfile

import pytest

from tuba.project import load_project
from tuba.project import package
from tuba.studio_launcher import create_project


@pytest.mark.parametrize("suffix", [".tubaproject", ".tgz", ".tar.gz"])
def test_clean_roundtrip_and_native_archive_inspection(tmp_path, suffix):
    root = tmp_path / "Piping ü"
    create_project(root)
    for name in ("units/helper.py", "geometry/component.step", "data/temperatures.csv"):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"# original project input\n")
    for name in (".tuba/state.json", ".build/scene.json", ".tmp/old.txt", "node_modules/package.json",
                 "evidence/Operating/study.rmed", "old.tubaproject", "old.zip", "__pycache__/model.pyc", ".env", "private.key"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("do not share")
    archive = tmp_path / ("handoff" + suffix)
    result = package.export_project_package(root, archive)
    expected = {"manifest.json", *["project/" + name for name in (
        "model.py", "study.py", "units/helper.py", "geometry/component.step", "data/temperatures.csv")]}
    if suffix == ".tubaproject":
        with zipfile.ZipFile(archive) as bundle:
            assert set(bundle.namelist()) == expected
            assert json.loads(bundle.read("manifest.json"))["format"] == package.FORMAT
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            assert set(bundle.getnames()) == expected
            assert json.load(bundle.extractfile("manifest.json"))["format"] == package.FORMAT
    opened = package.unpack_project_package(archive, tmp_path / "opened ü")
    for record in result["files"]:
        assert (opened / record["path"]).read_bytes() == (root / record["path"]).read_bytes()
    assert load_project(opened).load_settings().operations == ("Operating",)
    assert len(load_project(opened).run_model()["model"].elements) == 1
    with pytest.raises(FileExistsError):
        package.unpack_project_package(archive, opened)
    with pytest.raises(FileExistsError):
        package.export_project_package(root, archive)
    with pytest.raises(ValueError, match="Saved results"):
        package.export_project_package(root, tmp_path / "results.tubaproject", include_results=True)


@pytest.mark.parametrize("bad", ["../outside.py", "/absolute.py", "C:/outside.py", "bad\\path.py", "CON.txt", "trailing. ", ".tuba/solve.lock"])
def test_unsafe_paths_never_create_a_working_folder(tmp_path, bad):
    archive = tmp_path / "bad.zip"
    data = b"model = None"
    records = [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name in ("model.py", bad)]
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps({"format": package.FORMAT, "project_root": "project", "include_results": False, "files": records}))
        for record in records:
            bundle.writestr("project/" + record["path"], data)
    with pytest.raises(ValueError):
        package.unpack_project_package(archive, tmp_path / "working")
    assert not (tmp_path / "working").exists()
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.parametrize("change", ["checksum", "extra", "link", "case", "directory_case", "size", "format"])
def test_corrupt_or_ambiguous_archives_are_refused(tmp_path, monkeypatch, change):
    root = tmp_path / "source"
    create_project(root)
    original = tmp_path / "source.tubaproject"
    package.export_project_package(root, original)
    archive = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(archive, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if change == "checksum" and info.filename == "project/model.py":
                data = b"X" * len(data)
            if change == "link" and info.filename == "project/model.py":
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            if change == "format" and info.filename == "manifest.json":
                data = data.replace(b"tuba.project-package.v1", b"tuba.project-package.v9")
            target.writestr(info, data)
        if change == "extra":
            target.writestr("project/unlisted.py", "data")
        if change == "case":
            target.writestr("project/MODEL.py", "data")
        if change == "directory_case":
            target.writestr("project/Units/a.py", "data")
            target.writestr("project/units/b.py", "data")
    if change == "size":
        monkeypatch.setattr(package, "MAX_EXPANDED_BYTES", 1)
    with pytest.raises(ValueError):
        package.unpack_project_package(archive, tmp_path / "working")
    assert not (tmp_path / "working").exists()


def test_workspace_helpers_require_explicit_source_and_destination_approval(tmp_path, monkeypatch):
    # Gallery projects import shared helpers from their own workspace
    # (examples/<project> -> examples.code_aster_artifact_review); those come along.
    workspace = tmp_path / "workspace"
    root = workspace / "examples" / "demo"
    root.parent.mkdir(parents=True)
    create_project(root)
    (workspace / "examples" / "shared.py").write_text("from examples.deeper import VALUE\n")
    (workspace / "examples" / "deeper.py").write_text("VALUE = 2.5\n")
    (root / "model.py").write_text((root / "model.py").read_text(encoding="utf-8")
                                   + "\nfrom examples.shared import VALUE\nassert VALUE == 2.5\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(workspace))
    archive = tmp_path / "demo.tgz"
    with pytest.raises(ValueError, match="outside this project"):
        package.export_project_package(root, archive)
    assert not archive.exists()
    manifest = package.export_project_package(root, archive, external_sources={
        "examples/shared.py": workspace / "examples" / "shared.py",
        "examples/deeper.py": workspace / "examples" / "deeper.py",
    })
    assert {"examples/shared.py", "examples/deeper.py"} <= {record["path"] for record in manifest["files"]}
    assert all("external_source" in record for record in manifest["files"] if record["path"].startswith("examples/"))

    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != str(workspace)])
    monkeypatch.chdir(tmp_path)
    opened = package.unpack_project_package(archive, tmp_path / "opened")
    assert load_project(opened).run_model()["model"] is not None


def test_source_is_inspected_without_execution_and_external_workspace_imports_are_refused(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "model.py").write_text("raise RuntimeError('never executed by packing')\n")
    package.export_project_package(root, tmp_path / "safe.tubaproject")
    outside = tmp_path / "foreign"
    outside.mkdir()
    (outside / "helper.py").write_text("print('must not run')\n")
    monkeypatch.syspath_prepend(str(outside))
    (root / "model.py").write_text("import helper\n")
    with pytest.raises(ValueError, match="outside this project"):
        package.plan_project_package(root)
    (root / "model.py").write_text("from pathlib import Path\np = Path('C:/outside.step')\n")
    with pytest.raises(ValueError, match="absolute input path"):
        package.plan_project_package(root)


def test_source_changes_during_export_leave_no_package(tmp_path, monkeypatch):
    root = tmp_path / "source"
    create_project(root)
    original_write = zipfile.ZipFile.write
    def change_after_write(bundle, filename, *args, **kwargs):
        result = original_write(bundle, filename, *args, **kwargs)
        if Path(filename).name == "model.py":
            (root / "model.py").write_text("# changed while sharing\n")
        return result
    monkeypatch.setattr(zipfile.ZipFile, "write", change_after_write)
    with pytest.raises(ValueError, match="changed during export"):
        package.export_project_package(root, tmp_path / "changed.tubaproject")
    assert not (tmp_path / "changed.tubaproject").exists()


def test_linked_source_is_refused(tmp_path):
    root = tmp_path / "source"
    create_project(root)
    outside = tmp_path / "outside.py"
    outside.write_text("# shared by a different project\n")
    try:
        (root / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("Creating links requires privilege on this Windows host; Linux qualification covers it.")
    with pytest.raises(ValueError, match="linked input"):
        package.plan_project_package(root)


@pytest.mark.parametrize("suffix", [".tubaproject", ".tgz"])
def test_imported_cad_reloads_after_moving_the_package(tmp_path, suffix):
    from tests.test_studio_geometry import binary_triangle
    root = tmp_path / "CAD project"
    root.mkdir()
    (root / "geometry").mkdir()
    (root / "geometry" / "reference.stl").write_bytes(binary_triangle())
    (root / "model.py").write_text(
        "from pathlib import Path\nfrom tuba import Model\nmodel = Model('Portable CAD')\n"
        "model.import_stl(str(Path(__file__).resolve().parent / 'geometry' / 'reference.stl'), "
        "id='reference', unit_scale_to_m=.001, placement={'origin': [2,3,4], 'rotation': [1,0,0,0]})\n")
    before = load_project(root).run_model()["model"]
    archive = tmp_path / ("CAD" + suffix)
    package.export_project_package(root, archive)
    after = load_project(package.unpack_project_package(archive, tmp_path / "moved CAD")).run_model()["model"]
    assert before.cad_assets["reference_asset"].content_digest == after.cad_assets["reference_asset"].content_digest
    assert before.cad_assets["reference_asset"].placement == after.cad_assets["reference_asset"].placement


@pytest.mark.parametrize("change", ["symlink", "hardlink", "fifo", "device", "sparse", "traversal",
                                    "duplicate", "case", "checksum", "expanded", "pax_size", "truncated", "gzip_crc"])
def test_tgz_unsafe_or_corrupt_payloads_are_refused_before_extraction(tmp_path, change):
    archive = tmp_path / "unsafe.tgz"
    data = b"model = None\n"
    record = {"path": "model.py", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = {"format": package.FORMAT, "project_root": "project", "include_results": False,
                "files": [record], "size_bytes": len(data)}
    def add(bundle, name, body):
        info = tarfile.TarInfo(name)
        info.size = len(body)
        bundle.addfile(info, io.BytesIO(body))
    with tarfile.open(archive, "w:gz", format=tarfile.GNU_FORMAT) as bundle:
        add(bundle, "manifest.json", json.dumps(manifest).encode())
        if change in {"symlink", "hardlink", "fifo", "device", "sparse", "expanded", "pax_size"}:
            info = tarfile.TarInfo("project/model.py")
            info.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE,
                         "device": tarfile.CHRTYPE, "sparse": tarfile.GNUTYPE_SPARSE,
                         "expanded": tarfile.REGTYPE, "pax_size": tarfile.XHDTYPE}[change]
            info.linkname = "../../outside.py"
            if change == "expanded":
                info.size = package.MAX_EXPANDED_BYTES + 1
            elif change == "pax_size":
                info.size = 16 * 1024**2
            if change == "expanded":
                bundle.fileobj.write(info.tobuf(format=tarfile.GNU_FORMAT))
            else:
                bundle.addfile(info)
        else:
            add(bundle, "../outside.py" if change == "traversal" else "project/model.py",
                b"X" * len(data) if change == "checksum" else data)
            if change in {"duplicate", "case"}:
                add(bundle, "project/model.py" if change == "duplicate" else "project/MODEL.py", data)
    if change == "truncated":
        archive.write_bytes(archive.read_bytes()[:-8])
    elif change == "gzip_crc":
        payload = bytearray(archive.read_bytes())
        payload[-8] ^= 1
        archive.write_bytes(payload)
    with pytest.raises(ValueError):
        package.unpack_project_package(archive, tmp_path / "working")
    assert not (tmp_path / "working").exists()
    assert not (tmp_path / "outside.py").exists()


def test_native_tar_directory_entries_are_accepted_and_content_detection_ignores_extension(tmp_path):
    root = tmp_path / "source"
    create_project(root)
    original = tmp_path / "original.tgz"
    package.export_project_package(root, original)
    archive = tmp_path / "received.tubaproject"
    with tarfile.open(original, "r:gz") as source, tarfile.open(archive, "w:gz") as target:
        directory = tarfile.TarInfo("project/")
        directory.type = tarfile.DIRTYPE
        target.addfile(directory)
        for info in source:
            target.addfile(info, source.extractfile(info))
    assert package.inspect_project_package(archive)["format"] == package.FORMAT
    opened = package.unpack_project_package(archive, tmp_path / "working")
    assert (opened / "model.py").read_bytes() == (root / "model.py").read_bytes()
