import unittest
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.solver.aster import CodeAsterSolver
from tuba.validation import ModelValidationError


def _valid_pipe():
    model = Model('Numerical boundary')
    model.add_material('Steel', E=2e11, nu=0.3, alpha=12e-6)
    model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
    with model.pipe(section='Pipe', material='Steel') as pipe:
        pipe.start([0, 0, 0], support='anchor')
        pipe.run(1)
    model.define_operation('Hot', gravity=False)
    return model


def _invalid_material(model):
    model.materials['Steel'].E = -1


def _invalid_temperature(model):
    model.operations['Hot'].temperature = float('nan')


@pytest.mark.parametrize('mutate', [_invalid_material, _invalid_temperature])
@pytest.mark.parametrize('surface', [
    'export_study', 'export_analysis_study', 'analysis_study_inputs',
    'export_volume_study', 'volume_study_inputs', 'export_mixed_analysis_study', 'solve',
])
@pytest.mark.parametrize('existing', [False, True])
def test_invalid_numerics_never_write_or_mesh(tmp_path, monkeypatch, mutate, surface, existing):
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    import tuba.solver.aster_volume as volume

    model = _valid_pipe()
    output = tmp_path / 'study'
    solver = CodeAsterSolver(work_dir=output)
    if existing:
        solver.export_analysis_study(model, 'Hot', output)
    before = {p.name: p.read_bytes() for p in output.glob('*') if p.is_file()}
    mutate(model)

    def forbidden(*args, **kwargs):
        pytest.fail('Invalid model reached meshing or solver execution')

    monkeypatch.setattr(solver, '_write_mail', forbidden)
    monkeypatch.setattr(solver, '_execute', forbidden)
    monkeypatch.setattr(volume, 'build_pipe_volume_mesh', forbidden)
    monkeypatch.setattr(MixedCodeAsterStudyExporter, '_write_med', forbidden)
    options = dict(element_ids=['pipe_str_0'], max_element_size=0.02) if 'volume' in surface else {}
    args = [model, 'Hot']
    if surface.startswith('export'):
        args.append(output)
    with pytest.raises(ModelValidationError):
        getattr(solver, surface)(*args, **options)
    assert output.exists() == existing
    assert {p.name: p.read_bytes() for p in output.glob('*') if p.is_file()} == before


def test_invalid_volume_solve_does_not_allocate_a_temporary_directory(monkeypatch):
    import tuba.solver.aster as aster

    model = _valid_pipe()
    _invalid_temperature(model)

    def forbidden(**kwargs):
        pytest.fail('Invalid volume model allocated a solver work directory')

    monkeypatch.setattr(aster.tempfile, 'mkdtemp', forbidden)
    with pytest.raises(ModelValidationError, match='Hot.*temperature'):
        model.solve('Hot', pipe_modelization='3D',
                    volume_element_ids=['pipe_str_0'], max_element_size=0.02)


def test_exported_study_revalidates_mutated_model_before_artifact_access(tmp_path):
    model = _valid_pipe()
    solver = CodeAsterSolver(work_dir=tmp_path)
    study = solver.export_analysis_study(model, 'Hot', tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    _invalid_material(model)
    with pytest.raises(ModelValidationError, match='Steel.*E'):
        solver.solve_exported_study(model, study, force=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


@pytest.mark.parametrize('surface', ['export_volume_study', 'export_mixed_analysis_study',
                                    'direct_volume', 'direct_mixed', 'model_solve'])
@pytest.mark.parametrize('density', [0, 800])
@pytest.mark.parametrize('existing', [False, True])
def test_unsupported_contents_fail_before_all_volume_and_mixed_writes(tmp_path, monkeypatch, surface, density, existing):
    from tests.test_fluid_contents import contents_model
    from tuba.solver.aster_volume import PipeVolumeStudyExporter
    from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
    model = contents_model(insulated=False)
    model.define_operation('Filled').add_field('fluid_density', density)
    output = tmp_path / 'study'
    if existing:
        output.mkdir()
        for name in ('study.comm', 'study.mail', 'sentinel'):
            (output / name).write_bytes(b'previous evidence')
    before = {p.name: p.read_bytes() for p in output.glob('*')}
    def forbidden(*args, **kwargs):
        pytest.fail('Contents reached meshing or solver before refusal')
    monkeypatch.setattr(MixedCodeAsterStudyExporter, '_write_med', forbidden)
    import tuba.solver.aster_volume as volume
    monkeypatch.setattr(volume, 'build_pipe_volume_mesh', forbidden)
    options = dict(element_ids=[model.elements[0].id], max_element_size=0.02)
    with pytest.raises(ValueError, match='fluid_density'):
        if surface == 'direct_volume':
            PipeVolumeStudyExporter().export_analysis_study(model, 'Filled', output, **options)
        elif surface == 'direct_mixed':
            MixedCodeAsterStudyExporter().export_analysis_study(model, 'Filled', output)
        elif surface == 'model_solve':
            model.solve(operation='Filled', work_dir=str(output), pipe_modelization='3D',
                        volume_element_ids=options['element_ids'], max_element_size=0.02)
        else:
            getattr(CodeAsterSolver(), surface)(model, 'Filled', output,
                **(options if surface == 'export_volume_study' else {}))
    assert output.exists() == existing
    assert {p.name: p.read_bytes() for p in output.glob('*')} == before


@pytest.mark.parametrize('surface', ['export_study', 'export_analysis_study'])
@pytest.mark.parametrize('earlier', [None, ('Filled', 'Empty'), ('Filled', 'Empty', 'Filled')])
def test_contents_contact_and_history_refuse_before_writes(tmp_path, surface, earlier):
    from tests.test_fluid_contents import contents_model
    from tuba.model import OperationField
    model = contents_model(insulated=False)
    model.add_support(model.elements[-1].n2, type='rest', id='shoe', friction_coefficient=0.3)
    model.define_load_case('Filled', fields=[OperationField('fluid_density', 800)])
    model.define_load_case('Empty')
    output = tmp_path / 'study'
    output.mkdir()
    (output / 'sentinel').write_bytes(b'previous')
    solver = CodeAsterSolver(pipe_modelization='POU_D_T', load_path=earlier)
    with pytest.raises(ValueError, match='fluid_density'):
        getattr(solver, surface)(model, earlier[-1] if earlier else 'Filled', output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {'sentinel': b'previous'}


@pytest.mark.parametrize('surface', ['export_study', 'export_analysis_study'])
def test_contents_overflow_fails_before_directory_creation(tmp_path, surface):
    from tests.test_fluid_contents import contents_model
    model = contents_model(insulated=False)
    model.sections['Pipe'].OD, model.sections['Pipe'].WT = 10, 1
    model.define_operation('Filled').add_field('fluid_density', 1e308)
    output = tmp_path / 'study'
    with pytest.raises(ValueError, match='finite'):
        getattr(CodeAsterSolver(), surface)(model, 'Filled', output)
    assert not output.exists()


def test_fluid_volume_solve_does_not_allocate_tempdir(monkeypatch):
    from tests.test_fluid_contents import contents_model
    import tuba.solver.aster as aster
    model = contents_model(insulated=False)
    model.define_operation('Filled').add_field('fluid_density', 0)
    def forbidden(**kwargs):
        pytest.fail('Unsupported contents allocated a temporary directory')
    monkeypatch.setattr(aster.tempfile, 'mkdtemp', forbidden)
    with pytest.raises(ValueError, match='fluid_density'):
        model.solve(operation='Filled', pipe_modelization='3D',
                    volume_element_ids=[model.elements[0].id], max_element_size=0.02)


def test_pressurized_beam_contents_rejects_before_writes(tmp_path):
    from tests.test_fluid_contents import contents_model
    model = contents_model(insulated=False)
    model.define_operation('Hydro', pressure=1.5e6).add_field('fluid_density', 1000)
    output = tmp_path / 'study'
    with pytest.raises(ValueError, match='pressure is unsupported'):
        CodeAsterSolver(pipe_modelization='POU_D_T').export_study(model, 'Hydro', output)
    assert not output.exists()


class TestCodeAsterExportValidation(unittest.TestCase):
    def test_export_study_validates_before_writing_files(self):
        model = _model_with_missing_section()

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with self.assertRaisesRegex(ModelValidationError, "missing section"):
                CodeAsterSolver(work_dir=out_dir).export_study(model, "Hot", out_dir)

            self.assertFalse((out_dir / "study.mail").exists())
            self.assertFalse((out_dir / "study.comm").exists())
            self.assertFalse((out_dir / "study.export").exists())

    def test_export_analysis_study_validates_before_writing_files(self):
        model = _model_with_missing_material()

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with self.assertRaisesRegex(ModelValidationError, "missing material"):
                CodeAsterSolver(work_dir=out_dir).export_analysis_study(model, "Hot", out_dir)

            self.assertFalse((out_dir / "study.mail").exists())
            self.assertFalse((out_dir / "study.comm").exists())
            self.assertFalse((out_dir / "study.export").exists())
            self.assertFalse((out_dir / "study_manifest.json").exists())


def _model_with_missing_section() -> Model:
    model = Model(project_name="MissingSection")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    n0 = model.add_node((0.0, 0.0, 0.0))
    n1 = model.add_node((1.0, 0.0, 0.0))
    model.add_element(
        id="pipe_str_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="MissingSection",
        material="Steel",
    )
    model.define_load_case("Hot")
    return model


def _model_with_missing_material() -> Model:
    model = Model(project_name="MissingMaterial")
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node((0.0, 0.0, 0.0))
    n1 = model.add_node((1.0, 0.0, 0.0))
    model.add_element(
        id="pipe_str_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="MissingMaterial",
    )
    model.define_load_case("Hot")
    return model


if __name__ == "__main__":
    unittest.main()
