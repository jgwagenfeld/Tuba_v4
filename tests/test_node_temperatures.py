import json
import re
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis import AnalysisMesh
from tuba.model import BendGeometry, OperationField
from tuba.reporting.tables import build_load_cases_table
from tuba.sampling import field_from_function
from tuba.schema import validate_model_dict
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization
from tuba.validation import ModelValidationError
from tuba.visualization import SceneRequest, build_visualization_scene


def _model(name: str = "NodeTemperatures") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route(name: str = "NodeTemperatures") -> Model:
    """pipe_str_0 runs N0 to N1 and pipe_str_1 runs N1 to N2, 1 m each along X, anchored at N0 and N2."""
    model = _model(name)
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


class TestNodeTemperatureAuthoring(unittest.TestCase):
    def test_node_ids_set_the_nodes_scope_and_round_trip(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        field_record = operating.add_field("temperature", 180.0, node_ids=["N1"])
        self.assertEqual(field_record.scope, "nodes")
        self.assertEqual(field_record.node_ids, ["N1"])
        model.validate()

        data = model.to_dict()
        validate_model_dict(data)
        self.assertEqual(
            data["operations"]["Operating"]["fields"],
            [{"quantity": "temperature", "value": 180.0, "scope": "nodes", "profile": "uniform", "node_ids": ["N1"]}],
        )
        restored = Model.from_dict(data)
        self.assertEqual(restored.operations["Operating"].fields[0].node_ids, ["N1"])
        self.assertEqual(restored.operations["Operating"].fields[0].scope, "nodes")
        restored.validate()

    def test_element_fields_keep_their_serialized_shape(self):
        element_field = OperationField("temperature", 120.0, scope="route", route_id="P-100")
        self.assertEqual(
            element_field.to_dict(),
            {"quantity": "temperature", "value": 120.0, "scope": "route", "profile": "uniform", "route_id": "P-100"},
        )

        node_field = OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"])
        self.assertEqual(node_field.to_dict()["node_ids"], ["N1"])

    def test_a_field_round_trips_through_its_canonical_payload(self):
        field_record = OperationField(
            "wind",
            500.0,
            direction=[0.0, 1.0, 0.0],
            scope="route",
            route_id="P-100",
            station_start=0.0,
            station_end=2.0,
            element_ids=["pipe_str_0"],
        )

        self.assertEqual(OperationField(**field_record.to_dict()), field_record)
        # Absent selectors stay absent, so the canonical payload is the compact one.
        self.assertEqual(
            OperationField("temperature", 120.0).to_dict(),
            {"quantity": "temperature", "value": 120.0, "scope": "all", "profile": "uniform"},
        )

    def test_report_rows_project_the_canonical_payload(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 180.0, node_ids=["N1"])

        table = build_load_cases_table(model)
        row = next(row for row in table.rows if row["load_case"] == "Operating")
        field_row = row["fields"][0]

        self.assertEqual(field_row["node_ids"], ["N1"])
        self.assertEqual(field_row["element_ids"], [])
        self.assertIsNone(field_row["direction"])
        self.assertEqual(field_row["quantity"], "temperature")

    def test_node_fields_take_only_uniform_temperatures_on_existing_nodes(self):
        cases = (
            ("pressure", 1.0e6, {"node_ids": ["N1"]}, "scopes 'pressure' to nodes; only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "profile": "linear"}, "only uniform temperature fields take node_ids"),
            ("temperature", 80.0, {"scope": "nodes"}, "has scope 'nodes' but no node_ids"),
            ("temperature", 80.0, {"node_ids": ["N1"], "route_id": "P-100"}, "lists node_ids but has scope 'route'"),
            (
                "temperature",
                80.0,
                {"node_ids": ["N1"], "station_start": 0.0},
                "takes no group, route_id, station range, element_ids or direction",
            ),
            ("temperature", 80.0, {"node_ids": ["N9"]}, r"references missing nodes \['N9'\]"),
        )
        for quantity, value, kwargs, message in cases:
            model = _two_element_route()
            model.define_operation("Operating", gravity=False).add_field(quantity, value, **kwargs)
            with self.subTest(message=message):
                with self.assertRaisesRegex(ModelValidationError, message):
                    model.validate()

    def test_node_temperatures_need_a_pipe_node(self):
        model = _model("RackNode")
        with model.pipe("PipeSec", "Steel", route="RACK") as rack:
            rack.start([0.0, 0.0, 0.0], support="anchor")
            rack.run(1.0)
            rack.beam(1.0)
            rack.end(support="anchor")
        # pipe_str_0 runs N0 to N1 and beam_0 runs N1 to N2, so N2 touches only the beam.
        model.define_operation("Operating", gravity=False).add_field("temperature", 80.0, node_ids=["N2"])
        with self.assertRaisesRegex(ModelValidationError, r"nodes on no pipe element: \['N2'\]"):
            model.validate()

    def test_node_temperatures_are_states(self):
        agreeing = _two_element_route()
        operating = agreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 150.0, node_ids=["N1", "N2"])
        agreeing.validate()

        disagreeing = _two_element_route()
        operating = disagreeing.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, node_ids=["N1"])
        with self.assertRaisesRegex(
            ModelValidationError, r"overlapping incompatible temperature fields on node 'N1': 150\.0 vs 90\.0"
        ):
            disagreeing.validate()

    def test_node_and_element_temperatures_may_not_meet_at_a_node(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N1"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        with self.assertRaisesRegex(
            ModelValidationError,
            r"gives nodes \['N1'\] a node temperature, but they belong to elements that "
            r"element temperature fields \[1\] cover; a node takes one or the other",
        ):
            model.validate()

        # N0 lies only on pipe_str_0, which no element field covers.
        apart = _two_element_route()
        operating = apart.define_operation("Operating", gravity=False)
        operating.add_field("temperature", 150.0, node_ids=["N0"])
        operating.add_field("temperature", 90.0, element_ids=["pipe_str_1"])
        apart.validate()


# Captured from main at e155b2d: what an element-temperature model exports before node temperatures exist.
TEMP_FIELD_TODAY = """TEMP_FIELD = CREA_CHAMP(
    TYPE_CHAM='NOEU_TEMP_R',
    OPERATION='AFFE',
    MODELE=MODELE,
    AFFE=(
        _F(
            TOUT='OUI',
            NOM_CMP='TEMP',
            VALE=6.000000E+01,
        ),
        _F(
            GROUP_MA='pipe_str_0',
            NOM_CMP='TEMP',
            VALE=9.000000E+01,
        ),
        _F(
            GROUP_MA='pipe_str_1',
            NOM_CMP='TEMP',
            VALE=1.000000E+02,
        ),
    ),
);
"""
TEMP_HOT_FIELD_TODAY = TEMP_FIELD_TODAY.replace("TEMP_FIELD = ", "TEMP_HOT_FIELD = ", 1)
TEMP_REF_FIELD_TODAY = """TEMP_REF_FIELD = CREA_CHAMP(
    TYPE_CHAM='NOEU_TEMP_R',
    OPERATION='AFFE',
    MAILLAGE=MAIL,
    AFFE=_F(
        TOUT='OUI',
        NOM_CMP='TEMP',
        VALE=2.000000E+01,
    ),
);
"""


def _export(model: Model, case: str, **solver_options) -> tuple[str, str]:
    with TemporaryDirectory() as tmpdir:
        CodeAsterSolver(work_dir=tmpdir, **solver_options).export_study(model, case, tmpdir)
        root = Path(tmpdir)
        return (root / "study.comm").read_text(encoding="utf-8"), (root / "study.mail").read_text(encoding="utf-8")


def _crea_champ(comm: str, name: str) -> str:
    start = comm.index(f"{name} = CREA_CHAMP(")
    return comm[start : comm.index(");\n", start) + len(");\n")]


def _group_no_lines(mail: str) -> list[str]:
    return [line for line in mail.splitlines() if line.startswith("GROUP_NO NOM=")]


def _node_rows(block: str) -> list[tuple[str, str]]:
    """(GROUP_NO name, VALE text) of each node row of a CREA_CHAMP block, in order."""
    return re.findall(r"GROUP_NO='([^']+)',\n\s+NOM_CMP='TEMP',\n\s+VALE=([^,]+),", block)


def _element_temperature_model(*, rest: bool) -> Model:
    model = _two_element_route("ElementTemperatures")
    if rest:
        model.add_support("N1", type="rest")
    operating = model.define_operation("Operating", gravity=False, temperature=60.0, ref_temperature=20.0)
    operating.add_field("temperature", 120.0, route_id="P-100", station_start=0.0, station_end=1.0, profile="linear")
    operating.add_field("temperature", 100.0, element_ids=["pipe_str_1"])
    return model


def _elbow_model() -> Model:
    """run: N0 (0, 0, 0) to N1 (4, 0, 0); elbow: 90 degrees, R 0.5, N1 to N2 (4.5, 0.5, 0); anchored at N0 and N2."""
    model = _model("NodeTemperatureElbow")
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([4.0, 0.0, 0.0])
    end = model.add_node([4.5, 0.5, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="PipeSec", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="PipeSec", material="Steel",
        bend_radius=0.5, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[4.0, 0.5, 0.0], normal=[0.0, 0.0, 1.0], radius=0.5, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model


class TestNodeTemperatureCompiler(unittest.TestCase):
    def test_models_without_node_temperatures_export_todays_text(self):
        comm, mail = _export(_element_temperature_model(rest=False), "Operating")
        self.assertEqual(_crea_champ(comm, "TEMP_FIELD"), TEMP_FIELD_TODAY)
        self.assertEqual(
            _group_no_lines(mail),
            ["GROUP_NO NOM=PipeOrientationNodes", "GROUP_NO NOM=GN_N0", "GROUP_NO NOM=GN_N2", "GROUP_NO NOM=AllSupports"],
        )

        # A rest support makes the case nonlinear: a uniform reference field, then the hot field.
        comm, mail = _export(_element_temperature_model(rest=True), "Operating")
        self.assertEqual(_crea_champ(comm, "TEMP_REF_FIELD"), TEMP_REF_FIELD_TODAY)
        self.assertEqual(_crea_champ(comm, "TEMP_HOT_FIELD"), TEMP_HOT_FIELD_TODAY)
        self.assertEqual(
            _group_no_lines(mail),
            [
                "GROUP_NO NOM=GROUND_2",  # the rest's contact-shoe helper node
                "GROUP_NO NOM=PipeOrientationNodes",
                "GROUP_NO NOM=GN_N0",
                "GROUP_NO NOM=GN_N1",
                "GROUP_NO NOM=GN_N2",
                "GROUP_NO NOM=AllSupports",
            ],
        )

    def test_node_temperatures_interpolate_along_subdivided_beam_pipes(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 100.0, node_ids=["N0"])
        operating.add_field("temperature", 180.0, node_ids=["N1"])

        comm, mail = _export(model, "Operating", pipe_modelization=PipeModelization.POU_D_T)

        # The operation temperature equals the reference, so only the node temperatures make this a thermal case.
        block = _crea_champ(comm, "TEMP_FIELD")
        self.assertIn("MODELE=MODELE,", block)
        self.assertNotIn("GROUP_MA=", block)
        # Eight SEG2 spans per straight: N0 (100) to N1 (180) in 10-degree steps. Then N1 back to N2, which
        # nothing covers, so N2 keeps the operation temperature (20).
        expected = [("GN_N0", 100.0)]
        expected += [(f"GN_pipe_str_0_n{k}", 100.0 + 10.0 * k) for k in range(1, 8)]
        expected += [("GN_N1", 180.0)]
        expected += [(f"GN_pipe_str_1_n{k}", 180.0 - 20.0 * k) for k in range(1, 8)]
        expected += [("GN_N2", 20.0)]
        self.assertEqual(_node_rows(block), [(name, f"{value:.6E}") for name, value in expected])
        for name, _ in expected:
            self.assertIn(f"GROUP_NO NOM={name}", mail)

    def test_node_temperatures_interpolate_along_tuyau_bend_segments_and_midsides(self):
        model = _elbow_model()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 40.0, node_ids=["N1"])
        operating.add_field("temperature", 200.0, node_ids=["N2"])

        comm, mail = _export(model, "Operating")

        # The run is touched through N1: N0 keeps the operation temperature, and the SEG3 midside sits halfway.
        expected = [("GN_N0", 20.0), ("GN_run_mid", 30.0), ("GN_N1", 40.0)]
        # Sixteen SEG3 segments along the elbow: 10 degrees per segment, each midside halfway between.
        for k in range(16):
            expected.append((f"GN_elbow_s{k}_mid", 45.0 + 10.0 * k))
            expected.append((f"GN_elbow_n{k + 1}" if k < 15 else "GN_N2", 50.0 + 10.0 * k))
        self.assertEqual(_node_rows(_crea_champ(comm, "TEMP_FIELD")), [(name, f"{value:.6E}") for name, value in expected])
        self.assertIn("GROUP_NO NOM=GN_elbow_s0_mid", mail)

    def test_written_values_follow_the_analysis_mesh_parametric_t(self):
        # The writer's fractions and the mesh's node_sources are two copies of one rule; this holds them together.
        for modelization in (PipeModelization.TUYAU_3M, PipeModelization.POU_D_T):
            model = _elbow_model()
            tip = model.add_node([4.5, 1.5, 0.0])
            model.add_element(id="beam", type="beam", n1="N2", n2=tip, section="PipeSec", material="Steel")
            operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
            # The beam's far end has no node temperature, so it keeps the operation's 20 degrees.
            ends = {"N0": 100.0, "N1": 180.0, "N2": 260.0, tip: 20.0}
            for node_id in ("N0", "N1", "N2"):
                operating.add_field("temperature", ends[node_id], node_ids=[node_id])

            with TemporaryDirectory() as tmpdir:
                solver = CodeAsterSolver(work_dir=tmpdir, pipe_modelization=modelization)
                root = Path(solver.export_analysis_study(model, "Operating", tmpdir).work_dir)
                manifest = json.loads((root / "study_manifest.json").read_text(encoding="utf-8"))
                names = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))["name_map"]
                comm = (root / "study.comm").read_text(encoding="utf-8")
            mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
            written = {name: float(value) for name, value in _node_rows(_crea_champ(comm, "TEMP_FIELD"))}

            with self.subTest(modelization=modelization.value):
                generated = {
                    node_id: source for node_id, source in mesh.node_sources.items() if source.source_ref.kind == "element"
                }
                self.assertEqual({source.source_ref.id for source in generated.values()}, {"run", "elbow", "beam"})
                for node_id, source in generated.items():
                    elem = model.get_element(source.source_ref.id)
                    t = source.parametric_t
                    name = names[f"GN_{node_id}"]
                    self.assertIn(name, written, f"{node_id} has no temperature row")
                    self.assertAlmostEqual(
                        written.pop(name), (1.0 - t) * ends[elem.n1] + t * ends[elem.n2], places=3, msg=node_id
                    )
                # What is left are the four end nodes, each at its own value.
                self.assertEqual(written, {names[f"GN_{node_id}"]: value for node_id, value in ends.items()})

    def test_an_uncovered_end_takes_the_value_its_neighbour_field_gives_it(self):
        model = _two_element_route()
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 60.0, node_ids=["N0"])
        operating.add_field("temperature", 140.0, element_ids=["pipe_str_1"])
        model.validate()

        comm, _ = _export(model, "Operating")

        block = _crea_champ(comm, "TEMP_FIELD")
        # pipe_str_1's field gives N1 140 degrees, so pipe_str_0 runs 60 to 140 with its midside at 100.
        self.assertEqual(
            _node_rows(block),
            [("GN_N0", "6.000000E+01"), ("GN_pipe_str_0_mid", "1.000000E+02"), ("GN_N1", "1.400000E+02")],
        )
        self.assertLess(block.index("GROUP_MA='pipe_str_1'"), block.index("GROUP_NO="))

    def test_nonlinear_cases_ramp_to_the_node_temperatures(self):
        model = _two_element_route()
        model.add_support("N1", type="rest")
        operating = model.define_operation("Operating", gravity=False, temperature=20.0, ref_temperature=20.0)
        operating.add_field("temperature", 120.0, node_ids=["N0"])

        comm, _ = _export(model, "Operating")

        self.assertEqual(_crea_champ(comm, "TEMP_REF_FIELD"), TEMP_REF_FIELD_TODAY)
        self.assertEqual(
            _node_rows(_crea_champ(comm, "TEMP_HOT_FIELD")),
            [("GN_N0", "1.200000E+02"), ("GN_pipe_str_0_mid", "7.000000E+01"), ("GN_N1", "2.000000E+01")],
        )

    def test_groups_serve_every_study_but_rows_only_their_own_case(self):
        model = _two_element_route()
        model.define_operation("Hot", gravity=False).add_field("temperature", 120.0, node_ids=["N0"])
        model.define_operation("Warm", gravity=False, temperature=60.0, ref_temperature=20.0)

        comm, mail = _export(model, "Warm")

        self.assertNotIn("GROUP_NO=", _crea_champ(comm, "TEMP_FIELD"))
        self.assertIn("GROUP_NO NOM=GN_pipe_str_0_mid", mail)

    def test_the_analysis_mesh_records_the_node_temperature_groups(self):
        model = _two_element_route()
        model.define_operation("Hot", gravity=False).add_field("temperature", 120.0, node_ids=["N0"])

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))

        mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
        self.assertEqual(tuple(mesh.groups["GN_pipe_str_0_mid"]), ("pipe_str_0_mid",))
        self.assertEqual(mesh.node_sources["pipe_str_0_mid"].parametric_t, 0.5)

    def test_only_support_and_nodal_force_groups_become_viewer_layers(self):
        # A whole-model node temperature gives every solver node a GN_ group, in every study of the model.
        model = _model("NodeTemperatureLayers")
        with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.run(1.0)
            pipe.run(1.0)
            pipe.run(1.0)
            pipe.end(support="anchor")
        hot = model.define_operation("Hot", gravity=False)
        field_from_function(model, hot, "temperature", lambda x, y, z: 20.0 + 50.0 * x)
        model.define_operation("Load", gravity=False).add_nodal_force("N1", force=[0.0, 0.0, -1000.0])

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Load", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))
        mesh = replace(AnalysisMesh.from_dict(manifest["analysis_mesh"]), solver_input_identity=None)
        self.assertIn("GN_N2", mesh.groups)
        self.assertIn("GN_pipe_str_0_mid", mesh.groups)

        scene = build_visualization_scene(SceneRequest(model, analysis_meshes=[mesh]))

        # The anchors at N0 and N3, and the Load operation's force at N1.
        self.assertEqual(
            sorted(layer.id for layer in scene.layers if layer.id.startswith("analysis_mesh:group:GN_")),
            ["analysis_mesh:group:GN_N0", "analysis_mesh:group:GN_N1", "analysis_mesh:group:GN_N3"],
        )
        midside = next(obj for obj in scene.objects if obj.id.endswith(":node:pipe_str_0_mid"))
        self.assertEqual(midside.group_ids, ["GN_pipe_str_0_mid"])
        self.assertEqual(midside.layer_ids, ["analysis_mesh:nodes"])

    def test_load_case_node_fields_are_checked_at_export(self):
        # Validation walks only operations, so export applies its node rules to load-case fields.
        cases = (
            ([OperationField("temperature", 120.0, scope="nodes", node_ids=["N9"])], r"field 0 references missing nodes \['N9'\]"),
            ([OperationField("temperature", 120.0, scope="nodes")], "field 0 has scope 'nodes' but no node_ids"),
            # N2 lies only on beam_0, and N3 on no element.
            (
                [OperationField("temperature", 120.0, scope="nodes", node_ids=["N2", "N3"])],
                r"field 0 gives a temperature to nodes on no pipe element: \['N2', 'N3'\]",
            ),
            (
                [OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"], element_ids=["pipe_str_0"])],
                "field 0 scopes to nodes, so it takes no group, route_id, station range, element_ids or direction",
            ),
            (
                [OperationField("temperature", 120.0, scope="route", route_id="RACK", node_ids=["N1"])],
                "field 0 lists node_ids but has scope 'route'",
            ),
            # Export resolves node temperatures before wind, so a node-scoped wind field is refused here.
            (
                [OperationField("wind", 500.0, scope="nodes", node_ids=["N1"], direction=[0.0, 1.0, 0.0])],
                "field 0 scopes 'wind' to nodes; only uniform temperature fields take node_ids",
            ),
            (
                [
                    OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"]),
                    OperationField("temperature", 90.0, scope="nodes", node_ids=["N1"]),
                ],
                r"has overlapping incompatible temperature fields on node 'N1': 120\.0 vs 90\.0",
            ),
            (
                [
                    OperationField("temperature", 120.0, scope="nodes", node_ids=["N1"]),
                    OperationField("temperature", 90.0, scope="elements", element_ids=["pipe_str_0"]),
                ],
                r"gives nodes \['N1'\] a node temperature, but they belong to elements that",
            ),
        )
        for fields, message in cases:
            model = _model("LoadCaseNodeFields")
            with model.pipe("PipeSec", "Steel", route="RACK") as rack:
                rack.start([0.0, 0.0, 0.0], support="anchor")
                rack.run(1.0)
                rack.beam(1.0)
                rack.end(support="anchor")
            model.add_node([5.0, 5.0, 0.0])
            model.define_load_case("Hot", gravity=False).fields.extend(fields)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                _export(model, "Hot")
