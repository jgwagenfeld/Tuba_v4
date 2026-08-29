"""Build an engineering review and web scene from real Code_Aster artifacts.

The default input is the committed, solved ``VizGalleryDemo`` artifact set used
by the matching notebooks. Production review values must come from a real
Code_Aster run/import. Unattested generated tables cannot enter this workflow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba import Model
from tuba.assemblies import RackBay
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
from tuba.compliance.asme_b313 import ASMEB313Evaluator
from tuba.reporting import build_engineering_review
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.routing import AutoroutingAgent
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.rules import RuleEngine
from tuba.visualization import (
    SceneBuildOptions,
    build_visualization_scene,
    write_engineering_review_with_scene,
)


def run_example(
    output_dir: str | Path = ".build/benchmarks/code_aster_artifact_review",
    *,
    artifact_dir: str | Path | None = None,
    model: Model | None = None,
    scene_id: str = "scene:code_aster_artifact_review",
    title: str = "Code_Aster artifact engineering review",
    route_results: list[Any] | None = None,
    include_load_paths: bool = False,
    include_compliance: bool = False,
    clash_clearance_m: float | None = None,
    model_rules: list[Any] | None = None,
    scene_options: SceneBuildOptions | None = None,
    source: str | Path | None = None,
) -> dict[str, Any]:
    """Write the review package without running Code_Aster.

    ``artifact_dir`` must contain attested, solved Code_Aster outputs matching
    the model.

    ``include_compliance`` evaluates ASME B31.3 from the imported solver
    evidence and publishes the resulting ``code_compliance`` table. It is an
    optional layer over the result review, not part of it: the review is a
    Code_Aster result review with or without it, and a model whose material
    carries no allowable-stress table cannot be evaluated at all. When it is
    enabled the verdict is published as it comes out, pass or fail; it is
    never suppressed for a failing model.

    ``clash_clearance_m`` runs the operating-state clash check against the
    imported displacement field using a clearance envelope of that radius.

    ``model_rules`` are engineer-authored design rules evaluated against the
    model. They annotate the review; they are not solver results and not a
    piping-code judgement.

    ``source`` names the authoring script published beside the scene; it
    defaults to this module, which is what defines the models this function
    reviews. A caller that supplies its own model should name its own file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    resolved_model = model or build_model()
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

    artifact = import_code_aster_artifacts(model=resolved_model, work_dir=resolved_artifact_dir)
    solved_at = artifact.result_state.metadata["solve_attestation"]["solved_at"]
    artifact = stage_code_aster_artifact_evidence(artifact, output_path / "review_scene")
    operating_state = create_operating_geometry_state(model=resolved_model, result_state=artifact.result_state)
    visual_state = create_visual_deformed_geometry_state(
        model=resolved_model,
        result_state=artifact.result_state,
        visual_scale=40.0,
    )
    if include_compliance and not str(resolved_model.standard).startswith("ASME_B31.3"):
        raise ValueError(
            "Compliance publication uses the ASME B31.3 evaluator, but the model declares "
            f"standard {resolved_model.standard!r}."
        )
    compliance_reports = (
        [ASMEB313Evaluator().evaluate(resolved_model, artifact.results)] if include_compliance else []
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
    review = build_engineering_review(
        resolved_model,
        analysis_runs=[artifact],
        compliance_reports=compliance_reports,
        package_id="review:code_aster_artifact",
        created_at=solved_at,
    )
    bundle = write_engineering_review_with_scene(
        review,
        output_path / "review_scene",
        scene=scene,
        title=title,
        source=source if source is not None else __file__,
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
        "compliance": [
            {
                "load_case": report.load_case,
                "code": f"{report.code_name} {report.code_edition}",
                "overall_pass": report.overall_pass,
                "worst_sustained_ratio": report.worst_sustained_ratio,
                "worst_expansion_ratio": report.worst_expansion_ratio,
            }
            for report in compliance_reports
        ],
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


def build_support_rack_model() -> Model:
    """Build the canonical solved pipe-on-rack review model."""
    model = Model("SupportRackReview", standard="ASME_B31.3")
    model.add_material(
        "Steel",
        E=2.1e11,
        nu=0.3,
        rho=7850.0,
        alpha=1.2e-5,
        allowable_stress={20.0: 137e6, 180.0: 120e6},
    )
    model.add_ibeam_section("RackColumnIPE", "IPE160")
    model.add_rectangular_section(
        "RackLongRHS",
        height_y=0.14,
        height_z=0.08,
        thickness_y=0.008,
        thickness_z=0.008,
    )
    model.add_rectangular_section(
        "RackCrossRHS",
        height_y=0.10,
        height_z=0.06,
        thickness_y=0.006,
        thickness_z=0.006,
    )
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    ModelTransaction(model).apply(
        RackBay(
            name="rack_A",
            origin=(0.0, -1.0, 0.0),
            length=4.0,
            width=2.0,
            height=3.0,
            levels=(3.0,),
            section="RackLongRHS",
            material="Steel",
            zone="north",
            column_section="RackColumnIPE",
            longitudinal_section="RackLongRHS",
            transverse_section="RackCrossRHS",
        ).to_patch()
    )

    rack = model.groups["rack_A"]
    for node_id in rack["nodes"]:
        if abs(float(model.nodes[node_id].coords[2])) < 1e-9:
            model.add_support(node_id, "anchor")

    left_ref = rack["metadata"]["attachment_points"]["level_1_left"]
    right_ref = rack["metadata"]["attachment_points"]["level_1_right"]
    left = left_ref.split(":", 1)[1]
    right = right_ref.split(":", 1)[1]
    start = model.add_node((-2.0, -1.0, 3.0))
    end = model.add_node((6.0, -1.0, 3.0))
    model.add_element(
        id="pipe_inlet",
        type="pipe_straight",
        n1=start,
        n2=left,
        section="DN100",
        material="Steel",
        route_id="P-100",
    )
    model.add_element(
        id="pipe_rack_span",
        type="pipe_straight",
        n1=left,
        n2=right,
        section="DN100",
        material="Steel",
        route_id="P-100",
    )
    model.add_element(
        id="pipe_outlet",
        type="pipe_straight",
        n1=right,
        n2=end,
        section="DN100",
        material="Steel",
        route_id="P-100",
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    model.add_support(left, "rest")
    model.add_support(right, "rest")
    model.define_load_case(
        "Operating",
        gravity=True,
        pressure=1.5e6,
        temperature=180.0,
        ref_temperature=20.0,
    )
    model.validate()
    return model


def build_autorouted_expansion_model(output_root: str | Path) -> tuple[Model, Any]:
    """Build and apply the canonical U-loop while retaining its route review."""
    from examples.autoroute_expansion_loop import build_model, build_request, build_router

    model = build_model()
    run = AutoroutingAgent(
        router=build_router(),
        solver_config=SolverLoopConfig(run_solver=False, export_study=False, load_case="Hot"),
        output_root=output_root,
    ).route_pipe(
        model,
        build_request(),
        apply=True,
        add_supports=True,
        support_spacing=2.0,
    )
    if run.result.selected is None or not run.created_element_ids:
        raise RuntimeError("Canonical autorouting gallery did not produce a selected route.")
    for candidate in run.result.candidates:
        candidate.metadata.pop("solver", None)
    elements = {element.id: element for element in model.elements}
    for node_id in (
        elements[run.created_element_ids[0]].n1,
        elements[run.created_element_ids[-1]].n2,
    ):
        model.add_support(node_id, "anchor")
    # Added after routing on purpose: the router consumes model.obstacles, so an
    # obstacle declared earlier would change the generated nodes and elements and
    # break the solver-input fingerprint of the committed Code_Aster artifacts.
    # This tray clears the cold loop and is only reached once the line expands.
    model.add_obstacle(
        id="cable_tray",
        type="cuboid",
        min_point=(4.6, 0.95, -0.20),
        max_point=(6.4, 1.15, 0.20),
    )
    model.validate()
    return model, run.result


def main() -> int:
    print(json.dumps(run_example(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
