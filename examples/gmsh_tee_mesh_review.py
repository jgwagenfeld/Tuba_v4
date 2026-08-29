"""Publish an unsolved native Gmsh tee mesh for browser review."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

if __package__:
    from .code_aster_tee_volume_review import TEE_VOLUME_ELEMENT_IDS, build_tee_volume_model
else:
    from code_aster_tee_volume_review import TEE_VOLUME_ELEMENT_IDS, build_tee_volume_model
from tuba.meshing import build_pipe_volume_mesh
from tuba.visualization import SceneDiagnostic, build_visualization_scene, write_scene_bundle


def _build_scene(output: Path):
    model = build_tee_volume_model()
    generated = build_pipe_volume_mesh(
        model,
        output / "study.med",
        element_ids=TEE_VOLUME_ELEMENT_IDS,
        max_element_size=0.005,
    )
    analysis_mesh = replace(
        generated.analysis_mesh,
        id="analysis_mesh:gmsh_tee_unsolved",
        files={"med": "study.med"},
    )
    scene = build_visualization_scene(
        model,
        analysis_meshes=[analysis_mesh],
        scene_id="scene:gmsh_tee_mesh_review",
    )
    scene.diagnostics.append(
        SceneDiagnostic(
            code="publication.mesh_review.no_solver_results",
            severity="info",
            message=(
                "Unsolved Gmsh analysis-mesh review only. Code_Aster has not been run "
                "and no solver results are displayed."
            ),
        )
    )
    scene.extra.update(
        {
            "publication_status": "mesh_only_unsolved",
            "mesh_generator": {"name": "Gmsh", "version": generated.gmsh_version},
            "mesh_settings": generated.settings,
        }
    )
    return scene, generated


def build():
    """Return the mesh-only scene expected by viewer/scripts/make_bundle.py."""
    with TemporaryDirectory(prefix="tuba-gmsh-tee-mesh-") as temporary:
        scene, _generated = _build_scene(Path(temporary))
    return scene


def run_example(
    output_dir: str | Path = ".build/examples/gmsh_tee_mesh_review",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scene, generated = _build_scene(output)
    bundle = write_scene_bundle(scene, output / "review_scene", source=__file__)
    summary = {
        "publication_status": "mesh_only_unsolved",
        "mesh_nodes": len(generated.analysis_mesh.nodes),
        "mesh_elements": len(generated.analysis_mesh.elements),
        "med": str(generated.med_path),
        "bundle_root": str(bundle.root),
        "scene": str(bundle.scene_path),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
