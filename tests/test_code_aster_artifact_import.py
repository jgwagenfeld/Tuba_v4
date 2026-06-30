import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis import create_operating_geometry_state, create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene


class TestCodeAsterArtifactImport(unittest.TestCase):
    def _model(self):
        model = Model(project_name="RealAsterArtifacts")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(node=n0, type="anchor", id="support_anchor_0")
        model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
        return model, n0, n1

    def test_import_existing_code_aster_tables_into_result_state_and_scene(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            exported = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir)

        result_state = artifact.result_state
        self.assertEqual(artifact.study.id, exported.id)
        self.assertEqual(artifact.analysis_mesh.id, exported.mesh_id)
        self.assertEqual(result_state.solver_name, "Code_Aster")
        self.assertEqual(result_state.load_case, "Hot")
        self.assertEqual(result_state.node_displacements[n1][:3], (0.0, 0.015, 0.0))
        self.assertEqual(result_state.node_reactions[n0][:3], (1000.0, 0.0, -250.0))
        self.assertEqual(result_state.element_results["pipe_0"]["forces_n1"][:3], [10.0, 20.0, 30.0])
        self.assertEqual(result_state.element_results["pipe_0"]["max_von_mises"], 120.0e6)
        self.assertIn("study_depl.csv", result_state.files["depl"])
        self.assertEqual(artifact.diagnostics, [])

        operating_state = create_operating_geometry_state(model=model, result_state=result_state)
        visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=25.0)
        scene = build_visualization_scene(
            model,
            analysis_meshes=[artifact.analysis_mesh],
            result_states=[result_state],
            geometry_states=[operating_state, visual_state],
            scene_id="scene:real_code_aster_artifacts",
        )
        scene.validate()

        stress = next(overlay for overlay in scene.overlays if overlay.kind == "solver_result" and overlay.data["result_type"] == "stress")
        displacement = next(
            overlay for overlay in scene.overlays if overlay.kind == "solver_result" and overlay.data["result_type"] == "displacement"
        )
        self.assertEqual(stress.data["values"]["object:element:pipe_0"], 120.0e6)
        n1_vector = next(vector for vector in displacement.data["vectors"] if vector["node_id"] == n1)
        self.assertEqual(n1_vector["displacement_m"], [0.0, 0.015, 0.0])

    def test_artifact_review_example_writes_scene_bundle(self):
        from examples.code_aster_artifact_review import run_example

        with TemporaryDirectory() as tmpdir:
            summary = run_example(tmpdir)
            scene = json.loads(Path(summary["scene"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["result_source"], "code_aster_artifact_tables")
        self.assertEqual(summary["result_state_id"], "result_state:Hot")
        self.assertGreater(summary["counts"]["scene_objects"], 0)
        self.assertIn("solver_result", {overlay["kind"] for overlay in scene["overlays"]})


def _write_solver_tables(work_dir: Path, *, n0: str, n1: str) -> None:
    (work_dir / "study_depl.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},0.0,0.0,0.0,0.0,0.0,0.0",
                f"{n1},0.0,0.015,0.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_effo.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,NXX,VY,VZ,MT,MFY,MFZ",
                f"pipe_0,{n0},10.0,20.0,30.0,1.0,2.0,3.0",
                f"pipe_0,{n1},11.0,21.0,31.0,4.0,5.0,6.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_reac.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},1000.0,0.0,-250.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_sieq.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,VMIS",
                f"pipe_0,{n0},80000000.0",
                f"pipe_0,{n1},120000000.0",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
