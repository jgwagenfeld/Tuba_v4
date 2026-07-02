"""Operating-state clash export workflow requiring real Code_Aster artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tuba import Model
from tuba.solver.aster import CodeAsterSolver


def build_model() -> tuple[Model, str, str]:
    model = Model(project_name="OperatingStateClashExample")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.10, WT=0.01)
    model.add_insulation_spec("mw_30", material="mineral_wool", thickness_m=0.03, density_kg_m3=110.0)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([2.0, 0.0, 0.0])
    model.add_element(id="pipe_hot_0", type="pipe_straight", n1=n0, n2=n1, section="DN100", material="Steel")
    model.assign_insulation("element:pipe_hot_0", "mw_30")
    model.add_support(node=n0, type="anchor", id="support_anchor_0")
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
    model.add_obstacle(
        id="rack_member_0",
        type="cuboid",
        min_point=[0.9, 0.11, -0.12],
        max_point=[1.1, 0.25, 0.12],
    )
    return model, n0, n1


def run_example(output_dir: str | Path = ".benchmarks/operating_state_clash_example") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, _n0, _n1 = build_model()

    study = CodeAsterSolver(work_dir=str(output_path / "code_aster")).export_analysis_study(
        model,
        "Hot",
        output_dir=output_path / "code_aster",
    )
    raise RuntimeError(
        "Operating-state clash review requires real Code_Aster result artifacts. "
        f"Exported the study to {study.work_dir}. Execute study.export with Code_Aster, "
        "then import the generated result tables before building operating geometry states."
    )


def main() -> int:
    run_example()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
