"""The one-page summary tier.

SCIA, CSI and MIDAS all print three levels, and the middle one is defined by a
size: it "fits no more than a half of an A4 page and shows all important results
of the check". These tests hold the sheet to that - it leads, it states the
evidence, it names the governing location, and it claims no code check.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.reporting_fixtures import build_review_model
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.reporting.builder import build_engineering_review
from tuba.reporting.export import write_engineering_review


@pytest.fixture
def solved_review():
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
        metadata={"result_trust": "verified", "solve_attestation": {"fixture": "validated"}},
    )
    return build_engineering_review(
        model,
        studies=[study],
        result_states=[result],
        package_id="review:solved",
        created_at="2026-07-15T00:00:00Z",
    )


def _sheet_rows(html: str) -> dict[str, str]:
    """The sheet's definition list, as a plain mapping."""
    rows: dict[str, str] = {}
    block = html.split('<dl class="summary-facts">', 1)[-1].split("</dl>", 1)[0]
    for chunk in block.split("<dt>")[1:]:
        term, _, rest = chunk.partition("</dt>")
        rows[term] = rest.split("<dd>", 1)[-1].split("</dd>", 1)[0]
    return rows


def _render(review, tmp_path) -> str:
    return write_engineering_review(review, tmp_path, title="Review").index_path.read_text(encoding="utf-8")


def test_the_sheet_leads_the_document_and_is_bounded_to_one_printed_page(tmp_path, solved_review):
    html = _render(solved_review, tmp_path)
    sheet = html.index("<h2>Summary sheet</h2>")
    first_detail = min(html.index(f"<h2>{name}</h2>") for name in ("Summary", "Model", "Results"))
    assert sheet < first_detail, "the one-page tier is reached before the detail"
    # Defined by its size, so the size is enforced rather than hoped for.
    assert "break-after: page" in html
    assert 'class="summary-sheet"' in html


def test_the_sheet_answers_what_this_is_was_it_solved_and_where_is_the_worst_number(tmp_path, solved_review):
    rows = _sheet_rows(_render(solved_review, tmp_path))

    assert rows["Project"] == solved_review.project_name
    assert rows["Analysis status"] == solved_review.analysis_status
    assert rows["Model revision"] == str(solved_review.model_revision)
    assert "Published" in rows
    # A result row carries the quantity, its governing value and where it was.
    assert any(" at " in value for value in rows.values()), "a result must name its location"


def test_the_sheet_states_the_evidence_bar_the_builder_applies(tmp_path, solved_review):
    rows = _sheet_rows(_render(solved_review, tmp_path))

    # The single fact that decides whether the rest of the page is worth reading.
    # Counted over result states, because that is where the bar is: a study record
    # is an input reference, not evidence of a solve.
    assert rows["Evidence"] == "1 of 1 result record verified"


def test_an_unverified_solve_says_so_on_the_sheet(tmp_path, solved_review):
    """A review that reports eleven significant figures from an unverified solve is
    the failure this sheet exists to make impossible to miss."""
    unverified = replace(
        solved_review,
        provenance=tuple(
            replace(record, metadata={"result_trust": "unverified", "solve_attestation": {}})
            if record.kind == "result_state" else record
            for record in solved_review.provenance
        ),
    )
    rows = _sheet_rows(_render(unverified, tmp_path))

    assert rows["Evidence"].startswith("0 of 1 result record verified")
    # Stated as a shortfall, never rounded into confidence.
    assert "see Diagnostics" in rows["Evidence"]


def test_every_stress_number_on_the_sheet_carries_its_basis(tmp_path, solved_review):
    """A sheet that printed "64.2" beside "Von Mises" would be the one page of this
    document a reader could mistake for a code check."""
    rows = _sheet_rows(_render(solved_review, tmp_path))

    stress = [value for key, value in rows.items() if "von mises" in key.lower()]
    assert stress, "the result summary's stress row must reach the sheet"
    for value in stress:
        assert "not piping-code stress" in value
        assert " at " in value


def test_the_sheet_never_claims_a_code_check_or_a_verdict(tmp_path, solved_review):
    html = _render(solved_review, tmp_path)
    sheet = html.split('<section class="summary-sheet"', 1)[-1].split("</section>", 1)[0]

    # The disclaimer names the words in order to disclaim them, so the check is
    # against the values the sheet asserts - a row saying "utilization 0.94" would
    # be the claim, and the sentence above it is what denies it.
    assert "performs no standards evaluation" in sheet
    for forbidden in ("utilization", "utilisation", "compliance", "approved", "pass/fail"):
        for value in _sheet_rows(sheet).values():
            assert forbidden not in value.lower(), f"a sheet value claims {forbidden}"
        for heading in _sheet_rows(sheet):
            assert forbidden not in heading.lower(), f"a sheet row is named {forbidden}"


def test_a_missing_result_reads_as_unavailable_and_not_as_zero(tmp_path, solved_review):
    """ADR 0002: missing is unavailable, never zero. A sheet that printed 0 for an
    absent value would be the one place in the document where that rule broke."""
    tables = tuple(
        replace(table, rows=tuple(
            {**row, "maximum_value": None} if row.get("result_type") == "fe_von_mises" else row
            for row in table.rows
        ))
        if table.id == "result_summary" else table
        for table in solved_review.tables
    )
    rows = _sheet_rows(_render(replace(solved_review, tables=tables), tmp_path))

    stress = [value for key, value in rows.items() if "von mises" in key.lower()]
    assert stress and all(value.startswith("unavailable") for value in stress)
    # The nulled row must not read as a zero of its unit. A real zero elsewhere on
    # the sheet is fine - the fixture's N0 genuinely has no displacement - so this
    # is scoped to the row that was actually nulled.
    assert not any("0 Pa" in value for value in stress)


def test_a_sheet_with_no_studies_and_no_provenance_still_renders(tmp_path):
    model_only = build_engineering_review(
        build_review_model(), package_id="review:model", created_at="2026-07-15T00:00:00Z"
    )
    rows = _sheet_rows(_render(model_only, tmp_path))

    assert rows["Analysis status"] == "not_solved"
    assert "Solver" not in rows, "no studies means no solver to name"
    assert "Evidence" not in rows, "no provenance means nothing to attest to"
    assert rows["Diagnostics"] == "none recorded"


def test_diagnostic_counts_reach_the_sheet(tmp_path, solved_review):
    from tuba.reporting.model import ReviewDiagnostic
    with_diagnostics = replace(
        solved_review,
        diagnostics=(
            ReviewDiagnostic(severity="warning", message="one", code="a", source="test"),
            ReviewDiagnostic(severity="warning", message="two", code="b", source="test"),
        ),
    )
    rows = _sheet_rows(_render(with_diagnostics, tmp_path))
    assert "warning" in rows["Diagnostics"]
