from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _project():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_distribution_declares_lgpl_license():
    project = _project()

    assert project["license"] == "LGPL-3.0-or-later"
    assert (ROOT / "LICENSE").is_file()


def test_heavy_geometry_readers_are_optional():
    project = _project()
    dependencies = " ".join(project["dependencies"]).lower()

    assert "scipy" not in dependencies
    assert "meshio" not in dependencies
    assert "trimesh" not in dependencies
    assert "python-fcl" not in dependencies
    assert {"collision", "viz"} <= set(project["optional-dependencies"])


def test_publish_workflows_exist():
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_installed_distribution_owns_the_web_viewer():
    from tuba.visualization import viewer_assets_path

    assets = viewer_assets_path()
    assert assets.joinpath("index.html").is_file()
    assert any(assets.joinpath("assets").glob("*.js"))
