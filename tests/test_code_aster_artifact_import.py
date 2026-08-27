import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from tuba import Model
from tuba.analysis import AnalysisRun, create_operating_geometry_state, create_visual_deformed_geometry_state
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.external.ifc import IfcExporter
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene


_ATTESTED_FILES = (
    "study.comm", "study.mail", "study.export", "study_manifest.json",
    "study_tuba_fem.json", "study.mess", "study.rmed", "study_depl.csv",
    "study_effo.csv", "study_reac.csv", "study_sieq.csv",
)


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
            (work_dir / "study.mess").write_text("Version 18.0.12", encoding="utf-8")

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir, allow_unverified=True)

        self.assertIsInstance(artifact, AnalysisRun)
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
        self.assertIn("study.mess", result_state.files["mess"])
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

    def test_import_without_manifest_is_rejected(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)

            with self.assertRaisesRegex(FileNotFoundError, "study_manifest.json"):
                import_code_aster_artifacts(model=model, work_dir=work_dir)

    def test_import_without_attestation_requires_explicit_historical_mode(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)

            with self.assertRaisesRegex(ValueError, "solve attestation.*allow_unverified"):
                import_code_aster_artifacts(model=model, work_dir=work_dir)
            artifact = import_code_aster_artifacts(
                model=model,
                work_dir=work_dir,
                allow_unverified=True,
            )

        self.assertNotIn("solve_attestation", artifact.result_state.metadata)
        self.assertEqual(artifact.result_state.metadata["result_trust"], "unverified")

    def test_import_rebases_portable_manifest_records_to_the_actual_import_root(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = root / "original"
            moved = root / "moved"
            CodeAsterSolver(work_dir=original).export_analysis_study(model, "Hot", original)
            _write_solver_tables(original, n0=n0, n1=n1)
            shutil.move(str(original), moved)

            artifact = import_code_aster_artifacts(model=model, work_dir=moved, allow_unverified=True)

            self.assertEqual(Path(artifact.study.work_dir), moved)
            self.assertTrue(
                all(Path(value).parent == moved for value in artifact.study.input_files.values())
            )
            self.assertTrue(
                all(Path(value).parent == moved for value in artifact.analysis_mesh.files.values())
            )

    def test_import_rejects_tampered_attested_result_before_exposing_values(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            study = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            _write_execution_attestation(work_dir, study.solver_input_identity)
            (work_dir / "study_depl.csv").write_text("tampered", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "study_depl.csv.*(size|hash)"):
                import_code_aster_artifacts(model=model, work_dir=work_dir)

    def test_import_rejects_attestation_with_machine_path_field(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            study = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            _write_execution_attestation(work_dir, study.solver_input_identity)
            attestation_path = work_dir / "study_execution.json"
            attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
            attestation["command"] = "C:\\Users\\Alice\\run_aster study.export"
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unknown.*command"):
                import_code_aster_artifacts(model=model, work_dir=work_dir)

    def test_public_parser_ignores_forged_validation_attribute(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            study = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            _write_execution_attestation(work_dir, study.solver_input_identity)
            (work_dir / "study_depl.csv").write_text("tampered", encoding="utf-8")
            solver = CodeAsterSolver()
            solver._validated_attestation = {"forged": True}

            with self.assertRaisesRegex(ValueError, "study_depl.csv.*(size|hash)"):
                solver.parse_result_artifacts(
                    model,
                    work_dir,
                    study.load_case,
                    study=study,
                )

    def test_import_preserves_validated_attestation_on_result_state(self):
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            study = CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            _write_execution_attestation(work_dir, study.solver_input_identity)

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir)

        self.assertEqual(
            artifact.result_state.metadata["solve_attestation"]["solver_input_identity"],
            study.solver_input_identity.to_dict(),
        )
        self.assertEqual(artifact.result_state.metadata["result_trust"], "verified")
        self.assertEqual(artifact.result_state.files["execution"], str(work_dir / "study_execution.json"))

    def test_import_preserves_rmed_diagnostic_in_result_state_metadata(self):
        pytest.importorskip("h5py", exc_type=ImportError)
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)
            (work_dir / "study.rmed").write_bytes(b"not-an-rmed-file")

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir, allow_unverified=True)

        warning = next(
            item
            for item in artifact.diagnostics
            if item["code"] == "visualization.code_aster_artifacts.rmed_read_failed"
        )
        self.assertIn(warning, artifact.result_state.metadata["parser_diagnostics"])

    def test_import_deduplicates_existing_string_parser_diagnostics(self):
        model, n0, n1 = self._model()
        warning = "Legacy parser warning."
        parse_result_artifacts = CodeAsterSolver._parse_result_artifacts_after_validation

        def parse_with_duplicate_diagnostics(solver, *args, **kwargs):
            results = parse_result_artifacts(solver, *args, **kwargs)
            results.parser_diagnostics.extend([warning, warning])
            return results

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)

            with patch.object(CodeAsterSolver, "_parse_result_artifacts_after_validation", parse_with_duplicate_diagnostics):
                artifact = import_code_aster_artifacts(model=model, work_dir=work_dir, allow_unverified=True)

        self.assertEqual(artifact.result_state.metadata["parser_diagnostics"], [warning])

    def test_artifact_review_example_writes_engineering_review(self):
        from examples.code_aster_artifact_review import run_example

        with TemporaryDirectory() as tmpdir:
            summary = run_example(tmpdir)
            root = Path(summary["bundle_root"])
            scene = json.loads(Path(summary["scene"]).read_text(encoding="utf-8"))
            review = json.loads((root / "review.json").read_text(encoding="utf-8"))
            output_files = {
                relative: (root / relative).exists()
                for relative in (
                    "review.json",
                    "report_manifest.json",
                    "index.html",
                    "reports/fe_stress.csv",
                    "reports/displacements.csv",
                    "scene.json",
                )
            }

        self.assertEqual(summary["result_source"], "code_aster_artifact_tables")
        self.assertEqual(summary["artifact_provenance"], "committed_real_code_aster_artifacts")
        self.assertEqual(summary["result_state_id"], "result_state:Operating")
        self.assertGreater(summary["counts"]["scene_objects"], 0)
        self.assertIn("solver_result", {overlay["kind"] for overlay in scene["overlays"]})
        self.assertTrue(all(output_files.values()), output_files)
        provenance = next(
            record
            for record in review["provenance"]
            if record["kind"] == "result_state"
        )
        self.assertIn("pipe_bend_0_n1", provenance["metadata"]["analysis_node_ids"])
        analysis_row = next(
            row
            for row in review["tables"]["displacements"]["rows"]
            if row["node_id"] == "pipe_bend_0_n1"
        )
        self.assertEqual(analysis_row["entity_ref"], "analysis_node:pipe_bend_0_n1")
        self.assertEqual(analysis_row["location_kind"], "analysis_node")

    def test_artifact_review_chain_exports_ifc_result_provenance(self):
        ifcopenshell = pytest.importorskip("ifcopenshell", exc_type=ImportError)
        model, n0, n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            CodeAsterSolver(work_dir=work_dir).export_analysis_study(model, "Hot", work_dir)
            _write_solver_tables(work_dir, n0=n0, n1=n1)

            artifact = import_code_aster_artifacts(model=model, work_dir=work_dir, allow_unverified=True)
            operating_state = create_operating_geometry_state(model=model, result_state=artifact.result_state)
            visual_state = create_visual_deformed_geometry_state(model=model, result_state=artifact.result_state, visual_scale=25.0)
            scene = build_visualization_scene(
                model,
                analysis_meshes=[artifact.analysis_mesh],
                result_states=[artifact.result_state],
                geometry_states=[operating_state, visual_state],
                scene_id="scene:code_aster_to_ifc_release_gate",
            )
            scene.validate()

            ifc_path = work_dir / "review.ifc"
            IfcExporter().export_model(
                model,
                ifc_path,
                results=artifact.results,
                result_state=artifact.result_state,
            )
            ifc_file = ifcopenshell.open(str(ifc_path))

        pipe = next(product for product in ifc_file.by_type("IfcPipeSegment") if product.Name == "pipe_0")
        operating_props = _product_pset_values(pipe, "Pset_TubaOperatingState")
        self.assertEqual(operating_props["LoadCase"], "Hot")
        self.assertEqual(operating_props["SolverName"], "Code_Aster")
        self.assertEqual(operating_props["StudyId"], artifact.study.id)
        self.assertEqual(operating_props["ResultStateId"], artifact.result_state.id)
        self.assertEqual(operating_props["MeshId"], artifact.analysis_mesh.id)
        self.assertAlmostEqual(operating_props["MaxNodeDisplacementM"], 0.015)

        stress_props = _product_pset_values(pipe, "Pset_TubaStressAnalysis")
        self.assertGreater(stress_props["MaxStress_Pa"], 0.0)


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


def _write_execution_attestation(work_dir: Path, identity) -> None:
    (work_dir / "study.mess").write_text("Version 18.0.12", encoding="utf-8")
    (work_dir / "study.rmed").write_bytes(b"RMED")
    artifacts = {
        filename: {
            "size_bytes": (work_dir / filename).stat().st_size,
            "sha256": hashlib.sha256((work_dir / filename).read_bytes()).hexdigest(),
        }
        for filename in _ATTESTED_FILES
    }
    (work_dir / "study_execution.json").write_text(
        json.dumps(
            {
                "schema_version": "tuba.code_aster_execution.v1",
                "solver_name": "Code_Aster",
                "solver_version": "18.0.12",
                "execution_method": "wsl",
                "solved_at": "2026-07-29T12:00:00Z",
                "solver_input_identity": identity.to_dict(),
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )


def _product_pset_values(product, name: str) -> dict[str, object]:
    for definition in product.IsDefinedBy:
        if not definition.is_a("IfcRelDefinesByProperties"):
            continue
        pset = definition.RelatingPropertyDefinition
        if pset.is_a("IfcPropertySet") and pset.Name == name:
            return {prop.Name: prop.NominalValue.wrappedValue for prop in pset.HasProperties}
    raise AssertionError(f"Missing IFC property set {name!r} on {product.Name!r}.")


if __name__ == "__main__":
    unittest.main()
