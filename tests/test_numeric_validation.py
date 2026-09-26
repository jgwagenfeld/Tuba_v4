"""Invalid engineering inputs must fail before they can become solver inputs."""

import numpy as np
import pytest

from tuba import Model
from tuba.validation import ModelValidationError


def model_with_sections():
    model = Model('Numerical admission')
    model.add_material('Steel', E=2e11, nu=0.3, alpha=12e-6)
    model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
    model.add_bar_section('Bar', OD=0.1, WT=0)
    model.add_cable_section('Cable', radius=0.01)
    model.add_rectangular_section('Box', height_y=0.2, height_z=0.1,
                                  thickness_y=0.01, thickness_z=0.01)
    return model


@pytest.mark.parametrize('property_name', ['E', 'nu', 'rho', 'alpha'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), '1', True, None])
def test_material_rejects_nonfinite_and_nonnumeric_scalars(property_name, value):
    model = model_with_sections()
    setattr(model.materials['Steel'], property_name, value)
    with pytest.raises(ModelValidationError, match=f'Steel.*{property_name}'):
        model.validate()


@pytest.mark.parametrize(('property_name', 'value'), [
    ('E', 0), ('E', -2e11), ('nu', -1), ('nu', 0.5), ('nu', 0.8), ('rho', -7850),
])
def test_material_rejects_out_of_domain_properties(property_name, value):
    model = model_with_sections()
    setattr(model.materials['Steel'], property_name, value)
    with pytest.raises(ModelValidationError, match=f'Steel.*{property_name}'):
        model.validate()


@pytest.mark.parametrize('define', ['define_operation', 'define_load_case'])
@pytest.mark.parametrize('property_name', ['temperature', 'ref_temperature', 'internal_pressure'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), '120', False, None])
def test_uniform_cases_reject_invalid_scalars(define, property_name, value):
    model = model_with_sections()
    case = getattr(model, define)('Hot')
    setattr(case, property_name, value)
    with pytest.raises(ModelValidationError, match=f'Hot.*{property_name}'):
        model.validate()


@pytest.mark.parametrize('define', ['define_operation', 'define_load_case'])
def test_negative_internal_pressure_is_not_silently_dropped(define):
    model = model_with_sections()
    getattr(model, define)('Vacuum', pressure=-1e5)
    with pytest.raises(ModelValidationError, match='Vacuum.*internal_pressure'):
        model.validate()


SECTION_FIELDS = [
    ('Pipe', 'OD'), ('Pipe', 'WT'), ('Pipe', 'corrosion_allowance'),
    ('Bar', 'OD'), ('Bar', 'WT'), ('Cable', 'radius'), ('Cable', 'pretension'),
    ('Cable', 'compression_modulus_ratio'), ('Box', 'height_y'), ('Box', 'height_z'),
    ('Box', 'thickness_y'), ('Box', 'thickness_z'),
]


@pytest.mark.parametrize(('section', 'property_name'), SECTION_FIELDS)
@pytest.mark.parametrize('value', [float('nan'), float('inf'), '0.01', True])
def test_section_rejects_invalid_scalars(section, property_name, value):
    model = model_with_sections()
    setattr(model.sections[section], property_name, value)
    with pytest.raises(ModelValidationError, match=f'{section}.*{property_name}'):
        model.validate()


@pytest.mark.parametrize(('section', 'property_name', 'value'), [
    ('Pipe', 'OD', 0), ('Pipe', 'WT', 0), ('Pipe', 'WT', 0.05),
    ('Pipe', 'corrosion_allowance', -0.001), ('Pipe', 'corrosion_allowance', 0.01),
    ('Pipe', 'corrosion_allowance', 0.02), ('Bar', 'WT', -0.01),
    ('Cable', 'radius', 0), ('Cable', 'pretension', -1),
    ('Cable', 'compression_modulus_ratio', -0.1), ('Cable', 'compression_modulus_ratio', 1.1),
    ('Box', 'height_y', 0), ('Box', 'thickness_y', -0.01),
    ('Box', 'thickness_y', 0.1), ('Box', 'thickness_z', 0.05),
    ('Box', 'thickness_y', 0),
])
def test_section_rejects_impossible_dimensions(section, property_name, value):
    model = model_with_sections()
    setattr(model.sections[section], property_name, value)
    with pytest.raises(ModelValidationError, match=f'{section}.*{property_name}'):
        model.validate()


@pytest.mark.parametrize('alpha', [0, -1e-6])
@pytest.mark.parametrize('bar_wall', [0, 0.05, 0.06])
@pytest.mark.parametrize('compression_ratio', [0, 1])
def test_valid_boundary_values_preserve_existing_idealizations(alpha, bar_wall, compression_ratio):
    model = model_with_sections()
    model.materials['Steel'].E = np.float64(2e11)
    model.materials['Steel'].nu = -0.2
    model.materials['Steel'].rho = 0
    model.materials['Steel'].alpha = alpha
    model.sections['Bar'].WT = bar_wall
    model.sections['Cable'].compression_modulus_ratio = compression_ratio
    model.sections['Box'].thickness_y = model.sections['Box'].thickness_z = 0
    model.define_operation('Cold', temperature=-100, ref_temperature=-20, pressure=0)
    model.validate()
    restored = Model.from_dict(model.to_dict())
    restored.validate()
    assert restored.to_dict() == model.to_dict()


@pytest.mark.parametrize(('collection', 'name', 'property_name', 'value'), [
    ('materials', 'Steel', 'E', -1),
    ('sections', 'Pipe', 'corrosion_allowance', 0.02),
    ('operations', 'Hot', 'temperature', float('nan')),
])
def test_deserialization_cannot_bypass_semantic_validation(collection, name, property_name, value):
    model = model_with_sections()
    model.define_operation('Hot')
    payload = model.to_dict()
    payload[collection][name][property_name] = value
    # Schema rejection or semantic rejection is valid; successful admission is not.
    with pytest.raises(ValueError):
        Model.from_dict(payload).validate()


def test_validation_collects_material_section_and_case_errors():
    model = model_with_sections()
    model.materials['Steel'].E = -1
    model.sections['Pipe'].WT = float('nan')
    model.define_operation('Hot', temperature=float('nan'))
    with pytest.raises(ModelValidationError) as error:
        model.validate()
    for entity, property_name in [('Steel', 'E'), ('Pipe', 'WT'), ('Hot', 'temperature')]:
        assert any(entity in line and property_name in line for line in str(error.value).splitlines())
