from pathlib import Path

import numpy as np

from tuba.plotting import pipeline
from tuba.plotting import plots
from tuba.plotting.plots import _get_mesh
from tuba.solver.base import FEAResults


ROOT = Path(__file__).resolve().parents[1]
RMED = ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating" / "study.rmed"
MIXED_RMED = (
    ROOT
    / "notebooks"
    / "code_aster_results"
    / "elements_supports_loadcase1"
    / "study.rmed"
)


def test_load_rmed_preserves_quadratic_lines_and_normalizes_latest_results(monkeypatch):
    read = pipeline.meshio.read
    calls = []

    def read_med(path, *, file_format=None):
        calls.append((Path(path), file_format))
        return read(path, file_format=file_format)

    monkeypatch.setattr(pipeline.meshio, "read", read_med)

    grid = pipeline.load_rmed(str(RMED))

    assert calls == [(RMED, "med")]
    assert grid.n_points == 71
    assert grid.n_cells == 35
    assert set(grid.celltypes) == {21}  # VTK_QUADRATIC_EDGE
    assert list(grid.get_cell(0).point_ids) == [0, 1, 36]
    # Reference values from the artifacts re-solved with gravity along -Z. The
    # previous values were computed with gravity along -Y, which loaded this
    # line across itself rather than down it.
    np.testing.assert_allclose(
        grid.point_data["DEPL"][-1],
        [0.000396264522, 0.00357104759, -0.003109002647],
        rtol=0,
        atol=5e-8,
    )
    assert np.isclose(grid.point_data["DEPL_magnitude"].max(), 0.0051846816136452475)
    assert np.isclose(grid.point_data["VMIS"].max(), 333033617.25262654)


def test_load_rmed_keeps_mixed_element_n5_displacement_and_elno_stress():
    grid = pipeline.load_rmed(str(MIXED_RMED))

    n5_matches = np.flatnonzero(np.all(np.isclose(grid.points, [4.7, 1.7, 0.0]), axis=1))
    assert n5_matches.size == 1
    # The free cable end sags along -Z now, not +Y: this assertion pinned the
    # gravity-direction defect in place, so it is the value that had to move.
    np.testing.assert_allclose(
        grid.point_data["DEPL"][n5_matches[0]],
        [-0.002867512969, 0.0, 0.056817038551],
        rtol=2e-6,
    )
    assert abs(grid.point_data["DEPL"][n5_matches[0]][1]) < 1e-9, "no sag across the model"
    assert np.isfinite(grid.point_data["VMIS"]).any()


def test_result_file_is_loaded_instead_of_rebuilding_from_the_model(monkeypatch):
    sentinel = object()
    results = FEAResults(
        solver_name="code_aster",
        result_file=RMED,
        _model=object(),
    )
    monkeypatch.setattr(pipeline, "load_rmed", lambda path: sentinel)
    monkeypatch.setattr(
        pipeline,
        "build_3d_mesh_from_model",
        lambda *_args: (_ for _ in ()).throw(AssertionError("model reconstruction must not run")),
    )

    assert _get_mesh(results) is sentinel


def test_public_deformed_stress_quick_look_prefers_raw_rmed(monkeypatch):
    calls = []
    load = pipeline.load_rmed

    def load_raw(path):
        calls.append(Path(path))
        return load(path)

    class Plotter:
        def add_mesh(self, *_args, **_kwargs):
            pass

        def show(self, **kwargs):
            return kwargs

    monkeypatch.setattr(pipeline, "load_rmed", load_raw)
    monkeypatch.setattr(plots, "_make_plotter", lambda _title: Plotter())
    monkeypatch.setattr(
        "tuba.plotting.scenes.build_model_scene",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("public raw-RMED quick-look must not rebuild from the model")
        ),
    )
    results = FEAResults(solver_name="code_aster", result_file=RMED, _model=object())

    shown = results.plot_deformed_stress(deform_scale=2.0, off_screen=True)

    assert calls == [RMED]
    assert shown == {"off_screen": True}


def test_public_deformed_stress_keeps_model_only_fallback(monkeypatch):
    model = object()
    calls = []

    class Plotter:
        def show(self, **kwargs):
            return kwargs

    def build_model_scene(actual_model, actual_results, **kwargs):
        calls.append((actual_model, actual_results, kwargs))
        return Plotter()

    monkeypatch.setattr("tuba.plotting.scenes.build_model_scene", build_model_scene)
    results = FEAResults(solver_name="code_aster", _model=model)

    shown = results.plot_deformed_stress(deform_scale=3.0, off_screen=True)

    assert calls == [
        (
            model,
            results,
            {"off_screen": False, "title": "Deformed Stress", "deform_scale": 3.0},
        )
    ]
    assert shown == {"off_screen": True}
