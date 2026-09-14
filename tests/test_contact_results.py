import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from tuba import Model
from tuba.analysis import AnalysisRun, AnalysisStudy
from tuba.analysis.code_aster_artifacts import _with_artifact_files
from tuba.analysis.provenance import build_solver_input_identity
from tuba.analysis.results import ResultState, fea_results_from_result_state, result_state_from_fea_results
from tuba.solver.base import ContactResult, FEAResults


def contact():
    return ContactResult(
        support_id="shoe", node_id="N0", status="sticking", normal=(0, 1, 0),
        normal_force=10000, tangential_force=(-1000, 0, 0), gap=-1e-6,
        relative_displacement=(1e-5, -1e-6, 0), slip=(0, 0, 0),
        friction_limit=3000, utilization=1 / 3, status_source="derived",
    )


class TestContactResults(unittest.TestCase):
    def setUp(self):
        self.model = Model(project_name="Contact persistence fixture")
        self.model.define_load_case("Cold", gravity=False)
        identity = build_solver_input_identity(self.model, "Cold")
        self.study = AnalysisStudy(
            id="study", model_revision=0, solver_name="Code_Aster", load_case="Cold",
            work_dir=None, input_files={}, mesh_id="mesh", solver_input_identity=identity,
        )
        self.results = FEAResults("Code_Aster", "Cold", contact_results={"shoe": contact()})
        self.results.metadata = {"stage_index": 0, "stage_label": "Cold", "pseudo_time": 0.0}
        self.state = result_state_from_fea_results(model=self.model, study=self.study, results=self.results)

    def test_round_trip_and_artifact_reconstruction_preserve_contact_and_metadata(self):
        loaded = ResultState.from_dict(json.loads(json.dumps(self.state.to_dict(), allow_nan=False)))
        rebuilt = fea_results_from_result_state(model=self.model, result_state=loaded)
        self.assertEqual(rebuilt.contact_results, self.results.contact_results)
        self.assertEqual(rebuilt.metadata, self.results.metadata)
        copied = _with_artifact_files(loaded, {"contacts": "study_contact.csv"})
        self.assertEqual(copied.contact_results, loaded.contact_results)
        old = self.state.to_dict()
        del old["contact_results"]
        self.assertEqual(ResultState.from_dict(old).contact_results, {})

    def test_malformed_or_missing_contact_data_is_not_replaced_with_zero(self):
        for name, value in (
            ("normal_force", float("nan")), ("gap", float("inf")),
            ("slip", [0, 0]), ("normal", [0, 0, 0]),
            ("tangential_force", [0, float("nan"), 0]),
            ("utilization", float("inf")), ("status", "unknown"),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(contact(), **{name: value})
        data = contact().to_dict()
        del data["slip"]
        with self.assertRaises(TypeError):
            ContactResult.from_dict(data)
        with self.assertRaisesRegex(ValueError, "support_id"):
            replace(self.state, contact_results={"other": contact()})
        self.assertIsNone(replace(contact(), utilization=None).utilization)
        self.assertEqual(replace(contact(), utilization=1.1).utilization, 1.1)

    def _history(self):
        first = replace(self.state, id="step:0", metadata={**self.state.metadata, "result_trust": "verified"})
        final = replace(first, id="step:1", metadata={**first.metadata, "pseudo_time": 1.0})
        return AnalysisRun(self.study, self.results, final, result_states=(first, final))

    def test_history_requires_stage_metadata_order_and_final_compatibility(self):
        run = self._history()
        first, final = run.result_states
        for metadata in ({}, {**first.metadata, "pseudo_time": 2.0}, {**first.metadata, "stage_index": -1}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                replace(run, result_states=(replace(first, metadata=metadata), final))
        with self.assertRaisesRegex(ValueError, "final history"):
            replace(run, result_state=first)
        with self.assertRaisesRegex(ValueError, "study"):
            replace(run, result_states=(replace(first, study_id="another"), final))
        self.assertEqual(AnalysisRun(self.study, self.results, self.state).result_states, ())

    def test_publication_validates_every_history_state(self):
        run = self._history()
        first, final = run.result_states
        with patch("tuba.analysis.run.validate_code_aster_execution_attestation_payload", return_value=self.study.solver_input_identity) as validate:
            run.validate_for_publication(self.model)
            self.assertEqual(validate.call_count, 2)
            for changed in (
                replace(first, load_case="Hot"),
                replace(first, model_revision=1),
                replace(first, solver_input_identity=None),
                replace(first, metadata={**first.metadata, "result_trust": "unverified"}),
            ):
                with self.subTest(state=changed), self.assertRaises(ValueError):
                    replace(run, result_states=(changed, final)).validate_for_publication(self.model)


if __name__ == "__main__":
    unittest.main()
