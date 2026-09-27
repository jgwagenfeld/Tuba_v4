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


def test_compiler_assigns_contents_per_element_without_mutating_material(tmp_path):
    from tuba.solver.aster import CodeAsterSolver
    model = contents_model(insulated=False)
    with model.pipe('Pipe', 'Steel', route='P-200') as pipe:
        pipe.start([0, 2, 0], support='anchor')
        pipe.run(2)
    case = model.define_operation('Filled')
    case.add_field('fluid_density', 800, route_id='P-100')
    case.add_field('fluid_density', 1000, route_id='P-200')
    before = model.to_dict()
    CodeAsterSolver().export_study(model, 'Filled', tmp_path)
    comm = (tmp_path / 'study.comm').read_text()
    area = math.pi / 4 * (0.1**2 - 0.08**2)
    for density in (800, 1000):
        effective = 7850 + density * math.pi / 4 * 0.08**2 / area
        assert f'RHO={effective:.12E}' in comm
    assert model.to_dict() == before


def test_pre_contents_model_keeps_canonical_inputs_script_and_compiler(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    from tuba.project.script import generate_model_script
    from tuba.solver.aster import CodeAsterSolver
    from tuba.analysis.provenance import build_solver_input_identity
    model = Model.from_dict(json.loads(Path('tests/fixtures/pre_operation_model.json').read_text()))
    canonical = json.dumps(model.to_dict(), sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(canonical).hexdigest() == '079723f441084622c16582f7f1bd99922a096df084567e612966be7a709f7838'
    assert hashlib.sha256(generate_model_script(model).encode()).hexdigest() == 'ab29cffcc7d5c81f86ec479cbdd3c3c3a6f63e9ae332f5ca8c6cc0462baf7751'
    CodeAsterSolver().export_study(model, 'Hot', tmp_path)
    text = (tmp_path / 'study.comm').read_text().replace('\r\n', '\n').encode()
    assert hashlib.sha256(text).hexdigest() == '9767c67601af67b4ba119c9e920cbd5dae798ec883f23144d38483884b4f8884'
    assert build_solver_input_identity(model, 'Hot').fingerprint == 'c67e5e0fee6c935b961c85cc38a51ccdc39aad418616f418b087af91d44e5ed8'


@pytest.mark.parametrize('change', ['density', 'scope', 'members', 'bore', 'case'])
def test_contents_dependencies_invalidate_exported_identity(tmp_path, change):
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    from tuba.analysis.provenance import build_solver_input_identity
    from tuba.solver.aster import CodeAsterSolver
    model = contents_model(bent=True, insulated=False)
    ids = [e.id for e in model.elements]
    model.groups['selected'] = {'nodes': [], 'elements': ids[:1]}
    field = model.define_operation('Filled').add_field('fluid_density', 800, group='selected')
    model.define_operation('Other').add_field('fluid_density', 800, group='selected')
    study = CodeAsterSolver().export_analysis_study(model, 'Filled', tmp_path)
    case = 'Filled'
    if change == 'density':
        field.value = 1000
    elif change == 'scope':
        field.scope, field.group, field.element_ids = 'elements', None, ids[:1]
    elif change == 'members':
        model.groups['selected']['elements'] = ids
    elif change == 'bore':
        model.sections['Pipe'].WT = 0.012
    else:
        case = 'Other'
    assert build_solver_input_identity(model, case) != study.solver_input_identity
    if change != 'case':
        with pytest.raises(ValueError, match='fingerprint'):
            import_code_aster_artifacts(model=model, work_dir=tmp_path)


def test_unselected_contents_does_not_block_empty_volume_or_mixed_export(tmp_path):
    from tuba.solver.aster import CodeAsterSolver
    model = contents_model(insulated=False)
    # Shorten only the geometric model to keep this actual volume mesh small.
    model.nodes[model.elements[0].n2].coords[0] = 0.2
    model.define_operation('Empty', gravity=False)
    model.define_operation('Filled').add_field('fluid_density', 1000)
    solver = CodeAsterSolver()
    volume = solver.export_volume_study(model, 'Empty', tmp_path / 'volume',
                                       element_ids=[model.elements[0].id], max_element_size=0.005)
    mixed = solver.export_mixed_analysis_study(model, 'Empty', tmp_path / 'mixed')
    assert volume.load_case == mixed.load_case == 'Empty'


def test_operation_quantities_are_model_inputs():
    from tuba.reporting.tables import build_model_tables
    model = contents_model()
    model.define_load_case('Empty', gravity=False)
    model.define_operation('Operating').add_field('fluid_density', 800)
    table = next(table for table in build_model_tables(model)
                 if table.id == 'operation_quantities')
    assert table.source == 'model'
    rows = {row['name']: row for row in table.rows}
    assert rows['Empty']['fluid_mass_kg'] == 0
    assert rows['Empty']['gravity'] is False
    assert rows['Operating']['fluid_mass_kg'] == pytest.approx(math.pi * 0.08**2 / 4 * 800 * 2)
    for row in rows.values():
        assert row['total_mass_kg'] == pytest.approx(
            row['pipe_mass_kg'] + row['insulation_mass_kg'] + row['fluid_mass_kg'])
    empty_table = next(table for table in build_model_tables(Model('Empty'))
                       if table.id == 'operation_quantities')
    assert not empty_table.rows


def test_contents_input_table_exports_to_json_csv_and_html(tmp_path):
    import csv
    import json
    from tuba.reporting import build_engineering_review, write_engineering_review
    model = contents_model()
    model.define_operation('Filled').add_field('fluid_density', 1000)
    output = write_engineering_review(build_engineering_review(model), tmp_path)
    tables = json.loads(output.review_path.read_text())['tables']
    table = tables['operation_quantities']
    assert table['source'] == 'model'
    with output.csv_paths['operation_quantities'].open(newline='') as stream:
        row = next(csv.DictReader(stream))
    assert float(row['fluid_mass_kg']) == pytest.approx(math.pi / 4 * 0.08**2 * 1000 * 2)
    assert 'Contents mass' in output.index_path.read_text(encoding='utf-8')


def test_contents_example_does_not_publish_when_solver_is_unavailable(tmp_path, monkeypatch):
    import runpy
    namespace = runpy.run_path('examples/fluid_contents.py')
    def unavailable(*args, **kwargs):
        raise RuntimeError('Code_Aster runtime unavailable')
    monkeypatch.setattr(Model, 'solve', unavailable)
    with pytest.raises(RuntimeError, match='Code_Aster runtime unavailable'):
        namespace['main'](tmp_path / 'contents')
    assert not (tmp_path / 'contents' / 'review').exists()


def test_finite_element_masses_cannot_overflow_the_case_total(tmp_path):
    from tuba.solver.aster import CodeAsterSolver
    model = contents_model(insulated=False)
    # Each member has a finite mass near 1e308 kg, but the case total overflows.
    model.nodes[model.elements[0].n2].coords[0] = 200
    with model.pipe('Pipe', 'Steel', route='P-200') as pipe:
        pipe.start([0, 2, 0], support='anchor')
        pipe.run(200)
    model.define_operation('Huge').add_field('fluid_density', 1e308)
    for element in model.elements:
        assert math.isfinite(element_quantities(model, element, operation='Huge').total_mass_kg)
    with pytest.raises(ValueError, match='finite'):
        quantity_takeoff(model, operation='Huge')
    with pytest.raises(ValueError, match='finite'):
        CodeAsterSolver().export_study(model, 'Huge', tmp_path / 'study')
    assert not (tmp_path / 'study').exists()


def test_schema_validates_legacy_case_fields_too():
    from tuba.schema import validate_model_dict
    model = contents_model()
    model.define_load_case('Legacy', fields=[OperationField('fluid_density', 800)])
    data = model.to_dict()
    validate_model_dict(data)
    data['load_cases']['Legacy']['fields'][0]['quantity'] = 'unsupported'
    with pytest.raises(ValueError, match='quantity'):
        validate_model_dict(data)
