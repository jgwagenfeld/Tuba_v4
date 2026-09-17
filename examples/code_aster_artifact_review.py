"""Build an engineering review and web scene from real Code_Aster artifacts.

The gallery studies (``examples/<project>/study.py``) share this pipeline: each
hands over its model and either attested artifacts to import or a run it has just
solved. The default input is the committed, solved ``VizGalleryDemo`` artifact set
used by the matching notebooks. Production review values must come from a real
Code_Aster run/import. Unattested generated tables cannot enter this workflow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from tuba import Model
from tuba.analysis import (
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.analysis.code_aster_artifacts import (
    import_code_aster_artifacts,
    stage_code_aster_artifact_evidence,
)
from tuba.clash import ClashEngine
from tuba.reporting import build_engineering_review
from tuba.load_path import analyze_load_paths
from tuba.project import load_project
from tuba.rules import RuleEngine
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import (
    SceneBuildOptions,
    build_visualization_scene,
    write_engineering_review_with_scene,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = ROOT / "examples" / "code-aster-review"


def solve_or_import(
    model: Model,
    load_case: str,
    work_dir: str | Path,
    *,
    artifact_dir: str | Path | None = None,
    solver_options: dict[str, Any] | None = None,
    volume_export: dict[str, Any] | None = None,
) -> Any:
    """Import attested evidence from ``artifact_dir``, or solve now with Code_Aster.

    The solve is the one the gallery refresh runs - export, solve, then import
    what Code_Aster actually wrote - so a studio solve carries the same
    attestation as the committed evidence.
    """
    if artifact_dir is not None:
        return import_code_aster_artifacts(model=model, work_dir=Path(artifact_dir))
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    solver = CodeAsterSolver(work_dir=work, **(solver_options or {}))
    study = (
        solver.export_volume_study(model, load_case, work, **volume_export, export_tensor_stress=False)
        if volume_export
        else solver.export_analysis_study(model, load_case, work)
    )
    solver.solve_exported_study(model, study)
    return import_code_aster_artifacts(model=model, work_dir=work, study=study)


def run_example(
    output_dir: str | Path = ".build/benchmarks/code_aster_artifact_review",
    *,
    artifact_dir: str | Path | None = None,
    run: Any | None = None,
    model: Model | None = None,
    scene_id: str = "scene:code_aster_artifact_review",
    title: str = "Code_Aster artifact engineering review",
    route_results: list[Any] | None = None,
    include_load_paths: bool = False,
    clash_clearance_m: float | None = None,
    model_rules: list[Any] | None = None,
    scene_options: SceneBuildOptions | None = None,
    scene_modifier: Callable[[Any], None] | None = None,
    source: str | Path | None = None,
) -> dict[str, Any]:
    """Write the review package without running Code_Aster.

    ``artifact_dir`` must contain attested, solved Code_Aster outputs matching
    the model. A ``run`` that was just solved (see :func:`solve_or_import`) is
    reviewed as it is instead. Without a ``model`` the review is of
    ``examples/code-aster-review``.

    ``clash_clearance_m`` runs the operating-state clash check against the
    imported displacement field using a clearance envelope of that radius.

    ``model_rules`` are engineer-authored design rules evaluated against the
    model. They annotate the review; they are not solver results and not a
    piping-code judgement.

    ``source`` names the authoring script published beside the scene; it
    defaults to the default project's ``model.py``. A caller that supplies its
    own model should name its own file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    resolved_model = model or load_project(DEFAULT_PROJECT).run_model()["model"]
    resolved_artifact_dir = (
        Path(artifact_dir)
        if artifact_dir is not None
        else DEFAULT_PROJECT / "evidence" / "Operating"
    )
    artifact_provenance = (
        "solved_in_this_run"
        if run is not None
        else "provided_real_code_aster_artifacts"
        if artifact_dir is not None
        else "committed_real_code_aster_artifacts"
    )

    artifact = run if run is not None else import_code_aster_artifacts(model=resolved_model, work_dir=resolved_artifact_dir)
    solved_at = artifact.result_state.metadata["solve_attestation"]["solved_at"]
    artifact = stage_code_aster_artifact_evidence(artifact, output_path / "review_scene")
    operating_state = create_operating_geometry_state(model=resolved_model, result_state=artifact.result_state)
    visual_state = create_visual_deformed_geometry_state(
        model=resolved_model,
        result_state=artifact.result_state,
        visual_scale=40.0,
    )
    operating_clashes = (
        ClashEngine().check_operating_state(
            resolved_model,
            cold_state=create_cold_geometry_state(resolved_model),
            operating_state=operating_state,
            result_state=artifact.result_state,
            envelope_type="clearance",
            clearance_m=clash_clearance_m,
            analysis_mesh=artifact.analysis_mesh,
        )
        if clash_clearance_m is not None
        else []
    )
    rule_report = RuleEngine(list(model_rules)).evaluate(resolved_model) if model_rules else None
    scene = build_visualization_scene(
        resolved_model,
        options=scene_options,
        analysis_runs=[artifact],
        operating_clash_results=operating_clashes,
        rule_results=rule_report.results if rule_report is not None else None,
        geometry_states=[operating_state, visual_state],
        field_notes=[
            {
                "id": "review_scope",
                "title": "Review scope",
                "text": "Code_Aster result review; source artifacts are bundled below.",
                "position": [0.0, 0.0, 0.0],
            }
        ],
        route_results=route_results,
        load_path_report=(
            analyze_load_paths(resolved_model, result_state=artifact.result_state)
            if include_load_paths
            else None
        ),
        scene_id=scene_id,
        created_at=solved_at,
    )
    if scene_modifier is not None:
        scene_modifier(scene)
    review = build_engineering_review(
        resolved_model,
        analysis_runs=[artifact],
        package_id="review:code_aster_artifact",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output_path / "review_scene",
        scene=scene,
        title=title,
        source=source if source is not None else DEFAULT_PROJECT / "model.py",
    )
    summary = {
        "project_name": resolved_model.project_name,
        "study_id": artifact.study.id,
        "artifact_dir": str(resolved_artifact_dir),
        "artifact_provenance": artifact_provenance,
        "result_source": artifact.result_state.metadata["source"],
        "result_state_id": artifact.result_state.id,
        "bundle_root": str(bundle.root),
        "scene": str(bundle.root / bundle.scene_uri),
        "diagnostics": artifact.diagnostics,
        "analysis_status": review.analysis_status,
        "operating_clashes": [clash.to_dict() for clash in operating_clashes],
        "model_rules": rule_report.to_dict() if rule_report is not None else None,
        "counts": {
            "scene_objects": len(scene.objects),
            "scene_geometry_assets": len(scene.geometry_assets),
            "scene_overlays": len(scene.overlays),
            "scene_issues": len(scene.issues),
        },
    }
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
