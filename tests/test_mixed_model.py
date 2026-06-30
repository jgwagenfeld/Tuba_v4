import unittest

from tuba import Model
from tuba.refs import EntityRef, resolve_entity_ref
from tuba.schema import SchemaValidationError, validate_model_dict


class TestMixedModelRecords(unittest.TestCase):
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
