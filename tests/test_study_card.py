"""Study cards and reference figures: what they claim, and what they refuse to claim.

The cards in this repository describe committed Code_Aster evidence, so the tests read
that evidence rather than a fixture: a card that stopped describing the solved studies
would make every committed card quietly wrong.
"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tuba.reporting import (
    FigureSeries,
    ReferenceFigureError,
    build_study_card,
    compare_series,
    evidence_folders,
    parse_code_aster_keywords,
    parse_export_units,
    render_reference_figure,
    render_study_card_markdown,
    write_study_card,
)
from tuba.reporting.study_card import StudyCardError


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
OPERATING = EXAMPLES / "code-aster-review" / "evidence" / "Operating"
PROFILE = EXAMPLES / "profile-orientation-review" / "evidence" / "global"
DRIVER = ROOT / "scripts" / "build_study_cards.py"


def write_minimal_manifest(folder: Path) -> Path:
    """A manifest with just enough study and mesh for a card to describe."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "study_manifest.json"
    path.write_text(
        json.dumps({
            "study": {
                "id": "analysis_study:Case", "load_case": "Case", "solver_name": "Code_Aster",
                "model_revision": 3, "mesh_id": "analysis_mesh:Case", "metadata": {"project_name": "p"},
            },
            "analysis_mesh": {"nodes": {"N0": [0.0, 0.0, 0.0]}, "elements": {"e0": ["N0", "N1"]}},
        }),
        encoding="utf-8",
    )
    return path


class TestCommKeywordInventory:
    def test_counts_assigned_and_bare_commands(self):
        comm = (
            "DEBUT(PAR_LOT='NON');\n"
            "MAIL0 = LIRE_MAILLAGE(FORMAT='ASTER', UNITE=20);\n"
            "RESU = MECA_STATIQUE(MODELE=MODELE);\n"
            "FIN();\n"
        )

        assert parse_code_aster_keywords(comm) == (
            ("DEBUT", 1), ("FIN", 1), ("LIRE_MAILLAGE", 1), ("MECA_STATIQUE", 1),
        )

    def test_a_bare_debut_and_fin_are_commands(self):
        # DEBUT and FIN are called without being assigned; a parser that only reads
        # assignments reports a study that never opened or closed.
        assert dict(parse_code_aster_keywords("DEBUT();\nFIN();\n")) == {"DEBUT": 1, "FIN": 1}

    def test_field_constructors_are_not_commands(self):
        comm = "MAIL = AFFE_MODELE(AFFE=(_F(GROUP_MA='G',),),);\n"

        assert parse_code_aster_keywords(comm) == (("AFFE_MODELE", 1),)

    def test_repeated_commands_are_counted(self):
        comm = "A = CREA_TABLE(RESULTAT=RESU);\nB = CREA_TABLE(RESULTAT=RESU);\n"

        assert parse_code_aster_keywords(comm) == (("CREA_TABLE", 2),)

    def test_a_hash_inside_a_group_name_is_not_a_comment(self):
        comm = "A = DEFI_GROUP(CREA_GROUP_NO=('G#1',),);\n"

        assert parse_code_aster_keywords(comm) == (("DEFI_GROUP", 1),)

    def test_an_unreadable_command_file_is_refused_not_guessed(self):
        with pytest.raises(ValueError, match="not readable"):
            parse_code_aster_keywords("RESU = MECA_STATIQUE(\n")


class TestExportUnitMap:
    def test_reads_the_unit_map_and_skips_directives(self):
        export = (
            "P actions make_etude\n"
            "A memjeveux 512\n"
            "\n"
            "F comm study.comm D 1\n"
            "F rmed study.rmed R 80\n"
        )

        units = parse_export_units(export)

        assert [(unit.logical, unit.filename, unit.direction, unit.unit) for unit in units] == [
            ("comm", "study.comm", "D", "1"),
            ("rmed", "study.rmed", "R", "80"),
        ]

    def test_a_malformed_line_is_not_reported_as_a_unit(self):
        units = parse_export_units("F comm study.comm D 1\nF rmed\n")

        assert [unit.logical for unit in units] == ["comm"]

    def test_result_units_name_what_they_carry(self):
        meanings = {unit.logical: unit.meaning for unit in parse_export_units(
            "F depl study_depl.csv R 39\nF sieq study_sieq.csv R 41\nF odd thing R 99\n"
        )}

        assert meanings["depl"] == "displacements (DEPL)"
        assert meanings["sieq"] == "stress invariants (SIEQ_ELNO)"
        assert meanings["odd"] == "unmapped unit"


class TestStudyCard:
    def test_describes_the_committed_operating_study(self):
        card = build_study_card(OPERATING)

        assert card.evidence_status == "verified"
        assert card.load_case == "Operating"
        assert card.solver_name == "Code_Aster"
        assert card.solver_version.count(".") == 2
        assert card.execution_method
        assert card.solved_at.endswith("Z")
        assert card.node_count > 0 and card.element_count > 0
        names = [keyword.name for keyword in card.keywords]
        assert {"DEBUT", "FIN", "LIRE_MAILLAGE", "IMPR_RESU"} <= set(names)
        assert "_F" not in names
        assert card.keyword_inventory_is_lower_bound is False

    def test_the_unit_map_covers_every_result_the_evidence_holds(self):
        card = build_study_card(OPERATING)
        written = {unit.filename for unit in card.export_units if unit.direction == "R"}

        assert {"study.rmed", "study_depl.csv", "study_reac.csv", "study_sieq.csv"} <= written

    def test_every_attested_artifact_is_reported_with_its_hash(self):
        card = build_study_card(OPERATING)
        attested = {artifact.name for artifact in card.artifacts}

        assert {"study.comm", "study.export", "study.mail", "study.mess", "study.rmed"} <= attested
        assert all(len(artifact.sha256) == 64 for artifact in card.artifacts)

    def test_a_damaged_evidence_folder_is_reported_as_damaged(self, tmp_path):
        folder = tmp_path / "damaged"
        write_minimal_manifest(folder)
        (folder / "study_execution.json").write_text("{}", encoding="utf-8")

        card = build_study_card(folder)

        assert card.evidence_status == "damaged"
        assert card.solver_version == "not attested"
        assert card.artifacts == ()

    def test_a_folder_without_an_attestation_reports_no_verdict(self, tmp_path):
        folder = tmp_path / "exported_only"
        write_minimal_manifest(folder)

        card = build_study_card(folder)

        assert card.evidence_status == "missing"
        assert card.keywords == ()
        assert card.export_units == ()

    def test_a_folder_without_a_manifest_has_nothing_to_describe(self, tmp_path):
        with pytest.raises(StudyCardError, match="study_manifest"):
            build_study_card(tmp_path)

    def test_a_manifest_without_a_study_has_nothing_to_describe(self, tmp_path):
        (tmp_path / "study_manifest.json").write_text("{}", encoding="utf-8")

        with pytest.raises(StudyCardError, match="records no study"):
            build_study_card(tmp_path)

    def test_the_card_keeps_writes_outside_the_evidence_folder(self, tmp_path):
        folder = tmp_path / "evidence" / "Operating"
        manifest = write_minimal_manifest(folder)

        json_path, md_path = write_study_card(folder, tmp_path / "reference" / "Operating")

        # Evidence promotion removes every file the solve did not attest, so a card kept
        # inside the evidence folder would be deleted by the next solve.
        assert [path.name for path in folder.iterdir()] == [manifest.name]
        assert json_path == tmp_path / "reference" / "Operating" / "study_card.json"
        assert md_path == tmp_path / "reference" / "Operating" / "study_card.md"

    def test_two_writes_of_the_same_evidence_are_byte_identical(self, tmp_path):
        first_json, first_md = write_study_card(OPERATING, tmp_path / "one")
        second_json, second_md = write_study_card(OPERATING, tmp_path / "two")

        assert first_json.read_bytes() == second_json.read_bytes()
        assert first_md.read_bytes() == second_md.read_bytes()

    def test_a_committed_card_never_carries_an_absolute_path(self, tmp_path):
        # A card naming one author's checkout leaks a machine path and fails the
        # freshness check in every other checkout.
        json_path, md_path = write_study_card(
            OPERATING, tmp_path, project_root=OPERATING.parents[1]
        )

        assert build_study_card(OPERATING, project_root=OPERATING.parents[1]).source == "evidence/Operating"
        for text in (json_path.read_text(encoding="utf-8"), md_path.read_text(encoding="utf-8")):
            assert str(ROOT) not in text
            assert "evidence/Operating" in text

    def test_a_card_names_the_operation_when_it_has_no_project_root(self):
        assert build_study_card(OPERATING).source == "Operating"

    def test_the_json_card_round_trips(self, tmp_path):
        json_path, _ = write_study_card(OPERATING, tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))

        assert payload["schema_version"] == "tuba.study_card.v1"
        assert payload["study"]["load_case"] == "Operating"
        assert {"comm_keywords", "export_units", "attested_artifacts"} <= set(payload)

    def test_the_markdown_states_it_is_not_a_code_check(self):
        text = render_study_card_markdown(build_study_card(OPERATING))

        assert "No number here is a code check" in text
        assert "## Code_Aster commands in the generated .comm" in text
        assert "## Unit map in the generated .export" in text

    def test_a_pipe_breaker_in_a_project_name_cannot_break_the_table(self):
        broken = replace(build_study_card(OPERATING), project_name="rack | one")

        assert "rack \\| one" in render_study_card_markdown(broken)

    def test_every_committed_example_with_evidence_gets_a_folder(self):
        projects = {root for root in EXAMPLES.iterdir() if evidence_folders(root)}

        assert {PROFILE.parents[1], OPERATING.parents[1]} <= projects


class TestReferenceFigure:
    def test_renders_a_standalone_deterministic_document(self):
        series = [
            FigureSeries("Solved", ((0.0, 0.0), (1.0, 2.0), (2.0, 5.0))),
            FigureSeries("Reference", ((0.0, 0.0), (1.0, 2.1), (2.0, 4.9)), "reference"),
        ]
        labels = {"title": "Profile", "xlabel": "Station (m)", "ylabel": "Displacement (m)"}

        first = render_reference_figure(series, **labels)
        second = render_reference_figure(series, **labels)

        assert first == second
        assert first.startswith("<svg ") and first.rstrip().endswith("</svg>")
        assert 'stroke="#1d4ed8"' in first
        assert "stroke-dasharray" in first

    def test_draws_the_reference_under_the_solved_curve(self):
        # Where they agree the solid line must stay visible; a reversed draw order would
        # hide the solved curve under the reference it is supposed to be checked against.
        series = [
            FigureSeries("Solved", ((0.0, 0.0), (1.0, 1.0))),
            FigureSeries("Reference", ((0.0, 0.0), (1.0, 1.0)), "reference"),
        ]
        text = render_reference_figure(series, title="t", xlabel="x", ylabel="y")

        assert text.index('stroke="#b45309"') < text.index('stroke="#1d4ed8"')

    def test_escapes_a_title_that_would_otherwise_close_the_element(self):
        text = render_reference_figure(
            [FigureSeries("Solved", ((0.0, 0.0), (1.0, 1.0)))], title="a <b> & c", xlabel="x", ylabel="y"
        )

        assert "a &lt;b&gt; &amp; c" in text

    def test_a_non_finite_point_is_refused(self):
        with pytest.raises(ReferenceFigureError, match="non-finite"):
            FigureSeries("Solved", ((0.0, 0.0), (1.0, float("nan"))))

    def test_an_empty_series_is_refused(self):
        with pytest.raises(ReferenceFigureError, match="no points"):
            FigureSeries("Solved", ())

    def test_a_figure_needs_a_series(self):
        with pytest.raises(ReferenceFigureError, match="at least one series"):
            render_reference_figure([], title="t", xlabel="x", ylabel="y")

    def test_comparing_series_sampled_elsewhere_is_refused(self):
        solved = FigureSeries("Solved", ((0.0, 0.0), (1.0, 1.0)))
        elsewhere = FigureSeries("Reference", ((0.0, 0.0), (2.0, 1.0)), "reference")

        with pytest.raises(ReferenceFigureError, match="different x positions"):
            compare_series(solved, elsewhere)

    def test_comparing_series_reports_the_worst_difference(self):
        solved = FigureSeries("Solved", ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)))
        reference = FigureSeries("Reference", ((0.0, 0.0), (1.0, 1.01), (2.0, 2.0)), "reference")

        report = compare_series(solved, reference, rtol=0.02)

        assert report["points"] == 3
        assert report["worst_absolute"] == pytest.approx(0.01)
        # 1% of the reference value, not of the solved one: the reference is the answer
        # the solved value is being measured against.
        assert report["worst_relative"] == pytest.approx(0.01 / 1.01)
        assert report["within_tolerance"] is True

    def test_comparing_series_reports_a_disagreement(self):
        solved = FigureSeries("Solved", ((0.0, 0.0), (1.0, 2.0)))
        reference = FigureSeries("Reference", ((0.0, 0.0), (1.0, 1.0)), "reference")

        assert compare_series(solved, reference, rtol=0.02)["within_tolerance"] is False

    def test_a_nonzero_value_disagrees_with_a_zero_reference(self):
        solved = FigureSeries("Solved", ((0.0, 1.0),))
        reference = FigureSeries("Reference", ((0.0, 0.0),), "reference")
        report = compare_series(solved, reference)
        assert report["within_tolerance"] is False
        assert report["worst_relative"] == float("inf")
        assert compare_series(reference, reference)["within_tolerance"] is True

    @pytest.mark.parametrize("rtol", [-0.1, float("nan"), float("inf")])
    def test_comparison_refuses_invalid_tolerance(self, rtol):
        series = FigureSeries("Solved", ((0.0, 0.0),))
        with pytest.raises(ReferenceFigureError, match="tolerance"):
            compare_series(series, series, rtol=rtol)

    def test_the_canvas_contains_every_legend_row_and_the_note(self):
        import xml.etree.ElementTree as ET

        series = [FigureSeries(str(index), ((0.0, 0.0), (1.0, 1.0))) for index in range(5)]
        svg = ET.fromstring(render_reference_figure(series, title="t", xlabel="x", ylabel="y", note="a <note> & b"))
        texts = list(svg.iter("{http://www.w3.org/2000/svg}text"))
        assert any(text.text == "a <note> & b" for text in texts)
        assert all(float(text.attrib["y"]) + 12 < float(svg.attrib["height"]) for text in texts)


class TestCommittedReferenceArtifacts:

    def test_driver_accepts_its_documented_example_path_and_rejects_missing_projects(self):
        from scripts.build_study_cards import project_roots

        assert project_roots(EXAMPLES, ["examples/profile-orientation-review"]) == (PROFILE.parents[1],)
        assert project_roots(EXAMPLES, ["profile-orientation-review"]) == (PROFILE.parents[1],)
        with pytest.raises(StudyCardError, match="model.py"):
            project_roots(EXAMPLES, ["does-not-exist"])
    def test_the_profile_example_commits_a_card_and_both_figures(self):
        reference = PROFILE.parents[1] / "reference" / "global"

        for name in (
            "study_card.md", "study_card.json",
            "reference_displacement_profile.svg", "reference_tip_response.svg",
        ):
            assert (reference / name).is_file(), f"{name} is missing; run scripts/build_study_cards.py"

    def test_the_committed_figures_show_solved_values_against_beam_theory(self):
        for name in ("reference_displacement_profile.svg", "reference_tip_response.svg"):
            text = (PROFILE.parents[1] / "reference" / "global" / name).read_text(encoding="utf-8")
            assert "Code_Aster DEPL" in text
            assert "Cantilever beam theory" in text

    def test_the_committed_cards_are_current(self):
        result = subprocess.run(
            [sys.executable, str(DRIVER), "--check"], cwd=ROOT, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_no_committed_card_carries_a_machine_path(self):
        for card in EXAMPLES.rglob("reference/*/study_card.md"):
            text = card.read_text(encoding="utf-8")
            assert str(ROOT) not in text, f"{card} carries an absolute local path"
