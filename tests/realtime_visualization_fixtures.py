from __future__ import annotations

"""Reusable fixtures for realtime visualization roadmap tests."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tuba import Model
from tuba.clash import ClashEngine
from tuba.analysis import (
    AnalysisMesh,
    GeometryState,
    ResultState,
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.clash import ClashResult
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import SceneBundle, VisualizationScene, build_visualization_scene, write_scene_bundle


@dataclass(frozen=True)
class RealtimeVisualizationFixture:
    output_dir: Path
    model: Model
    study: Any
    analysis_mesh: AnalysisMesh
    result_state: ResultState
    cold_state: GeometryState
    operating_state: GeometryState
    visual_state: GeometryState
    operating_clashes: list[ClashResult]
    scene: VisualizationScene
    bundle: SceneBundle
    expected_counts: dict[str, int]


def operating_state_review_fixture(output_dir: Path) -> RealtimeVisualizationFixture:
    output_dir.mkdir(parents=True, exist_ok=True)
    model, n0, n1 = _build_fixture_model()
    study_dir = output_dir / "code_aster"
    study = CodeAsterSolver(work_dir=str(study_dir)).export_analysis_study(
        model,
        "Hot",
        output_dir=study_dir,
    )
    manifest_path = study_dir / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis_mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])
    result_state = _mock_result_state(study=study, manifest_path=manifest_path, n0=n0, n1=n1)
    cold_state = create_cold_geometry_state(model)
    operating_state = create_operating_geometry_state(model=model, result_state=result_state)
    visual_state = create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=50.0)
    operating_clashes = ClashEngine().check_operating_state(
        model,
        cold_state=cold_state,
        operating_state=operating_state,
        result_state=result_state,
        envelope_type="insulation",
        analysis_mesh=analysis_mesh,
    )
    scene = build_visualization_scene(
        model,
        analysis_meshes=[analysis_mesh],
        operating_clash_results=operating_clashes,
        result_states=[result_state],
        geometry_states=[cold_state, operating_state, visual_state],
        scene_id="scene:realtime_visualization_fixture",
        created_at="2026-06-21T00:00:00Z",
    )
    bundle = write_scene_bundle(scene, output_dir / "review_scene")
    expected_counts = {
        "analysis_mesh_nodes": len(analysis_mesh.nodes),
        "analysis_mesh_elements": len(analysis_mesh.elements),
        "operating_clashes": len(operating_clashes),
        "scene_objects": len(scene.objects),
        "scene_geometry_assets": len(scene.geometry_assets),
        "scene_overlays": len(scene.overlays),
        "scene_issues": len(scene.issues),
    }
    return RealtimeVisualizationFixture(
        output_dir=output_dir,
        model=model,
        study=study,
        analysis_mesh=analysis_mesh,
        result_state=result_state,
        cold_state=cold_state,
        operating_state=operating_state,
        visual_state=visual_state,
        operating_clashes=operating_clashes,
        scene=scene,
        bundle=bundle,
        expected_counts=expected_counts,
    )


def _build_fixture_model() -> tuple[Model, str, str]:
    model = Model(project_name="RealtimeVisualizationFixture")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5, allowable_stress={20.0: 137e6})
    model.add_pipe_section("DN100", OD=0.10, WT=0.01)
    model.add_insulation_spec("mw_30", material="mineral_wool", thickness_m=0.03, density_kg_m3=110.0, cost_per_m=16.0)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([2.0, 0.0, 0.0])
    model.add_element(id="pipe_hot_0", type="pipe_straight", n1=n0, n2=n1, section="DN100", material="Steel")
    model.assign_insulation("element:pipe_hot_0", "mw_30", source="rv01_fixture")
    model.add_support(node=n0, type="anchor", id="support_anchor_0")
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
    model.add_obstacle(
        id="rack_member_0",
        type="cuboid",
        min_point=[0.9, 0.11, -0.12],
        max_point=[1.1, 0.25, 0.12],
    )
    return model, n0, n1


def _mock_result_state(*, study: Any, manifest_path: Path, n0: str, n1: str) -> ResultState:
    return ResultState(
        id="result_state:Hot:rv01_mock",
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
        element_results={
            "pipe_hot_0": {
                "forces_n1": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "forces_n2": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "von_mises_n1": 42.0e6,
                "von_mises_n2": 57.0e6,
                "max_von_mises": 57.0e6,
            },
        },
        files={"manifest": str(manifest_path)},
        metadata={"source": "rv01_fixture_mock_result_state"},
    )
