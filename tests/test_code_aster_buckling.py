"""Linear buckling export, parsing and the refusals that protect it.

Two of these tests are the ones that matter most:

* the **closed-form** one, which pins the pipeline to a value Euler can predict -
  a buckling feature that merely runs is not evidence that it is right;
* the **refusal** ones, because the dangerous failure mode here is a failed
  eigen-solve being reported as a structure that does not buckle.
"""

import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis.buckling import BucklingMode, BucklingResult
from tuba.analysis.provenance import build_solver_input_identity
from tuba.analysis.results import ResultState
from tuba.model import BucklingOptions
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import expected_code_aster_artifact_files
from tuba.solver.parse_buckling import parse_buckling


def _cantilever(load: float = 100_000.0, *, buckling=None, twist: float = 0.0):
    """A fixed-free column carrying a known reference axial load."""
    model = Model("Column")
    model.add_material("S355", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_rectangular_section(
        "SQUARE", height_y=0.1, height_z=0.1, thickness_y=0.025, thickness_z=0.025
    )
    with model.pipe(section="SQUARE", material="S355") as b:
        b.start([0.0, 0.0, 0.0], support="anchor")
        b.set_direction([0.0, 0.0, 1.0])
        b.beam(6.0, twist_angle=twist)
        tip = b.last_node_id
    operation = model.define_operation("Ref", gravity=False, buckling=buckling)
    operation.add_nodal_force(node=tip, force=[0.0, 0.0, -load])
    return model, operation


def _euler_fixed_free(length=6.0, side=0.1, wall=0.025, modulus=2.0e11):
    """pi^2 E I / (4 L^2) for the hollow box the fixture actually builds."""
    inertia = (side**4 - (side - 2 * wall) ** 4) / 12.0
    return math.pi**2 * modulus * inertia / (4 * length**2)


def _export(model, load_case, root):
    solver = CodeAsterSolver(work_dir=root, exec_method="command", line_segments=1)
    return solver, solver.export_analysis_study(model, load_case, root)


class TestBucklingOptions(unittest.TestCase):
    def test_round_trip_preserves_every_choice(self):
        options = BucklingOptions(
            n_modes=8, modal_subspace=16, method="SORENSEN", rigid_modes="OUI",
            stop_on_error=True, mode_shapes=False,
        )
        self.assertEqual(BucklingOptions.from_dict(options.to_dict()), options)

    def test_rejects_a_non_positive_mode_count(self):
        for bad in (0, -1, 2.5, True):
            with self.assertRaises(ValueError):
                BucklingOptions(n_modes=bad)

    def test_rejects_an_unknown_eigensolver(self):
        with self.assertRaisesRegex(ValueError, "TRI_DIAG, SORENSEN or JACOBI"):
            BucklingOptions(method="POWER")

    def test_rejects_an_unknown_rigid_mode_flag(self):
        with self.assertRaisesRegex(ValueError, "OUI or NON"):
            BucklingOptions(rigid_modes="PEUT-ETRE")

    def test_model_accepts_a_plain_dict(self):
        model, _ = _cantilever(buckling={"n_modes": 3})
        _, load_case = model.resolve_load_case("Ref")
        self.assertIsInstance(load_case.buckling, BucklingOptions)
        self.assertEqual(load_case.buckling.n_modes, 3)

    def test_model_refuses_a_bare_number(self):
        with self.assertRaisesRegex(ValueError, "BucklingOptions, a dict, or None"):
            _cantilever(buckling=3)

    def test_survives_a_model_dict_round_trip(self):
        model, _ = _cantilever(buckling={"n_modes": 5, "modal_subspace": 7})
        restored = Model.from_dict(model.to_dict())
        self.assertEqual(restored.operations["Ref"].buckling.n_modes, 5)
        self.assertEqual(restored.operations["Ref"].buckling.modal_subspace, 7)

    def test_absent_by_default(self):
        model, _ = _cantilever()
        self.assertIsNone(model.operations["Ref"].buckling)
        self.assertNotIn("buckling", model.to_dict()["operations"]["Ref"])

    def test_a_dict_assigned_after_declaration_is_accepted(self):
        # op.buckling = {...} is a natural thing to write on an existing
        # operation. It must behave like passing the dict to define_operation
        # rather than failing deep inside the export with an AttributeError.
        model, _ = _cantilever()
        model.operations["Ref"].buckling = {"n_modes": 6, "modal_subspace": 11}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, study = _export(model, "Ref", root)
            self.assertEqual(study.metadata["compiler_inputs"]["buckling"]["n_modes"], 6)
        # And it must serialise rather than raise.
        restored = Model.from_dict(model.to_dict())
        self.assertEqual(restored.operations["Ref"].buckling.n_modes, 6)
        self.assertEqual(
            build_solver_input_identity(model, "Ref").fingerprint,
            build_solver_input_identity(restored, "Ref").fingerprint,
        )

    def test_a_bare_number_assigned_after_declaration_is_refused_clearly(self):
        model, _ = _cantilever()
        model.operations["Ref"].buckling = 3
        with self.assertRaisesRegex(ValueError, "BucklingOptions, a dict, or None"):
            model.to_dict()


class TestBucklingCommEmission(unittest.TestCase):
    def test_emits_the_eigen_chain_in_execution_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 4, "modal_subspace": 8})
            _, study = _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")

            for token in ("CALC_MATR_ELEM", "NUME_DDL", "ASSE_MATRICE", "CALC_MODES",
                          "TYPE_RESU='MODE_FLAMB'", "VERI_MODE"):
                self.assertIn(token, comm)
            # The eigenproblem needs the prestress, so it must follow the static solve
            # and precede FIN, which closes the jeveux memory manager.
            self.assertLess(comm.index("RESU = MECA_STATIQUE("), comm.index("CALC_MODES("))
            self.assertLess(comm.index("CALC_MODES("), comm.index("FIN();"))
            # Both stiffness matrices are assembled: one alone cannot buckle anything.
            self.assertIn("OPTION='RIGI_MECA'", comm)
            self.assertIn("OPTION='RIGI_GEOM'", comm)
            self.assertIn("SIEF_ELGA=PREC", comm)
            # The elastic matrix must be assembled with the boundary conditions,
            # or it has no constrained degrees of freedom and means nothing.
            self.assertRegex(comm, r"OPTION='RIGI_MECA',\s*\n\s*CHARGE=\(BC_\d+")

    def test_writes_the_prestress_with_an_explicit_instance(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 2})
            _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            # Without NUME_ORDRE the run dies with "Exactly one argument of
            # ('NUME_ORDRE', 'INST', 'FREQ', ...) is required".
            self.assertIn("NUME_ORDRE=1,", comm)
            self.assertIn("NOM_CHAM='SIEF_ELGA'", comm)

    def test_quotes_the_veri_mode_flag(self):
        # A bare NON would be a NameError in Code_Aster's own interpreter.
        for stop in (False, True):
            with TemporaryDirectory() as tmp:
                root = Path(tmp)
                model, _ = _cantilever(buckling={"n_modes": 2, "stop_on_error": stop})
                _export(model, "Ref", root)
                comm = (root / "study.comm").read_text(encoding="utf-8")
                expected = f"STOP_ERREUR=\"{'OUI' if stop else 'NON'}\""
                self.assertIn(expected, comm)

    def test_defaults_to_not_stopping_on_the_modal_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 2})
            _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            self.assertIn('STOP_ERREUR="NON"', comm)

    def test_honours_the_requested_mode_count(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 7})
            _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            self.assertIn("NMAX_CHAR_CRIT=7", comm)

    def test_emits_nothing_when_not_requested(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever()
            _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            self.assertNotIn("CALC_MODES", comm)
            self.assertNotIn("MODE_FLAMB", comm)

    def test_skips_the_mode_table_when_shapes_are_not_wanted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 2, "mode_shapes": False})
            _export(model, "Ref", root)
            comm = (root / "study.comm").read_text(encoding="utf-8")
            self.assertIn("CALC_MODES", comm)
            self.assertNotIn("TAB_FLANB", comm)

    def test_declares_the_extra_units_only_when_requested(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 2})
            _export(model, "Ref", root)
            export = (root / "study.export").read_text(encoding="utf-8")
            # run_aster copies a result out only for a unit the export names, so an
            # undeclared unit is silently lost with the temporary directory.
            self.assertIn("R 43", export)
            self.assertIn("R 44", export)
            self.assertIn("study_buckling.json", export)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever()
            _export(model, "Ref", root)
            export = (root / "study.export").read_text(encoding="utf-8")
            self.assertNotIn("study_buckling", export)


class TestBucklingFingerprint(unittest.TestCase):
    def test_buckling_changes_the_fingerprint(self):
        model, _ = _cantilever()
        plain = build_solver_input_identity(model, "Ref")
        model.operations["Ref"].buckling = BucklingOptions(n_modes=2)
        buckled = build_solver_input_identity(model, "Ref")
        self.assertNotEqual(plain.fingerprint, buckled.fingerprint)
        # Same compiler family: this is the beam study plus an extra analysis, not
        # a different kind of study.
        self.assertEqual(plain.compiler_id, buckled.compiler_id)

    def test_different_mode_counts_are_different_studies(self):
        model, _ = _cantilever()
        model.operations["Ref"].buckling = BucklingOptions(n_modes=2)
        two = build_solver_input_identity(model, "Ref")
        model.operations["Ref"].buckling = BucklingOptions(n_modes=8)
        eight = build_solver_input_identity(model, "Ref")
        self.assertNotEqual(two.fingerprint, eight.fingerprint)

    def test_buckling_is_visible_without_the_compiler_contract(self):
        # A caller that builds an identity directly must still see the difference;
        # hiding buckling in compiler_inputs alone would let two different studies
        # collide whenever the contract is not consulted.
        model, _ = _cantilever()
        plain = build_solver_input_identity(model, "Ref")
        model.operations["Ref"].buckling = BucklingOptions(n_modes=2)
        self.assertNotEqual(plain.fingerprint, build_solver_input_identity(model, "Ref").fingerprint)

    def test_records_the_options_in_compiler_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 3, "modal_subspace": 9})
            _, study = _export(model, "Ref", root)
            self.assertEqual(
                study.metadata["compiler_inputs"]["buckling"]["n_modes"], 3
            )
            self.assertEqual(
                study.metadata["compiler_inputs"]["buckling"]["modal_subspace"], 9
            )


class TestBucklingArtifactInventory(unittest.TestCase):
    def test_adds_both_artifacts(self):
        files = expected_code_aster_artifact_files(
            {"compiler_inputs": {"buckling": {"n_modes": 2, "mode_shapes": True}}},
            compiler_id="tuba.code_aster.v2",
        )
        self.assertIn("study_buckling.json", files)
        self.assertIn("study_buckling_modes.csv", files)

    def test_omits_the_mode_table_when_shapes_are_off(self):
        files = expected_code_aster_artifact_files(
            {"compiler_inputs": {"buckling": {"n_modes": 2, "mode_shapes": False}}},
            compiler_id="tuba.code_aster.v2",
        )
        self.assertIn("study_buckling.json", files)
        self.assertNotIn("study_buckling_modes.csv", files)

    def test_a_plain_study_is_unchanged(self):
        files = expected_code_aster_artifact_files({}, compiler_id="tuba.code_aster.v2")
        self.assertFalse([name for name in files if "buckling" in name])

    def test_refuses_an_empty_buckling_input(self):
        with self.assertRaisesRegex(ValueError, "nonempty object"):
            expected_code_aster_artifact_files(
                {"compiler_inputs": {"buckling": {}}}, compiler_id="tuba.code_aster.v2"
            )

    def test_refuses_buckling_on_a_volume_study(self):
        with self.assertRaisesRegex(ValueError, "1D beam-study capability"):
            expected_code_aster_artifact_files(
                {"volume_analysis": True, "compiler_inputs": {"buckling": {"n_modes": 2}}},
                compiler_id="tuba.code_aster.volume.v2",
            )


class TestBucklingRefusals(unittest.TestCase):
    def test_refuses_a_model_with_nothing_supported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = Model("Free")
            model.add_material("S355", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
            model.add_rectangular_section(
                "SQ", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01
            )
            a = model.add_node([0.0, 0.0, 0.0])
            b = model.add_node([0.0, 0.0, 1.0])
            model.add_element(
                id="b1", type="beam", n1=a, n2=b, section="SQ", material="S355"
            )
            model.define_operation("Free", gravity=True, buckling={"n_modes": 2})
            model.validate()
            with self.assertRaisesRegex(ValueError, "requires a supported model"):
                _export(model, "Free", root)

    def test_refuses_buckling_on_a_contact_study(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = _cantilever(buckling={"n_modes": 2})
            # A resting shoe forces the nonlinear path, whose prestress is a history
            # over increments rather than one SIEF_ELGA.
            model.add_support(node=_free_node(model), type="rest")
            model.define_operation("Contact", gravity=True, buckling={"n_modes": 2})
            with self.assertRaisesRegex(ValueError, "unsupported on native contact"):
                _export(model, "Contact", root)

    def test_refuses_buckling_on_a_cable_study(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = Model("Cable")
            model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
            model.add_cable_section("Cable", radius=0.025, pretension=1000.0)
            a = model.add_node([0.0, 0.0, 0.0])
            b = model.add_node([0.0, 0.0, 3.0])
            model.add_support(node=a, type="anchor")
            model.add_element(
                id="c1", type="cable", n1=a, n2=b, section="Cable", material="Steel"
            )
            model.define_operation("Taut", gravity=True, buckling={"n_modes": 2})
            model.validate()
            with self.assertRaisesRegex(ValueError, "unsupported on a nonlinear solve"):
                _export(model, "Taut", root)


def _free_node(model):
    for element in model.elements:
        return element.n2
    raise AssertionError("fixture has no elements")


class TestBucklingParsing(unittest.TestCase):
    def _write_factors(self, root, modes):
        (root / "study_buckling.json").write_text(
            json.dumps({"modes": modes}), encoding="utf-8"
        )

    def _write_modes(self, root, rows):
        header = "RESULTAT,NOM_CHAM,NUME_ORDRE,NOEUD,COOR_X,COOR_Y,COOR_Z,DX,DY,DZ,DRX,DRY,DRZ"
        body = [header]
        for mode, node, value in rows:
            body.append(
                f"MD_FLANB,DEPL,{mode},{node},0.0,0.0,0.0,"
                f"{value},0.0,0.0,0.0,0.0,0.0"
            )
        (root / "study_buckling_modes.csv").write_text(
            "\n".join(body) + "\n", encoding="utf-8"
        )

    def test_reads_factors_and_their_raw_eigenvalues(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [
                {"mode": 1, "critical_factor": 23.87, "raw_eigenvalue": -23.87},
                {"mode": 2, "critical_factor": 26.53, "raw_eigenvalue": -26.53},
            ])
            result = parse_buckling(root, {}, requested_modes=2)
            self.assertEqual(result.critical_factors, (23.87, 26.53))
            self.assertEqual(result.governing_factor, 23.87)
            self.assertEqual(result.governing_mode().mode, 1)
            # Solver order is preserved; the raw sign is kept for traceability.
            self.assertEqual(result.modes[0].raw_eigenvalue, -23.87)

    def test_reads_mode_shapes_and_maps_node_labels_back(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [
                {"mode": 1, "critical_factor": 1.5, "raw_eigenvalue": -1.5}
            ])
            self._write_modes(root, [(1, "GABC", 0.25), (1, "GDEF", -0.5)])
            result = parse_buckling(root, {"GABC": "N17", "GDEF": "N18"})
            shape = result.modes[0].node_displacements
            self.assertEqual(sorted(shape), ["N17", "N18"])
            self.assertAlmostEqual(shape["N17"][0], 0.25)
            self.assertAlmostEqual(shape["N18"][0], -0.5)

    def test_notes_a_shortfall_when_fewer_modes_come_back(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [
                {"mode": 1, "critical_factor": 2.0, "raw_eigenvalue": -2.0}
            ])
            result = parse_buckling(root, {}, requested_modes=6)
            self.assertTrue(any("of 6 requested" in note for note in result.notes))

    def test_an_empty_mode_list_is_a_real_answer_not_an_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [])
            result = parse_buckling(root, {})
            self.assertEqual(len(result), 0)
            self.assertIsNone(result.governing_factor)

    def test_a_missing_artifact_is_refused_not_read_as_stable(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "refusing to report an absent"):
                parse_buckling(root, {})

    def test_unreadable_json_is_refused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "study_buckling.json").write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "not readable JSON"):
                parse_buckling(root, {})

    def test_a_non_positive_factor_is_refused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [
                {"mode": 1, "critical_factor": 0.0, "raw_eigenvalue": -0.0}
            ])
            with self.assertRaisesRegex(RuntimeError, "non-physical critical factor"):
                parse_buckling(root, {})

    def test_a_non_finite_factor_is_refused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "study_buckling.json").write_text(
                json.dumps({"modes": [
                    {"mode": 1, "critical_factor": float("nan"), "raw_eigenvalue": -1.0}
                ]}),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                parse_buckling(root, {})

    def test_absent_mode_table_still_yields_the_factors(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_factors(root, [
                {"mode": 1, "critical_factor": 3.0, "raw_eigenvalue": -3.0}
            ])
            result = parse_buckling(root, {})
            self.assertEqual(result.critical_factors, (3.0,))
            self.assertEqual(result.modes[0].node_displacements, {})


class TestBucklingScriptRoundTrip(unittest.TestCase):
    """A generated script must rebuild the same model, including the analysis."""

    def _round_trip(self, model):
        from tuba.project.script import write_model_script

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "model.py"
            write_model_script(target, model, last_text=None)
            namespace: dict = {}
            exec(compile(target.read_text(encoding="utf-8"), str(target), "exec"), namespace)
            return namespace["model"]

    def test_an_operation_keeps_its_buckling_options(self):
        model, _ = _cantilever(buckling={"n_modes": 6, "modal_subspace": 11})
        rebuilt = self._round_trip(model)
        self.assertEqual(
            rebuilt.operations["Ref"].buckling,
            model.operations["Ref"].buckling,
        )
        self.assertEqual(rebuilt.to_dict(), model.to_dict())

    def test_a_load_case_keeps_its_buckling_options(self):
        model, _ = _cantilever()
        model.define_load_case("Sway", gravity=True, buckling={"n_modes": 3})
        rebuilt = self._round_trip(model)
        self.assertEqual(
            rebuilt.load_cases["Sway"].buckling.n_modes,
            model.load_cases["Sway"].buckling.n_modes,
        )
        self.assertEqual(rebuilt.to_dict(), model.to_dict())

    def test_a_plain_study_stays_plain(self):
        model, _ = _cantilever()
        rebuilt = self._round_trip(model)
        self.assertIsNone(rebuilt.operations["Ref"].buckling)


class TestBucklingResultTypes(unittest.TestCase):
    def test_round_trip(self):
        mode = BucklingMode(
            mode=1, critical_factor=2.5, raw_eigenvalue=-2.5,
            node_displacements={"N1": (0.1, 0.0, 0.0, 0.0, 0.0, 0.0)},
        )
        result = BucklingResult(modes=(mode,), requested_modes=4, notes=("a note",))
        restored = BucklingResult.from_dict(result.to_dict())
        self.assertEqual(restored, result)
        self.assertEqual(restored.governing_factor, 2.5)

    def test_governing_factor_is_the_smallest_not_the_first(self):
        modes = (
            BucklingMode(mode=1, critical_factor=30.0, raw_eigenvalue=-30.0),
            BucklingMode(mode=2, critical_factor=12.0, raw_eigenvalue=-12.0),
        )
        self.assertEqual(BucklingResult(modes=modes).governing_factor, 12.0)
        self.assertEqual(BucklingResult(modes=modes).governing_mode().mode, 2)

    def test_rejects_a_non_positive_factor(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            BucklingMode(mode=1, critical_factor=0.0, raw_eigenvalue=0.0)

    def test_rejects_duplicate_mode_numbers(self):
        mode = BucklingMode(mode=1, critical_factor=2.0, raw_eigenvalue=-2.0)
        with self.assertRaisesRegex(ValueError, "must be unique"):
            BucklingResult(modes=(mode, mode))

    def test_an_empty_result_is_falsy_and_has_no_governing_factor(self):
        empty = BucklingResult()
        self.assertFalse(empty)
        self.assertIsNone(empty.governing_factor)
        self.assertIsNone(empty.governing_mode())


class TestBucklingResultState(unittest.TestCase):
    def _state(self, buckling):
        return ResultState(
            id="result_state:Ref",
            study_id="analysis_study:Ref",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Ref",
            mesh_id=None,
            node_displacements={},
            node_reactions={},
            element_results={},
            buckling=buckling,
        )

    def test_absent_buckling_round_trips_as_absent(self):
        state = self._state(None)
        self.assertNotIn("buckling", state.to_dict())
        self.assertIsNone(ResultState.from_dict(state.to_dict()).buckling)

    def test_buckling_survives_a_dict_round_trip(self):
        mode = BucklingMode(mode=1, critical_factor=5.0, raw_eigenvalue=-5.0)
        state = self._state(BucklingResult(modes=(mode,), requested_modes=3))
        restored = ResultState.from_dict(state.to_dict())
        self.assertIsNotNone(restored.buckling)
        self.assertEqual(restored.buckling.critical_factors, (5.0,))
        self.assertEqual(restored.buckling.requested_modes, 3)

    def test_refuses_a_wrongly_typed_buckling(self):
        with self.assertRaisesRegex(ValueError, "must be a BucklingResult or None"):
            self._state({"modes": []})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
