"""Photograph the documentation figures in the Tuba viewer.

Run:  uv run python scripts/docs/generate_figures.py [figure ...]

Each figure is a scene built from live Tuba objects, written as a viewer bundle
and shot by the headless browser that photographs the gallery cards, so the
manual shows what a reader sees when they open a review. The PyVista renders
these replaced had drifted into a look the product no longer has. No solver
runs here: result pictures in the manual are the Pages-built gallery thumbnails.

Needs Node, the viewer's npm dependencies and the Playwright browser. Outputs
committed PNGs under docs/content/assets/figures/.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from tuba import Model
from tuba.geometry.section_mesh import beam_local_frame
from tuba.model import sample_bend_geometry
from tuba.placements import PlacementFrame
from tuba.routing import GridRouter
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingConstraints, RoutingGridSpec
from tuba.visualization import (
    GeometryAsset,
    SceneLayer,
    SceneObject,
    VisualizationScene,
    add_scene_label,
    build_visualization_scene,
    write_scene_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # figures import from examples/, which is not installed
    sys.path.insert(0, str(REPO_ROOT))
FIG_DIR = REPO_ROOT / "docs" / "content" / "assets" / "figures"
VIEWER = REPO_ROOT / "viewer"
SHOOTER = VIEWER / "scripts" / "gallery-thumbnails.mjs"
#: The viewer serves any public/ folder holding a scene.json as a bundle, so a
#: figure is shot from there and removed again afterwards.
BUNDLE_PREFIX = "docs-figure-"
LABEL_HEIGHT = 0.13
#: The viewer's own axis colours, as on its orientation gizmo.
AXIS_COLORS = {"x": "#dc2626", "y": "#16a34a", "z": "#2563eb"}


def _materials(model: Model) -> None:
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)


def _add_axes(scene: VisualizationScene, origin, basis, *, axes_id: str, length: float,
              labels: dict[str, str] | None = None) -> None:
    """Draw a right-handed triad as the viewer's local-axis vectors.

    The scene builder emits these only for imported-component placements, so a
    figure about element and placement frames adds its own in the same format.
    """
    if not any(layer.id == "local_coordinate_axes" for layer in scene.layers):
        scene.layers.append(SceneLayer(id="local_coordinate_axes", category="design", label="Local axes"))
    origin = np.asarray(origin, dtype=float)
    for axis, direction in zip("xyz", basis):
        direction = np.asarray(direction, dtype=float)
        end = origin + direction * length
        object_id = f"object:docs_axes:{axes_id}:{axis}"
        asset_id = f"geometry:docs_axes:{axes_id}:{axis}"
        scene.geometry_assets.append(GeometryAsset(
            id=asset_id,
            format="vector",
            bounds=[float(value) for value in (*np.minimum(origin, end), *np.maximum(origin, end))],
            object_ids=[object_id],
            generation_config={"axis": axis, "start": origin.tolist(), "end": end.tolist(),
                               "color": AXIS_COLORS[axis]},
        ))
        scene.objects.append(SceneObject(
            id=object_id,
            kind="local_coordinate_axis",
            name=f"{axes_id} {axis.upper()}",
            geometry_asset_id=asset_id,
            layer_ids=["local_coordinate_axes"],
            metadata={"axis": axis},
        ))
        if labels:
            tip = origin + direction * length * 1.2
            add_scene_label(scene, labels[axis], tip.tolist(), label_id=f"{axes_id}-{axis}", height=LABEL_HEIGHT)


def fig_tutorial_model() -> VisualizationScene:
    """The tutorial's model before it is solved: geometry and supports only."""
    from examples.code_aster_artifact_review import build_model

    return build_visualization_scene(build_model())


def fig_element_triad() -> VisualizationScene:
    """One straight pipe with its local triad."""
    model = Model(project_name="ElementTriad")
    _materials(model)
    with model.pipe(section="DN100", material="steel", route="P") as pipe:
        pipe.start([0.0, 0.0, 0.0])
        pipe.run(2.5)
    element = model.elements[0]
    start, end = model.nodes[element.n1].coords, model.nodes[element.n2].coords
    scene = build_visualization_scene(model)
    # At the pipe end rather than mid-span, where the pipe would hide local X.
    _add_axes(scene, end, beam_local_frame(start, end), axes_id="element", length=0.7,
              labels={"x": "local X (along the pipe)", "y": "local Y", "z": "local Z"})
    return scene


def fig_placement_frame() -> VisualizationScene:
    """The world frame and a rotated placement frame, with a pipe authored in that frame."""
    model = Model(project_name="Placement")
    _materials(model)
    frame = PlacementFrame(id="rack", origin=(2.4, 1.4, 0.4), axis=(0.0, 0.35, 1.0), ref_direction=(1.0, 0.6, 0.0))
    model.add_placement_frame(frame)
    # Beside the frame's local X axis rather than along it, where the pipe would hide the axis.
    n1, n2 = (
        model.add_node([float(value) for value in model.to_global_point(point, frame="placement_frame:rack")])
        for point in ((0.0, 0.45, 0.0), (1.8, 0.45, 0.0))
    )
    model.add_element(id="rack_pipe", type="pipe_straight", n1=n1, n2=n2, section="DN100", material="steel")
    scene = build_visualization_scene(model)
    cs = frame.to_coordinate_system()
    _add_axes(scene, (0.0, 0.0, 0.0), np.eye(3), axes_id="world", length=1.1,
              labels={"x": "world X", "y": "world Y", "z": "world Z"})
    _add_axes(scene, cs.origin, (cs.x_axis, cs.y_axis, cs.z_axis), axes_id="rack", length=1.0,
              labels={"x": "local X", "y": "local Y", "z": "local Z"})
    return scene


def fig_builder_route() -> VisualizationScene:
    """A builder route through an in-plane and an out-of-plane bend, with each run's local frame."""
    model = Model(project_name="BuilderRoute")
    _materials(model)
    with model.pipe(section="DN100", material="steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(2.0)
        pipe.bend(radius=0.3, angle=90.0, plane="XY")
        pipe.run(1.5)
        pipe.bend(radius=0.3, angle=90.0, plane="XZ")
        pipe.run(1.2)
        pipe.end(support="anchor")
    scene = build_visualization_scene(model)
    for index, element in enumerate(e for e in model.elements if e.type == "pipe_straight"):
        start, end = model.nodes[element.n1].coords, model.nodes[element.n2].coords
        frame = beam_local_frame(start, end)
        # Just clear of the crown: on the centreline the pipe hides local X.
        origin = (np.asarray(start) + np.asarray(end)) / 2 + frame[2] * 0.12
        _add_axes(scene, origin, frame, axes_id=f"run-{index}", length=0.45)
    for text, bend in zip(("bend in XY", "bend in XZ"), (e for e in model.elements if e.type == "pipe_bend")):
        arc = np.asarray(sample_bend_geometry(model.nodes[bend.n1].coords, bend.bend_geometry, n_segments=8))
        apex = arc[len(arc) // 2]
        outward = apex - (arc[0] + arc[-1]) / 2
        label_at = apex + outward / np.linalg.norm(outward) * 0.35
        add_scene_label(scene, text, label_at.tolist(), label_id=text.replace(" ", "-"), height=LABEL_HEIGHT)
    return scene


def fig_supports() -> VisualizationScene:
    """Anchor, guide, rest and spring supports on one line, each labelled with its type."""
    model = Model(project_name="Supports")
    _materials(model)
    with model.pipe(section="DN100", material="steel", route="S") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.5)
        pipe.add_support(type="guide")
        pipe.run(1.5)
        pipe.add_support(type="rest")
        pipe.run(1.5)
        pipe.add_support(type="spring", direction=[0.0, 0.0, 1.0], stiffness=2.0e5)
        pipe.run(1.5)
        pipe.end(support="anchor")
    scene = build_visualization_scene(model)
    for support in model.supports:
        above = np.asarray(model.nodes[support.node].coords) + [0.0, 0.0, 0.45]
        add_scene_label(scene, support.type, above.tolist(), label_id=f"support-{support.id}", height=LABEL_HEIGHT)
    return scene


def fig_route_candidates() -> VisualizationScene:
    """Ranked candidates around two obstacles, with the selected one applied as pipe."""
    model = Model(project_name="RouteDemo")
    _materials(model)
    model.add_obstacle(id="equipment_box", type="cuboid", min_point=[1.5, -0.4, -0.4], max_point=[2.5, 0.4, 0.4])
    model.add_obstacle(id="maintenance_keepout", type="cuboid", min_point=[2.8, 0.8, -0.4], max_point=[3.4, 1.4, 0.8])
    request = PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
        goal=RouteEndpoint("B", (4.0, 0.0, 0.0)),
        section="DN100",
        material="steel",
        constraints=RoutingConstraints(clearance=0.10, min_bend_radius=0.20),
    )
    result = GridRouter(RoutingGridSpec(cell_size=0.25, margin=1.0), candidate_count=3).route(model, request)
    apply_candidate_to_model(model, result.selected, request, add_supports=False)
    scene = build_visualization_scene(model, route_results=[result])
    for role, endpoint in (("start", request.start), ("goal", request.goal)):
        below = np.asarray(endpoint.point) + [0.0, 0.0, -0.3]
        add_scene_label(scene, f"{role} {endpoint.id}", below.tolist(), label_id=f"route-{role}", height=LABEL_HEIGHT)
    return scene


FIGURES: dict[str, Callable[[], VisualizationScene]] = {
    "tutorial_model": fig_tutorial_model,
    "element_triad": fig_element_triad,
    "placement_frame": fig_placement_frame,
    "builder_route": fig_builder_route,
    "supports": fig_supports,
    "route_candidates": fig_route_candidates,
}


def main(names: Iterable[str] = FIGURES, out_dir: Path = FIG_DIR) -> None:
    bundles = {name: VIEWER / "public" / f"{BUNDLE_PREFIX}{name}" for name in names}
    try:
        for name, bundle in bundles.items():
            scene = FIGURES[name]()
            scene.validate()  # a broken scene fails here, not as a blank photograph
            shutil.rmtree(bundle, ignore_errors=True)
            write_scene_bundle(scene, bundle)
        with tempfile.TemporaryDirectory() as shots:
            node = shutil.which("node") or "node"
            subprocess.run([node, str(SHOOTER), "--bare", shots, *(bundle.name for bundle in bundles.values())],
                           cwd=VIEWER, check=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, bundle in bundles.items():
                shutil.copyfile(Path(shots) / f"{bundle.name}.png", out_dir / f"{name}.png")
                print(f"OK  {name}.png")
    finally:
        for bundle in bundles.values():
            shutil.rmtree(bundle, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:] or FIGURES)
