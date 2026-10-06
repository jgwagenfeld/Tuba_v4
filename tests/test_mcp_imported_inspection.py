"""Existing MCP inspection exposes imported engineering records and source links."""

import json

def test_inspect_model_reports_mixed_records_with_transient_source_links(tmp_path):
    import tuba.mcp.server as server

    script = tmp_path / "model.py"
    script.write_text(
        "from tuba import Model\n"
        "model = Model('Inspection')\n"
        "asset = model.add_cad_asset(id='equipment_asset', source_path='geometry/part.step')\n"
        "component = model.add_imported_component(id='equipment', asset='cad_asset:equipment_asset', name='Equipment')\n"
        "port = model.add_port(id='inlet', owner='component:equipment', kind='circular_face', position=[0,0,0], axis=[1,0,0], radius=.05)\n"
        "region = model.add_analysis_region(id='solid', owner='component:equipment', role='solid_3d', code_aster_modelisation='3D', material='Steel', mesh_group='G_SOLID')\n"
        "reference = model.add_node([0,0,0])\n"
        "coupling = model.add_coupling(id='inlet_link', kind='rigid_patch', source='port:inlet', source_node='node:N0', target='component:equipment', code_aster_keyword='LIAISON_SOLIDE', code_aster_option='')\n"
    )
    server.init_session(file_path=str(script))
    info = server.inspect_model()
    model = server.get_active_model()
    for collection, identity in (("cad_assets", "equipment_asset"), ("imported_components", "equipment"),
                                 ("ports", "inlet"), ("analysis_regions", "solid"), ("couplings", "inlet_link")):
        record = getattr(model, collection)[identity]
        assert info[collection][identity]["source_line"] == record.source_line
        assert record.source_line is not None
        assert "source_line" not in record.to_dict()
    assert info["ports"]["inlet"]["status"] == "detected"
    assert info["couplings"]["inlet_link"]["code_aster_keyword"] == "LIAISON_SOLIDE"
    json.dumps(info, allow_nan=False)
