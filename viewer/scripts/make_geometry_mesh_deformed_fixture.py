#!/usr/bin/env python
"""Regenerate the ``geometry_mesh_deformed`` viewer test fixture.

The fixture exercises the composited geometry / mesh / sub-point / deformed
screen: a bent TUYAU run, so the bundle carries a real bend-chord discretisation
check, and a TUYAU sub-point field, so it carries a section profile and a peak.

The mesh, the layer taxonomy and the scene contract all come from the real
builders, so the fixture cannot drift from what Tuba actually emits.

The **result state is a deterministic test fixture, not a solve.** It is named
and tagged as one throughout, exactly like ``tests/realtime_visualization_fixtures``:
CI has to stay portable, and no Code_Aster runtime is available here. Nothing in
this file may be presented as a Code_Aster result.

Run from the repo root with the Tuba env active:

    python viewer/scripts/make_geometry_mesh_deformed_fixture.py
"""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from pathlib import Path

from tuba.analysis import AnalysisMesh, create_cold_geometry_state, create_visual_deformed_geometry_state
from tuba.analysis.results import ResultState
from tuba.analysis.tuyau import CODE_ASTER_TUYAU_NCOU, CODE_ASTER_TUYAU_NSEC, subpoint_station
from tuba.model import TubaModel as Model
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene, write_scene_bundle

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "test" / "fixtures" / "geometry_mesh_deformed"
FIXTURE_TAG = "gmd_fixture_not_a_solve"
OD = 0.1143
WT = 0.00602
BEND_RADIUS = 0.3429


def build_model() -> tuple[Model, list[str]]:
    """A straight run into a 90 degree bend into a riser."""
    model = Model(project_name="GeometryMeshDeformed", standard="ASME_B31.3")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5, allowable_stress={20.0: 137e6})
    model.add_pipe_section("DN100", OD=OD, WT=WT)
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(2.4)
        builder.bend(radius=BEND_RADIUS, angle=90, plane="XZ")
        builder.run(1.2)
        builder.end(support="anchor")
    model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=180.0, ref_temperature=20.0)
    return model, list(model.nodes)


def fixture_result_state(*, model: Model, study, manifest_path: Path, node_ids: list[str]) -> ResultState:
    """A deterministic stand-in for a solved state. Never a Code_Aster result."""
    anchor, tip = node_ids[0], node_ids[-1]
    displacements = {}
    for index, node_id in enumerate(node_ids):
        reach = index / max(len(node_ids) - 1, 1)
        displacements[node_id] = (0.0, 0.0, 0.0426 * reach**2, 0.0, 0.0, 0.0)

    elements = [element for element in model.elements if element.type.startswith("pipe")]
    element_results = {}
    for index, element in enumerate(elements):
        reach = index / max(len(elements) - 1, 1)
        peak = 70.0e6 + 130.0e6 * reach
        element_results[element.id] = {
            "forces_n1": [0.0] * 6,
            "forces_n2": [0.0] * 6,
            "von_mises_n1": peak * 0.82,
            "von_mises_n2": peak,
            "max_von_mises": peak,
        }

    return ResultState(
        id=f"result_state:Hot:{FIXTURE_TAG}",
        study_id=study.id,
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=study.mesh_id,
        node_displacements=displacements,
        node_reactions={anchor: (1200.0, 0.0, 3400.0, 0.0, 0.0, 0.0)},
        element_results=element_results,
        files={"manifest": str(manifest_path)},
        metadata={
            "source": FIXTURE_TAG,
            "tuyau_subpoints": tuyau_subpoint_rows(model, elements[-1].id, node_id=tip),
        },
    )


def tuyau_subpoint_rows(model: Model, element_id: str, *, node_id: str) -> list[dict]:
    """One ring of sub-point rows placed with the real fibre convention."""
    element = next(item for item in model.elements if item.id == element_id)
    centre = [float(value) for value in model.nodes[element.n2].coords]
    r_ext = OD / 2.0
    rows = []
    # A quarter of one layer plus one through-wall station: enough for the
    # section rosette to show measured points without inflating the fixture.
    indices = [1, 5, 9, 13, 17, 1 + 3 * (2 * CODE_ASTER_TUYAU_NSEC + 1), 9 + 6 * (2 * CODE_ASTER_TUYAU_NSEC + 1)]
    for subpoint_index in indices:
        station = subpoint_station(subpoint_index)
        radius = (r_ext - WT) + WT * station.radius_fraction
        rows.append(
            {
                "field": "SIEQ_ELNO",
                "component": "VMIS",
                "unit": "Pa",
                "value": 120.0e6 + 81.5e6 * (0.5 - 0.5 * math.cos(station.angle_rad)) * (0.4 + 0.6 * station.radius_fraction),
                "element_id": element_id,
                "analysis_element_id": element_id,
                "node_id": node_id,
                "subpoint_index": subpoint_index,
                "centerline_position": centre,
                "display_position": [
                    centre[0],
                    centre[1] + radius * math.cos(station.angle_rad),
                    centre[2] - radius * math.sin(station.angle_rad),
                ],
                "position_source": "code_aster_tuyau_subpoint_formula",
                "tuyau_ncou": CODE_ASTER_TUYAU_NCOU,
                "tuyau_nsec": CODE_ASTER_TUYAU_NSEC,
            }
        )
    return rows


def main() -> None:
    model, node_ids = build_model()
    with tempfile.TemporaryDirectory() as tmp:
        study_dir = Path(tmp) / "code_aster"
        study = CodeAsterSolver(work_dir=str(study_dir)).export_analysis_study(model, "Hot", output_dir=study_dir)
        manifest_path = study_dir / "study_manifest.json"
        analysis_mesh = AnalysisMesh.from_dict(json.loads(manifest_path.read_text(encoding="utf-8"))["analysis_mesh"])
        result_state = fixture_result_state(
            model=model, study=study, manifest_path=manifest_path, node_ids=node_ids
        )
        scene = build_visualization_scene(
            model,
            analysis_meshes=[analysis_mesh],
            result_states=[result_state],
            geometry_states=[
                create_cold_geometry_state(model),
                create_visual_deformed_geometry_state(model=model, result_state=result_state, visual_scale=50.0),
            ],
            scene_id="scene:geometry_mesh_deformed",
            created_at="2026-08-22T00:00:00Z",
        )
        staged = write_scene_bundle(scene, Path(tmp) / "bundle")
        staged_root = Path(staged.root if hasattr(staged, "root") else staged)
        if FIXTURE_DIR.exists():
            shutil.rmtree(FIXTURE_DIR)
        shutil.copytree(staged_root, FIXTURE_DIR)

    identity = next(
        (layer.extra["mesh_identity"] for layer in scene.layers if layer.extra.get("mesh_identity")), None
    )
    print(f"wrote {FIXTURE_DIR}")
    print(f"  objects={len(scene.objects)} overlays={len(scene.overlays)} layers={len(scene.layers)}")
    print(f"  element_families={identity and identity.get('element_families')}")
    print(f"  discretisation={identity and identity.get('discretisation', {}).get('worst_bend')}")


if __name__ == "__main__":
    main()
