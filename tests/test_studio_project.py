import json
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"

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

from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle

LOAD_CASES = ()
SOLVER_OPTIONS = {}
ARTIFACT_DIR = None
VOLUME_EXPORT = None
#: Cleared by a test to hold a review build open.
GATE = threading.Event()
GATE.set()


def build_review(namespace, output, *, artifact_dir=None, force=False):
    GATE.wait(10)
    root = Path(output) / "review_scene"
    write_scene_bundle(build_visualization_scene(SceneRequest(namespace["model"])), root)
    return root
"""


class _RecordingClient:
    """A broker client that keeps broadcasts in a list instead of a socket."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def send_json(self, event: dict) -> None:
        self.events.append(event)

    def close(self) -> None:
        pass


class StudioProjectModeTest(unittest.TestCase):
    def _server(self, root: Path, study: str = STUDY):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(MODEL, encoding="utf-8")
        (project / "study.py").write_text(study, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        server._recorder = _RecordingClient()
        server.broker.add(server._recorder)
        self.addCleanup(server.stop)
        return server

    def _start(self, root: Path):
        return self._server(root).start()

    def _rack_server(self, root: Path, *, evidence: bool = True, study_edit=lambda text: text, solver=None):
        """A studio on a copy of the support-rack project, started and settled after its startup import."""
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        shutil.copytree(SUPPORT_RACK, project, ignore=None if evidence else shutil.ignore_patterns("evidence"))
        study = project / "study.py"
        study.write_text(study_edit(study.read_text(encoding="utf-8")), encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05, solver=solver)
        server._recorder = _RecordingClient()
        server.broker.add(server._recorder)
        self.addCleanup(server.stop)
        server.start()
        self._wait(lambda: self._idle(server), "the startup import never settled", timeout=120.0)
        return server, project

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

    def _events(self, server, kind: str) -> int:
        return sum(event.get("type") == kind for event in server._recorder.events)

    def _idle(self, server) -> bool:
        info = self._get(server, "api/project")
        return not info["preparing_review"] and not info["solving"]

    def test_a_model_only_study_builds_its_review_at_startup_and_again_on_solve(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)

        self.assertTrue((root / "out" / "build" / "scene.json").is_file())
        self._wait(lambda: self._idle(server), "the model-only review was never built")
        info = self._get(server, "api/project")
        keys = ("name", "has_study", "can_solve", "solves", "has_review", "review_stale", "solving", "unverified")
        self.assertEqual(
            {key: info[key] for key in keys},
            {"name": "project", "has_study": True, "can_solve": True, "solves": False, "has_review": True,
             "review_stale": False, "solving": False, "unverified": []},
        )

        self.assertEqual(self._post(server, "api/solve", Origin="http://evil.example")[0], 403)
        self.assertEqual(self._post(server, "api/solve", {"force": "yes"})[0], 400)

        self.assertEqual(self._post(server, "api/solve"), (202, {"ok": True}))
        self._wait(lambda: self._events(server, "solve_finished") == 1 and self._idle(server), "the solve never finished")
        # Nothing had to be solved, so nothing was claimed, staged or promoted.
        self.assertEqual(sorted(path.name for path in (root / "project").iterdir()), ["model.py", "study.py"])

        # This study's review carries no solver evidence, so nothing in it can go stale (spec decision 15).
        status, payload = self._post(server, "api/script", {"code": MODEL.replace("run(2.0)", "run(3.0)")})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])
        self.assertFalse(self._get(server, "api/project")["review_stale"])

    def test_build_serves_the_code_aster_commands_a_solve_would_run_now(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._server(root, STUDY.replace("LOAD_CASES = ()", 'LOAD_CASES = ("Operating",)')).start()
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

    def test_watcher_survives_an_unreadable_model_file(self):
        from unittest import mock

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)
        before = server.revision

        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("locked mid-save")):
            time.sleep(0.4)  # several polls under an unreadable file
            self.assertTrue(server._watch_thread.is_alive())
        (root / "project" / "model.py").write_text(MODEL.replace("run(2.0)", "run(3.0)"), encoding="utf-8")
        self._wait(lambda: server.revision > before, "the watcher never recovered to rerun the model")

    def test_an_imported_review_goes_stale_only_when_its_solver_input_changes(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server, project = self._rack_server(root)
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

        moved = model.replace("[-2.0, 0.0, 3.25]", "[-2.5, 0.0, 3.25]")
        status, payload = self._post(server, "api/script", {"code": moved})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])
        self.assertTrue(self._get(server, "api/project")["review_stale"])

    def test_invalid_study_solver_options_keep_the_studio_usable_and_mark_the_review_stale(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server, project = self._rack_server(
            root,
            study_edit=lambda text: text.replace("SOLVER_OPTIONS: dict = {}", 'SOLVER_OPTIONS: dict = {"line_segments": 0}'),
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
        self._wait(lambda: any(event.get("type") == "review_ready" for event in server._recorder.events), "no review_ready")
        self._wait(lambda: self._idle(server), "the import never released")
        info = self._get(server, "api/project")
        self.assertEqual((info["preparing_review"], info["has_review"], info["solving"]), (False, True, False))

    def test_a_second_solve_waits_for_the_first(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start(Path(tmpdir))
        self._wait(lambda: self._idle(server), "the model-only review was never built")
        server.study.GATE.clear()
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self.assertEqual(self._post(server, "api/solve")[0], 409)
        server.study.GATE.set()
        self._wait(lambda: self._idle(server), "the solve never released")
        self.assertEqual(self._events(server, "solve_finished"), 1)
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self._wait(lambda: self._events(server, "solve_finished") == 2, "the second solve never finished")

    def test_solve_lands_evidence_reuses_it_and_a_forced_solve_runs_again(self):
        from tests.project_replay import ReplaySolver

        root = Path(self.enterContext(TemporaryDirectory()))
        solver = ReplaySolver(SUPPORT_RACK / "evidence")
        server, project = self._rack_server(root, evidence=False, solver=solver)

        for count, body, solved in (
            (1, None, ["Operating"]),
            (2, None, ["Operating"]),  # the evidence still matches: reused, not solved
            (3, {"force": True}, ["Operating", "Operating"]),
        ):
            self.assertEqual(self._post(server, "api/solve", body), (202, {"ok": True}))
            self._wait(
                lambda count=count: self._events(server, "solve_finished") == count and self._idle(server),
                f"solve {count} never finished",
                timeout=120.0,
            )
            self.assertEqual(solver.solved, solved)
        self.assertTrue((project / "evidence" / "Operating" / "study_execution.json").is_file())
        info = self._get(server, "api/project")
        self.assertEqual(
            (info["has_review"], info["review_stale"], info["review_error"], info["unverified"]),
            (True, False, None, []),
        )

    def test_a_solve_another_process_holds_makes_the_studio_busy(self):
        from tuba.project.claim import claim_solve

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)
        self._wait(lambda: self._idle(server), "the model-only review was never built")

        with claim_solve(root / "project"):
            self.assertTrue(self._get(server, "api/project")["solving"])
            status, payload = self._post(server, "api/solve")
            self.assertEqual(status, 409)
            self.assertIn("Another process", payload["error"])
        self.assertFalse(self._get(server, "api/project")["solving"])

    def test_an_unverified_solve_is_written_and_reported_but_not_published(self):
        from tests.project_replay import ReplaySolver

        root = Path(self.enterContext(TemporaryDirectory()))
        replay = ReplaySolver(SUPPORT_RACK / "evidence", execution_method="docker")
        server, project = self._rack_server(root, evidence=False, solver=replay)

        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self._wait(
            lambda: self._events(server, "solve_failed") == 1 and self._idle(server),
            "the unverified solve never failed",
            timeout=120.0,
        )
        written = json.loads((project / "evidence" / "Operating" / "study_execution.json").read_text(encoding="utf-8"))
        self.assertEqual(written["execution_method"], "docker")
        info = self._get(server, "api/project")
        self.assertEqual(info["unverified"], ["Operating"])
        self.assertIn("result_trust == 'verified'", info["review_error"])


if __name__ == "__main__":
    unittest.main()
