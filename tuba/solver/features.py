"""Solver capability gate.

A model can legitimately describe behaviour Tuba cannot yet hand to
Code_Aster. When that happens the export must stop and say so. Writing input
files that quietly omit the requested physics is worse than refusing: the run
succeeds, the numbers look ordinary, and nothing in the result says the
behaviour was dropped.
"""

from __future__ import annotations

from typing import Any


#: Supports whose friction semantics are defined. Friction on other support
#: types would need its own normal-force and preload treatment, so a guide or
#: a stop must not silently inherit shoe behaviour.
FRICTION_CAPABLE_SUPPORT_TYPES = frozenset({"rest"})


def reject_unsupported_features(model: Any) -> None:
    """Stop an export that would discard physics the model asked for.

    Raises
    ------
    NotImplementedError
        When the model requests behaviour the Code_Aster writer cannot emit.
    """
    frictional = [
        support
        for support in getattr(model, "supports", [])
        if float(getattr(support, "friction_coefficient", 0.0) or 0.0) > 0.0
    ]
    if not frictional:
        return

    nodes = ", ".join(sorted({str(support.node) for support in frictional}))
    raise NotImplementedError(
        "Code_Aster export does not yet emit a friction law, so a positive "
        f"friction_coefficient would be silently ignored. Supports at: {nodes}. "
        "Requesting friction currently only switches the analysis to "
        "STAT_NON_LINE, which solves the model frictionless. Set "
        "friction_coefficient=0.0 to export the frictionless model explicitly, "
        "or wait for native DIS_CONTACT friction support."
    )
