"""Connect a custom STEP/STL component to a programmatic Tuba pipe model.

STEP/STP can be exported as a mixed Code_Aster handoff. STL is recorded as
review geometry only until it is converted to a solver-ready volume mesh with
confirmed groups.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import tuba
from tuba.geometry.step_analysis_importer import StepAnalysisImporter
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene, write_scene_bundle


ANALYSIS_FORMATS = {"STEP", "STP"}
DEFAULT_LOCAL_BOUNDS = [-0.05, -0.18, -0.18, 0.45, 0.18, 0.18]
DEFAULT_LOCAL_PORT = [0.0, 0.0, 0.0]
DEFAULT_LOCAL_AXIS = [-1.0, 0.0, 0.0]
DEFAULT_PLACEMENT_ORIGIN = [1.2, 0.45, 0.0]
DEFAULT_PLACEMENT_ROTATION = [1.0, 0.0, 0.0, 0.0]


def infer_source_format(source_path: str | Path) -> str:
    suffix = Path(source_path).suffix.lower()
    if suffix in {".step", ".stp"}:
        return "STEP"
    if suffix == ".stl":
        return "STL"
    raise ValueError("Custom component must be a .step, .stp, or .stl file.")


def build_model(
    source_path: str | Path,
    *,
    source_format: str | None = None,
    asset_origin: list[float] | tuple[float, float, float] = DEFAULT_PLACEMENT_ORIGIN,
    asset_rotation: list[float] | tuple[float, float, float, float] = DEFAULT_PLACEMENT_ROTATION,
    local_bounds: list[float] | tuple[float, float, float, float, float, float] = DEFAULT_LOCAL_BOUNDS,
    local_port_position: list[float] | tuple[float, float, float] = DEFAULT_LOCAL_PORT,
    local_port_axis: list[float] | tuple[float, float, float] = DEFAULT_LOCAL_AXIS,
) -> tuba.Model:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Custom component file not found: {source}")

    fmt = (source_format or infer_source_format(source)).upper()
    placement = {
        "origin": [float(value) for value in asset_origin],
        "rotation": [float(value) for value in asset_rotation],
    }
    global_port = local_to_global_point(local_port_position, placement)
    global_axis = local_to_global_vector(local_port_axis, placement)
    metadata = {
        "local_bounds": [float(value) for value in local_bounds],
        **_mesh_metadata_for_source(source, fmt),
    }
    model = tuba.Model(project_name="Imported_Component_Mixed_System")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1, WT=0.008)

    with model.pipe(section="DN100", material="Steel", route="line_to_equipment") as pipe:
        pipe.start([0.0, global_port[1], global_port[2]], support="anchor")
        pipe.end(global_port)

    model.define_load_case(
        "Hot",
        gravity=True,
        pressure=1.0e6,
        temperature=120.0,
        ref_temperature=20.0,
    )

    StepAnalysisImporter().record_component_from_metadata(
        model,
        source_path=source,
        source_format=fmt,
        component_id="component_custom_equipment",
        asset_id="cad_asset_custom_equipment",
        role="equipment",
        placement=placement,
        importer="manual-port-metadata",
        metadata=metadata,
        ports=[
            {
                "id": "port_equipment_nozzle_a",
                "position": global_port,
                "axis": global_axis,
                "radius": 0.05,
                "face_group": "G_EQUIP_PORT_A",
                "edge_group": "G_EQUIP_PORT_EDGE_A",
                "status": "confirmed",
                "metadata": {
                    "source": "user_confirmed_port",
                    "coordinate_basis": "asset_local_transformed_to_global",
                    "local_position": [float(value) for value in local_port_position],
                    "local_axis": [float(value) for value in local_port_axis],
                    "asset_placement": placement,
                },
            }
        ],
    )
    model.add_analysis_region(
        id="region_equipment_solid",
        owner="component:component_custom_equipment",
        role="solid_3d",
        code_aster_modelisation="3D",
        material="Steel",
        mesh_group="G_EQUIP_SOLID",
        status="reviewed",
        metadata={"source_format": fmt},
    )
    model.connect_pipe_to_port(
        pipe="element:pipe_str_0",
        node="node:N1",
        port="port:port_equipment_nozzle_a",
        method="3D_TUYAU",
        id="coupling_pipe_to_equipment_a",
    )
    model.validate()
    return model


def run_demo(
    source_path: str | Path,
    *,
    output_root: str | Path = "mixed_imported_component_demo",
    export_study: bool | None = None,
    asset_origin: list[float] | tuple[float, float, float] = DEFAULT_PLACEMENT_ORIGIN,
    asset_rotation: list[float] | tuple[float, float, float, float] = DEFAULT_PLACEMENT_ROTATION,
) -> dict[str, Any]:
    source = Path(source_path)
    fmt = infer_source_format(source)
    export = fmt in ANALYSIS_FORMATS if export_study is None else export_study

    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    model = build_model(source, source_format=fmt, asset_origin=asset_origin, asset_rotation=asset_rotation)
    model_path = output / "mixed_imported_component_model.json"
    model.to_json(str(model_path))
    scene = build_visualization_scene(model, scene_id="scene:imported_component_mixed_system")
    scene_bundle = write_scene_bundle(scene, output / "review_scene")

    summary: dict[str, Any] = {
        "model_path": str(model_path),
        "scene_dir": str(scene_bundle.root),
        "source_format": fmt,
        "asset_placement": {
            "origin": [float(value) for value in asset_origin],
            "rotation": [float(value) for value in asset_rotation],
        },
        "component_ref": "component:component_custom_equipment",
        "port_ref": "port:port_equipment_nozzle_a",
        "coupling_ref": "coupling:coupling_pipe_to_equipment_a",
        "study_dir": None,
        "result_status": "model_connected_only",
        "runtime_blocker": (
            "STL is recorded as review geometry only. Mixed Code_Aster export "
            "currently needs a STEP/STP volume asset with confirmed solver groups."
        ),
    }
    if not export:
        return summary
    if fmt not in ANALYSIS_FORMATS:
        return summary

    study = CodeAsterSolver(work_dir=output / "code_aster_mixed_study").export_mixed_analysis_study(
        model,
        "Hot",
        output / "code_aster_mixed_study",
    )
    summary.update(
        {
            "study_dir": study.work_dir,
            "result_status": study.metadata["result_status"],
            "runtime_blocker": study.metadata["runtime_blocker"],
        }
    )
    return summary


def publish_viewer_bundle(scene_dir: str | Path, *, bundle_name: str = "imported_component_mixed_demo") -> Path:
    destination = Path(__file__).resolve().parents[1] / "viewer" / "public" / bundle_name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(scene_dir, destination)
    return destination


def local_to_global_point(point: list[float] | tuple[float, float, float], placement: dict[str, Any]) -> list[float]:
    origin, rotation = _placement_transform(placement)
    global_point = origin + rotation @ np.asarray(point, dtype=float)
    return [float(value) for value in global_point.tolist()]


def local_to_global_vector(vector: list[float] | tuple[float, float, float], placement: dict[str, Any]) -> list[float]:
    _origin, rotation = _placement_transform(placement)
    global_vector = rotation @ np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(global_vector))
    if norm <= 1e-12:
        raise ValueError("local vector must be non-zero")
    return [float(value) for value in (global_vector / norm).tolist()]


def _placement_transform(placement: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    origin = np.asarray(placement.get("origin", [0.0, 0.0, 0.0]), dtype=float)
    qw, qx, qy, qz = [float(value) for value in placement.get("rotation", [1.0, 0.0, 0.0, 0.0])]
    quat_norm = float(np.linalg.norm([qw, qx, qy, qz]))
    if quat_norm <= 1e-12:
        raise ValueError("placement rotation quaternion must be non-zero")
    qw, qx, qy, qz = [value / quat_norm for value in (qw, qx, qy, qz)]
    rotation = np.array(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=float,
    )
    return origin, rotation


def _mesh_metadata_for_source(source: Path, fmt: str) -> dict[str, Any]:
    if fmt != "STL":
        return {}
    try:
        import trimesh
    except ImportError:
        return {}
    mesh = trimesh.load_mesh(source, force="mesh")
    if mesh.vertices is None or mesh.faces is None or len(mesh.vertices) > 5000:
        return {}
    return {
        "mesh_vertices_local": [[float(value) for value in row] for row in mesh.vertices.tolist()],
        "mesh_faces": [[int(value) for value in row] for row in mesh.faces.tolist()],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Custom .step, .stp, or .stl component")
    parser.add_argument("--output", default="mixed_imported_component_demo")
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--publish-viewer-bundle", action="store_true")
    args = parser.parse_args()

    summary = run_demo(args.source, output_root=args.output, export_study=False if args.no_export else None)
    if args.publish_viewer_bundle:
        summary["viewer_public_dir"] = str(publish_viewer_bundle(summary["scene_dir"]))
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
