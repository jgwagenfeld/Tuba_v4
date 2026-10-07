"""Disposable native CAD/IFC workers; no parser runs in the Studio process."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from uuid import uuid4

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_ENTITIES = 100_000
MAX_PRODUCTS = 5_000
MAX_CAD_ENTITIES = 10_000
MAX_VERTICES = 200_000
MAX_FACES = 200_000
MAX_PROPERTY_VALUES = 100_000
MAX_PROPERTY_DEPTH = 12
MEMORY_BYTES = 1024 * 1024 * 1024
CPU_SECONDS = 60
WALL_SECONDS = 90
# ponytail: two native workers per process; use a host queue if multiple Studios compete.
_slots = threading.BoundedSemaphore(2)


class NativeImportError(ValueError):
    """Native input exceeded a budget or its disposable worker failed."""


def check_source(data: bytes) -> None:
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise NativeImportError("CAD/IFC source must be nonempty and at most 16 MiB.")
    if sum(1 for _ in re.finditer(rb"#\d+\s*=", data)) > MAX_ENTITIES:
        raise NativeImportError(f"CAD/IFC source exceeds {MAX_ENTITIES} entities before native parsing.")


def read_source(path: str | Path) -> bytes:
    with Path(path).open("rb") as file:
        data = file.read(MAX_SOURCE_BYTES + 1)
    check_source(data)
    return data


def write_bounded_json(path: Path, value) -> None:
    size = 0
    with path.open("wb") as file:
        for chunk in json.JSONEncoder(allow_nan=False, separators=(",", ":")).iterencode(value):
            encoded = chunk.encode("utf-8")
            size += len(encoded)
            if size > MAX_OUTPUT_BYTES:
                raise NativeImportError("Native import serialized output exceeds 64 MiB.")
            file.write(encoded)


def _windows_job(process, name):
    """Enforce native memory/CPU limits with an OS Job, before releasing stdin."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                    ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                    ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.basic.flags = 0x2 | 0x4 | 0x8 | 0x100 | 0x200 | 0x2000
    limits.basic.process_time = CPU_SECONDS * 10_000_000
    limits.basic.job_time = CPU_SECONDS * 10_000_000
    # uv's Windows interpreter shim launches the real Python as one child.
    limits.basic.active_processes = 2
    limits.process_memory = MEMORY_BYTES
    limits.job_memory = MEMORY_BYTES
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(process._handle)):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel.CloseHandle(handle)
        raise error
    in_job = wintypes.BOOL()
    if not kernel.IsProcessInJob(wintypes.HANDLE(process._handle), handle, ctypes.byref(in_job)) or not in_job.value:
        kernel.CloseHandle(handle)
        raise NativeImportError("Native interpreter was not assigned to its resource Job.")
    return lambda: kernel.CloseHandle(handle)


def _resume_windows_process(process):
    import ctypes
    from ctypes import wintypes
    class ThreadEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("thread", wintypes.DWORD),
                    ("owner", wintypes.DWORD), ("priority", wintypes.LONG), ("delta", wintypes.LONG), ("flags", wintypes.DWORD)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x4, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ThreadEntry(size=ctypes.sizeof(ThreadEntry))
        available = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while available:
            if entry.owner == process.pid:
                thread = kernel.OpenThread(0x2, False, entry.thread)
                if not thread:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if kernel.ResumeThread(thread) == 0xffffffff:
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    kernel.CloseHandle(thread)
                return
            available = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise NativeImportError("Cannot resume the resource-limited native interpreter.")
    finally:
        kernel.CloseHandle(snapshot)


def _verify_windows_worker_job(name):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenJobObjectW(0x4, False, name)
    if not handle:
        raise NativeImportError("Native parser cannot verify its resource Job.")
    try:
        in_job = wintypes.BOOL()
        if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), handle, ctypes.byref(in_job)) or not in_job.value:
            raise NativeImportError("Native parser escaped its resource Job.")
    finally:
        kernel.CloseHandle(handle)


def run_native(operation: str, data: bytes, **options):
    """Receive only bounded JSON from a process with OS memory/CPU and wall limits."""
    if operation in {"step_mesh", "legacy_step_mesh"}:
        if len(data) > MAX_OUTPUT_BYTES:
            raise NativeImportError("Native meshing model input exceeds 64 MiB.")
    else:
        check_source(data)
    with _slots, tempfile.TemporaryDirectory(prefix="tuba-native-") as folder:
        root = Path(folder)
        source = root / ("source.step" if operation == "step" else "source.ifc")
        source.write_bytes(data)
        request, output = root / "request.json", root / "output.json"
        job_name = "TubaNative-" + uuid4().hex
        write_bounded_json(request, {"operation": operation, "source": str(source), "options": options, "job_name": job_name})
        env = dict(os.environ)
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get("PYTHONPATH", "")
        process = subprocess.Popen([sys.executable, "-m", "tuba.geometry._native_worker", str(request), str(output)],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                                   creationflags=(0x4 | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0)
        close_job = None
        try:
            if os.name == "nt":
                close_job = _windows_job(process, job_name)
                _resume_windows_process(process)
            process.stdin.write(b"1")
            process.stdin.close()
            try:
                process.wait(timeout=WALL_SECONDS)
            except subprocess.TimeoutExpired as exc:
                raise NativeImportError("Native CAD/IFC worker exceeded its 90 second wall-time budget.") from exc
            if process.returncode or not output.is_file():
                raise NativeImportError(f"Native CAD/IFC worker failed (exit {process.returncode}); memory/CPU or parser failure.")
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                raise NativeImportError("Native import serialized output exceeds 64 MiB.")
            reply = json.loads(output.read_bytes())
            if "error" in reply:
                if "mesh_review" in reply:
                    from tuba.meshing.quality import MeshQualityError
                    target = Path(options["output_path"]).with_suffix(".quality.json")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    write_bounded_json(target, reply["mesh_review"])
                    raise MeshQualityError(reply["mesh_review"])
                if reply.get("type") == "ImportError":
                    raise ImportError(reply["error"])
                if reply.get("type") == "KeyError":
                    raise KeyError(reply["error"])
                raise NativeImportError(reply["error"])
            value = reply["value"]
            if operation in {"step_mesh", "legacy_step_mesh"}:
                mesh_file = root / "mesh.med"
                if not mesh_file.is_file() or mesh_file.stat().st_size > MAX_OUTPUT_BYTES:
                    raise NativeImportError("Native MED mesh is missing or exceeds 64 MiB.")
                target = Path(options["output_path"]).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix=".tuba-native-", suffix=".med", dir=target.parent, delete=False) as file:
                    temporary = Path(file.name)
                try:
                    shutil.copyfile(mesh_file, temporary)
                    for source_path, digest in options.get("source_digests", []):
                        if hashlib.sha256(read_source(source_path)).hexdigest() != digest:
                            raise NativeImportError("STEP source changed during meshing; reimport it.")
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                if operation == "step_mesh":
                    value["analysis_mesh"]["files"]["med"] = str(target)
            return value
        except OSError as exc:
            raise NativeImportError(f"Cannot enforce native worker resource limits: {exc}") from exc
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if close_job is not None:
                close_job()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def _main():
    if sys.stdin.buffer.read(1) != b"1":
        return
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    request_path, output_path = map(Path, sys.argv[1:3])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if os.name == "nt":
            _verify_windows_worker_job(request["job_name"])
        source, options = Path(request["source"]), request["options"]
        if request["operation"] == "step":
            from tuba.geometry.step_analysis_importer import StepAnalysisImporter
            value = StepAnalysisImporter()._parse_native(source, **options)
        elif request["operation"] == "ifc_extract":
            from tuba.external.ifc_reference import _extract_native
            value = _extract_native(read_source(source), **options)
        elif request["operation"] == "ifc_convert":
            from tuba.external.ifc_reference import _convert_pipes_native
            value = _convert_pipes_native(source, **options).to_dict()
        elif request["operation"] == "ifc_model":
            from tuba.external.ifc import IfcImporter
            value = IfcImporter()._import_model_native(source).to_dict()
        elif request["operation"] == "step_mesh":
            from tuba.model import TubaModel
            from tuba.mixed import AnalysisRegion
            from tuba.meshing.policy import ResolvedMeshPolicy
            from tuba.meshing.step_component import _build_step_component_mesh_native
            model = TubaModel.from_dict(json.loads(source.read_bytes()))
            options.pop("output_path")
            options.pop("source_digests", None)
            region = options.pop("region", None)
            policy = options.pop("mesh_policy", None)
            generated = _build_step_component_mesh_native(model, request_path.parent / "mesh.med",
                region=AnalysisRegion.from_dict(region) if region else None,
                mesh_policy=ResolvedMeshPolicy(policy["data"], tuple(policy["samples"])) if policy else None, **options)
            value = {"analysis_mesh": generated.analysis_mesh.to_dict(), "groups": generated.groups,
                     "gmsh_version": generated.gmsh_version, "settings": generated.settings}
        elif request["operation"] == "legacy_step_mesh":
            from tuba.model import TubaModel
            from tuba.solver.mixed_study import MixedCodeAsterStudyExporter
            model = TubaModel.from_dict(json.loads(source.read_bytes()))
            MixedCodeAsterStudyExporter()._write_med_with_gmsh_native(model, request_path.parent / "mesh.med")
            value = {}
        else:
            raise ValueError("Unknown native import operation.")
        write_bounded_json(output_path, {"value": value})
    except Exception as exc:
        reply = {"error": str(exc)[:2000], "type": type(exc).__name__}
        if hasattr(exc, "mesh_review"):
            reply["mesh_review"] = exc.mesh_review
        write_bounded_json(output_path, reply)


if __name__ == "__main__":
    _main()
