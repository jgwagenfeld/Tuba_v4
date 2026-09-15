import json
import shutil
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

    def _wait(self, condition, message: str, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail(message)

    def _solves_finished(self, server) -> int:
        return sum(event.get("type") == "solve_finished" for event in server.broker.events)

    def test_build_and_review_bundles_solve_and_an_evidence_free_review_never_goes_stale(self):
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

        # This study's review carries no solver evidence, so nothing in it can go stale (spec decision 15).
        status, payload = self._post(server, "api/script", {"code": MODEL.replace("run(2.0)", "run(3.0)")})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])
        self.assertFalse(self._get(server, "api/project")["review_stale"])

    def test_build_serves_the_code_aster_commands_a_solve_would_run_now(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)
        self.assertEqual(self._get(server, "api/project")["load_cases"], ["Operating"])

        comm = self._get(server, "api/comm?case=Operating")
        self.assertTrue(comm["ok"], comm)
        self.assertIn("DEBUT", comm["code"])
        # Generated on request, never written into the project folder.
        self.assertEqual(sorted(path.name for path in (root / "project").iterdir()), ["model.py", "study.py"])

        # It follows model.py: the next request compiles the saved model.
        status, payload = self._post(server, "api/script", {"code": MODEL.replace("pressure=1.0e6", "pressure=2.5e6")})
        self.assertEqual(status, 200, payload)
        self.assertNotEqual(self._get(server, "api/comm?case=Operating")["code"], comm["code"])

        def status_of(path: str) -> tuple[int, dict]:
            try:
                return 200, self._get(server, path)
            except HTTPError as exc:
                return exc.code, json.loads(exc.read().decode("utf-8"))

        self.assertEqual(status_of("api/comm?case=Hydrotest")[0], 404)
        # It follows study.py too: options the solver rejects are the answer, not a stale file.
        server.study.SOLVER_OPTIONS = {"line_segments": 0}
        status, payload = status_of("api/comm?case=Operating")
        self.assertEqual((status, payload["ok"]), (422, False))
        self.assertIn("line_segments", payload["error"])

    def test_an_imported_review_goes_stale_only_when_its_solver_input_changes(self):
        from tuba.visualization.preview.server import ProjectStudioServer

        root = Path(self.enterContext(TemporaryDirectory()))
        project = root / "project"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "support-rack-review", project)
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        self.addCleanup(server.stop)
        server.start()
        self._wait(
            lambda: any(event.get("type") in {"review_ready", "review_failed"} for event in server.broker.events),
            "the committed evidence never imported",
            timeout=120.0,
        )
        # Saves judge staleness from the identities read when the review was produced.
        (server.out_dir / "review" / "scene.json").write_text("not json", encoding="utf-8")
        self.assertIsNone(server.review_error)
        self.assertFalse(self._get(server, "api/project")["review_stale"])

        model = (project / "model.py").read_text(encoding="utf-8")
        renamed = model.replace('Model("SupportRackReview")', 'Model("RenamedRack")') + (
            'model.define_load_case("Hydrotest", gravity=True, pressure=2.0e6)\n'
        )
        status, payload = self._post(server, "api/script", {"code": renamed})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])

        moved = model.replace("(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)")
        status, payload = self._post(server, "api/script", {"code": moved})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])
        self.assertTrue(self._get(server, "api/project")["review_stale"])

    def test_invalid_study_solver_options_keep_the_studio_usable_and_mark_the_review_stale(self):
        from tuba.visualization.preview.server import ProjectStudioServer

        root = Path(self.enterContext(TemporaryDirectory()))
        project = root / "project"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "support-rack-review", project)
        study = project / "study.py"
        study.write_text(
            study.read_text(encoding="utf-8").replace(
                "SOLVER_OPTIONS: dict = {}", 'SOLVER_OPTIONS: dict = {"line_segments": 0}'
            ),
            encoding="utf-8",
        )
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        self.addCleanup(server.stop)
        server.start()
        self._wait(
            lambda: any(event.get("type") in {"review_ready", "review_failed"} for event in server.broker.events),
            "the committed evidence never imported",
            timeout=120.0,
        )

        self.assertIsNone(server.review_error)
        info = self._get(server, "api/project")
        self.assertTrue(info["has_review"])
        self.assertTrue(info["review_stale"])
        status, payload = self._post(server, "api/script", {"code": (project / "model.py").read_text(encoding="utf-8")})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])

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
