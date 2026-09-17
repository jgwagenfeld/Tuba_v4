"""inspect_model reports the model in the authoring vocabulary: routes, stations,
support ids and attachment points."""

from __future__ import annotations

from tuba.mcp.server import build_pipe_run, init_session, inspect_model, run_model_code


def test_inspection_reports_routes_and_station_ranges(tmp_path):
    init_session(project_name="Inspect", file_path=str(tmp_path / "model.py"), load_existing=False)
    build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        route_id="P-100",
        steps=[
            {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 4.0},
            {"op": "end", "point": [4.0, 2.0, 0.0], "support": "anchor"},
        ],
    )

    info = inspect_model()

    assert set(info["routes"]) == {"P-100"}
    route = info["routes"]["P-100"]
    assert route["section"] == "DN100_SCH40"
    assert route["material"] == "P265GH"
    assert route["station_start"] == 0.0
    assert route["station_end"] == 6.0
    assert len(route["elements"]) == 2
    spans = [(e["station_start"], e["station_end"]) for e in info["elements"] if e.get("route_id") == "P-100"]
    assert spans == [(0.0, 4.0), (4.0, 6.0)]


def test_inspection_reports_support_ids_and_attachment_points(tmp_path):
    init_session(project_name="Inspect", file_path=str(tmp_path / "model.py"), load_existing=False)
    run_model_code(
        'assemble(model, "tuba.assemblies:rack_bay", name="rack_A", origin=(0.0, -1.0, 0.0), '
        'length=4.0, width=2.0, height=3.0, levels=(3.0,), section="DN100_SCH40", '
        'material="P265GH", shoe_level=3.0)\n'
        'mid = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_mid_left"].split(":", 1)[1]\n'
        'node = model.add_node((-2.0, 0.0, 3.25))\n'
        'model.add_support(node, "rest", attached_to=mid, friction_coefficient=0.3)\n'
    )

    info = inspect_model()

    points = info["groups"]["rack_A"]["attachment_points"]
    assert points["level_1_mid_left"] in info["nodes"]
    assert ":" not in points["level_1_mid_left"]
    rest = next(support for support in info["supports"] if support["type"] == "rest")
    assert rest["attached_to"] == points["level_1_mid_left"]
    assert rest["friction_coefficient"] == 0.3
    assert all("id" in support for support in info["supports"])
