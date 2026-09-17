"""Project-studio host: a project folder's Build and Review bundles over the preview transport."""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tuba.model import TubaModel
from tuba.visualization.preview.transport import PreviewServer
from tuba.visualization.web_export import write_scene_bundle

if TYPE_CHECKING:
    from tuba.project.study import StudySettings


class ProjectStudioServer(PreviewServer):
    """The studio for a project folder: ``model.py`` drives Build, ``study.py`` drives Review.

    The live model scene is the ``build/`` bundle and the solved or imported review is
    ``review/``. A Run never overwrites a review, and Review never shows results for a
    model that has changed since without saying so (``review_stale``): a review is stale
    when an operation it was solved for would now attest a different identity.
    """

    def __init__(
        self,
        project: str | Path,
        out_dir: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.2,
        solver: Any = None,
    ) -> None:
        from tuba.project import load_project
        from tuba.project.freshness import attested_identities

        self.project = load_project(project)
        super().__init__(
            self.project.model_path,
            out_dir,
            host=host,
            port=port,
            poll_interval_s=poll_interval_s,
            debounce_s=debounce_s,
        )
        self.model: TubaModel | None = None
        self.namespace: dict[str, Any] | None = None
        self.study = self.project.load_study()
        self.review_error: str | None = None
        # review_stale runs on every save, and a review scene can be tens of MB: read its identities
        # once per bundle, here for a bundle left on disk and in _produce_review for each new one.
        self._review_identities = attested_identities(self.out_dir / "review")
        self._solve_lock = threading.Lock()
        # Busy with a review (the startup import or a Solve); _preparing marks the import.
        self._solving = False
        self._preparing = False
        # The solver port a Solve hands to the project solve: Code_Aster when None, a replay in tests.
        self.solver = solver
        #: The operations the last Solve left unverified (spec decision 18).
        self.unverified: tuple[str, ...] = ()

    def _study_settings(self) -> "StudySettings":
        """The study's validated settings; raises when there is no study or they are invalid."""
        from tuba.project.study import study_settings

        if self.study is None:
            raise ValueError(f"{self.project.name} has no study.py to solve.")
        return study_settings(self.study)

    def _study_settings_or_none(self) -> "StudySettings | None":
        """Validated settings for display and staleness; None when there is no study or it is invalid."""
        if self.study is None:
            return None
        try:
            return self._study_settings()
        except ValueError:
            return None

    def _declared_operations(self) -> tuple[str, ...]:
        """The operations study.py declares: what it would solve, even when its options are invalid."""
        settings = self._study_settings_or_none()
        if settings is not None:
            return settings.operations
        return tuple(getattr(self.study, "LOAD_CASES", ()) or ())

    def _declared_artifact_dir(self) -> Path | None:
        """study.py's declared ARTIFACT_DIR: the import-only review path needs no solver options."""
        settings = self._study_settings_or_none()
        if settings is not None:
            return settings.artifact_dir
        declared = getattr(self.study, "ARTIFACT_DIR", None)
        return Path(declared) if declared is not None else None

    def _review_builder(self):
        """The study's review builder; the import-only path does not need valid solver options."""
        settings = self._study_settings_or_none()
        builder = settings.build_review if settings is not None else getattr(self.study, "build_review", None)
        if not callable(builder):
            raise ValueError(f"{self.project.name}'s study.py defines no build_review(namespace, output, ...).")
        return builder

    def start(self) -> "ProjectStudioServer":
        super().start()
        result, event = self._run_script()
        if not result["ok"]:
            self.broker.broadcast(event)
            return self
        artifact_dir = self._declared_artifact_dir()
        operations = self._declared_operations()
        if self.study is not None and (artifact_dir is not None or not operations):
            # Attested evidence imports without a solver, and a study with no solver
            # has nothing to wait for; a study that must solve waits for Solve. It runs
            # in the background: the viewer is already up and hears review_ready.
            with self._solve_lock:
                self._solving = self._preparing = True
            threading.Thread(
                target=self._prepare_review,
                args=(self.namespace, artifact_dir),
                name="tuba-studio-review",
                daemon=True,
            ).start()
        return self

    def run_once(self) -> None:
        # model.py is the source of truth: a save from any editor reruns it.
        result, event = self._run_script()
        if not result["ok"]:
            # The last good scene stays; tell viewers why it did not change.
            self.broker.broadcast(event)

    def get_python_script(self) -> str:
        return self.script_path.read_text(encoding="utf-8")

    def execute_python_code(self, code: str) -> dict[str, Any]:
        """Save *code* as model.py, run it, and broadcast the live scene."""
        self.mark_saved(code)
        return self._run_script()[0]

    def _run_script(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run model.py; on success validate it and publish its scene.

        Returns the /api/script response and the viewer event: ``scene_reloaded``, or
        ``script_error`` when the script fails (the previous scene is left as it was).
        """
        from tuba.project import run_model_script
        from tuba.validation import validate_model

        # ponytail: scripts run in-process, so an infinite loop still hangs the server;
        # upgrade path is a subprocess with a timeout.
        try:
            namespace = run_model_script(self.script_path)
            new_model = namespace["model"]
            validate_model(new_model)
            self.model = new_model
            # Kept for Solve: a study reviews the script's globals, not just the model.
            self.namespace = namespace
            event = self._publish_scene()
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # sys.exit() in a script fails the run, not the request
            error = f"{type(exc).__name__}: {exc}"
            line = _script_error_line(exc, self.script_path)
            return (
                {"ok": False, "error": error, "line": line, "traceback": traceback.format_exc()},
                {"type": "script_error", "error": error, "line": line},
            )
        return (
            {
                "ok": True,
                "revision": self.revision,
                "results_stale": event["results_stale"],
                "review_stale": event["review_stale"],
                "nodes": len(self.model.nodes),
                "elements": len(self.model.elements),
            },
            event,
        )

    def _prepare_review(self, namespace: dict[str, Any], artifact_dir: Path | None) -> None:
        try:
            self._produce_review(namespace, artifact_dir=artifact_dir)
        except Exception as exc:
            self.review_error = f"{type(exc).__name__}: {exc}"
            self.broker.broadcast({"type": "review_failed", "error": self.review_error})
        else:
            self.broker.broadcast({
                "type": "review_ready",
                "bundle": "review",
                "bundle_url": f"{self.base_url}review/",
                "review_stale": self.review_stale,
            })
        finally:
            with self._solve_lock:
                self._solving = self._preparing = False

    @property
    def review_stale(self) -> bool:
        """Spec decision 15 and ADR-0005: the review is stale when its evidence is no longer reusable."""
        from tuba.project.freshness import stale_operations

        if self.model is None or self.study is None:
            return False
        settings = self._study_settings_or_none()
        if settings is None:
            # study.py's solver options are invalid: nothing it would solve can match the review, and a Solve reports why.
            return True
        attested = self._review_identities
        if not attested:
            return False
        try:
            stale = stale_operations(
                self.model,
                attested,
                project_root=self.project.root,
                solver_options=settings.solver_options,
                volume_export=settings.volume_export,
            )
        except (TypeError, ValueError):
            return True
        return bool(stale)

    def _publish_scene(self) -> dict[str, Any]:
        from tuba.visualization.builders import SceneRequest, build_visualization_scene

        self.revision += 1
        scene = build_visualization_scene(SceneRequest(self.model, include_analysis_mesh=True, clash_results=self._model_clashes()))
        staging = self.out_dir / ".build-staging"
        shutil.rmtree(staging, ignore_errors=True)
        write_scene_bundle(scene, staging)
        self._swap_bundle("build", staging)
        stale = self.review_stale
        event = {
            "type": "scene_reloaded",
            "revision": self.revision,
            "bundle_revision": self.revision,
            "scene_id": scene.scene_id,
            "scene_uri": "scene.json",
            "bundle": "build",
            "bundle_url": f"{self.base_url}build/",
            "review_stale": stale,
            "results_stale": stale,
            "objects": len(scene.objects),
            "issues": len(scene.issues),
        }
        self.broker.broadcast(event)
        return event

    def _model_clashes(self) -> list[Any]:
        """Cold-model clashes for the live Build scene: obstacles, self, duplicates."""
        from tuba.clash import ClashEngine

        return ClashEngine().check_all(self.model)

    def _swap_bundle(self, name: str, source: Path) -> None:
        """Move a finished bundle into place, so a half-written one is never served."""
        target = self.out_dir / name
        retired = self.out_dir / f".{name}-retired"
        shutil.rmtree(retired, ignore_errors=True)
        for attempt in range(5):
            try:
                if target.exists():
                    target.rename(retired)
                Path(source).rename(target)
                shutil.rmtree(retired, ignore_errors=True)
                break
            except OSError:
                if attempt == 4:
                    shutil.copytree(source, target, dirs_exist_ok=True)
                    shutil.rmtree(source, ignore_errors=True)
                    shutil.rmtree(retired, ignore_errors=True)
                else:
                    time.sleep(0.1)

    def _produce_review(self, namespace: dict[str, Any], *, artifact_dir: Path | None) -> None:
        from tuba.project.freshness import attested_identities

        work = self.out_dir / ".review-work"
        shutil.rmtree(work, ignore_errors=True)
        root = self._review_builder()(namespace, work, artifact_dir=artifact_dir)
        identities = attested_identities(Path(root))
        self._swap_bundle("review", Path(root))
        self._review_identities = identities
        self.review_error = None
        shutil.rmtree(work, ignore_errors=True)

    def project_info(self) -> dict[str, Any]:
        from tuba.project.claim import solve_claimed

        operations = self._declared_operations()
        return {
            "ok": True,
            "name": self.project.name,
            "has_study": self.study is not None,
            "can_solve": self.study is not None and self.namespace is not None,
            "solves": bool(operations),
            "load_cases": list(operations),
            "has_review": (self.out_dir / "review" / "scene.json").is_file(),
            "review_stale": self.review_stale,
            "review_error": self.review_error,
            "solving": (self._solving and not self._preparing) or solve_claimed(self.project.root),
            "preparing_review": self._preparing,
            "unverified": list(self.unverified),
        }

    def code_aster_commands(self, case: str) -> tuple[int, dict[str, Any]]:
        """The ``study.comm`` a Solve of *case* would compile now from model.py and study.py.

        Generated on request into a scratch folder the same way the gallery studies export
        before solving; nothing is solved and nothing is written into the project.
        """
        if self.study is None:
            return 404, {"ok": False, "error": f"study.py solves no load case {case!r}."}
        try:
            settings = self._study_settings()
        except ValueError as exc:  # invalid solver options are the answer, not a stale file
            return 422, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if case not in settings.operations:
            return 404, {"ok": False, "error": f"study.py solves no load case {case!r}."}
        model = self.model
        if model is None:
            return 400, {"ok": False, "error": "model.py has not run successfully yet."}
        from tuba.project.freshness import export_study

        # ignore_cleanup_errors: on Windows a mesher can still hold a file in the folder for a moment.
        with tempfile.TemporaryDirectory(prefix="tuba-comm-", ignore_cleanup_errors=True) as work:
            try:
                study = export_study(settings.solver(work), model, case, work, settings.volume_export)
                code = Path(study.input_files["comm"]).read_text(encoding="utf-8")
            except Exception as exc:  # a case the model can no longer compile
                return 422, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return 200, {"ok": True, "case": case, "code": code}

    def start_solve(self, force: bool = False) -> tuple[int, dict[str, Any]]:
        from tuba.project.claim import solve_claimed

        if self.study is None:
            return 400, {"ok": False, "error": f"{self.project.name} has no study.py to solve."}
        if self.namespace is None:
            return 400, {"ok": False, "error": "model.py has not run successfully yet."}
        with self._solve_lock:
            if self._solving:
                busy = "The review is still being imported." if self._preparing else "A solve is already running."
                return 409, {"ok": False, "error": busy}
            if solve_claimed(self.project.root):
                return 409, {"ok": False, "error": "Another process is solving this project."}
            self._solving = True
        threading.Thread(
            target=self._solve, args=(self.namespace, force), name="tuba-studio-solve", daemon=True
        ).start()
        return 202, {"ok": True}

    def _solve(self, namespace: dict[str, Any], force: bool = False) -> None:
        from tuba.project.evidence import study_artifact_dir
        from tuba.project.solve import solve_project

        self.broker.broadcast({"type": "solve_started"})
        try:
            operations = self._study_settings().operations
            artifact_dir = None
            if operations:
                # Spec decisions 11 and 13: bring the project's evidence up to date, then review it.
                self.unverified = solve_project(self.project, namespace, force=force, solver=self.solver).unverified
                artifact_dir = study_artifact_dir(self.project.root, operations)
            self._produce_review(namespace, artifact_dir=artifact_dir)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # a study calling sys.exit() fails the solve, not the server
            self.review_error = f"{type(exc).__name__}: {exc}"
            self.broker.broadcast({"type": "solve_failed", "error": self.review_error})
        else:
            self.broker.broadcast({
                "type": "solve_finished",
                "bundle": "review",
                "bundle_url": f"{self.base_url}review/",
                "review_stale": self.review_stale,
            })
        finally:
            with self._solve_lock:
                self._solving = False


def _script_error_line(exc: BaseException, script_path: Path) -> int | None:
    """The model.py line to blame for *exc*: a syntax error's own line, else the
    innermost traceback frame in the script; None when the script is not on the stack."""
    script = script_path.resolve()
    if isinstance(exc, SyntaxError) and exc.filename and Path(exc.filename).resolve() == script:
        return exc.lineno
    lines = [
        lineno
        for frame, lineno in traceback.walk_tb(exc.__traceback__)
        if Path(frame.f_code.co_filename).resolve() == script
    ]
    return lines[-1] if lines else None


