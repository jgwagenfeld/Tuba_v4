"""Report checks use deterministic fixtures; production previews use attested solves."""

from dataclasses import replace
import math
import xml.etree.ElementTree as ET

import pytest

from tests.reporting_fixtures import build_review_model
from tuba import Model
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.model import BendGeometry, OperationField
from tuba.reporting import EngineeringReviewError, build_engineering_review
from tuba.reporting.equilibrium import build_equilibrium_table, _line_quadrature
from tuba.reporting.export import _model_overview, _summary_rows, write_engineering_review
from tuba.reporting.model import ReportTable
from tuba.solver.aster_mesh import generate_analysis_mesh


def _records():
    model = Model("Offset cantilever")
    model.add_material("steel", E=2e11, nu=0.3, rho=1000, alpha=1.2e-5)
    model.add_pipe_section("pipe", OD=0.1, WT=0.01)
    a = model.add_node([1, 2, 3])
    b = model.add_node([3, 2, 3])
    model.add_element(id="span", type="pipe_straight", n1=a, n2=b, section="pipe", material="steel")
    model.add_support(id="anchor", node=a, type="anchor")
    case = model.define_load_case("Point", gravity=False)
    case.add_nodal_force(b, [3, 4, -5, 2, 7, 11])
    study = AnalysisStudy("study", 0, "Code_Aster", "Point", None, {}, "mesh")
    state = ResultState("state", "study", 0, "Code_Aster", "Point", "mesh", {},
                        {a: (-3, -4, 5, -2, -17, -19)}, {})
    return model, study, state, a


def _balance(model, study, state, **kwargs):
    return build_equilibrium_table(model, {study.id: study}, [state], **kwargs)


def test_balance_uses_global_force_signs_and_a_common_moment_origin():
    model, study, state, _ = _records()
    rows = _balance(model, study, state).rows
    assert [row["applied"] for row in rows] == pytest.approx([3, 4, -5, -20, 31, 17])
    assert [row["residual"] for row in rows] == pytest.approx([0] * 6)
    assert all(row["status"] == "within_tolerance" for row in rows)
    assert all(row["load_case"] == "Point" and row["result_state_id"] == "state" for row in rows)
    wrong = replace(state, node_reactions={model.supports[0].node: (3, 4, -5, 2, 17, 19)})
    assert all(row["status"] == "outside_tolerance" for row in _balance(model, study, wrong).rows)


def test_gravity_and_uniform_line_loads_include_their_moment_arms():
    model, study, state, a = _records()
    case = model.load_cases["Point"]
    case.gravity = True
    case.fields.append(OperationField(quantity="line_load", value=10, direction=[0, 1, 0],
                                      scope="elements", element_ids=["span"]))
    # Independent annulus mass and a uniform load at the span midpoint.
    weight = math.pi * (0.1**2 - 0.08**2) / 4 * 1000 * 2 * 9.81
    state = replace(state, node_reactions={a: (-3, -24, 5 + weight, -2, -17 - weight, -39)})
    rows = _balance(model, study, state).rows
    assert rows[2]["applied"] == pytest.approx(-5 - weight)
    assert all(abs(row["residual"]) < 1e-10 for row in rows)


@pytest.mark.parametrize("unavailable", ["missing", "component", "pressure", "wind", "volume", "path", "spring"])
def test_incomplete_load_or_reaction_basis_never_reports_a_balanced_zero(unavailable):
    model, study, state, a = _records()
    if unavailable == "missing":
        state = replace(state, node_reactions={})
    elif unavailable == "component":
        state = replace(state, node_reactions={a: (None, -4, 5, -2, -17, -19)})
    elif unavailable == "pressure":
        model.load_cases["Point"].internal_pressure = 1e6
    elif unavailable == "wind":
        model.load_cases["Point"].fields.append(OperationField(
            quantity="wind", value=100, direction=[0, 1, 0], scope="all"))
    elif unavailable == "volume":
        study = replace(study, metadata={"volume_analysis": True})
    elif unavailable == "path":
        study = replace(study, metadata={"compiler_inputs": {"load_path": ["Point"]}})
    else:
        model.supports[0].type = "spring"
    rows = _balance(model, study, state).rows
    assert len(rows) == 1 and rows[0]["status"] == "not_evaluated"
    assert rows[0]["note"] and "residual" not in rows[0] and "applied" not in rows[0]


def test_bend_loads_use_exported_segments_instead_of_the_endpoint_chord():
    model, study, state, a = _records()
    model.nodes[a].coords[:] = [0, 0, 0]
    element = model.elements[0]
    model.nodes[element.n2].coords[:] = [1, 1, 0]
    element.type = "pipe_bend"
    element.bend_radius, element.bend_angle = 1, 90
    element.bend_geometry = BendGeometry([0, 1, 0], [0, 0, 1], 1, 90, [1, 0, 0], [0, 1, 0])
    mesh = generate_analysis_mesh(model)
    samples = _line_quadrature(model, element, mesh, {})
    length = math.fsum(weight for weight, _ in samples)
    # This exporter puts midsides on each segment's chord, not on the ideal arc.
    # Check the solved polygon's mass and centroid, rather than analytic arc values.
    assert length == pytest.approx(32 * math.sin(math.pi / 64), rel=1e-12)
    centroid = [math.fsum(weight * point[axis] for weight, point in samples) / length for axis in range(3)]
    mean = 1 / (32 * math.tan(math.pi / 64))
    assert centroid == pytest.approx([mean, 1 - mean, 0], abs=1e-12)
    with pytest.raises(ValueError, match="authoritative analysis mesh"):
        _line_quadrature(model, element, None, {})


def test_headline_summary_keeps_the_winning_case_entity_and_element_end():
    review = build_engineering_review(build_review_model())
    table = ReportTable("result_summary", "Results", (), (
        {"result_type": "element_force_magnitude", "maximum_value": 5, "unit": "N",
         "load_case": "Cold", "governing_entity_ref": "element:E-20", "governing_location": "n1"},
        {"result_type": "element_force_magnitude", "maximum_value": 9, "unit": "N",
         "load_case": "Hot", "governing_entity_ref": "element:E-10", "governing_location": "n2"},
    ), "result_state")
    rows = dict(_summary_rows(replace(review, tables=review.tables + (table,))))
    assert "9 N" in rows["element force magnitude"]
    assert "load case Hot" in rows["element force magnitude"]
    assert "element:E-10 / n2" in rows["element force magnitude"]
    assert "Cold" not in rows["element force magnitude"]


def test_model_drawings_keep_native_ids_canonical_bends_and_accessible_titles(tmp_path):
    review = build_engineering_review(build_review_model())
    html = write_engineering_review(review, tmp_path).index_path.read_text(encoding="utf-8")
    assert "Authored, undeformed centerlines" in html
    assert "Elements and supports" in html and "Node numbering" in html
    for block in html.split('<svg xmlns=')[1:]:
        svg = ET.fromstring('<svg xmlns=' + block.split('</svg>', 1)[0] + '</svg>')
        assert svg.attrib["role"] == "img" and svg.attrib["aria-labelledby"]
        if svg.attrib.get("class") != "model-diagram":
            continue
        polylines = {item.attrib["data-element"]: item for item in svg.iter() if "data-element" in item.attrib}
        assert set(polylines) == {"E-10", "E-20", "E-30"}
        assert len(polylines["E-10"].attrib["points"].split()) == 33
    assert 'data-ref="SUP-1"' in html and 'data-ref="N0"' in html
    assert '<b>S1</b><span>SUP-1</span>' in html
    broken = replace(review, tables=tuple(replace(table, rows=tuple(
        {**row, "bend_geometry": None} if row["element_type"] == "pipe_bend" else row
        for row in table.rows)) if table.id == "line_list" else table for table in review.tables))
    with pytest.raises(EngineeringReviewError, match="canonical geometry"):
        _model_overview(broken)


def test_section_plates_use_actual_dimensions_bores_and_rolled_fillets(tmp_path):
    from tuba.reporting.profile_svg import section_svg
    review = build_engineering_review(build_review_model())
    rows = {row['section']: row for row in review.table('section_schedule').rows}
    for index, row in enumerate(rows.values()):
        svg = ET.fromstring(section_svg(row, index))
        assert svg.attrib['class'] == 'profile-diagram'
        assert 'millimetres' in next(svg.iter('{http://www.w3.org/2000/svg}title')).text
    pipe = ET.fromstring(section_svg(rows['PipeSec'], 1))
    assert len([p for p in pipe.iter() if p.attrib.get('class') == 'profile-bore']) == 1
    ibeam = ET.fromstring(section_svg(rows['IBeamSec'], 2))
    outline = next(p.attrib['d'] for p in ibeam.iter() if p.attrib.get('class') == 'profile-object')
    # Rounded corners use the existing section-property outline, beyond 12 sharp vertices.
    assert outline.count(' L ') > 100
    text = ''.join(ibeam.itertext())
    assert 'H 100' in text and 'B 55' in text and 'R 7' in text
    html = write_engineering_review(review, tmp_path).index_path.read_text(encoding='utf-8')
    assert 'Section profiles' in html and 'TUBA' in html
    assert 'class="detail-block"' in html
    assert 'content-visibility: visible' in html
