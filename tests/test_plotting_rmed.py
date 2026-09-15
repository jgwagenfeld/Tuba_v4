from pathlib import Path

import numpy as np

from tuba.plotting import pipeline
from tuba.plotting import plots
from tuba.plotting.plots import _get_mesh
from tuba.solver.base import FEAResults


ROOT = Path(__file__).resolve().parents[1]
RMED = ROOT / "examples" / "code-aster-review" / "evidence" / "Operating" / "study.rmed"
MIXED_RMED = ROOT / "examples" / "elements-supports-review" / "evidence" / "LoadCase1" / "study.rmed"


def test_load_rmed_preserves_quadratic_lines_and_normalizes_latest_results(monkeypatch):
    read = pipeline.meshio.read
    calls = []

    def read_med(path, *, file_format=None):
        calls.append((Path(path), file_format))
        return read(path, file_format=file_format)

    monkeypatch.setattr(pipeline.meshio, "read", read_med)

    grid = pipeline.load_rmed(str(RMED))

    assert calls == [(RMED, "med")]
    # The rest is solved as a contact shoe: a helper node and a two-node line
    # from it to the pipe, which is cell 0. The pipe edges stay quadratic.
    assert grid.n_points == 72
    assert grid.n_cells == 36
    assert set(grid.celltypes) == {3, 21}  # VTK_LINE, VTK_QUADRATIC_EDGE
    assert list(grid.get_cell(1).point_ids) == [1, 2, 37]
    # Reference values from the artifacts re-solved with gravity along -Z. The
    # values before that were computed with gravity along -Y, which loaded this
    # line across itself rather than down it.
    #
    # Re-solved again once a rest support started emitting the warping restraint
    # every other support type already got. The two in-plane components moved by
    # about 0.16%; DZ is unchanged to eight decimals, which is what a secondary
    # section effect should look like.
    #
    # Re-solved once more when the riser to the far anchor grew from 2 m to 3 m.
    #
    # Re-solved again when the rest became a contact shoe.
    np.testing.assert_allclose(
        grid.point_data["DEPL"][-1],
        [0.003312064928, 0.007295506559, -0.004043201424],
        rtol=0,
        atol=5e-8,
    )
    # The longer riser raised peak displacement about 21% and lowered peak von Mises 0.3%.
    # The shoe raised peak displacement about 44% and peak von Mises about 5%.
    assert np.isclose(grid.point_data["DEPL_magnitude"].max(), 0.00909002553351697)
    # The shoe's helper node carries no stress, so its VMIS is NaN.
    assert np.flatnonzero(np.isnan(grid.point_data["VMIS"])).tolist() == [0]
    assert np.isclose(np.nanmax(grid.point_data["VMIS"]), 349965981.94583714)


def test_load_rmed_keeps_mixed_element_n5_displacement_and_elno_stress():
    grid = pipeline.load_rmed(str(MIXED_RMED))

    n5_matches = np.flatnonzero(np.all(np.isclose(grid.points, [4.7, 1.7, 0.0]), axis=1))
    assert n5_matches.size == 1
    # The free cable end sags along -Z, not +Y: an earlier assertion here pinned
    # a gravity-direction defect in place.
    #
    # The value moved again, and hard, when line_segments=8 became the default:
    # Uz went +0.0568 -> -0.1885 and Ux -0.00287 -> +0.00502. A cable meshed as
    # one span cannot sag - it carries self-weight as pure axial stretch, and
    # the old number was that artifact. With interior nodes the cable hangs, so
    # the displacement is downward and roughly three times larger. Uy stays at
    # zero either way, which is the invariant this test is really guarding.
    #
    # Re-solved when the rest became a contact shoe and the spring and support
    # mass moved onto their own nodes: Ux 0.00502 -> 0.00473, Uz -0.1885 -> -0.1855.
    # Re-solved with shoes converged as tightly as load paths: Ux +1.1e-8, Uz -2.1e-7.
    np.testing.assert_allclose(
        grid.point_data["DEPL"][n5_matches[0]],
        [0.004727627556, 0.0, -0.185451764522],
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
