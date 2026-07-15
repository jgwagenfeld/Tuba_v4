from __future__ import annotations

import csv
import json
from dataclasses import replace

import pytest

from tests.reporting_fixtures import build_review_model
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.reporting import (
    EngineeringReviewPackage,
    ReportColumn,
    ReportTable,
    build_engineering_review,
    write_engineering_review,
)
from tuba.visualization import (
    GeometryAsset,
    SceneObject,
    VisualizationScene,
    write_engineering_review_with_scene,
)


@pytest.fixture
def solved_review() -> EngineeringReviewPackage:
    model = build_review_model()
    study = AnalysisStudy(
        id="study:hot",
        model_revision=4,
        solver_name="Code_Aster",
        load_case="Hot",
        work_dir="artifacts/hot",
        input_files={"mesh": "artifacts/hot/study.mail"},
        mesh_id="mesh:hot",
    )
    result = ResultState(
        id="result:hot",
        study_id=study.id,
        model_revision=4,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=study.mesh_id,
        node_displacements={"N0": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)},
        node_reactions={"N0": (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)},
        element_results={
            "E-20": {
                "forces_n1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "forces_n2": [-1.0, -2.0, -3.0, -4.0, -5.0, -6.0],
                "von_mises_n1": 12.0e6,
                "von_mises_n2": 15.0e6,
                "max_von_mises": 15.0e6,
            }
        },
        files={"result": "artifacts/hot/study.rmed"},
    )
    return build_engineering_review(
        model,
        studies=[study],
        result_states=[result],
        package_id="review:solved",
        created_at="2026-07-15T00:00:00Z",
    )


def test_write_engineering_review_exports_one_contract_to_all_formats(
    tmp_path, solved_review
):
    output = write_engineering_review(
        solved_review, tmp_path, title="HOT-100 engineering review"
    )

    payload = json.loads(output.review_path.read_text(encoding="utf-8"))
    manifest = json.loads(output.manifest_path.read_text(encoding="utf-8"))
    html = output.index_path.read_text(encoding="utf-8")

    assert payload == solved_review.to_dict()
    assert manifest["review_uri"] == "review.json"
    assert manifest["reports"]["line_list"] == "reports/line_list.csv"
    assert output.scene_uri is None
    assert "scene_uri" not in manifest
    assert "@media print" in html
    assert "FE Von Mises (not piping-code stress)" in html
    assert "not solved" not in html.lower()


def test_csv_headers_follow_columns_and_nested_values_are_compact_sorted_json(
    tmp_path, solved_review
):
    output = write_engineering_review(solved_review, tmp_path)
    table = solved_review.table("line_list")

    with output.csv_paths["line_list"].open(
        encoding="utf-8", newline=""
    ) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == [column.id for column in table.columns]
    bend_row = rows[1]
    bend_geometry = bend_row[rows[0].index("bend_geometry")]
    assert bend_geometry == json.dumps(
        table.rows[0]["bend_geometry"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_printable_html_has_fixed_section_order_csv_links_and_escaped_content(
    tmp_path, solved_review
):
    unsafe_table = ReportTable(
        id="unsafe",
        title="Unsafe <table>",
        source="model",
        columns=(ReportColumn("value", "Value <label>"),),
        rows=({"value": '<script>alert("bad")</script>'},),
    )
    review = replace(
        solved_review,
        project_name="HOT & <100>",
        tables=solved_review.tables + (unsafe_table,),
    )

    output = write_engineering_review(
        review, tmp_path, title="Review <draft> & evidence"
    )
    html = output.index_path.read_text(encoding="utf-8")

    positions = [html.index(f">{heading}<") for heading in (
        "Summary",
        "Model",
        "Load Cases",
        "Results",
        "Compliance",
        "Diagnostics",
    )]
    assert positions == sorted(positions)
    assert 'href="reports/line_list.csv"' in html
    assert 'href="reports/unsafe.csv"' in html
    assert "Review &lt;draft&gt; &amp; evidence" in html
    assert "HOT &amp; &lt;100&gt;" in html
    assert "Unsafe &lt;table&gt;" in html
    assert "&lt;script&gt;alert(&quot;bad&quot;)&lt;/script&gt;" in html
    assert "<script>" not in html


def test_model_only_html_explicitly_marks_results_and_compliance_unavailable(tmp_path):
    review = build_engineering_review(
        build_review_model(),
        package_id="review:model-only",
        created_at="2026-07-15T00:00:00Z",
    )

    output = write_engineering_review(review, tmp_path)
    html = output.index_path.read_text(encoding="utf-8")

    assert "Results are unavailable because this review package has not been solved" in html
    assert "Compliance is unavailable because no piping-code compliance report was supplied" in html
    assert not any(word in html.lower() for word in ("approved", "certified", "signed"))


def test_repeated_writes_are_byte_deterministic_and_links_are_relative(
    tmp_path, solved_review
):
    first = write_engineering_review(solved_review, tmp_path, title="Stable review")
    first_bytes = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    second = write_engineering_review(solved_review, tmp_path, title="Stable review")
    second_bytes = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))

    assert first.root == second.root
    assert first_bytes == second_bytes
    assert manifest["review_uri"] == "review.json"
    assert all(not value.startswith(("/", "http:", "https:")) for value in manifest["reports"].values())
    assert first.review_path.read_bytes().endswith(b"\n")
    assert first.manifest_path.read_bytes().endswith(b"\n")


def test_visualization_adapter_preserves_scene_bundle_layout(tmp_path, solved_review):
    scene = VisualizationScene(
        scene_id="scene:review",
        model_id="model:HOT-100",
        objects=[
            SceneObject(
                id="object:E-20",
                kind="pipe",
                geometry_asset_id="geometry:E-20",
                entity_ref="element:E-20",
            )
        ],
        geometry_assets=[
            GeometryAsset(
                id="geometry:E-20",
                format="procedural_pipe",
                bounds=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                object_ids=["object:E-20"],
                generation_config={"entity_ref": "element:E-20"},
            )
        ],
    )

    output = write_engineering_review_with_scene(
        solved_review, tmp_path, scene=scene, title="Review with scene"
    )
    payload = json.loads(output.review_path.read_text(encoding="utf-8"))
    manifest = json.loads(output.manifest_path.read_text(encoding="utf-8"))

    assert output.scene_uri == "scene.json"
    assert payload["scene_uri"] == "scene.json"
    assert manifest["scene_uri"] == "scene.json"
    assert (tmp_path / "scene.json").is_file()
    assert (tmp_path / "metadata" / "objects.json").is_file()
    assert (tmp_path / "geometry" / "geometry_assets.json").is_file()
    assert (tmp_path / "geometry" / "geometry_E-20.json").is_file()


def test_visualization_adapter_with_no_scene_matches_core_export(tmp_path, solved_review):
    output = write_engineering_review_with_scene(solved_review, tmp_path, scene=None)

    assert output.scene_uri is None
    assert not (tmp_path / "scene.json").exists()
