"""Solve dispatch for a model: argument routing to the Code_Aster solver adapter.

Owns how a ``solve()`` call turns into solver construction and study selection
(modelization choice, load-path handling, volume-study guards). ``TubaModel.solve``
keeps the documented interface and delegates here in one line.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from tuba.solver.modelisation import PipeModelization


def solve_model(
    model,
    load_case: Optional[str] = None,
    operation: Optional[str] = None,
    pipe_modelization: PipeModelization | str | None = None,
    load_path: Optional[Sequence[str]] = None,
    load_step: float = 0.1,
    volume_element_ids: Optional[Sequence[str]] = None,
    max_element_size: Optional[float] = None,
    force: bool = False,
    **kwargs: Any,
):
    """See :meth:`tuba.model.TubaModel.solve` for the interface contract."""
    if load_case is not None and operation is not None:
        raise ValueError("Pass either load_case or operation, not both.")

    from tuba.solver.aster import CodeAsterSolver

    lc_name = operation or load_case
    if load_path is not None:
        if load_case is not None or operation is not None or not load_path:
            raise ValueError('load_path must be nonempty and cannot be combined with load_case or operation.')
        lc_name = load_path[-1]
    selected_modelization = PipeModelization(pipe_modelization or PipeModelization.TUYAU_3M)
    if pipe_modelization is not None:
        kwargs['pipe_modelization'] = selected_modelization
    if load_path is not None:
        kwargs['load_path'] = load_path
    if load_path is not None or load_step != 0.1:
        kwargs['load_step'] = load_step
    solver = CodeAsterSolver(**kwargs)
    if selected_modelization is PipeModelization.SOLID_3D:
        if load_path is not None or any(s.friction_coefficient for s in model.supports):
            raise ValueError('Friction, gap, contact stiffness and load-path histories require a 1D study (TUYAU_3M or POU_D_T).')
        if not volume_element_ids or max_element_size is None:
            raise ValueError("SOLID_3D requires volume_element_ids and max_element_size.")
        return solver.solve_volume_study(
            model,
            lc_name,
            element_ids=volume_element_ids,
            max_element_size=max_element_size,
            force=force,
        )
    if volume_element_ids is not None or max_element_size is not None:
        raise ValueError("Volume mesh arguments require pipe_modelization=PipeModelization.SOLID_3D.")
    return solver.solve(model, lc_name, force=force)
