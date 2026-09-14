import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MODEL = """from tuba import Model

model = Model("StudioProject")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(2.0)
    builder.end(support="anchor")
"""

STUDY = """import threading
from pathlib import Path

from tuba.visualization import build_visualization_scene, write_scene_bundle

LOAD_CASES = ("Operating",)
SOLVER_OPTIONS = {}
ARTIFACT_DIR = None
VOLUME_EXPORT = None
#: Cleared by a test to hold a solve open, where a real study would be running Code_Aster.
GATE = threading.Event()
GATE.set()


def build_review(namespace, output, *, artifact_dir=None, force=False):
    GATE.wait(10)
    root = Path(output) / "review_scene"
    write_scene_bundle(build_visualization_scene(namespace["model"]), root)
    return root
"""


class StudioProjectModeTest(unittest.TestCase):
    def _server(self, root: Path, study: str = STUDY):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(MODEL, encoding="utf-8")
        (project / "study.py").write_text(study, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        self.addCleanup(server.stop)
        return server

    def _start(self, root: Path):
        return self._server(root).start()

    def _get(self, server, path: str) -> dict:
        with urlopen(server.base_url + path, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, server, path: str, payload: dict | None = None, **headers):
        request = Request(
            server.base_url + path,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _wait(self, condition, message: str) -> None:
        deadline = time.time() + 10
        while time.time() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail(message)

    def _solves_finished(self, server) -> int:
        return sum(event.get("type") == "solve_finished" for event in server.broker.events)

    def test_build_and_review_bundles_solve_and_go_stale(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)
        out = root / "out"

        self.assertTrue((out / "build" / "scene.json").is_file())
        self.assertEqual(sorted(path.name for path in (root / "project").iterdir()), ["model.py", "study.py"])
        info = self._get(server, "api/project")
        self.assertEqual(
            {key: info[key] for key in ("name", "has_study", "can_solve", "solves", "has_review", "review_stale", "solving")},
            {"name": "project", "has_study": True, "can_solve": True, "solves": True, "has_review": False,
             "review_stale": False, "solving": False},
        )

        self.assertEqual(self._post(server, "api/solve", Origin="http://evil.example")[0], 403)

        self.assertEqual(self._post(server, "api/solve"), (202, {"ok": True}))
        self._wait(lambda: self._solves_finished(server) == 1, "the solve never finished")
        self.assertTrue((out / "review" / "scene.json").is_file())
        self.assertTrue(self._get(server, "api/project")["has_review"])

        status, payload = self._post(server, "api/script", {"code": MODEL.replace("run(2.0)", "run(3.0)")})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])
        self.assertTrue(self._get(server, "api/project")["review_stale"])

    def test_attested_evidence_imports_after_startup_without_holding_it_up(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._server(Path(tmpdir), STUDY.replace("ARTIFACT_DIR = None", "ARTIFACT_DIR = Path(__file__).parent"))
        server.study.GATE.clear()
        server.start()

        info = self._get(server, "api/project")
        self.assertEqual((info["preparing_review"], info["has_review"], info["solving"]), (True, False, False))
        self.assertEqual(self._post(server, "api/solve")[0], 409)

        server.study.GATE.set()
        self._wait(lambda: any(event.get("type") == "review_ready" for event in server.broker.events), "no review_ready")
        info = self._get(server, "api/project")
        self.assertEqual((info["preparing_review"], info["has_review"], info["solving"]), (False, True, False))

    def test_a_second_solve_waits_for_the_first(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start(Path(tmpdir))
        server.study.GATE.clear()
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self.assertEqual(self._post(server, "api/solve")[0], 409)
        server.study.GATE.set()
        self._wait(lambda: not self._get(server, "api/project")["solving"], "the solve never released")
        self.assertEqual(self._solves_finished(server), 1)
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self._wait(lambda: self._solves_finished(server) == 2, "the second solve never finished")


if __name__ == "__main__":
    unittest.main()
