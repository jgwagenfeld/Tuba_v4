"""Opt-in real-browser IFC exchange check; run with UV_NO_SYNC=1 uv run python."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tuba.visualization.preview.server import ProjectStudioServer
from tuba.project import run_model_script


VIEWER = ROOT / "viewer"
MODEL = """from tuba import Model
model = Model('Browser exchange')
model.add_material('Steel', E=2e11, nu=0.3)
model.add_pipe_section('DN', OD=0.1, WT=0.01)
a = model.add_node([0, 0, 0])
b = model.add_node([1, 0, 0])
model.add_element(id='P', type='pipe_straight', n1=a, n2=b, section='DN', material='Steel')
"""


def main() -> None:
    assert Path(__import__("tuba").__file__).resolve().is_relative_to(ROOT)
    fixture_bytes = runpy.run_path(str(ROOT / "tests/test_ifc_reference.py"))["fixture_bytes"]
    data, pipe_guid, fitting_guid = fixture_bytes()
    with TemporaryDirectory(prefix="tuba-ifc-browser-") as temporary:
        scratch = Path(temporary)
        project = scratch / "project"
        project.mkdir()
        (project / "model.py").write_text(MODEL, encoding="utf-8")
        fixture = scratch / "plant.ifc"
        fixture.write_bytes(data)
        server = ProjectStudioServer(project, scratch / "out", port=0).start()
        try:
            subprocess.run([
                "node", str(VIEWER / "e2e/ifc-exchange-smoke.mjs"),
                f"{server.base_url}?bundle=build&preview_ws={server.ws_url}",
                str(fixture), pipe_guid, fitting_guid, str(scratch),
            ], cwd=VIEWER, check=True, timeout=180)
            with ZipFile(scratch / "converted.zip") as archive:
                assert archive.read("source.ifc") == data
                assert {"model.py", "README.md"} <= set(archive.namelist())
                assert not any(name.startswith("evidence/") or name == "study.py" for name in archive.namelist())
                archive.extractall(scratch / "converted")
            converted = run_model_script(scratch / "converted/model.py")["model"]
            assert len(converted.elements) == 1
            pipe = converted.elements[0]
            assert pipe.type == "pipe_straight" and pipe.material == "S235JR" and pipe.section == "DN100"
            assert np.allclose([converted.nodes[node].coords for node in (pipe.n1, pipe.n2)],
                               [[2, 1, 0], [1, 1, 0]])
            assert converted.materials["S235JR"].E == 210_000_000_000
            assert converted.materials["S235JR"].nu == 0.3
            assert converted.materials["S235JR"].rho == 7850
            assert converted.sections["DN100"].OD == 0.1143
            assert converted.sections["DN100"].WT == 0.006
            assert not converted.supports and not converted.load_cases and not converted.operations
            import ifcopenshell

            exported = ifcopenshell.open(str(scratch / "export.ifc"))
            assert exported.by_type("IfcProject") and exported.by_type("IfcPipeSegment")
            assert list((project / "references/ifc").glob("*/source.ifc")) == []
            assert (project / "model.py").read_text(encoding="utf-8") == MODEL
            print(json.dumps({"result": "passed", "browser": "Chromium", "ifc": "real IfcOpenShell"}))
        finally:
            server.stop()


if __name__ == "__main__":
    main()
