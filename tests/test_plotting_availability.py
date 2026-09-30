from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.plotting import export, pipeline, plots
from tuba.plotting.scenes import build_model_scene
from tuba.solver.base import ElementResult, FEAResults, NodeResult


def _model(*, bend=False, two_members=False):
    model = Model(project_name="Result availability")
    model.add_material("Steel", E=2e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    with model.pipe(section="Pipe", material="Steel") as route:
        route.start([0, 0, 0]).run(1)
        if bend:
            route.bend(radius=0.2, angle=90, plane="XY")
        elif two_members:
            route.run(1)
    return model


def _zeros(model):
    results = FEAResults(solver_name="Code_Aster", _model=model)
    for node_id in model.nodes:
        # Rotations/moments can be unavailable on a valid translational field.
        vector = np.array([0., 0., 0., np.nan, np.nan, np.nan])
        results.node_results[node_id] = NodeResult(node_id, vector.copy(), vector.copy())
    for elem in model.elements:
        results.element_results[elem.id] = ElementResult(elem.id, np.zeros(6), np.zeros(6), 0., 0., 0.)
    return results


@pytest.mark.parametrize("builder", [pipeline.build_mesh_from_model, pipeline.build_3d_mesh_from_model])
def test_missing_records_are_nan_and_measured_zeros_survive(builder):
    model = _model()
    empty = builder(model, FEAResults(solver_name="Code_Aster"))
    for field in ["DEPL", "DEPL_magnitude", "VMIS", "FORC_NODA", "FORC_magnitude"]:
        assert np.isnan(empty.point_data[field]).all(), field
    complete = builder(model, _zeros(model))
    for field in ["DEPL", "DEPL_magnitude", "VMIS", "FORC_NODA", "FORC_magnitude"]:
        assert np.equal(complete.point_data[field], 0).all(), field


@pytest.mark.parametrize("builder", [pipeline.build_mesh_from_model, pipeline.build_3d_mesh_from_model])
def test_known_endpoint_is_retained_without_filling_the_missing_end(builder):
    model = _model()
    results = _zeros(model)
    elem = model.elements[0]
    del results.node_results[elem.n2]
    results.element_results[elem.id].von_mises_n2 = np.inf
    mesh = builder(model, results)
    for field in ["DEPL", "VMIS", "FORC_NODA"]:
        assert np.equal(mesh.point_data[field][np.isclose(mesh.points[:, 0], 0)], 0).all(), field
        assert np.isnan(mesh.point_data[field][np.isclose(mesh.points[:, 0], 1)]).all(), field


def test_bend_does_not_interpolate_unknown_endpoints_or_nodal_reactions():
    model = _model(bend=True)
    results = _zeros(model)
    bend = model.elements[-1]
    del results.node_results[bend.n2]
    del results.element_results[bend.id]
    mesh = pipeline.build_mesh_from_model(model, results)
    interior = slice(len(model.nodes), None)
    for field in ["DEPL", "VMIS", "FORC_NODA"]:
        assert np.isnan(mesh.point_data[field][interior]).all(), field
    shared = list(model.nodes).index(bend.n1)
    assert np.isnan(mesh.point_data["VMIS"][shared]), "missing incident member must not be averaged away"


def test_surface_merge_keeps_missing_member_stress_at_shared_endpoints():
    model = _model(two_members=True)
    results = _zeros(model)
    del results.element_results[model.elements[-1].id]
    mesh = pipeline.build_3d_mesh_from_model(model, results)
    shared = mesh.point_data["VMIS"][np.isclose(mesh.points[:, 0], 1)]
    assert np.isfinite(shared).any()
    assert np.isnan(shared).any(), "merging must not replace the missing member's endpoint data"


@pytest.mark.parametrize("method", ["plot_stress", "plot_deformed", "plot_displacement_vectors", "plot_deformed_stress", "plot_reactions"])
def test_public_plots_refuse_rmed_without_the_requested_field(monkeypatch, method):
    model = _model()
    mesh = pipeline.pv.PolyData([[0., 0., 0.], [1., 0., 0.]])
    monkeypatch.setattr(plots, "_get_mesh", lambda *_args: mesh)
    results = FEAResults(solver_name="Code_Aster", result_file=Path("missing-fields.rmed"), _model=model)
    with pytest.raises(ValueError, match="DEPL|VMIS|FORC_NODA"):
        getattr(results, method)(off_screen=True)


def test_deformed_model_scene_refuses_missing_displacement():
    model = _model()
    results = _zeros(model)
    results.node_results.clear()
    with pytest.raises(ValueError, match="DEPL"):
        build_model_scene(model, results, off_screen=True, deform_scale=2)
    geometry = build_model_scene(model, off_screen=True)
    geometry.close()


@pytest.mark.parametrize("writer", [export.export_blender_script, export.export_ply, export.export_gltf, export.export_html])
def test_result_exports_refuse_missing_stress_before_writing(tmp_path, writer):
    model = _model()
    results = _zeros(model)
    results.element_results.clear()
    path = tmp_path / "existing-output"
    path.write_text("keep this output", encoding="utf-8")
    with pytest.raises(ValueError, match="stress|VMIS"):
        writer(results, path, model=model)
    assert path.read_text(encoding="utf-8") == "keep this output"


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_blender_refuses_nonfinite_endpoint_stress(tmp_path, value):
    model = _model()
    results = _zeros(model)
    results.element_results[model.elements[0].id].von_mises_n2 = value
    path = tmp_path / "review.py"
    with pytest.raises(ValueError, match="stress"):
        export.export_blender_script(results, path)
    assert not path.exists()


def test_blender_retains_measured_zero_stress(tmp_path):
    model = _model()
    path = tmp_path / "review.py"
    export.export_blender_script(_zeros(model), path)
    assert "vmis = [0.0, 0.0]" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("builder", [pipeline.build_mesh_from_model, pipeline.build_3d_mesh_from_model])
def test_nonfinite_translation_is_unknown_without_rejecting_other_endpoint(builder):
    model = _model()
    results = _zeros(model)
    first = model.elements[0].n1
    results.node_results[first].displacement[1] = np.inf
    results.node_results[first].reaction_force[1] = np.inf
    mesh = builder(model, results)
    for field in ["DEPL", "FORC_NODA"]:
        assert np.isnan(mesh.point_data[field][np.isclose(mesh.points[:, 0], 0)]).all()
        assert np.equal(mesh.point_data[field][np.isclose(mesh.points[:, 0], 1)], 0).all()


@pytest.mark.parametrize("method, field", [("plot_displacement_vectors", "DEPL"), ("plot_reactions", "FORC_NODA")])
def test_raw_vector_plot_refuses_a_field_with_no_complete_xyz_vector(monkeypatch, method, field):
    model = _model()
    mesh = pipeline.pv.PolyData([[0., 0., 0.], [1., 0., 0.]])
    mesh.point_data[field] = [[1., np.nan, 0.], [0., np.nan, 1.]]
    monkeypatch.setattr(plots, "_get_mesh", lambda *_args: mesh)
    results = FEAResults(solver_name="Code_Aster", _model=model)
    with pytest.raises(ValueError, match=field):
        getattr(results, method)(off_screen=True)


def test_raw_rmed_html_keeps_annotated_unavailable_helper_node_stress(monkeypatch, tmp_path):
    from tests.test_plotting_rmed import RMED

    exported = []
    drawn = []

    class Plotter:
        def add_mesh(self, mesh, **kwargs):
            drawn.append((mesh, kwargs))

        def export_html(self, path):
            exported.append(path)

        def show(self, **kwargs):
            return kwargs

    monkeypatch.setattr(plots, "_make_plotter", lambda _title: Plotter())
    results = FEAResults(solver_name="Code_Aster", result_file=RMED)
    path = tmp_path / "review.html"
    results.plot_deformed_stress(export_html=path, off_screen=True)
    assert exported == [path]
    assert np.isnan(drawn[0][0].point_data["VMIS"]).any()
    assert drawn[0][1]["scalar_bar_args"]["nan_annotation"] is True


def test_default_html_refuses_incomplete_displacement_before_writing(tmp_path):
    model = _model()
    results = _zeros(model)
    results.node_results.clear()
    path = tmp_path / "review.html"
    with pytest.raises(ValueError, match="DEPL"):
        export.export_html(results, path)
    assert not path.exists()


def test_ply_retains_zero_stress_and_writes_real_vertex_colors(tmp_path):
    model = _model()
    path = tmp_path / "review.ply"
    export.export_ply(_zeros(model), path)
    mesh = pipeline.pv.read(path)
    assert mesh.n_points > 0
    assert "RGB" in mesh.point_data
    assert np.isfinite(mesh.point_data["RGB"]).all()


@pytest.mark.parametrize("method, field", [("plot_displacement_vectors", "DEPL"), ("plot_reactions", "FORC_NODA")])
def test_raw_vector_plot_masks_incomplete_xyz_and_ignores_missing_rotations(monkeypatch, method, field):
    model = _model()
    mesh = pipeline.pv.PolyData([[0., 0., 0.], [1., 0., 0.]])
    mesh.point_data[field] = [[1., 0., 0., np.nan, np.nan, np.nan], [0., np.nan, 1., np.nan, np.nan, np.nan]]
    drawn = []

    class Plotter:
        def add_mesh(self, data, **kwargs):
            drawn.append(data)

        def add_legend(self, **kwargs):
            pass

        def show(self, **kwargs):
            return kwargs

    monkeypatch.setattr(plots, "_get_mesh", lambda *_args: mesh)
    monkeypatch.setattr(plots, "_make_plotter", lambda _title: Plotter())
    results = FEAResults(solver_name="Code_Aster", _model=model)
    getattr(results, method)(off_screen=True)
    np.testing.assert_array_equal(mesh.point_data[field][0], [1, 0, 0])
    assert np.isnan(mesh.point_data[field][1]).all()
    assert len(drawn) == 2
    assert drawn[-1].n_points > 0
    assert np.isfinite(drawn[-1].points).all()
