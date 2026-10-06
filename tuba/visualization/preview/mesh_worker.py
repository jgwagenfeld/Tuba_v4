"""External native meshing, deliberately unsolved; receipt is written last."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from tuba.visualization.preview.mesh import atomic_json, digest, mesh_inputs, read_native_line_mail


def run(project_root, directory):
    from tuba.project import load_project, run_model_script
    from tuba.project.study import study_settings
    from tuba.validation import validate_model

    directory = Path(directory)
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    if request.get("mode") == "convergence":
        import os
        from tuba.solver.code_aster_process import worker_process_identity
        worker = worker_process_identity(os.getpid())
        atomic_json(directory / "worker.json", {"schema": "tuba.mesh-worker.v1", "job_id": directory.name,
            "project_root": str(Path(project_root).resolve()), **worker})
    atomic_json(directory / "status.json", {"stage": "preparing"})
    project = load_project(project_root)
    namespace = run_model_script(project.model_path)
    model = namespace["model"]
    validate_model(model)
    study = project.load_study()
    settings = study_settings(study) if study is not None else None
    volume = settings.volume_export if settings else None
    if mesh_inputs(model, volume) != request["inputs"]:
        raise ValueError("Loaded Python/policy identity differs from the requested mesh job.")
    for path, expected in request["source_fingerprints"]:
        observed = digest(path) if Path(path).is_file() else None
        if observed != expected:
            raise ValueError(f"Source changed during worker preparation: {path}")
    if request.get("mode") == "convergence":
        from tuba.analysis.mesh_convergence import run_mesh_convergence
        from tuba.project.solve import verify_project
        from tuba.solver.code_aster_process import ExecutionController
        if settings is None or settings.mesh_convergence is None:
            raise ValueError("study.py must define MESH_CONVERGENCE.")
        verify_project(project, namespace)
        controller = ExecutionController(directory)
        def progress(report):
            atomic_json(directory / "status.json", {"stage": "solving", "levels": report["levels"]})
        report = run_mesh_convergence(model, settings.operations[0], output_dir=directory,
            solver_options=settings.solver_options, volume_export=volume,
            execution_controller=controller, progress=progress, **settings.mesh_convergence)
        controller.check_cancelled()
        if report["status"] != "completed":
            raise ValueError(report.get("error", "One or more Code_Aster convergence levels failed; inspect comparison.json."))
        atomic_json(directory / "status.json", {"stage": "complete", "levels": report["levels"]})
        return
    output = directory / "mesh.med"
    atomic_json(directory / "status.json", {"stage": "generating"})
    if volume:
        from tuba.meshing.pipe_volume import build_pipe_volume_mesh
        mesh = build_pipe_volume_mesh(model, output, **volume).analysis_mesh
    elif any(r.role in {"solid_3d", "shell_2d"} for r in model.analysis_regions.values()):
        from tuba.meshing.step_component import build_step_component_mesh
        # The Studio receipt below already carries the full analysis mesh.
        mesh = build_step_component_mesh(model, output).analysis_mesh
    else:
        from dataclasses import replace
        from tuba.solver.aster_mesh import generate_analysis_mesh
        from tuba.meshing.policy import resolve_mesh_policy
        from tuba.meshing.quality import mesh_review

        output = directory / "mesh.mail"
        solver = settings.solver() if settings else None
        options = {"pipe_modelization": solver.pipe_modelization, "line_segments": solver.line_segments} if solver else {}
        mesh = generate_analysis_mesh(model, mail_path=output, **options)
        if mesh.mesh_review is None:
            # Legacy AnalysisMesh keeps endpoint-only line records. Build only the
            # new diagnostics from actual MAIL nodes/cells, preserving those records
            # and established solver identities while correctly counting SEG3.
            nodes, elements = read_native_line_mail(output)
            diagnostic_mesh = replace(mesh, nodes=nodes, elements=elements)
            mesh = replace(mesh, mesh_review=mesh_review(diagnostic_mesh, resolve_mesh_policy(model), output_path=output))
    atomic_json(directory / "status.json", {"stage": "validating"})
    atomic_json(directory / "analysis_mesh.json", mesh.to_dict())
    atomic_json(directory / "manifest.json", {"schema": "tuba.mesh-job.v1", "identity": request["identity"],
        "result_status": "mesh_only", "artifact": output.name,
        "sha256": {name: digest(directory / name) for name in (output.name, "analysis_mesh.json")}})
    # The host independently imports and verifies these bytes before publication.
    atomic_json(directory / "status.json", {"stage": "complete"})


def main():
    directory = Path(sys.argv[2])
    try:
        run(Path(sys.argv[1]), directory)
    except BaseException as exc:
        atomic_json(directory / "status.json", {"stage": "failed", "error": f"{type(exc).__name__}: {exc}"})
        raise


if __name__ == "__main__":
    main()
