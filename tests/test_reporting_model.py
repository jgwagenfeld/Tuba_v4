import json

import pytest

from tuba.reporting import (
    EngineeringReviewError,
    EngineeringReviewPackage,
    ReportColumn,
    ReportTable,
    ReviewDiagnostic,
    ReviewProvenance,
)


def test_package_serializes_tables_in_declared_order():
    summary = ReportTable(
        id="project_summary",
        title="Project summary",
        columns=(ReportColumn("project_name", "Project"),),
        rows=({"project_name": "HOT-100"},),
        source="model",
    )
    nodes = ReportTable(
        id="nodes",
        title="Nodes",
        columns=(ReportColumn("id", "Node"),),
        rows=({"id": "N1"},),
        source="model",
    )
    package = EngineeringReviewPackage(
        package_id="review:hot-100:r0",
        created_at="2026-07-15T00:00:00Z",
        project_name="HOT-100",
        model_standard="ASME_B31.3",
        model_revision=0,
        analysis_status="not_solved",
        tables=(summary, nodes),
    )

    assert package.table("project_summary") is summary
    assert list(package.to_dict()["tables"]) == ["project_summary", "nodes"]


def test_package_rejects_duplicate_table_ids():
    table = ReportTable(id="nodes", title="Nodes", columns=(), rows=(), source="model")

    with pytest.raises(EngineeringReviewError, match="Duplicate report table"):
        EngineeringReviewPackage(
            package_id="review:test",
            created_at="2026-07-15T00:00:00Z",
            project_name="Test",
            model_standard="ASME_B31.3",
            model_revision=0,
            analysis_status="not_solved",
            tables=(table, table),
        )


def test_package_serialization_is_recursively_json_safe_and_deterministic():
    table = ReportTable(
        id="nodes",
        title="Nodes",
        columns=(ReportColumn("details", "Details", description="Nested values"),),
        rows=({"details": {"z": (2, {"b": True, "a": None}), "a": 1}},),
        source="model",
    )
    provenance = ReviewProvenance(
        kind="model",
        id="model:r0",
        files={"study": "artifacts/study.comm", "mesh": "artifacts/study.mail"},
        metadata={"z": ("last",), "a": {"two": 2, "one": 1}},
    )
    diagnostic = ReviewDiagnostic(
        severity="info",
        code="MODEL_ONLY",
        source="model",
        message="No Code_Aster result artifact was supplied.",
        target="package:review:test",
    )
    package = EngineeringReviewPackage(
        package_id="review:test",
        created_at="2026-07-15T00:00:00Z",
        project_name="Test",
        model_standard="ASME_B31.3",
        model_revision=0,
        analysis_status="not_solved",
        tables=(table,),
        units={"stress": "Pa", "force": "N", "length": "m"},
        coordinate_system={"up_axis": "Z", "origin": (0.0, 0.0, 0.0)},
        provenance=(provenance,),
        diagnostics=(diagnostic,),
        scene_uri="scene.json",
    )

    payload = package.to_dict()

    assert list(payload["units"]) == ["force", "length", "stress"]
    assert list(payload["provenance"][0]["files"]) == ["mesh", "study"]
    assert list(payload["provenance"][0]["metadata"]) == ["a", "z"]
    assert payload["coordinate_system"]["origin"] == [0.0, 0.0, 0.0]
    assert payload["tables"]["nodes"]["rows"][0]["details"]["z"] == [
        2,
        {"a": None, "b": True},
    ]
    assert payload["diagnostics"] == [
        {
            "severity": "info",
            "code": "MODEL_ONLY",
            "source": "model",
            "message": "No Code_Aster result artifact was supplied.",
            "target": "package:review:test",
        }
    ]
    assert payload["scene_uri"] == "scene.json"
    json.dumps(payload)


def test_package_raises_explicit_error_for_missing_table():
    package = EngineeringReviewPackage(
        package_id="review:test",
        created_at="2026-07-15T00:00:00Z",
        project_name="Test",
        model_standard="ASME_B31.3",
        model_revision=0,
        analysis_status="not_solved",
        tables=(),
    )

    with pytest.raises(EngineeringReviewError, match=r"Unknown report table 'nodes'\."):
        package.table("nodes")


def test_reporting_public_api_does_not_export_future_builder_names():
    import tuba.reporting as reporting

    assert reporting.__all__ == (
        "EngineeringReviewError",
        "EngineeringReviewPackage",
        "ReportColumn",
        "ReportTable",
        "ReviewDiagnostic",
        "ReviewProvenance",
    )
    assert not hasattr(reporting, "build_engineering_review")
    assert not hasattr(reporting, "write_engineering_review")
