"""One explicit native worker slot; only verified, fresh mesh diagnostics publish.

All lifecycle operations acquire the host's script lock before its solve lock.
The monitor never calls scene publication while holding the solve lock.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4


def atomic_json(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(record, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def digest(path):
    with Path(path).open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def launch_mesh_worker(project_root, directory):
    """Launch the shared native worker in this process's filesystem environment."""
    environment = os.environ.copy()
    package_root = str(Path(__file__).resolve().parents[3])
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (package_root, environment.get("PYTHONPATH"))))
    with (Path(directory) / "worker.log").open("wb") as log:
        return subprocess.Popen([sys.executable, "-m", "tuba.visualization.preview.mesh_worker",
                                 str(project_root), str(directory)],
                                cwd=os.getcwd(), env=environment,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def mesh_inputs(model, volume_export=None):
    """Pure geometry/policy identity, shared by the host and child."""
    from tuba.meshing.policy import resolve_mesh_policy
    from tuba.geometry.volume import build_volume_geometry

    geometry = build_volume_geometry(model, volume_export["element_ids"]) if volume_export else None
    policy = resolve_mesh_policy(model, max_element_size=(volume_export or {}).get("max_element_size"),
                                 volume_geometry=geometry)
    payload = {"mesher": "native-gmsh-fields-v1", "model": model.to_dict(),
               "volume_export": volume_export, "policy": policy.to_dict()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_native_line_mail(path):
    """Read actual ASTER line topology, including implicit quadratic midsides."""
    text = Path(path).read_text(encoding="utf-8")
    if "COOR_3D" not in text or "FINSF" not in text or not text.rstrip().endswith("FIN"):
        raise ValueError("Native ASTER mesh is incomplete; regenerate.")
    nodes, elements, block = {}, {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if line in {"COOR_3D", "SEG2", "SEG3"}:
            block = line
        elif line == "FINSF":
            block = None
        elif line and block:
            label, *values = line.split()
            if block == "COOR_3D":
                if len(values) != 3 or label in nodes:
                    raise ValueError("Invalid ASTER node record; regenerate.")
                nodes[label] = tuple(float(value) for value in values)
            else:
                if len(values) != int(block[-1]) or label in elements:
                    raise ValueError("Invalid ASTER connectivity record; regenerate.")
                elements[label] = tuple(values)
    return nodes, elements


def validate_artifact(directory, identity, *, cache=None):
    """Verify every receipt and artifact; optionally reuse identical hydrated data."""
    import meshio
    import numpy as np
    from tuba.analysis.mesh import AnalysisMesh

    directory = Path(directory)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest.get("schema") != "tuba.mesh-job.v1" or manifest.get("identity") != identity
            or manifest.get("result_status") != "mesh_only"):
        raise ValueError("Mesh cache manifest does not match the current mesh identity.")
    artifact = manifest.get("artifact")
    if artifact not in {"mesh.med", "mesh.mail"}:
        raise ValueError("Unsupported mesh artifact in cache manifest.")
    hashes = {filename: digest(directory / filename) for filename in (artifact, "analysis_mesh.json")}
    for filename, observed in hashes.items():
        if observed != manifest["sha256"][filename]:
            raise ValueError(f"Mesh cache {filename} bytes do not match their manifest; regenerate.")
    key = (str(directory.resolve()), identity, manifest_bytes, tuple(hashes.items()))
    if cache is not None and cache.get("key") == key:
        return cache["mesh"]
    mesh = AnalysisMesh.from_dict(json.loads((directory / "analysis_mesh.json").read_text(encoding="utf-8")))
    review = mesh.mesh_review or {}
    if mesh.solver_input_identity is not None or review.get("schema") != "tuba.mesh-review.v1":
        raise ValueError("Diagnostic mesh has missing review metadata or claims solved provenance.")
    if not mesh.nodes or not mesh.elements or review.get("quality", {}).get("invalid_count") != 0:
        raise ValueError("Empty or invalid mesh cannot be published; inspect its quality report.")
    if not np.isfinite(list(mesh.nodes.values())).all():
        raise ValueError("Mesh coordinates must be finite.")
    if artifact == "mesh.med":
        try:
            med = meshio.read(directory / artifact)
        except SystemExit as exc:
            # meshio's public reader exits on unsupported MED layouts. Convert
            # that parser failure into a retired receipt, not a dead HTTP thread.
            raise ValueError("MED mesh could not be read; regenerate.") from exc
        if not len(med.points) or not med.cells or not np.isfinite(med.points).all():
            raise ValueError("MED mesh is empty or invalid; regenerate.")
        for cells in med.cells:
            if not np.issubdtype(cells.data.dtype, np.integer):
                raise ValueError("MED connectivity must contain integer node indices.")
            if cells.data.size and (cells.data.min() < 0 or cells.data.max() >= len(med.points)):
                raise ValueError("MED connectivity references missing nodes.")
        _validate_med_record(directory / artifact, med, mesh)
    else:
        nodes, elements = read_native_line_mail(directory / artifact)
        if set(nodes) != set(mesh.nodes) or set(elements) != set(mesh.elements):
            raise ValueError("ASTER nodes/cells do not match the analysis mesh record.")
        for label, coordinates in nodes.items():
            if not np.isfinite(coordinates).all() or not np.allclose(coordinates, mesh.nodes[label], rtol=1e-10, atol=1e-12):
                raise ValueError("ASTER coordinates do not match the analysis mesh record.")
        for label, connectivity in elements.items():
            # Historical policy-free line records store endpoints while MAIL also
            # carries the quadratic midpoint. Preserve that existing record contract.
            expected = mesh.elements[label]
            if any(node not in nodes for node in connectivity) or connectivity[:len(expected)] != expected:
                raise ValueError("ASTER connectivity does not match the analysis mesh record.")
    if ((directory / "manifest.json").read_bytes() != manifest_bytes
            or any(digest(directory / filename) != expected for filename, expected in hashes.items())):
        raise ValueError("Mesh artifact bytes changed during verified import; regenerate.")
    if cache is not None:
        cache.clear()
        cache.update(key=key, mesh=mesh)
    return mesh


def _validate_med_record(path, native, record):
    """Match native labels, families and ordered connectivity, including midsides.

    Gmsh volume exports retain sparse tags; mixed STEP exports normalize them.
    MED NUM/NOM is the identity map in both contracts. Insertion order or equal
    coordinates cannot identify coincident nodes or attest connectivity.
    """
    import h5py
    import numpy as np

    med_types = {"hexahedron20": "H20", "tetra10": "T10", "quad8": "QU8",
                 "triangle6": "TR6", "triangle": "TR3", "line3": "SE3", "line": "SE2", "vertex": "PO1"}
    families = {("volume_cell", 20): "hexahedron20", ("volume_cell", 10): "tetra10",
                ("volume_skin", 8): "quad8", ("volume_skin", 6): "triangle6",
                ("volume_skin", 3): "triangle", ("shell_cell", 3): "triangle",
                ("native_element", 3): "line3", ("native_element", 2): "line",
                ("reference_carrier", 1): "vertex"}
    # Native MED ordering relative to Gmsh's retained analysis record. These
    # preserve corner/midside roles; an unordered node-set comparison would not.
    permutations = {"hexahedron20": (0, 3, 2, 1, 4, 7, 6, 5, 9, 13, 11, 8, 17, 19, 18, 16, 10, 15, 14, 12),
                    "tetra10": (0, 2, 1, 3, 6, 5, 4, 7, 8, 9)}

    def tags(group, count):
        numbers = None
        if "NUM" in group:
            raw = group["NUM"][:]
            if raw.shape != (count,) or not np.issubdtype(raw.dtype, np.integer):
                raise ValueError("MED numeric identities have invalid lengths or types.")
            numbers = [int(value) for value in raw]
        if "NOM" in group:
            names = [row.tobytes().decode("ascii").strip(" \x00") for row in group["NOM"][:]]
            if len(names) != count or any(not name.isdigit() for name in names):
                raise ValueError("MED labels must be explicit numeric identities.")
            named = [int(name) for name in names]
            if numbers is not None and named != numbers:
                raise ValueError("MED NUM and NOM identities disagree.")
            numbers = named
        if numbers is None or len(set(numbers)) != count or any(tag <= 0 for tag in numbers):
            raise ValueError("MED identities are missing or duplicated; regenerate the diagnostic mesh.")
        return numbers

    expected = {}
    for label, nodes in record.elements.items():
        source = record.element_sources.get(label)
        family = families.get((source.role if source else None, len(nodes)))
        if family is None or not label[2:].isdigit():
            raise ValueError("Analysis mesh has unsupported MED family or element identity.")
        tag = int(label[2:])
        if source.metadata.get("solver_element_tag", tag) != tag or (family, tag) in expected:
            raise ValueError("Analysis mesh MED element identities are inconsistent or duplicated.")
        expected[family, tag] = nodes

    with h5py.File(path, "r") as file:
        root = file["ENS_MAA"]
        if len(root) != 1:
            raise ValueError("MED readback requires exactly one named mesh.")
        geometry = next(iter(root.values()))
        if "NOE" not in geometry:
            frames = [group for group in geometry.values() if isinstance(group, h5py.Group) and "NOE" in group]
            if len(frames) != 1:
                raise ValueError("MED readback requires exactly one geometry frame.")
            geometry = frames[0]
        node_ids = [f"VN{tag}" for tag in tags(geometry["NOE"], len(native.points))]
        if set(node_ids) != set(record.nodes):
            raise ValueError("MED nodes do not match the analysis mesh record.")
        if not np.allclose(native.points, [record.nodes[label] for label in node_ids], rtol=1e-10, atol=1e-12):
            raise ValueError("MED coordinates do not match the analysis mesh record.")
        seen = set()
        for cells in native.cells:
            med_type = med_types.get(cells.type)
            if med_type is None:
                raise ValueError("MED has an unsupported cell family.")
            cell_tags = tags(geometry["MAI"][med_type], len(cells.data))
            for tag, indices in zip(cell_tags, cells.data):
                key = cells.type, tag
                if key not in expected or key in seen:
                    raise ValueError("MED cell identities/families do not match the analysis mesh record.")
                seen.add(key)
                nodes = expected[key]
                order = permutations.get(cells.type, range(len(nodes)))
                if tuple(node_ids[int(index)] for index in indices) != tuple(nodes[index] for index in order):
                    raise ValueError("MED connectivity does not match the analysis mesh record.")
        if seen != set(expected):
            raise ValueError("MED cell inventory does not match the analysis mesh record.")


class MeshJobManager:
    def __init__(self, studio):
        self.studio = studio
        self.root = studio.out_dir / ".mesh-jobs"
        self._job = None
        self._process = None
        self._artifact = None
        self._restored = False
        self._claim = None
        self._claim_token = None
        self._cleanup_obligation = None
        self._comparison_cache = None
        self._mesh_cache = {}
        self._artifacts = {}
        self._history_restored = set()
        self._scene_retirement_pending = False
        self._restore_cleanup_obligation()

    def _restore_cleanup_obligation(self):
        from tuba.project.claim import cleanup_claim
        if not hasattr(self.studio, "project"):
            return  # analysis-only cache readers have no project execution slot
        claim = cleanup_claim(self.studio.project.root)
        if not claim:
            return
        obligation = claim["cleanup_obligation"]
        job_id = obligation.get("job_id")
        directory = Path(obligation.get("directory", "")).resolve()
        if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
            return  # claim still excludes work; an invalid identity must never be signalled
        if directory.name != job_id:
            return
        self._claim_token, self._cleanup_obligation = claim["token"], obligation
        try:
            job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            job = {"id": job_id, "mode": "convergence", "directory": str(directory), "identity": "",
                   "source_revision": self.studio.revision, "elapsed_seconds": 0.0}
        self._job = {**job, "id": job_id, "directory": str(directory), "state": "cancelled", "stage": "cleanup_pending",
                     "cleanup_pending": True, "error": "Owned Code_Aster cleanup must be verified; retry cleanup for this job."}
        self._restored = True

    @property
    def busy(self):
        # Host calls this under _solve_lock. Cancellation retains the slot until exit.
        return self._process is not None or self._cleanup_obligation is not None

    def _identity(self):
        host = self.studio
        if host._source_error or host.model is None or host.namespace is None:
            raise ValueError("model.py must run successfully before mesh generation.")
        sources = getattr(host, "_mesh_source_fingerprints", ())
        if not sources or host._dependency_fingerprints([Path(path) for path, _ in sources]) != sources:
            raise ValueError("Python or CAD source changed; run the current source before generating.")
        settings = host._study_settings() if host.study is not None else None
        volume = settings.volume_export if settings else None
        inputs = mesh_inputs(host.model, volume)
        records = [[path, value.hex() if value is not None else None] for path, value in sources]
        identity = hashlib.sha256(json.dumps([inputs, records], sort_keys=True).encode()).hexdigest()
        return identity, inputs, records

    def _clear_current(self, *, record_io_error=False):
        self._artifact = None
        mode = (self._job or {}).get("mode", "mesh")
        self._artifacts.pop(mode, None)
        if mode == "convergence":
            self._comparison_cache = None
        else:
            self._mesh_cache.clear()
        try:
            atomic_json(self.root / f"current-{mode}.json", {"job_id": None})
            atomic_json(self.root / "current.json", {"job_id": None})
        except OSError as exc:
            if not record_io_error:
                raise
            message = f"Current mesh pointer could not be cleared: {exc}"
            self._job["pointer_error"] = message
            existing = self._job.get("error", "")
            if message not in existing:
                self._job["error"] = f"{existing}; {message}" if existing else message

    def _refresh(self):
        try:
            identity, _, _ = self._identity()
        except (OSError, ValueError, TypeError) as exc:
            if self._job and self._job["state"] == "succeeded":
                self._job.update(state="stale", stage="stale", error=str(exc))
                self._retain_report()
            self._scene_retirement_pending |= self._artifact is not None
            self._artifact = None
            self._mesh_cache.clear()
            return
        if not self._restored:
            self._restored = True
            try:
                job_id = json.loads((self.root / "current.json").read_text(encoding="utf-8"))["job_id"]
                if isinstance(job_id, str) and len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id):
                    saved = json.loads((self.root / job_id / "request.json").read_text(encoding="utf-8"))
                    self._job = {"id": job_id, "mode": saved.get("mode", "mesh"), "state": "succeeded", "stage": "complete",
                                 "directory": str(self.root / job_id), "identity": saved["identity"],
                                 "source_revision": self.studio.revision, "elapsed_seconds": 0.0}
                    self._artifact = self._job
                    self._artifacts[self._job["mode"]] = self._job
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if self._job and self._job["state"] == "succeeded":
            if self._job["identity"] != identity:
                self._job.update(state="stale", stage="stale", error="Mesh settings, Python or CAD identity changed; regenerate.")
                self._scene_retirement_pending |= self._artifact is not None
                self._clear_current()
                self._retain_report()
        if self._artifact:
            try:
                # Reverify bytes even in the same host: files may have changed externally.
                return self._validate_current(self._artifact, identity)
            except Exception as exc:
                self._job.update(state="failed", stage="failed", error=f"Mesh cache validation failed: {exc}")
                self._scene_retirement_pending = True
                self._clear_current()
                self._retain_report()

    def current_meshes(self):
        with self.studio._script_lock:
            self._refresh()
            mesh = self._artifact_for_mode("mesh")
            return (mesh,) if mesh is not None and not isinstance(mesh, dict) else ()

    def _artifact_for_mode(self, mode):
        """Independent current receipts share a process slot, not artifact lifetime."""
        try:
            identity, _, _ = self._identity()
        except (OSError, ValueError, TypeError):
            return None
        # A cancelled/failed replacement cannot restore its mode's retired receipt.
        if self._job and self._job.get("mode") == mode and self._job["state"] != "succeeded":
            return None
        if mode not in self._history_restored:
            self._history_restored.add(mode)
            if mode not in self._artifacts:
                try:
                    job_id = json.loads((self.root / f"current-{mode}.json").read_text(encoding="utf-8"))["job_id"]
                    if isinstance(job_id, str) and len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id):
                        job = json.loads((self.root / job_id / "job.json").read_text(encoding="utf-8"))
                        if job.get("mode") == mode and job.get("state") == "succeeded":
                            job["directory"] = str(self.root / job_id)
                            self._artifacts[mode] = job
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        artifact = self._artifacts.get(mode)
        if artifact is None:
            return None
        try:
            if artifact["identity"] != identity:
                raise ValueError("Source or mesh policy changed; rerun this mesh operation.")
            return self._validate_current(artifact, identity)
        except Exception as exc:
            artifact.update(state="failed", stage="failed", error=str(exc))
            self._artifacts.pop(mode, None)
            if mode == "convergence":
                self._comparison_cache = None
            else:
                self._mesh_cache.clear()
            self._scene_retirement_pending = True
            atomic_json(self.root / f"current-{mode}.json", {"job_id": None})
            atomic_json(Path(artifact["directory"]) / "job.json", artifact)
            return None

    def _validate_current(self, job, identity):
        if job.get("mode") != "convergence":
            return validate_artifact(job["directory"], identity, cache=self._mesh_cache)
        from tuba.analysis.mesh_convergence import reopen_mesh_convergence
        cache = self._comparison_cache
        if cache and cache["identity"] == identity and cache["directory"] == job["directory"]:
            if all(digest(path) == expected for path,expected in cache["files"].items()):
                return deepcopy(cache["report"])
        root = Path(job["directory"])
        saved = json.loads((root / "comparison.json").read_text(encoding="utf-8"))
        files = [root / "comparison.json", root / "source_model.json"]
        for index,level in enumerate(saved["levels"]):
            names = ("model.json", "study_execution.json", *level["attestation"]["artifacts"])
            if any(Path(name).name != name for name in names):
                raise ValueError("Convergence artifact names must be local filenames.")
            files.extend(root / f"level-{index:02d}" / name for name in names)
        before = {str(path):digest(path) for path in files}
        report = reopen_mesh_convergence(self.studio.model, job["directory"])
        verified_files = {root / "comparison.json", root / "source_model.json"}
        for index,level in enumerate(report["levels"]):
            verified_files.update(root / f"level-{index:02d}" / name for name in
                ("model.json", "study_execution.json", *level["attestation"]["artifacts"]))
        if verified_files != set(files):
            raise ValueError("Comparison cache inventory does not match independently verified solve artifacts.")
        if any(digest(path) != expected for path,expected in before.items()):
            raise ValueError("Convergence artifact bytes changed during verified import; rerun or reopen after the writer finishes.")
        self._comparison_cache = {"identity": identity, "directory": job["directory"], "report": deepcopy(report),
                                  "files": before}
        return report

    def current_comparison(self):
        with self.studio._script_lock:
            self._refresh()
            value = self._artifact_for_mode("convergence")
            return value if isinstance(value, dict) else None

    def status(self):
        with self.studio._script_lock:
            current = self._refresh()
            job = dict(self._job or {"id": None, "mode": "mesh", "state": "idle", "stage": "idle"})
            if job["state"] == "running":
                job["elapsed_seconds"] = time.monotonic() - job["started_at"]
                try:
                    progress = json.loads((Path(job["directory"]) / "status.json").read_text(encoding="utf-8"))
                    if progress.get("stage") in {"preparing", "generating", "validating", "solving", "comparing"}:
                        job["stage"] = progress["stage"]
                    if job.get("mode") == "convergence":
                        job["levels"] = progress.get("levels", [])
                except (OSError, ValueError):
                    pass
            job.pop("started_at", None)
            settings = self.studio._study_settings_or_none()
            comparison = current if job.get("mode") == "convergence" and self._artifact else self._artifact_for_mode("convergence")
            job["comparison"] = comparison
            job["comparison_current"] = comparison is not None
            job["mesh_current"] = self._artifact_for_mode("mesh") is not None
            job.update(ok=True, current=self._artifact is not None, busy=self.busy, unsolved=job.get("mode") != "convergence" or not self._artifact,
                       cleanup_pending=bool(self._cleanup_obligation and job.get("state") != "running"),
                       convergence_config=settings.mesh_convergence if settings else None,
                       loaded_source_revision=self.studio.revision, source_error=self.studio._source_error,
                       source_revision=self.studio.revision if job["id"] is None else job["source_revision"])
            from tuba.solver.code_aster_process import convergence_capability
            job["convergence_capability"] = convergence_capability()
            if self._scene_retirement_pending and not self.studio._source_error:
                # Validate both retained modes before withdrawing served metadata.
                # Clear first: publication itself reads the already retired receipts.
                self._scene_retirement_pending = False
                try:
                    self.studio._publish_scene(advance_revision=False)
                except BaseException:
                    self._scene_retirement_pending = True
                    raise
            return job

    def start(self, *, force=False, expected_source_revision=None, mode="mesh"):
        from tuba.project.claim import claim_solve, solve_claimed, SolveBusy
        host = self.studio
        with host._script_lock:
            with host._solve_lock:
                if self.busy or host._solving or solve_claimed(host.project.root):
                    return 409, {"ok": False, "error": "A mesh worker, solve or review import already owns this project."}
                if expected_source_revision is not None and expected_source_revision != host.revision:
                    return 409, {"ok": False, "error": "Source revision changed; refresh before generating."}
                try:
                    identity, inputs, sources = self._identity()
                    if mode not in {"mesh", "convergence"}:
                        raise ValueError("Unsupported mesh job mode.")
                    settings = host._study_settings_or_none()
                    if mode == "convergence" and (settings is None or settings.mesh_convergence is None):
                        raise ValueError("Define MESH_CONVERGENCE and exactly one LOAD_CASES operation in study.py before running convergence.")
                    if mode == "convergence":
                        from tuba.solver.code_aster_process import convergence_capability
                        capability = convergence_capability()
                        if not capability["supported"]:
                            raise ValueError(capability["reason"])
                except (ValueError, OSError, TypeError) as exc:
                    return 422, {"ok": False, "error": str(exc)}
                if not force and self._refresh() is not None and self._job.get("mode") == mode:
                    return 200, self.status()
                job_id = uuid4().hex
                directory = self.root / job_id
                obligation = {"job_id": job_id, "directory": str(directory.resolve())} if mode == "convergence" else None
                claim = claim_solve(host.project.root, cleanup_obligation=obligation)
                try:
                    self._claim_token = claim.__enter__()
                except SolveBusy as exc:
                    return 409, {"ok": False, "error": str(exc)}
                self._claim = claim
                self._cleanup_obligation = obligation
                request = {"identity": identity, "inputs": inputs, "source_fingerprints": sources, "mode": mode}
                self._artifact = None
                self._job = {"id": job_id, "mode": mode, "state": "running", "stage": "preparing",
                             "identity": identity, "directory": str(directory), "source_revision": host.revision,
                             "started_at": time.monotonic(), "elapsed_seconds": 0.0}
                try:
                    atomic_json(directory / "request.json", request)
                    self._clear_current()
                    self._restored = True
                    self._process = self._launch(directory)
                except Exception as exc:
                    self._job.update(state="failed", stage="failed", error=f"Mesh worker could not start: {exc}")
                    self._process = None
                    self._job["worker_exited"] = True  # Popen did not return a worker handle
                    if mode == "convergence":
                        self._cleanup_runtime(self._job, cancel=True)
                    self._release_claim()
                    self._retain_report()
                    return 500, self.status()
                threading.Thread(target=self._monitor, args=(job_id, self._process), daemon=True,
                                 name="tuba-studio-mesh").start()
            # Remove an old mesh skin immediately, even if remeshing later fails.
            host._publish_scene(advance_revision=False)
            self._notify()
            return 202, self.status()

    def _launch(self, directory):
        # The worker re-runs model.py and must rebuild the host's model, so it
        # runs in the host's cwd: the project folder broke cwd-relative CAD paths
        # the host had resolved. Use the running checkout rather than
        # accidentally importing a different installed Tuba version.
        return launch_mesh_worker(self.studio.project.root, directory)

    def _monitor(self, job_id, process):
        process.wait()
        self._complete(job_id, process)

    def _complete(self, job_id, process):
        host = self.studio
        with host._script_lock:
            with host._solve_lock:
                if not self._job or self._job["id"] != job_id or self._process is not process:
                    return
                self._process = None
                job = self._job
                job["worker_exited"] = True
                job["elapsed_seconds"] = time.monotonic() - job["started_at"]
                if job.get("mode") == "convergence" and job["state"] == "cancelled":
                    self._cleanup_runtime(job, cancel=True)
                if job["state"] != "cancelled":
                    try:
                        if job.get("mode") == "convergence":
                            self._cleanup_runtime(job, cancel=process.returncode != 0)
                        try:
                            identity, _, _ = self._identity()
                        except (ValueError, OSError, TypeError):
                            identity = None
                        if identity != job["identity"] or host.revision != job["source_revision"]:
                            job.update(state="stale", error="Source or mesh policy changed while generating; regenerate.")
                        elif process.returncode != 0:
                            status = json.loads((Path(job["directory"]) / "status.json").read_text(encoding="utf-8"))
                            raise ValueError(status.get("error", f"Mesh worker exited {process.returncode}; inspect worker.log."))
                        else:
                            self._validate_current(job, identity)
                            job.update(state="succeeded", stage="complete")
                            self._artifact = job
                            self._artifacts[job["mode"]] = job
                            atomic_json(self.root / f"current-{job['mode']}.json", {"job_id": job_id})
                            atomic_json(self.root / "current.json", {"job_id": job_id})
                    except Exception as exc:
                        job.update(state="failed", error=str(exc))
                try:
                    if job["state"] != "succeeded":
                        self._clear_current(record_io_error=True)
                        job["stage"] = "cleanup_pending" if job.get("cleanup_pending") else job["state"]
                finally:
                    try:
                        self._retain_report()
                    finally:
                        self._release_claim()
            try:
                if not host._source_error:
                    host._publish_scene(advance_revision=False)
            except Exception as exc:
                job["publication_error"] = str(exc)
                if job["state"] == "succeeded":
                    job.update(state="failed", stage="failed", error=f"Mesh scene publication failed: {exc}")
                    self._clear_current(record_io_error=True)
            finally:
                job["elapsed_seconds"] = time.monotonic() - job["started_at"]
                self._retain_report()
                self._notify()

    def _cancel_process(self, process, job):
        """Extension seam: additional modes must clean up owned children before termination."""
        try:
            if job.get("mode") == "convergence":
                self._cleanup_runtime(job, cancel=True)
        finally:
            if process.poll() is None:
                process.terminate()

    def _cleanup_runtime(self, job, *, cancel):
        from tuba.solver.code_aster_process import ExecutionController
        try:
            controller = ExecutionController(job["directory"], cleanup_only=True)
            if cancel:
                controller.cancel()
            else:
                controller.cleanup()
            job.pop("cleanup_error", None)
            job["cleanup_pending"] = False
        except Exception as exc:
            message = f"Owned Code_Aster cleanup failed: {exc}"
            job.update(cleanup_error=message, error=message, cleanup_pending=True, stage="cleanup_pending")
            if not cancel:
                raise

    def _release_claim(self):
        if self._cleanup_obligation is not None and not self._job.get("cleanup_pending", False):
            from tuba.project.claim import release_cleanup_claim
            release_cleanup_claim(self.studio.project.root, token=self._claim_token, obligation=self._cleanup_obligation)
            self._cleanup_obligation = None
        if self._claim is not None:
            self._claim.__exit__(None, None, None)
            self._claim = None

    def _worker_exited(self):
        if self._process is not None:
            return self._process.poll() is not None
        if self._job.get("worker_exited"):
            return True
        from tuba.solver.code_aster_process import worker_process_identity
        directory = Path(self._job["directory"])
        receipt = json.loads((directory / "worker.json").read_text(encoding="utf-8"))
        if (receipt.get("schema") != "tuba.mesh-worker.v1" or receipt.get("job_id") != self._job["id"]
                or receipt.get("project_root") != str(self.studio.project.root.resolve())
                or not isinstance(receipt.get("pid"), int) or receipt["pid"] <= 1 or not receipt.get("starttime")):
            raise ValueError("Worker ownership identity is invalid; cleanup claim release refused.")
        observed = worker_process_identity(receipt["pid"])
        return observed is None or observed != {key: receipt[key] for key in ("pid", "starttime")}

    def _retain_report(self):
        """Host-owned outcome survives cancellation even if the child writes later."""
        if not self._job:
            return
        record = {key: value for key, value in self._job.items() if key != "started_at"}
        if "started_at" in self._job and not self._job.get("worker_exited"):
            record["elapsed_seconds"] = time.monotonic() - self._job["started_at"]
        record.update(schema="tuba.mesh-job-status.v1", unsolved=record.get("mode") != "convergence" or record.get("state") != "succeeded")
        try:
            atomic_json(Path(record["directory"]) / "job.json", record)
        except OSError as exc:
            # Preserve the truthful in-memory outcome if the output drive failed.
            self._job["report_error"] = f"Mesh job report could not be retained: {exc}"

    def cancel(self, job_id):
        host = self.studio
        with host._script_lock:
            with host._solve_lock:
                if not self._job or self._job["id"] != job_id:
                    return 404, {"ok": False, "error": "No such mesh job."}
                if self._job["state"] != "running":
                    if self._cleanup_obligation is not None:
                        self._cleanup_runtime(self._job, cancel=True)
                        if self._process is None and not self._job.get("cleanup_pending"):
                            try:
                                if not self._worker_exited():
                                    raise RuntimeError("Owned mesh worker still runs; retry cleanup after it exits.")
                                self._release_claim()
                                self._job.update(stage="cancelled", error="Job cancelled; owned runtime cleanup verified.")
                            except Exception as exc:
                                self._job.update(cleanup_pending=True, stage="cleanup_pending", cleanup_error=str(exc), error=str(exc))
                        self._retain_report()
                        return 200, self.status()
                    if self._job["state"] == "cancelled":
                        return 200, self.status()
                    return 409, {"ok": False, "error": "This mesh job is no longer running."}
                self._job.update(state="cancelled", stage="cancelled")
                try:
                    self._clear_current(record_io_error=True)
                finally:
                    try:
                        if self._process:
                            self._cancel_process(self._process, self._job)
                    finally:
                        self._retain_report()
            self._notify()
            return 200, self.status()

    def close(self):
        if self._job and self.busy:
            self.cancel(self._job["id"])

    def _notify(self):
        self.studio.broker.broadcast({"type": "mesh_status", **self.status()})
