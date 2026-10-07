"""Project-studio host: a project folder's Build and Review bundles over the preview transport."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
import hashlib
import json
import os
import re
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tuba.model import TubaModel
from tuba.visualization.preview.transport import PreviewServer, file_fingerprint
from tuba.visualization.viewer import MAX_SCENE_BYTES
from tuba.visualization.web_export import write_scene_bundle

if TYPE_CHECKING:
    from tuba.project.study import StudySettings

MAX_REFERENCE_SCENE_BYTES = MAX_SCENE_BYTES


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
        allowed_dev_origin: str | None = None,
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
            allowed_dev_origin=allowed_dev_origin,
        )
        self.model: TubaModel | None = None
        self.namespace: dict[str, Any] | None = None
        self._source_error = False
        self._script_lock = threading.RLock()
        self.study = self.project.load_study()
        self._watched_paths = {self.script_path, self.project.study_path}
        self._study_paths = set(getattr(self.study, "__tuba_project_dependencies__", ())) | {self.project.study_path}
        self._watched_paths.update(self._study_paths)
        self._study_fingerprints = self._execution_fingerprints(self._study_paths, self.study)
        self._geometry_lock = threading.Lock()
        # Keep one successful preview, so Store/Attach don't repeat native parsing.
        self._geometry_preview = None
        self._ifc_preview = None
        self.review_error: str | None = None
        # review_stale runs on every save, and a review scene can be tens of MB: read its identities
        # once per bundle, here for a bundle left on disk and in _produce_review for each new one.
        self._review_identities = attested_identities(self.out_dir / "review")
        self._review_mapping_meshes = None
        self._review_mapping_mesh_error = None
        self._build_analysis_meshes = ()
        self._build_mesh_error = None
        self._solve_lock = threading.Lock()
        self._ifc_lock = threading.RLock()
        # Busy with a review (the startup import or a Solve); _preparing marks the import.
        self._solving = False
        self._preparing = False
        # The solver port a Solve hands to the project solve: Code_Aster when None, a replay in tests.
        self.solver = solver
        #: The operations the last Solve left unverified (spec decision 18).
        self.unverified: tuple[str, ...] = ()
        self._studio_session: dict[str, Any] | None = None
        self._evidence_signature = self._external_evidence_signature()
        self._executed_fingerprint = None
        from tuba.visualization.preview.mesh import MeshJobManager

        self.mesh_jobs = MeshJobManager(self)

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
        """study.py's declared ARTIFACT_DIR; evidence still requires current compiler settings."""
        settings = self._study_settings_or_none()
        if settings is not None:
            return settings.artifact_dir
        declared = getattr(self.study, "ARTIFACT_DIR", None)
        return Path(declared) if declared is not None else None

    def _review_builder(self):
        """The study's review builder; imported results must first match current study settings."""
        settings = self._study_settings_or_none()
        builder = settings.build_review if settings is not None else getattr(self.study, "build_review", None)
        if not callable(builder):
            raise ValueError(f"{self.project.name}'s study.py defines no build_review(namespace, output, ...).")
        return builder

    def start(self) -> "ProjectStudioServer":
        super().start()
        from tuba.project.session import register_studio

        try:
            self._studio_session = register_studio(self.project.root, self.base_url, self.access_token)
        except BaseException:
            super().stop()
            raise
        result, event = self._run_script()
        if not result["ok"]:
            self.broker.broadcast(event)
            return self
        artifact_dir = self._declared_artifact_dir()
        operations = self._declared_operations()
        if artifact_dir is None and self._evidence_signature and all(digest is not None for _, digest in self._evidence_signature):
            from tuba.project.evidence import study_artifact_dir

            artifact_dir = study_artifact_dir(self.project.root, operations)
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

    def stop(self) -> None:
        from tuba.project.session import unregister_studio

        try:
            self.mesh_jobs.close()
            super().stop()
        finally:
            if self._studio_session is not None:
                unregister_studio(self.project.root, self._studio_session["session_id"])
                self._studio_session = None

    def run_once(self) -> None:
        # model.py is the source of truth: a save from any editor reruns it.
        result, event = self._run_script()
        if not result["ok"]:
            # The last good scene stays; tell viewers why it did not change.
            self.broker.broadcast(event)

    def _external_evidence_signature(self):
        from tuba.project.evidence import ATTESTATION, evidence_dir

        try:
            return tuple((str(path), file_fingerprint(path)) for operation in self._declared_operations()
                         for path in (evidence_dir(self.project.root, operation) / ATTESTATION,))
        except ValueError:
            return ()  # invalid study options remain inspectable and fail at the solve entry point

    def poll_review(self) -> None:
        """Import completed CLI/MCP evidence; receipts are promoted last under the solve claim."""
        if not self._script_lock.acquire(blocking=False):
            return
        try:
            self._poll_review_locked()
        finally:
            self._script_lock.release()

    def _poll_review_locked(self) -> None:
        from tuba.project.claim import solve_claimed
        from tuba.project.evidence import study_artifact_dir

        if self.namespace is None or self._source_error or self.study is None:
            return
        if self.watch_fingerprint() != self._last_fingerprint:
            return  # run pending source edits first, so the importer sees the current model
        with self._solve_lock:
            if self._solving or self.mesh_jobs.busy or solve_claimed(self.project.root):
                return
            signature = self._external_evidence_signature()
            if not signature or signature == self._evidence_signature or any(digest is None for _, digest in signature):
                return
            self._solving = self._preparing = True
            artifact_dir = study_artifact_dir(self.project.root, self._declared_operations())
            threading.Thread(target=self._prepare_review, args=(self.namespace, artifact_dir),
                             name="tuba-studio-external-review", daemon=True).start()

    def get_python_script(self) -> dict[str, str]:
        from tuba.project.source import read_source

        return read_source(self.script_path)

    def execute_python_code(self, code: str, *, expected_revision: str | None = None) -> dict[str, Any]:
        """Save *code* as model.py, run it, and broadcast the live scene."""
        with self._script_lock:
            from tuba.project.source import SourceConflict

            try:
                revision = self.mark_saved(code, expected_revision)
            except SourceConflict as exc:
                return {"ok": False, "conflict": True, "error": str(exc), "source_revision": exc.source_revision}
            return {**self._run_script()[0], "source_revision": revision}

    @staticmethod
    def _dependency_fingerprints(paths):
        return tuple((str(path), file_fingerprint(path)) for path in sorted(paths))

    @staticmethod
    def _execution_fingerprints(paths, namespace):
        captured = dict((namespace or {}).get("__tuba_project_fingerprints__", ())) if isinstance(namespace, dict) else dict(getattr(namespace, "__tuba_project_fingerprints__", ()))
        return tuple((str(path), captured[path] if path in captured else file_fingerprint(path)) for path in sorted(paths))

    def watch_fingerprint(self) -> bytes | None:
        paths = getattr(self, "_watched_paths", {self.script_path})
        values = self._dependency_fingerprints(paths)
        if any(value is None and Path(path).exists() for path, value in values):
            return None  # an editor holds a file mid-save: retry the next poll
        return hashlib.sha256(repr(values).encode()).digest()

    def _run_script(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Serialize a complete run and publication against editor and watcher runs."""
        with self._script_lock:
            return self._run_script_locked()

    def _run_script_locked(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run model.py; on success validate it and publish its scene.

        Returns the /api/script response and the viewer event: ``scene_reloaded``, or
        ``script_error`` when the script fails (the previous scene is left as it was).
        """
        from tuba.project import run_model_script
        from tuba.validation import validate_model

        # ponytail: scripts run in-process, so an infinite loop still hangs the server;
        # upgrade path is a subprocess with a timeout.
        previous_model, previous_namespace = self.model, self.namespace
        had_source_error = self._source_error
        namespace = None
        try:
            if self._dependency_fingerprints(self._study_paths) != self._study_fingerprints:
                study = self.project.load_study()
                self.study = study
                self._study_paths = set(getattr(study, "__tuba_project_dependencies__", ())) | {self.project.study_path}
                self._study_fingerprints = self._execution_fingerprints(self._study_paths, study)
            namespace = run_model_script(self.script_path)
            new_model = namespace["model"]
            self._watched_paths.update(namespace.get("__tuba_project_dependencies__", ()))
            for asset in new_model.cad_assets.values():
                source = Path(asset.source_path)
                self._watched_paths.add(source.resolve() if source.is_absolute() else (self.project.root / source).resolve())
            validate_model(new_model)
            self.model = new_model
            # Kept for Solve: a study reviews the script's globals, not just the model.
            self.namespace = namespace
            self._source_error = False
            watched = {self.script_path, self.project.study_path, *self._study_paths}
            watched.update(namespace.get("__tuba_project_dependencies__", ()))
            captured = {Path(path): value for path, value in self._study_fingerprints}
            captured.update(namespace.get("__tuba_project_fingerprints__", ()))
            for asset in new_model.cad_assets.values():
                source = Path(asset.source_path)
                source = source.resolve() if source.is_absolute() else (self.project.root / source).resolve()
                watched.add(source)
                digest = str(asset.content_digest or "").removeprefix("sha256:")
                if re.fullmatch("[0-9a-fA-F]{64}", digest):
                    captured[source] = bytes.fromhex(digest)
            observed = tuple((str(path), captured[path] if path in captured else file_fingerprint(path)) for path in sorted(watched))
            self._watched_paths = watched
            self._mesh_source_fingerprints = observed
            event = self._publish_scene()
            # A corrected/reverted source may match existing evidence without new receipts.
            fingerprint = hashlib.sha256(repr(observed).encode()).digest()
            if had_source_error or (self._executed_fingerprint is not None and self._executed_fingerprint != fingerprint):
                self._evidence_signature = None
            self._executed_fingerprint = fingerprint
            with self._fingerprint_lock:
                # A dependency edited during scene publication must trigger a
                # further run; acknowledge only the bytes this run consumed.
                self._last_fingerprint = fingerprint
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # sys.exit() in a script fails the run, not the request
            self.model, self.namespace = previous_model, previous_namespace
            self._source_error = True
            self._watched_paths.update(getattr(exc, "__tuba_project_dependencies__", ()))
            error = f"{type(exc).__name__}: {exc}"
            line = _script_error_line(exc, self.script_path)
            return (
                {"ok": False, "error": error, "line": line, "traceback": traceback.format_exc(), "review_stale": self.review_stale},
                {"type": "script_error", "error": error, "line": line, "review_stale": self.review_stale},
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

        if self._source_error:
            return bool(self._review_identities or (self.out_dir / "review" / "scene.json").is_file())
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

    def _publish_scene(self, *, advance_revision=True) -> dict[str, Any]:
        with self._script_lock, self._ifc_lock:
            return self._publish_scene_locked(advance_revision=advance_revision)

    def _publish_scene_locked(self, *, advance_revision=True) -> dict[str, Any]:
        from tuba.visualization.builders import SceneRequest, build_visualization_scene

        if advance_revision:
            self.revision += 1
        model = self.model
        settings = self._study_settings_or_none()
        scene = build_visualization_scene(SceneRequest(model, include_analysis_mesh=False,
            analysis_meshes=self._current_build_meshes(model),
            volume_export=settings.volume_export if settings else None, clash_results=self._model_clashes(model)))
        comparison = self.mesh_jobs.current_comparison()
        if comparison is not None:
            from tuba.meshing.policy import resolve_mesh_policy
            from tuba.geometry.volume import build_volume_geometry
            from tuba.visualization.scene import SceneLayer
            volume = settings.volume_export if settings else None
            policy = resolve_mesh_policy(model, max_element_size=(volume or {}).get("max_element_size"),
                volume_geometry=build_volume_geometry(model, volume["element_ids"]) if volume else None)
            scene.layers.insert(0, SceneLayer(id="analysis_mesh:identity:convergence", category="analysis_mesh",
                label="Verified Code_Aster mesh comparison", default_visible=False,
                extra={"mesh_identity": {"mesh_review": {"schema": "tuba.mesh-review.v1",
                    "policy": policy.to_dict(), "size_preview": policy.preview(), "comparison": comparison}}}))
        # Build retains the CAD surface; its diagnostic FE skin appears on Mesh.
        for layer in scene.layers:
            if layer.category == "analysis_mesh":
                layer.default_visible = False
        if self._build_mesh_error:
            from tuba.visualization.scene import SceneDiagnostic

            scene.diagnostics.append(SceneDiagnostic(code="analysis_mesh.native_unavailable", severity="error",
                message=f"Solid/shell analysis mesh unavailable: {self._build_mesh_error}"))
        meshes = self._current_mapping_meshes()
        if meshes:
            from tuba.visualization.builders._mappings import build_interface_mapping_scene

            mappings = build_interface_mapping_scene(self.model, analysis_meshes=meshes,
                volume_export=settings.volume_export if settings else None)
            scene.objects = [obj for obj in scene.objects if obj.kind != "interface_mapping"] + list(mappings.objects)
            scene.geometry_assets = [asset for asset in scene.geometry_assets
                if asset.generation_config.get("source") != "tuba.interface_mapping"] + list(mappings.assets)
            scene.diagnostics = [diagnostic for diagnostic in scene.diagnostics
                if not diagnostic.code.startswith("interface_mapping.")] + list(mappings.diagnostics)
        elif self._review_mapping_mesh_error and not self.review_stale:
            from tuba.visualization.scene import SceneDiagnostic

            scene.diagnostics.append(SceneDiagnostic(code="interface_mapping.unavailable_mesh", severity="warning",
                message=f"Build retains authored interface footprints; the verified mesh could not be reused: {self._review_mapping_mesh_error}"))
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

    def _current_build_meshes(self, model):
        """Reuse a verified current diagnostic; never invoke native meshing on save."""
        self._build_analysis_meshes = self.mesh_jobs.current_meshes()
        self._build_mesh_error = (self.mesh_jobs._job or {}).get("error")
        return self._build_analysis_meshes

    def _current_mapping_meshes(self):
        """Reuse verified Review mesh records only while model, study and evidence remain current."""
        if self.model is None or self._source_error or self._study_settings_or_none() is None or not self._review_identities or self.review_stale:
            return ()
        if self._review_mapping_meshes is None:
            from tuba.analysis.staged_run import ARTIFACTS, operation_folder_name
            from tuba.solver.aster_sidecar import load_and_attest_artifact_chain
            from tuba.solver.code_aster_runtime import execution_trust

            meshes = []
            self._review_mapping_mesh_error = None
            try:
                for identity in self._review_identities:
                    root = self.out_dir / "review" / ARTIFACTS / operation_folder_name(identity.load_case)
                    study, mesh, _, attestation = load_and_attest_artifact_chain(self.model, root)
                    if execution_trust(attestation) != "verified":
                        raise ValueError(f"Operation {identity.load_case!r} has no verified mesh attestation.")
                    if mesh is not None:
                        if study.solver_input_identity != identity or mesh.solver_input_identity != identity:
                            raise ValueError(f"Operation {identity.load_case!r} mesh does not belong to this Review.")
                        meshes.append(mesh)
            except (OSError, ValueError) as exc:
                self._review_mapping_mesh_error = str(exc)
                meshes = []
            self._review_mapping_meshes = tuple(meshes)
        return self._review_mapping_meshes

    def _model_clashes(self, model=None) -> list[Any]:
        """Cold-model clashes for the live Build scene: obstacles, self, duplicates."""
        from tuba.clash import ClashEngine

        return ClashEngine().check_all(self.model if model is None else model)

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
        # The expensive review builder owns IFC publication, not source execution.
        # Release that lock before entering the script -> IFC publication order.
        if self.model is not None and not self._source_error:
            self._publish_scene()

    def _produce_review_locked(self, namespace: dict[str, Any], *, artifact_dir: Path | None) -> None:
        from tuba.project.freshness import attested_identities

        # Capture what this import starts with. Evidence that changes during it remains pending.
        self._evidence_signature = self._external_evidence_signature()

        work = self.out_dir / ".review-work"
        shutil.rmtree(work, ignore_errors=True)
        settings = self._study_settings()
        if artifact_dir is not None and settings.operations:
            from tuba.project.study import import_study_evidence
            import_study_evidence(namespace, settings, artifact_dir)
        root = self._review_builder()(namespace, work, artifact_dir=artifact_dir)
        self._rewrite_review_references(Path(root))
        identities = attested_identities(Path(root))
        self._swap_bundle("review", Path(root))
        self._review_identities = identities
        self._review_mapping_meshes = None
        self._review_mapping_mesh_error = None
        self.review_error = None
        shutil.rmtree(work, ignore_errors=True)

    def project_info(self) -> dict[str, Any]:
        from tuba.project.claim import solve_claimed
        from tuba.project.session import project_id

        operations = self._declared_operations()
        return {
            "ok": True,
            "name": self.project.name,
            "project_root": str(self.project.root.resolve()),
            "project_id": project_id(self.project.root),
            "session_id": (self._studio_session or {}).get("session_id"),
            "base_url": self.base_url,
            "viewer_url": f"{self.base_url}?bundle=build&preview_ws={self.ws_url}",
            "launcher_url": getattr(self, "launcher_url", None),
            "has_study": self.study is not None,
            "can_solve": self.study is not None and self.namespace is not None and not self._source_error,
            "solves": bool(operations),
            "load_cases": list(operations),
            "has_review": (self.out_dir / "review" / "scene.json").is_file(),
            "review_stale": self.review_stale,
            "review_error": self.review_error,
            "solving": (self._solving and not self._preparing) or (solve_claimed(self.project.root) and not self.mesh_jobs.busy),
            "preparing_review": self._preparing,
            "mesh": self.mesh_jobs.status(),
            "can_mesh": self.namespace is not None and not self._source_error,
            "source_revision": self.revision,
            "unverified": list(self.unverified),
            "ifc": self.ifc_capability(),
            "geometry": {"available": True, "formats": ["STL", "STEP", "STP"],
                         "max_upload_bytes": 16 * 1024 * 1024, "scale_required": True},
            "package": {"available": True},
        }

    def package_preview(self, include_results=False):
        from tuba.project.package import plan_project_package
        with self._script_lock:
            manifest = plan_project_package(self.project.root, include_results=include_results)
        return {"ok": True, "file_count": len(manifest["files"]),
                "size_bytes": manifest["size_bytes"], "include_results": include_results}

    @contextmanager
    def package_export(self, include_results=False, archive_format="zip"):
        from tuba.project.package import export_project_package
        with tempfile.TemporaryDirectory(prefix="package-", dir=self.out_dir) as temporary:
            path = Path(temporary) / ("project.tgz" if archive_format == "tgz" else "project.tubaproject")
            with self._script_lock:
                export_project_package(self.project.root, path, include_results=include_results)
            yield path

    def geometry_request(self, route, body, name, options):
        """Inspect/store bytes and return explicit Python; authored source is unchanged."""
        from tuba.visualization.preview.geometry import geometry_upload, upload_options
        from tuba.geometry.step_analysis_importer import StepImportError

        try:
            validated = upload_options(name, options)
        except (ValueError, TypeError, UnicodeError) as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            with self._geometry_lock:
                key = (hashlib.sha256(body).hexdigest(), json.dumps(validated, sort_keys=True))
                cached = self._geometry_preview[1] if self._geometry_preview and self._geometry_preview[0] == key else None
                result = geometry_upload(self.project.root, self.out_dir, route, body, validated, cached=cached)
                self._geometry_preview = key, {key: value for key, value in result.items() if key not in {"path", "python"}}
                return 200, result
        except ImportError as exc:
            return 503, {"ok": False, "error": str(exc)}
        except StepImportError as exc:
            return (503 if "gmsh is required" in str(exc) else 422), {"ok": False, "error": str(exc)}
        except ValueError as exc:
            return 422, {"ok": False, "error": str(exc)}
        except OSError as exc:
            return 500, {"ok": False, "error": str(exc)}
        except Exception as exc:
            return 500, {"ok": False, "error": f"Geometry inspection failed: {exc}"}

    def profile_library(self) -> dict[str, Any]:
        from tuba.visualization.profile_catalog import model_sections, profile_catalog

        return {**profile_catalog(), "used": model_sections(self.model)}

    @property
    def _ifc_root(self) -> Path:
        return self.project.root / "references" / "ifc"

    def _ifc_manifests(self):
        from tuba.geometry._native_worker import MAX_OUTPUT_BYTES
        retained = 0
        vertices = faces = products = 0
        for path in sorted(self._ifc_root.glob("*/manifest.json")):
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError("IFC references must not contain links.")
            retained += 1
            if retained > 8 or path.stat().st_size > MAX_OUTPUT_BYTES:
                raise ValueError("IFC retained references exceed 8 manifests or 64 MiB per manifest.")
            if re.fullmatch(r"[0-9a-f]{64}", path.parent.name) and (path.parent / "source.ifc").is_file():
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    if manifest["preview"]["sha256"] == path.parent.name:
                        products += len(manifest["preview"]["products"])
                        vertices += sum(len(mesh["vertices"]) for mesh in manifest["meshes"].values())
                        faces += sum(len(mesh["faces"]) for mesh in manifest["meshes"].values())
                        if products > 10000 or vertices > 500000 or faces > 500000:
                            raise RuntimeError("IFC retained product/vertex/face budget exceeded.")
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

        merged = False
        for identity, manifest in self._ifc_manifests():
            merge_reference(scene, identity, manifest)
            merged = True
        if merged:
            from tuba.visualization.web_export import _manifest_generation_config, _relative_geometry_uri
            if len(scene.objects) > 10000 or len(scene.geometry_assets) > 10000:
                raise ValueError("IFC merged scene object/asset budget exceeds 10000.")
            payload = scene.to_dict()
            for asset in payload["geometry_assets"]:
                asset["uri"] = _relative_geometry_uri(asset["id"]) if asset["format"] == "tuyau_subpoint_glyphs" else ""
                asset["generation_config"] = _manifest_generation_config(asset)
                asset["hash"] = "sha256:" + "0" * 64
            size = 0
            for chunk in json.JSONEncoder(indent=2, sort_keys=True, allow_nan=False).iterencode(payload):
                # write_scene_bundle writes text; Windows expands LF to CRLF.
                size += len(chunk.encode("utf-8")) + (chunk.count("\n") if os.name == "nt" else 0)
                if size > MAX_REFERENCE_SCENE_BYTES:
                    raise ValueError("IFC merged scene JSON exceeds the 64 MiB receiving limit before publication.")

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
        with self._script_lock, self._ifc_lock:
            return self._ifc_request_locked(route, body, name)

    def _ifc_request_locked(self, route: str, body: bytes | None, name: str):
        from tuba.external.ifc_reference import conversion_zip, extract, require_ifc, validate_assignment

        try:
            require_ifc()
            if route == "preview":
                preview, meshes = extract(body or b"", name)
                self._ifc_preview = preview["sha256"], preview, meshes
                return 200, {"ok": True, "preview": preview}
            if route == "attach":
                from tuba.geometry._native_worker import check_source, write_bounded_json
                check_source(body or b"")
                identity = hashlib.sha256(body).hexdigest()
                target = self._ifc_root / identity
                manifests = list(self._ifc_manifests())
                if target.is_symlink():
                    raise ValueError("IFC references must not contain links.")
                if target.is_dir():
                    return 200, {"ok": True, "reference": self._ifc_summary(identity, json.loads((target / "manifest.json").read_text(encoding="utf-8"))),
                                 "build_url": f"{self.base_url}build/", "review_url": f"{self.base_url}review/"}
                if len(manifests) >= 8:
                    raise ValueError("IFC retained reference budget exceeds 8 references.")
                if self._ifc_preview and self._ifc_preview[0] == identity:
                    _, preview, meshes = self._ifc_preview
                else:
                    preview, meshes = extract(body or b"", name)
                all_manifests = [manifest for _, manifest in manifests] + [{"preview": preview, "meshes": meshes}]
                if (len(all_manifests) > 8
                        or sum(len(manifest["preview"]["products"]) for manifest in all_manifests) > 10000
                        or sum(len(mesh["vertices"]) for manifest in all_manifests for mesh in manifest["meshes"].values()) > 500000
                        or sum(len(mesh["faces"]) for manifest in all_manifests for mesh in manifest["meshes"].values()) > 500000):
                    raise ValueError("IFC retained reference/product/vertex/face budget exceeded.")
                self._ifc_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=self._ifc_root) as temp:
                    folder = Path(temp)
                    (folder / "source.ifc").write_bytes(body)
                    manifest = {"preview": preview, "meshes": meshes}
                    write_bounded_json(folder / "manifest.json", manifest)
                    retained = sum(path.stat().st_size for path in self._ifc_root.glob("*/*") if path.is_file())
                    if retained > 512 * 1024 * 1024:
                        raise ValueError("IFC project reference storage exceeds 512 MiB.")
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
        with self._script_lock:
            if self.watch_fingerprint() != self._last_fingerprint:
                self.run_once()
            if self._source_error:
                return 422, {"ok": False, "error": "Project source has errors; reload it successfully before compiling a study."}
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
        with self._script_lock:
            return self._start_solve_locked(force)

    def _start_solve_locked(self, force: bool) -> tuple[int, dict[str, Any]]:
        from tuba.project.claim import solve_claimed

        if self.watch_fingerprint() != self._last_fingerprint:
            self.run_once()
        if self._source_error:
            return 400, {"ok": False, "error": "Project source has errors; reload it successfully before solving."}
        if self.study is None:
            return 400, {"ok": False, "error": f"{self.project.name} has no study.py to solve."}
        if self.namespace is None:
            return 400, {"ok": False, "error": "model.py has not run successfully yet."}
        with self._solve_lock:
            if self.mesh_jobs.busy:
                return 409, {"ok": False, "error": "A mesh job is running; wait or cancel it before solving."}
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


