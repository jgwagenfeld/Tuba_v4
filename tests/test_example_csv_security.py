"""Shipped custom CSV exports keep authored text inert without altering numbers."""

import csv
from pathlib import Path
from types import SimpleNamespace

from tuba.project import load_project


ROOT = Path(__file__).resolve().parents[1]


def test_custom_example_csv_exports_are_spreadsheet_safe(tmp_path, monkeypatch):
    rows = [{"element": " \t=1+1", "section": "@SUM(A1)", "force": -12.5}]
    steel = load_project(ROOT / "examples/steel-portal-frame").load_study()
    steel_csv = steel.write_section_forces(tmp_path, rows)

    preparation = load_project(ROOT / "examples/load-case-preparation").load_study()
    # Exercise only the custom CSV boundary; no solver artifacts are fabricated or published.
    run = SimpleNamespace(validate_for_publication=lambda _model: None,
        result_state=SimpleNamespace(metadata={"solve_attestation": {"solved_at": "unit-test"}}))
    study_globals = preparation.build_review.__globals__
    monkeypatch.setitem(study_globals, "import_code_aster_artifacts", lambda **_options: run)
    monkeypatch.setitem(study_globals, "force_rows", lambda *_args: rows)
    monkeypatch.setitem(study_globals, "check", lambda *_args: None)
    monkeypatch.setitem(study_globals, "stage_runs", lambda runs, _root: runs)
    monkeypatch.setitem(study_globals, "create_visual_deformed_geometry_state", lambda **_options: None)
    monkeypatch.setitem(study_globals, "build_visualization_scene", lambda *_args: None)
    monkeypatch.setitem(study_globals, "add_scene_label", lambda *_args, **_options: None)
    monkeypatch.setitem(study_globals, "build_engineering_review", lambda *_args, **_options: None)
    monkeypatch.setitem(study_globals, "write_engineering_review_with_scene",
                        lambda _review, root, **_options: root.mkdir(parents=True))
    output = preparation.build_review({"model": SimpleNamespace(project_name="CSV regression"), "__file__": "unused"},
                                     tmp_path / "preparation", artifact_dir=tmp_path)

    for path in (steel_csv, output / "user-check-forces.csv"):
        with path.open(encoding="utf-8", newline="") as source:
            exported = list(csv.DictReader(source))
        assert exported == [{"element": "' \t=1+1", "section": "'@SUM(A1)", "force": "-12.5"}]
