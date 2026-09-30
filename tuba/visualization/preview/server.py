"""Project-studio host: a project folder's Build and Review bundles over the preview transport."""

from __future__ import annotations

import shutil
import json
import re
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
        self._ifc_lock = threading.RLock()
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
            if artifact_dir is not None and operations and not artifact_dir.exists():
                # Portable project ZIPs omit evidence; Solve remains available.
                return self
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
        with self._ifc_lock:
            return self._publish_scene_locked()

    def _publish_scene_locked(self) -> dict[str, Any]:
        from tuba.visualization.builders import SceneRequest, build_visualization_scene

        self.revision += 1
        scene = build_visualization_scene(SceneRequest(self.model, include_analysis_mesh=True, clash_results=self._model_clashes()))
        self._merge_ifc_references(scene)
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
        with self._ifc_lock:
            self._produce_review_locked(namespace, artifact_dir=artifact_dir)

    def _produce_review_locked(self, namespace: dict[str, Any], *, artifact_dir: Path | None) -> None:
        from tuba.project.freshness import attested_identities

        work = self.out_dir / ".review-work"
        shutil.rmtree(work, ignore_errors=True)
        root = self._review_builder()(namespace, work, artifact_dir=artifact_dir)
        self._rewrite_review_references(Path(root))
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
            "ifc": self.ifc_capability(),
        }

    def profile_library(self) -> dict[str, Any]:
        from tuba.model import IBeamSection, PipeSection
        from tuba.sections import SectionCatalog
        from tuba.visualization.builders._objects import _section_profile_metadata

        catalog = []
        sections = SectionCatalog.default()
        for row in sections.list_ibeam_profiles():
            family = re.sub(r"\d.*", "", row.name)
            if family == "HE":
                family += row.name[-1]
            section = IBeamSection(row.name, row.name, dict(row.properties))
            catalog.append({"name": row.name, "family": family,
                            "profile": _section_profile_metadata(section)})
        for row in sections.list_pipe_profiles():
            section = PipeSection(row.name, row.OD, row.WT)
            catalog.append({"name": row.name, "family": "Pipe", "dn": row.dn,
                            "nps": row.nps, "schedule": row.schedule,
                            "profile": _section_profile_metadata(section),
                            "source": "ASME B36.10 — InfraBuild pipe chart (October 2022, page 3). Nominal dimensions in mm; manufacturing tolerances and corrosion allowance are excluded.",
                            "source_url": "https://www.infrabuild.com/wp-content/uploads/sites/8/2019/05/IBSC_Pipe-Fittings-Data-Charts_A4_Oct22_24pp.pdf"})
        model = self.model
        used = [{"name": section.name, "profile_name": getattr(section, "profile_name", None),
                 "source_line": section.source_line, "profile": _section_profile_metadata(section)}
                for section in (model.sections.values() if model is not None else ())]
        return {"ok": True, "catalog": catalog, "used": used,
                "source": "Tuba bundled IBeam.input / IBeam.output",
                "source_note": "Imported profile tables; original geometry source and Code_Aster version are not recorded."}

    @property
    def _ifc_root(self) -> Path:
        return self.project.root / "references" / "ifc"

    def _ifc_manifests(self):
        for path in sorted(self._ifc_root.glob("*/manifest.json")):
            if re.fullmatch(r"[0-9a-f]{64}", path.parent.name) and (path.parent / "source.ifc").is_file():
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    if manifest["preview"]["sha256"] == path.parent.name:
                        yield path.parent.name, manifest
                except (OSError, ValueError, KeyError):
                    continue

    def ifc_capability(self) -> dict[str, Any]:
        from tuba.external.ifc_reference import require_ifc

        try:
            require_ifc()
            available, reason = True, None
        except ImportError as exc:
            available, reason = False, str(exc)
        return {"available": available, "reason": reason, "max_upload_bytes": 16777216,
                "export": "geometry-only", "references": [self._ifc_summary(identity, manifest)
                                                       for identity, manifest in self._ifc_manifests()],
                "export_scope": "Native Tuba model geometry only; IFC references are excluded",
                "export_available": available and self._ifc_export_issue() is None,
                "export_reason": self._ifc_export_issue()}

    def _ifc_export_issue(self) -> str | None:
        model = self.model
        if model is None:
            return "model.py has not run successfully yet"
        if model.imported_components or model.cad_assets or model.mesh_groups:
            return "Imported components, CAD assets, or mesh groups cannot be included in IFC export"
        if model.tees:
            return "Tee records cannot be included in IFC export"
        if any(element.type not in {"pipe_straight", "pipe_bend", "beam", "bar", "cable"} for element in model.elements):
            return "An element type cannot be included in IFC export"
        if any(obstacle.get("type") != "cuboid" for obstacle in model.obstacles):
            return "Only cuboid obstacles can be included in IFC export"
        return None

    @staticmethod
    def _ifc_summary(identity: str, manifest: dict) -> dict[str, Any]:
        preview = manifest["preview"]
        return {"id": identity, "name": preview["name"], "product_count": len(preview["products"]),
                "warning_count": len(preview["warnings"])}

    def _merge_ifc_references(self, scene):
        from tuba.external.ifc_reference import merge_reference

        for identity, manifest in self._ifc_manifests():
            merge_reference(scene, identity, manifest)

    def _rewrite_review_references(self, root: Path) -> None:
        from tuba.visualization.scene import VisualizationScene

        path = root / "scene.json"
        if not path.is_file():
            return
        scene = VisualizationScene.from_dict(json.loads(path.read_text(encoding="utf-8")))
        scene.objects = [obj for obj in scene.objects if not obj.id.startswith("ifc:")]
        scene.geometry_assets = [asset for asset in scene.geometry_assets if not asset.id.startswith("ifc:")]
        scene.layers = [layer for layer in scene.layers if not layer.id.startswith("ifc:")]
        for asset in scene.geometry_assets:
            if asset.uri:
                payload = json.loads((root / asset.uri).read_text(encoding="utf-8"))
                asset.generation_config = payload["generation_config"]
        self._merge_ifc_references(scene)
        source = root / "source.py"
        source_bytes = source.read_bytes() if source.is_file() else None
        write_scene_bundle(scene, root)
        if source_bytes is not None:
            source.write_bytes(source_bytes)

    def _republish_ifc(self) -> tuple[str, str]:
        if self.model is not None:
            self._publish_scene()
        review = self.out_dir / "review"
        if (review / "scene.json").is_file():
            staging = self.out_dir / ".ifc-review-staging"
            shutil.rmtree(staging, ignore_errors=True)
            shutil.copytree(review, staging)
            self._rewrite_review_references(staging)
            self._swap_bundle("review", staging)
        return f"{self.base_url}build/", f"{self.base_url}review/"

    def ifc_request(self, route: str, body: bytes | None = None, name: str = "reference.ifc"):
        with self._ifc_lock:
            return self._ifc_request_locked(route, body, name)

    def _ifc_request_locked(self, route: str, body: bytes | None, name: str):
        from tuba.external.ifc_reference import conversion_zip, extract, require_ifc, validate_assignment

        try:
            require_ifc()
            if route == "preview":
                preview, _ = extract(body or b"", name)
                return 200, {"ok": True, "preview": preview}
            if route == "attach":
                preview, meshes = extract(body or b"", name)
                identity = preview["sha256"]
                target = self._ifc_root / identity
                if target.is_dir():
                    return 200, {"ok": True, "reference": self._ifc_summary(identity, json.loads((target / "manifest.json").read_text(encoding="utf-8"))),
                                 "build_url": f"{self.base_url}build/", "review_url": f"{self.base_url}review/"}
                self._ifc_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=self._ifc_root) as temp:
                    folder = Path(temp)
                    (folder / "source.ifc").write_bytes(body)
                    manifest = {"preview": preview, "meshes": meshes}
                    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                    folder.rename(target)
                try:
                    build_url, review_url = self._republish_ifc()
                except Exception:
                    shutil.rmtree(target)
                    self._republish_ifc()
                    raise
                return 201, {"ok": True, "reference": self._ifc_summary(identity, manifest),
                             "build_url": build_url, "review_url": review_url}
            if route == "export":
                issue = self._ifc_export_issue()
                if issue:
                    return 409, {"ok": False, "error": issue}
                from tuba.external.ifc import IfcExporter
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "export.ifc"
                    IfcExporter().export_model(self.model, path)
                    return 200, path.read_bytes()
            try:
                payload = json.loads((body or b"").decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return 400, {"ok": False, "error": "Invalid JSON body"}
            if not isinstance(payload, dict):
                return 400, {"ok": False, "error": "Expected JSON object"}
            identity = payload.get("id" if route == "remove" else "reference_id")
            if not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{64}", identity) is None:
                return 400, {"ok": False, "error": "Invalid reference ID"}
            target = self._ifc_root / identity
            if not (target / "source.ifc").is_file():
                return 404, {"ok": False, "error": "Unknown IFC reference"}
            if route == "remove":
                if set(payload) != {"id"}:
                    return 400, {"ok": False, "error": "Expected only reference ID"}
                retired = self._ifc_root / f".{identity}-removing"
                target.rename(retired)
                try:
                    build_url, review_url = self._republish_ifc()
                except Exception:
                    retired.rename(target)
                    self._republish_ifc()
                    raise
                shutil.rmtree(retired)
                return 200, {"ok": True, "id": identity, "build_url": build_url, "review_url": review_url}
            if route == "convert":
                guids, material, section = validate_assignment(payload)
                return 200, conversion_zip((target / "source.ifc").read_bytes(), guids, material, section)
            return 404, {"ok": False, "error": "Unknown IFC route"}
        except ImportError as exc:
            return 503, {"ok": False, "error": str(exc)}
        except KeyError as exc:
            return 404, {"ok": False, "error": str(exc)}
        except ValueError as exc:
            return 422, {"ok": False, "error": str(exc)}
        except (OSError, RuntimeError) as exc:
            return 500, {"ok": False, "error": f"IFC operation failed: {exc}"}

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


