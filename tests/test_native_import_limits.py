"""Native payload amplification is rejected and a failed worker cannot kill its host."""

from types import SimpleNamespace
import os
import subprocess
import sys

import pytest

from tuba.geometry import _native_worker as worker
from tuba.geometry import step_analysis_importer as step
from tuba.external.ifc_reference import _json_safe


def test_source_entities_property_depth_and_output_limits_fail_before_retention(tmp_path, monkeypatch):
    with pytest.raises(worker.NativeImportError, match="before native parsing"):
        worker.check_source(b"#1=X();" * (worker.MAX_ENTITIES + 1))
    props = "value"
    for _ in range(worker.MAX_PROPERTY_DEPTH + 1):
        props = {"nested": props}
    with pytest.raises(worker.NativeImportError, match="property depth"):
        _json_safe(props)
    with pytest.raises(worker.NativeImportError, match="cumulative property"):
        _json_safe({"value": 1}, [worker.MAX_PROPERTY_VALUES])
    monkeypatch.setattr(worker, "MAX_OUTPUT_BYTES", 32)
    with pytest.raises(worker.NativeImportError, match="serialized output"):
        worker.write_bounded_json(tmp_path / "bounded.json", {"value": "x" * 64})
    assert (tmp_path / "bounded.json").stat().st_size <= 32


def test_step_rejects_native_mesh_counts_before_python_arrays(monkeypatch):
    mesh = SimpleNamespace(generate=lambda _: None,
        getElements=lambda _: ([2], [range(worker.MAX_FACES + 1)], []),
        getNodes=lambda: pytest.fail("must reject faces before expanding vertices"))
    monkeypatch.setattr(step, "gmsh", SimpleNamespace(model=SimpleNamespace(mesh=mesh)))
    with pytest.raises(step.StepImportError, match="before Python mesh expansion"):
        step.StepAnalysisImporter._tessellate([])
    mesh.getElements = lambda _: ([2], [[1]], [[1, 2, 3]])
    mesh.getNodes = lambda: (range(worker.MAX_VERTICES + 1), [], None)
    with pytest.raises(step.StepImportError, match="display vertices"):
        step.StepAnalysisImporter._tessellate([])


@pytest.mark.parametrize("failure", ["crash", "timeout"])
def test_failed_native_process_does_not_affect_next_request(monkeypatch, failure):
    popen = subprocess.Popen
    events = []
    def failing_process(command, **options):
        if os.name == "nt":
            assert options["creationflags"] & 0x4, "interpreter must start suspended"
        script = "import sys, time, os; sys.stdin.buffer.read(1); " + ("os._exit(99)" if failure == "crash" else "time.sleep(15)")
        return popen([sys.executable, "-c", script], **options)
    with monkeypatch.context() as patch:
        patch.setattr(worker.subprocess, "Popen", failing_process)
        if failure == "timeout":
            patch.setattr(worker, "WALL_SECONDS", .3)
        if os.name == "nt":
            assign, resume = worker._windows_job, worker._resume_windows_process
            def assigned(process, name):
                events.append("assigned")
                return assign(process, name)
            def resumed(process):
                assert events == ["assigned"]
                events.append("resumed")
                return resume(process)
            patch.setattr(worker, "_windows_job", assigned)
            patch.setattr(worker, "_resume_windows_process", resumed)
        with pytest.raises(worker.NativeImportError, match="worker failed|wall-time"):
            worker.run_native("ifc_extract", b"ISO-10303-21;")
    # A fresh worker still runs and reports its own bounded input error.
    with pytest.raises(worker.NativeImportError, match="Unknown native import operation"):
        worker.run_native("invalid-operation", b"ISO-10303-21;")


def test_ifc_product_limit_runs_in_worker_and_host_survives():
    ifc = pytest.importorskip("ifcopenshell")
    from tuba.external.ifc_reference import extract
    file = ifc.file(schema="IFC4")
    file.create_entity("IfcProject", GlobalId=ifc.guid.new())
    for _ in range(worker.MAX_PRODUCTS + 1):
        file.create_entity("IfcPipeSegment", GlobalId=ifc.guid.new())
    with pytest.raises(worker.NativeImportError, match="before geometry extraction"):
        extract(file.to_string().encode())
    with pytest.raises(worker.NativeImportError, match="Invalid IFC STEP"):
        extract(b"invalid")


@pytest.mark.skipif(os.name != "nt", reason="Windows Job/uv child memory enforcement regression")
def test_windows_job_memory_limit_reaches_real_uv_python_child(monkeypatch):
    popen = subprocess.Popen
    script = ("import os, sys\nsys.stdin.buffer.read(1)\ntry:\n bytearray(128*1024*1024)\n"
              "except MemoryError:\n os._exit(77)\nos._exit(0)\n")
    def allocation_probe(command, **options):
        return popen([sys.executable, "-c", script], **options)
    monkeypatch.setattr(worker, "MEMORY_BYTES", 64 * 1024 * 1024)
    monkeypatch.setattr(worker.subprocess, "Popen", allocation_probe)
    with pytest.raises(worker.NativeImportError, match=r"exit 77"):
        worker.run_native("ifc_extract", b"ISO-10303-21;")
