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
