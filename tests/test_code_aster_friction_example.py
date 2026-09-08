import os
import unittest
from pathlib import Path

import numpy as np

from examples.code_aster_friction_review import LOAD_PATH, build_friction_comparison_model
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts


class NativePipingFrictionExample(unittest.TestCase):
    def test_combined_model_has_disconnected_translated_identical_copies(self):
        model = build_friction_comparison_model()
        self.assertEqual(LOAD_PATH, ["Cold", "Hot", "Cold", "Lift", "Cold"])
        self.assertEqual([support.id for support in model.supports],
                         ["NF_anchor", "NF_S1", "NF_S2", "F_anchor", "F_S1", "F_S2"])
        self.assertEqual([support.friction_coefficient for support in model.supports if support.type == "rest"],
                         [0.0, 0.0, 0.3, 0.3])
        nf_nodes = {node for element in model.elements if element.id.startswith("NF_") for node in (element.n1, element.n2)}
        f_nodes = {node for element in model.elements if element.id.startswith("F_") for node in (element.n1, element.n2)}
        self.assertFalse(nf_nodes & f_nodes)
        for nf_id, f_id in zip(sorted(nf_nodes, key=lambda value: int(value[1:])),
                               sorted(f_nodes, key=lambda value: int(value[1:]))):
            np.testing.assert_allclose(model.nodes[f_id].coords - model.nodes[nf_id].coords, [0.0, 5.0, 0.0])
        for case in model.load_cases.values():
            self.assertEqual([tuple(load.components) for load in case.nodal_forces[:2]],
                             [tuple(load.components) for load in case.nodal_forces[2:]])


@unittest.skipUnless(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1", "requires real Code_Aster")
class NativePipingExampleSolve(unittest.TestCase):
    def test_one_attested_run_contains_both_contact_histories(self):
        model = build_friction_comparison_model()
        artifacts = Path("notebooks/code_aster_results/native-friction-review")
        run = (import_code_aster_artifacts(model=model, work_dir=artifacts)
               if (artifacts / "study_execution.json").is_file()
               else model.solve(pipe_modelization="POU_D_T", load_path=LOAD_PATH, load_step=0.1,
                                work_dir=".build/native-friction-comparison-test"))
        run.validate_for_publication(model)
        self.assertEqual(run.study.metadata["compiler_inputs"]["load_path"], LOAD_PATH)
        self.assertGreater(len(run.result_states), len(LOAD_PATH))
        self.assertEqual({key for state in run.result_states for key in state.contact_results},
                         {"NF_S1", "NF_S2", "F_S1", "F_S2"})
        self.assertTrue({"open", "sticking", "sliding"} <= {
            contact.status for state in run.result_states
            for key, contact in state.contact_results.items() if key.startswith("F_")})
        for state in run.result_states:
            for key, contact in state.contact_results.items():
                if key.startswith("NF_"):
                    self.assertIsNone(contact.utilization)
                    self.assertLess(np.linalg.norm(contact.tangential_force), 1e-8)
        lift = next(state for state in run.result_states if state.metadata["pseudo_time"] == 4.0)
        self.assertEqual(lift.contact_results["F_S2"].status, "open")
        self.assertNotEqual(lift.contact_results["F_S1"].status, "open")
        self.assertTrue(all(contact.status != "open" for contact in run.result_states[-1].contact_results.values()))


if __name__ == "__main__":
    unittest.main()
