"""Explicit native qualification; invokes and cleans only fresh token-owned trees.

Run with shared Python, this checkout on PYTHONPATH, output outside source.
The unrelated sentinel is created here and survives the tested cancellation;
its separate finally block closes only that fresh test sentinel afterwards.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from tuba.analysis.mesh_convergence import run_mesh_convergence, reopen_mesh_convergence
from tuba.solver.code_aster_process import WslExecutionController, SolverCancelled
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate
from tests.test_code_aster_node_temperatures import cantilever


def wait_receipt(controller):
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        paths = list(controller.directory.glob("runtime-*/ownership.json"))
        if paths:
            record = json.loads(paths[-1].read_text())
            assert record["pid"] == record["pgid"] == record["sid"]
            assert record["active"]
            return paths[-1], record
        time.sleep(.1)
    raise RuntimeError("Owned Linux session did not publish ownership in 30 seconds.")


def snapshot(record):
    code = "import pathlib,json; sid="+str(record["sid"])+"; rows=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit():\n  try:\n   s=(p/'stat').read_text(); a=s[s.rfind(')')+2:].split()\n   if int(a[3])==sid and a[0]!='Z': rows.append({'pid':int(p.name),'command':(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')})\n  except OSError: pass\nprint(json.dumps(rows))"
    return json.loads(subprocess.check_output(["wsl", "-d", "Ubuntu", "--", "python3", "-c", code], text=True))


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    candidate = CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", "Ubuntu", "--"))
    evidence = {"source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "changed_source": subprocess.check_output(["git", "diff", "--stat"], text=True)}
    files = subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    files += subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True).splitlines()
    evidence["tested_source_sha256"] = {name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files if Path(name).is_file()}
    tree = WslExecutionController(output / "owned-tree")
    sentinel = WslExecutionController(output / "unrelated-test-sentinel")
    with ThreadPoolExecutor(max_workers=2) as pool:
        sentinel_future = pool.submit(sentinel.execute, candidate, [*candidate.command, "bash", "-lc", "sleep 120"], None, 150, sentinel.directory)
        _, sentinel_owner = wait_receipt(sentinel)
        owned_future = pool.submit(tree.execute, candidate, [*candidate.command, "bash", "-lc", "trap '' TERM; sleep 120 & wait"], None, 150, tree.directory)
        _, owner = wait_receipt(tree)
        try:
            evidence["owned_before"] = snapshot(owner)
            evidence["sentinel_before"] = snapshot(sentinel_owner)
            tree.cancel()
            try:
                owned_future.result(timeout=20)
            except SolverCancelled:
                pass
            assert not snapshot(owner)
            evidence["owned_cleanup"] = json.loads((tree.directory / "cleanup.json").read_text())
            evidence["sentinel_after_owned_cancel"] = snapshot(sentinel_owner)
            assert evidence["sentinel_after_owned_cancel"]
        finally:
            sentinel.cancel()
            try:
                sentinel_future.result(timeout=20)
            except SolverCancelled:
                pass
    model, _ = cantilever("Native convergence")
    model.set_mesh_size(.4)
    (output / "qualification-partial.json").write_text(json.dumps(evidence, indent=2))
    model.define_load_case("Hot", gravity=False, temperature=120., ref_temperature=20., pressure=1e6)
    controller = WslExecutionController(output / "comparison")
    report = run_mesh_convergence(model, "Hot", scales=[1., .5], output_dir=controller.directory,
        solver_options={"exec_method": "wsl", "wsl_distro": "Ubuntu"}, execution_controller=controller)
    assert report["status"] == "completed", report
    assert report["distinct_successful_meshes"] == 2
    assert report["levels"][0]["mesh"]["cell_count"] != report["levels"][1]["mesh"]["cell_count"]
    assert reopen_mesh_convergence(model, controller.directory) == report
    evidence["comparison"] = report
    (output / "qualification-partial.json").write_text(json.dumps(evidence, indent=2, allow_nan=False))
    cancelled = WslExecutionController(output / "solver-cancel")
    model.set_mesh_size(.002)  # Long enough to observe the actual study payload.
    # A fresh level, not the successful study or any retained host.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_mesh_convergence, model, "Hot", scales=[.5, .25], output_dir=cancelled.directory,
            solver_options={"exec_method": "wsl", "wsl_distro": "Ubuntu"}, execution_controller=cancelled)
        _, owner = wait_receipt(cancelled)
        deadline = time.monotonic()+30
        observed = []
        while time.monotonic() < deadline:
            observed = snapshot(owner)
            messages = list((cancelled.directory / "level-00" / ".aster-work").glob("*/fort.6"))
            texts = [p.read_text(encoding="utf-8", errors="replace") for p in messages]
            if any("study.comm.changed.py" in p["command"] for p in observed) and any("Version" in text for text in texts):
                evidence["solver_computation_marker"] = [{"path":str(p), "size_bytes":p.stat().st_size,
                    "text_prefix":text[:4000]} for p,text in zip(messages, texts)]
                break
            time.sleep(.1)
        assert any("study.comm.changed.py" in p["command"] for p in observed) and evidence.get("solver_computation_marker"), observed
        evidence["solver_before_cancel"] = observed
        cancelled.cancel()
        try:
            future.result(timeout=20)
        except SolverCancelled:
            pass
        assert not snapshot(owner)
        saved = json.loads((cancelled.directory / "comparison.json").read_text())
        assert saved["status"] != "completed"
        assert not (cancelled.directory / "level-01").exists()
        evidence["cancelled_comparison"] = saved
        evidence["solver_cleanup"] = json.loads((cancelled.directory / "cleanup.json").read_text())
    (output / "qualification.json").write_text(json.dumps(evidence, indent=2, allow_nan=False))
    print(json.dumps({"passed": True, "levels": [{"scale":l["scale"], "mesh":l["mesh"], "measurements":l["measurements"]} for l in report["levels"]],
                      "owned_cancel_verified": True, "solver_cancel_verified": True}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
