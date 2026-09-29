"""The published contact story, against synthetic histories and real evidence.

These assertions are the reason the example reads as a cycle rather than a
number. A friction review is a sequence, so the tests below care about which
stage a shoe moved in, whether a run of stages is one finding or several, and
whether a transition is detected across a stage boundary - the three things the
viewer now navigates by.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tuba.analysis.contact_findings import (
    FINDING_KINDS,
    FORCE_TOLERANCE_N,
    OVER_LIMIT_UTILIZATION,
    build_contact_findings,
    contact_samples,
)
from tuba.analysis.results import ResultState
from tuba.solver.base import ContactResult

REPO_ROOT = Path(__file__).resolve().parents[1]
#: A load path's study and evidence are filed under its final stage, which is Reseat.
EVIDENCE = REPO_ROOT / "examples" / "native-friction-review" / "evidence" / "Reseat"

PATH = ("Cold", "Hot", "Cold", "Lift", "Cold")


def shoe(
    support_id: str,
    *,
    status: str = "sticking",
    normal_force: float = 10_000.0,
    tangential: tuple[float, float, float] = (0.0, 0.0, 0.0),
    mu: float = 0.3,
    gap: float = 0.0,
    slip: tuple[float, float, float] = (0.0, 0.0, 0.0),
    status_source: str = "solver",
) -> ContactResult:
    limit = mu * max(0.0, normal_force)
    magnitude = sum(value**2 for value in tangential) ** 0.5
    return ContactResult(
        support_id=support_id,
        node_id=f"n_{support_id}",
        status=status,
        normal=(0.0, 0.0, 1.0),
        normal_force=normal_force,
        tangential_force=tangential,
        gap=gap,
        relative_displacement=tangential,
        slip=slip,
        friction_limit=limit,
        utilization=magnitude / limit if limit > 1e-9 and status != "open" else None,
        status_source=status_source,
    )


def state(stage: int, label: str, pseudo_time: float, contacts: dict[str, ContactResult], **extra) -> ResultState:
    return ResultState(
        id=f"result_state:step:{pseudo_time:g}",
        study_id="study:test",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Cycle",
        mesh_id="mesh:test",
        node_displacements={},
        node_reactions={},
        element_results={},
        metadata={
            "run_id": "run:test",
            "pseudo_time": pseudo_time,
            "stage_index": stage,
            "stage_label": label,
            **extra,
        },
        contact_results=contacts,
    )


def reference(contacts: dict[str, ContactResult]) -> ResultState:
    return state(0, "Reference", 0.0, contacts)


def staged(path=PATH, **per_stage) -> list[ResultState]:
    """One reference state plus one state per authored stage."""
    states = [reference({"shoe": shoe("shoe", normal_force=0.0)})]
    for index, label in enumerate(path, start=1):
        states.append(state(index, label, float(index), {"shoe": per_stage.get(label, shoe("shoe"))}))
    return states


def findings_of(states) -> list[dict]:
    block = build_contact_findings(states)
    return [] if block is None else block["runs"][0]["findings"]


def by_kind(states, kind: str) -> list[dict]:
    return [finding for finding in findings_of(states) if finding["kind"] == kind]


class ContactFindingsDerivation(unittest.TestCase):
    def test_no_contact_history_yields_no_block(self) -> None:
        bare = state(0, "Cold", 0.0, {})
        self.assertIsNone(build_contact_findings([bare]))
        self.assertIsNone(build_contact_findings([]))

    def test_a_sticking_shoe_reports_nothing(self) -> None:
        block = build_contact_findings(staged())
        self.assertEqual(block["runs"][0]["findings"], [])
        self.assertFalse(block["runs"][0]["shoes"][0]["ever_slid"])
        self.assertEqual(block["runs"][0]["stage_count"], len(PATH) + 1)

    def test_sliding_is_one_finding_spanning_the_stages_it_covered(self) -> None:
        # The real failure mode this guards: a shoe on the cone for three
        # consecutive stages is one behaviour, and reporting it three times
        # makes the story longer than the run.
        states = [
            reference({"shoe": shoe("shoe")}),
            state(1, "Cold", 1.0, {"shoe": shoe("shoe")}),
            state(2, "Hot", 2.0, {"shoe": shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))}),
            state(3, "Cold", 3.0, {"shoe": shoe("shoe", status="sliding", tangential=(3_000.0, 0.0, 0.0))}),
            state(4, "Lift", 4.0, {"shoe": shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))}),
            state(5, "Cold", 5.0, {"shoe": shoe("shoe")}),
        ]
        slips = by_kind(states, "slip")
        self.assertEqual(len(slips), 1)
        self.assertEqual(slips[0]["stage_indices"], [2, 3, 4])
        self.assertEqual((slips[0]["stage_label"], slips[0]["final_stage_label"]), ("Hot", "Lift"))
        self.assertTrue(slips[0]["spans_stages"])
        self.assertEqual(slips[0]["severity"], "attention")

    def test_a_break_in_the_sequence_starts_a_second_slip_finding(self) -> None:
        states = [
            reference({"shoe": shoe("shoe")}),
            state(1, "Cold", 1.0, {"shoe": shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))}),
            state(2, "Hot", 2.0, {"shoe": shoe("shoe")}),
            state(3, "Cold", 3.0, {"shoe": shoe("shoe", status="sliding", tangential=(3_000.0, 0.0, 0.0))}),
        ]
        slips = by_kind(states, "slip")
        self.assertEqual([finding["stage_indices"] for finding in slips], [[1], [3]])

    def test_force_reversal_is_detected_across_a_stage_boundary(self) -> None:
        # A per-stage walk compares the first increment of a stage against
        # nothing and misses the reversal that a load change causes. The only
        # reversal here is between the last increment of "Hot" and the first of
        # "Cold", so finding it at all proves the boundary is crossed.
        states = [
            reference({"shoe": shoe("shoe")}),
            state(1, "Hot", 1.0, {"shoe": shoe("shoe", tangential=(-2_000.0, 0.0, 0.0))}),
            state(2, "Cold", 2.0, {"shoe": shoe("shoe", tangential=(1_500.0, 0.0, 0.0))}),
        ]
        reversals = by_kind(states, "force_reversal")
        self.assertEqual(len(reversals), 1)
        self.assertEqual(reversals[0]["stage_indices"], [2])
        self.assertAlmostEqual(reversals[0]["values"]["previous_tangential_force_n"], 2_000.0)
        self.assertAlmostEqual(reversals[0]["values"]["tangential_force_n"], 1_500.0)
        self.assertEqual(reversals[0]["severity"], "info")

    def test_lift_off_and_reseat_are_reported_for_a_frictionless_shoe_too(self) -> None:
        # A mu = 0 shoe has no cone, but the pipe still leaving it is the more
        # consequential outcome, so the separation is not suppressed.
        def series():
            return [
                reference({"shoe": shoe("shoe", mu=0.0, normal_force=0.0, status="indeterminate", status_source="derived")}),
                state(1, "Cold", 1.0, {"shoe": shoe("shoe", mu=0.0, normal_force=10_000.0, status="indeterminate", status_source="derived")}),
                state(2, "Lift", 2.0, {"shoe": shoe("shoe", mu=0.0, normal_force=0.0, status="open", gap=3.0e-3)}),
                state(3, "Cold", 3.0, {"shoe": shoe("shoe", mu=0.0, normal_force=10_000.0, status="indeterminate", status_source="derived")}),
            ]

        states = series()
        self.assertEqual([finding["stage_indices"] for finding in by_kind(states, "lift_off")], [[2]])
        self.assertEqual([finding["stage_indices"] for finding in by_kind(states, "reseat")], [[3]])
        # No cone, so no slip or cone finding is invented for it.
        self.assertEqual(by_kind(states, "slip"), [])
        self.assertEqual(by_kind(states, "over_limit"), [])
        self.assertTrue(build_contact_findings(states)["runs"][0]["shoes"][0]["frictionless"])

    def test_a_frictionless_shoe_carries_an_explanation_not_a_finding(self) -> None:
        states = [
            reference({"shoe": shoe("shoe", mu=0.0, normal_force=0.0, status="indeterminate", status_source="derived")}),
            state(1, "Cold", 1.0, {"shoe": shoe("shoe", mu=0.0, status="indeterminate", status_source="derived")}),
        ]
        self.assertEqual(by_kind(states, "frictionless"), [])
        note = build_contact_findings(states)["runs"][0]["shoes"][0]["note"]
        self.assertIn("no Coulomb cone", note)

    def test_an_unloaded_shoe_is_reported_per_run_of_stages(self) -> None:
        states = [
            reference({"shoe": shoe("shoe", normal_force=0.0)}),
            state(1, "Cold", 1.0, {"shoe": shoe("shoe", normal_force=0.0)}),
            state(2, "Hot", 2.0, {"shoe": shoe("shoe")}),
            state(3, "Cold", 3.0, {"shoe": shoe("shoe", normal_force=0.0)}),
        ]
        unloaded = by_kind(states, "unloaded")
        self.assertEqual([finding["stage_indices"] for finding in unloaded], [[1], [3]])

    def test_a_shoe_on_the_cone_is_not_reported_as_exceeding_it(self) -> None:
        # |Ft| = mu*N exactly on the sliding branch, so "over limit" would fire
        # on every correct slide. Only a real overshoot is reported.
        on_cone = shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))
        self.assertAlmostEqual(on_cone.utilization, 1.0, places=12)
        self.assertEqual(by_kind([reference({"shoe": on_cone})], "over_limit"), [])

    def test_a_genuine_overshoot_is_reported_as_a_convergence_artifact(self) -> None:
        overshoot = shoe("shoe", status="sliding", tangential=(-3_100.0, 0.0, 0.0))
        self.assertGreater(overshoot.utilization, OVER_LIMIT_UTILIZATION)
        found = by_kind([reference({"shoe": overshoot})], "over_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("convergence artifact", found[0]["note"])

    def test_a_small_overshoot_is_still_caught(self) -> None:
        # The native reader raises unless |Ft| <= mu*N + 1e-3*max(|N|, mu*N), so
        # a real overshoot can be as small as one part in a thousand. A threshold
        # at 1.001 could never fire, which is what made the first version of this
        # finding dead code.
        limit = 0.3 * 10_000.0
        small = shoe("shoe", status="sliding", tangential=(-(limit * 1.0005), 0.0, 0.0))
        self.assertGreater(small.utilization, OVER_LIMIT_UTILIZATION)
        self.assertLess(small.utilization, 1.001, "the overshoot has to be one the reader would accept")
        self.assertEqual(len(by_kind([reference({"shoe": small})], "over_limit")), 1)

    def test_a_shoe_that_recovers_and_overshoots_again_reports_both(self) -> None:
        def sliding(force: float) -> dict[str, ContactResult]:
            return {"shoe": shoe("shoe", status="sliding", tangential=(-force, 0.0, 0.0))}

        limit = 0.3 * 10_000.0
        states = [
            reference({"shoe": shoe("shoe")}),
            state(1, "Hot", 1.0, sliding(limit * 1.0005)),
            state(2, "Cold", 2.0, sliding(limit)),
            state(3, "Lift", 3.0, sliding(limit * 1.0005)),
        ]
        found = by_kind(states, "over_limit")
        self.assertEqual([finding["stage_indices"] for finding in found], [[1], [3]])

    def test_a_shoe_is_not_frictionless_because_its_reference_is_unloaded(self) -> None:
        # friction_limit is mu*max(0, N), so an unloaded reference has a zero
        # limit whatever the coefficient is. Asking only about the first sample
        # called every shoe frictionless and silently dropped its slip.
        states = [
            reference({"shoe": shoe("shoe", normal_force=0.0, status="open", gap=1.0e-3, mu=0.0)}),
            state(1, "Cold", 1.0, {"shoe": shoe("shoe", normal_force=10_000.0)}),
            state(2, "Hot", 2.0, {"shoe": shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))}),
        ]
        record = build_contact_findings(states)["runs"][0]["shoes"][0]
        self.assertFalse(record["frictionless"])
        self.assertEqual([finding["kind"] for finding in by_kind(states, "slip")], ["slip"])

    def test_a_stage_reports_what_happened_in_it_not_only_where_it_ended(self) -> None:
        # Nine sliding increments and a final re-stick: the stage must read as a
        # slide, or a reader scanning the row sees a shoe that never moved.
        members = [("sliding", 3_000.0)] * 3 + [("sticking", 0.0)]
        history = [
            reference({"shoe": shoe("shoe")}),
            state(1, "Hot", 1.0, {"shoe": shoe("shoe", status="sticking")}),
        ]
        for offset, (status, force) in enumerate(members):
            history.append(
                state(2, "Cold", 2.0 + offset / 10, {"shoe": shoe(
                    "shoe", status=status, tangential=(-force, 0.0, 0.0))})
            )
        summary = next(
            entry
            for entry in build_contact_findings(history)["runs"][0]["shoes"][0]["stages"]
            if entry["index"] == 2
        )
        self.assertEqual(summary["status"], "sticking", "the increment the stage ended on")
        self.assertEqual(summary["governing_status"], "sliding", "what happened in the stage")
        self.assertTrue(summary["transitioned"])

    def test_the_schema_publishes_its_vocabulary_and_threshold(self) -> None:
        # A reader that keeps its own copy of the kinds or the cone threshold
        # drifts from the module that applies them.
        block = build_contact_findings(staged())
        self.assertEqual(block["finding_kinds"], list(FINDING_KINDS))
        self.assertEqual(block["over_limit_utilization"], OVER_LIMIT_UTILIZATION)
        self.assertEqual(block["severities"], ["info", "attention"])

    def test_severities_stay_inside_the_two_words_the_pages_gate_allows(self) -> None:
        states = [
            reference({"shoe": shoe("shoe", status="sliding", tangential=(-3_000.0, 0.0, 0.0))}),
            state(1, "Lift", 1.0, {"shoe": shoe("shoe", normal_force=0.0, status="open", gap=4.0e-3)}),
        ]
        for finding in findings_of(states):
            self.assertIn(finding["severity"], {"info", "attention"})

    def test_every_finding_is_identifiable_and_anchored_at_a_real_state(self) -> None:
        block = build_contact_findings(staged())
        identifiers = [finding["id"] for finding in block["runs"][0]["findings"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        state_ids = {sample.state_id for sample in contact_samples(staged())["shoe"]}
        for finding in block["runs"][0]["findings"]:
            self.assertIn(finding["result_state_id"], state_ids)
            self.assertTrue(finding["note"])

    def test_two_runs_in_one_bundle_stay_separable(self) -> None:
        first = staged()
        second = [
            ResultState(
                id=state.id.replace("step:", "other:"),
                study_id=state.study_id,
                model_revision=state.model_revision,
                solver_name=state.solver_name,
                load_case=state.load_case,
                mesh_id=state.mesh_id,
                node_displacements={},
                node_reactions={},
                element_results={},
                metadata={**state.metadata, "run_id": "run:other"},
                contact_results=state.contact_results,
            )
            for state in first
        ]
        block = build_contact_findings([*first, *second])
        # Runs are ordered by id, not by arrival, so a bundle that stages two
        # runs describes them the same way every time it is rebuilt.
        self.assertEqual([run["run_id"] for run in block["runs"]], ["run:other", "run:test"])
        self.assertEqual(block["primary_run_id"], "run:other")
        for run in block["runs"]:
            self.assertEqual(run["stage_count"], len(PATH) + 1)


class NativeFrictionEvidence(unittest.TestCase):
    """The story the committed Code_Aster evidence actually tells."""

    @classmethod
    def setUpClass(cls) -> None:
        from tuba.project import load_project

        project = load_project(REPO_ROOT / "examples" / "native-friction-review")
        namespace = project.run_model()
        from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts

        cls.model = namespace["model"]
        cls.analysis_run = import_code_aster_artifacts(model=cls.model, work_dir=EVIDENCE)
        cls.block = build_contact_findings(cls.analysis_run.result_states)

    def test_the_cycle_is_six_stages_of_ten_increments(self) -> None:
        run = self.block["runs"][0]
        self.assertEqual(
            [(stage["index"], stage["label"]) for stage in run["stages"]],
            [(0, "Reference"), (1, "Cold"), (2, "Hot"), (3, "Cold"), (4, "Lift"), (5, "Reseat")],
        )
        self.assertEqual(sum(stage["increment_count"] for stage in run["stages"]), 51)

    def test_the_published_story_is_the_one_the_example_asserts(self) -> None:
        run = self.block["runs"][0]
        shoes = {record["support_id"]: record for record in run["shoes"]}
        self.assertEqual(set(shoes), {"F_S1", "F_S2", "NF_S1", "NF_S2"})

        # F_S1 reached its cone and slid, from Hot through Lift.
        self.assertTrue(shoes["F_S1"]["ever_slid"])
        slip = next(finding for finding in run["findings"] if finding["kind"] == "slip")
        self.assertEqual(slip["support_ids"], ["F_S1"])
        self.assertEqual(slip["stage_indices"], [2, 3, 4])

        # It then lost and regained the cone as the path cooled and heated again.
        self.assertAlmostEqual(shoes["F_S1"]["peak_utilization"], 1.0, places=6)
        self.assertEqual(shoes["F_S1"]["final_status"], "sticking")

        # F_S2 never slid, but lifted clear at Lift and reseated afterwards.
        self.assertFalse(shoes["F_S2"]["ever_slid"])
        self.assertTrue(shoes["F_S2"]["ever_open"])
        self.assertAlmostEqual(shoes["F_S2"]["max_gap_m"], 3.7525e-3, places=6)
        lifted = {tuple(finding["support_ids"]) for finding in run["findings"] if finding["kind"] == "lift_off"}
        self.assertEqual(lifted, {("F_S2",), ("NF_S2",)})
        reseated = {tuple(finding["support_ids"]) for finding in run["findings"] if finding["kind"] == "reseat"}
        self.assertEqual(reseated, {("F_S2",), ("NF_S2",)})

        # The frictionless copy is explained rather than reported as a failure.
        self.assertTrue(shoes["NF_S1"]["frictionless"])
        self.assertIsNone(shoes["NF_S1"]["peak_utilization"])
        self.assertEqual(shoes["NF_S1"]["peak_tangential_force_n"], 0.0)

    def test_the_first_stage_is_genuinely_inert_which_is_why_the_example_read_as_empty(self) -> None:
        # Gravity acts along the shoe normal and nothing drives the pipe
        # tangentially at the cold stage, so no shoe has friction work to do
        # until the temperature rises. This is the whole reason the example read
        # as doing nothing: its first stage really is doing nothing.
        run = self.block["runs"][0]
        cold = next(stage for stage in run["stages"] if stage["index"] == 1)
        self.assertEqual(cold["label"], "Cold")
        for record in run["shoes"]:
            summary = next(entry for entry in record["stages"] if entry["index"] == 1)
            self.assertLess(summary["peak_tangential_force_n"], FORCE_TOLERANCE_N, cold["label"])
            # Not "sticking": a mu = 0 shoe has no cone to stick, and the
            # reader correctly calls that indeterminate. What must not appear is
            # a shoe that moved or left the surface.
            self.assertNotIn(summary["status"], {"sliding", "open"}, cold["label"])
            self.assertFalse(summary["transitioned"], cold["label"])
            self.assertLess(summary["peak_slip_m"], FORCE_TOLERANCE_N * 1e-6, cold["label"])

    def test_finding_identifiers_are_unique_within_the_run(self) -> None:
        run = self.block["runs"][0]
        identifiers = [finding["id"] for finding in run["findings"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(run["attention_count"], sum(
            1 for finding in run["findings"] if finding["severity"] == "attention"
        ))


if __name__ == "__main__":
    unittest.main()
