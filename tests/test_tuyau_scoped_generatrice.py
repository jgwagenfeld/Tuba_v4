"""Portable readback of the actual mixed compiler's pipe orientations.

The small CSV/mesh records exercise parsing only; they are not solver evidence.
"""

import json

import numpy as np
import pytest

from tuba import Model
from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar
from tuba.solver.aster_volume import _write_comm, mixed_pipe_generatrices
from tuba.solver.base import ElementResult, FEAResults
from tuba.solver.parse_tables import parse_sieq_table


def _emitted_study(root, *, subdivided=False):
    model = Model("Scoped generatrice parser check")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Annulus", OD=0.1, WT=0.01)
    start_x = model.add_node([0, 0, 0])
    end_x = model.add_node([1, 0, 0])
    start_z = model.add_node([2, 0, 0])
    end_z = model.add_node([2, 0, 1])
    for eid, start, end in (("pipe_x", start_x, end_x), ("pipe_z", start_z, end_z)):
        model.add_element(id=eid, type="pipe_straight", n1=start, n2=end,
                          section="Annulus", material="Steel")
    if subdivided:
        tail = model.add_node([1.5, 0, 0])
        model.add_element(id="pipe_x_tail", type="pipe_straight", n1=end_x, n2=tail,
                          section="Annulus", material="Steel")
    model.define_load_case("Check", gravity=False)
    nodes = {f"VN{index + 1}": tuple(node.coords) for index, node in enumerate(model.nodes.values())}
    native_nodes = dict(zip(model.nodes, nodes))
    cells = {f"LM{101 + index}": (native_nodes[e.n1], native_nodes[e.n2])
             for index, e in enumerate(model.elements)}
    groups = {f"G_NODE_{node}": (mesh_node,) for node, mesh_node in native_nodes.items()}
    groups.update({f"G_LINE_{e.id}": (cell,) for e, cell in zip(model.elements, cells)})
    groups["G_TUBE"] = tuple(cells)
    names = build_solver_name_map(groups, max_length=8)
    mesh = AnalysisMesh(
        id="parser_check", model_revision=0, solver_name="Code_Aster", nodes=nodes,
        elements=cells, groups=groups, modelisations={"G_TUBE": "TUYAU_3M"},
        node_sources={mesh_node: MeshNodeSource(mesh_node, f"node:{node}", "native_node")
                      for node, mesh_node in native_nodes.items()},
        element_sources={cell: MeshElementSource(cell, f"element:{e.id}", "native_element")
                         for e, cell in zip(model.elements, cells)},
    )
    _write_comm(model, root / "study.comm", name_map=names, pressure=0,
                support_groups=(), couplings=(), line_elements=list(model.elements),
                nodal_forces=[], node_groups={}, gravity=False, material_name="Steel",
                export_tensor_stress=False, solid_group=None, skin_groups_raw=(),
                pressure_groups_raw=(), modelisations={"G_TUBE": "TUYAU_3M"},
                load_case=model.load_cases["Check"], mesh=mesh)
    dump_solver_sidecar(root / "study_tuba_fem.json", solver_name="Code_Aster",
                        load_case="Check", analysis_mesh_id=mesh.id, name_map=names, lineage={})
    (root / "study_manifest.json").write_text(json.dumps({
        "analysis_mesh": mesh.to_dict(),
        "study": {"metadata": {"compiler_inputs": {
            "line_element_ids": [e.id for e in model.elements],
            "pipe_generatrices": mixed_pipe_generatrices(model, list(model.elements))}}},
    }))
    rows = ["MAILLE,NOEUD,SOUS_POINT,COOR_X,COOR_Y,COOR_Z,VMIS"]
    for e, cell in zip(model.elements, cells):
        point = model.nodes[e.n1].coords
        node = native_nodes[e.n1]
        rows.append(f"{cell[2:]},{node[2:]},1,{point[0]},{point[1]},{point[2]},10")
    (root / "study_sieq.csv").write_text("\n".join(rows))
    results = FEAResults(solver_name="Code_Aster")
    results.element_results = {e.id: ElementResult(element_id=e.id, forces_n1=np.zeros(6),
                                                  forces_n2=np.zeros(6)) for e in model.elements}
    node_map = {mesh_node[2:]: node for node, mesh_node in native_nodes.items()}
    element_map = {cell[2:]: e.id for e, cell in zip(model.elements, cells)}
    return model, results, node_map, element_map, names


def _parse(root, fixture):
    model, results, node_map, element_map, _ = fixture
    parse_sieq_table(model, root, results, node_map, element_map)
    return results.tuyau_subpoints


def test_each_pipe_reads_its_actual_emitted_generatrice_and_numeric_source_ref(tmp_path):
    fixture = _emitted_study(tmp_path)
    rows = {row["element_id"]: row for row in _parse(tmp_path, fixture)}
    assert rows["pipe_x"]["generatrice"]["vector"] == [0, 0, 1]
    assert rows["pipe_z"]["generatrice"]["vector"] == [0, 1, 0]
    assert all(row["generatrice"]["solved"] for row in rows.values())
    np.testing.assert_allclose(rows["pipe_x"]["display_position"], [0, 0, 0.04])
    np.testing.assert_allclose(rows["pipe_z"]["display_position"], [2, 0.04, 0])


def test_scoped_generatrice_rejects_element_groups_unsupported_by_code_aster(tmp_path):
    fixture = _emitted_study(tmp_path)
    names = fixture[-1]
    (tmp_path / "study.comm").write_text("\n".join(
        f"_F(GROUP_MA={names[f'G_LINE_{eid}']!r}, CARA='GENE_TUYAU', VALE={vector!r})"
        for eid, vector in (("pipe_x", (0, 0, 1)), ("pipe_z", (0, 1, 0)))))
    with pytest.raises(RuntimeError, match="GENE_TUYAU.*GROUP_NO"):
        _parse(tmp_path, fixture)


@pytest.mark.parametrize("problem", ["unknown", "missing", "invalid"])
def test_scoped_generatrice_refuses_unresolved_or_invalid_orientation(tmp_path, problem):
    fixture = _emitted_study(tmp_path)
    names = fixture[-1]
    known = names[f"G_NODE_{fixture[0].elements[0].n1}"]
    group = "unknown_group" if problem == "unknown" else known
    vector = (0, 0, 0) if problem == "invalid" else (0, 0, 1)
    (tmp_path / "study.comm").write_text(
        f"_F(GROUP_NO={group!r}, CARA='GENE_TUYAU', VALE={vector!r})")
    with pytest.raises(RuntimeError, match="GENE_TUYAU"):
        _parse(tmp_path, fixture)


def test_conflicting_factors_at_one_actual_start_node_fail_loudly(tmp_path):
    fixture = _emitted_study(tmp_path)
    group = fixture[-1][f"G_NODE_{fixture[0].elements[0].n1}"]
    with (tmp_path / "study.comm").open("a") as stream:
        stream.write(f"\n_F(GROUP_NO={group!r}, CARA='GENE_TUYAU', VALE=(0, 0, 1))")
    with pytest.raises(RuntimeError, match="GENE_TUYAU.*conflict"):
        _parse(tmp_path, fixture)


def test_legacy_global_generatrice_still_applies_to_all_legacy_pipe_rows(tmp_path):
    fixture = _emitted_study(tmp_path)
    (tmp_path / "study.comm").write_text(
        "_F(GROUP_NO='legacy_orientation_group', CARA='GENE_TUYAU', VALE=(1, 1, 1))")
    (tmp_path / "study_tuba_fem.json").unlink()
    path = tmp_path / "study_manifest.json"
    payload = json.loads(path.read_text())
    payload.pop("study")
    path.write_text(json.dumps(payload))
    assert all(row["generatrice"]["vector"] == [1, 1, 1] for row in _parse(tmp_path, fixture))


def test_one_endpoint_seed_propagates_to_the_subdivided_actual_pipe_chain(tmp_path):
    fixture = _emitted_study(tmp_path, subdivided=True)
    assert (tmp_path / "study.comm").read_text().count("CARA='GENE_TUYAU'") == 2
    rows = {row["element_id"]: row for row in _parse(tmp_path, fixture)}
    assert rows["pipe_x_tail"]["generatrice"] == rows["pipe_x"]["generatrice"]
    assert rows["pipe_z"]["generatrice"]["vector"] == [0, 1, 0]
    np.testing.assert_allclose(rows["pipe_x_tail"]["display_position"], [1, 0, 0.04])


def test_old_repeated_global_seeds_on_connected_members_remain_compatible(tmp_path):
    fixture = _emitted_study(tmp_path, subdivided=True)
    model, _, _, _, names = fixture
    (tmp_path / "study.comm").write_text("\n".join(
        f"_F(GROUP_NO={names[f'G_NODE_{node}']!r}, CARA='GENE_TUYAU', VALE=(1, 1, 1))"
        for node in (model.elements[0].n1, model.elements[0].n2)))
    path = tmp_path / "study_manifest.json"
    payload = json.loads(path.read_text())
    payload["study"]["metadata"]["compiler_inputs"].pop("pipe_generatrices")
    path.write_text(json.dumps(payload))
    assert all(row["generatrice"]["vector"] == [1, 1, 1] for row in _parse(tmp_path, fixture))


def test_reader_uses_nested_recorded_chain_metadata_from_earlier_manifest_shape(tmp_path):
    fixture = _emitted_study(tmp_path)
    path = tmp_path / "study_manifest.json"
    payload = json.loads(path.read_text())
    inputs = payload["study"]["metadata"]["compiler_inputs"]
    inputs["resolved_loads"] = {"pipe_generatrices": inputs.pop("pipe_generatrices")}
    path.write_text(json.dumps(payload))
    assert len(_parse(tmp_path, fixture)) == 2


def test_authored_pipe_meshed_as_solid_does_not_require_a_tuyau_seed(tmp_path):
    fixture = _emitted_study(tmp_path)
    model = fixture[0]
    start, end = model.add_node([5, 0, 0]), model.add_node([6, 0, 0])
    model.add_element(id="solid_pipe", type="pipe_straight", n1=start, n2=end,
                      section="Annulus", material="Steel")
    with (tmp_path / "study_sieq.csv").open("a") as stream:
        stream.write("\nsolid_pipe,1,,5,0,0,12")
    assert len(_parse(tmp_path, fixture)) == 2


def test_scoped_seed_cannot_point_to_an_interior_chain_node(tmp_path):
    fixture = _emitted_study(tmp_path, subdivided=True)
    model, _, _, _, names = fixture
    path = tmp_path / "study.comm"
    path.write_text(path.read_text().replace(names[f"G_NODE_{model.elements[0].n1}"],
                                            names[f"G_NODE_{model.elements[0].n2}"]))
    with pytest.raises(RuntimeError, match="GENE_TUYAU.*endpoint"):
        _parse(tmp_path, fixture)


@pytest.mark.parametrize("problem", ["comm_vector", "metadata", "actual_node", "absent_comm"])
def test_scoped_orientation_must_match_the_recorded_solver_input(tmp_path, problem):
    fixture = _emitted_study(tmp_path)
    manifest = tmp_path / "study_manifest.json"
    payload = json.loads(manifest.read_text())
    if problem == "comm_vector":
        path = tmp_path / "study.comm"
        path.write_text(path.read_text().replace("0.00000000E+00, 0.00000000E+00, 1.00000000E+00",
                                                "1.00000000E+00, 1.00000000E+00, 1.00000000E+00"))
    elif problem == "metadata":
        payload["study"]["metadata"]["compiler_inputs"]["pipe_generatrices"][0]["element_ids"] = ["pipe_z"]
    elif problem == "actual_node":
        node = fixture[0].elements[0].n1
        payload["analysis_mesh"]["groups"][f"G_NODE_{node}"] = ["VN2"]
    else:
        (tmp_path / "study.comm").unlink()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="GENE_TUYAU"):
        _parse(tmp_path, fixture)


def test_beam_stress_rows_never_become_tuyau_sector_samples(tmp_path):
    fixture = _emitted_study(tmp_path)
    model = fixture[0]
    model.add_element(id="frame", type="beam", n1=model.elements[0].n1,
                      n2=model.elements[0].n2, section="Annulus", material="Steel")
    with (tmp_path / "study_sieq.csv").open("a") as stream:
        stream.write("\nframe,1,1,0,0,0,12")
    assert len(_parse(tmp_path, fixture)) == 2
