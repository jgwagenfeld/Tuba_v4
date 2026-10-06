"""The authored Studio example builds actual imports, named joins and functions."""

from pathlib import Path

from tuba.project import load_project
from tuba.project.script import require_model_script_style
from tuba.solver.aster import CodeAsterSolver


PROJECT = Path(__file__).resolve().parents[1] / 'examples' / 'imported-geometry-studio'


def test_studio_example_replays_functions_and_keeps_stl_out_of_structural_regions():
    require_model_script_style((PROJECT / 'model.py').read_text())
    project = load_project(PROJECT)
    namespace = project.run_model()
    model = namespace['model']
    model.validate()
    reference = model.imported_components['enclosure_reference']
    assert reference.role == 'reference'
    asset = model.cad_assets[reference.asset.id]
    assert asset.metadata['inspection']['triangle_count'] == 12
    assert asset.metadata['inspection']['closed_surface']
    assert not any(region.owner == reference.asset for region in model.analysis_regions.values())
    assert not any(str(region.owner) == 'component:enclosure_reference' for region in model.analysis_regions.values())
    assert {c.code_aster_option for c in model.couplings.values()} == {'3D_TUYAU', '3D_POU', 'RIGID_PATCH'}
    assert sum(call['ref'] == 'solid_part' for call in model.assembly_calls) == 2
    assert model.imported_components['spool'].source_line
    assert model.imported_components['spool'].source_call_line
    assert model.imported_components['beam_spool'].source_call_line != model.imported_components['spool'].source_call_line
    assert project.load_settings().operations == ('Combined',)
    inputs = CodeAsterSolver().mixed_study_inputs(model, 'Combined')
    assert inputs.solver_input_identity.fingerprint
