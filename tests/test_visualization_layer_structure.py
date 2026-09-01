"""Layer taxonomy, mesh identity, applied loads, and the result-field catalogue."""

import re
import unittest

from tests.realtime_visualization_fixtures import operating_state_review_fixture
from tests.reporting_fixtures import build_review_model
from tuba.analysis import AnalysisMesh
from tuba.analysis.mesh import modelisation_info
from tuba.model import Support
from tuba.solver.modelisation import (
    discrete_support_group,
    modelisation_assignments,
    needs_discrete_element,
)
from tuba.visualization import build_visualization_scene
from tuba.visualization.builders._layers import (
    OBJECT_KIND_CATEGORY,
    OVERLAY_KIND_CATEGORY,
    build_layer_registry,
    build_result_fields,
    mesh_identity,
)
from tuba.visualization.scene import (
    LAYER_CATEGORIES,
    Overlay,
    ResultField,
    SceneLayer,
    SceneObject,
    SceneValidationError,
    VisualizationScene,
)
import tempfile
from pathlib import Path


class TestModelisationIsNotDuplicated(unittest.TestCase):
    """The .comm and the AnalysisMesh must not drift on MODELISATION."""

    def _model_with_every_element_family(self):
        model = build_review_model()
        # A discrete spring and a lumped mass both force POI1/DIS_TR entries,
        # which is where the two emitters used to be able to disagree.
        model.supports.append(Support(node="N0", type="spring", stiffness=1.0e6, direction=[0.0, 0.0, 1.0]))
        model.supports.append(Support(node="N1", type="rest", mass=25.0))
        return model

    def test_affe_modele_matches_the_shared_assignment(self):
        model = self._model_with_every_element_family()
        assignments = modelisation_assignments(model)

        solver = _code_aster_solver()
        with tempfile.TemporaryDirectory() as tmp:
            comm_path = Path(tmp) / "study.comm"
            solver._write_comm(model, next(iter(model.load_cases.values())), comm_path)
            comm = comm_path.read_text(encoding="utf8")

        affe_modele = comm.split("AFFE_MODELE(", 1)[1].split(");", 1)[0]
        emitted = dict(
            zip(
                re.findall(r"GROUP_MA='([^']+)'", affe_modele),
                re.findall(r"MODELISATION='([^']+)'", affe_modele),
            )
        )
        self.assertEqual(emitted, assignments)

    def test_analysis_mesh_records_the_same_assignment(self):
        model = self._model_with_every_element_family()
        solver = _code_aster_solver()
        with tempfile.TemporaryDirectory() as tmp:
            mesh = solver._write_mail(model, Path(tmp) / "study.mail", analysis_mesh_id="mesh:test")
        self.assertEqual(mesh.modelisations, modelisation_assignments(model))

    def test_discrete_supports_use_one_predicate(self):
        spring = Support(node="N9", type="spring", stiffness=1.0e6)
        massive = Support(node="N8", type="rest", mass=10.0)
        plain = Support(node="N7", type="guide")
        self.assertTrue(needs_discrete_element(spring))
        self.assertTrue(needs_discrete_element(massive))
        self.assertFalse(needs_discrete_element(plain))
        self.assertEqual(discrete_support_group("N9"), "DIS_N9")


class TestMeshIdentity(unittest.TestCase):
    def test_tuyau_is_a_1d_mesh_with_subpoint_recovery(self):
        self.assertEqual(modelisation_info("TUYAU_3M"), (1, "subpoint"))
        self.assertEqual(modelisation_info("POU_D_T"), (1, "cell"))
        self.assertEqual(modelisation_info("3D"), (3, "gauss"))

    def test_unknown_modelisation_does_not_raise(self):
        self.assertEqual(modelisation_info("SOMETHING_NEW"), (-1, "unknown"))

    def test_identity_orders_modelisations_by_element_count(self):
        mesh = AnalysisMesh(
            id="m",
            model_revision=1,
            solver_name="Code_Aster",
            nodes={"N0": (0.0, 0.0, 0.0), "N1": (1.0, 0.0, 0.0)},
            elements={"e0": ("N0", "N1"), "e1": ("N0", "N1"), "e2": ("N0", "N1")},
            groups={"AllPipes": ("e0", "e1"), "G_TUBE": ("e2",)},
            node_sources={},
            element_sources={},
            modelisations={"G_TUBE": "POU_D_T", "AllPipes": "TUYAU_3M"},
        )
        identity = mesh_identity(mesh)
        self.assertEqual(
            [entry["modelisation"] for entry in identity["modelisations"]],
            ["TUYAU_3M", "POU_D_T"],
        )
        self.assertEqual(identity["topological_dim"], 1)

    def test_modelisations_round_trip_and_default_empty(self):
        mesh = AnalysisMesh(
            id="m",
            model_revision=1,
            solver_name="Code_Aster",
            nodes={"N0": (0.0, 0.0, 0.0)},
            elements={},
            groups={},
            node_sources={},
            element_sources={},
            modelisations={"AllPipes": "TUYAU_3M"},
        )
        self.assertEqual(AnalysisMesh.from_dict(mesh.to_dict()), mesh)

        legacy = mesh.to_dict()
        del legacy["modelisations"]
        self.assertEqual(AnalysisMesh.from_dict(legacy).modelisations, {})


class TestAppliedLoads(unittest.TestCase):
    def setUp(self):
        self.scene = build_visualization_scene(build_review_model())
        self.loads = [obj for obj in self.scene.objects if obj.kind == "applied_load"]

    def test_forces_and_moments_are_separate_glyphs(self):
        kinds = sorted(obj.metadata["vector_kind"] for obj in self.loads)
        self.assertEqual(kinds, ["force", "moment"])
        units = {obj.metadata["vector_kind"]: obj.metadata["unit"] for obj in self.loads}
        self.assertEqual(units, {"force": "N", "moment": "N*m"})

    def test_loads_are_tagged_with_their_load_case(self):
        for obj in self.loads:
            self.assertIn(obj.metadata["load_case"], self.scene_load_cases())

    def test_applied_force_and_moment_glyphs_use_authored_input_colours(self):
        assets = {asset.id: asset for asset in self.scene.geometry_assets}
        colours = {
            obj.metadata["vector_kind"]: assets[obj.geometry_asset_id].generation_config["color"]
            for obj in self.loads
        }
        self.assertEqual(colours, {"force": "#2563eb", "moment": "#0f766e"})

    def test_load_case_overlay_carries_the_definition(self):
        overlays = [o for o in self.scene.overlays if o.kind == "load_case"]
        self.assertTrue(overlays)
        data = overlays[0].data
        for key in ("gravity", "internal_pressure_pa", "temperature_c", "ref_temperature_c"):
            self.assertIn(key, data)

    def test_load_case_overlay_carries_resolved_pressure_inputs(self):
        model = build_review_model()
        operation = model.define_operation("LinearPressure", gravity=False, pressure=1.0e6)
        operation.add_field(
            "pressure",
            3.0e6,
            route_id="R-100",
            station_start=0.0,
            station_end=5.0,
            profile="linear",
        )

        scene = build_visualization_scene(model)
        overlay = next(item for item in scene.overlays if item.id == "overlay:load_case:LinearPressure")

        self.assertEqual(
            overlay.data["pressure_fields"],
            [
                {"element_ids": ["E-20"], "pressure_pa": 2.0e6},
                {"element_ids": ["E-10"], "pressure_pa": 1.0e6},
            ],
        )
        self.assertEqual(overlay.data["pressure_source"], "authored_input")

    def test_loads_can_be_excluded(self):
        from tuba.visualization import SceneBuildOptions

        scene = build_visualization_scene(build_review_model(), options=SceneBuildOptions(include_loads=False))
        self.assertEqual([obj for obj in scene.objects if obj.kind == "applied_load"], [])

    def scene_load_cases(self):
        return {o.data["load_case"] for o in self.scene.overlays if o.kind == "load_case"}


class TestLayerRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        fixture = operating_state_review_fixture(Path(self._tmp.name))
        self.scene = build_visualization_scene(
            fixture.model,
            result_states=[fixture.result_state],
            geometry_states=[fixture.operating_state, fixture.visual_state, fixture.cold_state],
            analysis_meshes=[fixture.analysis_mesh],
            operating_clash_results=fixture.operating_clashes,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _ids(self, category):
        return {layer.id for layer in self.scene.layers if layer.category == category}

    def test_every_category_is_populated(self):
        for category in LAYER_CATEGORIES:
            self.assertTrue(self._ids(category), f"no layers in category {category}")

    def test_layers_land_in_the_right_category(self):
        self.assertIn("pipe", self._ids("design"))
        self.assertIn("support", self._ids("design"))
        self.assertEqual(next(layer for layer in self.scene.layers if layer.id == "support").label, "Supports / constraints")
        self.assertIn("analysis_mesh:nodes", self._ids("analysis_mesh"))
        self.assertIn("result:displacement", self._ids("results"))
        self.assertIn("overlay:clash", self._ids("annotations"))

    def test_analytical_envelopes_start_hidden_while_real_geometry_stays_visible(self):
        layers, _ = build_layer_registry(
            [
                SceneObject(id="object:pipe", kind="pipe"),
                SceneObject(
                    id="object:clearance",
                    kind="physical_envelope",
                    layer_ids=["physical_envelope:clearance"],
                ),
            ],
            [],
            [],
        )
        by_id = {layer.id: layer for layer in layers}

        self.assertTrue(by_id["pipe"].default_visible)
        self.assertFalse(by_id["physical_envelope:clearance"].default_visible)

    def test_nothing_is_unclassified(self):
        unclassified = [d for d in self.scene.diagnostics if d.code == "visualization.layer.unclassified"]
        self.assertEqual(unclassified, [], f"unclassified kinds: {[d.message for d in unclassified]}")

    def test_mesh_identity_layer_describes_the_mesh(self):
        identity_layers = [layer for layer in self.scene.layers if layer.extra.get("mesh_identity")]
        self.assertTrue(identity_layers)
        badge = identity_layers[0].label
        self.assertIn("1D", badge)
        self.assertIn("TUYAU_3M", badge)
        self.assertIn("subpoint", badge)

    def test_taxonomy_tables_only_use_known_categories(self):
        for table in (OBJECT_KIND_CATEGORY, OVERLAY_KIND_CATEGORY):
            for kind, category in table.items():
                self.assertIn(category, LAYER_CATEGORIES, f"{kind} -> {category}")


class TestResultFieldCatalogue(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        fixture = operating_state_review_fixture(Path(self._tmp.name))
        self.scene = build_visualization_scene(
            fixture.model,
            result_states=[fixture.result_state],
            analysis_meshes=[fixture.analysis_mesh],
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_field_points_at_a_real_overlay(self):
        overlay_ids = {overlay.id for overlay in self.scene.overlays}
        self.assertTrue(self.scene.result_fields)
        for result_field in self.scene.result_fields:
            self.assertIn(result_field.overlay_id, overlay_ids)

    def test_vectors_offer_components_and_scalars_do_not(self):
        by_support = {f.label: f for f in self.scene.result_fields}
        vectors = [f for f in self.scene.result_fields if f.components != ("magnitude",)]
        scalars = [f for f in self.scene.result_fields if f.components == ("magnitude",)]
        self.assertTrue(vectors, f"expected vector fields among {list(by_support)}")
        self.assertTrue(scalars, f"expected scalar fields among {list(by_support)}")
        for result_field in vectors:
            self.assertEqual(result_field.components, ("DX", "DY", "DZ", "magnitude"))
            self.assertEqual(result_field.support, "node")

    def test_declared_range_matches_the_overlay_values(self):
        overlays = {overlay.id: overlay for overlay in self.scene.overlays}
        for result_field in self.scene.result_fields:
            values = overlays[result_field.overlay_id].data.get("values", {})
            numeric = [v for v in values.values() if isinstance(v, (int, float))]
            if numeric and result_field.range:
                self.assertLessEqual(result_field.range[0], min(numeric))
                self.assertGreaterEqual(result_field.range[1], max(numeric))

    def test_overlay_without_values_yields_no_field(self):
        empty = Overlay(id="overlay:solver_result:empty", kind="solver_result", data={"result_type": "stress"})
        self.assertEqual(build_result_fields([empty]), [])

    def test_compliance_role_survives_into_the_field(self):
        overlay = Overlay(
            id="overlay:solver_result:tuyau",
            kind="solver_result",
            data={
                "result_type": "tuyau_subpoints",
                "values": {"o1": 1.0},
                "compliance_role": "visualization_only_not_asme_code_stress",
            },
        )
        field = build_result_fields([overlay])[0]
        self.assertEqual(field.compliance_role, "visualization_only_not_asme_code_stress")
        self.assertEqual(field.support, "subpoint")


class TestSceneValidation(unittest.TestCase):
    def test_unknown_layer_category_is_rejected(self):
        scene = VisualizationScene(
            scene_id="s",
            model_id="m",
            layers=[SceneLayer(id="l", category="not_a_category", label="L")],
        )
        with self.assertRaises(SceneValidationError):
            scene.validate()

    def test_field_pointing_at_a_missing_overlay_is_rejected(self):
        scene = VisualizationScene(
            scene_id="s",
            model_id="m",
            result_fields=[
                ResultField(id="f", label="F", load_case="c", result_state_id="r", overlay_id="overlay:gone")
            ],
        )
        with self.assertRaises(SceneValidationError):
            scene.validate()

    def test_legacy_payload_without_layers_still_loads(self):
        scene = VisualizationScene(scene_id="s", model_id="m")
        payload = scene.to_dict()
        del payload["layers"]
        del payload["result_fields"]
        restored = VisualizationScene.from_dict(payload)
        restored.validate()
        self.assertEqual(restored.layers, [])
        self.assertEqual(restored.result_fields, [])


def _code_aster_solver():
    from tuba.solver.aster import CodeAsterSolver

    return CodeAsterSolver()


if __name__ == "__main__":
    unittest.main()
