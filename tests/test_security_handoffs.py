"""Adversarial checks for current evidence, inert exports and bounded package metadata."""

import csv
import gzip
import io
import json
import shutil
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest

from tuba.project import main
from tuba.project import package
from tuba.project.study import study_scaffold
from tuba.reporting.csv_cells import spreadsheet_cell
from tuba.reporting.export import _csv_value, _write_table_csv, regenerate_received_review
from tuba.reporting.isometry import _csv
from tuba.reporting.model import EngineeringReviewPackage, ReportColumn, ReportTable

RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"


def test_viewer_scene_size_boundary_rejects_before_json_parser(tmp_path, monkeypatch):
    from tuba.visualization import viewer

    monkeypatch.setattr(viewer, "MAX_SCENE_BYTES", 32)
    scene = tmp_path / "scene.json"
    scene.write_bytes(b"{}" + b" " * 30)
    server, _ = viewer.create_server(tmp_path)
    server.server_close()
    scene.write_bytes(scene.read_bytes() + b" ")
    monkeypatch.setattr(viewer.json, "loads", lambda *_args: pytest.fail("oversized scene reached JSON parser"))
    with pytest.raises(ValueError, match="scene.json exceeds"):
        viewer.create_server(tmp_path)


@pytest.mark.parametrize("options", [{"line_segments": 4}, {"pipe_modelization": "POU_D_T"},
                                    {"pipe_modelization": "POU_D_T", "load_path": ["Operating"]}])
def test_explicit_cli_evidence_rejects_changed_settings_before_any_review(tmp_path, capsys, options):
    shutil.copyfile(RACK / "model.py", tmp_path / "model.py")
    study = study_scaffold("SecurityRack", ["Operating"]).replace("SOLVER_OPTIONS: dict = {}", f"SOLVER_OPTIONS = {options!r}")
    (tmp_path / "study.py").write_text(study, encoding="utf-8")
    output = tmp_path / "review"
    assert main([str(tmp_path), "--output", str(output), "--artifact-dir", str(RACK / "evidence" / "Operating")]) == 1
    error = capsys.readouterr().err
    assert "current verified Code_Aster evidence" in error or "POU_D_T pipe pressure is unsupported" in error
    assert not output.exists()


def test_explicit_cli_matching_evidence_publishes_and_runs_current_study_check(tmp_path):
    shutil.copyfile(RACK / "model.py", tmp_path / "model.py")
    (tmp_path / "study.py").write_text(study_scaffold("SecurityRack", ["Operating"]) +
        "\ndef check(solved):\n    assert solved.runs['Operating'].result_state.metadata['result_trust'] == 'verified'\n", encoding="utf-8")
    assert main([str(tmp_path), "--output", str(tmp_path / "review"), "--artifact-dir", str(RACK / "evidence" / "Operating")]) == 0
    assert (tmp_path / "review" / "review_scene" / "scene.json").exists()
    with (tmp_path / "study.py").open("a", encoding="utf-8") as source:
        source.write("\ndef check(solved):\n    raise ValueError('current study rejects this result')\n")
    assert main([str(tmp_path), "--output", str(tmp_path / "rejected"), "--artifact-dir", str(RACK / "evidence" / "Operating")]) == 1
    assert not (tmp_path / "rejected").exists()


@pytest.mark.parametrize("text", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", " \t=1", "\x00 \r@SUM(A1)", "\u2003+1", "\nlabel"])
def test_every_python_csv_boundary_neutralizes_text_and_preserves_numbers(tmp_path, text):
    assert spreadsheet_cell(text) == "'" + text
    assert _csv_value(text) == "'" + text
    table = ReportTable("unsafe", "Test", (ReportColumn(text, "Text"), ReportColumn("number", "Number")),
                        ({text: text, "number": -12.5},), "model")
    path = _write_table_csv(table, tmp_path / "unsafe.csv", tmp_path.resolve())
    rows = list(csv.reader(io.StringIO(path.read_bytes().decode("utf-8"))))
    assert rows[0][0] == rows[1][0] == "'" + text
    assert rows[1][1] == "-12.5"
    rows = list(csv.reader(io.StringIO(_csv([{text: text, "number": -12.5}]))))
    assert rows[0][0] == rows[1][0] == "'" + text
    assert rows[1][1] == "-12.5"
    assert spreadsheet_cell(-12.5) == -12.5


@pytest.mark.parametrize("format", ["zip", "tgz"])
def test_package_long_paths_reject_before_metadata_or_ancestor_allocation(tmp_path, monkeypatch, format):
    archive = tmp_path / ("long." + format)
    if format == "zip":
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("a/" * 30000 + "payload", b"x")
        monkeypatch.setattr(zipfile, "ZipFile", lambda *args, **kwargs: pytest.fail("must reject before ZipFile allocation"))
    else:
        with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
            member = tarfile.TarInfo("a/" * 30000 + "payload")
            member.size = 1
            bundle.addfile(member, io.BytesIO(b"x"))
    monkeypatch.setattr(package, "PurePosixPath", lambda *args: pytest.fail("must reject before ancestor allocation"))
    with pytest.raises(ValueError, match="path"):
        package.inspect_project_package(archive)


def test_package_cannot_understate_central_directory_entry_count(tmp_path, monkeypatch):
    archive = tmp_path / "understated.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("model.py", b"x")
        bundle.writestr("other.py", b"x")
    original = archive.read_bytes()
    fields = list(struct.unpack("<4s4H2LH", original[-22:]))
    fields[3] = fields[4] = 1
    archive.write_bytes(original[:-22] + struct.pack("<4s4H2LH", *fields))
    monkeypatch.setattr(zipfile, "ZipFile", lambda *args, **kwargs: pytest.fail("must reject before ZipFile allocation"))
    with pytest.raises(ValueError, match="entry count differs"):
        package.inspect_project_package(archive)


def test_package_rejects_displaced_zip_directory_before_eager_parser(tmp_path, monkeypatch):
    archive = tmp_path / "displaced.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("model.py", b"x")
    original = archive.read_bytes()
    fields = struct.unpack("<4s4H2LH", original[-22:])
    directory = original[fields[6]:-22]
    # The declared directory is valid, but ZipFile would parse the second copy.
    archive.write_bytes(original[:-22] + directory + original[-22:])
    monkeypatch.setattr(zipfile, "ZipFile", lambda *args, **kwargs: pytest.fail("must reject before ZipFile allocation"))
    with pytest.raises(ValueError, match="directory bounds"):
        package.inspect_project_package(archive)


@pytest.mark.parametrize("header_type", [tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME])
@pytest.mark.parametrize("budget", ["depth", "bytes"])
def test_package_bounds_recursive_tar_headers_before_first_member(tmp_path, monkeypatch, header_type, budget):
    archive = tmp_path / "nested.tgz"
    payload = b"10 path=x\n" if header_type == tarfile.XHDTYPE else b"x\0"
    header = tarfile.TarInfo("metadata")
    header.type, header.size = header_type, len(payload)
    count = package.MAX_PATH_DEPTH + 1 if budget == "depth" else 3
    if budget == "bytes":
        monkeypatch.setattr(package, "MAX_TAR_METADATA_BYTES", 2048)
    member = tarfile.TarInfo("model.py")
    block = header.tobuf() + payload.ljust(tarfile.BLOCKSIZE, b"\0")
    archive.write_bytes(gzip.compress(block * count + member.tobuf() + b"\0" * 1024))
    with pytest.raises(ValueError, match="metadata.*" + ("depth" if budget == "depth" else "cumulative")):
        package.inspect_project_package(archive)


@pytest.mark.parametrize("zip64", [False, True])
def test_package_declared_entry_budget_rejects_before_allocation(tmp_path, monkeypatch, zip64):
    archive = tmp_path / "huge.zip"
    count = 2 * package.MAX_FILES + 2
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("model.py", b"x")
    original = archive.read_bytes()
    body = original[:-22]
    end_fields = list(struct.unpack("<4s4H2LH", original[-22:]))
    if zip64:
        record = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45, 0, 0, count, count, end_fields[5], end_fields[6])
        locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, len(body), 1)
        end = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 65535, 65535, 0xffffffff, 0xffffffff, 0)
        archive.write_bytes(body + record + locator + end)
    else:
        end_fields[3] = end_fields[4] = count
        archive.write_bytes(body + struct.pack("<4s4H2LH", *end_fields))
    monkeypatch.setattr(zipfile, "ZipFile", lambda *args, **kwargs: pytest.fail("must reject before ZipFile allocation"))
    with pytest.raises(ValueError, match="central directory exceeds"):
        package.inspect_project_package(archive)


def test_received_report_is_regenerated_with_escaped_text_and_script_policy(tmp_path):
    review = EngineeringReviewPackage("review:received", "2026-10-07", "<script>window.attack=1</script>",
                                     "", 0, "not_solved", ())
    (tmp_path / "review.json").write_text(json.dumps(review.to_dict()), encoding="utf-8")
    (tmp_path / "index.html").write_text("<script>fetch('/api/script')</script>", encoding="utf-8")
    regenerate_received_review(tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;script&gt;window.attack=1&lt;/script&gt;" in html
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
