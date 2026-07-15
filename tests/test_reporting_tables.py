from __future__ import annotations

import math

import pytest

from tests.reporting_fixtures import build_review_model
from tuba.reporting.tables import build_model_tables


MODEL_TABLE_IDS = (
    "project_summary",
    "nodes",
    "line_list",
    "section_schedule",
    "materials",
    "supports",
    "load_cases",
)


@pytest.fixture
def review_model():
    return build_review_model()


def _table(tables, table_id):
    return next(table for table in tables if table.id == table_id)


def _rows(tables, table_id):
    return _table(tables, table_id).rows


def test_model_tables_retain_engineering_inputs(review_model):
    tables = build_model_tables(review_model)

    assert tuple(table.id for table in tables) == MODEL_TABLE_IDS
    pipe = next(
        row for row in _rows(tables, "section_schedule") if row["section"] == "PipeSec"
    )
    assert pipe["outer_diameter_m"] == 0.1143
    assert pipe["wall_thickness_m"] == 0.00602
    assert pipe["corrosion_allowance_m"] == 0.001
    support = next(
        row for row in _rows(tables, "supports") if row["support_id"] == "SUP-1"
    )
    assert support["blocked_dof"] == [True, True, True, True, True, True]
    hot = next(row for row in _rows(tables, "load_cases") if row["load_case"] == "Hot")
    assert hot["nodal_load_count"] == 1
    assert hot["field_count"] == 1


def test_model_table_rows_are_sorted_by_stable_ids(review_model):
    tables = build_model_tables(review_model)

    assert [row["node_id"] for row in _rows(tables, "nodes")] == ["N0", "N1", "N2", "N3"]
    assert [row["element_id"] for row in _rows(tables, "line_list")] == [
        "E-10",
        "E-20",
        "E-30",
    ]
    assert [row["section"] for row in _rows(tables, "section_schedule")] == [
        "BarSec",
        "CableSec",
        "IBeamSec",
        "PipeSec",
        "RectSec",
    ]
    assert [row["material"] for row in _rows(tables, "materials")] == [
        "Aluminium",
        "Steel",
    ]
    assert [row["support_id"] for row in _rows(tables, "supports")] == ["SUP-1", "SUP-2"]
    assert [row["load_case"] for row in _rows(tables, "load_cases")] == ["Hot", "Upset"]


def test_line_list_uses_node_distance_for_straights_and_arc_length_for_bends(review_model):
    tables = build_model_tables(review_model)
    rows = {row["element_id"]: row for row in _rows(tables, "line_list")}

    assert rows["E-20"]["length_m"] == 5.0
    assert rows["E-10"]["length_m"] == pytest.approx(math.pi / 2.0)
    assert rows["E-30"]["length_m"] == 2.5
    assert rows["E-10"]["route_id"] == "R-100"
    assert rows["E-10"]["station_start_m"] == 5.0
    assert rows["E-10"]["bend_geometry"]["generation_mode"] == "bend_in_plane"
    assert rows["E-30"]["route_id"] is None


def test_section_schedule_includes_count_length_and_authoritative_mass(review_model):
    tables = build_model_tables(review_model)
    rows = {row["section"]: row for row in _rows(tables, "section_schedule")}

    pipe_length = 5.0 + math.pi / 2.0
    pipe_mass = pipe_length * review_model.sections["PipeSec"].area * 7850.0
    assert rows["PipeSec"]["element_count"] == 2
    assert rows["PipeSec"]["total_length_m"] == pytest.approx(pipe_length)
    assert rows["PipeSec"]["total_mass_kg"] == pytest.approx(pipe_mass)

    rect_mass = 2.5 * review_model.sections["RectSec"].area * 2700.0
    assert rows["RectSec"]["element_count"] == 1
    assert rows["RectSec"]["total_length_m"] == 2.5
    assert rows["RectSec"]["total_mass_kg"] == pytest.approx(rect_mass)
    assert rows["BarSec"]["element_count"] == 0
    assert rows["BarSec"]["total_length_m"] == 0.0
    assert rows["BarSec"]["total_mass_kg"] == 0.0


def test_every_section_type_serializes_all_defining_dimensions_and_properties(review_model):
    tables = build_model_tables(review_model)
    rows = {row["section"]: row for row in _rows(tables, "section_schedule")}

    assert {
        key: rows["PipeSec"][key]
        for key in ("outer_diameter_m", "wall_thickness_m", "corrosion_allowance_m")
    } == {
        "outer_diameter_m": 0.1143,
        "wall_thickness_m": 0.00602,
        "corrosion_allowance_m": 0.001,
    }
    assert {
        key: rows["BarSec"][key] for key in ("outer_diameter_m", "wall_thickness_m")
    } == {
        "outer_diameter_m": 0.04,
        "wall_thickness_m": 0.005,
    }
    assert {key: rows["CableSec"][key] for key in ("radius_m", "pretension_n")} == {
        "radius_m": 0.012,
        "pretension_n": 12000.0,
    }
    assert {
        key: rows["RectSec"][key]
        for key in ("height_y_m", "height_z_m", "thickness_y_m", "thickness_z_m")
    } == {
        "height_y_m": 0.2,
        "height_z_m": 0.1,
        "thickness_y_m": 0.01,
        "thickness_z_m": 0.008,
    }
    assert rows["IBeamSec"]["profile_name"] == "IPE100"
    assert rows["IBeamSec"]["properties"] == review_model.sections["IBeamSec"].properties


def test_materials_and_load_cases_preserve_nested_authoritative_definitions(review_model):
    tables = build_model_tables(review_model)
    steel = next(row for row in _rows(tables, "materials") if row["material"] == "Steel")
    assert steel["allowable_stress"] == [
        {"temperature_c": 20.0, "allowable_stress_pa": 138.0e6},
        {"temperature_c": 150.0, "allowable_stress_pa": 112.0e6},
    ]

    hot = next(row for row in _rows(tables, "load_cases") if row["load_case"] == "Hot")
    assert hot["nodal_forces"] == [
        {
            "node": "N3",
            "components": [1000.0, 2000.0, -3000.0, 10.0, 20.0, 30.0],
        }
    ]
    assert hot["fields"] == [
        {
            "quantity": "temperature",
            "value": 175.0,
            "direction": None,
            "scope": "route",
            "profile": "uniform",
            "group": None,
            "route_id": "R-100",
            "station_start": 1.0,
            "station_end": 4.0,
            "element_ids": [],
        }
    ]
    upset = next(row for row in _rows(tables, "load_cases") if row["load_case"] == "Upset")
    assert upset["definition_type"] == "operation"
    assert upset["metadata"] == {"design_basis": "occasional"}


def test_project_summary_is_model_only_and_units_live_on_columns(review_model):
    tables = build_model_tables(review_model)
    summary = _rows(tables, "project_summary")[0]

    assert summary == {
        "project_name": "HOT-100",
        "model_standard": "ASME_B31.3",
        "model_revision": 4,
        "analysis_status": "not_solved",
        "node_count": 4,
        "element_count": 3,
        "section_count": 5,
        "material_count": 2,
        "support_count": 2,
        "load_case_count": 2,
    }
    line_list = _table(tables, "line_list")
    assert next(column for column in line_list.columns if column.id == "length_m").unit == "m"
    assert isinstance(next(row for row in line_list.rows if row["element_id"] == "E-20")["length_m"], float)


def test_missing_material_does_not_create_a_mass_value(review_model):
    review_model.elements[0].material = "Unspecified"

    pipe = next(
        row
        for row in _rows(build_model_tables(review_model), "section_schedule")
        if row["section"] == "PipeSec"
    )

    assert pipe["total_mass_kg"] is None
