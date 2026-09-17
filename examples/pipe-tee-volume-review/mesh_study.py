"""Mesh-only review of the tee: what Gmsh discretises at the branch, with no solver results."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.meshing import build_pipe_volume_mesh
from tuba.project import load_project
from tuba.visualization import SceneDiagnostic, SceneRequest, build_visualization_scene, write_scene_bundle

LOAD_CASES = ()
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = None
VOLUME_EXPORT = None

_PROJECT = load_project(Path(__file__).resolve().parent)
#: The same solids and element size as the solved tee review.
_VOLUME = _PROJECT.load_study().VOLUME_EXPORT


def _build_scene(model, output: Path):
    from tuba import Model

    mesh_model = Model(model.project_name)
    for mat in model.materials.values():
        mesh_model.materials[mat.name] = mat
    for sec in model.sections.values():
        mesh_model.sections[sec.name] = sec
    for elem_id in _VOLUME["element_ids"]:
        elem = model.get_element(elem_id)
        if elem is not None:
            for nid in (elem.n1, elem.n2):
                if nid not in mesh_model.nodes:
                    mesh_model.nodes[nid] = model.nodes[nid]
            mesh_model.add_element(
                id=elem.id,
                type=elem.type,
                n1=elem.n1,
                n2=elem.n2,
                section=elem.section,
                material=elem.material,
            )
    for node_id, tee in model.tees.items():
        if node_id in mesh_model.nodes:
            mesh_model.define_tee(node_id, type=tee.type, pad_thickness=tee.pad_thickness)

    generated = build_pipe_volume_mesh(
        mesh_model,
        output / "study.med",
        element_ids=_VOLUME["element_ids"],
        max_element_size=_VOLUME["max_element_size"],
    )
    analysis_mesh = replace(
        generated.analysis_mesh,
        id="analysis_mesh:gmsh_tee_unsolved",
        files={"med": "study.med"},
    )
    scene = build_visualization_scene(SceneRequest(
        mesh_model,
        analysis_meshes=[analysis_mesh],
        scene_id="scene:gmsh_tee_mesh_review",
    ))
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
    return scene


def build_review(namespace, output, *, artifact_dir=None, force=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scene = _build_scene(namespace["model"], output)
    return write_scene_bundle(scene, output / "review_scene", source=namespace["__file__"]).root


def build():
    """Return the mesh-only scene, meshed in a temporary folder."""
    with TemporaryDirectory(prefix="tuba-gmsh-tee-mesh-") as temporary:
        return _build_scene(_PROJECT.run_model()["model"], Path(temporary))
