"""Model facade seams: linkage, solve dispatch, and coupling live outside tuba.model."""

import pytest

from tuba import Model


def test_line_linkage_lives_in_codelink():
    import tuba.codelink as codelink
    import tuba.model as model_module

    assert callable(codelink.script_lines)
    assert not hasattr(model_module, "_script_lines")
    assert not hasattr(model_module, "_inside_tuba")


def test_solve_dispatch_lives_in_solver_adapter():
    from tuba.solver import model_solve

    assert callable(model_solve.solve_model)
    # Argument routing needs no solver runtime: conflicting selectors fail fast.
    with pytest.raises(ValueError, match="either load_case or operation"):
        Model(project_name="Seam").solve(load_case="Hot", operation="Hot")


def test_pipe_port_coupling_lives_in_mixed():
    import tuba.mixed as mixed

    assert callable(mixed.connect_pipe_to_port)
