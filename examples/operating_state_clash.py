"""End-to-end operating-state clash workflow without running Code_Aster."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model, TrimeshClashEngine
from tuba.analysis import (
    ResultState,
    create_cold_geometry_state,
    create_operating_geometry_state,
)
from tuba.geometry.deformed import build_deformed_envelopes
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization.bcf import export_bcf_topics
from tuba.visualization.builders import build_visualization_scene


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
    model, n0, n1 = build_model()

    study = CodeAsterSolver(work_dir=str(output_path / "code_aster")).export_analysis_study(
        model,
        "Hot",
        output_dir=output_path / "code_aster",
    )
    result_state = ResultState(
        id="result_state:Hot:mock",
        study_id=study.id,
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=study.mesh_id,
        node_displacements={
            n0: (0.0, 0.05, 0.0, 0.0, 0.0, 0.0),
            n1: (0.0, 0.05, 0.0, 0.0, 0.0, 0.0),
        },
        node_reactions={
            n0: (1000.0, 250.0, 0.0, 0.0, 0.0, 0.0),
        },
        element_results={},
        files={"manifest": str(output_path / "code_aster" / "study_manifest.json")},
        metadata={"source": "mock_result_state_for_example"},
    )
    cold_state = create_cold_geometry_state(model)
    operating_state = create_operating_geometry_state(model=model, result_state=result_state)
    envelopes = build_deformed_envelopes(
        model=model,
        result_state=result_state,
        geometry_state=operating_state,
        envelope_type="insulation",
    )
    clashes = TrimeshClashEngine().check_operating_state(
        model,
        cold_state=cold_state,
        operating_state=operating_state,
        result_state=result_state,
        envelope_type="insulation",
    )
    scene = build_visualization_scene(
        model,
        operating_clash_results=clashes,
        result_states=[result_state],
        geometry_states=[cold_state, operating_state],
    )
    scene_path = output_path / "operating_state_scene.json"
    bcf_path = output_path / "operating_state_clash.bcfzip"
    scene_path.write_text(json.dumps(scene.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    export_bcf_topics(scene, bcf_path)

    return {
        "project_name": model.project_name,
        "study_id": study.id,
        "manifest": str(output_path / "code_aster" / "study_manifest.json"),
        "result_state_id": result_state.id,
        "geometry_state_id": operating_state.id,
        "envelopes": len(envelopes),
        "clashes": [clash.to_dict() for clash in clashes],
        "scene": str(scene_path),
        "bcf": str(bcf_path),
    }


def main() -> int:
    summary = run_example()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
