"""Headless native mesh diagnostics and verified Code_Aster convergence jobs."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

from tuba.project import load_project
from tuba.project.claim import claim_solve, release_cleanup_claim
from tuba.project.study import study_settings
from tuba.visualization.preview.mesh import atomic_json, digest, launch_mesh_worker, mesh_inputs, validate_artifact


def run_project_mesh(project_root, output_dir, *, mode="mesh") -> dict:
    """Run Studio's native worker into a NEW output folder and verify its artifacts.

    ``mesh`` produces unsolved diagnostic cells. ``convergence`` requires exactly
    one study operation, MESH_CONVERGENCE and a supported Code_Aster runtime.
    Neither rewrites source or replaces the project's ordinary solve evidence.
    Each output folder contains one job directory; failures retain diagnostics.
    """
    if mode not in {"mesh", "convergence"}:
        raise ValueError("Mode must be mesh or convergence.")
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new output folder; destination already exists: {output}.")
    project = load_project(project_root)
    namespace = project.run_model()
    model = namespace["model"]
    study = project.load_study()
    settings = study_settings(study)
    if mode == "convergence":
        from tuba.project.solve import verify_project
        from tuba.solver.code_aster_process import convergence_capability
        verify_project(project, namespace)
        if settings.mesh_convergence is None:
            raise ValueError("Define MESH_CONVERGENCE and exactly one LOAD_CASES operation in study.py.")
        capability = convergence_capability()
        if not capability["supported"]:
            raise ValueError(capability["reason"])
    captured = dict(namespace["__tuba_project_fingerprints__"])
    captured.update(getattr(study, "__tuba_project_fingerprints__", ()))
    captured.setdefault(project.study_path, None)
    sources = {str(path): value.hex() if value is not None else None for path, value in captured.items()}
    for asset in model.cad_assets.values():
        path = Path(asset.source_path)
        path = path.resolve() if path.is_absolute() else (project.root / path).resolve()
        sources[str(path)] = str(asset.content_digest).removeprefix("sha256:") if asset.content_digest else digest(path)

    def unchanged():
        for path, expected in sources.items():
            if (digest(path) if Path(path).is_file() else None) != expected:
                raise ValueError(f"Python or CAD source changed during the mesh job: {path}; rerun.")

    inputs = mesh_inputs(model, settings.volume_export)
    records = sorted(sources.items())
    identity = hashlib.sha256(json.dumps([inputs, records], sort_keys=True).encode()).hexdigest()
    job_id = uuid4().hex
    directory = output / job_id
    obligation = {"job_id": job_id, "directory": str(directory)} if mode == "convergence" else None
    job = {"id": job_id, "mode": mode, "directory": str(directory), "identity": identity,
           "source_revision": identity, "state": "running", "stage": "preparing"}
    process = None
    with claim_solve(project.root, cleanup_obligation=obligation) as token:
        try:
            unchanged()
            output.mkdir(parents=True)  # Atomically refuse a competing output owner.
            atomic_json(directory / "request.json", {"identity": identity, "inputs": inputs,
                        "source_fingerprints": records, "mode": mode})
            atomic_json(directory / "job.json", job)
            process = launch_mesh_worker(project.root, directory)
            returncode = process.wait()
            if returncode != 0:
                status_path = directory / "status.json"
                status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
                raise RuntimeError(status.get("error", f"Native worker exited {returncode}; inspect {directory / 'worker.log'}."))
            unchanged()
            if mode == "mesh":
                mesh = validate_artifact(directory, identity)
                result = {"result_status": "mesh_only", "mesh_review": mesh.mesh_review}
            else:
                from tuba.analysis.mesh_convergence import reopen_mesh_convergence
                result = {"result_status": "verified_comparison", "comparison": reopen_mesh_convergence(model, directory)}
            unchanged()
            job.update(state="succeeded", stage="complete")
        except BaseException as exc:
            job.update(state="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            try:
                try:
                    if obligation is not None and process is not None:
                        from tuba.solver.code_aster_process import ExecutionController
                        controller = ExecutionController(directory, cleanup_only=True)
                        if job["state"] == "succeeded":
                            controller.cleanup()
                        else:
                            controller.cancel()
                finally:
                    if process is not None and process.poll() is None:
                        process.terminate()
                        process.wait()
                if obligation is not None:
                    release_cleanup_claim(project.root, token=token, obligation=obligation)
            except Exception as exc:
                job.update(state="failed", stage="cleanup_pending", cleanup_pending=True,
                           error=f"Owned Code_Aster cleanup failed: {exc}; reopen this project in Studio to retry cleanup.")
                raise RuntimeError(job["error"]) from exc
            finally:
                if directory.exists():
                    atomic_json(directory / "job.json", job)
    return {"status": "success", "project_root": str(project.root), "directory": str(directory),
            "mode": mode, **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate unsolved meshes or run verified Code_Aster convergence without Studio.")
    parser.add_argument("mode", choices=("mesh", "convergence"))
    parser.add_argument("project", type=Path, help="Folder containing model.py and optional study.py")
    parser.add_argument("--output", required=True, type=Path, help="New output folder; contains one native job directory")
    args = parser.parse_args(argv)
    try:
        with redirect_stdout(sys.stderr):
            result = run_project_mesh(args.project, args.output, mode=args.mode)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
