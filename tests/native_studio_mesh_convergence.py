"""Fresh task-owned native HTTP/browser host lifecycle; no prior host is stopped."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

from tuba.visualization.preview.server import ProjectStudioServer
from tests.test_studio_analysis_mesh import request


SOURCE = '''from tests.test_code_aster_node_temperatures import cantilever
model, tip = cantilever("Native convergence")
model.set_mesh_size(.4)
model.define_load_case("Hot", gravity=False, temperature=120., ref_temperature=20., pressure=1e6)
'''
STUDY = '''LOAD_CASES = ("Hot",)
MESH_CONVERGENCE = {"scales": [1., .5], "relative_tolerance": .05}
'''


def main(output):
    project = output / "project"
    project.mkdir(parents=True,exist_ok=True)
    (project / "model.py").write_text(SOURCE,newline="")
    (project / "study.py").write_text(STUDY,newline="")
    os.environ["TUBA_CODE_ASTER_EXEC_METHOD"]="wsl"
    os.environ["TUBA_CODE_ASTER_WSL_DISTRO"]="Ubuntu"
    out = output / "out"
    server = ProjectStudioServer(project,out,port=0,poll_interval_s=60).start()
    try:
        files=subprocess.check_output(["git","diff","--name-only"],text=True).splitlines()
        files+=subprocess.check_output(["git","ls-files","--others","--exclude-standard"],text=True).splitlines()
        (output / "tested-source-hashes.json").write_text(json.dumps({name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files if Path(name).is_file()},indent=2))
        print(json.dumps({"native_url":server.base_url}),flush=True)
        subprocess.run(["node","viewer/scripts/mesh-convergence.mjs",server.base_url,str(output / "browser")],check=True)
        timings=[]
        for _ in range(4):
            start=time.monotonic()
            status,job=request(server)
            timings.append(time.monotonic()-start)
            assert status==200 and job["current"]
        source_start=time.monotonic()
        assert server.execute_python_code(SOURCE)["ok"]
        source_elapsed=time.monotonic()-source_start
        (output / "responsiveness.json").write_text(json.dumps({"poll_seconds":timings,"python_seconds":source_elapsed}))
        assert max(timings)<1., timings
        assert source_elapsed<2.,source_elapsed
    finally:
        server.stop() # Fresh host explicitly owned by this test's lifecycle.
    reopened=ProjectStudioServer(project,out,port=0,poll_interval_s=60).start()
    try:
        assert request(reopened)[1]["current"]
        job=reopened.mesh_jobs._job
        artifact=Path(job["directory"]) / "level-00" / "study_depl.csv"
        artifact.write_bytes(artifact.read_bytes()+b"corrupt appended bytes")
        status,job=request(reopened)
        assert status==200 and job["state"]=="failed" and not job["current"]
        scene=json.loads((out / "build" / "scene.json").read_text())
        assert not any(layer.get("mesh_identity",{}).get("mesh_review",{}).get("comparison") for layer in scene["layers"])
        (output / "corrupt-cache-status.json").write_text(json.dumps(job,indent=2))
    finally:
        reopened.stop()


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve())
