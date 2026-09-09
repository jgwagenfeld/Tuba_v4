"""Subdivided members retain loads, lineage and solver endpoint lookup."""
import json
import os
from dataclasses import replace

import numpy as np
import pytest

from examples.guyed_mast_review import build_guyed_mast_model
from tuba.analysis import AnalysisMesh
from tuba.solver.aster import CodeAsterSolver


@pytest.mark.parametrize("segments", [1, 8, 16])
@pytest.mark.parametrize("beam_pipes", [False, True])
def test_straight_member_discretisation(tmp_path, segments, beam_pipes):
    model = build_guyed_mast_model()
    if beam_pipes:
        for element in model.elements:
            if element.type == "beam":
                element.type = "pipe_straight"
    solver = CodeAsterSolver(line_segments=segments, pipe_modelization="POU_D_T" if beam_pipes else "TUYAU_3M")
    solver.export_analysis_study(model, "Wind", tmp_path)
    manifest = json.loads((tmp_path / "study_manifest.json").read_text())
    mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    mail = (tmp_path / "study.mail").read_text()
    lookup = solver._result_element_lookup(model)
    for element in model.elements:
        members = mesh.groups[element.id]
        assert len(members) == segments
        assert mesh.elements[members[0]][0] == element.n1
        assert mesh.elements[members[-1]][1] == element.n2
        ids = [element.n1] + [mesh.elements[sid][1] for sid in members]
        np.testing.assert_allclose([mesh.nodes[nid] for nid in ids],
                                   np.linspace(model.nodes[element.n1].coords, model.nodes[element.n2].coords, segments + 1), atol=1e-14)
        for sid in members:
            assert lookup[sid] is element
            assert str(mesh.element_sources[sid].source_ref) == f"element:{element.id}"
            assert sid in mesh.groups[solver._material_group_name(element.material)]
        group = "G_CABLE" if element.type == "cable" else "AllPipes" if beam_pipes else "G_TUBE"
        assert set(members) <= set(mesh.groups[group])
    name_map = json.loads((tmp_path / "study_tuba_fem.json").read_text())["name_map"]
    # Named .mail groups must contain cells, never the now-abstract parent IDs.
    for group in ("G_CABLE", "AllPipes" if beam_pipes else "G_TUBE"):
        body = mail.split(f"GROUP_MA NOM={name_map[group]}\n", 1)[1].split("FINSF", 1)[0]
        assert body.split() == [name_map[sid] for sid in mesh.groups[group]]
    assert manifest["study"]["metadata"].get("compiler_inputs", {}).get("line_segments", 1) == segments


def test_line_segments_rejects_invalid_counts():
    for value in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="line_segments"):
            CodeAsterSolver(line_segments=value)


@pytest.mark.skipif(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
                    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 for the real cable solve")
def test_real_cable_sag_and_beam_curvature(tmp_path):
    model = build_guyed_mast_model()
    solver = CodeAsterSolver()
    study = solver.export_analysis_study(model, "Wind", tmp_path)
    solver.solve_exported_study(model, study)
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    run = import_code_aster_artifacts(model=model, work_dir=tmp_path)
    mesh, state = run.analysis_mesh, run.result_state
    from tuba.analysis.projection import project_deformed_centerline
    from tuba.analysis.states import create_operating_geometry_state
    geometry = create_operating_geometry_state(model=model, result_state=state)
    for element in model.elements:
        projected = project_deformed_centerline(model=model, element=element, result_state=state,
                                                geometry_state=geometry, analysis_mesh=mesh)
        assert len(projected.points) == 9
        assert not projected.diagnostics
        for nid, point in zip(projected.source_mesh_nodes, projected.points):
            np.testing.assert_allclose(point, np.array(mesh.nodes[nid]) + np.array(state.node_displacements[nid][:3]))
    incomplete = replace(state, node_displacements={k: v for k, v in state.node_displacements.items() if k != "cable_0_n4"})
    cable = next(e for e in model.elements if e.id == "cable_0")
    with pytest.raises(ValueError, match="Missing solved interior"):
        project_deformed_centerline(model=model, element=cable, result_state=incomplete,
                                    geometry_state=geometry, analysis_mesh=mesh)

    def chord_offset(element_id):
        element = next(e for e in model.elements if e.id == element_id)
        nid = mesh.elements[mesh.groups[element_id][3]][1]
        def displaced(n):
            return np.array(mesh.nodes[n]) + np.array(state.node_displacements[n][:3])
        return displaced(nid) - (displaced(element.n1) + displaced(element.n2)) / 2
    assert -0.11 < chord_offset("cable_0")[2] < -0.09
    assert -0.006 < chord_offset("cable_1")[2] < -0.003
    assert abs(chord_offset("beam_1")[0]) > 0.001
    assert state.element_results["cable_0"]["forces_n1"][0] > 0
    assert state.metadata["solve_attestation"]["solver_version"]
