import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.validation import ModelValidationError
from tuba.solver.aster import CodeAsterSolver


def _model(name: str = "OperationFields") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route() -> Model:
    model = _model()
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


class TestOperationFields(unittest.TestCase):
    def test_builder_records_route_station_and_recipe_replays(self):
        model = _model("AuthoredRoute")
        with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.run(2.0)
            pipe.bend(radius=0.5, angle=90.0, plane="XY")
            pipe.run(1.0)
        recipe = pipe.recipe

        elements = model.elements
        self.assertEqual([element.route_id for element in elements], ["P-100", "P-100", "P-100"])
        self.assertAlmostEqual(elements[0].station_start, 0.0)
        self.assertAlmostEqual(elements[0].station_end, 2.0)
        self.assertAlmostEqual(elements[1].station_start, 2.0)
        self.assertAlmostEqual(elements[1].station_end, 2.0 + 0.5 * math.pi / 2.0)
        self.assertAlmostEqual(elements[2].station_start, elements[1].station_end)
        self.assertEqual(recipe.to_dict()["route_id"], "P-100")

        restored = type(recipe).from_dict(recipe.to_dict())
        regen = _model("RegeneratedRoute")
        built = restored.build(regen)

        replayed = [regen.get_element(element_id) for element_id in built.element_ids]
        self.assertEqual([element.route_id for element in replayed], ["P-100", "P-100", "P-100"])
        self.assertAlmostEqual(replayed[1].station_end, elements[1].station_end)

    def test_operation_field_roundtrip_and_backward_fixture(self):
        model = _two_element_route()
        operating = model.define_operation(
            "Operating",
            gravity=True,
            pressure=0.0,
            temperature=20.0,
            ref_temperature=20.0,
        )
        operating.add_field(
            "temperature",
            120.0,
            route_id="P-100",
            station_start=0.0,
            station_end=1.0,
        )

        restored = Model.from_dict(model.to_dict())
        field = restored.operations["Operating"].fields[0]
        self.assertEqual(field.quantity, "temperature")
        self.assertEqual(field.route_id, "P-100")
        self.assertAlmostEqual(field.station_end, 1.0)
        restored.validate()

        fixture = json.loads(Path("tests/fixtures/pre_operation_model.json").read_text(encoding="utf-8"))
        legacy = Model.from_dict(fixture)
        legacy.validate()
        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(legacy, "Hot", tmpdir)

    def test_overlapping_incompatible_fields_fail_validation(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 100.0, route_id="P-100")
        operating.add_field("temperature", 120.0, element_ids=[model.elements[0].id])

        with self.assertRaisesRegex(ModelValidationError, "overlapping incompatible"):
            model.validate()

    def test_local_pressure_and_temperature_fields_export_to_code_aster_groups(self):
        model = _two_element_route()
        operating = model.define_operation(
            "Operating",
            gravity=False,
            pressure=0.0,
            temperature=20.0,
            ref_temperature=20.0,
        )
        operating.add_field("pressure", 1.0e6, element_ids=["pipe_str_0"])
        operating.add_field("pressure", 2.0e6, element_ids=["pipe_str_1"])
        operating.add_field(
            "temperature",
            80.0,
            route_id="P-100",
            station_start=0.0,
            station_end=1.0,
        )
        operating.add_field(
            "temperature",
            120.0,
            route_id="P-100",
            station_start=1.0,
            station_end=2.0,
        )

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("PRESSURE = AFFE_CHAR_MECA(", comm)
        self.assertIn("FORCE_TUYAU=(", comm)
        self.assertIn("GROUP_MA='pipe_str_0'", comm)
        self.assertIn("GROUP_MA='pipe_str_1'", comm)
        self.assertIn("PRES=1.000000E+06", comm)
        self.assertIn("PRES=2.000000E+06", comm)
        self.assertIn("TEMP_FIELD = CREA_CHAMP(", comm)
        self.assertIn("MODELE=MODELE,", comm)
        self.assertIn("VALE=8.000000E+01", comm)
        self.assertIn("VALE=1.200000E+02", comm)

    def test_linear_temperature_field_exports_element_midpoint_values(self):
        model = _two_element_route()
        operating = model.define_operation(
            "Operating",
            gravity=False,
            pressure=0.0,
            temperature=20.0,
            ref_temperature=20.0,
        )
        operating.add_field(
            "temperature",
            120.0,
            route_id="P-100",
            station_start=0.0,
            station_end=2.0,
            profile="linear",
        )

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("TEMP_FIELD = CREA_CHAMP(", comm)
        self.assertIn("GROUP_MA='pipe_str_0'", comm)
        self.assertIn("GROUP_MA='pipe_str_1'", comm)
        self.assertIn("VALE=4.500000E+01", comm)
        self.assertIn("VALE=9.500000E+01", comm)

    def test_linear_pressure_field_exports_element_midpoint_values_without_overlapping_base_load(self):
        model = _two_element_route()
        operating = model.define_operation(
            "Operating",
            gravity=False,
            pressure=1.0e6,
            temperature=20.0,
            ref_temperature=20.0,
        )
        operating.add_field(
            "pressure",
            3.0e6,
            route_id="P-100",
            station_start=0.0,
            station_end=2.0,
            profile="linear",
        )

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        pressure = comm[comm.index("# ----- Internal pressure -----") : comm.index("# ----- Solve -----")]
        self.assertNotIn("GROUP_MA='AllPipes'", pressure)
        self.assertIn("GROUP_MA='pipe_str_0'", pressure)
        self.assertIn("PRES=1.500000E+06", pressure)
        self.assertIn("GROUP_MA='pipe_str_1'", pressure)
        self.assertIn("PRES=2.500000E+06", pressure)

    def test_local_pressure_override_partitions_default_elements_instead_of_stacking_loads(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False, pressure=1.0e6)
        operating.add_field("pressure", 2.0e6, element_ids=["pipe_str_1"])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        pressure = comm[comm.index("# ----- Internal pressure -----") : comm.index("# ----- Solve -----")]
        self.assertNotIn("GROUP_MA='AllPipes'", pressure)
        self.assertIn("GROUP_MA='pipe_str_0'", pressure)
        self.assertIn("PRES=1.000000E+06", pressure)
        self.assertIn("GROUP_MA='pipe_str_1'", pressure)
        self.assertIn("PRES=2.000000E+06", pressure)

    def test_wind_field_exports_for_beam_modelized_pipe_sections_only(self):
        model = _model("BeamPipeWind")
        with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.beam(2.0)
            pipe.end(support="anchor")
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, route_id="P-100", direction=[1.0, 0.0, 0.0])

        restored = Model.from_dict(model.to_dict())
        self.assertEqual(restored.operations["Operating"].fields[0].direction, [1.0, 0.0, 0.0])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(restored, "Operating", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("WIND = AFFE_CHAR_MECA_F(", comm)
        self.assertIn("FORCE_POUTRE=(", comm)
        self.assertIn("TYPE_CHARGE='VENT'", comm)
        self.assertIn("GROUP_MA='beam_0'", comm)
        self.assertIn("WFX_0 = FORMULE(", comm)
        self.assertIn("VALE='1.000000E+02'", comm)
        self.assertIn("FX=WFX_0", comm)
        self.assertIn("_F(CHARGE=WIND),", comm)
        self.assertNotIn("FORCE_NODALE", comm)
        self.assertNotIn("FORCE_TUYAU", comm)
        self.assertNotIn("SIEQ_ELNO", comm)

    def test_nodal_force_roundtrips_and_exports_force_nodale(self):
        model = _model("PointForce")
        model.add_rectangular_section("BoxSec", height_y=0.08, height_z=0.04, thickness_y=0.006, thickness_z=0.006)
        with model.pipe("BoxSec", "Steel") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.beam(2.0)
            pipe.end()
        load_case = model.define_load_case("PointLoad", gravity=False)
        load_case.add_nodal_force("N1", force=[0.0, 0.0, -500.0])

        restored = Model.from_dict(model.to_dict())
        self.assertEqual(restored.load_cases["PointLoad"].nodal_forces[0].components, [0.0, 0.0, -500.0, 0.0, 0.0, 0.0])

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(restored, "PointLoad", tmpdir)
            comm = (Path(tmpdir) / "study.comm").read_text(encoding="utf-8")
            mail = (Path(tmpdir) / "study.mail").read_text(encoding="utf-8")

        self.assertIn("POINT_FORCE = AFFE_CHAR_MECA(", comm)
        self.assertIn("FORCE_NODALE=(", comm)
        self.assertIn("GROUP_NO='GN_N1'", comm)
        self.assertIn("FZ=-5.00000000E+02", comm)
        self.assertIn("_F(CHARGE=POINT_FORCE),", comm)
        self.assertIn("GROUP_NO NOM=GN_N1", mail)

    def test_wind_field_rejects_tuyau_pipe_elements(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("wind", 1000.0, route_id="P-100", direction=[1.0, 0.0, 0.0])

        with self.assertRaisesRegex(ModelValidationError, "FORCE_POUTRE.*TUYAU_3M.*FORCE_NODALE"):
            model.validate()

    def test_piecewise_profile_fails_before_export(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", temperature=20.0, ref_temperature=20.0)
        operating.add_field("pressure", 1.0e6, route_id="P-100", profile="piecewise")

        with TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ModelValidationError, "piecewise"):
                CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)
            self.assertFalse((Path(tmpdir) / "study.comm").exists())


if __name__ == "__main__":
    unittest.main()
