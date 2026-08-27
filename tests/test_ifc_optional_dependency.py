import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ifc_module_defers_missing_dependency_until_use():
    script = r'''
import sys

class BlockIfcOpenShell:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ifcopenshell" or fullname.startswith("ifcopenshell."):
            raise ModuleNotFoundError("blocked for optional-dependency test", name=fullname)
        return None

sys.meta_path.insert(0, BlockIfcOpenShell())
from tuba.external.ifc import IfcExporter, _HAS_IFCOPENSHELL

assert _HAS_IFCOPENSHELL is False
try:
    IfcExporter()
except ImportError as exc:
    assert "tuba[ifc]" in str(exc)
else:
    raise AssertionError("IfcExporter accepted a missing IfcOpenShell runtime")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_native_optional_import_errors_do_not_break_unrelated_collection(tmp_path):
    (tmp_path / "sitecustomize.py").write_text(
        r'''
import sys

class BreakOptionalWheels:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ifcopenshell" or fullname.startswith("ifcopenshell.") or fullname == "nbformat":
            raise ImportError(f"native wheel failed to load: {fullname}", name=fullname)
        return None

sys.meta_path.insert(0, BreakOptionalWheels())
''',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(tmp_path), str(ROOT)))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/test_ifc.py",
            "tests/test_ifc_mapping.py",
            "tests/test_ifc_pipe_systems.py",
            "tests/test_ifc_placements.py",
            "tests/test_code_aster_artifact_import.py",
            "tests/test_notebook_course_didactics.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_import_preserves_validated_attestation_on_result_state" in result.stdout
    assert "test_notebook_course_uses_installed_viewer_launcher" in result.stdout


def test_ifc_module_does_not_hide_internal_import_errors():
    script = r'''
import importlib.abc
import sys
import types

ifcopenshell = types.ModuleType("ifcopenshell")
ifcopenshell.__path__ = []
guid = types.ModuleType("ifcopenshell.guid")
util = types.ModuleType("ifcopenshell.util")
util.__path__ = []
representation = types.ModuleType("ifcopenshell.util.representation")
ifcopenshell.guid = guid
ifcopenshell.util = util
util.representation = representation
sys.modules.update({
    "ifcopenshell": ifcopenshell,
    "ifcopenshell.guid": guid,
    "ifcopenshell.util": util,
    "ifcopenshell.util.representation": representation,
})

class BreakInternalIfcImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tuba.external.ifc_mapping":
            raise ImportError("internal IFC mapping defect", name=fullname)
        return None

sys.meta_path.insert(0, BreakInternalIfcImport())
try:
    import tuba.external.ifc
except ImportError as exc:
    assert "internal IFC mapping defect" in str(exc)
else:
    raise AssertionError("internal IFC import defect was hidden")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
