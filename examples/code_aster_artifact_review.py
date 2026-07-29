"""Build an engineering review and web scene from real Code_Aster artifacts.

The default input is the committed, solved ``VizGalleryDemo`` artifact set used
by the matching notebooks. Production review values must come from a real
Code_Aster run/import. Deterministic generated tables are available only through
the explicit ``test_fixture_mode`` and are non-engineering test data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model
from tuba.analysis import (
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.analysis.code_aster_artifacts import (
    import_code_aster_artifacts,
    stage_code_aster_artifact_evidence,
)
from tuba.reporting import build_engineering_review
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import (
    build_visualization_scene,
    write_engineering_review_with_scene,
)


def run_example(
    output_dir: str | Path = ".benchmarks/code_aster_artifact_review",
    *,
    artifact_dir: str | Path | None = None,
    test_fixture_mode: bool = False,
) -> dict[str, Any]:
    """Write the review package without running Code_Aster.

    ``artifact_dir`` must contain solved Code_Aster outputs matching the model.
    ``test_fixture_mode`` is reserved for portable automated tests and must not
    be used for engineering review or published result artifacts.
    """
    if artifact_dir is not None and test_fixture_mode:
        raise ValueError("artifact_dir and test_fixture_mode are mutually exclusive")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if test_fixture_mode:
        model, n0, n1 = _build_fixture_model()
        resolved_artifact_dir = output_path / "non_engineering_test_fixture"
        CodeAsterSolver(work_dir=resolved_artifact_dir).export_analysis_study(
            model, "Hot", resolved_artifact_dir
        )
        _write_sample_result_tables(resolved_artifact_dir, n0=n0, n1=n1)
        artifact_provenance = "deterministic_non_engineering_test_fixture"
    else:
        model = build_model()
        resolved_artifact_dir = (
            Path(artifact_dir)
            if artifact_dir is not None
            else Path(__file__).resolve().parents[1]
            / "notebooks"
            / "code_aster_results"
            / "viz_gallery_operating"
        )
        artifact_provenance = (
            "provided_real_code_aster_artifacts"
            if artifact_dir is not None
            else "committed_real_code_aster_artifacts"
        )

    artifact = import_code_aster_artifacts(model=model, work_dir=resolved_artifact_dir)
    if test_fixture_mode:
        artifact.result_state.metadata["source"] = artifact_provenance
        artifact.result_state.metadata["provenance_warning"] = (
            "Non-engineering test fixture; values are deterministic generated test data."
        )
        solved_at = None
    else:
        solved_at = artifact.result_state.metadata["solve_attestation"]["solved_at"]
    if not test_fixture_mode:
        artifact = stage_code_aster_artifact_evidence(artifact, output_path / "review_scene")
    operating_state = create_operating_geometry_state(model=model, result_state=artifact.result_state)
    visual_state = create_visual_deformed_geometry_state(model=model, result_state=artifact.result_state, visual_scale=40.0)
    scene = build_visualization_scene(
        model,
        analysis_meshes=[artifact.analysis_mesh] if artifact.analysis_mesh is not None else [],
        result_states=[artifact.result_state],
        geometry_states=[operating_state, visual_state],
        field_notes=[
            {
                "id": "review_scope",
                "title": "Review scope",
                "text": "Code_Aster result review; source artifacts are bundled below.",
                "position": [0.0, 0.0, 0.0],
            }
        ],
        scene_id="scene:code_aster_artifact_review",
        created_at=solved_at,
    )
    review = build_engineering_review(
        model,
        studies=[artifact.study],
        analysis_meshes=(
            [artifact.analysis_mesh] if artifact.analysis_mesh is not None else []
        ),
        result_states=[artifact.result_state],
        package_id="review:code_aster_artifact",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output_path / "review_scene",
        scene=scene,
        title="Code_Aster artifact engineering review",
    )
    summary = {
        "project_name": model.project_name,
        "study_id": artifact.study.id,
        "artifact_dir": str(resolved_artifact_dir),
        "artifact_provenance": artifact_provenance,
        "result_source": artifact.result_state.metadata["source"],
        "result_state_id": artifact.result_state.id,
        "bundle_root": str(bundle.root),
        "scene": str(bundle.root / bundle.scene_uri),
        "diagnostics": artifact.diagnostics,
        "counts": {
            "scene_objects": len(scene.objects),
            "scene_geometry_assets": len(scene.geometry_assets),
            "scene_overlays": len(scene.overlays),
            "scene_issues": len(scene.issues),
        },
    }
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def build_model() -> Model:
    """Rebuild the model that produced ``viz_gallery_operating`` artifacts."""
    model = Model("VizGalleryDemo", standard="ASME_B31.3")
    model.add_material(
        "Steel",
        E=2.1e11,
        nu=0.3,
        rho=7850.0,
        alpha=1.2e-5,
        allowable_stress={20.0: 137e6, 150.0: 127e6},
    )
    model.add_pipe_section(
        "DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001
    )
    model.define_load_case(
        "Operating",
        gravity=True,
        pressure=1.5e6,
        temperature=150.0,
        ref_temperature=20.0,
    )
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(3.0)
        builder.add_support(type="guide")
        builder.bend(radius=0.3, angle=90.0, plane="XY")
        builder.run(2.0)
        builder.add_support(type="rest")
        builder.bend(radius=0.3, angle=90.0, plane="XZ")
        builder.run(2.0)
        builder.end(support="anchor")
    model.validate()
    return model


def _build_fixture_model():
    """Build the small model used only by the non-engineering test fixture."""
    model = Model(project_name="CodeAsterArtifactReview")
    model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
    model.add_support(node=n0, type="anchor", id="support_anchor_0")
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model, n0, n1


def _write_sample_result_tables(work_dir: Path, *, n0: str, n1: str) -> None:
    """Write deterministic non-engineering tables for explicit tests only."""
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "study_depl.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},0.0,0.0,0.0,0.0,0.0,0.0",
                f"{n1},0.0,0.012,0.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_effo.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                f"pipe_0,{n0},8.0,15.0,20.0,1.0,2.0,3.0",
                f"pipe_0,{n1},9.0,16.0,21.0,4.0,5.0,6.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_reac.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},900.0,0.0,-300.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_sieq.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,VMIS",
                f"pipe_0,{n0},76000000.0",
                f"pipe_0,{n1},118000000.0",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
