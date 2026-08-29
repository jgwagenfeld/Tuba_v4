"""Solved review of the mixed element and support types.

This is the only committed Code_Aster study that exercises bar, cable and
discrete-spring elements alongside pipe and beam elements, so it is the
gallery's evidence that Tuba's element and support translation reaches the
solver intact.

The model must stay byte-identical to the one that produced
``notebooks/code_aster_results/elements_supports_loadcase1``: the imported
artifacts are matched on a solver-input fingerprint, so any drift here makes
the committed evidence unusable rather than merely stale.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model

from examples.code_aster_artifact_review import run_example as run_artifact_review


ARTIFACT_DIR = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "code_aster_results"
    / "elements_supports_loadcase1"
)


def build_elements_supports_model() -> Model:
    """Rebuild the model that produced ``elements_supports_loadcase1``."""
    model = Model("Tuba_v4_Demo_Study")
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, rho=7850)

    model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
    model.add_bar_section("BarSec", OD=0.05, WT=0.0)
    model.add_cable_section("CableSec", radius=0.01, pretension=500.0)
    model.add_rectangular_section(
        "RectSec", height_y=0.08, height_z=0.04, thickness_y=0.005, thickness_z=0.005
    )
    model.add_ibeam_section("IBeamSec", "IPE100")

    with model.pipe(section="PipeSec", material="Steel") as builder:
        builder.start([0, 0, 0], support="anchor")
        builder.run(2.0)
        builder.bend(radius=0.2, angle=90, plane="XY")
        builder.run(1.5)

    with model.pipe(section="IBeamSec", material="Steel") as builder:
        builder.start([2.2, 1.7, 0]).beam(1.5)

    with model.pipe(section="BarSec", material="Steel") as builder:
        builder.start([3.7, 1.7, 0]).bar(1.0)

    with model.pipe(section="CableSec", material="Steel") as builder:
        builder.start([4.7, 1.7, 0]).cable(2.0)

    with model.pipe(section="RectSec", material="Steel") as builder:
        builder.start([6.7, 1.7, 0]).beam(1.2)

    model.add_support(node="N1", type="spring", stiffness_matrix=[0.0, 1.5e6, 0.0, 0.0, 0.0, 0.0])
    model.add_support(node="N2", type="custom", blocked_dof=[1, 1, 0, 0, 0, 1])
    model.add_support(node="N3", type="spring", stiffness_matrix=[1e5, 2e5, 3e5, 0.0, 0.0, 0.0])
    model.add_support(node="N4", type="rest", mass=50.0)
    model.add_support(node="N7", type="custom", blocked_dof=[1, 1, 1, 1, 1, 1])

    model.define_load_case("LoadCase1", gravity=True, pressure=1.0e6, temperature=120.0)
    return model


def run_example(
    output_dir: str | Path = ".build/benchmarks/elements_supports_review",
    *,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write the solved mixed-element review bundle."""
    return run_artifact_review(
        output_dir,
        artifact_dir=artifact_dir if artifact_dir is not None else ARTIFACT_DIR,
        model=build_elements_supports_model(),
        scene_id="scene:elements_supports_review",
        title="Solved mixed element and support review",
        source=__file__,
    )


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
