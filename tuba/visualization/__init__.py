"""tuba.visualization — semantic scene / preview / web-export engine.

NOTE: distinct from :mod:`tuba.plotting` (the interactive PyVista result plotter).
THIS package is the large, headless system: JSON scene contracts, scene
builders (which carry IFC identities onto scene objects), the studio server
and web/static-report export. It does not render PyVista windows.

For interactive PyVista result plotting in notebooks (``results.plot_*``,
``build_model_scene``, PLY/glTF/Blender export), see :mod:`tuba.plotting`.
"""

from tuba.visualization.scene import (
    LAYER_CATEGORIES,
    GeometryAsset,
    Issue,
    Overlay,
    ResultField,
    RouteReview,
    SceneDiagnostic,
    SceneLayer,
    SceneObject,
    ViewState,
    VisualizationScene,
)
from tuba.visualization.builders import SceneBuildOptions, build_visualization_scene
from tuba.visualization.schema import SceneValidationError
from tuba.visualization.web_export import SceneBundle, write_scene_bundle
from tuba.visualization.reporting_adapter import write_engineering_review_with_scene
from tuba.visualization.labels import add_scene_label


def viewer_assets_path():
    from tuba.visualization.viewer import viewer_assets_path as _viewer_assets_path

    return _viewer_assets_path()

__all__ = [
    "LAYER_CATEGORIES",
    "GeometryAsset",
    "Issue",
    "Overlay",
    "ResultField",
    "RouteReview",
    "SceneDiagnostic",
    "SceneLayer",
    "SceneObject",
    "ViewState",
    "VisualizationScene",
    "SceneBuildOptions",
    "build_visualization_scene",
    "SceneBundle",
    "write_scene_bundle",
    "write_engineering_review_with_scene",
    "viewer_assets_path",
    "SceneValidationError",
    "add_scene_label",
]
