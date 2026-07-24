"""Access to the bundled Three.js review application."""

from importlib.resources import files


def viewer_assets_path():
    """Return the installed viewer asset directory."""
    return files("tuba.visualization").joinpath("_viewer")
