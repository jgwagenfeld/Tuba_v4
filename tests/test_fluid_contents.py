import math
import pytest
from tuba import Model
from tuba.model import OperationField
from tuba.physical import physical_properties_for_element, element_quantities
from tuba.quantities import quantity_takeoff


def contents_model(*, bent=False, insulated=True):
    model = Model('FluidContents')
    model.add_material('Steel', E=2e11, nu=0.3, rho=7850)
    model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
    with model.pipe('Pipe', 'Steel', route='P-100') as pipe:
        pipe.start([0, 0, 0], support='anchor')
        pipe.run(2.0)
        if bent:
            pipe.bend(radius=0.5, angle=90, plane='XY')
            pipe.run(1.0)
    if insulated:
        model.add_insulation_spec('wool', material='mineral wool',
                                  thickness_m=0.02, density_kg_m3=100)
        for element in model.elements:
            model.assign_insulation(f'element:{element.id}', 'wool')
    return model


@pytest.mark.parametrize('bent', [False, True])
@pytest.mark.parametrize('density', [0.0, 800.0, 1000.0])
def test_contents_mass_is_independent_and_dry_default_is_preserved(bent, density):
    model = contents_model(bent=bent)
    model.define_operation('Filled', gravity=False).add_field(
        'fluid_density', density, route_id='P-100')
    length = 3 + math.pi / 4 if bent else 2.0
    pipe_mass = math.pi / 4 * (0.1**2 - 0.08**2) * 7850 * length
    insulation_mass = math.pi / 4 * (0.14**2 - 0.1**2) * 100 * length
    fluid_mass = math.pi / 4 * 0.08**2 * density * length
    wet = quantity_takeoff(model, operation='Filled')
    dry = quantity_takeoff(model)
    for key, expected in [('pipe_mass_kg', pipe_mass),
                          ('insulation_mass_kg', insulation_mass),
                          ('fluid_mass_kg', fluid_mass),
                          ('total_mass_kg', pipe_mass + insulation_mass + fluid_mass)]:
        assert wet.totals[key] == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert dry.totals['fluid_mass_kg'] == 0
    assert 'operation' not in dry.to_dict()
    assert wet.to_dict()['operation'] == 'Filled'
    for element in model.elements:
        before = physical_properties_for_element(model, element)
        after = physical_properties_for_element(model, element, operation='Filled')
        assert after.metal_area_m2 == before.metal_area_m2
        assert after.wind_diameter_m == before.wind_diameter_m
        assert after.effective_radius_m == before.effective_radius_m
        assert after.fluid_density_kg_m3 == density
        assert element_quantities(model, element, operation='Filled').fluid_mass_kg >= 0


@pytest.mark.parametrize('value', [True, False, '800', None, 1+0j,
                                  -1, float('nan'), float('inf')])
def test_invalid_density_is_not_coerced(value):
    model = contents_model()
    operation = model.define_operation('Bad')
    with pytest.raises(ValueError, match='fluid_density'):
        operation.add_field('fluid_density', value)
    operation.fields[:] = [OperationField(quantity='fluid_density', value=value)]
    with pytest.raises(ValueError, match='fluid_density'):
        model.validate()
    with pytest.raises(ValueError, match='fluid_density'):
        quantity_takeoff(model, operation='Bad')


def test_equal_overlaps_apply_once_and_conflicts_fail_without_gravity():
    model = contents_model()
    case = model.define_operation('Filled', gravity=False)
    case.add_field('fluid_density', 800, route_id='P-100')
    duplicate = case.add_field('fluid_density', 800,
                               element_ids=[model.elements[0].id])
    expected = math.pi * 0.08**2 / 4 * 800 * 2
    assert quantity_takeoff(model, operation='Filled').totals['fluid_mass_kg'] == pytest.approx(expected)
    duplicate.value = 1000
    with pytest.raises(ValueError, match='overlapping incompatible'):
        quantity_takeoff(model, operation='Filled')


@pytest.mark.parametrize('selectors', [
    {'route_id': 'P-100', 'element_ids': ['missing']},
    {'route_id': 'P-100', 'element_ids': []},
    {'node_ids': ['missing']},
    {'direction': [0, 0, -1]},
    {'station_start': 0, 'station_end': 2},
    {'route_id': 'P-100', 'station_start': 0.5, 'station_end': 2},
    {'route_id': 'P-100', 'profile': 'linear'},
    {'element_ids': ['missing']},
])
def test_unsupported_selection_never_silently_changes_meaning(selectors):
    model = contents_model()
    with pytest.raises(ValueError):
        model.define_operation('Bad').add_field('fluid_density', 800, **selectors)
        model.validate()


def test_legacy_and_operation_fields_survive_json_and_generated_python():
    from tuba.project.script import generate_model_script
    model = contents_model()
    model.define_load_case('Empty')
    model.define_load_case('Legacy', fields=[{
        'quantity': 'fluid_density', 'value': 800, 'route_id': 'P-100'}])
    model.define_operation('Hydro').add_field('fluid_density', 1000)
    data = model.to_dict()
    assert 'fields' not in data['load_cases']['Empty']
    restored = Model.from_dict(data)
    namespace = {'__name__': 'fluid_replay'}
    exec(compile(generate_model_script(restored), 'model.py', 'exec'), namespace)
    assert namespace['model'].to_dict() == restored.to_dict() == data


def test_all_pipes_excludes_beams_but_explicit_mixed_selection_rejects():
    model = contents_model(bent=True)
    model.elements[-1].type = 'beam'
    case = model.define_operation('Filled')
    field = case.add_field('fluid_density', 800)
    expected = math.pi / 4 * 0.08**2 * 800 * (2 + math.pi / 4)
    assert quantity_takeoff(model, operation='Filled').totals['fluid_mass_kg'] == pytest.approx(expected)
    model.groups['mixed'] = {'nodes': [], 'elements': [e.id for e in model.elements]}
    for scope in ('group', 'route', 'elements'):
        field.scope = scope
        field.group = 'mixed' if scope == 'group' else None
        field.route_id = 'P-100' if scope == 'route' else None
        field.element_ids = [e.id for e in model.elements] if scope == 'elements' else []
        with pytest.raises(ValueError, match='cannot carry'):
            quantity_takeoff(model, operation='Filled')


@pytest.mark.parametrize('end,admitted', [(2, True), (2 + 5e-10, True), (2 - 1e-5, False)])
def test_station_boundary_does_not_fill_neighbor(end, admitted):
    model = contents_model(bent=True)
    case = model.define_operation('Filled')
    case.add_field('fluid_density', 800, route_id='P-100', station_start=0, station_end=end)
    if not admitted:
        with pytest.raises(ValueError, match='partly covers'):
            quantity_takeoff(model, operation='Filled')
    else:
        case.add_field('fluid_density', 800, element_ids=[model.elements[0].id])
        takeoff = quantity_takeoff(model, operation='Filled')
        assert takeoff.records[0].fluid_mass_kg == pytest.approx(math.pi / 4 * 0.08**2 * 800 * 2)
        assert all(r.fluid_mass_kg == 0 for r in takeoff.records[1:])


@pytest.mark.parametrize('selectors', [{'group': 'empty'}, {'route_id': 'absent'},
                                      {'element_ids': []}, {'group': 'missing_member'}])
def test_empty_or_missing_selection_fails_in_quantity_api(selectors):
    model = contents_model()
    model.groups['empty'] = {'nodes': [], 'elements': []}
    model.groups['missing_member'] = {'nodes': [], 'elements': ['missing']}
    model.define_operation('Filled').add_field('fluid_density', 800, **selectors)
    with pytest.raises(ValueError):
        quantity_takeoff(model, operation='Filled')


def test_unknown_case_bad_section_and_finite_input_overflow():
    model = contents_model()
    with pytest.raises(ValueError, match='not found'):
        quantity_takeoff(model, operation='absent')
    field = model.define_operation('Filled').add_field('fluid_density', 800)
    model.add_rectangular_section('Box', height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    model.elements[0].section = 'Box'
    with pytest.raises(ValueError, match='PipeSection'):
        quantity_takeoff(model, operation='Filled')
    model.elements[0].section = 'Pipe'
    model.sections['Pipe'].OD, model.sections['Pipe'].WT = 10, 1
    field.value = 1e308
    with pytest.raises(ValueError, match='finite'):
        quantity_takeoff(model, operation='Filled')


def test_group_breakdown_and_corrosion_use_nominal_bore():
    model = contents_model()
    model.groups['pipes'] = {'nodes': [], 'elements': [model.elements[0].id]}
    model.sections['Pipe'].corrosion_allowance = 0.002
    model.define_load_case('Legacy', fields=[OperationField('fluid_density', 800)])
    takeoff = quantity_takeoff(model, operation='Legacy')
    for key in ('pipe_mass_kg', 'fluid_mass_kg', 'insulation_mass_kg', 'total_mass_kg'):
        assert takeoff.groups['pipes'][key] == takeoff.totals[key]
    assert takeoff.totals['fluid_mass_kg'] == pytest.approx(math.pi / 4 * 0.08**2 * 800 * 2)


def test_authored_contents_reload_never_rewrites_python(tmp_path):
    from tuba.project import run_model_script
    from tuba.project.script import AuthoredModelScript, write_model_script
    text = '''from tuba import Model
model = Model('Authored contents')
model.add_material('Steel', E=2e11, nu=0.3, rho=7850)
model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
with model.pipe('Pipe', 'Steel') as pipe:
    pipe.start([0, 0, 0], support='anchor')
    pipe.run(2)
model.define_load_case('Empty')
for name, density in [('Operating', 800), ('Hydrotest', 1000)]:
    model.define_operation(name).add_field('fluid_density', density)
'''
    target = tmp_path / 'model.py'
    target.write_text(text, encoding='utf-8')
    before = target.read_bytes()
    model = run_model_script(target)['model']
    assert quantity_takeoff(model, operation='Empty').totals['fluid_mass_kg'] == 0
    assert quantity_takeoff(model, operation='Operating').totals['fluid_mass_kg'] > 0
    with pytest.raises(AuthoredModelScript):
        write_model_script(target, model, last_text=None)
    assert target.read_bytes() == before
