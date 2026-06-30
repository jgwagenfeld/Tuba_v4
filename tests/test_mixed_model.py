import unittest

from tuba import Model
from tuba.refs import EntityRef, resolve_entity_ref
from tuba.schema import SchemaValidationError, validate_model_dict
from tuba.validation import ModelValidationError


class TestMixedModelRecords(unittest.TestCase):
    def _build_pipe_to_port_model(self, *, port_radius: float = 0.05, port_status: str = "confirmed"):
        model = Model(project_name="PipePortCoupling")
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

        model.add_cad_asset(
            id="cad_asset_0",
            source_path="equipment.step",
            source_format="STEP",
            unit_scale_to_m=0.001,
            placement={
                "origin": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
            content_digest="sha256:test",
            importer="gmsh-occ",
        )
        model.add_imported_component(
            id="component_pump_body",
            asset="cad_asset:cad_asset_0",
            name="Pump body",
            role="equipment",
            status="reviewed",
        )
        model.add_analysis_region(
            id="region_pump_solid",
            owner="component:component_pump_body",
            role="solid_3d",
            code_aster_modelisation="3D",
            material="Steel",
            mesh_group="G_PUMP_SOLID",
            element_order=2,
            status="reviewed",
        )
        model.add_port(
            id="port_pump_nozzle_a",
            owner="component:component_pump_body",
            kind="circular_face",
            position=[1.0, 0.0, 0.0],
            axis=[1.0, 0.0, 0.0],
            radius=port_radius,
            face_group="G_PORT_FACE",
            edge_group="G_PORT_EDGE",
            status=port_status,
        )

        return model

    def test_connect_pipe_to_confirmed_solid_port(self):
        model = self._build_pipe_to_port_model()
        coupling = model.connect_pipe_to_port(
            pipe="element:pipe_0",
            node="node:N1",
            port="port:port_pump_nozzle_a",
            method="3D_TUYAU",
            id="coupling_pipe_to_pump_a",
        )

        self.assertEqual(coupling.code_aster_keyword, "LIAISON_ELEM")
        self.assertEqual(coupling.code_aster_option, "3D_TUYAU")
        self.assertEqual(coupling.source, EntityRef("element", "pipe_0"))
        self.assertEqual(coupling.source_node, EntityRef("node", "N1"))
        self.assertEqual(coupling.target, EntityRef("port", "port_pump_nozzle_a"))

        data = model.to_dict()
        self.assertEqual(data["couplings"]["coupling_pipe_to_pump_a"]["source"], "element:pipe_0")
        self.assertEqual(data["couplings"]["coupling_pipe_to_pump_a"]["source_node"], "node:N1")
        self.assertEqual(data["couplings"]["coupling_pipe_to_pump_a"]["target"], "port:port_pump_nozzle_a")

        model.validate()

    def test_unconfirmed_port_blocks_validation(self):
        model = self._build_pipe_to_port_model(port_status="detected")
        model.connect_pipe_to_port(
            pipe="element:pipe_0",
            node="node:N1",
            port="port:port_pump_nozzle_a",
            method="3D_TUYAU",
            id="coupling_pipe_to_pump_a",
        )

        with self.assertRaisesRegex(ModelValidationError, "is not confirmed"):
            model.validate()

    def test_pipe_radius_mismatch_blocks_connection(self):
        model = self._build_pipe_to_port_model(port_radius=0.08)
        with self.assertRaisesRegex(ValueError, "diameter"):
            model.connect_pipe_to_port(
                pipe="element:pipe_0",
                node="node:N1",
                port="port:port_pump_nozzle_a",
                method="3D_TUYAU",
                id="coupling_pipe_to_pump_a",
            )

    def test_beam_element_is_not_valid_for_3d_tuyau_connection(self):
        model = self._build_pipe_to_port_model()
        model.elements[0].type = "beam"

        with self.assertRaisesRegex(ValueError, "not valid for pipe-port coupling"):
            model.connect_pipe_to_port(
                pipe="element:pipe_0",
                node="node:N1",
                port="port:port_pump_nozzle_a",
                method="3D_TUYAU",
                id="coupling_pipe_to_pump_a",
            )

    def test_invalid_imported_coupling_option_blocks_validation(self):
        model = self._build_pipe_to_port_model()
        model.add_coupling(
            id="coupling_pipe_to_pump_a",
            kind="pipe_to_solid_port",
            source="element:pipe_0",
            source_node="node:N1",
            target="port:port_pump_nozzle_a",
            code_aster_keyword="LIAISON_ELEM",
            code_aster_option="INVALID_OPTION",
        )

        with self.assertRaisesRegex(ModelValidationError, "unsupported pipe-to-port option"):
            model.validate()

    def test_imported_pipe_port_diameter_mismatch_blocks_validation(self):
        model = self._build_pipe_to_port_model(port_radius=0.08)
        model.add_coupling(
            id="coupling_pipe_to_pump_a",
            kind="pipe_to_solid_port",
            source="element:pipe_0",
            source_node="node:N1",
            target="port:port_pump_nozzle_a",
            code_aster_keyword="LIAISON_ELEM",
            code_aster_option="3D_TUYAU",
        )

        with self.assertRaisesRegex(ModelValidationError, "diameter mismatch"):
            model.validate()

    def test_mixed_records_roundtrip_and_resolve_refs(self):
        model = Model(project_name="MixedRecords")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        asset = model.add_cad_asset(
            id="cad_asset_0",
            source_path="equipment.step",
            source_format="STEP",
            unit_scale_to_m=0.001,
            placement={
                "origin": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
            content_digest="sha256:test",
            importer="gmsh-occ",
        )
        component = model.add_imported_component(
            id="component_pump_body",
            asset="cad_asset:cad_asset_0",
            name="Pump body",
            role="equipment",
            status="reviewed",
        )
        region = model.add_analysis_region(
            id="region_pump_solid",
            owner="component:component_pump_body",
            role="solid_3d",
            code_aster_modelisation="3D",
            material="Steel",
            mesh_group="G_PUMP_SOLID",
            element_order=2,
            status="reviewed",
        )
        port = model.add_port(
            id="port_pump_nozzle_a",
            owner="component:component_pump_body",
            kind="circular_face",
            position=[1.0, 0.0, 0.0],
            axis=[1.0, 0.0, 0.0],
            radius=0.05,
            face_group="G_PORT_FACE",
            edge_group="G_PORT_EDGE",
            status="confirmed",
        )
        mesh_group = model.add_mesh_group(
            id="mesh_group_port_face",
            owner="port:port_pump_nozzle_a",
            solver_name="G_PORT_FACE",
            dimension=2,
            members=["face:42"],
        )
        coupling = model.add_coupling(
            id="coupling_pipe_to_pump_a",
            kind="pipe_to_solid_port",
            source="element:pipe_0",
            source_node="node:N1",
            target="port:port_pump_nozzle_a",
            code_aster_keyword="LIAISON_ELEM",
            code_aster_option="3D_TUYAU",
        )

        data = model.to_dict()
        validate_model_dict(data)
        self.assertEqual(data["cad_assets"]["cad_asset_0"]["source_path"], "equipment.step")
        self.assertEqual(data["imported_components"]["component_pump_body"]["asset"], "cad_asset:cad_asset_0")
        self.assertEqual(data["analysis_regions"]["region_pump_solid"]["mesh_group"], "G_PUMP_SOLID")
        self.assertEqual(data["ports"]["port_pump_nozzle_a"]["status"], "confirmed")
        self.assertEqual(data["mesh_groups"]["mesh_group_port_face"]["members"], ["face:42"])
        self.assertEqual(data["couplings"]["coupling_pipe_to_pump_a"]["code_aster_option"], "3D_TUYAU")

        loaded = Model.from_dict(data)
        self.assertEqual(loaded.cad_assets["cad_asset_0"], asset)
        self.assertEqual(loaded.imported_components["component_pump_body"], component)
        self.assertEqual(loaded.analysis_regions["region_pump_solid"], region)
        self.assertEqual(loaded.ports["port_pump_nozzle_a"], port)
        self.assertEqual(loaded.mesh_groups["mesh_group_port_face"], mesh_group)
        self.assertEqual(loaded.couplings["coupling_pipe_to_pump_a"], coupling)
        self.assertIs(resolve_entity_ref(loaded, EntityRef("cad_asset", "cad_asset_0")), loaded.cad_assets["cad_asset_0"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("component", "component_pump_body")), loaded.imported_components["component_pump_body"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("analysis_region", "region_pump_solid")), loaded.analysis_regions["region_pump_solid"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("port", "port_pump_nozzle_a")), loaded.ports["port_pump_nozzle_a"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("mesh_group", "mesh_group_port_face")), loaded.mesh_groups["mesh_group_port_face"])
        self.assertIs(resolve_entity_ref(loaded, EntityRef("coupling", "coupling_pipe_to_pump_a")), loaded.couplings["coupling_pipe_to_pump_a"])

    def test_mixed_schema_rejects_malformed_records(self):
        model = Model(project_name="MixedSchema")
        data = model.to_dict()
        data["cad_assets"] = {
            "cad_asset_0": {
                "id": "cad_asset_0",
            }
        }

        with self.assertRaisesRegex(SchemaValidationError, "source_path"):
            validate_model_dict(data)

    def test_mixed_schema_rejects_unknown_ref_kind(self):
        model = Model(project_name="MixedSchemaRefs")
        data = model.to_dict()
        data["cad_assets"] = {
            "cad_asset_0": {
                "id": "cad_asset_0",
                "source_path": "equipment.step",
            }
        }
        data["imported_components"] = {
            "component_pump_body": {
                "id": "component_pump_body",
                "asset": "unknown_kind:cad_asset_0",
            }
        }

        with self.assertRaisesRegex(SchemaValidationError, "imported_components"):
            validate_model_dict(data)

    def test_old_model_payload_without_mixed_records_still_loads(self):
        model = Model(project_name="OldShape")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        data = model.to_dict()
        data.pop("cad_assets", None)
        data.pop("imported_components", None)
        data.pop("analysis_regions", None)
        data.pop("ports", None)
        data.pop("mesh_groups", None)
        data.pop("couplings", None)

        loaded = Model.from_dict(data)

        self.assertEqual(loaded.cad_assets, {})
        self.assertEqual(loaded.imported_components, {})
        self.assertEqual(loaded.analysis_regions, {})
        self.assertEqual(loaded.ports, {})
        self.assertEqual(loaded.mesh_groups, {})
        self.assertEqual(loaded.couplings, {})


if __name__ == "__main__":
    unittest.main()
