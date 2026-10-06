"""Real STEP/1D qualification: independent stiffness and equilibrium checks."""

import json
import math
import os
from statistics import median

import gmsh
import numpy as np
import pytest

from tuba import Model
from tuba.meshing._gmsh import gmsh_model
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import SceneRequest, build_visualization_scene


pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to qualify STEP with real Code_Aster",
)

E, NU, OUTER, INNER, SOLID_LENGTH, LENGTH = 2.1e11, 0.3, 0.05, 0.04, 0.2, 1.2
AREA = math.pi * (OUTER**2 - INNER**2)
INERTIA = math.pi * (OUTER**4 - INNER**4) / 4.0
SHEAR = E / (2.0 * (1.0 + NU))


def build_step_reference(root, *, mesh_size, beam=False, unit_scale_to_m=1.0, placement=None):
    """Closed-end annular cantilever; STEP occupies its first 0.2 m."""
    root.mkdir(parents=True, exist_ok=True)
    source = root / "annulus.step"
    source_length, source_outer, source_inner = (v / unit_scale_to_m for v in (SOLID_LENGTH, OUTER, INNER))
    with gmsh_model(gmsh, "step_reference"):
        outer = gmsh.model.occ.addCylinder(0, 0, 0, source_length, 0, 0, source_outer)
        bore = gmsh.model.occ.addCylinder(-0.01 / unit_scale_to_m, 0, 0,
                                         source_length + 0.02 / unit_scale_to_m, 0, 0, source_inner)
        gmsh.model.occ.cut([(3, outer)], [(3, bore)])
        gmsh.model.occ.synchronize()
        gmsh.write(str(source))
    model = Model("STEP annular cantilever")
    model.add_material("Steel", E=E, nu=NU, rho=7850.0)
    model.add_pipe_section("Annulus", OD=2 * OUTER, WT=OUTER - INNER)
    model.import_step(
        source, id="component", material="Steel", mesh_size=mesh_size,
        unit_scale_to_m=unit_scale_to_m, placement=placement,
        interfaces={
            "base": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": source_outer},
            "nozzle": {"position": [source_length, 0, 0], "axis": [1, 0, 0], "radius": source_outer},
        },
        fixed_interfaces=["base"],
        pressure_surfaces=[{"type": "Cylinder", "position": [source_length / 2, 0, 0], "radius": source_inner}],
    )
    from tuba.mixed import normalize_placement, transform_point
    placement = normalize_placement(placement)
    connection = model.add_node(transform_point([SOLID_LENGTH, 0, 0], 1.0, placement))
    tip = model.add_node(transform_point([LENGTH, 0, 0], 1.0, placement))
    model.add_element(id="extension", type="beam" if beam else "pipe_straight",
                      n1=connection, n2=tip, section="Annulus", material="Steel")
    if beam:
        model.connect_beam_to_port(beam="element:extension", node=f"node:{connection}",
                                   port="port:component_nozzle")
    else:
        model.connect_pipe_to_port(pipe="element:extension", node=f"node:{connection}",
                                   port="port:component_nozzle")
    return model, connection, tip


def _reaction_resultant(run):
    force, moment = np.zeros(3), np.zeros(3)
    # Model-node aliases duplicate analysis nodes; sum the physical mesh once.
    for node_id, point in run.analysis_mesh.nodes.items():
        reaction = run.result_state.node_reactions.get(node_id)
        if reaction is None:
            continue
        nodal_force = np.asarray(reaction[:3], dtype=float)
        nodal_moment = np.asarray([0.0 if value is None else value for value in reaction[3:]])
        force += nodal_force
        moment += np.cross(point, nodal_force) + nodal_moment
    return force, moment


def _check_interface_continuity(run, connection):
    """Fit section translation/rotation while allowing uniform radial expansion."""
    blocks, displacements = [], []
    for node_id, point in run.analysis_mesh.nodes.items():
        if abs(point[0] - SOLID_LENGTH) > 1e-8:
            continue
        x, y, z = np.asarray(point) - [SOLID_LENGTH, 0, 0]
        blocks.append([[1, 0, 0, 0, z, -y, 0],
                       [0, 1, 0, -z, 0, x, y],
                       [0, 0, 1, y, -x, 0, z]])
        displacements.extend(run.result_state.node_displacements[node_id][:3])
    assert len(blocks) > 6
    fitted = np.linalg.lstsq(np.vstack(blocks), np.asarray(displacements), rcond=None)[0][:6]
    pipe_displacement = np.asarray(run.result_state.node_displacements[connection], dtype=float)
    for start, stop in ((0, 3), (3, 6)):
        scale = max(np.linalg.norm(pipe_displacement[start:stop]), 1e-9)
        assert np.linalg.norm(fitted[start:stop] - pipe_displacement[start:stop]) < 0.05 * scale + 1e-10


def _solve(model, load_case, root):
    solver = CodeAsterSolver(work_dir=root,
                            exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"))
    study = solver.export_mixed_analysis_study(model, load_case, root)
    run = solver.solve_exported_study(model, study)
    assert run.result_state.metadata["result_trust"] == "verified"
    assert run.study.solver_input_identity == run.analysis_mesh.solver_input_identity
    assert run.study.solver_input_identity == run.result_state.solver_input_identity
    assert run.results.volume_von_mises
    assert (root / "study.rmed").is_file()
    scene = build_visualization_scene(SceneRequest(
        model, result_states=[run.result_state], analysis_meshes=[run.analysis_mesh]))
    scene.validate()
    json.dumps(scene.to_dict(), allow_nan=False)
    assert any(obj.kind == "volume_stress_field" for obj in scene.objects)
    assert any(obj.kind == "volume_displacement_field" for obj in scene.objects)
    return run


@pytest.mark.parametrize("kind", ["axial", "bending", "torsion", "pressure"])
def test_step_pipe_stiffness_balance_continuity_and_refinement(tmp_path, kind):
    measured = []
    for mesh_size in (0.008, 0.006):
        root = tmp_path / str(mesh_size)
        model, connection, tip = build_step_reference(root, mesh_size=mesh_size)
        pressure = 1e6 if kind == "pressure" else 0.0
        force = {"axial": [1000., 0, 0], "bending": [0, 100., 0],
                 "torsion": [0, 0, 0], "pressure": [pressure * math.pi * INNER**2, 0, 0]}[kind]
        moment = [10., 0, 0] if kind == "torsion" else [0, 0, 0]
        case = model.define_load_case(kind, gravity=False, pressure=pressure)
        # The tip force is the equivalent closed cap; inner-wall pressure alone
        # does not apply the physical end closure to this open mesh.
        case.add_nodal_force(tip, force=force, moment=moment)
        run = _solve(model, kind, root)
        reaction_force, reaction_moment = _reaction_resultant(run)
        applied_moment = np.asarray(moment) + np.cross([LENGTH, 0, 0], force)
        assert reaction_force == pytest.approx(-np.asarray(force), abs=0.01 * max(np.linalg.norm(force), 1))
        assert reaction_moment == pytest.approx(-applied_moment, abs=0.01 * max(np.linalg.norm(applied_moment), 1))
        _check_interface_continuity(run, connection)
        displacement = run.result_state.node_displacements[tip]
        if kind == "axial":
            value, expected = displacement[0], force[0] * LENGTH / (E * AREA)
        elif kind == "bending":
            value, expected = displacement[1], force[1] * LENGTH**3 / (3 * E * INERTIA)
        elif kind == "torsion":
            value, expected = displacement[3], moment[0] * LENGTH / (SHEAR * 2 * INERTIA)
        else:
            inner_values = [stress for node_id, stress in run.results.volume_von_mises.items()
                            if abs(run.analysis_mesh.nodes[node_id][0] - SOLID_LENGTH / 2) < 0.025
                            and abs(math.hypot(*run.analysis_mesh.nodes[node_id][1:]) - INNER) < 1e-7]
            assert inner_values
            value = median(inner_values)
            expected = math.sqrt(3) * pressure * OUTER**2 / (OUTER**2 - INNER**2)
        assert value == pytest.approx(expected, rel=0.08 if kind == "pressure" else 0.05)
        measured.append(value)
    assert measured[0] == pytest.approx(measured[1], rel=0.03)


def test_step_beam_3d_pou_transfers_force_and_moment(tmp_path):
    model, connection, tip = build_step_reference(tmp_path, mesh_size=0.008, beam=True)
    force, moment = [1000., 100., 0], [10., 0, 0]
    model.define_load_case("Beam", gravity=False).add_nodal_force(tip, force=force, moment=moment)
    run = _solve(model, "Beam", tmp_path)
    assert {coupling.code_aster_option for coupling in model.couplings.values()} == {"3D_POU"}
    reaction_force, reaction_moment = _reaction_resultant(run)
    assert reaction_force == pytest.approx(-np.asarray(force), abs=0.5)
    assert reaction_moment == pytest.approx(-np.asarray(moment) - np.cross([LENGTH, 0, 0], force), abs=0.5)
    _check_interface_continuity(run, connection)
    displacement = run.result_state.node_displacements[tip]
    assert displacement[0] == pytest.approx(force[0] * LENGTH / (E * AREA), rel=0.05)
    assert displacement[1] == pytest.approx(force[1] * LENGTH**3 / (3 * E * INERTIA), rel=0.05)
    assert displacement[3] == pytest.approx(moment[0] * LENGTH / (SHEAR * 2 * INERTIA), rel=0.05)
