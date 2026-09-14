"""Reaction parsing at a support node that has no rotational freedom.

A guy cable anchors into the ground through CABLE elements, which carry three
translational degrees of freedom and no rotations. Code_Aster prints ``-`` for
DRX/DRY/DRZ at such a node, and the reaction parser used to reject the row as
corrupt - so a guyed structure could solve cleanly and still fail on import.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.solver.base import FEAResults, NodeResult
from tuba.solver.aster import CodeAsterSolver


_HEADER = "RESULTAT,NOM_CHAM,INST,NUME_ORDRE,NOEUD,COOR_X,COOR_Y,COOR_Z,DX,DY,DZ,DRX,DRY,DRZ"


def _mast_with_one_guy() -> Model:
    model = Model("Cable_Anchor_Reactions")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, rho=7850)
    model.add_pipe_section("MastSec", OD=0.2, WT=0.008)
    model.add_cable_section("GuySec", radius=0.006, pretension=5000.0)

    with model.pipe(section="MastSec", material="Steel") as mast:
        mast.start([0.0, 0.0, 0.0], support="anchor")
        mast.set_direction([0.0, 0.0, 1.0])
        mast.beam(5.0)

    with model.pipe(section="GuySec", material="Steel") as guy:
        guy.start([0.0, 0.0, 5.0])
        guy.set_direction([3.0, 0.0, -5.0])
        guy.cable(5.830951894845301)
        model.add_support(node=guy.last_node_id, type="anchor")

    model.define_load_case("Wind", gravity=True)
    return model


def _row(node: str, translations: tuple[float, float, float], rotations: str | tuple[float, float, float]) -> str:
    rotation_text = (
        ",-,-,-" if rotations == "absent" else "," + ",".join(f"{value:.8E}" for value in rotations)
    )
    return (
        f"RESU,REAC_NODA,1.0,1,{node},0.0,0.0,0.0,"
        + ",".join(f"{value:.8E}" for value in translations)
        + rotation_text
    )


def _parse(model: Model, work_dir: Path, rows: list[str]) -> FEAResults:
    (work_dir / "study_reac.csv").write_text("\n".join([_HEADER, *rows]) + "\n", encoding="utf-8")
    results = FEAResults(solver_name="Code_Aster", load_case="Wind")
    for support in model.supports:
        results.node_results[support.node] = NodeResult(
            node_id=support.node, displacement=np.zeros(6)
        )
    CodeAsterSolver()._parse_reac_table(model, work_dir, results, {})
    return results


def test_a_cable_only_anchor_reports_zero_reaction_moments(tmp_path):
    """The absent rotational DOFs are a pin, so the reaction moments are zero."""
    model = _mast_with_one_guy()
    mast_base, guy_anchor = (support.node for support in model.supports)

    results = _parse(
        model,
        tmp_path,
        [
            _row(mast_base, (2.1e3, 0.0, 4.9e3), (0.0, 4.8e3, 0.0)),
            _row(guy_anchor, (-3.4e3, 0.0, 4.6e3), "absent"),
        ],
    )

    np.testing.assert_allclose(
        results.node_results[guy_anchor].reaction_force,
        [-3.4e3, 0.0, 4.6e3, 0.0, 0.0, 0.0],
    )
    # The mast base has beam elements and full rotational freedom; unchanged.
    np.testing.assert_allclose(
        results.node_results[mast_base].reaction_force,
        [2.1e3, 0.0, 4.9e3, 0.0, 4.8e3, 0.0],
    )


def test_a_missing_translation_is_still_rejected_at_a_cable_anchor(tmp_path):
    """The guard keeps its teeth: only the rotations a cable lacks may be absent."""
    model = _mast_with_one_guy()
    _mast_base, guy_anchor = (support.node for support in model.supports)

    with pytest.raises(RuntimeError, match="invalid reaction components"):
        _parse(model, tmp_path, [f"RESU,REAC_NODA,1.0,1,{guy_anchor},0.0,0.0,0.0,-,-,-,-,-,-"])


def test_absent_rotations_are_still_rejected_where_the_node_has_them(tmp_path):
    """A beam node printing "-" is a real problem, not a missing degree of freedom."""
    model = _mast_with_one_guy()
    mast_base, _guy_anchor = (support.node for support in model.supports)

    with pytest.raises(RuntimeError, match="invalid reaction components"):
        _parse(model, tmp_path, [_row(mast_base, (2.1e3, 0.0, 4.9e3), "absent")])
