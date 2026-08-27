import unittest
from dataclasses import replace

import numpy as np

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisRun, AnalysisStudy, build_solver_input_identity
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import (
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.clash import TrimeshClashEngine
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.solver.code_aster_runtime import expected_code_aster_artifact_files
from tuba.visualization import build_visualization_scene
from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture


class TestVisualizationResults(unittest.TestCase):
    def _model_and_results(self):
        model = Model(project_name="ResultReview")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.define_load_case("Hot", gravity=True, temperature=100.0)
        results = FEAResults(solver_name="Code_Aster", load_case="Hot")
        results.node_results[n0] = NodeResult(
            node_id=n0,
            displacement=np.zeros(6),
            reaction_force=np.array([100.0, 0.0, -500.0, 25.0, 0.0, -75.0]),
        )
        results.node_results[n1] = NodeResult(
            node_id=n1,
            displacement=np.array([0.01, 0.0, 0.0, 0.0, 0.0, 0.0]),
            reaction_force=np.zeros(6),
        )
        results.element_results[elem.id] = ElementResult(
            element_id=elem.id,
            forces_n1=np.zeros(6),
            forces_n2=np.zeros(6),
            von_mises_n1=80.0e6,
            von_mises_n2=120.0e6,
            max_von_mises=120.0e6,
        )
        return model, results

    def _analysis_run(self):
        model, results = self._model_and_results()
        identity = build_solver_input_identity(model, "Hot")
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
            solver_input_identity=identity,
        )
        state = result_state_from_fea_results(model=model, study=study, results=results)
        state = replace(
            state,
            metadata={
                **state.metadata,
                "result_trust": "verified",
                "solve_attestation": {
                    "schema_version": "tuba.code_aster_execution.v1",
                    "solver_name": "Code_Aster",
                    "solver_version": "18.0.12",
                    "execution_method": "test",
                    "solved_at": "2026-08-27T12:00:00Z",
                    "solver_input_identity": identity.to_dict(),
                    "artifacts": {
                        filename: {"size_bytes": 1, "sha256": "0" * 64}
                        for filename in expected_code_aster_artifact_files(study.metadata)
                    },
                },
            },
        )
        mesh = AnalysisMesh(
            id=study.mesh_id,
            model_revision=0,
            solver_name="Code_Aster",
            nodes={node_id: tuple(node.coords) for node_id, node in model.nodes.items()},
            elements={element.id: (element.n1, element.n2) for element in model.elements},
            groups={},
            node_sources={},
            element_sources={},
            solver_input_identity=identity,
        )
        return model, AnalysisRun(study=study, results=results, result_state=state, analysis_mesh=mesh)

    def test_analysis_run_publishes_result_mesh_and_deformed_records(self):
        model, run = self._analysis_run()
        visual_state = create_visual_deformed_geometry_state(
            model=model,
            result_state=run.result_state,
            visual_scale=10.0,
        )

        scene = build_visualization_scene(
            model,
            analysis_runs=[run],
            geometry_states=[visual_state],
            scene_id="scene_result_review",
        )
        scene.validate()

        deformed = next(obj for obj in scene.objects if obj.kind == "deformed_centerline")
        asset = next(asset for asset in scene.geometry_assets if asset.id == deformed.geometry_asset_id)
        self.assertEqual(asset.format, "polyline")
        self.assertEqual(asset.generation_config["points"], [[0.0, 0.0, 0.0], [1.1, 0.0, 0.0]])
        self.assertEqual(deformed.metadata["load_case"], "Hot")
        self.assertEqual(deformed.metadata["displacement_scale"], 10.0)
        self.assertTrue(any(obj.kind == "result_state" for obj in scene.objects))
        self.assertTrue(any(obj.kind == "analysis_mesh_element" for obj in scene.objects))

        stress = next(overlay for overlay in scene.overlays if overlay.kind == "solver_result" and overlay.data["result_type"] == "stress")
        self.assertEqual(stress.data["values"], {"object:element:pipe_0": 120.0e6})
        self.assertEqual(stress.data["range"], {"min": 120.0e6, "max": 120.0e6})
        self.assertEqual(
            {overlay.data.get("result_type") for overlay in scene.overlays if overlay.kind == "solver_result"},
            {"stress", "displacement", "reaction_force", "reaction_moment"},
        )

    def test_analysis_run_cannot_mix_with_lower_level_result_records(self):
        model, run = self._analysis_run()

        for records in (
            {"result_states": [run.result_state]},
            {"analysis_meshes": [run.analysis_mesh]},
        ):
            with self.subTest(records=tuple(records)):
                with self.assertRaisesRegex(ValueError, "analysis_runs.*lower-level"):
                    build_visualization_scene(model, analysis_runs=[run], **records)

    def test_scene_analysis_run_validates_persistent_record_lineage(self):
        model, run = self._analysis_run()
        invalid_runs = (
            ("study solver", replace(run, study=replace(run.study, solver_name="Fabricated")), "Code_Aster"),
            (
                "result state solver",
                replace(run, result_state=replace(run.result_state, solver_name="Fabricated")),
                "Code_Aster",
            ),
            (
                "study revision",
                replace(run, study=replace(run.study, model_revision=1)),
                "model revision",
            ),
            (
                "result state revision",
                replace(run, result_state=replace(run.result_state, model_revision=1)),
                "model revision",
            ),
            (
                "study load case",
                replace(run, study=replace(run.study, load_case="Cold")),
                "load case",
            ),
        )

        for name, invalid_run, message in invalid_runs:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, message):
                    build_visualization_scene(model, analysis_runs=[invalid_run])

    def test_web_scene_rejects_raw_solver_results_keyword(self):
        model, run = self._analysis_run()

        with self.assertRaisesRegex(TypeError, "unexpected keyword argument 'solver_results'"):
            build_visualization_scene(model, solver_results=run.results)

    def test_build_scene_adds_result_and_geometry_state_records(self):
        fixture = straight_pipe_hot_clash_fixture()
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name=fixture.results.solver_name,
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
        )
        result_state = result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)
        visual_state = create_visual_deformed_geometry_state(model=fixture.model, result_state=result_state, visual_scale=50.0)
        operating_clashes = TrimeshClashEngine().check_operating_state(
            fixture.model,
            cold_state=create_cold_geometry_state(fixture.model),
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        scene = build_visualization_scene(
            fixture.model,
            result_states=[result_state],
            geometry_states=[operating_state, visual_state],
            operating_clash_results=operating_clashes,
            scene_id="scene_operating_state",
        )
        scene.validate()

        result_object = next(obj for obj in scene.objects if obj.kind == "result_state")
        geometry_objects = [obj for obj in scene.objects if obj.kind == "geometry_state"]
        issue = scene.issues[0]
        marker = next(obj for obj in scene.objects if obj.kind == "clash_marker")

        self.assertEqual(result_object.metadata["load_case"], "Hot")
        self.assertEqual({obj.metadata["purpose"] for obj in geometry_objects}, {"engineering", "visualization"})
        self.assertEqual(issue.external_refs["clash"]["metadata"]["geometry_state"], operating_state.id)
        self.assertEqual(marker.metadata["clash_metadata"]["load_case"], "Hot")
        self.assertEqual(issue.severity, "error")


if __name__ == "__main__":
    unittest.main()
