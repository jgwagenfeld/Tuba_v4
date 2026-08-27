import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from tuba import Model
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterGeneratedMeshResults(unittest.TestCase):
    def _parse_single_node_displacement(self, displacement_fields: str):
        model = Model(project_name="InvalidDisplacement")
        node_id = model.add_node([0.0, 0.0, 0.0])
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                f"{node_id},{displacement_fields}\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8"
            )
            root.joinpath("study_reac.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8"
            )
            root.joinpath("study_sieq.csv").write_text(
                "MAILLE,NOEUD,VMIS\n", encoding="utf-8"
            )
            return CodeAsterSolver()._parse_results(model, root)

    def _parse_single_pipe_forces(self, force_table: str):
        model = Model(project_name="InvalidInternalForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.0,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(force_table, encoding="utf-8")
            root.joinpath("study_reac.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8"
            )
            root.joinpath("study_sieq.csv").write_text(
                "MAILLE,NOEUD,VMIS\n", encoding="utf-8"
            )
            return CodeAsterSolver()._parse_results(model, root)

    def test_depl_parser_rejects_unavailable_translation(self):
        with self.assertRaisesRegex(
            RuntimeError,
            r"invalid translation DX='-' for node 'N0'.*finite",
        ):
            self._parse_single_node_displacement("-,0.0,0.0,-,-,-")

    def test_depl_parser_rejects_non_finite_translations(self):
        cases = {
            "NaN": "0.0,NaN,0.0,-,-,-",
            "positive infinity": "0.0,0.0,Inf,-,-,-",
            "negative infinity": "-Inf,0.0,0.0,-,-,-",
        }
        for label, fields in cases.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"invalid translation (?:DX|DY|DZ)='(?:NaN|Inf|-Inf)' for node 'N0'.*finite",
                ):
                    self._parse_single_node_displacement(fields)

    def test_depl_parser_preserves_translation_when_rotations_are_not_applicable(self):
        model = Model(project_name="CableDisplacement")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_cable_section("CableSec", radius=0.01, pretension=500.0)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="cable_0", type="cable", n1=n0, n2=n1, section="CableSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                f"{n0},0.0,0.0,0.0,-,-,-\n"
                f"{n1},0.001,0.002,0.003,-,-,-\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            root.joinpath("study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            results = CodeAsterSolver()._parse_results(model, root)

        self.assertTrue(np.allclose(results.get_displacement(n1)[:3], [0.001, 0.002, 0.003]))
        self.assertTrue(np.isnan(results.get_displacement(n1)[3:]).all())

    def test_effo_parser_preserves_axial_only_bar_and_cable_results(self):
        model = Model(project_name="AxialOnlyInternalForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_bar_section("BarSec", OD=0.04, WT=0.005)
        model.add_cable_section("CableSec", radius=0.01, pretension=500.0)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        n2 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="bar_0", type="bar", n1=n0, n2=n1, section="BarSec", material="Steel")
        model.add_element(id="cable_0", type="cable", n1=n1, n2=n2, section="CableSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.0,0.0,0.0,-,-,-\n"
                "N1,0.001,0.0,0.0,-,-,-\n"
                "N2,0.002,0.0,0.0,-,-,-\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "bar_0,N0,100.0,-,-,-,-,-\n"
                "bar_0,N1,101.0,-,-,-,-,-\n"
                "cable_0,N1,200.0,-,-,-,-,-\n"
                "cable_0,N2,201.0,-,-,-,-,-\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8"
            )
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            results = CodeAsterSolver()._parse_results(model, root)

        self.assertEqual(results.get_forces("bar_0")["n1"][0], 100.0)
        self.assertTrue(np.isnan(results.get_forces("bar_0")["n1"][1:]).all())
        self.assertEqual(results.get_forces("cable_0")["n2"][0], 201.0)
        self.assertTrue(np.isnan(results.get_forces("cable_0")["n2"][1:]).all())

    def test_effo_parser_rejects_unavailable_beam_components(self):
        model = Model(project_name="InvalidBeamInternalForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("BeamSec", height_y=0.1, height_z=0.1)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(
            id="beam_0",
            type="beam",
            n1=n0,
            n2=n1,
            section="BeamSec",
            material="Steel",
        )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.0,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "beam_0,N0,100.0,-,-,-,-,-\n"
                "beam_0,N1,101.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8"
            )
            root.joinpath("study_sieq.csv").write_text(
                "MAILLE,NOEUD,VMIS\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(
                RuntimeError,
                r"invalid internal-force component VY='-'.*beam_0:N0.*finite",
            ):
                CodeAsterSolver()._parse_results(model, root)

    def test_effo_parser_rejects_missing_moment_component(self):
        with self.assertRaisesRegex(
            RuntimeError,
            r"invalid internal-force component MFY=.*pipe_0:N0.*finite",
        ):
            self._parse_single_pipe_forces(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFZ\n"
                "pipe_0,N0,100.0,0.0,0.0,0.0,0.0\n"
                "pipe_0,N1,100.0,0.0,0.0,0.0,0.0\n"
            )

    def test_effo_parser_rejects_non_finite_components(self):
        for value in ("NaN", "Inf", "-Inf"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    RuntimeError,
                    rf"invalid internal-force component MFY='{value}'.*pipe_0:N0.*finite",
                ):
                    self._parse_single_pipe_forces(
                        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                        f"pipe_0,N0,100.0,0.0,0.0,0.0,{value},0.0\n"
                        "pipe_0,N1,100.0,0.0,0.0,0.0,0.0,0.0\n"
                    )

    def test_effo_parser_rejects_non_generated_segment_ids(self):
        for element_id in ("pipe_0_sbogus", "pipe_0_s0"):
            with self.subTest(element_id=element_id):
                with self.assertRaisesRegex(RuntimeError, "no element internal forces"):
                    self._parse_single_pipe_forces(
                        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                        f"{element_id},N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
                        f"{element_id},N1,101.0,0.0,0.0,0.0,0.0,0.0\n"
                    )

    def test_missing_sieq_is_unavailable_instead_of_zero(self):
        results = self._parse_single_pipe_forces(
            "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
            "pipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
            "pipe_0,N1,100.0,0.0,0.0,0.0,0.0,0.0\n"
        )

        self.assertTrue(np.isnan(results.get_max_von_mises("pipe_0")))

    def test_result_parsers_fold_only_generated_bend_segments(self):
        model = Model(project_name="GeneratedBendResultIds")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.0,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_bend_0_s0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
                "pipe_bend_0_s15,N1,101.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8"
            )
            root.joinpath("study_sieq.csv").write_text(
                "MAILLE,NOEUD,VMIS\n"
                "pipe_bend_0_s0,N0,10.0\n"
                "pipe_bend_0_sbogus,N0,999.0\n",
                encoding="utf-8",
            )

            results = CodeAsterSolver()._parse_results(model, root)

        self.assertEqual(results.get_forces("pipe_bend_0")["n1"][0], 100.0)
        self.assertEqual(results.get_forces("pipe_bend_0")["n2"][0], 101.0)
        self.assertEqual(results.get_max_von_mises("pipe_bend_0"), 10.0)

    def test_depl_parser_preserves_generated_mesh_node_displacements(self):
        model = Model(project_name="GeneratedMeshResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_bend_0", type="pipe_bend", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "study_depl.csv").write_text(
                "\n".join(
                    [
                        "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                        "N0,0.001,0.0,0.0,0.0,0.0,0.0",
                        "N1,0.002,0.0,0.0,0.0,0.0,0.0",
                        "pipe_bend_0_n1,0.010,0.020,0.030,0.001,0.002,0.003",
                    ]
                ),
                encoding="utf-8",
            )
            Path(tmpdir, "study_effo.csv").write_text(
                "\n".join(
                    [
                        "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                        "pipe_bend_0,N0,100.0,0.0,0.0,0.0,0.0,0.0",
                        "pipe_bend_0,N1,100.0,0.0,0.0,0.0,0.0,0.0",
                    ]
                ),
                encoding="utf-8",
            )
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            Path(tmpdir, "study_manifest.json").write_text(
                json.dumps(
                    {
                        "analysis_mesh": {
                            "id": "analysis_mesh:Hot",
                            "nodes": {
                                "N0": [0.0, 0.0, 0.0],
                                "N1": [1.0, 0.0, 0.0],
                                "pipe_bend_0_n1": [0.5, 0.1, 0.0],
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            results = CodeAsterSolver()._parse_results(model, Path(tmpdir))

        self.assertTrue(np.allclose(results.get_displacement("N0")[:3], [0.001, 0.0, 0.0]))
        self.assertNotIn("pipe_bend_0_n1", results.node_results)
        self.assertIn("pipe_bend_0_n1", results.analysis_node_results)
        self.assertTrue(np.allclose(results.get_analysis_displacement("pipe_bend_0_n1")[:3], [0.010, 0.020, 0.030]))
        self.assertNotIn("non-native analysis node", " ".join(results.parser_diagnostics))

    def test_depl_parser_warns_for_generated_node_absent_from_manifest_mesh(self):
        model = Model(project_name="UnmappedGeneratedMeshResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_bend_0", type="pipe_bend", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.001,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.002,0.0,0.0,0.0,0.0,0.0\n"
                "unmapped_analysis_node,0.010,0.020,0.030,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_bend_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
                "pipe_bend_0,N1,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            root.joinpath("study_manifest.json").write_text(
                json.dumps({"analysis_mesh": {"id": "analysis_mesh:Hot", "nodes": {"N0": [0, 0, 0]}}}),
                encoding="utf-8",
            )

            results = CodeAsterSolver()._parse_results(model, root)

        self.assertIn("unmapped_analysis_node", results.analysis_node_results)
        self.assertIn("without mesh source mapping", " ".join(results.parser_diagnostics))

    def test_parse_raises_on_empty_displacement_results(self):
        """A run that emitted no displacement rows must fail loudly, not return zeros."""
        model = Model(project_name="EmptyResults")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            # Header-only tables: solver "ran" but produced no data rows.
            Path(tmpdir, "study_depl.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                CodeAsterSolver()._parse_results(model, Path(tmpdir))

    def test_parse_raises_on_empty_force_results(self):
        """Displacement present but no internal forces must fail loudly, not pass compliance on zeros."""
        model = Model(project_name="EmptyForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            # Displacement solved, but the force table came back empty (post-processing
            # failed or labels mismatched). Zero forces would silently pass compliance.
            Path(tmpdir, "study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.001,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.002,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            Path(tmpdir, "study_effo.csv").write_text("MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n", encoding="utf-8")
            Path(tmpdir, "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            Path(tmpdir, "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                CodeAsterSolver()._parse_results(model, Path(tmpdir))

    def test_parse_raises_on_partial_displacement_results(self):
        model = Model(project_name="PartialDisplacements")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\nN0,0.001,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
                "pipe_0,N1,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "missing displacement results.*N1"):
                CodeAsterSolver()._parse_results(model, root)

    def test_parse_raises_when_pipe_force_endpoint_is_missing(self):
        model = Model(project_name="PartialForces")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.001,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.002,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            root.joinpath("study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            root.joinpath("study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "missing internal-force results.*pipe_0:N1"):
                CodeAsterSolver()._parse_results(model, root)

    def test_parse_result_tables_does_not_auto_open_rmed(self):
        model = Model(project_name="RmedBoundary")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")

        calls = []

        class FakeMeshio:
            @staticmethod
            def read(path, *, file_format=None):
                calls.append((Path(path).name, file_format))
                raise RuntimeError("RMED loading must be explicit")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study_depl.csv").write_text(
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n"
                "N0,0.001,0.0,0.0,0.0,0.0,0.0\n"
                "N1,0.002,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            (root / "study_effo.csv").write_text(
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ\n"
                "pipe_0,N0,100.0,0.0,0.0,0.0,0.0,0.0\n"
                "pipe_0,N1,100.0,0.0,0.0,0.0,0.0,0.0\n",
                encoding="utf-8",
            )
            (root / "study_reac.csv").write_text("NOEUD,DX,DY,DZ,DRX,DRY,DRZ\n", encoding="utf-8")
            (root / "study_sieq.csv").write_text("MAILLE,NOEUD,VMIS\n", encoding="utf-8")
            (root / "study.rmed").write_bytes(b"fake-rmed")

            with patch.dict("sys.modules", {"meshio": FakeMeshio}):
                results = CodeAsterSolver()._parse_results(model, root)

            self.assertEqual(root / "study.rmed", results.result_file)
            self.assertIsNone(results.raw_mesh)

        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
