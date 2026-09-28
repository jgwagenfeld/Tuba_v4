from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from scripts.build_browser_runtime import browser_runtime_archive


def test_browser_runtime_contains_current_python_and_data_but_no_results_or_viewer():
    root = Path(__file__).resolve().parents[1]
    archive = browser_runtime_archive(root)
    assert archive == browser_runtime_archive(root)
    with ZipFile(BytesIO(archive)) as bundle:
        assert {entry.create_system for entry in bundle.infolist()} == {3}
        assert bundle.read("examples/assets/imported_component_demo.stl") == (root / "examples/assets/imported_component_demo.stl").read_bytes()
        assert bundle.read("tuba/model.py") == (root / "tuba/model.py").read_bytes().replace(b"\r\n", b"\n")
        assert bundle.read("tuba/visualization/builders/_objects.py") == (root / "tuba/visualization/builders/_objects.py").read_bytes().replace(b"\r\n", b"\n")
        assert "examples/code-aster-review/model.py" in bundle.namelist()
        assert any("sections/data/" in name for name in bundle.namelist())
        assert not any("/evidence/" in name or "/_viewer/" in name or name.endswith(".rmed") for name in bundle.namelist())
