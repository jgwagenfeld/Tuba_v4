"""tuba.visualization — semantic scene / preview / web-export / BIM engine.

NOTE: distinct from :mod:`tuba.plotting` (the interactive PyVista result plotter).
THIS package is the large, headless system: JSON scene contracts, scene
builders, diffing, the live-preview server, web/static-report export, and
BIM interop (BCF/IFC). It does not render PyVista windows.

For interactive PyVista result plotting in notebooks (``results.plot_*``,
``build_model_scene``, PLY/glTF/Blender export), see :mod:`tuba.plotting`.
"""

from tuba.visualization.scene import (
    AgentProposal,
    GeometryAsset,
    Issue,
    Overlay,
    RouteReview,
    SceneDiagnostic,
    SceneDiff,
    SceneMaterial,
    SceneObject,
    SceneStyle,
    ViewState,
    VisualizationScene,
)
from tuba.visualization.builders import SceneBuildOptions, build_visualization_scene
from tuba.visualization.schema import SceneValidationError, validate_scene_dict
from tuba.visualization.bcf import export_bcf_topics, import_bcf_topics
from tuba.visualization.agent_workspace import AgenticPythonWorkspace, AgentWorkspaceSession, WorkspaceCellResult
from tuba.visualization.live_preview import LivePreviewResult, preview_json_patch, preview_python_script
from tuba.visualization.performance import benchmark_scene_build, benchmark_viewer_smoke
from tuba.visualization.scene_diff import SceneDiffBuildResult, apply_scene_diff, build_scene_diff
from tuba.visualization.static_report import StaticReport, notebook_iframe_html, write_static_report
from tuba.visualization.web_export import SceneBundle, write_scene_bundle

__all__ = [
    "AgentProposal",
    "GeometryAsset",
    "Issue",
    "Overlay",
    "RouteReview",
    "SceneDiagnostic",
    "SceneDiff",
    "SceneMaterial",
    "SceneObject",
    "SceneStyle",
    "ViewState",
    "VisualizationScene",
    "SceneBuildOptions",
    "build_visualization_scene",
    "SceneBundle",
    "write_scene_bundle",
    "SceneValidationError",
    "validate_scene_dict",
    "export_bcf_topics",
    "import_bcf_topics",
    "benchmark_scene_build",
    "benchmark_viewer_smoke",
    "SceneDiffBuildResult",
    "apply_scene_diff",
    "build_scene_diff",
    "StaticReport",
    "notebook_iframe_html",
    "write_static_report",
    "LivePreviewResult",
    "preview_json_patch",
    "preview_python_script",
    "AgenticPythonWorkspace",
    "AgentWorkspaceSession",
    "WorkspaceCellResult",
]
