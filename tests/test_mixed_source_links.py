"""Imported records retain function/call navigation without changing FEM identity."""

import json
import math

import pytest

from tuba import Model
from tuba.project import run_model_script
from tuba.visualization import SceneRequest, build_visualization_scene


def test_large_finite_quaternion_stays_valid_through_upload_and_asset():
    from tuba.mixed import CadAsset
    from tuba.visualization.preview.geometry import upload_options

    options = json.dumps({'id': 'part', 'unit_scale_to_m': .001,
                          'placement': {'rotation': [1e308, 1e308, 0, 0]}})
    placement = upload_options('part.stl', options)[-1]
    assert placement['rotation'] == pytest.approx([math.sqrt(.5), math.sqrt(.5), 0, 0])
    assert CadAsset('part', 'part.stl', placement=placement).placement['rotation'] == pytest.approx(placement['rotation'])


def test_mixed_records_link_repeated_function_calls_and_do_not_serialize_lines(tmp_path):
    source = '''from tuba import Model

def part(model, name, origin):
    model.add_cad_asset(id=name + '_asset', source_path='unused.step')
    model.add_imported_component(id=name, asset='cad_asset:' + name + '_asset', name=name)
    carrier = model.add_reference_point(name + '_reference', position=origin)
    model.add_shell_panel(name + '_panel', polygon=[[origin[0], 0, 0], [origin[0]+1, 0, 0], [origin[0], 1, 0]], thickness=0.01, material='Steel')
    model.add_rigid_patch(name + '_patch', reference=carrier, shell=name + '_panel', vertices=[0])

model = Model('Source links')
model.add_material('Steel', E=2.1e11, nu=0.3)
part(model, 'left', [0, 0, 0])
part(model, 'right', [2, 0, 0])
'''
    script = tmp_path / 'model.py'
    script.write_text(source)
    model = run_model_script(script)['model']
    left, right = (model.imported_components[name] for name in ('left', 'right'))
    assert left.source_line == right.source_line == 5
    assert (left.source_call_line, right.source_call_line) == (12, 13)
    assert model.couplings['left_patch'].source_line == 8
    assert model.analysis_regions['left_panel'].source_line == 7
    for records in (model.cad_assets, model.imported_components, model.ports,
                    model.analysis_regions, model.mesh_groups, model.couplings):
        for record in records.values():
            assert 'source_line' not in record.to_dict()
            assert 'source_call_line' not in record.to_dict()
    assert Model.from_dict(model.to_dict()).to_dict() == model.to_dict()
    # Scene linkage is a UI projection, independent of persisted solver inputs.
    scene = build_visualization_scene(SceneRequest(model))
    components = {str(obj.entity_ref): obj for obj in scene.objects if obj.kind == 'imported_component'}
    assert components['component:left'].metadata['source_line'] == 5
    assert components['component:right'].metadata['source_call_line'] == 13
