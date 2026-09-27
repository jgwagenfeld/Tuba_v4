"""Real Code_Aster qualification of contents mass, stiffness and pressure independence."""
import math
import os
import pytest
from tests.test_fluid_contents import contents_model

pytestmark = pytest.mark.skipif(
    os.environ.get('TUBA_RUN_CODE_ASTER_INTEGRATION') != '1',
    reason='real Code_Aster required')


@pytest.mark.parametrize('formulation', ['TUYAU_3M', 'POU_D_T'])
@pytest.mark.parametrize('bent', [False, True])
@pytest.mark.parametrize('insulated', [False, True])
def test_contents_gravity_matrix(tmp_path, formulation, bent, insulated):
    model = contents_model(bent=bent, insulated=insulated)
    fixed, tip = model.elements[0].n1, model.elements[-1].n2
    area = math.pi / 4 * (0.1**2 - 0.08**2)
    bore = math.pi / 4 * 0.08**2
    dry = 7850 * area + (100 * math.pi / 4 * (0.14**2 - 0.1**2) if insulated else 0)
    length = 3 + math.pi / 4 if bent else 2
    ix = 4.75 + math.pi / 2 if bent else 2
    iy = 0.75 + math.pi / 8 if bent else 0
    inertia = math.pi / 64 * (0.1**4 - 0.08**4)
    empty_displacement = None
    for density in (0, 800, 1000):
        name = f'Density{density}'
        model.define_operation(name, gravity=True).add_field('fluid_density', density)
        run = model.solve(operation=name, pipe_modelization=formulation,
                          work_dir=str(tmp_path / name),
                          exec_method=os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto'))
        reaction = run.results.node_results[fixed].reaction_force
        q = (dry + density * bore) * 9.81
        tolerance = 5e-3 if bent else 1e-5
        assert reaction[2] == pytest.approx(q * length, rel=tolerance, abs=1e-6)
        assert reaction[3] == pytest.approx(q * iy, rel=tolerance, abs=1e-6)
        assert reaction[4] == pytest.approx(-q * ix, rel=tolerance, abs=1e-6)
        if not bent:
            displacement = abs(run.results.node_results[tip].displacement[2])
            assert displacement == pytest.approx(q * length**4 / (8 * 2e11 * inertia), rel=0.03)
            if density == 0:
                empty_displacement = displacement
            else:
                assert displacement / empty_displacement == pytest.approx(
                    (dry + density * bore) / dry, rel=1e-3)


@pytest.mark.parametrize('formulation', ['TUYAU_3M', 'POU_D_T'])
def test_contents_do_not_change_stiffness_or_load_when_gravity_disabled(tmp_path, formulation):
    model = contents_model(insulated=False)
    fixed, tip = model.elements[0].n1, model.elements[-1].n2
    displacements = []
    for density in (0, 1000):
        name = f'Density{density}'
        case = model.define_operation(name, gravity=False)
        case.add_field('fluid_density', density)
        case.add_nodal_force(tip, [0, 0, -100])
        run = model.solve(operation=name, pipe_modelization=formulation, work_dir=str(tmp_path / name),
                          exec_method=os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto'))
        reaction = run.results.node_results[fixed].reaction_force
        displacement = run.results.node_results[tip].displacement[2]
        expected = 100 * 2**3 / (3 * 2e11 * (math.pi / 64 * (0.1**4 - 0.08**4)))
        assert reaction[2] == pytest.approx(100, rel=1e-5, abs=1e-6)
        assert reaction[4] == pytest.approx(-200, rel=1e-5, abs=1e-6)
        assert abs(displacement) == pytest.approx(expected, rel=0.03)
        displacements.append(displacement)
    assert displacements[1] == pytest.approx(displacements[0], rel=1e-6)


@pytest.mark.parametrize('formulation', ['TUYAU_3M', 'POU_D_T'])
def test_shared_material_does_not_share_contents(tmp_path, formulation):
    model = contents_model(insulated=False)
    with model.pipe('Pipe', 'Steel', route='P-200') as pipe:
        pipe.start([0, 2, 0], support='anchor')
        pipe.run(2)
    case = model.define_operation('DifferentContents')
    case.add_field('fluid_density', 800, route_id='P-100')
    case.add_field('fluid_density', 1000, route_id='P-200')
    run = model.solve(operation=case.name, pipe_modelization=formulation, work_dir=str(tmp_path),
                      exec_method=os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto'))
    for element, density in zip(model.elements, (800, 1000)):
        reaction = run.results.node_results[element.n1].reaction_force
        weight = (7850 * math.pi / 4 * (0.1**2 - 0.08**2)
                  + density * math.pi / 4 * 0.08**2) * 2 * 9.81
        assert reaction[2] == pytest.approx(weight, rel=1e-5, abs=1e-6)
        assert reaction[4] == pytest.approx(-weight, rel=1e-5, abs=1e-6)


def test_hydrotest_pressure_and_contents_are_independent(tmp_path):
    model = contents_model(insulated=False)
    fixed, tip = model.elements[0].n1, model.elements[-1].n2
    axial_increments = []
    for density in (0, 1000):
        axial = []
        for pressure in (0, 1.5e6):
            name = f'Density{density}_Pressure{int(pressure)}'
            model.define_operation(name, pressure=pressure).add_field('fluid_density', density)
            run = model.solve(operation=name, work_dir=str(tmp_path / name),
                              exec_method=os.environ.get('TUBA_CODE_ASTER_EXEC_METHOD', 'auto'))
            reaction = run.results.node_results[fixed].reaction_force
            weight = (7850 * math.pi / 4 * (0.1**2 - 0.08**2)
                      + density * math.pi / 4 * 0.08**2) * 2 * 9.81
            assert reaction[2] == pytest.approx(weight, rel=1e-5, abs=1e-6)
            assert reaction[4] == pytest.approx(-weight, rel=1e-5, abs=1e-6)
            axial.append(run.results.node_results[tip].displacement[0])
        assert abs(axial[1] - axial[0]) > 1e-9
        axial_increments.append(axial[1] - axial[0])
    assert axial_increments[1] == pytest.approx(axial_increments[0], rel=1e-6)
